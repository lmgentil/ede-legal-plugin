# -*- coding: utf-8 -*-
"""
tests/oauth_harness.py — harness OAuth local e determinístico
(Gate 6.3-D2 §16).

NÃO É UM TESTE: é a infraestrutura sintética que os testes de
tests/test_mcp_oauth.py usam. Tudo aqui é gerado no processo, em memória:

  * par de chaves RSA SINTÉTICO, gerado na hora (nunca chave commitada,
    nunca chave real);
  * JWKS SINTÉTICO, servido por uma app ASGI em processo;
  * issuer SINTÉTICO e Resource canônico SINTÉTICO, ambos sob domínios
    `.invalid` (RFC 2606) — literalmente irresolvíveis na internet, o que
    torna impossível um teste tocar serviço externo por acidente;
  * nenhuma dependência de rede: o transporte HTTP é
    `httpx2.ASGITransport`, que entrega a requisição direto à app, sem
    socket, sem porta, sem processo filho.

NENHUM SEGREDO REAL DO DESCOPE ENTRA AQUI. Nem em fixture, nem em
variável de ambiente, nem em comentário.

LIMITE EXPLÍCITO DESTE HARNESS
==============================
Ele prova SEMÂNTICA DE IMPLEMENTAÇÃO: que a cadeia de verificação
rejeita o que deve rejeitar, na ordem certa, antes do dispatch. Ele NÃO
substitui, e não deve ser apresentado como substituto de, o gate
posterior com Resource Descope real — que é o único capaz de provar
interoperabilidade com o emissor de verdade (formato de claims reais,
rotação de chave real, latência real, comportamento real do
authorization_code + PKCE).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import anyio
import httpx2
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

BASE = Path(__file__).resolve().parent.parent
MCP_SERVER_DIR = BASE / "mcp_server"
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from auth_config import EdeAuthConfig  # noqa: E402

# ---------------------------------------------------------- identidades

RESOURCE_CANONICO = "https://ede-mcp-000000000000.southamerica-east1.run.app/mcp"
"""Mesma FORMA do Resource de produção esperado (Cloud Run determinístico
em southamerica-east1, caminho /mcp), com número de projeto obviamente
sintético. Deliberadamente NÃO é o `run.app` real: nenhum teste deve
apontar para um host que possa existir."""

RESOURCE_LEGADO = "https://ede-mcp-legado.example.invalid/mcp"
"""Segunda audience usada só nos testes da janela de migração
explícita."""

ISSUER = "https://descope-sintetico.example.invalid/v1/apps/P000"
JWKS_URI = "https://descope-sintetico.example.invalid/v1/keys/P000"

HOST_CANONICO = "ede-mcp-000000000000.southamerica-east1.run.app"
HOST_ALTERNATIVO = "ede-mcp-outro-000000000000.southamerica-east1.run.app"
"""Hostname alternativo que o Cloud Run poderia rotear para o mesmo
serviço. Nunca é canônico, nunca entra no PRM, nunca é aceito."""


def config_canonica(**sobrescritas: Any) -> EdeAuthConfig:
    """Configuração válida de referência — a operação NORMAL: exatamente
    uma audience aceita, igual ao Resource canônico."""
    argumentos: dict[str, Any] = {
        "canonical_resource": RESOURCE_CANONICO,
        "issuer": ISSUER,
        "jwks_uri": JWKS_URI,
        "accepted_audiences": (RESOURCE_CANONICO,),
    }
    argumentos.update(sobrescritas)
    return EdeAuthConfig(**argumentos)


def config_migracao() -> EdeAuthConfig:
    """Janela de migração EXPLÍCITA: duas audiences autorizadas. Nunca
    acontece por omissão — o teste precisa pedir."""
    return config_canonica(accepted_audiences=(RESOURCE_CANONICO, RESOURCE_LEGADO))


# ------------------------------------------------------- chaves sintéticas

def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


@dataclass
class ChavesSinteticas:
    """Par RSA de teste + o JWKS correspondente."""

    kid: str
    privada: Any
    publica: Any = field(init=False)

    def __post_init__(self) -> None:
        self.publica = self.privada.public_key()

    def jwk(self) -> dict[str, Any]:
        documento = RSAAlgorithm.to_jwk(self.publica, as_dict=True)
        documento.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return documento

    def jwks(self) -> dict[str, Any]:
        return {"keys": [self.jwk()]}

    def pem_publica(self) -> bytes:
        return self.publica.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


_CACHE_CHAVES: dict[str, ChavesSinteticas] = {}


def chaves(kid: str = "ede-teste-1") -> ChavesSinteticas:
    """Gerar RSA-2048 não é barato; a suíte reusa o par por `kid` dentro
    da mesma sessão. Continua 100% sintético e efêmero — nada é gravado
    em disco."""
    if kid not in _CACHE_CHAVES:
        _CACHE_CHAVES[kid] = ChavesSinteticas(
            kid=kid, privada=rsa.generate_private_key(public_exponent=65537, key_size=2048)
        )
    return _CACHE_CHAVES[kid]


# ---------------------------------------------------------- emissão

ESCOPO_PADRAO = "ede:health"


def emitir_token(
    *,
    chave: ChavesSinteticas | None = None,
    assinar_com: ChavesSinteticas | None = None,
    issuer: str = ISSUER,
    audiencia: Any = RESOURCE_CANONICO,
    escopo: str | None = ESCOPO_PADRAO,
    sub: str | None = "usuario-sintetico",
    azp: str | None = "cliente-sintetico",
    exp_em: float = 300.0,
    nbf_em: float | None = None,
    iat_em: float = 0.0,
    kid: str | None = None,
    cabecalhos_extra: dict[str, Any] | None = None,
    omitir_audiencia: bool = False,
    omitir_exp: bool = False,
) -> str:
    """JWT RS256 sintético.

    `assinar_com` diferente de `chave` produz o caso "assinatura
    inválida": o cabeçalho anuncia o `kid` publicado no JWKS, mas a
    assinatura vem de outra chave."""
    chave = chave or chaves()
    assinante = assinar_com or chave
    agora = int(time.time())

    reivindicacoes: dict[str, Any] = {"iss": issuer, "iat": agora + int(iat_em)}
    if not omitir_exp:
        reivindicacoes["exp"] = agora + int(exp_em)
    if not omitir_audiencia:
        reivindicacoes["aud"] = audiencia
    if escopo is not None:
        reivindicacoes["scope"] = escopo
    if sub is not None:
        reivindicacoes["sub"] = sub
    if azp is not None:
        reivindicacoes["azp"] = azp
    if nbf_em is not None:
        reivindicacoes["nbf"] = agora + int(nbf_em)

    cabecalhos: dict[str, Any] = {"kid": kid if kid is not None else chave.kid}
    if cabecalhos_extra:
        cabecalhos.update(cabecalhos_extra)

    return jwt.encode(
        reivindicacoes, assinante.privada, algorithm="RS256", headers=cabecalhos
    )


def token_alg_none(*, audiencia: str = RESOURCE_CANONICO) -> str:
    """Token `alg=none` — assinatura ausente, formato válido."""
    agora = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": audiencia,
            "exp": agora + 300,
            "sub": "atacante",
            "scope": ESCOPO_PADRAO,
        },
        key=None,
        algorithm="none",
        headers={"kid": chaves().kid},
    )


def token_confusao_de_algoritmo(*, audiencia: str = RESOURCE_CANONICO) -> str:
    """Confusão de algoritmo clássica: HS256 usando a CHAVE PÚBLICA RSA
    como segredo HMAC.

    Montado à mão porque o próprio PyJWT se recusa a assinar HMAC com
    material assimétrico — e é justamente esse token, que uma biblioteca
    descuidada aceitaria, que precisa ser rejeitado aqui."""
    agora = int(time.time())
    cabecalho = {"alg": "HS256", "typ": "JWT", "kid": chaves().kid}
    corpo = {
        "iss": ISSUER,
        "aud": audiencia,
        "exp": agora + 300,
        "sub": "atacante",
        "scope": ESCOPO_PADRAO,
    }
    parte1 = _b64url(json.dumps(cabecalho, separators=(",", ":")).encode())
    parte2 = _b64url(json.dumps(corpo, separators=(",", ":")).encode())
    assinado = f"{parte1}.{parte2}".encode("ascii")
    assinatura = hmac.new(chaves().pem_publica(), assinado, hashlib.sha256).digest()
    return f"{parte1}.{parte2}.{_b64url(assinatura)}"


# ------------------------------------------------------------ app JWKS

class AppJwks:
    """App ASGI que serve um JWKS controlado pelo teste.

    `corpo` é texto bruto de propósito: é assim que se exercita JWKS
    malformado (JSON inválido) sem contorcer a serialização."""

    def __init__(self, corpo: str | None = None, status: int = 200) -> None:
        self.corpo = corpo if corpo is not None else json.dumps(chaves().jwks())
        self.status = status
        self.requisicoes = 0

    def servir(self, documento: dict[str, Any]) -> None:
        self.corpo = json.dumps(documento)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        self.requisicoes += 1
        corpo = self.corpo.encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": self.status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(corpo)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": corpo})


class AppJwksIndisponivel:
    """JWKS que falha no transporte (não é um 5xx: a conexão morre), o
    caso "JWKS inalcançável"."""

    def __init__(self) -> None:
        self.requisicoes = 0

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        self.requisicoes += 1
        raise ConnectionError("JWKS sintético inalcançável")


def cliente_jwks(app: Any) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app))


# ------------------------------------------------------- ciclo de vida ASGI

@asynccontextmanager
async def ciclo_de_vida(app: Any) -> Iterator[None]:
    """Executa o protocolo ASGI de lifespan à mão.

    `httpx2.ASGITransport` entrega só requisições HTTP; ele não inicia o
    lifespan, e o `StreamableHTTPSessionManager` do SDK só funciona com
    o lifespan rodando. Dirigir o lifespan aqui é o que permite testar a
    app REAL, montada por `server.construir_app_http`, sem subir uvicorn
    nem abrir socket."""
    para_app, do_teste = anyio.create_memory_object_stream(10)
    do_app, no_teste = anyio.create_memory_object_stream(10)

    async def receive() -> Any:
        return await do_teste.receive()

    async def send(mensagem: Any) -> None:
        await do_app.send(mensagem)

    async with anyio.create_task_group() as tg:
        tg.start_soon(app, {"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)
        await para_app.send({"type": "lifespan.startup"})
        mensagem = await no_teste.receive()
        if mensagem["type"] != "lifespan.startup.complete":
            raise RuntimeError(f"lifespan não subiu: {mensagem}")
        try:
            yield
        finally:
            await para_app.send({"type": "lifespan.shutdown"})
            await no_teste.receive()
            tg.cancel_scope.cancel()


def cliente_mcp(app: Any, config: EdeAuthConfig, **kwargs: Any) -> httpx2.AsyncClient:
    """Cliente HTTP apontado para a app MCP em processo.

    `base_url` com o host canônico faz o httpx emitir o header `Host`
    correto por conta própria — o teste de Host inesperado sobrescreve o
    header explicitamente."""
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url=f"https://{config.canonical_host}",
        **kwargs,
    )


@asynccontextmanager
async def cliente_mcp_protocolo(app: Any, config: EdeAuthConfig, token: str) -> Iterator[Any]:
    """Cliente MCP OFICIAL (`mcp.Client`) falando o protocolo completo
    sobre a app em processo.

    Usado no caminho POSITIVO, onde interessa provar que um token válido
    chega de fato ao dispatch da tool — não basta o 200 de um POST cru,
    porque o transporte Streamable HTTP com sessão exige o handshake que
    só um cliente real executa. Nos caminhos NEGATIVOS os testes usam
    POST cru: a rejeição acontece antes do handshake, e um POST cru prova
    isso de forma mais direta e sem parte móvel."""
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as http:
        transporte = streamable_http_client(config.canonical_resource, http_client=http)
        async with Client(transporte, raise_exceptions=True) as cliente:
            yield cliente


CABECALHOS_JSONRPC = {"Accept": "application/json, text/event-stream"}


def corpo_tools_list(identificador: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identificador, "method": "tools/list"}


def corpo_tools_call(
    ferramenta: str = "ede_health", identificador: int = 2
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": identificador,
        "method": "tools/call",
        "params": {"name": ferramenta, "arguments": {}},
    }
