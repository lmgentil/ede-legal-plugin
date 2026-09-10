#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_homologar_distribuicao.py — harness de homologação de distribuição
(Etapa 5.10, Commit 7: "test(distribuicao): homologar pipeline em clone
limpo").

Testa a MECÂNICA PRÓPRIA do harness (parsing de contagens do pytest,
filtro de ambiente do subprocesso, busca de caminho privado, fórmula de
aprovação de Fase 8, invocação/parsing das ferramentas já testadas em
seus próprios arquivos) — nunca reimplementa nem reexercita a lógica de
negócio de `docx_package.py`/`ede_doctor.py`/`instalar_modelo_oficial.py`/
`gerar_contestacao.py`, já cobertos em `tests/test_docx_package.py`,
`tests/test_ede_doctor.py`, `tests/test_instalar_modelo_oficial.py`,
`tests/test_e2e_contestacao.py` etc.

Os testes que precisam de um "clone" usam CÓPIA REAL de `scripts/`
(nunca reimplementada) sobre um par schema/catálogo SINTÉTICO mínimo
(mesmo padrão de tests/test_ede_doctor.py) — nunca um `git clone` de
verdade (caro, desnecessário para testar só a mecânica do harness; o
harness real já prova a homologação completa via clone Git de verdade,
não repetida aqui). O único cenário que precisa do Modelo Oficial real
("happy path aprovado", Fase 17 do pedido) é `docx_real`, com `pytest.skip`
explícito quando o asset não está instalado.

Uso:
  python tests/test_homologar_distribuicao.py
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import homologar_distribuicao as h  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
FIXTURE_HAPPY_PATH = BASE / "tests" / "fixtures" / "contestacao" / "happy_path"

SCHEMA_MINIMO = {"editable_placeholders": ["FOO"], "version": "9.9.9-teste"}
CATALOGO_MINIMO = {
    "version": "9.9.9-teste",
    "blocks": [
        {"id": "BLOCO_FOO", "tag": "BLOCO:FOO", "tipo": "FIXO", "parent": None,
         "children": [], "decision_mode": "estrategista", "cardinality": "ONE"},
    ],
    "zones": [],
}


def _copiar_apenas_py(origem: Path, destino: Path) -> None:
    """Copia só os `.py` de `origem` para `destino`, preservando a árvore
    de diretórios — usado para `rag/`, cujo código (search_hybrid.py,
    legal_validation/, embeddings/artifact_contract.py) precisa existir
    para gerar_contestacao.py importar no nível de módulo, mas cujos
    dados (~49MB de .parquet/.joblib/índices) são irrelevantes para um
    pipeline que aborta antes de qualquer etapa de RAG de verdade."""
    for arq in origem.rglob("*.py"):
        rel = arq.relative_to(origem)
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, alvo)


def _construir_pseudo_clone(tmp: Path, incluir_rag=True) -> Path:
    """CÓPIA REAL de scripts/ (nunca reimplementada) + contrato SINTÉTICO
    mínimo em templates/contestacao/ — suficiente para exercitar
    `rodar_doctor`/`rodar_bootstrap`/`rodar_happy_path` (que só invocam os
    scripts via subprocesso) sem precisar de `git clone` nem do Modelo
    Oficial real. `gerar_contestacao.BASE` se resolve sozinho a partir de
    onde o arquivo foi copiado (`Path(__file__).parent.parent`) — a mesma
    propriedade host-agnostic que o harness real explora contra o clone
    Git de verdade."""
    raiz = Path(tempfile.mkdtemp(dir=str(tmp), prefix="pseudo_clone_"))
    shutil.copytree(BASE / "scripts", raiz / "scripts")
    # gerar_contestacao.py insere BASE/skills/calendario-forense-tjba-2026/
    # scripts e BASE/rag no sys.path e importa calcular_tempestividade/
    # legal_validation (que por sua vez importa search_hybrid/embeddings.
    # artifact_contract) no nível de módulo — código real, nunca
    # reimplementado. Dados de rag/ (~49MB) excluídos via
    # _copiar_apenas_py: irrelevantes para um pipeline que aborta antes
    # de qualquer etapa de RAG de verdade.
    shutil.copytree(BASE / "skills" / "calendario-forense-tjba-2026",
                     raiz / "skills" / "calendario-forense-tjba-2026")
    _copiar_apenas_py(BASE / "rag", raiz / "rag")
    (raiz / "templates" / "contestacao").mkdir(parents=True)
    (raiz / "templates" / "contestacao" / "schema.json").write_text(
        json.dumps(SCHEMA_MINIMO, ensure_ascii=False), encoding="utf-8")
    (raiz / "templates" / "contestacao" / "blocos.json").write_text(
        json.dumps(CATALOGO_MINIMO, ensure_ascii=False), encoding="utf-8")
    if incluir_rag:
        (raiz / "rag" / "config.yaml").write_text("alpha: 0.5\n", encoding="utf-8")
        (raiz / "rag" / "index_artigos.json").write_text("{}", encoding="utf-8")
    return raiz


def _docx_sintetico_compativel(destino: Path) -> Path:
    """DOCX sintético compatível com SCHEMA_MINIMO/CATALOGO_MINIMO — mesma
    técnica de tests/test_instalar_modelo_oficial.py (zipfile puro)."""
    import zipfile
    content_types = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="xml" ContentType="application/xml"/>'
        b'<Override PartName="/word/document.xml" ContentType='
        b'"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        b'</Types>'
    )
    rels_raiz = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        b'Target="word/document.xml"/></Relationships>'
    )
    document_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:body><w:sdt><w:sdtPr><w:tag w:val="BLOCO:FOO"/></w:sdtPr>'
        b'<w:sdtContent><w:p><w:r><w:t>{{FOO}}</w:t></w:r></w:p></w:sdtContent></w:sdt>'
        b'</w:body></w:document>'
    )
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_raiz)
        zf.writestr("word/document.xml", document_xml)
    return destino


# --------------------------------------------------------------- funções puras
def test_extrair_contagens_varios_formatos():
    casos = [
        ("603 passed, 57 skipped in 40.56s", {"passed": 603, "failed": 0, "skipped": 57}),
        ("1 failed, 659 passed in 85.27s", {"passed": 659, "failed": 1, "skipped": 0}),
        ("30 passed, 3 skipped, 627 deselected in 24.88s", {"passed": 30, "failed": 0, "skipped": 3}),
        ("no tests ran in 0.01s", {"passed": 0, "failed": 0, "skipped": 0}),
    ]
    for stdout, esperado in casos:
        r = h._extrair_contagens(stdout)
        assert r["passed"] == esperado["passed"], stdout
        assert r["failed"] == esperado["failed"], stdout
        assert r["skipped"] == esperado["skipped"], stdout


def test_ambiente_limpo_remove_pythonpath_e_claude_plugin_root(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/algum/caminho/do/desenvolvedor")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/outro/caminho")
    env = h._ambiente_limpo()
    assert "PYTHONPATH" not in env
    assert "CLAUDE_PLUGIN_ROOT" not in env


def test_buscar_caminho_privado_detecta_substring():
    textos = {"a": "nada aqui", "b": "contém C:\\Users\\dev\\projeto dentro do texto"}
    achados = h.buscar_caminho_privado(textos, "C:\\Users\\dev\\projeto")
    assert achados == {"b": True}


def test_buscar_caminho_privado_nao_detecta_quando_ausente():
    textos = {"a": "nada aqui", "b": "nem aqui"}
    assert h.buscar_caminho_privado(textos, "C:\\Users\\dev\\projeto") == {}


def _checks_base_aprovados():
    return {
        "arquivo_existe": True, "tamanho_bytes": 12345, "zip_docx_valido": True,
        "estrutura_minima_ok": True, "zero_placeholder_residual": True,
        "zero_sdt_residual": True, "numeracao_valida": True, "template_lock": "OK",
    }


def test_avaliar_checks_saida_aprovado():
    assert h.avaliar_checks_saida(_checks_base_aprovados()) is True


def test_avaliar_checks_saida_template_lock_falho():
    checks = _checks_base_aprovados()
    checks["template_lock"] = "DIVERGENTE"
    assert h.avaliar_checks_saida(checks) is False


def test_avaliar_checks_saida_placeholder_residual():
    checks = _checks_base_aprovados()
    checks["zero_placeholder_residual"] = False
    assert h.avaliar_checks_saida(checks) is False


def test_resolver_juizo_stub_e_deterministico():
    """Fase 17, cenário 'DataJud fake usado': o stub embutido no driver
    (_RESOLVER_JUIZO_STUB_SRC) devolve sempre o mesmo valor, nunca chama
    rede — mesmos valores de tests/test_e2e_contestacao.py._resolver_juizo_stub
    (Fase 5 do pedido: reaproveitar, não reimplementar)."""
    ns = {}
    exec(compile(h._RESOLVER_JUIZO_STUB_SRC, "stub", "exec"), ns)
    stub = ns["_resolver_juizo_stub"]
    r1 = stub("0000000-00.2026.8.05.0000")
    r2 = stub("1111111-11.2026.8.05.0001")
    assert r1["juizo"] == r2["juizo"] == (
        "AO JUÍZO DA VARA DOS FEITOS DE RELAÇÕES DE CONSUMO DA COMARCA DE FEIRA DE SANTANA")
    assert r1["comarca"] == "Feira de Santana"
    assert r1["tribunal"] == "TJBA"


def test_verificar_ausencias_pre_bootstrap():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = h.verificar_ausencias_pre_bootstrap(tmp)
        assert r == {"skills_docx_ausente": True, "modelo_oficial_ausente": True}

        (tmp / "skills" / "docx").mkdir(parents=True)
        (tmp / "templates" / "contestacao").mkdir(parents=True)
        (tmp / "templates" / "contestacao" / "modelo-oficial.docx").write_bytes(b"x")
        r2 = h.verificar_ausencias_pre_bootstrap(tmp)
        assert r2 == {"skills_docx_ausente": False, "modelo_oficial_ausente": False}


def test_buscar_dependencias_skills_docx_classifica_ocorrencias():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "scripts").mkdir()
        (tmp / "scripts" / "exemplo.py").write_text(
            '"""docstring mencionando skills/docx/ e unpack.py por contexto histórico."""\n'
            "x = 1\n",
            encoding="utf-8")
        achados = h.buscar_dependencias_skills_docx(tmp)
        assert len(achados) == 1
        assert "skills/docx" in achados[0] or "unpack.py" in achados[0]


# --------------------------------------------------------------- pseudo-clone (subprocesso)
def test_doctor_nao_pronto_sem_modelo():
    with tempfile.TemporaryDirectory() as tmp:
        clone = _construir_pseudo_clone(Path(tmp))
        r = h.rodar_doctor(clone, Path(tmp) / "saida_doctor")
        assert r["ready"] is False
        assert "template:modelo-oficial.docx" in r["obrigatorias_falhando"]


def test_bootstrap_rejeitado_arquivo_inexistente():
    with tempfile.TemporaryDirectory() as tmp:
        clone = _construir_pseudo_clone(Path(tmp))
        r = h.rodar_bootstrap(clone, Path(tmp) / "nao_existe.docx")
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == "ARQUIVO_NAO_ENCONTRADO"


def test_doctor_pronto_apos_bootstrap_sintetico():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clone = _construir_pseudo_clone(tmp)
        origem = _docx_sintetico_compativel(tmp / "origem.docx")

        r_bootstrap = h.rodar_bootstrap(clone, origem)
        assert r_bootstrap["status"] == "INSTALADO", r_bootstrap

        r_doctor = h.rodar_doctor(clone, tmp / "saida_doctor")
        assert r_doctor["ready"] is True, r_doctor["obrigatorias_falhando"]


def test_pipeline_abortado_sem_modelo_e_docx_final_ausente():
    """Fase 17: 'pipeline abortado' + 'DOCX final ausente' juntos — sem
    modelo-oficial.docx instalado, a primeira etapa (contexto
    institucional) aborta antes de qualquer outra coisa; o driver nunca
    chega a escrever o .docx de saída."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clone = _construir_pseudo_clone(tmp)
        saida_dir = tmp / "saida"
        saida_dir.mkdir()

        resultado = h.rodar_happy_path(clone, "caso_inexistente", saida_dir)

        assert resultado["relatorio"]["status"] == "PIPELINE_ABORTED"
        assert resultado["relatorio"]["stage"] == "contexto_institucional"
        assert resultado["checks"] == {}
        assert not Path(resultado["_output_path"]).exists()


# --------------------------------------------------------------- docx_real: happy path real
@pytest.mark.docx_real
def test_happy_path_aprovado_contra_repositorio_real():
    """Fase 17, cenário 'happy path aprovado': roda o driver do harness
    direto contra ESTE repositório (BASE) com o Modelo Oficial e a
    fixture happy_path reais — não um git clone (caro/redundante aqui; o
    clone Git de verdade já é exercitado pelo harness real, não por este
    arquivo de teste). `pytest.skip` explícito se o asset não estiver
    instalado localmente (ADR-0009), mesmo padrão da Etapa 5.10, Commit 5."""
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    with tempfile.TemporaryDirectory() as tmp:
        saida_dir = Path(tmp)
        resultado = h.rodar_happy_path(BASE, "tests/fixtures/contestacao/happy_path", saida_dir)
        assert resultado["relatorio"]["status"] == "OK", resultado["relatorio"]
        assert resultado["ok_geral"] is True, resultado["checks"]
        assert resultado["checks"]["template_lock"] == "OK"
        assert resultado["checks"]["zero_placeholder_residual"] is True
        assert resultado["checks"]["zero_sdt_residual"] is True


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        if getattr(t, "pytestmark", None):
            continue  # docx_real / fixtures do pytest — só via `pytest`
        import inspect
        if "monkeypatch" in inspect.signature(t).parameters:
            continue
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes executados (alguns exigem pytest, ver acima).")


if __name__ == "__main__":
    main()
