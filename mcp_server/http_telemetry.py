#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/http_telemetry.py — middleware ASGI de telemetria de segurança
(Gate 6.3-D2 §11, ADR-0016).

Fica na camada MAIS EXTERNA da aplicação Starlette, por fora da
`AuthenticationMiddleware` do SDK. Consequência deliberada: ele observa
TAMBÉM as respostas 401/403 produzidas pelo `RequireAuthMiddleware` —
que é justamente o evento de segurança que interessa registrar. Um
middleware por dentro da autenticação nunca veria a rejeição.

Só metadado sai daqui: a emissão passa inteira pela allowlist fechada de
`mcp_server/auth_logging.py`, então nem por engano o header Authorization,
o token, o corpo da requisição ou conteúdo jurídico chegam ao log. Nada
do corpo da requisição ou da resposta é lido — o middleware observa
apenas a linha de status e o tempo decorrido.

O identificador de correlação é GERADO AQUI (uuid4), nunca lido de header
do cliente: aceitar um `X-Request-Id` externo permitiria ao chamador
injetar conteúdo arbitrário no log de segurança.
"""
from __future__ import annotations

import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from auth_config import EdeAuthConfig
import auth_logging as telemetria


class TelemetriaSegurancaMiddleware:
    """Registra um evento somente-metadado por requisição HTTP."""

    def __init__(self, app: ASGIApp, config: EdeAuthConfig) -> None:
        self.app = app
        self._config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlacao = telemetria.novo_id_correlacao()
        marca = telemetria.definir_id_correlacao(correlacao)
        inicio = time.monotonic()
        status: dict[str, int | None] = {"codigo": None}

        async def send_observado(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["codigo"] = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_observado)
        finally:
            decorrido = int((time.monotonic() - inicio) * 1000)
            codigo = status["codigo"]
            try:
                telemetria.registrar_evento(
                    telemetria.EVENTO_REQUISICAO_HTTP,
                    id_correlacao=correlacao,
                    metodo_http=scope.get("method"),
                    # `raw_path`/`query_string` NÃO são registrados: query
                    # string é conteúdo controlado pelo cliente.
                    caminho=scope.get("path"),
                    status_http=codigo,
                    latencia_ms=decorrido,
                    resultado_auth=self._resultado_auth(scope, codigo),
                    resultado_autz=self._resultado_autz(codigo),
                    issuer=self._config.issuer,
                    audiencias_aceitas=len(self._config.accepted_audiences),
                    migracao_audiencia=self._config.migracao_de_audiencia_ativa,
                )
            finally:
                telemetria.limpar_id_correlacao(marca)

    # ------------------------------------------------------- classificação

    def _autenticado(self, scope: Scope) -> bool:
        """`AuthenticationMiddleware` do Starlette escreve `user`/`auth` no
        MESMO dicionário de scope, então o resultado já está visível aqui
        depois que a aplicação interna retorna."""
        from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

        return isinstance(scope.get("user"), AuthenticatedUser)

    def _resultado_auth(self, scope: Scope, codigo: int | None) -> str:
        if self._autenticado(scope):
            return telemetria.AUTH_OK
        if codigo == 401:
            # Distinguir "ausente" de "inválida" exigiria inspecionar o
            # header Authorization aqui. A categoria fina do motivo já é
            # emitida pelo verificador (mcp_server/token_verifier.py), com
            # o mesmo id de correlação — este evento não a duplica nem
            # tenta adivinhá-la.
            return telemetria.AUTH_INVALIDA
        return telemetria.AUTH_NAO_APLICAVEL

    def _resultado_autz(self, codigo: int | None) -> str:
        if codigo == 403:
            return telemetria.AUTZ_ESCOPO_INSUFICIENTE
        if codigo is not None and 200 <= codigo < 300:
            return telemetria.AUTZ_CONCEDIDA
        return telemetria.AUTZ_NAO_AVALIADA


def registrar_startup(config: EdeAuthConfig | None) -> dict[str, Any]:
    """Telemetria de startup. Com a camada OAuth desligada, diz isso
    explicitamente — o gate exige que a ausência de autorização de
    aplicação seja VISÍVEL, nunca implícita (identidade de infraestrutura
    do Google Cloud não é autorização de aplicação EDE)."""
    if config is None:
        return telemetria.registrar_evento(
            telemetria.EVENTO_STARTUP,
            auth_aplicacao=False,
            resultado_auth=telemetria.AUTH_NAO_APLICAVEL,
        )
    return telemetria.registrar_evento(
        telemetria.EVENTO_STARTUP,
        auth_aplicacao=True,
        issuer=config.issuer,
        host_canonico=config.canonical_host,
        audiencias_aceitas=len(config.accepted_audiences),
        migracao_audiencia=config.migracao_de_audiencia_ativa,
        resultado_auth=telemetria.AUTH_NAO_APLICAVEL,
    )
