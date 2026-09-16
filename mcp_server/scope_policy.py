#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/scope_policy.py — autorização POR FERRAMENTA e prova de
dispatch zero (Gate 6.3-D2 §6/§7/§17, ADR-0016).

DUAS CAMADAS, PROPÓSITOS DIFERENTES
===================================
1. CAMADA HTTP (SDK): `AuthSettings.required_scopes` faz o
   `RequireAuthMiddleware` do SDK devolver 401 sem token válido e 403
   `insufficient_scope` sem o escopo de BASE — antes de qualquer byte
   chegar ao dispatcher MCP. Hoje a base é `ede:health`, exata porque
   toda a superfície exposta é operacional/health.

2. CAMADA MCP (este módulo): exigência POR FERRAMENTA, via
   `ServerMiddleware` — mecanismo de primeira classe do SDK 2.2.0
   (`MCPServer(..., middleware=[...])`), não modificação invasiva de
   framework. É esta camada que carrega `ede:legal` quando tools
   jurídicas existirem, sem precisar tornar `ede:legal` um escopo de
   transporte nem obrigar todo principal jurídico a carregar
   `ede:health`.

`ede:health` NÃO IMPLICA `ede:legal`: o mapa é explícito, tool por tool,
e um principal só alcança a tool cujo escopo ele realmente tem. Um
principal com `ede:legal` apenas também NÃO alcança a health: falta-lhe
o escopo de base do transporte e o 403 acontece na camada HTTP. As duas
direções são independentes e testadas.

Autenticação nunca vira autorização por osmose: um token válido sem o
escopo da ferramenta é rejeitado ANTES do handler — nunca "autenticou,
então deixa passar".

DESCOBERTA (tools/list) COM FILTRAGEM DETERMINÍSTICA
====================================================
O SDK 2.2.0 suporta isto de forma limpa: `ServerMiddleware` observa
`tools/list` e pode reescrever o resultado. A filtragem é
DETERMINÍSTICA — deriva do mesmo mapa que protege o dispatch, nunca de
heurística. Um principal sem `ede:legal` não vê tool `ede:legal` na
listagem E não conseguiria chamá-la mesmo que a descobrisse por outro
meio: a proteção de dispatch é a garantia, a filtragem da descoberta é
higiene. Não há invenção de comportamento não suportado pelo SDK.

CONTAGEM DE DISPATCH
====================
`CONTADOR_DISPATCH` é um contador em memória, local ao processo, que só
avança quando o CORPO de uma tool efetivamente executa. Ele nunca é
exposto por MCP, por HTTP ou por log — existe para que a suíte possa
provar a afirmação forte do gate: toda falha de autenticação/autorização
ocorre ANTES do dispatch protegido (contador inalterado), e a chamada
autorizada incrementa exatamente uma vez. É mecanismo de prova, isolado
de qualquer semântica jurídica do Core.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, Final, Mapping

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_REQUEST

from auth_config import ESCOPO_HEALTH
import auth_logging as telemetria

FERRAMENTA_HEALTH: Final = "ede_health"

MAPA_ESCOPO_POR_FERRAMENTA: Final[Mapping[str, str]] = {
    FERRAMENTA_HEALTH: ESCOPO_HEALTH,
}
"""Mapa EXPLÍCITO tool -> escopo exigido. Uma tool ausente deste mapa não
é "livre": `escopo_exigido_por` devolve `None` e o middleware NEGA — uma
ferramenta nova sem política declarada nunca nasce acessível por
omissão (fail-closed, CLAUDE.md §17).

Nenhuma tool `ede:legal` existe neste gate. Acrescentar uma é trabalho de
gate posterior e exige, junto, reavaliar o escopo de base do transporte
(auth_config.ESCOPOS_EXIGIDOS_PADRAO)."""


def escopo_exigido_por(ferramenta: str) -> str | None:
    """Escopo exigido pela ferramenta, ou `None` quando ela não tem
    política declarada (o middleware trata isso como negação)."""
    return MAPA_ESCOPO_POR_FERRAMENTA.get(ferramenta)


# ------------------------------------------------------- contador de dispatch

class ContadorDispatch:
    """Contador em memória de execuções reais de corpo de tool."""

    def __init__(self) -> None:
        self._por_ferramenta: dict[str, int] = {}

    def registrar(self, ferramenta: str) -> None:
        self._por_ferramenta[ferramenta] = self._por_ferramenta.get(ferramenta, 0) + 1

    def total(self) -> int:
        return sum(self._por_ferramenta.values())

    def de(self, ferramenta: str) -> int:
        return self._por_ferramenta.get(ferramenta, 0)

    def zerar(self) -> None:
        """Somente para isolamento entre testes."""
        self._por_ferramenta.clear()


CONTADOR_DISPATCH: Final = ContadorDispatch()


def contar_dispatch(ferramenta: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Marca o corpo de uma tool como "dispatch real".

    Aplicado ABAIXO do registro no servidor, de modo que o contador só
    avance quando a função de negócio realmente roda. `functools.wraps`
    preserva assinatura e anotações, então o schema que o SDK deriva da
    função continua o mesmo — a decoração é invisível ao protocolo."""

    def decorador(funcao: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(funcao)
        def envolvida(*args: Any, **kwargs: Any) -> Any:
            CONTADOR_DISPATCH.registrar(ferramenta)
            return funcao(*args, **kwargs)

        return envolvida

    return decorador


# -------------------------------------------------------------- middleware

class EscopoFerramentaMiddleware:
    """`ServerMiddleware` do SDK 2.2.0: exige escopo por ferramenta em
    `tools/call` e filtra `tools/list`.

    Instalado SOMENTE quando a camada OAuth de aplicação está ligada — com
    ela desligada o servidor preserva exatamente o comportamento das
    Etapas 6.1/6.2, sem uma segunda política implícita."""

    def __init__(self, mapa: Mapping[str, str] | None = None) -> None:
        self._mapa = dict(mapa if mapa is not None else MAPA_ESCOPO_POR_FERRAMENTA)

    # ------------------------------------------------------- auxiliares

    def _escopos_do_principal(self) -> tuple[str, ...]:
        """Escopos do token desta requisição.

        `None` (sem contexto de auth) é tratado como NENHUM escopo, nunca
        como "sem restrição": se um caminho futuro alcançar o dispatcher
        sem passar pela autenticação, ele encontra negação, não permissão."""
        token = get_access_token()
        if token is None:
            return ()
        return tuple(token.scopes or ())

    def decidir(self, ferramenta: str, escopos: tuple[str, ...]) -> tuple[bool, str | None]:
        """Decisão de autorização, isolada e determinística: `(autorizado,
        escopo_exigido)`.

        Pública de propósito — é a matriz de escopos que a suíte precisa
        exercitar diretamente, sem montar uma requisição MCP inteira. Uma
        ferramenta ausente do mapa devolve `(False, None)`: sem política
        declarada, não há acesso."""
        exigido = self._mapa.get(ferramenta)
        if exigido is None:
            return False, None
        return exigido in escopos, exigido

    # -------------------------------------------------------- despacho

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        if ctx.method == "tools/call":
            return await self._proteger_chamada(ctx, call_next)
        if ctx.method == "tools/list":
            return await self._filtrar_listagem(ctx, call_next)
        return await call_next(ctx)

    async def _proteger_chamada(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        parametros = ctx.params if isinstance(ctx.params, dict) else {}
        nome = parametros.get("name")
        if not isinstance(nome, str):
            # Params malformados seguem para a validação do SDK, que já
            # responde INVALID_PARAMS; não há tool a autorizar aqui.
            return await call_next(ctx)

        escopos = self._escopos_do_principal()
        autorizado, exigido = self.decidir(nome, escopos)
        if not autorizado:
            telemetria.registrar_evento(
                telemetria.EVENTO_AUTORIZACAO_FERRAMENTA,
                ferramenta=nome,
                escopo_exigido=exigido,
                resultado_autz=telemetria.AUTZ_ESCOPO_INSUFICIENTE,
            )
            # Levantado ANTES de call_next: o handler da tool nunca roda,
            # então o contador de dispatch não se move. É esta ordem que a
            # suíte prova em tests/test_mcp_oauth.py.
            raise MCPError(code=INVALID_REQUEST, message="insufficient_scope")

        telemetria.registrar_evento(
            telemetria.EVENTO_AUTORIZACAO_FERRAMENTA,
            ferramenta=nome,
            escopo_exigido=exigido,
            resultado_autz=telemetria.AUTZ_CONCEDIDA,
        )
        return await call_next(ctx)

    @staticmethod
    def _nome_da_ferramenta(entrada: Any) -> str | None:
        if isinstance(entrada, dict):
            nome = entrada.get("name")
        else:
            nome = getattr(entrada, "name", None)
        return nome if isinstance(nome, str) else None

    async def _filtrar_listagem(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        """Filtra a descoberta pelos escopos do principal.

        `HandlerResult` é `BaseModel | dict | None`, e o SDK 2.2.0
        entrega `tools/list` ao middleware JÁ como `dict` — não como
        `ListToolsResult`. Tratar só o modelo (primeira versão deste
        código) fazia o filtro virar um no-op silencioso: a tool
        `ede:legal` continuava listada para um principal só com
        `ede:health`. Achado real da suíte desta etapa
        (`test_health_nao_descobre_nem_alcanca_ferramenta_legal`); por
        isso as DUAS formas são tratadas, e o teste existe para travar a
        regressão caso o SDK mude de forma outra vez.

        Uma resposta sem `tools` (em qualquer das formas) passa intacta:
        não há o que filtrar, e nada vaza."""
        resultado = await call_next(ctx)

        if isinstance(resultado, dict):
            brutas = resultado.get("tools")
        else:
            brutas = getattr(resultado, "tools", None)
        if not isinstance(brutas, list):
            return resultado

        escopos = self._escopos_do_principal()
        visiveis = [
            ferramenta
            for ferramenta in brutas
            if self.decidir(self._nome_da_ferramenta(ferramenta) or "", escopos)[0]
        ]
        if len(visiveis) == len(brutas):
            return resultado
        if isinstance(resultado, dict):
            filtrado = dict(resultado)
            filtrado["tools"] = visiveis
            return filtrado
        return resultado.model_copy(update={"tools": visiveis})
