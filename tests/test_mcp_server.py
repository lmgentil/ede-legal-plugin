# -*- coding: utf-8 -*-
"""
tests/test_mcp_server.py — contrato do EDE MCP Server
(Etapa 6.1, ADR-0015; readiness jurídica desde o Gate 6.4-A).

Cobre: o servidor inicializa, `ede_health` existe e responde conforme o
schema, distingue `service_status` de `contestacao_status`, é
fail-closed diante de erro interno, não depende do host Claude
(`CLAUDE_PLUGIN_ROOT`), e não carrega dependência de análise/busca
(pandas/numpy/pyarrow/rank_bm25/sentence-transformers) só para
responder `ede_health` — mesmo sem RAG/Modelo Oficial serem mais
stubs fixos desde o Gate 6.4-A (ver docstring de
`scripts/legal_readiness.py`: a checagem de saúde do corpus usa só
biblioteca padrão, nunca constrói o índice de busca).

Usa o client MCP oficial in-memory do SDK (`mcp.Client`) para os testes
de contrato via protocolo — nunca mock de protocolo (item 10 do pedido:
"não testar protocolo por mocks frágeis se o SDK fornecer mecanismo
oficial"). Testes de comportamento puro (fail-closed, versionamento)
chamam a função Python diretamente: `@mcp.tool()` devolve a função
original sem envolvê-la (mcp/server/mcpserver/server.py, `MCPServer.tool`
-> `decorator` -> `return fn`), então `ede_health` importado deste módulo
já é a função de negócio, sem precisar do transporte para testá-la.

Não depende de nenhum artefato de CASO (fatos.json, tempestividade) —
a matriz completa de prontidão do corpus RAG/Modelo Oficial é coberta à
parte, em tests/test_legal_readiness.py (Core); esta suíte testa só a
FIAÇÃO do adapter (server.py traduz fielmente o resultado do Core, nunca
reimplementa a validação)."""
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


def test_service_ready_separado_de_contestacao_ready(monkeypatch):
    """Prova central da Etapa 6.1 (itens 5/7 do pedido), preservada no
    Gate 6.4-A: o servidor pode estar operacional (service_status=READY)
    sem estar apto a gerar uma Contestação (contestacao_status=NOT_READY)
    — os dois nunca são fundidos num único campo "status". Sem
    EDE_MODELO_OFICIAL_PATH/_SHA256 configurados (estado real de
    produção hoje), `modelo_oficial` fica NOT_CONFIGURED e isso basta
    para NOT_READY, independentemente do estado do corpus RAG."""
    for var in (
        "EDE_MODELO_OFICIAL_PATH", "EDE_MODELO_OFICIAL_SHA256",
        "EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT",
        "EDE_MODELO_OFICIAL_GCS_GENERATION",
    ):
        monkeypatch.delenv(var, raising=False)
    resposta = ede_health()
    assert resposta.service_status == "READY"
    assert resposta.contestacao_status == "NOT_READY"
    assert resposta.checks["modelo_oficial"].status.value == "NOT_CONFIGURED"


def test_contestacao_ready_exige_todas_as_checagens(monkeypatch):
    """`contestacao_status` só READY quando process/rag/modelo_oficial
    estiverem todos READY — server.py nunca decide isso sozinho, só
    agrega o que scripts/legal_readiness.py (Core) devolveu (ADR-0015:
    adapter fino, nenhuma lógica de validação duplicada aqui)."""
    import legal_readiness

    monkeypatch.setattr(
        legal_readiness, "avaliar_corpus_rag",
        lambda: legal_readiness.ResultadoReadiness("READY", "sintético"),
    )
    monkeypatch.setattr(
        legal_readiness, "avaliar_modelo_oficial",
        lambda: legal_readiness.ResultadoReadiness("READY", "sintético"),
    )
    resposta = ede_health()
    assert resposta.checks["rag"].status.value == "READY"
    assert resposta.checks["modelo_oficial"].status.value == "READY"
    assert resposta.contestacao_status == "READY"


@pytest.mark.docx_real
def test_contestacao_ready_via_gcs_fim_a_fim(monkeypatch):
    """Gate 6.4-B: prova de ponta a ponta através do adapter real — só o
    seam de baixo nível (`_baixar_modelo_oficial_gcs`, a fronteira de
    rede/autenticação) é mockado; toda a orquestração
    (`ede_health` -> `legal_readiness.avaliar_modelo_oficial` ->
    `_validar_conteudo_modelo_oficial` -> SHA-256 -> Template Lock) roda
    de verdade contra o CONTRATO REAL (schema.json/blocos.json, os
    mesmos que `avaliar_modelo_oficial()` usa por default — por isso
    precisa do Modelo Oficial real, não de um DOCX sintético), com o
    corpus RAG real desta checkout (READY sem mock algum)."""
    import hashlib
    import sys
    from unittest.mock import patch

    sys.path.insert(0, str(BASE / "scripts"))
    import legal_readiness

    template_real = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
    if not template_real.is_file():
        pytest.skip(f"{template_real} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    conteudo = template_real.read_bytes()
    sha = hashlib.sha256(conteudo).hexdigest()

    for var in ("EDE_MODELO_OFICIAL_PATH",):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv(legal_readiness.ENV_GCS_BUCKET, "ede-modelo-oficial-privado")
    monkeypatch.setenv(legal_readiness.ENV_GCS_OBJECT, "modelo-oficial/modelo-oficial.docx")
    monkeypatch.setenv(legal_readiness.ENV_GCS_GENERATION, "1234567890123456")
    monkeypatch.setenv(legal_readiness.ENV_MODELO_SHA256, sha)

    with patch.object(legal_readiness, "_baixar_modelo_oficial_gcs", return_value=conteudo):
        resposta = ede_health()

    assert resposta.checks["modelo_oficial"].status.value == "READY", resposta.checks["modelo_oficial"].detail
    assert resposta.checks["rag"].status.value == "READY"
    assert resposta.contestacao_status == "READY"

    monkeypatch.setattr(
        legal_readiness, "avaliar_modelo_oficial",
        lambda: legal_readiness.ResultadoReadiness("NOT_READY", "sintético"),
    )
    resposta2 = ede_health()
    assert resposta2.contestacao_status == "NOT_READY"


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


def test_nenhuma_referencia_a_modelo_oficial_real(monkeypatch):
    """Nem o texto-fonte nem a execução tocam o Modelo Oficial real
    (CLAUDE.md §13; ADR-0009) — server.py não referencia
    "modelo-oficial.docx" (a leitura/validação vive em
    scripts/legal_readiness.py + instalar_modelo_oficial.py, nunca
    duplicada aqui) e, sem EDE_MODELO_OFICIAL_PATH/_SHA256 configurados
    (estado real de produção hoje), a checagem nunca tenta acessar
    arquivo algum."""
    codigo_fonte = (MCP_SERVER_DIR / "server.py").read_text(encoding="utf-8")
    assert "modelo-oficial.docx" not in codigo_fonte

    monkeypatch.delenv("EDE_MODELO_OFICIAL_PATH", raising=False)
    monkeypatch.delenv("EDE_MODELO_OFICIAL_SHA256", raising=False)
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


# ------------------------------------------------- resolução de HOST/PORT
#
# Ajuste obrigatório (mensagem do usuário, pós-Etapa 6.2, commit 25791cd):
# 8080 estava reservada a outro serviço do ambiente local e NUNCA deve
# voltar a ser o default local do EDE MCP; 127.0.0.1:8765 passa a ser o
# único default local. `main()` nunca é chamado de verdade nestes testes
# (bloquearia a suíte inteira, é `mcp.run()`) -- `mcp.run` é substituído
# por um espião que só grava os kwargs recebidos.

def _capturar_chamada_run(monkeypatch):
    capturado: dict = {}
    monkeypatch.setattr(mcp, "run", lambda **kwargs: capturado.update(kwargs))
    return capturado


def test_resolucao_host_port_sem_configuracao(monkeypatch):
    """A. Sem HOST e sem PORT no ambiente, main() resolve para o novo
    default local 127.0.0.1:8765 — nunca mais a porta antiga."""
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    capturado = _capturar_chamada_run(monkeypatch)

    ede_mcp_server.main()

    assert capturado["host"] == "127.0.0.1"
    assert capturado["port"] == 8765
    assert capturado["transport"] == "streamable-http"


def test_resolucao_respeita_host_customizado(monkeypatch):
    """B. HOST customizado é respeitado (ex.: 0.0.0.0 dentro de um
    container) — PORT continua no default local quando ausente."""
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.delenv("PORT", raising=False)
    capturado = _capturar_chamada_run(monkeypatch)

    ede_mcp_server.main()

    assert capturado["host"] == "0.0.0.0"
    assert capturado["port"] == 8765


def test_resolucao_respeita_port_customizada(monkeypatch):
    """C. PORT customizada (ex.: a que o Cloud Run injeta) é respeitada —
    nunca substituída por um valor fixo."""
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("PORT", "9999")
    capturado = _capturar_chamada_run(monkeypatch)

    ede_mcp_server.main()

    assert capturado["host"] == "127.0.0.1"
    assert capturado["port"] == 9999


def test_resolucao_respeita_host_e_port_customizados(monkeypatch):
    """D. HOST e PORT customizados simultaneamente — o cenário real de
    CONTAINER/CLOUD RUN (HOST=0.0.0.0, PORT injetada pela plataforma)."""
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "12345")
    capturado = _capturar_chamada_run(monkeypatch)

    ede_mcp_server.main()

    assert capturado["host"] == "0.0.0.0"
    assert capturado["port"] == 12345


def test_nenhuma_dependencia_funcional_da_porta_antiga():
    """E. Nenhuma ocorrência funcional da porta antiga (8080) permanece
    no EDE MCP Server — nem como default, nem como fallback, nem como
    valor de substituição em qualquer ponto do módulo."""
    codigo_fonte = (MCP_SERVER_DIR / "server.py").read_text(encoding="utf-8")
    assert "8080" not in codigo_fonte
    assert ede_mcp_server.DEFAULT_HOST_LOCAL == "127.0.0.1"
    assert ede_mcp_server.DEFAULT_PORT_LOCAL == 8765
