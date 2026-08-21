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


def test_sdt_aninhado_dentro_de_textbox_e_processado():
    # Etapa 5.2 — achado real: INLINE_COM_RECONVENCAO vive dentro de
    # wps:txbx/w:txbxContent (caixa de texto do título), não como filho
    # direto de w:body nem de outro w:sdtContent. A composição precisa
    # alcançar esse SDT mesmo assim (regressão do bug em que ele ficava
    # intocado, qualquer que fosse a decisão).
    wps = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
    xml = (
        '<w:document xmlns:w="%s" xmlns:wps="%s"><w:body>'
        '<w:p><w:r><w:drawing><wps:wsp><wps:txbx><w:txbxContent>'
        '<w:p><w:r><w:t>CONTESTAÇÃO</w:t></w:r>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:r><w:t> conteudo A</w:t></w:r></w:sdtContent></w:sdt>'
        '</w:p></w:txbxContent></wps:txbx></wps:wsp></w:drawing></w:r></w:p>'
        '</w:body></w:document>'
    ) % (W, wps)
    catalogo = {"blocks": [CATALOGO_SIMPLES["blocks"][0]]}
    root = _parse(xml)
    r = compor_blocos(root, catalogo, {"FOLHA_A": "INCLUIR"})
    assert r["incluidos"] == ["FOLHA_A"]
    saida = LET.tostring(root).decode("utf-8")
    assert "conteudo A" in saida
    assert "<w:sdt>" not in saida  # unwrap efetivo — não ficou intocado


def test_sdt_aninhado_dentro_de_textbox_excluir_remove():
    wps = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
    xml = (
        '<w:document xmlns:w="%s" xmlns:wps="%s"><w:body>'
        '<w:p><w:r><w:drawing><wps:wsp><wps:txbx><w:txbxContent>'
        '<w:p><w:r><w:t>CONTESTAÇÃO</w:t></w:r>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:A"/><w:id w:val="1"/></w:sdtPr>'
        '<w:sdtContent><w:r><w:t> COM RECONVENÇÃO</w:t></w:r></w:sdtContent></w:sdt>'
        '</w:p></w:txbxContent></wps:txbx></wps:wsp></w:drawing></w:r></w:p>'
        '</w:body></w:document>'
    ) % (W, wps)
    catalogo = {"blocks": [CATALOGO_SIMPLES["blocks"][0]]}
    root = _parse(xml)
    r = compor_blocos(root, catalogo, {"FOLHA_A": "EXCLUIR"})
    assert r["excluidos"] == ["FOLHA_A"]
    saida = LET.tostring(root).decode("utf-8")
    assert "COM RECONVENÇÃO" not in saida
    assert "<w:sdt>" not in saida


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
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
    }
    decisoes_tudo_incluido = {b["id"]: {"decisao": "INCLUIR"}
                               for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    # INV-GRATUIDADE-LINKED (state_linked, nunca aceita decisão manual —
    # PRELIMINAR_REVOGACAO_GRATUIDADE não entra em decisoes_tudo_incluido)
    # vs. INV-CORTE-GATE-HUMANO (decision_mode='humano' com requires_fact:
    # LICITUDE_CORTE_SUSPENSAO ENTRA em decisoes_tudo_incluido com INCLUIR,
    # mas só é aceita se o fato CORTE_EFETIVO estiver confirmado).
    fatos_processuais_tudo = {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True}
    # dict sem decisão para LICITUDE_CORTE_SUSPENSAO — usado nos cenários
    # que testam a resolução automática "sem pergunta" (fato ausente/false).
    decisoes_sem_corte = {k: v for k, v in decisoes_tudo_incluido.items()
                           if k != "LICITUDE_CORTE_SUSPENSAO"}

    with __import__("tempfile").TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao-blocos-teste.docx"
        r = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes_tudo_incluido, saida,
                                   fatos_processuais=fatos_processuais_tudo)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"
        assert saida.exists() and saida.stat().st_size > 0
        assert "PRELIMINARES" in r["blocos_incluidos"]
        assert "PRELIMINAR_CDC_INAPLICAVEL" in r["blocos_incluidos"]
        # GRATUIDADE_CONCEDIDA=true (fatos_processuais_tudo) inclui o bloco
        # automaticamente (state_linked) — sem decisão manual do estrategista.
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" in r["blocos_incluidos"]
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" not in decisoes_tudo_incluido
        assert r["containers_derivados"]["PRELIMINARES"] == "INCLUIR"
        # CORTE_EFETIVO=true (fatos_processuais_tudo) + decisão humana
        # INCLUIR presente em decisoes_tudo_incluido (INV-CORTE-GATE-HUMANO)
        # -> bloco incluído. Diferente da gratuidade: aqui a decisão manual
        # É exigida e aceita, só fica condicionada ao gate fático.
        assert "LICITUDE_CORTE_SUSPENSAO" in r["blocos_incluidos"]

        # cenário "nenhuma preliminar / evolução excluída / reconvenção
        # excluída / sem corte efetivo". PRELIMINAR_REVOGACAO_GRATUIDADE NÃO
        # entra neste loop — 'state_linked' (INV-GRATUIDADE-LINKED), nunca
        # aceita decisão manual; sem fatos_processuais nesta chamada,
        # resolve automaticamente para EXCLUIR (fato ausente).
        # LICITUDE_CORTE_SUSPENSAO recebe EXCLUIR explícito (decision_mode
        # 'humano' aceita EXCLUIR mesmo sem o gate satisfeito).
        decisoes_minimo = dict(decisoes_tudo_incluido)
        for bid in ("PRELIMINAR_CDC_INAPLICAVEL", "EVOLUCAO_CONSUMO", "RECONVENCAO", "LICITUDE_CORTE_SUSPENSAO"):
            decisoes_minimo[bid] = {"decisao": "EXCLUIR"}
        dados_sem_evolucao = dict(dados)
        saida2 = Path(tmp) / "contestacao-blocos-minimo.docx"
        r2 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados_sem_evolucao, decisoes_minimo, saida2)
        assert r2["status"] == "OK", r2
        assert r2["containers_derivados"]["PRELIMINARES"] == "EXCLUIR"
        assert "RECONVENCAO" in r2["blocos_excluidos"]
        assert "EVOLUCAO_CONSUMO" in r2["blocos_excluidos"]
        # sem fatos_processuais nesta chamada -> ambos os fatos vinculados
        # ausentes -> EXCLUIR automático (state_linked), sem decisão manual.
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" in r2["blocos_excluidos"]
        assert "LICITUDE_CORTE_SUSPENSAO" in r2["blocos_excluidos"]

        import zipfile as _zf
        with _zf.ZipFile(saida2) as z:
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        assert "{{" not in gerado_xml, "nenhum placeholder residual no DOCX final"
        # EVOLUCAO_CONSUMO=EXCLUIR: seu texto fixo institucional (o bloco não
        # tem mais placeholder próprio — removido em correção pontual) some
        # do documento junto com o bloco inteiro.
        assert "levantamento de carga instalada" not in gerado_xml
        # Teste J (INV-CORTE-GATE-HUMANO): LICITUDE_CORTE_SUSPENSAO=EXCLUIR
        # (decisão humana explícita) -> zero conteúdo residual do bloco
        # (título, texto-base institucional).
        assert "LICITUDE DA COBRANÇA E CORTE" not in gerado_xml
        assert "TEMA 699" not in gerado_xml

        with _zf.ZipFile(saida) as z:  # o primeiro DOCX (tudo incluído)
            gerado_xml_incluido = z.read("word/document.xml").decode("utf-8")
        # Teste K: bloco incluído (CORTE_EFETIVO=true + decisão humana
        # INCLUIR) -> título/texto-base presentes (duas ocorrências no XML —
        # mc:Choice + mc:Fallback do próprio template, mesmo padrão
        # estrutural já usado para outros títulos deste modelo, ex. "COM
        # RECONVENÇÃO"; não é duplicação introduzida por este pipeline).
        assert "LICITUDE DA COBRANÇA E CORTE" in gerado_xml_incluido
        assert gerado_xml_incluido.count("LICITUDE DA COBRANÇA E CORTE") == 2

        # INDETERMINADO em qualquer folha aborta e não produz DOCX
        # (fatos_processuais informado para que o gate de CORTE não seja o
        # motivo do abort — o alvo real do teste é DESCABIMENTO_DANO_MORAL).
        decisoes_indeterminada = dict(decisoes_tudo_incluido)
        decisoes_indeterminada["DESCABIMENTO_DANO_MORAL"] = {"decisao": "INDETERMINADO"}
        saida3 = Path(tmp) / "nao_deve_existir.docx"
        r3 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_indeterminada, saida3,
                                    fatos_processuais=fatos_processuais_tudo)
        assert r3["status"] == "FALHOU"
        assert not saida3.exists()

        # Etapa 5.2 / correção pontual — INV-GRATUIDADE-LINKED contra o
        # template real: decisão manual do estrategista para bloco
        # state_linked é sempre rejeitada, mesmo quando o fato coincide
        # com a decisão fornecida — a decisão simplesmente não existe
        # para este bloco (diferente de LICITUDE_CORTE_SUSPENSAO, que
        # voltou a aceitar decisão manual sob INV-CORTE-GATE-HUMANO —
        # ver abaixo).
        decisoes_com_decisao_indevida = dict(decisoes_tudo_incluido)
        decisoes_com_decisao_indevida["PRELIMINAR_REVOGACAO_GRATUIDADE"] = {"decisao": "INCLUIR"}
        saida4 = Path(tmp) / "nao_deve_existir_gratuidade.docx"
        r4 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_com_decisao_indevida, saida4,
                                    fatos_processuais={"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True})
        assert r4["status"] == "FALHOU" and r4["etapa"] == "decisao_invalida"
        assert not saida4.exists()

        # INV-CORTE-GATE-HUMANO (Etapa 5.5): CORTE_EFETIVO=true SEM decisão
        # humana registrada NÃO inclui automaticamente (diferente do vínculo
        # state_linked da gratuidade) — o pipeline para e pede a decisão ao
        # advogado (decisao_ausente), nunca gera o DOCX final calado.
        decisoes_corte_sem_decisao = dict(decisoes_sem_corte)
        saida4c = Path(tmp) / "nao_deve_existir_corte_sem_decisao_humana.docx"
        r4c = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                     dados, decisoes_corte_sem_decisao, saida4c,
                                     fatos_processuais={"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True})
        assert r4c["status"] == "FALHOU" and r4c["etapa"] == "decisao_ausente"
        assert not saida4c.exists()

        # GRATUIDADE_CONCEDIDA/CORTE_EFETIVO indeterminados -> aborta para
        # interação com o advogado, nunca decisão silenciosa.
        saida4b = Path(tmp) / "nao_deve_existir_gratuidade_indeterminada.docx"
        r4b = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                     dados, decisoes_tudo_incluido, saida4b,
                                     fatos_processuais={"GRATUIDADE_CONCEDIDA": "INDETERMINADO", "CORTE_EFETIVO": True})
        assert r4b["status"] == "FALHOU" and r4b["etapa"] == "decisao_indeterminada"
        assert not saida4b.exists()

        saida5 = Path(tmp) / "nao_deve_existir_corte_indeterminado.docx"
        r5 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_tudo_incluido, saida5,
                                    fatos_processuais={"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": "INDETERMINADO"})
        assert r5["status"] == "FALHOU" and r5["etapa"] == "decisao_indeterminada"
        assert not saida5.exists()

        # CORTE_EFETIVO=false, SEM decisão humana registrada -> EXCLUIR
        # automático, sem pergunta (INV-CORTE-GATE-HUMANO §18: nada a
        # decidir sobre tese sem suporte fático — não desperdiça interação
        # humana), igual à gratuidade não concedida (state_linked).
        saida6 = Path(tmp) / "contestacao-blocos-sem-corte.docx"
        r6 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_sem_corte, saida6,
                                    fatos_processuais={"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": False})
        assert r6["status"] == "OK", r6
        assert "LICITUDE_CORTE_SUSPENSAO" in r6["blocos_excluidos"]

        # fato ausente (fatos_processuais=None) tem o mesmo efeito que
        # falso — fail closed por omissão, nunca por presunção de
        # verdadeiro, mas continua sendo EXCLUIR automático sem pergunta,
        # não FALHOU.
        saida7 = Path(tmp) / "contestacao-blocos-sem-estado.docx"
        r7 = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_sem_corte, saida7)
        assert r7["status"] == "OK", r7
        assert "LICITUDE_CORTE_SUSPENSAO" in r7["blocos_excluidos"]
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" in r7["blocos_excluidos"]

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
