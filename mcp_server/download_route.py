#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/download_route.py — rota pública `/download/<token>` do
artefato efêmero (Gate 6.6-F/G, ADR-0019; substitui a URL V4 assinada do
GCS entregue ao cliente, rejeitada por DELIVERY-CLIENT-01).

EXCEÇÃO EXPLÍCITA DE AUTENTICAÇÃO — não acidental. Mapa de autorização
do serviço (adendo da ADR-0017, `INV-CLOUD-RUN-AUTH-OBRIGATORIA`):

    /mcp                     -> OAuth obrigatório (RequireAuthMiddleware
                                do SDK, só nesta rota)
    PRM / discovery OAuth    -> público, conforme RFC 9728
    /download/<token>        -> autorização por CAPACIDADE PORTADORA
                                opaca (o token), nunca por OAuth

Este middleware intercepta SOMENTE caminhos sob `/download/` e fica POR
FORA da app do SDK: a requisição de download nunca chega ao
`AuthenticationMiddleware`/`RequireAuthMiddleware` nem ao dispatcher MCP
(nenhum `Authorization` é lido aqui, nenhum JWKS é consultado). Todo
outro caminho — inclusive `/mcp` — segue inalterado para a app interna,
com a autenticação do SDK intacta. Ordem real verificada no SDK 2.2.0
(`mcp/server/lowlevel/server.py::streamable_http_app`): Authentication
+ AuthContext como middleware global da Starlette interna, e
`RequireAuthMiddleware` como endpoint da rota `/mcp` apenas.

Autorização do download: o token (256 bits, `secrets.token_urlsafe`) é
resolvido por `artifact_storage.resolver_download`, que valida formato,
metadado, expiração (24h) e SHA-256 do conteúdo ANTES de qualquer byte
sair. A query string NUNCA é lida — `?utm_source=chatgpt.com` ou
qualquer outro parâmetro acrescentado pelo cliente não tem efeito.

Respostas:
    200  DOCX (GET) / só cabeçalhos (HEAD)
    404  uniforme: token malformado, inexistente, expirado, metadado
         ausente/malformado, objeto já excluído — o motivo fino fica só
         na telemetria interna, nunca na resposta
    405  método diferente de GET/HEAD
    500  SHA-256 divergente — nenhum byte do documento enviado
    503  armazenamento indisponível/não configurado

Logs: nenhuma linha deste módulo contém o token. O evento de telemetria
carrega só rótulos fechados e `artefato_id` (= sha256 do token); o
caminho é redigido por `http_telemetry.caminho_para_log`, e
`auth_logging` recusa qualquer `caminho` não redigido sob `/download/`.
"""
from __future__ import annotations

import os
from typing import Callable

import anyio.to_thread
from starlette.types import ASGIApp, Receive, Scope, Send

import artifact_storage as ast
import auth_logging as telemetria

METODOS_PERMITIDOS = ("GET", "HEAD")

_CABECALHOS_COMUNS = [
    (b"cache-control", b"no-store"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
]

_STATUS_POR_RESULTADO = {
    ast.DOWNLOAD_ENTREGUE: 200,
    ast.DOWNLOAD_NAO_ENCONTRADO: 404,
    ast.DOWNLOAD_INTEGRIDADE_DIVERGENTE: 500,
    ast.DOWNLOAD_INDISPONIVEL: 503,
}

_CORPO_POR_STATUS = {
    404: b"Not Found",
    405: b"Method Not Allowed",
    500: b"Internal Server Error",
    503: b"Service Unavailable",
}


def _transporte_do_ambiente() -> ast.TransporteArtefato:
    return ast.obter_transporte_do_ambiente(os.environ)


class DownloadArtefatoMiddleware:
    """Serve `/download/<token>`; encaminha todo o resto sem alteração."""

    def __init__(self, app: ASGIApp,
                 obter_transporte: Callable[[], ast.TransporteArtefato] = _transporte_do_ambiente) -> None:
        self.app = app
        self._obter_transporte = obter_transporte

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        caminho = scope.get("path") or ""
        if scope["type"] != "http" or not caminho.startswith(ast.PREFIXO_ROTA_DOWNLOAD):
            await self.app(scope, receive, send)
            return

        metodo = scope.get("method")
        if metodo not in METODOS_PERMITIDOS:
            await _responder_texto(send, 405, incluir_corpo=True, extras=[(b"allow", b"GET, HEAD")])
            return

        token = caminho[len(ast.PREFIXO_ROTA_DOWNLOAD):]
        # I/O síncrono (httpx2) fora do event loop.
        resultado = await anyio.to_thread.run_sync(self._resolver, token)
        status = _STATUS_POR_RESULTADO[resultado.status]
        _registrar(metodo, status, resultado)

        if status != 200:
            await _responder_texto(send, status, incluir_corpo=(metodo == "GET"))
            return

        dados = resultado.dados
        cabecalhos = [
            (b"content-type", ast.CONTENT_TYPE_DOCX.encode("ascii")),
            (b"content-disposition", f'attachment; filename="{resultado.filename}"'.encode("ascii")),
            (b"content-length", str(len(dados)).encode("ascii")),
            *_CABECALHOS_COMUNS,
        ]
        await send({"type": "http.response.start", "status": 200, "headers": cabecalhos})
        await send({"type": "http.response.body", "body": dados if metodo == "GET" else b""})

    def _resolver(self, token: str) -> ast.ResultadoDownload:
        """Fail-closed: configuração ausente ou qualquer exceção inesperada
        vira `indisponivel` (503) — nunca um traceback no log (que poderia
        carregar o caminho) e nunca bytes sem verificação de SHA."""
        try:
            return ast.resolver_download(token, self._obter_transporte())
        except Exception:
            return ast.ResultadoDownload(ast.DOWNLOAD_INDISPONIVEL)


def _registrar(metodo: str, status: int, resultado: ast.ResultadoDownload) -> None:
    telemetria.registrar_evento(
        telemetria.EVENTO_DOWNLOAD_ARTEFATO,
        metodo_http=metodo,
        status_http=status,
        resultado_download=resultado.status,
        motivo_download=resultado.motivo,
        artefato_id=resultado.artefato_id,
        documento_tamanho_bytes=len(resultado.dados) if resultado.dados is not None else None,
    )


async def _responder_texto(send: Send, status: int, incluir_corpo: bool,
                           extras: list[tuple[bytes, bytes]] | None = None) -> None:
    corpo = _CORPO_POR_STATUS[status]
    cabecalhos = [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(corpo)).encode("ascii")),
        *_CABECALHOS_COMUNS,
        *(extras or []),
    ]
    await send({"type": "http.response.start", "status": status, "headers": cabecalhos})
    await send({"type": "http.response.body", "body": corpo if incluir_corpo else b""})
