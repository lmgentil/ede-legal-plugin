#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/auth_config.py — configuração canônica de OAuth do EDE MCP
Server (Gate 6.3-D2, ADR-0016).

Este módulo NÃO fala protocolo, NÃO valida token e NÃO conhece JWT: ele
só resolve, valida e congela a identidade OAuth deste Resource Server —
qual é o Resource canônico, qual é o issuer esperado, onde fica o JWKS,
quais audiences são aceitas, quais escopos são exigidos e qual Host é
legítimo. Tudo o que depende disso (verificador de token, telemetria,
proteção contra DNS rebinding) consome `EdeAuthConfig` já validado, nunca
lê o ambiente por conta própria.

DECISÃO ESTRUTURAL — UM ÚNICO RESOURCE CANÔNICO
===============================================
O EDE MCP anuncia EXATAMENTE UM Resource (RFC 9728), sempre: o
`canonical_resource`. Não existe modo "vários resources", nem anúncio
alternativo, nem hostname legado co-canônico. O Cloud Run pode rotear
mais de um hostname para o mesmo serviço; isso NUNCA torna o hostname
alternativo canônico, não entra no PRM e não é aceito como Host.

O URI final de produção NÃO é hardcoded aqui, de propósito: o serviço
`ede-mcp` ainda não existe (o Gate 6.3-D2 é implementação de repositório;
nenhuma migração de nuvem está autorizada). A forma esperada é

    https://ede-mcp-<PROJECT_NUMBER>.southamerica-east1.run.app/mcp

mas o valor exato é INJETADO em runtime (`EDE_MCP_RESOURCE`) quando o
serviço de produção for criado. `ede-mcp-staging` permanece staging e
nunca vira a identidade OAuth permanente (ADR-0016).

AUDIENCE — EXATIDÃO, NUNCA ALARGAMENTO IMPLÍCITO
================================================
`accepted_audiences` é, na operação normal, exatamente
`(canonical_resource,)` — um elemento. A lista com mais de um elemento
existe SÓ para tornar possível uma futura migração controlada
`run.app` -> domínio customizado sem rearquitetar o verificador, e:

  * precisa ser declarada explicitamente (`EDE_MCP_ACCEPTED_AUDIENCES`);
  * cada entrada é validada com o mesmo rigor do Resource canônico;
  * o `canonical_resource` precisa estar contido nela;
  * a condição fica visível na telemetria de startup
    (`migracao_de_audiencia_ativa`, ver mcp_server/auth_logging.py);
  * o PRM CONTINUA anunciando um único Resource;
  * curinga ("*") é rejeitado em qualquer posição — não existe audience
    coringa, nem por prefixo, nem por sufixo, nem "mesmo host".

Nenhum alargamento acontece por omissão: sem `EDE_MCP_ACCEPTED_AUDIENCES`
a lista é derivada do Resource canônico e tem tamanho 1.

MODO AUTH — POR QUE É OPT-IN NESTE GATE
=======================================
`EDE_MCP_AUTH_ENABLED` liga a camada OAuth de aplicação. Com ela
desligada, o servidor mantém exatamente o comportamento das Etapas
6.1/6.2 (o staging atual é protegido por IAM de INFRAESTRUTURA do Cloud
Run, nunca por autorização de aplicação — ADR-0016: identidade de
infraestrutura Google NÃO é autorização de aplicação EDE). Isso é estado
conhecido e declarado, não disfarçado: `main()` emite telemetria de
startup dizendo que a autorização de aplicação está DESLIGADA.

O que NUNCA pode acontecer é configuração pela metade virar
"silenciosamente sem autenticação": se QUALQUER variável `EDE_MCP_*` de
auth estiver presente sem `EDE_MCP_AUTH_ENABLED` verdadeira, o servidor
RECUSA subir (`ConfiguracaoAuthInvalida`) — fail-closed (CLAUDE.md §17).
E com `EDE_MCP_AUTH_ENABLED` verdadeira, toda a configuração obrigatória
precisa estar presente e bem formada, ou o servidor também recusa subir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final, Mapping
from urllib.parse import urlsplit

# --------------------------------------------------------------- escopos

ESCOPO_HEALTH: Final = "ede:health"
"""Funcionalidade operacional/sintética/health. NUNCA autoriza operação
jurídica determinística do Core (ver ESCOPO_LEGAL)."""

ESCOPO_LEGAL: Final = "ede:legal"
"""Reservado à funcionalidade jurídica protegida do Core. Nenhuma tool
legal existe neste gate; nenhum principal recebe este escopo só por ter
autenticado com sucesso (autenticação != autorização)."""

ESCOPOS_CONHECIDOS: Final = (ESCOPO_HEALTH, ESCOPO_LEGAL)

ESCOPOS_EXIGIDOS_PADRAO: Final = (ESCOPO_HEALTH,)
"""Escopo de BASE do transporte: o mínimo para alcançar QUALQUER dispatch
MCP neste servidor. Hoje é exato (não excessivo) porque toda a superfície
exposta é operacional/health. Quando tools `ede:legal` forem criadas
(gate posterior, nunca aqui), esta base precisa ser reavaliada
explicitamente — ver mcp_server/scope_policy.py, que já faz a exigência
POR FERRAMENTA, independente desta."""

# ------------------------------------------------------------- variáveis

VAR_AUTH_ENABLED: Final = "EDE_MCP_AUTH_ENABLED"
VAR_RESOURCE: Final = "EDE_MCP_RESOURCE"
VAR_ISSUER: Final = "EDE_MCP_ISSUER"
VAR_JWKS_URI: Final = "EDE_MCP_JWKS_URI"
VAR_AUDIENCES: Final = "EDE_MCP_ACCEPTED_AUDIENCES"
VAR_REQUIRED_SCOPES: Final = "EDE_MCP_REQUIRED_SCOPES"
VAR_ALLOWED_ORIGINS: Final = "EDE_MCP_ALLOWED_ORIGINS"
VAR_CANONICAL_HOST: Final = "EDE_MCP_CANONICAL_HOST"

VAR_K_SERVICE: Final = "K_SERVICE"
"""Injetada pela própria plataforma Cloud Run em todo serviço — nunca por
configuração externa esquecível. Base do guard de produção abaixo."""

NOME_SERVICO_PRODUCAO: Final = "ede-mcp"
"""Nome do serviço Cloud Run de produção (Gate 6.3-D3.0/D3.1, ADR-0017).
Amarrado deliberadamente a este único nome — nunca generalizado para
qualquer `K_SERVICE`: `ede-mcp-staging`, o serviço de prova descartável,
desenvolvimento local e a suíte de testes continuam podendo rodar com a
camada OAuth desligada, exatamente como antes (ADR-0016). Só o serviço
que se anuncia como `ede-mcp` fica sob a obrigação desta seção."""

VARIAVEIS_DE_AUTH: Final = (
    VAR_RESOURCE,
    VAR_ISSUER,
    VAR_JWKS_URI,
    VAR_AUDIENCES,
    VAR_REQUIRED_SCOPES,
    VAR_ALLOWED_ORIGINS,
    VAR_CANONICAL_HOST,
)
"""Variáveis que só fazem sentido com a camada OAuth ligada. Qualquer uma
delas presente com VAR_AUTH_ENABLED falsa/ausente é configuração pela
metade -> recusa de subida, nunca degradação para anônimo."""

_VALORES_VERDADEIROS: Final = frozenset({"1", "true", "yes", "on", "sim"})
_VALORES_FALSOS: Final = frozenset({"0", "false", "no", "off", "nao", ""})

TOLERANCIA_RELOGIO_SEGUNDOS: Final = 60
"""Skew limitado e fixo (Gate 6.3-D2 §5). Não configurável de propósito:
um skew maior é decisão de segurança, não de ambiente."""


class ConfiguracaoAuthInvalida(ValueError):
    """Configuração OAuth ausente, malformada ou internamente
    inconsistente. Sempre fatal: o servidor recusa subir (CLAUDE.md §17)
    em vez de servir rota protegida com identidade duvidosa."""


class ProducaoSemAuthInvalida(ConfiguracaoAuthInvalida):
    """INV-PRODUCAO-AUTH-OBRIGATORIA (Gate 6.3-D3.1, ADR-0017):
    `K_SERVICE` identifica o serviço Cloud Run de produção
    (`NOME_SERVICO_PRODUCAO`) mas a camada OAuth de aplicação não está
    corretamente habilitada. Achado do Gate 6.3-D3.0: com toda variável
    `EDE_MCP_*` ausente, a auth desliga por design — comportamento
    aceitável para staging/local (ADR-0016), mas nunca para produção,
    onde um deploy mal configurado seguido de `allUsers` exporia o
    servidor sem autenticação alguma. Fail-closed específico e
    intransferível: produção nunca alcança o dispatcher MCP com
    autenticação desligada, mesmo que a omissão de
    `EDE_MCP_AUTH_ENABLED` fosse tolerada em outro ambiente."""


# ------------------------------------------------------------ validadores

def _exigir_texto(valor: str | None, variavel: str) -> str:
    if valor is None or not valor.strip():
        raise ConfiguracaoAuthInvalida(
            f"{variavel} é obrigatória quando {VAR_AUTH_ENABLED} está ligada e "
            f"não pode ser vazia."
        )
    return valor.strip()


def _validar_uri_https(valor: str, rotulo: str) -> str:
    """URI absoluta, HTTPS, sem curinga, sem userinfo, sem query/fragmento.

    HTTPS é exigido SEMPRE — não existe escape hatch de "ambiente local"
    aqui. Os testes usam URIs sintéticas `https://...invalid/...`
    (RFC 2606), que nunca resolvem na internet: isso mantém a regra de
    produção literalmente a mesma que a suíte exercita, em vez de criar um
    segundo caminho de código que a produção nunca percorre."""
    if "*" in valor:
        raise ConfiguracaoAuthInvalida(
            f"{rotulo} não pode conter curinga: {valor!r}. Audience/Resource do EDE "
            f"são sempre URIs exatas — não existe correspondência por prefixo, "
            f"sufixo, substring ou hostname."
        )
    if any(caractere.isspace() for caractere in valor):
        raise ConfiguracaoAuthInvalida(
            f"{rotulo} não pode conter espaço em branco: {valor!r}."
        )

    partes = urlsplit(valor)
    if partes.scheme != "https":
        raise ConfiguracaoAuthInvalida(
            f"{rotulo} precisa ser HTTPS (recebido esquema {partes.scheme!r} em "
            f"{valor!r}). Resource/issuer/JWKS de produção nunca trafegam em texto claro."
        )
    if not partes.netloc:
        raise ConfiguracaoAuthInvalida(f"{rotulo} precisa ter host: {valor!r}.")
    if "@" in partes.netloc:
        raise ConfiguracaoAuthInvalida(f"{rotulo} não pode carregar userinfo: {valor!r}.")
    if partes.query or partes.fragment:
        raise ConfiguracaoAuthInvalida(
            f"{rotulo} não pode ter query string nem fragmento: {valor!r}."
        )
    if partes.path not in ("", "/") and valor.endswith("/"):
        raise ConfiguracaoAuthInvalida(
            f"{rotulo} não pode terminar em barra: {valor!r}. A comparação de "
            f"Resource/issuer é string exata (RFC 8414/9207) — uma barra sobrando "
            f"muda a identidade."
        )
    return valor


def _validar_token_de_escopo(token: str) -> str:
    """RFC 6749 3.3: scope-token = 1*( %x21 / %x23-5B / %x5D-7E ).

    Ou seja: ASCII imprimível, exceto espaço (0x20), aspas duplas (0x22) e
    barra invertida (0x5C)."""
    if not token:
        raise ConfiguracaoAuthInvalida(
            "escopo vazio não é um scope-token válido (RFC 6749 3.3)."
        )
    for caractere in token:
        ponto = ord(caractere)
        if ponto == 0x21 or 0x23 <= ponto <= 0x5B or 0x5D <= ponto <= 0x7E:
            continue
        raise ConfiguracaoAuthInvalida(
            f"escopo {token!r} contém caractere inválido {caractere!r} — RFC 6749 3.3 "
            f"admite só ASCII imprimível fora de espaço, aspas duplas e barra invertida."
        )
    return token


def separar_escopos(bruto: str | None) -> tuple[str, ...]:
    """Semântica padrão de `scope`: lista separada por ESPAÇO (RFC 6749
    3.3), preservando a ordem e sem duplicatas.

    Aceita qualquer espaço em branco como separador (um cliente que mande
    tabulação ou quebra de linha não vira um escopo inventado). Cada token
    é validado: escopo malformado faz a leitura INTEIRA falhar — nunca
    "aproveita os válidos e ignora o resto", que seria degradar
    silenciosamente a autorização."""
    if bruto is None:
        return ()
    vistos: list[str] = []
    for token in bruto.split():
        _validar_token_de_escopo(token)
        if token not in vistos:
            vistos.append(token)
    return tuple(vistos)


def _separar_lista_de_uris(bruto: str) -> list[str]:
    """Aceita separação por espaço e/ou vírgula (as duas convenções que
    aparecem em plataforma de deploy), preservando ordem e DUPLICATAS — a
    duplicata é rejeitada depois, explicitamente, em vez de silenciada
    aqui."""
    return [item for item in bruto.replace(",", " ").split() if item]


def _validar_origem_permitida(valor: str) -> str:
    """Origin é uma origem serializada (`esquema://host[:porta]`), sem
    caminho. Aceita http só para loopback explícito, que é o único caso em
    que um Origin de navegador legítimo não seria HTTPS."""
    partes = urlsplit(valor)
    if partes.path or partes.query or partes.fragment:
        raise ConfiguracaoAuthInvalida(
            f"Origin permitida precisa ser uma origem serializada "
            f"(esquema://host[:porta]), sem caminho: {valor!r}."
        )
    if partes.scheme == "https":
        return valor
    if partes.scheme == "http" and partes.hostname in ("127.0.0.1", "localhost", "::1"):
        return valor
    raise ConfiguracaoAuthInvalida(
        f"Origin permitida precisa ser HTTPS (ou HTTP em loopback): {valor!r}."
    )


def _interpretar_booleano(bruto: str | None, variavel: str) -> bool:
    if bruto is None:
        return False
    normalizado = bruto.strip().lower()
    if normalizado in _VALORES_VERDADEIROS:
        return True
    if normalizado in _VALORES_FALSOS:
        return False
    raise ConfiguracaoAuthInvalida(
        f"{variavel} precisa ser um booleano reconhecível; recebido {bruto!r}."
    )


# ---------------------------------------------------------------- config

@dataclass(frozen=True)
class EdeAuthConfig:
    """Identidade OAuth validada e imutável deste Resource Server.

    Construir esta dataclass JÁ É a validação: `__post_init__` recusa
    qualquer combinação inválida. Não existe instância "parcialmente
    válida" circulando pelo processo."""

    canonical_resource: str
    issuer: str
    jwks_uri: str
    accepted_audiences: tuple[str, ...]
    required_scopes: tuple[str, ...] = ESCOPOS_EXIGIDOS_PADRAO
    allowed_origins: tuple[str, ...] = ()
    canonical_host: str = ""
    clock_skew_seconds: int = TOLERANCIA_RELOGIO_SEGUNDOS

    # Política do cache de JWKS — documentada em mcp_server/token_verifier.py.
    jwks_timeout_seconds: float = 5.0
    jwks_cache_ttl_seconds: float = 600.0
    jwks_max_keys: int = 20
    jwks_min_refresh_interval_seconds: float = 30.0

    variaveis_definidas: tuple[str, ...] = field(default=(), repr=False, compare=False)

    def __post_init__(self) -> None:
        _validar_uri_https(self.canonical_resource, "Resource canônico")
        _validar_uri_https(self.issuer, "issuer esperado")
        _validar_uri_https(self.jwks_uri, "JWKS URI")

        if not self.accepted_audiences:
            raise ConfiguracaoAuthInvalida(
                "conjunto de audiences aceitas vazio. Audience vazia aceitaria qualquer "
                "token que passasse pelas demais validações — proibido."
            )
        for audiencia in self.accepted_audiences:
            _validar_uri_https(audiencia, "audience aceita")
        if len(set(self.accepted_audiences)) != len(self.accepted_audiences):
            raise ConfiguracaoAuthInvalida(
                f"audiences aceitas contêm entrada duplicada: "
                f"{list(self.accepted_audiences)}. Duplicata esconde erro de "
                f"configuração — nunca é deduplicada em silêncio."
            )
        if self.canonical_resource not in self.accepted_audiences:
            raise ConfiguracaoAuthInvalida(
                f"o Resource canônico {self.canonical_resource!r} precisa estar entre as "
                f"audiences aceitas {list(self.accepted_audiences)} — caso contrário o "
                f"servidor anunciaria (PRM) um Resource para o qual ele próprio recusaria "
                f"todo token."
            )

        if not self.required_scopes:
            raise ConfiguracaoAuthInvalida(
                "nenhum escopo exigido. Sem escopo exigido, autenticar passaria a bastar "
                "para alcançar qualquer dispatch — autenticação e autorização são camadas "
                "distintas (Gate 6.3-D2 §6)."
            )
        for escopo in self.required_scopes:
            _validar_token_de_escopo(escopo)
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise ConfiguracaoAuthInvalida(
                f"escopos exigidos contêm duplicata: {list(self.required_scopes)}."
            )

        for origem in self.allowed_origins:
            if "*" in origem:
                raise ConfiguracaoAuthInvalida(
                    f"Origin permitida não pode ser curinga: {origem!r}. A política do "
                    f"EDE é Origin AUSENTE aceita (Claude e ChatGPT não mandam Origin de "
                    f"navegador — prova viva do Gate 6.3-D0c) e Origin PRESENTE "
                    f"inesperada rejeitada; curinga anularia a proteção contra DNS "
                    f"rebinding."
                )
            _validar_origem_permitida(origem)

        host_do_resource = urlsplit(self.canonical_resource).netloc
        if not self.canonical_host:
            object.__setattr__(self, "canonical_host", host_do_resource)
        elif self.canonical_host != host_do_resource:
            raise ConfiguracaoAuthInvalida(
                f"Host canônico {self.canonical_host!r} é inconsistente com o host do "
                f"Resource canônico {host_do_resource!r}. Identidade de host e identidade "
                f"de Resource são a MESMA coisa neste servidor — divergência entre elas é "
                f"exatamente o defeito que permitiria um hostname alternativo do Cloud Run "
                f"virar canônico por acidente."
            )

        if self.clock_skew_seconds < 0:
            raise ConfiguracaoAuthInvalida("tolerância de relógio não pode ser negativa.")
        if self.jwks_max_keys < 1:
            raise ConfiguracaoAuthInvalida(
                "cache de JWKS precisa comportar ao menos uma chave."
            )
        if self.jwks_timeout_seconds <= 0:
            raise ConfiguracaoAuthInvalida(
                "timeout do JWKS precisa ser positivo (nunca ilimitado)."
            )

    # -------------------------------------------------------- derivados

    @property
    def caminho_mcp(self) -> str:
        """Caminho servido pelo transporte Streamable HTTP, DERIVADO do
        Resource canônico — nunca configurado à parte. Se fossem duas
        configurações independentes, poderiam divergir e o servidor
        anunciaria um Resource que ele não serve."""
        return urlsplit(self.canonical_resource).path or "/"

    @property
    def migracao_de_audiencia_ativa(self) -> bool:
        """`True` só quando há MAIS DE UMA audience explicitamente
        autorizada — a janela de migração controlada de hostname. Fica
        visível na telemetria de startup (Gate 6.3-D2 §3)."""
        return len(self.accepted_audiences) > 1

    def escopo_faltante(self, escopos_do_principal: tuple[str, ...]) -> str | None:
        """Primeiro escopo exigido que o principal NÃO tem, ou `None`."""
        for escopo in self.required_scopes:
            if escopo not in escopos_do_principal:
                return escopo
        return None


# --------------------------------------------------------------- ambiente

def auth_habilitada(ambiente: Mapping[str, str] | None = None) -> bool:
    env = os.environ if ambiente is None else ambiente
    return _interpretar_booleano(env.get(VAR_AUTH_ENABLED), VAR_AUTH_ENABLED)


def servico_de_producao(ambiente: Mapping[str, str] | None = None) -> bool:
    """`True` quando `K_SERVICE` identifica exatamente o serviço Cloud Run
    de produção (Gate 6.3-D3.1). Exposta à parte para que o guard seja
    testável e auditável sem depender da leitura completa de
    `carregar_config_do_ambiente`."""
    env = os.environ if ambiente is None else ambiente
    return (env.get(VAR_K_SERVICE) or "").strip() == NOME_SERVICO_PRODUCAO


def carregar_config_do_ambiente(
    ambiente: Mapping[str, str] | None = None,
) -> EdeAuthConfig | None:
    """Resolve a configuração OAuth a partir do ambiente.

    Devolve `None` SOMENTE quando a camada OAuth de aplicação está
    deliberadamente desligada E nenhuma variável de auth foi fornecida
    E o processo não é o serviço de produção. Qualquer outra combinação
    levanta `ConfiguracaoAuthInvalida` (ou, especificamente em produção,
    `ProducaoSemAuthInvalida`) — nunca devolve `None` por não ter
    conseguido montar a configuração, porque isso viraria rota protegida
    servida anonimamente (Gate 6.3-D2, condição de parada)."""
    env = os.environ if ambiente is None else ambiente
    definidas = tuple(v for v in VARIAVEIS_DE_AUTH if (env.get(v) or "").strip())
    producao = servico_de_producao(env)

    if not auth_habilitada(env):
        if definidas:
            raise ConfiguracaoAuthInvalida(
                f"configuração de auth pela metade: {list(definidas)} presente(s) sem "
                f"{VAR_AUTH_ENABLED} ligada. Isto nunca degrada para acesso anônimo — "
                f"ou ligue {VAR_AUTH_ENABLED}, ou remova essas variáveis."
            )
        if producao:
            raise ProducaoSemAuthInvalida(
                f"{VAR_K_SERVICE}={NOME_SERVICO_PRODUCAO!r}: a camada OAuth de "
                f"aplicação é obrigatória em produção (INV-PRODUCAO-AUTH-"
                f"OBRIGATORIA, ADR-0017) — ligue {VAR_AUTH_ENABLED} e configure "
                f"Resource/issuer/JWKS. O serviço de produção nunca sobe com "
                f"autenticação desligada."
            )
        return None

    resource = _validar_uri_https(
        _exigir_texto(env.get(VAR_RESOURCE), VAR_RESOURCE), "Resource canônico"
    )
    issuer = _validar_uri_https(
        _exigir_texto(env.get(VAR_ISSUER), VAR_ISSUER), "issuer esperado"
    )
    jwks_uri = _validar_uri_https(
        _exigir_texto(env.get(VAR_JWKS_URI), VAR_JWKS_URI), "JWKS URI"
    )

    bruto_audiencias = (env.get(VAR_AUDIENCES) or "").strip()
    if bruto_audiencias:
        audiencias = tuple(_separar_lista_de_uris(bruto_audiencias))
        if not audiencias:
            raise ConfiguracaoAuthInvalida(
                f"{VAR_AUDIENCES} foi fornecida mas não contém nenhuma URI."
            )
    else:
        # Operação normal: exatamente uma audience, derivada do Resource.
        audiencias = (resource,)

    bruto_escopos = (env.get(VAR_REQUIRED_SCOPES) or "").strip()
    escopos = separar_escopos(bruto_escopos) if bruto_escopos else ESCOPOS_EXIGIDOS_PADRAO

    bruto_origens = (env.get(VAR_ALLOWED_ORIGINS) or "").strip()
    origens = tuple(_separar_lista_de_uris(bruto_origens)) if bruto_origens else ()

    return EdeAuthConfig(
        canonical_resource=resource,
        issuer=issuer,
        jwks_uri=jwks_uri,
        accepted_audiences=audiencias,
        required_scopes=escopos,
        allowed_origins=origens,
        canonical_host=(env.get(VAR_CANONICAL_HOST) or "").strip(),
        variaveis_definidas=definidas,
    )
