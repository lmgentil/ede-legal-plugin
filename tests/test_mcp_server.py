# -*- coding: utf-8 -*-
"""
tests/test_mcp_server.py — contrato do EDE MCP Server mínimo
(Etapa 6.1, ADR-0015).

Cobre exatamente o que a Etapa 6.1 promete e nada mais: o servidor
inicializa, `ede_health` existe e responde conforme o schema, distingue
`service_status` de `contestacao_status`, é fail-closed diante de erro
interno, e não carrega nenhuma dependência reservada a etapas futuras
(RAG) nem depende do host Claude (`CLAUDE_PLUGIN_ROOT`) ou do Modelo
Oficial real.

Usa o client MCP oficial in-memory do SDK (`mcp.Client`) para os testes
de contrato via protocolo — nunca mock de protocolo (item 10 do pedido:
"não testar protocolo por mocks frágeis se o SDK fornecer mecanismo
oficial"). Testes de comportamento puro (fail-closed, versionamento)
chamam a função Python diretamente: `@mcp.tool()` devolve a função
original sem envolvê-la (mcp/server/mcpserver/server.py, `MCPServer.tool`
-> `decorator` -> `return fn`), então `ede_health` importado deste módulo
já é a função de negócio, sem precisar do transporte para testá-la.

Não depende de nenhum artefato de caso (fatos.json, tempestividade,
Modelo Oficial) nem altera nada em scripts/, rag/ ou skills/ — suíte
inteiramente isolada em mcp_server/.
"""
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
MCP_SERVER_DIR = BASE / "mcp_server"

sys.path.insert(0, str(MCP_SERVER_DIR))

import server as ede_mcp_server  # noqa: E402
from server import ede_health, mcp  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    from mcp import Client

    async with Client(mcp, raise_exceptions=True) as c:
        yield c


# --------------------------------------------------------------- inicialização

def test_servidor_inicializa():
    """mcp_server/server.py importa sem exceção e expõe uma instância
    real de MCPServer (item 10 do pedido: "servidor inicializa")."""
    from mcp.server import MCPServer

    assert isinstance(mcp, MCPServer)


# ------------------------------------------------------------------ ede_health

@pytest.mark.anyio
async def test_ede_health_ferramenta_registrada(client):
    """ede_health existe e é anunciada pelo protocolo MCP (não só como
    função Python solta)."""
    tools = await client.list_tools()
    nomes = {t.name for t in tools.tools}
    assert "ede_health" in nomes


@pytest.mark.anyio
async def test_ede_health_schema_estruturado(client):
    """Chamando por protocolo (não em processo), a resposta tem conteúdo
    estruturado batendo com o schema de EdeHealthResponse."""
    result = await client.call_tool("ede_health", {})
    assert result.is_error is not True
    dados = result.structured_content
    assert dados is not None
    for campo in ("service_status", "contestacao_status", "version", "runtime", "checks"):
        assert campo in dados
    assert set(dados["checks"].keys()) >= {"process", "rag", "modelo_oficial"}


def test_ede_health_versionamento():
    """version bate com o arquivo VERSION da raiz do repositório — nunca
    hardcoded aqui, para o teste não quebrar a cada bump de versão."""
    resposta = ede_health()
    versao_arquivo = (BASE / "VERSION").read_text(encoding="utf-8").strip()
    assert resposta.version == versao_arquivo


def test_service_ready_separado_de_contestacao_ready():
    """Prova central da Etapa 6.1 (itens 5/7 do pedido): o servidor pode
    estar operacional (service_status=READY) sem estar apto a gerar uma
    Contestação (contestacao_status=NOT_READY) — os dois nunca são
    fundidos num único campo "status"."""
    resposta = ede_health()
    assert resposta.service_status == "READY"
    assert resposta.contestacao_status == "NOT_READY"
    assert resposta.checks["rag"].status.value == "NOT_CONFIGURED"
    assert resposta.checks["modelo_oficial"].status.value == "NOT_CONFIGURED"


def test_erro_interno_nunca_vira_ready(monkeypatch):
    """Fail-closed (CLAUDE.md §17): se o cálculo do diagnóstico lançar
    exceção, a resposta é ERROR estruturado — nunca READY — e a exceção/
    stack trace crua nunca é exposta ao chamador."""

    def _falha():
        raise RuntimeError("falha sintética de teste — nunca deve vazar ao chamador")

    monkeypatch.setattr(ede_mcp_server, "_versao_plugin", _falha)
    resposta = ede_health()
    assert resposta.service_status == "ERROR"
    assert resposta.contestacao_status == "NOT_READY"
    assert "falha sintética" not in resposta.checks["process"].detail
    assert "RuntimeError" not in resposta.checks["process"].detail


def test_nenhum_dado_juridico_necessario():
    """ede_health não recebe nem exige nenhum artefato de caso (fatos,
    tempestividade, placeholders, citações) — chamável isoladamente."""
    assinatura = inspect.signature(ede_health)
    assert len(assinatura.parameters) == 0


def test_nenhuma_referencia_a_modelo_oficial_real():
    """Nem o texto-fonte nem a execução tocam o Modelo Oficial
    (CLAUDE.md §13; ADR-0009) — o servidor mínimo nunca acessa
    templates/contestacao/modelo-oficial.docx."""
    codigo_fonte = (MCP_SERVER_DIR / "server.py").read_text(encoding="utf-8")
    assert "modelo-oficial.docx" not in codigo_fonte

    resposta = ede_health()
    assert resposta.checks["modelo_oficial"].status.value == "NOT_CONFIGURED"


def test_nenhuma_dependencia_de_claude_plugin_root():
    """Host-agnostic (mesmo princípio do EDE Core, ADR-0014): nada em
    mcp_server LÊ CLAUDE_PLUGIN_ROOT do ambiente (mencionar o nome em
    docstring/comentário para DISCLAIMAR a dependência é convenção já
    usada em scripts/docx_package.py e scripts/instalar_modelo_oficial.py
    — legítimo; ler a variável é que não seria). O servidor também
    precisa funcionar de verdade com a variável ausente do ambiente
    (processo isolado, ambiente limpo)."""
    codigo_fonte = (MCP_SERVER_DIR / "server.py").read_text(encoding="utf-8")
    padroes_de_leitura = (
        'environ.get("CLAUDE_PLUGIN_ROOT")', "environ.get('CLAUDE_PLUGIN_ROOT')",
        'environ["CLAUDE_PLUGIN_ROOT"]', "environ['CLAUDE_PLUGIN_ROOT']",
        'getenv("CLAUDE_PLUGIN_ROOT"', "getenv('CLAUDE_PLUGIN_ROOT'",
    )
    assert not any(p in codigo_fonte for p in padroes_de_leitura)

    ambiente_sem_var = dict(os.environ)
    ambiente_sem_var.pop("CLAUDE_PLUGIN_ROOT", None)
    script = (
        f"import sys; sys.path.insert(0, r'{MCP_SERVER_DIR}'); "
        "import server; r = server.ede_health(); "
        "print(r.service_status)"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(BASE), capture_output=True, text=True, env=ambiente_sem_var, timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "READY"


def test_nenhuma_dependencia_de_pyarrow_ou_rank_bm25():
    """Etapa 6.1 (itens 8/14 do pedido): o servidor mínimo não deve
    puxar pyarrow/rank_bm25/sentence-transformers/pandas/numpy/joblib só
    para responder ede_health. Verificado em PROCESSO ISOLADO — nunca via
    sys.modules do processo de teste, que pode já ter essas libs
    carregadas por outros testes da suíte (isso seria um teste frágil,
    dependente de ordem de execução)."""
    proibidas = ("pyarrow", "rank_bm25", "sentence_transformers", "pandas", "numpy", "joblib")
    script = (
        f"import sys; sys.path.insert(0, r'{MCP_SERVER_DIR}'); "
        "import server; "
        f"print(sorted(m for m in {proibidas!r} if m in sys.modules))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(BASE), capture_output=True, text=True, timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "[]", resultado.stdout

    requirements = (MCP_SERVER_DIR / "requirements.txt").read_text(encoding="utf-8")
    linhas_ativas = [
        linha for linha in requirements.splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]
    for proibida in proibidas:
        assert not any(proibida in linha for linha in linhas_ativas)
