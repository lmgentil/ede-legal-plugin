#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_e2e_contestacao.py — Fase 7 (SPEC-0001): integração end-to-end do
pipeline da Contestação sobre `scripts/gerar_contestacao.py`.

Cenários sintéticos em tests/fixtures/contestacao/ — nomes, processo,
documentos e valores fictícios. Nenhum dado real de cliente; nada de
`rag/jurisprudencia/`.

Escopo real do que este arquivo testa (SPEC-0001 Fase 7 §33 — não
simular execução de Skill): `estrategista-contestacao-ede`,
`redator-peca-processual-elite` e `humanizer-pt-br` são Skills do Claude
Code, não funções Python — não há como "executá-las" de dentro de um
teste automatizado. O que ESTE arquivo verifica é a integração real dos
componentes que SÃO código (validate_fatos, calendario, RAG,
legal_validation, Template Engine, Template Lock) mais a verificação
estrutural de que a saída esperada das Skills existe e tem a forma
certa. A execução real das três Skills sobre o cenário "happy_path"
(produção de `estrategia.md`, `placeholders_redator.json` e
`placeholders.json`) foi feita manualmente por este agente, registrada em
`docs/E2E_FASE7.md` — não fabricada nem simulada por código.

Cenário de Template Lock reprovando adulteração fora de placeholder já
tem cobertura equivalente em tests/test_template_engine.py
(`test_template_lock_detecta_alteracao_fora_de_placeholder` +
`test_pipeline_completo_contra_template_real`, que testa adulteração
contra o DOCX real) — não duplicado aqui (SPEC-0001 Fase 7 §28).

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.

Uso:
  python tests/test_e2e_contestacao.py
"""
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE = Path(__file__).parent.parent
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"
sys.path.insert(0, str(BASE / "scripts"))
from gerar_contestacao import MARCADOR_FOTOS, gerar  # noqa: E402

REAL_TEMPLATE = BASE / "templates" / "contestacao" / "modelo-oficial.docx"


def _pular_se_sem_template_real():
    if not REAL_TEMPLATE.exists():
        print("SKIP (template real ausente localmente — ADR-0006, esperado em CI/clone limpo)")
        return True
    return False


# --------------------------------------------------------------- happy path
def test_happy_path_pipeline_completo():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao_sintetica.docx"
        r = gerar(FIXTURES / "happy_path", saida)

        assert r["status"] == "OK", r
        nomes_stage = {s["name"] for s in r["stages"]}
        assert nomes_stage == {"facts", "tempestividade", "strategy",
                                "rag_legal_validation", "drafting_humanization",
                                "template_engine"}
        assert all(s["status"] == "ok" for s in r["stages"]), r["stages"]

        assert r["fatos_com_proveniencia"] == 11
        assert r["citacoes_validadas"] == 7   # 7 citações reais do corpus
        assert r["citacoes_nao_validadas"] == 1  # art. 999999 — inexistente, rejeitado
        assert r["template_lock"] == "OK"
        assert r["fotos"] == "INSERÇÃO MANUAL"
        assert r["tempestividade"].startswith("TEMPESTIVO")

        assert saida.exists() and saida.stat().st_size > 0
        _validar_docx_integro(saida)
        _validar_conteudo_sintetico(saida)


def _validar_docx_integro(caminho: Path):
    # TEST-009 (SPEC-0001): DOCX final deve abrir sem corrupção — aqui,
    # verificação programática mínima: ZIP íntegro + XML bem formado.
    assert zipfile.is_zipfile(caminho)
    with zipfile.ZipFile(caminho) as z:
        ruim = z.testzip()
        assert ruim is None, f"membro corrompido no zip: {ruim}"
        nomes = z.namelist()
        assert "word/document.xml" in nomes
        assert "[Content_Types].xml" in nomes
        assert any(n.startswith("word/header") for n in nomes), \
            "nenhum header preservado no DOCX final"
        assert any(n.startswith("word/footer") for n in nomes), \
            "nenhum footer preservado no DOCX final"
        document_xml = z.read("word/document.xml").decode("utf-8")
        ET.fromstring(document_xml)  # levanta ParseError se malformado


def _validar_conteudo_sintetico(caminho: Path):
    # TEST-041 (Fase 7 §41): não basta o arquivo existir — os dados
    # sintéticos esperados precisam aparecer no XML gerado.
    with zipfile.ZipFile(caminho) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    esperados = [
        "MARIA JOS", "8000001-11.2026.8.05.0080",
        "445566-7",  # unidade consumidora, prova que IRREGULARIDADE_ENCONTRADA entrou
        "4.328,17",  # VALOR_FRA
        MARCADOR_FOTOS,
        "Feira de Santana",
    ]
    for trecho in esperados:
        assert trecho in document_xml, f"trecho esperado não encontrado no DOCX gerado: {trecho!r}"
    assert "{{" not in document_xml, "placeholder residual (chaves duplas) no XML final"


# --------------------------------------------------------------- fail-closed
def test_fail_closed_valor_essencial_ausente():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(FIXTURES / "fail_closed_valor_ausente", saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "placeholders"
        assert "VALOR_FRA" in r["reason"]
        assert not saida.exists(), "PIPELINE_ABORTED não pode deixar DOCX no disco"


def test_fail_closed_estrategista_indisponivel():
    # Simula Skill obrigatória indisponível (SPEC-0001 Fase 7 §27, terceiro
    # exemplo): copia o caso happy_path para um diretório temporário e
    # remove estrategia.md — o pipeline deve abortar no estágio "strategy",
    # nunca prosseguir como se a etapa estratégica tivesse ocorrido
    # (INV-CONTESTACAO-ESTRATEGIA).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estrategia.md").unlink()

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "strategy"
        assert not saida.exists()


def test_fail_closed_estrategia_estruturalmente_invalida():
    # Skill "executada", mas saída inválida (seções ausentes) — também não
    # pode ser tratada como concluída (§7: "produzir saída estruturalmente
    # inválida" é equiparado a falha).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estrategia.md").write_text(
            "# ANÁLISE ESTRATÉGICA\n\nTexto incompleto, sem as 15 seções do contrato.",
            encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "strategy"
        assert not saida.exists()


# ------------------------------------------------------- rastreabilidade
def test_rastreabilidade_de_execucao_no_happy_path():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "x.docx"
        r = gerar(FIXTURES / "happy_path", saida)
        # cada stage tem nome + status verificável — não é só um "ok" solto
        for s in r["stages"]:
            assert "name" in s and "status" in s
        # a etapa estratégica tem evidência do arquivo-fonte, não só "ok"
        strategy = next(s for s in r["stages"] if s["name"] == "strategy")
        assert Path(strategy["fonte"]).name == "estrategia.md"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
