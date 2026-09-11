#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/server.py — EDE MCP Server (Etapa 6.1, ADR-0015).

Adapter remoto fino sobre o EDE Core, nos termos da Opção A aprovada no
Gate da Etapa 6.0 e formalizada em ADR-0015: este servidor NUNCA chama a
API Claude/qualquer LLM e NUNCA reimplementa o raciocínio de
`estrategista-contestacao-ede`, `redator-peca-processual-elite` ou
`humanizer-pt-br` — essas Skills continuam rodando no host Claude. Nesta
primeira rodada (Etapa 6.1) o servidor expõe SOMENTE a tool `ede_health`:
nenhuma geração de Contestação, nenhum RAG carregado, nenhum Modelo
Oficial acessado, copiado ou referenciado (CLAUDE.md §13; ADR-0009 — o
Modelo Oficial permanece inteiramente fora do MCP nesta etapa).

Transporte: Streamable HTTP, conforme a especificação MCP 2026-07-28
(núcleo do protocolo stateless; headers Mcp-Method/Mcp-Name resolvidos
pelo próprio SDK). Nenhum protocolo é implementado manualmente e nenhuma
abstração MCP própria é criada aqui — toda a conformidade vem do SDK
Python oficial `mcp` (pip, `mcp==2.2.0`; ver mcp_server/requirements.txt e
ADR-0015 para a justificativa da escolha/versão). `mcp.server.MCPServer`
é a classe que substitui `FastMCP` na major 2.x do SDK.

Host-agnostic, no mesmo espírito já adotado pelo EDE Core (ADR-0014):
nenhuma dependência de CLAUDE_PLUGIN_ROOT, SKILL.md, ~/.claude/~/.agents
ou de qualquer estado específico do host Claude. `BASE` é resolvido só a
partir da posição deste arquivo no repositório.

SERVICE_READY vs CONTESTACAO_READY (Etapa 6.1, itens 5/6/14 do pedido):
  service_status      -> só diz se ESTE PROCESSO está de pé e conseguiu
                          calcular o diagnóstico sem exceção. Não depende
                          de RAG nem de Modelo Oficial.
  contestacao_status  -> diz se o pipeline determinístico da Contestação
                          teria como rodar. Nesta etapa é SEMPRE
                          NOT_READY, porque RAG e Modelo Oficial estão
                          deliberadamente fora do escopo (ver `checks`).
Os dois nunca são fundidos num único campo "status" — um servidor pode
estar operacional (service_status=READY) sem estar apto a gerar uma
Contestação (contestacao_status=NOT_READY); ver ADR-0015 e SPEC-0001.

Fail-closed (CLAUDE.md §17): qualquer exceção interna ao calcular o
diagnóstico vira service_status="ERROR" estruturado — nunca "READY", e o
detalhe exposto ao chamador nunca inclui stack trace ou mensagem bruta da
exceção (mesma disciplina de log/segurança do restante do EDE Core).

Dependências desta etapa: só o SDK MCP e o que ele já traz (pydantic,
anyio, starlette, uvicorn). Deliberadamente ausentes: pyarrow, rank_bm25,
sentence-transformers, pandas, numpy, joblib, parquet — RAG entra em
etapa posterior (itens 8/14 do pedido da Etapa 6.1). Nenhum Modelo
Oficial é lido, baixado, enviado ou referenciado por este módulo (item 13
do pedido).

Não confundir com o healthcheck de container/Cloud Run: aquele verifica
só "processo vivo" e não deve carregar nada deste módulo além do processo
já estar de pé — `ede_health` é o diagnóstico funcional do EDE, mais caro
e mais informativo, nunca o mesmo mecanismo (item 6 do pedido).
"""
from __future__ import annotations

import importlib.metadata
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from mcp.server import MCPServer

BASE = Path(__file__).resolve().parent.parent
VERSION_FILE = BASE / "VERSION"

NOME_SERVIDOR = "EDE Legal Plugin — MCP Server"


class CheckStatus(str, Enum):
    """Estado de uma checagem individual dentro de `ede_health.checks`."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class HealthCheck(BaseModel):
    """Uma checagem nomeada (ex.: "rag", "modelo_oficial") e seu motivo."""

    status: CheckStatus
    detail: str


class EdeHealthResponse(BaseModel):
    """Schema de resposta de `ede_health` (Etapa 6.1, item 5 do pedido).

    `service_status` e `contestacao_status` são deliberadamente dois
    campos separados, nunca um único "status" genérico — ver docstring do
    módulo e ADR-0015.
    """

    service_status: Literal["READY", "DEGRADED", "ERROR"]
    contestacao_status: Literal["READY", "NOT_READY"]
    version: str
    runtime: str
    checks: dict[str, HealthCheck]


def _versao_plugin() -> str:
    """Versão do EDE Legal Plugin (arquivo VERSION na raiz do repo).

    Somente leitura; nunca falha o diagnóstico inteiro por conta disto —
    devolve um valor sentinela em vez de propagar a exceção, porque a
    ausência do arquivo VERSION não impede o processo de responder."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "desconhecida"


def _runtime_info() -> str:
    """Identificação do runtime deste servidor (Python + SDK MCP)."""
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    try:
        mcp_version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        mcp_version = "desconhecida"
    return f"python {py} / mcp {mcp_version} / EDE MCP Server (Etapa 6.1)"


mcp = MCPServer(NOME_SERVIDOR)


@mcp.tool()
def ede_health() -> EdeHealthResponse:
    """Diagnóstico funcional do EDE MCP Server.

    Nesta etapa (6.1) verifica somente o que existe no protótipo: o
    próprio processo. RAG e Modelo Oficial são reportados como
    NOT_CONFIGURED (nunca como erro) porque estão deliberadamente fora do
    escopo desta rodada — ADR-0015, itens 8/13/14 do pedido da
    Etapa 6.1. `contestacao_status` só chega a READY quando TODAS as
    checagens abaixo estiverem READY; hoje isso nunca acontece.
    """
    try:
        checks = {
            "process": HealthCheck(
                status=CheckStatus.READY,
                detail="Processo do EDE MCP Server ativo e respondendo.",
            ),
            "rag": HealthCheck(
                status=CheckStatus.NOT_CONFIGURED,
                detail=(
                    "RAG jurídico (busca híbrida lexical+vetorial) não "
                    "carregado nesta etapa (Etapa 6.1, ADR-0015) — "
                    "previsto para etapa posterior, fora do escopo deste "
                    "servidor mínimo."
                ),
            ),
            "modelo_oficial": HealthCheck(
                status=CheckStatus.NOT_CONFIGURED,
                detail=(
                    "Modelo Oficial permanece inteiramente fora deste "
                    "servidor nesta etapa (CLAUDE.md §13, ADR-0009) — "
                    "nenhum asset institucional é acessado, referenciado "
                    "ou provisionado por este MCP Server."
                ),
            ),
        }

        contestacao_pronta = all(c.status == CheckStatus.READY for c in checks.values())

        return EdeHealthResponse(
            service_status="READY",
            contestacao_status="READY" if contestacao_pronta else "NOT_READY",
            version=_versao_plugin(),
            runtime=_runtime_info(),
            checks=checks,
        )
    except Exception:
        # Fail-closed (CLAUDE.md §17): erro interno nunca vira READY. O
        # detalhe exposto ao chamador é genérico de propósito — nunca a
        # mensagem/stack trace bruta da exceção. Nunca reinvocar aqui
        # _versao_plugin()/_runtime_info() (ou qualquer outro helper do
        # bloco acima): se a falha original veio de um deles, chamá-los
        # de novo no próprio tratamento de erro derrotaria o fail-closed
        # inteiro — achado real do teste desta etapa
        # (test_erro_interno_nunca_vira_ready). Este caminho usa só
        # valores literais, incondicionalmente seguros.
        return EdeHealthResponse(
            service_status="ERROR",
            contestacao_status="NOT_READY",
            version="desconhecida",
            runtime="desconhecida",
            checks={
                "process": HealthCheck(
                    status=CheckStatus.ERROR,
                    detail="Falha interna ao calcular o diagnóstico do servidor.",
                ),
            },
        )


DEFAULT_HOST_LOCAL = "127.0.0.1"
DEFAULT_PORT_LOCAL = 8765
"""Endereço/porta default da EXECUÇÃO LOCAL SEM CONFIGURAÇÃO (não do
container/Cloud Run -- ver main()). Decisão de arquitetura registrada
nesta rodada: a porta usada por esta constante ANTES desta mudança
(ver `git log -p` do commit que a alterou para a Etapa 6.2) passou a
estar reservada a outro serviço no ambiente local do projeto e NUNCA
deve voltar a ser o default do EDE MCP -- 8765 é, daqui em diante, a
única porta local default do EDE MCP; nenhum outro ponto deste módulo
hardcoda um valor de substituição."""


def main() -> None:
    """Entrypoint de processo — único lugar que decide transporte/porta.

    Streamable HTTP conforme a especificação MCP 2026-07-28. Nenhuma
    lógica de protocolo é escrita aqui; `mcp.run()` é fornecido pelo SDK.

    Host/porta são sempre lidos do ambiente primeiro -- distinção
    obrigatória entre dois cenários (não confundir um com o outro):

      EXECUÇÃO LOCAL SEM CONFIGURAÇÃO -> 127.0.0.1:8765
        (DEFAULT_HOST_LOCAL/DEFAULT_PORT_LOCAL acima; usado só quando
        HOST/PORT não estão definidas no ambiente)

      CONTAINER/CLOUD RUN -> 0.0.0.0:${PORT}
        (a plataforma injeta PORT; o Dockerfile define HOST=0.0.0.0;
        este código nunca decide isso por conta própria nem substitui a
        PORT fornecida por um valor fixo -- só cai nos defaults locais
        quando a variável correspondente está mesmo ausente)

    O default local mudou para 127.0.0.1:8765 nesta rodada (commit
    25791cd tinha introduzido a leitura de ambiente preservando ainda o
    valor antigo como fallback) porque a porta antiga passou a ser
    reservada a outro serviço do ambiente local -- decisão de
    arquitetura explícita do usuário, não uma escolha técnica deste
    módulo. Nenhum outro ponto deste arquivo hardcoda um valor de
    substituição."""
    host = os.environ.get("HOST", DEFAULT_HOST_LOCAL)
    port = int(os.environ.get("PORT", DEFAULT_PORT_LOCAL))
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
