#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_docx_block_engine.py — regressão do motor de composição de blocos
(Etapa 5, INV-COMPOSICAO-BLOCOS — SPEC-0001 §5).

Mesmo padrão de tests/test_template_engine.py: sem framework de teste,
asserts + `if __name__ == "__main__"`.

Dois níveis:
  1. Testes de unidade sobre XML sintético (lxml) — sempre rodam, cobrem
     validar_sdts_contra_catalogo/compor_blocos/compor_xml estruturalmente,
     incluindo os casos negativos I-O (SDT malformado, tag desconhecida/
     ausente, cardinalidade errada, estado inválido).
  2. LOCAL_ONLY — `test_pipeline_completo_com_blocos_contra_template_real`:
     ponta a ponta contra o modelo-oficial.docx real (já migrado com os
     SDTs de bloco/container/inline — Etapa 5). SKIP explícito se o
     arquivo não existir (ADR-0006 — asset institucional fora do git).

Uso:
  python tests/test_docx_block_engine.py
"""
import sys
from pathlib import Path

import lxml.etree as LET

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    compor_blocos,
    compor_xml,
    validar_sdts_contra_catalogo,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except ComposicaoAbortada as e:
        return e


def _parse(xml):
    return LET.fromstring(xml.encode("utf-8"))


CATALOGO_SIMPLES = {"blocks": [
    {"id": "FOLHA_A", "tag": "BLOCO:A", "tipo": "CONDICIONAL_PADRAO", "parent": None,
     "children": [], "decision_mode": "estrategista", "placeholders": [],
     "dependencies": [], "cardinality": "ONE"},
    {"id": "FOLHA_B", "tag": "BLOCO:B", "tipo": "CONDICIONAL_PADRAO", "parent": None,
     "children": [], "decision_mode": "estrategista", "placeholders": [],
     "dependencies": [], "cardinality": "ONE"},
]}

XML_DOIS_BLOCOS = (
    '<w:document xmlns:w="%s"><w:body>'
    '<w:p><w:r><w:t>antes</w:t></w:r></w:p>'
    '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
    '<w:sdtContent><w:p><w:r><w:t>conteudo A</w:t></w:r></w:p></w:sdtContent></w:sdt>'
    '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:B"/><w:id w:val="2"/></w:sdtPr>'
    '<w:sdtContent><w:p><w:r><w:t>conteudo B</w:t></w:r></w:p></w:sdtContent></w:sdt>'
    '<w:p><w:r><w:t>depois</w:t></w:r></w:p>'
    '</w:body></w:document>'
) % W


# --------------------------------------------------------------- composição básica
def test_incluir_faz_unwrap_preservando_conteudo():
    root = _parse(XML_DOIS_BLOCOS)
    validar_sdts_contra_catalogo(root, CATALOGO_SIMPLES)
    r = compor_blocos(root, CATALOGO_SIMPLES, {"FOLHA_A": "INCLUIR", "FOLHA_B": "EXCLUIR"})
    assert r == {"incluidos": ["FOLHA_A"], "excluidos": ["FOLHA_B"]}
    saida = LET.tostring(root).decode("utf-8")
    assert "conteudo A" in saida
    assert "conteudo B" not in saida
    assert saida.count("<w:sdt>") == 0  # ambos processados: um vira unwrap, outro some


def test_excluir_remove_sdt_inteiro():
    root = _parse(XML_DOIS_BLOCOS)
    compor_blocos(root, CATALOGO_SIMPLES, {"FOLHA_A": "EXCLUIR", "FOLHA_B": "EXCLUIR"})
    saida = LET.tostring(root).decode("utf-8")
    assert "conteudo A" not in saida and "conteudo B" not in saida
    assert "antes" in saida and "depois" in saida  # vizinhos preservados


def test_nao_assume_indice_paragrafo_igual_indice_filho_corpo():
    # bookmarkEnd solto intercalado entre parágrafos (achado real do
    # template institucional) — a composição não pode se confundir com
    # isso: o bloco B ainda deve ser localizado e processado corretamente.
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:bookmarkEnd w:id="0"/>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:B"/><w:id w:val="2"/></w:sdtPr>'
        '<w:sdtContent><w:p><w:r><w:t>conteudo B</w:t></w:r></w:p></w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % W
    catalogo = {"blocks": [CATALOGO_SIMPLES["blocks"][1]]}
    root = _parse(xml)
    r = compor_blocos(root, catalogo, {"FOLHA_B": "INCLUIR"})
    assert r["incluidos"] == ["FOLHA_B"]
    saida = LET.tostring(root).decode("utf-8")
    assert "conteudo B" in saida and "<w:bookmarkEnd" in saida


def test_mc_choice_fallback_preservados_juntos():
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    xml = (
        '<w:document xmlns:w="%s" xmlns:mc="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent>'
        '<mc:AlternateContent>'
        '<mc:Choice Requires="wps"><w:p><w:r><w:t>choice</w:t></w:r></w:p></mc:Choice>'
        '<mc:Fallback><w:p><w:r><w:t>fallback</w:t></w:r></w:p></mc:Fallback>'
        '</mc:AlternateContent>'
        '</w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % (W, mc)
    catalogo = {"blocks": [CATALOGO_SIMPLES["blocks"][0]]}
    root = _parse(xml)
    compor_blocos(root, catalogo, {"FOLHA_A": "INCLUIR"})
    saida = LET.tostring(root).decode("utf-8")
    assert saida.count("AlternateContent") == 2  # abre+fecha, um par intacto
    assert "choice" in saida and "fallback" in saida


# --------------------------------------------------------------- negativos I-O
def test_I_sdt_duplicado_cardinalidade_one():
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:p/></w:sdtContent></w:sdt>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="2"/></w:sdtPr>'
        '<w:sdtContent><w:p/></w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % W
    catalogo = {"blocks": [CATALOGO_SIMPLES["blocks"][0]]}
    e = _abortou(validar_sdts_contra_catalogo, _parse(xml), catalogo)
    assert e and e.stage == "cardinalidade_invalida"


def test_J_sdt_sem_sdtcontent():
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr></w:sdt>'
        '</w:body></w:document>'
    ) % W
    e = _abortou(validar_sdts_contra_catalogo, _parse(xml), CATALOGO_SIMPLES)
    assert e and e.stage == "sdt_sem_content"


def test_K_sdt_sem_tag():
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:p/></w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % W
    e = _abortou(validar_sdts_contra_catalogo, _parse(xml), CATALOGO_SIMPLES)
    assert e and e.stage == "sdt_sem_tag"


def test_L_tag_desconhecida_no_documento():
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:FANTASMA"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:p/></w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % W
    e = _abortou(validar_sdts_contra_catalogo, _parse(xml), CATALOGO_SIMPLES)
    assert e and e.stage == "tag_desconhecida"


def test_M_tag_do_catalogo_ausente_no_documento():
    xml = (
        '<w:document xmlns:w="%s"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:p/></w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    ) % W  # falta BLOCO:B do catálogo
    e = _abortou(validar_sdts_contra_catalogo, _parse(xml), CATALOGO_SIMPLES)
    assert e and e.stage == "tag_ausente"


def test_N_estado_indeterminado_na_composicao():
    root = _parse(XML_DOIS_BLOCOS)
    e = _abortou(compor_blocos, root, CATALOGO_SIMPLES,
                  {"FOLHA_A": "INDETERMINADO", "FOLHA_B": "EXCLUIR"})
    assert e and e.stage == "estado_invalido"


def test_O_estado_ausente_na_composicao():
    root = _parse(XML_DOIS_BLOCOS)
    e = _abortou(compor_blocos, root, CATALOGO_SIMPLES, {"FOLHA_A": "INCLUIR"})  # falta FOLHA_B
    assert e and e.stage == "estado_invalido"


def test_adulteracao_fora_de_bloco_placeholder_nao_e_deste_modulo():
    # A composição de blocos não cobre adulteração fora de SDT/placeholder
    # — isso é responsabilidade do Template Lock (docx_template_engine.py),
    # já testado em test_template_engine.py::test_template_lock_detecta_*.
    # Este teste só documenta a fronteira de responsabilidade (evita
    # duplicar a mesma cobertura em dois módulos).
    assert True


# --------------------------------------------------------------- compor_xml (wrapper)
def test_compor_xml_via_wrapper_string_to_string():
    novo_xml, resultado = compor_xml(XML_DOIS_BLOCOS, CATALOGO_SIMPLES,
                                      {"FOLHA_A": "INCLUIR", "FOLHA_B": "EXCLUIR"})
    assert "conteudo A" in novo_xml and "conteudo B" not in novo_xml
    assert resultado == {"incluidos": ["FOLHA_A"], "excluidos": ["FOLHA_B"]}


# --------------------------------------------------------------- LOCAL_ONLY (template real)
def test_pipeline_completo_com_blocos_contra_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ADR-0006).")
        return

    from docx_block_engine import carregar_catalogo, gerar_peca_com_blocos, validar_catalogo

    catalogo = carregar_catalogo(CATALOGO_REAL)
    validar_catalogo(catalogo)

    dados = {
        "JUIZO": "1ª Vara Cível da Comarca de Salvador/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "ligação direta (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada — dado fictício de teste)",
        "ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA": "Argumento fictício de teste.",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
    }
    decisoes_tudo_incluido = {b["id"]: {"decisao": "INCLUIR"}
                               for b in catalogo["blocks"] if b["decision_mode"] == "estrategista"}

    with __import__("tempfile").TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao-blocos-teste.docx"
        r = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes_tudo_incluido, saida)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"
        assert saida.exists() and saida.stat().st_size > 0
        assert "PRELIMINARES" in r["blocos_incluidos"]
        assert "PRELIMINAR_CDC_INAPLICAVEL" in r["blocos_incluidos"]
        assert r["containers_derivados"]["PRELIMINARES"] == "INCLUIR"

        # cenário "nenhuma preliminar / evolução excluída / reconvenção excluída"
        decisoes_minimo = dict(decisoes_tudo_incluido)
        for bid in ("PRELIMINAR_CDC_INAPLICAVEL", "PRELIMINAR_REVOGACAO_GRATUIDADE",
                    "EVOLUCAO_CONSUMO", "RECONVENCAO"):
            decisoes_minimo[bid] = {"decisao": "EXCLUIR"}
        dados_sem_evolucao = dict(dados)
        saida2 = Path(tmp) / "contestacao-blocos-minimo.docx"
        r2 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados_sem_evolucao, decisoes_minimo, saida2)
        assert r2["status"] == "OK", r2
        assert r2["containers_derivados"]["PRELIMINARES"] == "EXCLUIR"
        assert "RECONVENCAO" in r2["blocos_excluidos"]
        assert "EVOLUCAO_CONSUMO" in r2["blocos_excluidos"]

        import zipfile as _zf
        with _zf.ZipFile(saida2) as z:
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        assert "{{ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA}}" not in gerado_xml
        assert "NÃO INFORMADO" not in gerado_xml.upper() or "ARGUMENTACAO_EVOLUCAO" not in gerado_xml

        # INDETERMINADO em qualquer folha aborta e não produz DOCX
        decisoes_indeterminada = dict(decisoes_tudo_incluido)
        decisoes_indeterminada["DESCABIMENTO_DANO_MORAL"] = {"decisao": "INDETERMINADO"}
        saida3 = Path(tmp) / "nao_deve_existir.docx"
        r3 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_indeterminada, saida3)
        assert r3["status"] == "FALHOU"
        assert not saida3.exists()

    print("Pipeline completo com blocos contra o template real: OK "
          "(tudo incluído, mínimo, INDETERMINADO aborta sem DOCX).")


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
