#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fail_closed_docx_package.py — contrato de erro do runtime DOCX
(Etapa 5.10, Commit 4: "fix(contestacao): padronizar fail-closed do
runtime DOCX").

Diferente de tests/test_docx_package.py (unidade do módulo
docx_package.py isolado), este arquivo testa como os CONSUMIDORES
(docx_template_engine.gerar_peca, docx_block_engine.gerar_peca_com_blocos,
gerar_contestacao.gerar) REPORTAM falhas de PacoteDocxAbortada — nunca
traceback cru, sempre um relatório estruturado com `stage`/`etapa`
preservando a informação original, e NUNCA convertendo um bug de
programação genuíno (não um dos casos ambientais/documentais conhecidos)
em sucesso silencioso ou em PIPELINE_ABORTED.

Todos os pacotes DOCX são sintéticos (zipfile puro). `SCHEMA_REAL`/
`CATALOGO_REAL` apontam para templates/contestacao/schema.json e
blocos.json — versionados no git, nunca `modelo-oficial.docx`. Nenhum
teste depende de skills/docx/, do ambiente Claude, de OpenAI/MCP ou do
DataJud real (a etapa que dependeria de DataJud nunca é alcançada — os
cenários aqui abortam antes dela).

Uso:
  python tests/test_fail_closed_docx_package.py
"""
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_package import PacoteDocxAbortada  # noqa: E402
from docx_template_engine import gerar_peca  # noqa: E402
from docx_block_engine import carregar_catalogo, gerar_peca_com_blocos  # noqa: E402
import docx_block_engine  # noqa: E402
import gerar_contestacao  # noqa: E402

SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"

_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" ContentType='
    b'"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    b'</Types>'
)
_RELS_RAIZ = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    b'Target="word/document.xml"/></Relationships>'
)
_DOCUMENT_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b'<w:body><w:p><w:r><w:t>ola</w:t></w:r></w:p></w:body></w:document>'
)


def _zip_com_partes(destino: Path, partes: dict, entradas_brutas=None) -> Path:
    """Mesma técnica de tests/test_docx_package.py — zipfile puro,
    independente do código sob teste."""
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in partes.items():
            zf.writestr(nome, conteudo)
        for nome, conteudo, external_attr in (entradas_brutas or []):
            info = zipfile.ZipInfo(nome)
            info.external_attr = external_attr
            zf.writestr(info, conteudo)
    return destino


def _decisoes_tudo_excluido():
    """EXCLUIR é sempre aceito pelos gates (§ requires_fact só restringe
    INCLUIR) — dispensa fatos_processuais, o mínimo necessário para passar
    por validar_e_resolver_decisoes sem depender de nenhum estado
    processual do caso."""
    catalogo = carregar_catalogo(CATALOGO_REAL)
    return {b["id"]: {"decisao": "EXCLUIR"} for b in catalogo["blocks"]
            if b["decision_mode"] in ("estrategista", "humano")}


# ------------------------------------------------------------- A: template ausente

def test_A_template_ausente_gerar_peca_retorna_falhou_sem_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = gerar_peca(tmp / "nao_existe.docx", SCHEMA_REAL, {}, tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "template"


def test_A_template_ausente_gerar_peca_com_blocos_retorna_falhou_sem_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = gerar_peca_com_blocos(tmp / "nao_existe.docx", SCHEMA_REAL, CATALOGO_REAL,
                                   {}, _decisoes_tudo_excluido(), tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "template"


# ------------------------------------------------------------- B: DOCX não é ZIP

def test_B_docx_nao_zip_gerar_peca_reporta_docx_package_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lixo = tmp / "nao_e_docx.docx"
        lixo.write_bytes(b"isto nao e um zip valido")
        r = gerar_peca(lixo, SCHEMA_REAL, {}, tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_invalido"


def test_B_docx_nao_zip_gerar_peca_com_blocos_reporta_docx_package_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lixo = tmp / "nao_e_docx.docx"
        lixo.write_bytes(b"isto nao e um zip valido")
        r = gerar_peca_com_blocos(lixo, SCHEMA_REAL, CATALOGO_REAL,
                                   {}, _decisoes_tudo_excluido(), tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_invalido"


# ------------------------------------------------------------- C: [Content_Types].xml ausente

def test_C_content_types_ausente_reporta_docx_package_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _zip_com_partes(tmp / "sem_content_types.docx", {
            "_rels/.rels": _RELS_RAIZ, "word/document.xml": _DOCUMENT_XML,
        })
        r = gerar_peca(docx, SCHEMA_REAL, {}, tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_invalido"


# ------------------------------------------------------------- D: word/document.xml ausente

def test_D_document_xml_ausente_reporta_docx_package_estrutura_incompleta():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _zip_com_partes(tmp / "sem_document.docx", {
            "[Content_Types].xml": _CONTENT_TYPES, "_rels/.rels": _RELS_RAIZ,
        })
        r = gerar_peca(docx, SCHEMA_REAL, {}, tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_estrutura_incompleta"


def test_D_document_xml_ausente_gerar_peca_com_blocos_reporta_docx_package_estrutura_incompleta():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _zip_com_partes(tmp / "sem_document.docx", {
            "[Content_Types].xml": _CONTENT_TYPES, "_rels/.rels": _RELS_RAIZ,
        })
        r = gerar_peca_com_blocos(docx, SCHEMA_REAL, CATALOGO_REAL,
                                   {}, _decisoes_tudo_excluido(), tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_estrutura_incompleta"


# ------------------------------------------------------------- E: Zip Slip

def test_E_zip_slip_reporta_docx_package_invalido_sem_vazar_arquivo():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _zip_com_partes(
            tmp / "malicioso.docx",
            {"[Content_Types].xml": _CONTENT_TYPES, "_rels/.rels": _RELS_RAIZ,
             "word/document.xml": _DOCUMENT_XML},
            entradas_brutas=[("../fora_do_pacote.txt", b"malicioso", 0)],
        )
        alvo_externo = tmp.parent / "fora_do_pacote.txt"
        if alvo_externo.exists():
            alvo_externo.unlink()
        r = gerar_peca(docx, SCHEMA_REAL, {}, tmp / "saida.docx")
        assert r["status"] == "FALHOU"
        assert r["etapa"] == "docx_package_invalido"
        assert not alvo_externo.exists()


# ------------------------------------------------------------- F: erro conhecido -> PIPELINE_ABORTED (E2E via gerar_contestacao)

def test_F_template_corrompido_via_gerar_contestacao_produz_pipeline_aborted_estruturado():
    """Ponta a ponta, pela ORQUESTRAÇÃO real (gerar_contestacao.gerar) —
    a etapa contexto_institucional é a PRIMEIRA do pipeline (INV-MODELO-
    INSTITUCIONAL-FONTE-PRIMARIA), então um template corrompido aborta ali
    mesmo, antes de qualquer leitura de arquivo do caso — o diretório do
    caso pode até estar vazio."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lixo = tmp / "nao_e_docx.docx"
        lixo.write_bytes(b"isto nao e um zip valido")
        caso_vazio = tmp / "caso"
        caso_vazio.mkdir()

        r = gerar_contestacao.gerar(caso_vazio, tmp / "saida.docx", template=lixo,
                                     schema=SCHEMA_REAL, catalogo_blocos=CATALOGO_REAL)
        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "contexto_institucional"
        assert "docx_package_invalido" in r["reason"] or "unpack_falhou" in r["reason"]


# ------------------------------------------------------------- G: bug inesperado não é mascarado

def test_G_bug_inesperado_em_extrair_pacote_docx_nao_e_convertido_em_falhou():
    """Se algo dentro de gerar_peca_com_blocos chamar extrair_pacote_docx e
    receber uma exceção que NÃO é PacoteDocxAbortada (aqui, simulada como
    TypeError — um bug de programação hipotético, não uma condição
    ambiental/documental conhecida), essa exceção deve se propagar
    intacta — nunca ser silenciosamente absorvida como {"status":
    "FALHOU", ...} nem como sucesso."""
    original = docx_block_engine.extrair_pacote_docx

    def _bug_simulado(*_a, **_k):
        raise TypeError("bug de programação simulado — não é PacoteDocxAbortada")

    docx_block_engine.extrair_pacote_docx = _bug_simulado
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            template_qualquer = tmp / "qualquer.docx"
            template_qualquer.write_bytes(b"conteudo irrelevante, extrair_pacote_docx esta mockada")

            propagou = False
            try:
                gerar_peca_com_blocos(template_qualquer, SCHEMA_REAL, CATALOGO_REAL,
                                       {}, _decisoes_tudo_excluido(), tmp / "saida.docx")
            except TypeError as e:
                propagou = True
                assert "bug de programação simulado" in str(e)
            assert propagou, ("TypeError inesperado foi engolido/convertido em vez de se "
                               "propagar — violação do princípio 'erro_interno não mascara bug'")
    finally:
        docx_block_engine.extrair_pacote_docx = original


def test_G_pacote_docx_abortada_continua_sendo_o_unico_tipo_convertido_em_falhou():
    """Contraste direto com o teste anterior: PacoteDocxAbortada (erro
    CONHECIDO) É convertida em {"status": "FALHOU", ...} — confirma que a
    distinção não é "toda exceção vira FALHOU" nem "nenhuma vira", é
    exatamente PacoteDocxAbortada, nada mais amplo."""
    original = docx_block_engine.extrair_pacote_docx

    def _erro_conhecido_simulado(*_a, **_k):
        raise PacoteDocxAbortada("docx_package_invalido", "erro conhecido simulado")

    docx_block_engine.extrair_pacote_docx = _erro_conhecido_simulado
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            template_qualquer = tmp / "qualquer.docx"
            template_qualquer.write_bytes(b"conteudo irrelevante")
            r = gerar_peca_com_blocos(template_qualquer, SCHEMA_REAL, CATALOGO_REAL,
                                       {}, _decisoes_tudo_excluido(), tmp / "saida.docx")
            assert r["status"] == "FALHOU"
            assert r["etapa"] == "docx_package_invalido"
            assert "erro conhecido simulado" in r["erros"][0]
    finally:
        docx_block_engine.extrair_pacote_docx = original


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
