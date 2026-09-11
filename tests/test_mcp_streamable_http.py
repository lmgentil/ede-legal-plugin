# -*- coding: utf-8 -*-
"""
tests/test_mcp_streamable_http.py — prova de transporte real (Etapa 6.2,
item 1 do pedido: "verificação prévia do transporte" antes de qualquer
container).

Diferente de tests/test_mcp_server.py (client MCP oficial *in-memory*,
sem rede — Etapa 6.1), este arquivo sobe `mcp_server/server.py` como
PROCESSO REAL, escutando em loopback (127.0.0.1) numa porta livre
escolhida dinamicamente, e conecta com o mesmo `mcp.Client` do SDK
oficial — só que passando uma URL HTTP em vez do objeto do servidor, o
que o faz usar de verdade o transporte Streamable HTTP
(`streamable_http_client` internamente), nunca o transporte in-memory.
Prova o diagrama completo do pedido:

    CLIENTE MCP -> HTTP -> servidor -> tool ede_health -> resposta

Determinístico e sem processo órfão: a fixture `servidor_http_real`
garante finalização do subprocesso (terminate -> wait com timeout ->
kill se necessário) em `finally`, mesmo se o teste falhar no meio; a
porta é obtida do próprio SO (bind a porta 0), nunca fixa, para não
colidir com nada que já esteja ouvindo em 8080 nesta máquina.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
MCP_SERVER_DIR = BASE / "mcp_server"


def _porta_livre() -> int:
    """Porta TCP livre em loopback, escolhida pelo SO (bind à porta 0 e
    lida de volta) — evita colisão com qualquer processo já ocupando a
    porta padrão 8080 nesta máquina."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _porta_aceita_conexao(host: str, porta: int) -> bool:
    try:
        with socket.create_connection((host, porta), timeout=0.2):
            return True
    except OSError:
        return False


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def servidor_http_real():
    """Sobe mcp_server/server.py como subprocesso real, em Streamable
    HTTP, numa porta livre — e garante finalização determinística,
    nunca deixando o processo órfão mesmo se o teste falhar."""
    porta = _porta_livre()
    env = dict(os.environ)
    env["PORT"] = str(porta)
    env["HOST"] = "127.0.0.1"
    script = (
        f"import sys; sys.path.insert(0, r'{MCP_SERVER_DIR}'); "
        "import server; server.main()"
    )
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        cwd=str(BASE), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        prazo = time.monotonic() + 15.0
        while time.monotonic() < prazo:
            if proc.poll() is not None:
                saida = proc.stdout.read() if proc.stdout else ""
                raise RuntimeError(
                    f"Servidor MCP encerrou prematuramente (exit={proc.returncode}):\n{saida}"
                )
            if _porta_aceita_conexao("127.0.0.1", porta):
                break
            time.sleep(0.1)
        else:
            raise TimeoutError("Servidor MCP não passou a aceitar conexões em 15s")

        yield f"http://127.0.0.1:{porta}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.mcp_transport
@pytest.mark.anyio
async def test_streamable_http_real_ede_health(servidor_http_real):
    """CLIENTE MCP -> HTTP real -> servidor -> ede_health -> resposta
    estruturada. Client real (mcp.Client), transporte real (Streamable
    HTTP sobre socket loopback), processo real — nada in-memory."""
    from mcp import Client

    async with Client(servidor_http_real, raise_exceptions=True) as client:
        tools = await client.list_tools()
        nomes = {t.name for t in tools.tools}
        assert "ede_health" in nomes

        resultado = await client.call_tool("ede_health", {})
        assert resultado.is_error is not True
        dados = resultado.structured_content
        assert dados is not None
        assert dados["service_status"] == "READY"
        assert dados["contestacao_status"] == "NOT_READY"
        assert dados["checks"]["rag"]["status"] == "NOT_CONFIGURED"
        assert dados["checks"]["modelo_oficial"]["status"] == "NOT_CONFIGURED"
