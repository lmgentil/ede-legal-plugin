# -*- coding: utf-8 -*-
"""
tests/test_docker_context.py — segurança determinística do contexto de
build do EDE MCP Server (Gate 6.4-B §14).

`.dockerignore` é ALLOWLIST (nega tudo com `*`, libera nominalmente cada
caminho) e `mcp_server/Dockerfile` copia arquivo a arquivo — mesma
disciplina já coberta para `mcp_server/*.py` por
`test_mcp_oauth.py::test_todo_modulo_do_servidor_entra_no_contexto_de_build`.
Este módulo generaliza a mesma verificação (toda linha `COPY` tem uma
linha `!caminho` correspondente) para os caminhos novos do Gate 6.4-A
(scripts/, templates/contestacao/, rag/) e prova, pela ausência de
qualquer linha de liberação correspondente, que nenhum asset privado
(Modelo Oficial real, backups, jurisprudência) pode entrar no contexto —
sem depender de um build Docker real (indisponível nesta máquina, mesma
limitação já registrada no cabeçalho de `.dockerignore`).

Não é um motor genérico de pattern-matching de `.dockerignore` (over-
engineering desnecessário para uma allowlist com só linhas exatas e um
punhado de `/**` recursivos) — é uma prova direcionada, específica ao
vocabulário de padrões que este arquivo realmente usa.
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
WORKFLOW_HOMOLOGACAO = (
    BASE / ".github" / "workflows" / "homologar-mcp-container.yml"
).read_text(encoding="utf-8")
DOCKERFILE = (BASE / "mcp_server" / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE_LINHAS = [
    linha.strip()
    for linha in (BASE / ".dockerignore").read_text(encoding="utf-8").splitlines()
    if linha.strip() and not linha.strip().startswith("#")
]
DOCKERIGNORE_PERMITIDOS = {
    linha[1:] for linha in DOCKERIGNORE_LINHAS if linha.startswith("!")
}

_COPY_RE = re.compile(r"^COPY\s+(?:--chown=\S+\s+)?(\S+)\s+(\S+)\s*$", re.MULTILINE)


def _linhas_copy():
    """(origem, destino) de cada instrução COPY do Dockerfile — nunca
    `COPY dir/ dir/` (recursivo cego): cada linha deste projeto copia um
    arquivo ou um diretório nomeado explicitamente, allowlist também no
    Dockerfile, não só no .dockerignore (ver comentário no próprio
    arquivo, Gate 6.4-A)."""
    return _COPY_RE.findall(DOCKERFILE)


# --------------------------------------------------- toda COPY é permitida

def test_toda_instrucao_copy_tem_liberacao_correspondente():
    """Nenhuma linha COPY referencia um caminho ausente de `!<caminho>`
    em `.dockerignore` — se copiasse, o build real falharia por arquivo
    inexistente no contexto (fail-closed real, não silencioso)."""
    for origem, _destino in _linhas_copy():
        assert origem in DOCKERIGNORE_PERMITIDOS, (
            f"COPY {origem} não tem `!{origem}` em .dockerignore — "
            f"entraria no build mas nunca no contexto"
        )


def test_modulos_core_do_gate_6_4_a_liberados():
    """Os cinco módulos Core que scripts/legal_readiness.py importa
    transitivamente, mais o próprio módulo, estão todos liberados e
    copiados — nenhum esquecido silenciosamente."""
    esperados = {
        "scripts/legal_readiness.py",
        "scripts/docx_package.py",
        "scripts/docx_template_engine.py",
        "scripts/docx_block_engine.py",
        "scripts/docx_numeracao_engine.py",
        "scripts/instalar_modelo_oficial.py",
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS
        assert caminho in origens_copiadas


def test_contrato_institucional_publico_liberado():
    for caminho in ("templates/contestacao/schema.json", "templates/contestacao/blocos.json"):
        assert caminho in DOCKERIGNORE_PERMITIDOS
        assert caminho in {o for o, _ in _linhas_copy()}


def test_corpus_manifesto_e_seis_diplomas_liberados():
    esperados = {"rag/corpus_manifest.json"} | {
        f"rag/chunks_{d}" for d in ("CPC", "CC", "CDC", "L8987", "L9427", "REN1000")
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS
        assert caminho in origens_copiadas
        # cada diretório de diploma também tem seu `/**` recursivo, para
        # que TODOS os arquivos dentro dele entrem (não só a entrada do
        # diretório) — sem isso, um builder BuildKit real copiaria um
        # diretório vazio.
        if caminho.startswith("rag/chunks_"):
            assert f"{caminho}/**" in DOCKERIGNORE_PERMITIDOS


# -------------------------------------------- nada perigoso é liberável

def test_nenhum_arquivo_docx_e_liberado():
    """Nenhuma linha `!...` libera QUALQUER `.docx` — nem o Modelo
    Oficial real, nem a variante `_topicos-2.3-a-2.6_contratados`, nem
    backups. `.dockerignore` nunca precisa de uma exclusão específica
    para eles: como a estratégia é allowlist (`*` nega tudo primeiro),
    a mera ausência de uma linha `!*.docx` já basta — provado aqui pela
    negativa, sobre a lista real de linhas do arquivo."""
    docx_liberados = [c for c in DOCKERIGNORE_PERMITIDOS if c.lower().endswith(".docx")]
    assert docx_liberados == []


def test_nenhum_caminho_sensivel_e_liberado():
    proibidos_substr = (
        "modelo-oficial", "backup", "jurisprudencia", "ede-private",
        ".env", ".git/", "credential", "secret", ".cache",
    )
    for caminho in DOCKERIGNORE_PERMITIDOS:
        baixo = caminho.lower()
        for termo in proibidos_substr:
            assert termo not in baixo, f"{caminho!r} contém termo sensível {termo!r}"


def test_rag_embeddings_nao_liberado():
    """`rag/embeddings/` (43 MiB — parquet/joblib, exigiria pandas/numpy/
    pyarrow/scikit-learn só para existir na imagem) permanece de fora:
    a checagem de saúde do corpus usa só os chunks de texto + manifesto,
    nunca o índice de busca (Gate 6.4-A)."""
    assert not any(c.startswith("rag/embeddings") for c in DOCKERIGNORE_PERMITIDOS)


def test_rag_config_yaml_nao_e_necessario_e_nao_e_liberado():
    """`rag/config.yaml` é consumido por `rag/search_hybrid.py` (fora do
    escopo deste servidor — nenhuma ferramenta de busca é exposta),
    nunca por `scripts/legal_readiness.py` (lê só
    `rag/corpus_manifest.json` + os diretórios `chunks_*/`, com
    biblioteca padrão). Ausência do build context é intencional, não um
    esquecimento a corrigir."""
    assert "rag/config.yaml" not in DOCKERIGNORE_PERMITIDOS
    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    codigo_fonte = (BASE / "scripts" / "legal_readiness.py").read_text(encoding="utf-8")
    assert "config.yaml" not in codigo_fonte


def test_diretorios_de_corpus_nao_elegiveis_ausentes():
    """Diplomas fora do manifesto de produção (nenhum hoje) e diretórios
    auxiliares do RAG (`_originais_pre_split`, `embeddings`) nunca
    aparecem na allowlist — só os seis `chunks_*` do manifesto e, desde
    o Gate 6.5-A, `rag/legal_validation` (só `models.py`, ver teste
    dedicado abaixo — nunca o pacote inteiro)."""
    diretorios_rag_liberados = {
        c for c in DOCKERIGNORE_PERMITIDOS
        if c.startswith("rag/") and c not in ("rag/corpus_manifest.json",)
    }
    diretorios_rag_liberados = {c.split("/**")[0] for c in diretorios_rag_liberados}
    esperado = {f"rag/chunks_{d}" for d in ("CPC", "CC", "CDC", "L8987", "L9427", "REN1000")}
    esperado |= {"rag/legal_validation", "rag/legal_validation/models.py"}
    assert diretorios_rag_liberados == esperado


def test_legal_validation_so_libera_models_py():
    """Gate 6.5-A: `rag/legal_validation/__init__.py` nunca é liberado —
    importaria `citation_parser.py` -> `rag/search_hybrid.py` inteiro
    (pandas/numpy/scikit-learn/pyarrow/rank_bm25), o oposto do footprint
    mínimo que este servidor mantém desde o Gate 6.4-A."""
    liberados_legal_validation = {
        c for c in DOCKERIGNORE_PERMITIDOS if c.startswith("rag/legal_validation/")
    }
    assert liberados_legal_validation == {"rag/legal_validation/models.py"}
    assert "rag/legal_validation/__init__.py" not in DOCKERIGNORE_PERMITIDOS
    assert "rag/legal_validation/citation_parser.py" not in DOCKERIGNORE_PERMITIDOS


def test_modulos_core_do_gate_6_5_a_liberados():
    """`scripts/preparar_contestacao.py` e seus dois módulos Core novos
    (`docx_context_engine.py`, `validate_fatos.py`) — nunca `gerar_
    contestacao.py`/`datajud_client.py` inteiros (este gate não expõe
    geração de DOCX nem consulta DataJud, Gate 6.5-A §11)."""
    esperados = {
        "scripts/preparar_contestacao.py",
        "scripts/docx_context_engine.py",
        "scripts/validate_fatos.py",
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS
        assert caminho in origens_copiadas
    # ADR-0021: `datajud_client.py` passou a entrar na imagem para o
    # FINALIZADOR resolver JUIZO; a preparação continua sem consultar o
    # DataJud (provado em test_preparacao_continua_sem_datajud abaixo).
    assert "scripts/gerar_contestacao.py" not in DOCKERIGNORE_PERMITIDOS


def test_preparacao_continua_sem_datajud():
    """Gate 6.5-A §11 continua valendo para `ede_preparar_contestacao`:
    o módulo não importa o cliente DataJud (ADR-0021 só muda o
    finalizador)."""
    fonte = (BASE / "scripts" / "preparar_contestacao.py").read_text(encoding="utf-8")
    assert "import datajud_client" not in fonte and "from datajud_client" not in fonte


def test_modulos_core_da_adr_0021_liberados():
    """Dados derivados pelo sistema no finalizador V1 (ADR-0021): cliente
    DataJud, data da peça, proveito econômico, redação da tempestividade,
    zonas, e só os dois arquivos da skill de calendário usados no cálculo."""
    esperados = {
        "scripts/datajud_client.py",
        "scripts/dados_derivados.py",
        "scripts/proveito_economico.py",
        "scripts/tempestividade_texto.py",
        "scripts/zonas_conteudo.py",
        "skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py",
        "skills/calendario-forense-tjba-2026/feriados_forenses_tjba_2026.json",
        "templates/contestacao/v1/manifesto-1.1.0.json",
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS, caminho
        assert caminho in origens_copiadas, caminho
    assert "skills/calendario-forense-tjba-2026/SKILL.md" not in DOCKERIGNORE_PERMITIDOS


def test_modulos_core_do_gate_6_6_c_liberados():
    """`scripts/finalizar_peca.py` e os cinco módulos Core que ele importa
    e que nenhum gate anterior tinha liberado: `capability_registry.py`
    (registro de capacidades), `validate_paragrafos.py`/`validate_
    placeholder_semantics.py` (validação estrutural/semântica pré-render,
    Gate 6.6-A) e `docx_fidelidade_independente.py`/`docx_round_trip.py`
    (verificação pós-render que nunca chama as funções de composição/
    substituição do próprio renderer, Gate 6.6-A) — nenhum esquecido
    silenciosamente. `gerar_contestacao.py` continua de fora. (Até a
    ADR-0021 o `datajud_client.py` também ficava: o finalizador passou a
    resolver `JUIZO` e a tempestividade — ver teste da ADR-0021.)"""
    esperados = {
        "scripts/finalizar_peca.py",
        "scripts/capability_registry.py",
        "scripts/validate_paragrafos.py",
        "scripts/validate_placeholder_semantics.py",
        "scripts/docx_fidelidade_independente.py",
        "scripts/docx_round_trip.py",
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS
        assert caminho in origens_copiadas
    assert "scripts/gerar_contestacao.py" not in DOCKERIGNORE_PERMITIDOS


def test_modulos_core_do_gate_6_6_e_liberados():
    """Gate 6.6-E (entrega v2 do artefato) e sua continuação (limpeza
    agendada): `artifact_storage.py` é o Core de armazenamento/
    assinatura chamado por `finalizar_peca.py`; `limpar_artefatos_
    agendado.py` é o entrypoint da limpeza AGENDADA, que roda a partir
    da MESMA imagem de runtime (um Cloud Run Job troca só o comando do
    container) — nunca uma segunda implementação de exclusão fora da
    imagem. Os dois precisam estar liberados nas DUAS allowlists
    independentes (`.dockerignore` e as linhas `COPY` do Dockerfile);
    esquecer qualquer uma quebra o import dentro do container, fail-
    closed, em vez de rodar sem a checagem que deveria carregar."""
    esperados = {
        "scripts/artifact_storage.py",
        "scripts/limpar_artefatos_agendado.py",
    }
    origens_copiadas = {origem for origem, _ in _linhas_copy()}
    for caminho in esperados:
        assert caminho in DOCKERIGNORE_PERMITIDOS, caminho
        assert caminho in origens_copiadas, caminho


# --------------------------------- allowlist independente do workflow CI

def test_allowlist_de_scripts_do_workflow_ci_espelha_o_dockerignore():
    """`homologar-mcp-container.yml` tem sua PRÓPRIA allowlist fechada de
    `scripts/*.py` (prova de DENTRO da imagem real construída, deliberada
    e independente de `.dockerignore`/`Dockerfile` — nunca confia só na
    configuração de build) — achado real do Gate 6.6-C: essa terceira
    lista ficou esquecida quando os seis módulos do finalizador foram
    liberados nas outras duas, e a homologação real falhou
    (`ARQUIVO INESPERADO EM /app/scripts NA IMAGEM`) por isso. Esta prova
    trava as duas listas uma contra a outra a partir de agora — nenhuma
    pode divergir silenciosamente da outra."""
    bloco = re.search(
        r"find /app/scripts -maxdepth 1 -type f(.*?)2>/dev/null \|\| true\)",
        WORKFLOW_HOMOLOGACAO, re.DOTALL,
    )
    assert bloco, "bloco `achados_scripts=$(find /app/scripts ...)` não encontrado no workflow"
    liberados_workflow = {
        nome for nome in re.findall(r'! -name "([^"]+)"', bloco.group(1))
        if nome.endswith(".py")
    }
    assert liberados_workflow, "nenhum `! -name \"*.py\"` extraído do bloco — regex desalinhada com o workflow real"

    liberados_dockerignore = {
        Path(c).name for c in DOCKERIGNORE_PERMITIDOS
        if c.startswith("scripts/") and c.endswith(".py")
    }
    assert liberados_workflow == liberados_dockerignore, (
        f"scripts/*.py liberados só no workflow CI: "
        f"{sorted(liberados_workflow - liberados_dockerignore)}; "
        f"só no .dockerignore: {sorted(liberados_dockerignore - liberados_workflow)}"
    )


# ------------------------------------------------ corpus real no disco

def test_arquivos_reais_do_corpus_ficam_sob_diretorios_liberados():
    """Enumera de verdade os arquivos em disco de cada `chunks_<diploma>`
    liberado e confirma que nenhum arquivo do corpus real vive fora dos
    seis diretórios explicitamente copiados — o padrão recursivo
    `!rag/chunks_X/**` cobre 100% do corpus real, não uma amostra."""
    for diploma in ("CPC", "CC", "CDC", "L8987", "L9427", "REN1000"):
        dirp = BASE / "rag" / f"chunks_{diploma}"
        assert dirp.is_dir()
        arquivos = list(dirp.rglob("*"))
        assert any(f.is_file() for f in arquivos), f"chunks_{diploma} está vazio"


def test_manifesto_declara_exatamente_os_diretorios_copiados():
    import json
    manifesto = json.loads((BASE / "rag" / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert set(manifesto["diplomas"]) == {"CPC", "CC", "CDC", "L8987", "L9427", "REN1000"}
