#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/token_verifier.py — TokenVerifier de produção do EDE MCP
Server (Gate 6.3-D2 §5, ADR-0016).

Implementa o `mcp.server.auth.provider.TokenVerifier` do SDK MCP 2.2.0.
O EDE é RESOURCE SERVER; Descope é o Authorization Server. Este módulo
NUNCA emite token, nunca implementa endpoint de autorização e nunca
conhece client secret — só VERIFICA o que chega.

Cadeia de verificação, nesta ordem, cada etapa fail-closed:

    Bearer extraído (feito pelo BearerAuthBackend do SDK)
      -> cabeçalho JOSE lido SEM confiar nele
      -> jku / jwk / x5u presentes?  -> REJEITA
      -> alg != RS256               -> REJEITA (inclui "none")
      -> kid ausente                -> REJEITA
      -> chave obtida SOMENTE do JWKS configurado
      -> assinatura verificada (RS256)
      -> exp / nbf com skew limitado (60s)
      -> iss exatamente igual ao configurado
      -> aud com pertinência EXATA ao conjunto aceito
      -> scope parseado (RFC 6749 3.3)
      -> AccessToken devolvido ao SDK

Qualquer falha devolve `None` — que o `BearerAuthBackend` traduz em
"não autenticado" e o `RequireAuthMiddleware` em 401, ANTES de qualquer
dispatch de tool. Nenhuma exceção vaza para a resposta HTTP e nenhum
detalhe do token entra no log (ver mcp_server/auth_logging.py).

POR QUE O TOKEN NÃO PODE ESCOLHER A CHAVE
=========================================
`jku`, `jwk` e `x5u` são campos do cabeçalho JOSE que apontam para (ou
embutem) material de chave escolhido por quem assinou — isto é, pelo
atacante, num token forjado. Aceitar qualquer um deles transformaria a
verificação de assinatura em teatro: o token provaria apenas que foi
assinado pela chave que ele próprio indicou. Aqui a chave vem
EXCLUSIVAMENTE do `jwks_uri` configurado. `x5c` (cadeia de certificados
embutida) não é rejeitado porque é INERTE nesta implementação — a chave
nunca é derivada do token, só do JWKS configurado; ele simplesmente não
é consultado.

POLÍTICA DE CACHE DO JWKS (Gate 6.3-D2 §5 — "documente as semânticas")
======================================================================
1. Um refresh bem-sucedido substitui o conjunto de chaves inteiro e
   marca o instante da busca.
2. `kid` presente no cache e cache DENTRO do TTL
   (`jwks_cache_ttl_seconds`, padrão 600s) -> usa o cache, sem rede.
3. `kid` AUSENTE do cache -> força um refresh (rotação de chave é
   normal), mas no máximo um a cada `jwks_min_refresh_interval_seconds`
   (padrão 30s). Dentro desse intervalo, um `kid` desconhecido é
   rejeitado SEM ir à rede — é isso que impede um atacante de usar
   `kid` aleatório para gerar tráfego ilimitado contra o Authorization
   Server, e é por isso que não existe laço de retry.
4. Cache FORA do TTL -> refresh obrigatório antes de usar qualquer
   chave. Se esse refresh falhar, a verificação é REJEITADA. Não existe
   fail-open com chave velha além do TTL.
5. Refresh falhou, mas o cache ainda está DENTRO do TTL e contém o
   `kid` -> a chave em cache é usada. Esta é a única tolerância a
   indisponibilidade, é limitada pelo TTL e é deliberada: um blip do
   JWKS não deve derrubar sessões legítimas.
6. JWKS malformado (JSON inválido, sem `keys`, chave sem `kid`, mais de
   `jwks_max_keys` chaves) -> rejeitado e o cache VÁLIDO existente é
   preservado, nunca sobrescrito por resposta corrompida; o instante da
   última busca bem-sucedida também não avança.
7. Toda busca tem timeout limitado e User-Agent explícito.
8. Uma tentativa HTTP por refresh. Nenhuma repetição automática.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Final

import httpx2
import jwt
from jwt import PyJWK
from jwt.exceptions import (
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    MissingRequiredClaimError,
    PyJWTError,
)
from mcp.server.auth.provider import AccessToken

from auth_config import EdeAuthConfig, ConfiguracaoAuthInvalida, separar_escopos
import auth_logging as telemetria

ALGORITMOS_PERMITIDOS: Final = ("RS256",)
"""Allowlist explícita. Passar a lista ao PyJWT é o que impede confusão de
algoritmo (um token HS256 assinado com a chave PÚBLICA RSA como segredo)
e `alg=none`. O cabeçalho ainda é checado antes, para que a rejeição seja
categorizada com precisão na telemetria."""

CABECALHOS_JOSE_PROIBIDOS: Final = ("jku", "jwk", "x5u")

USER_AGENT_JWKS: Final = "ede-legal-mcp/jwks-client"
"""User-Agent explícito (Gate 6.3-D2 §5). Um Authorization Server pode
exigi-lo, e ele torna o tráfego do EDE identificável no lado do Descope."""


class ErroJwks(RuntimeError):
    """Falha ao obter uma chave utilizável. Carrega a CATEGORIA do motivo
    (vocabulário fechado de auth_logging), nunca a mensagem crua."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class CacheJwks:
    """Cache limitado de chaves públicas JWKS. Semântica no topo do módulo."""

    def __init__(
        self,
        config: EdeAuthConfig,
        *,
        cliente_http: httpx2.AsyncClient | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._cliente_http = cliente_http
        self._relogio = relogio
        self._chaves: dict[str, PyJWK] = {}
        self._buscado_em: float | None = None
        self._ultima_tentativa_em: float | None = None
        self.buscas_realizadas = 0
        """Contador de buscas HTTP efetivamente disparadas — é o que prova,
        na suíte, que o cache evita rede e que o rate limit segura o
        refresh por `kid` desconhecido."""

    # ------------------------------------------------------------ estado

    @property
    def kids_em_cache(self) -> tuple[str, ...]:
        return tuple(self._chaves)

    def _cache_fresco(self, agora: float) -> bool:
        if self._buscado_em is None:
            return False
        return (agora - self._buscado_em) < self._config.jwks_cache_ttl_seconds

    def _pode_tentar_refresh(self, agora: float) -> bool:
        if self._ultima_tentativa_em is None:
            return True
        return (
            agora - self._ultima_tentativa_em
        ) >= self._config.jwks_min_refresh_interval_seconds

    # ------------------------------------------------------------ rede

    async def _corpo_bruto(self) -> str:
        cliente = self._cliente_http
        if cliente is not None:
            resposta = await cliente.get(
                self._config.jwks_uri,
                headers={"User-Agent": USER_AGENT_JWKS, "Accept": "application/json"},
                timeout=self._config.jwks_timeout_seconds,
            )
            resposta.raise_for_status()
            return resposta.text
        async with httpx2.AsyncClient(timeout=self._config.jwks_timeout_seconds) as proprio:
            resposta = await proprio.get(
                self._config.jwks_uri,
                headers={"User-Agent": USER_AGENT_JWKS, "Accept": "application/json"},
            )
            resposta.raise_for_status()
            return resposta.text

    def _interpretar(self, corpo: str) -> dict[str, PyJWK]:
        """Converte o corpo bruto em chaves utilizáveis, ou levanta
        `ErroJwks(MOTIVO_JWKS_MALFORMADO)`. Nunca devolve conjunto
        parcial silenciosamente."""
        try:
            documento = json.loads(corpo)
        except ValueError as erro:
            raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO) from erro
        if not isinstance(documento, dict):
            raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)
        lista = documento.get("keys")
        if not isinstance(lista, list) or not lista:
            raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)
        if len(lista) > self._config.jwks_max_keys:
            # Limite de tamanho: uma resposta enorme não pode consumir
            # memória do processo nem "empurrar" chaves legítimas.
            raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)

        chaves: dict[str, PyJWK] = {}
        for entrada in lista:
            if not isinstance(entrada, dict):
                raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)
            kid = entrada.get("kid")
            if not isinstance(kid, str) or not kid:
                raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)
            if entrada.get("kty") != "RSA":
                # Chave de outro tipo não serve para RS256; ignorar é
                # legítimo (o JWKS pode servir outros consumidores), mas
                # nunca vira erro nem chave utilizável.
                continue
            try:
                chaves[kid] = PyJWK(entrada, algorithm="RS256")
            except Exception as erro:  # material de chave inválido
                raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO) from erro
        if not chaves:
            raise ErroJwks(telemetria.MOTIVO_JWKS_MALFORMADO)
        return chaves

    async def _atualizar(self, agora: float) -> None:
        """Uma única tentativa. Sucesso substitui o conjunto inteiro;
        falha preserva o cache existente (que só será usado se ainda
        estiver dentro do TTL — regras 4/5/6 do topo do módulo)."""
        self._ultima_tentativa_em = agora
        self.buscas_realizadas += 1
        try:
            corpo = await self._corpo_bruto()
        except ErroJwks:
            raise
        except Exception as erro:
            raise ErroJwks(telemetria.MOTIVO_JWKS_INDISPONIVEL) from erro
        chaves = self._interpretar(corpo)
        self._chaves = chaves
        self._buscado_em = agora

    # ------------------------------------------------------------ leitura

    async def obter_chave(self, kid: str) -> PyJWK:
        agora = self._relogio()
        fresco = self._cache_fresco(agora)

        if fresco and kid in self._chaves:
            return self._chaves[kid]

        if not self._pode_tentar_refresh(agora):
            # Rate limit do refresh: nem ida à rede, nem chave fora do
            # TTL. Sem isto, `kid` aleatório viraria amplificador de
            # tráfego contra o Authorization Server.
            if fresco and kid in self._chaves:
                return self._chaves[kid]
            raise ErroJwks(telemetria.MOTIVO_CHAVE_DESCONHECIDA)

        try:
            await self._atualizar(agora)
        except ErroJwks:
            # Tolerância limitada e explícita (regra 5): só dentro do TTL.
            if self._cache_fresco(agora) and kid in self._chaves:
                return self._chaves[kid]
            raise

        chave = self._chaves.get(kid)
        if chave is None:
            raise ErroJwks(telemetria.MOTIVO_CHAVE_DESCONHECIDA)
        return chave


class EdeTokenVerifier:
    """`TokenVerifier` do SDK MCP 2.2.0, com validação exata de audience.

    Estruturalmente incapaz de "passar mesmo assim": todo caminho de
    falha termina em `None`."""

    def __init__(
        self,
        config: EdeAuthConfig,
        *,
        cache: CacheJwks | None = None,
        cliente_http: httpx2.AsyncClient | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._cache = cache or CacheJwks(
            config, cliente_http=cliente_http, relogio=relogio
        )

    @property
    def cache(self) -> CacheJwks:
        return self._cache

    # -------------------------------------------------------- auxiliares

    def _rejeitar(self, motivo: str) -> None:
        telemetria.registrar_evento(
            telemetria.EVENTO_REQUISICAO_HTTP,
            resultado_auth=telemetria.AUTH_INVALIDA,
            motivo=motivo,
            issuer=self._config.issuer,
            audiencias_aceitas=len(self._config.accepted_audiences),
            migracao_audiencia=self._config.migracao_de_audiencia_ativa,
        )

    def _audiencias_do_token(self, claims: dict[str, Any]) -> tuple[str, ...]:
        """Extrai `aud` com tipagem ESTRITA: string única ou lista de
        strings. Qualquer outra forma é malformada.

        Esta é uma checagem INDEPENDENTE da que o PyJWT já fez com
        `audience=` — duas verificações exatas separadas, para que um
        eventual afrouxamento futuro da biblioteca não passe despercebido,
        e para descobrir QUAL audience casou (vira `AccessToken.resource`
        / indicador RFC 8707)."""
        bruto = claims.get("aud")
        if isinstance(bruto, str):
            valores: tuple[str, ...] = (bruto,)
        elif isinstance(bruto, list) and bruto:
            if not all(isinstance(item, str) for item in bruto):
                return ()
            valores = tuple(bruto)
        else:
            return ()
        aceitas = self._config.accepted_audiences
        # Pertinência EXATA de conjunto. Nunca prefixo, sufixo, substring,
        # comparação por hostname ou normalização de barra final.
        return tuple(valor for valor in valores if valor in aceitas)

    def _principal(self, claims: dict[str, Any]) -> str | None:
        """Identificador do cliente. `AccessToken.client_id` é obrigatório
        no SDK; sem nenhum destes, o principal é indeterminado e o token é
        recusado — nunca preenchido com um valor inventado."""
        for candidato in ("azp", "client_id", "sub"):
            valor = claims.get(candidato)
            if isinstance(valor, str) and valor:
                return valor
        return None

    # ------------------------------------------------------- verificação

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not token.strip():
            self._rejeitar(telemetria.MOTIVO_BEARER_AUSENTE)
            return None

        try:
            cabecalho = jwt.get_unverified_header(token)
        except PyJWTError:
            self._rejeitar(telemetria.MOTIVO_JWT_MALFORMADO)
            return None
        except Exception:
            self._rejeitar(telemetria.MOTIVO_JWT_MALFORMADO)
            return None

        if not isinstance(cabecalho, dict):
            self._rejeitar(telemetria.MOTIVO_JWT_MALFORMADO)
            return None

        presentes = [c for c in CABECALHOS_JOSE_PROIBIDOS if c in cabecalho]
        if presentes:
            # O token não escolhe a fonte de chave. Ver topo do módulo.
            self._rejeitar(telemetria.MOTIVO_CABECALHO_JOSE_PROIBIDO)
            return None

        if cabecalho.get("alg") not in ALGORITMOS_PERMITIDOS:
            self._rejeitar(telemetria.MOTIVO_ALGORITMO_NAO_PERMITIDO)
            return None

        kid = cabecalho.get("kid")
        if not isinstance(kid, str) or not kid:
            self._rejeitar(telemetria.MOTIVO_KID_AUSENTE)
            return None

        try:
            chave = await self._cache.obter_chave(kid)
        except ErroJwks as erro:
            self._rejeitar(erro.motivo)
            return None
        except Exception:
            self._rejeitar(telemetria.MOTIVO_JWKS_INDISPONIVEL)
            return None

        try:
            claims = jwt.decode(
                token,
                key=chave,
                algorithms=list(ALGORITMOS_PERMITIDOS),
                audience=list(self._config.accepted_audiences),
                issuer=self._config.issuer,
                leeway=self._config.clock_skew_seconds,
                options={
                    "require": ["exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except ExpiredSignatureError:
            self._rejeitar(telemetria.MOTIVO_EXPIRADO)
            return None
        except ImmatureSignatureError:
            self._rejeitar(telemetria.MOTIVO_AINDA_NAO_VALIDO)
            return None
        except InvalidIssuerError:
            self._rejeitar(telemetria.MOTIVO_ISSUER_INVALIDO)
            return None
        except InvalidAudienceError:
            self._rejeitar(telemetria.MOTIVO_AUDIENCIA_INVALIDA)
            return None
        except MissingRequiredClaimError as erro:
            motivo = (
                telemetria.MOTIVO_AUDIENCIA_AUSENTE
                if getattr(erro, "claim", None) == "aud"
                else telemetria.MOTIVO_CLAIMS_MALFORMADAS
            )
            self._rejeitar(motivo)
            return None
        except InvalidSignatureError:
            self._rejeitar(telemetria.MOTIVO_ASSINATURA_INVALIDA)
            return None
        except PyJWTError:
            self._rejeitar(telemetria.MOTIVO_JWT_MALFORMADO)
            return None
        except Exception:
            self._rejeitar(telemetria.MOTIVO_JWT_MALFORMADO)
            return None

        if not isinstance(claims, dict):
            self._rejeitar(telemetria.MOTIVO_CLAIMS_MALFORMADAS)
            return None

        casadas = self._audiencias_do_token(claims)
        if not casadas:
            # Só alcançável se o PyJWT tiver aceitado algo que a nossa
            # checagem exata recusa. Fail-closed de propósito.
            self._rejeitar(telemetria.MOTIVO_AUDIENCIA_INVALIDA)
            return None

        bruto_escopo = claims.get("scope")
        if bruto_escopo is None:
            escopos: tuple[str, ...] = ()
        elif isinstance(bruto_escopo, str):
            try:
                escopos = separar_escopos(bruto_escopo)
            except ConfiguracaoAuthInvalida:
                self._rejeitar(telemetria.MOTIVO_ESCOPO_MALFORMADO)
                return None
        else:
            self._rejeitar(telemetria.MOTIVO_ESCOPO_MALFORMADO)
            return None

        cliente = self._principal(claims)
        if cliente is None:
            self._rejeitar(telemetria.MOTIVO_PRINCIPAL_INDETERMINADO)
            return None

        expiracao = claims.get("exp")
        if not isinstance(expiracao, (int, float)):
            self._rejeitar(telemetria.MOTIVO_CLAIMS_MALFORMADAS)
            return None

        sujeito = claims.get("sub")
        return AccessToken(
            token=token,
            client_id=cliente,
            scopes=list(escopos),
            expires_at=int(expiracao),
            # Indicador RFC 8707: a audience que de fato casou. Com uma
            # única audience aceita (operação normal) é sempre o Resource
            # canônico; numa janela de migração explícita pode ser a
            # audience legada autorizada.
            resource=casadas[0],
            subject=sujeito if isinstance(sujeito, str) else None,
            # Somente `iss` — o SDK usa essa claim para identificar o
            # principal (`principal_components`). O payload completo NUNCA
            # é propagado: quanto menos do token circula no processo,
            # menor a superfície para vazamento acidental em log.
            claims={"iss": claims.get("iss")},
        )
