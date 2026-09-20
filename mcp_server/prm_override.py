#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/prm_override.py — catálogo completo de escopos no Protected
Resource Metadata (RFC 9728), Gate 6.5-B2.

PROBLEMA (root-caused no Gate 6.5-B1, diagnóstico): o SDK MCP 2.2.0 usa
o MESMO valor (`AuthSettings.required_scopes`) para duas finalidades
distintas:

  1. exigência de escopo de BASE do transporte HTTP
     (`RequireAuthMiddleware`, mcp/server/lowlevel/server.py);
  2. `scopes_supported` do Protected Resource Metadata
     (`create_protected_resource_routes(..., scopes_supported=auth.
     required_scopes)`, mesmo módulo, mesma linha de construção).

Alargar `EDE_MCP_REQUIRED_SCOPES` para incluir `ede:legal` tornaria
`ede:legal` OBRIGATÓRIO para QUALQUER dispatch (inclusive `ede_health`),
quebrando o modelo por-ferramenta independente de
`scope_policy.EscopoFerramentaMiddleware` — proibido pelo Gate 6.5-B2
§3/§8. Manter `required_scopes` só com `ede:health` (correto para a
base) tem o efeito colateral de o PRM nunca anunciar `ede:legal`: um
cliente OAuth conforme ao protocolo decide o que pedir na autorização
A PARTIR do `scopes_supported` do PRM
(`mcp.client.auth.utils.get_client_metadata_scopes`) — nunca pede um
escopo que não viu anunciado ali, mesmo que a política do Authorization
Server (Descope) já o concedesse.

SOLUÇÃO: interceptar, na camada ASGI (mesmo padrão já usado por
`http_telemetry.TelemetriaSegurancaMiddleware` — camada mais externa,
por fora da autenticação do SDK), SOMENTE o caminho exato do PRM, e
responder com um documento que anuncia o catálogo COMPLETO
(`scope_policy.escopos_anunciaveis`). As funções que constroem esse
documento são as MESMAS do SDK (`create_protected_resource_routes`,
`build_resource_metadata_url`, ambas públicas e já usadas pelo próprio
`mcp_server/server.py` indiretamente) — nenhuma lógica de RFC 9728 é
reimplementada à mão, nenhum arquivo do pacote `mcp` instalado é
modificado, vendorizado ou monkey-patchado. A rota original do SDK
continua montada dentro do app interno; ela simplesmente nunca é
alcançada para este caminho específico, por precedência de middleware
ASGI — nunca removida.

Este middleware intercepta SOMENTE requisições HTTP cujo caminho seja
exatamente o do PRM. Toda outra rota (inclusive `POST /mcp`, autenticado
ou não) segue inalterada para o app interno — autenticação, autorização
por ferramenta (`EscopoFerramentaMiddleware`) e qualquer outro
comportamento permanecem exatamente como antes deste gate."""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp.server.auth.routes import build_resource_metadata_url, create_protected_resource_routes

from auth_config import EdeAuthConfig


class MetadadosRecursoProtegidoMiddleware:
    """Substitui SOMENTE a resposta do Protected Resource Metadata pelo
    catálogo completo de escopos anunciáveis — todo o resto do app é
    encaminhado sem qualquer alteração."""

    def __init__(
        self,
        app: ASGIApp,
        config: EdeAuthConfig,
        escopos_anunciados: tuple[str, ...],
    ) -> None:
        self.app = app
        self._caminho = self._caminho_prm(config)
        self._prm_app = Starlette(
            routes=create_protected_resource_routes(
                resource_url=config.canonical_resource,
                authorization_servers=[config.issuer],
                scopes_supported=list(escopos_anunciados),
            )
        )

    @staticmethod
    def _caminho_prm(config: EdeAuthConfig) -> str:
        """Mesmo caminho que o SDK já serve — reconstruído com a MESMA
        função pública que ele usa internamente (RFC 9728 §3.1), nunca
        reimplementado à mão, para que os dois nunca possam divergir."""
        url = build_resource_metadata_url(config.canonical_resource)
        return urlsplit(str(url)).path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == self._caminho:
            await self._prm_app(scope, receive, send)
            return
        await self.app(scope, receive, send)
