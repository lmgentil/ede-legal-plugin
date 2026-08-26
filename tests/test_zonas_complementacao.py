#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_zonas_complementacao.py — regressão da Zona de Complementação piloto
(Etapa 5.8-B, INV-ZONA-COMPLEMENTACAO — SPEC-0001 §58, ADR-0010).

Mesmo padrão dos demais testes do projeto: asserts + `if __name__ ==
"__main__"`, sem framework.

Cobre a matriz A-AF do pedido da Etapa 5.8-B:
  - catálogo × template (A-E): presença, ausência (MODELO_INSTITUCIONAL_
    DESATUALIZADO), zona não catalogada, bloco_pai divergente, token
    duplicado;
  - ativação (F-J): bloco-pai EXCLUIR, fato ausente, fato INDETERMINADO,
    necessidade falsa (conteúdo vazio), necessidade verdadeira;
  - composição (K-P): remoção integral do SDT, substituição do token,
    ausência de token/parágrafo residual, FF0000, <w:p> reais;
  - semântica (Q-V): parágrafos, 380, total, prefixo numerado, travessão,
    sentinela;
  - contexto (W-Z): texto anterior/posterior, bloco_pai, não editável;
  - Template Lock/E2E (AA-AF): lock OK nos dois estados, blocos e
    numeração intactos, 13 placeholders preservados, E2E contra o
    modelo-oficial.docx REAL.

Uso:
  python tests/test_zonas_complementacao.py
"""
import copy
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import lxml.etree as LET

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "rag"))
sys.path.insert(0, str(BASE / "skills" / "calendario-forense-tjba-2026" / "scripts"))

import gerar_contestacao  # noqa: E402
from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    compor_xml,
    compor_zonas_xml,
    gerar_peca_com_blocos,
    resolver_estados_zonas,
    token_da_zona,
    validar_catalogo,
)
from validate_paragrafos import validar_densidade_zonas  # noqa: E402
from validate_placeholder_semantics import (validar_semantica_zonas,  # noqa: E402
                                             validar_continuidade_zonas)
from test_e2e_contestacao import _resolver_juizo_stub  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ZONA_ID = "ZONA_METODOLOGIA_APURACAO"
ZONA_TAG = "ZONA:METODOLOGIA_APURACAO"
TOKEN = "{{" + ZONA_ID + "}}"

FONTE_MEM = "memorial_calculo_sintetico.txt"
FONTE_TOI = "toi_sintetico.txt"

# Conteúdo de zona válido (recalibrado na Etapa 5.8-C, corrigido na
# 5.8-C.1): demonstra a APLICAÇÃO CONCRETA do critério aos dados do
# processo, com cada número rastreável ao documento de origem. Não repete
# o texto institucional, não cria tese, não usa travessão, não cria
# numeração de tópico.
#
# A atribuição de fonte foi corrigida na 5.8-C.1: o CRITÉRIO (média dos
# três maiores consumos dos 12 ciclos) consta da memória de cálculo, não
# do TOI; o que o TOI documenta é o LEVANTAMENTO do histórico no ato da
# inspeção. A redação anterior dizia que o levantamento "consta do Termo
# de Ocorrência e Inspeção", vinculando o critério ao documento errado.
#
# O VALOR TOTAL é o R$ 4.328,17 do memorial — PRESERVADO, nunca
# recalculado (gate de fechamento da 5.8-C.1). Auditoria confirmou que o
# memorial NÃO apresenta "2.412 kWh x R$ 1,7947/kWh = valor final" como
# fórmula integral: registra consumo, tarifa e valor total como três
# fatos em linhas separadas, sem sinal de igual conectando-os. O produto
# simples desses dois números (R$ 4.328,82) diverge do valor documental
# em R$ 0,65 — não é contradição interna da fixture, porque o documento
# nunca afirmou aquela conta; é o memorial simplesmente não detalhando
# toda a apuração real (proporcionalização, arredondamento etc.), o que é
# normal num documento sintético resumido. Por isso a redação NÃO
# apresenta o valor como resultado de multiplicação ("do que resultou") —
# apresenta os três dados como fatos documentais distintos e paralelos,
# tal como o próprio memorial faz, e `valor_total_apurado` não declara
# `operacao`: nada na peça afirma que a multiplicação produz o total.
#
# Lógica de redação fixada no ajuste da 5.8-C.1: DOCUMENTAÇÃO
# ADMINISTRATIVA -> CRITÉRIO REGULAMENTAR -> METODOLOGIA EFETIVAMENTE
# APLICADA -> RESULTADO DOCUMENTADO. Cada número é atribuído ao documento
# que o registra ("a memória de cálculo registra/consigna/aplicou"),
# nunca apresentado como recálculo próprio.
#
# Abertura corrigida na Etapa 5.8-D.1 (INV-CONTINUIDADE-ZONA): a versão
# anterior abria com "No caso concreto, a apuração observou...", que
# colide com a abertura do parágrafo institucional real imediatamente
# anterior a este bloco no modelo oficial ("No caso concreto, a
# concessionária observou..."). Corrigido removendo só o prefixo
# colidente — mesmos fatos, mesma proveniência, mesmos números, mesma
# finalidade.
CONTEUDO_VALIDO = (
    "A apuração observou o critério do art. 595, III, da Resolução "
    "ANEEL nº 1.000/2021, tal como registrado na memória de cálculo do procedimento "
    "administrativo: média dos três maiores consumos verificados nos 12 ciclos de "
    "medição regular anteriores, cujo levantamento se deu no ato da inspeção.\n"
    "A memória de cálculo registra consumo médio apurado de 612 kWh por ciclo, contra "
    "210 kWh efetivamente faturados no período, diferença de 402 kWh por ciclo, e "
    "consigna 2.412 kWh não registrados nos 6 ciclos do período de apuração.\n"
    "Sobre esse montante, a memória de cálculo aplicou a tarifa vigente à época, de "
    "R$ 1,7947/kWh, e consignou o valor recuperado de R$ 4.328,17, exatamente a quantia "
    "impugnada nesta ação. A cobrança tem por base, portanto, a apuração regulamentar "
    "constituída no procedimento administrativo."
)

# Proveniência exigida desde a Etapa 5.8-C, estruturada por dado desde a
# 5.8-C.1: tipo/valor/unidade/fonte/natureza, e `operacao` sempre que o
# dado mantém relação matemática EXPLICITAMENTE presente no documento.
# `diferenca_por_ciclo` (612-210=402) e `consumo_nao_registrado_total`
# (402x6=2.412, escrito literalmente no memorial: "402 kWh/ciclo x 6
# ciclos = 2.412 kWh") são operações que o próprio documento evidencia e
# que fecham sem exceção. `valor_total_apurado` NÃO declara `operacao`:
# o memorial não apresenta a multiplicação por tarifa como fórmula do
# total, então a peça não afirma essa derivação — o valor é preservado
# como fato documental simples (gate de fechamento da 5.8-C.1, §2).
FATOS_ZONA = [
    {"tipo": "criterio_apuracao",
     "valor": "art. 595, III, da Resolução ANEEL nº 1.000/2021",
     "fonte": FONTE_MEM, "natureza": "documental"},
    {"tipo": "ciclos_historico_levantado", "valor": "12", "unidade": "ciclo",
     "fonte": FONTE_TOI, "natureza": "documental"},
    {"tipo": "consumo_medio_apurado", "valor": "612", "unidade": "kWh/ciclo",
     "fonte": FONTE_MEM, "natureza": "documental"},
    {"tipo": "consumo_faturado", "valor": "210", "unidade": "kWh/ciclo",
     "fonte": FONTE_MEM, "natureza": "documental"},
    {"tipo": "diferenca_por_ciclo", "valor": "402", "unidade": "kWh/ciclo",
     "fonte": FONTE_MEM, "natureza": "documental",
     "operacao": {"op": "subtracao",
                  "operandos": ["consumo_medio_apurado", "consumo_faturado"]}},
    {"tipo": "ciclos_periodo_apuracao", "valor": "6", "unidade": "ciclo",
     "fonte": FONTE_MEM, "natureza": "documental"},
    {"tipo": "consumo_nao_registrado_total", "valor": "2.412", "unidade": "kWh",
     "fonte": FONTE_MEM, "natureza": "documental",
     "operacao": {"op": "multiplicacao",
                  "operandos": ["diferenca_por_ciclo", "ciclos_periodo_apuracao"]}},
    {"tipo": "tarifa_aplicavel", "valor": "1,7947", "unidade": "R$/kWh",
     "fonte": FONTE_MEM, "natureza": "documental"},
    {"tipo": "valor_total_apurado", "valor": "4.328,17", "unidade": "R$",
     "fonte": FONTE_MEM, "natureza": "documental"},
]
ZONA_RICA = {"conteudo": CONTEUDO_VALIDO, "fatos": FATOS_ZONA}


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except ComposicaoAbortada as e:
        return e


def _pular_sem_template():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ver ADR-0009).")
        return True
    return False


def _texto(elemento):
    return "".join(t.text or "" for t in elemento.iter(f"{{{W}}}t"))


# --------------------------------------------------------------- XML sintético
def _xml_sintetico(tag_zona=ZONA_TAG, token=TOKEN, bloco="BLOCO:CALCULOS", extra_no_paragrafo=""):
    """Corpo mínimo com um bloco condicional contendo a zona — mesmo
    formato do template real (SDT de zona ANINHADO no SDT do bloco-pai)."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>'
        '<w:p><w:r><w:t>texto institucional antes do bloco</w:t></w:r></w:p>'
        f'<w:sdt><w:sdtPr><w:tag w:val="{bloco}"/></w:sdtPr><w:sdtContent>'
        '<w:p><w:r><w:t>fundamento normativo fixo do topico</w:t></w:r></w:p>'
        f'<w:sdt><w:sdtPr><w:tag w:val="{tag_zona}"/></w:sdtPr><w:sdtContent>'
        f'<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:t>{token}{extra_no_paragrafo}</w:t></w:r></w:p>'
        '</w:sdtContent></w:sdt>'
        '<w:p><w:r><w:t>Trata-se, portanto, de mecanismo de recomposicao</w:t></w:r></w:p>'
        '</w:sdtContent></w:sdt>'
        '<w:p><w:r><w:t>texto institucional depois do bloco</w:t></w:r></w:p>'
        '</w:body></w:document>'
    )


def _catalogo_sintetico(**over_zona):
    zona = {
        "id": ZONA_ID, "tag": ZONA_TAG, "bloco_pai": "CALCULOS",
        "finalidade": "dados concretos da apuração",
        "tipo_conteudo": "dado_documental",
        "requires_facts": ["METODOLOGIA_APURACAO_DOCUMENTADA"],
        "max_paragrafos": 3, "max_caracteres_paragrafo": 380,
        "max_caracteres_total": 1000, "exige_proveniencia": True,
        "comportamento_vazia": "remover_sdt",
    }
    zona.update(over_zona)
    return {
        "blocks": [{
            "id": "CALCULOS", "tag": "BLOCO:CALCULOS", "tipo": "CONDICIONAL_PADRAO",
            "parent": None, "children": [], "decision_mode": "estrategista",
            "placeholders": [], "dependencies": [], "cardinality": "ONE",
        }],
        "zones": [zona],
    }


# =============================================================== A-E: catálogo × template
def test_A_zona_no_catalogo_com_sdt_no_template_passa():
    catalogo = _catalogo_sintetico()
    validar_catalogo(catalogo)
    xml, _ = compor_xml(_xml_sintetico(), catalogo, {"CALCULOS": "INCLUIR"})
    assert TOKEN in xml, "zona não composta ainda: token deve sobreviver a compor_blocos"


def test_B_zona_sem_sdt_no_template_e_modelo_desatualizado():
    """§15: erro operacional que orienta o advogado, nunca um `tag_ausente`
    cru — e nunca busca/edição automática do modelo."""
    catalogo = _catalogo_sintetico()
    xml_sem_zona = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:CALCULOS"/></w:sdtPr><w:sdtContent>'
        '<w:p><w:r><w:t>so texto fixo</w:t></w:r></w:p>'
        '</w:sdtContent></w:sdt></w:body></w:document>'
    )
    e = _abortou(compor_xml, xml_sem_zona, catalogo, {"CALCULOS": "INCLUIR"})
    assert e and e.stage == "modelo_institucional_desatualizado", e
    assert "MODELO_INSTITUCIONAL_DESATUALIZADO" in e.motivo
    assert "atualizado" in e.motivo.lower()


def test_C_sdt_de_zona_sem_entrada_no_catalogo_aborta():
    catalogo = _catalogo_sintetico()
    catalogo["zones"] = []
    e = _abortou(compor_xml, _xml_sintetico(), catalogo, {"CALCULOS": "INCLUIR"})
    assert e and e.stage == "zona_nao_catalogada", e


def test_D_bloco_pai_divergente_do_ancestral_real_aborta():
    catalogo = _catalogo_sintetico()
    catalogo["blocks"].append({
        "id": "OUTRO", "tag": "BLOCO:OUTRO", "tipo": "CONDICIONAL_PADRAO",
        "parent": None, "children": [], "decision_mode": "estrategista",
        "placeholders": [], "dependencies": [], "cardinality": "ONE",
    })
    catalogo["zones"][0]["bloco_pai"] = "OUTRO"
    xml = _xml_sintetico().replace(
        '<w:p><w:r><w:t>texto institucional depois do bloco</w:t></w:r></w:p>',
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:OUTRO"/></w:sdtPr><w:sdtContent>'
        '<w:p><w:r><w:t>outro bloco</w:t></w:r></w:p></w:sdtContent></w:sdt>')
    e = _abortou(compor_xml, xml, catalogo, {"CALCULOS": "INCLUIR", "OUTRO": "INCLUIR"})
    assert e and e.stage == "zona_bloco_pai_divergente", e


def test_E_token_duplicado_no_documento_aborta():
    catalogo = _catalogo_sintetico()
    xml = _xml_sintetico().replace(
        '<w:p><w:r><w:t>texto institucional depois do bloco</w:t></w:r></w:p>',
        f'<w:p><w:r><w:t>{TOKEN}</w:t></w:r></w:p>')
    e = _abortou(compor_xml, xml, catalogo, {"CALCULOS": "INCLUIR"})
    assert e and e.stage == "zona_token_duplicado", e


def test_E2_token_ausente_dentro_do_sdt_aborta():
    catalogo = _catalogo_sintetico()
    xml = _xml_sintetico(token="sem token aqui")
    e = _abortou(compor_xml, xml, catalogo, {"CALCULOS": "INCLUIR"})
    assert e and e.stage == "zona_token_ausente", e


def test_E3_token_acompanhado_de_texto_fixo_aborta():
    """O parágrafo hospedeiro precisa ser só do token: é o w:pPr dele que os
    parágrafos gerados clonam (INV-PARAGRAFO-HERDA-TEMPLATE), e texto fixo
    na mesma <w:p> seria arrastado pela expansão multilinha."""
    catalogo = _catalogo_sintetico()
    xml = _xml_sintetico(extra_no_paragrafo=" e mais texto institucional")
    e = _abortou(compor_xml, xml, catalogo, {"CALCULOS": "INCLUIR"})
    assert e and e.stage == "zona_token_nao_isolado", e


def test_E4_catalogo_de_zona_malformado_aborta():
    for over, trecho in [
        ({"requires_facts": []}, "requires_facts"),
        ({"tipo_conteudo": "complemento_factual"}, "tipo_conteudo"),
        ({"comportamento_vazia": "manter"}, "comportamento_vazia"),
        ({"bloco_pai": "INEXISTENTE"}, "bloco_pai"),
        ({"tag": "BLOCO:METODOLOGIA"}, "tag de zona deve começar"),
        ({"max_paragrafos": 0}, "max_paragrafos"),
    ]:
        e = _abortou(validar_catalogo, _catalogo_sintetico(**over))
        assert e and e.stage == "catalogo_invalido", (over, e)
        assert trecho in e.motivo, (over, e.motivo)


def test_E5_zona_nao_pode_declarar_campo_de_bloco():
    """§6/§11: zona não é bloco — não tem decision_mode nem entra em
    derived_rule. Declarar qualquer um deles é erro de catálogo, não um
    campo silenciosamente ignorado."""
    for campo in ("decision_mode", "children", "derived_rule", "linked_fact", "cardinality"):
        e = _abortou(validar_catalogo, _catalogo_sintetico(**{campo: "qualquer"}))
        assert e and e.stage == "catalogo_invalido", campo
        assert "zona não é" in e.motivo, e.motivo


# =============================================================== F-J: ativação
def _estados(conteudo=None, fatos=None, estado_bloco="INCLUIR", catalogo=None):
    catalogo = catalogo or _catalogo_sintetico()
    return resolver_estados_zonas(catalogo, {"CALCULOS": estado_bloco}, conteudo, fatos)


FATO_OK = {"METODOLOGIA_APURACAO_DOCUMENTADA": True}


def test_F_bloco_pai_excluir_zona_excluir():
    assert _estados(estado_bloco="EXCLUIR", fatos=FATO_OK) == {ZONA_ID: "EXCLUIR"}


def test_F2_conteudo_com_bloco_pai_excluido_aborta():
    """§6: incoerência de pipeline, nunca descarte silencioso."""
    e = _abortou(_estados, {ZONA_ID: CONTEUDO_VALIDO}, FATO_OK, "EXCLUIR")
    assert e and e.stage == "zona_incoerente", e
    assert "EXCLUÍDO" in e.motivo


def test_G_fato_ausente_zona_excluir_sem_perguntar():
    assert _estados(fatos={}) == {ZONA_ID: "EXCLUIR"}
    assert _estados(fatos={"METODOLOGIA_APURACAO_DOCUMENTADA": False}) == {ZONA_ID: "EXCLUIR"}


def test_G2_conteudo_sem_suporte_fatico_aborta():
    e = _abortou(_estados, {ZONA_ID: CONTEUDO_VALIDO}, {})
    assert e and e.stage == "zona_incoerente", e
    assert "suporte fático" in e.motivo


def test_H_fato_indeterminado_aborta():
    e = _abortou(_estados, None, {"METODOLOGIA_APURACAO_DOCUMENTADA": "INDETERMINADO"})
    assert e and e.stage == "zona_indeterminada", e
    # ambiguidade vence a ausência: aborta mesmo com conteúdo presente
    e2 = _abortou(_estados, {ZONA_ID: CONTEUDO_VALIDO},
                  {"METODOLOGIA_APURACAO_DOCUMENTADA": "INDETERMINADO"})
    assert e2 and e2.stage == "zona_indeterminada", e2


def test_I_fatos_presentes_sem_conteudo_zona_excluir():
    """Teste de necessidade reprovado pelo Redator => conteúdo vazio =>
    zona EXCLUIR. Este é o caminho NORMAL da peça."""
    assert _estados(fatos=FATO_OK) == {ZONA_ID: "EXCLUIR"}
    assert _estados({ZONA_ID: ""}, FATO_OK) == {ZONA_ID: "EXCLUIR"}
    assert _estados({ZONA_ID: "   \n  "}, FATO_OK) == {ZONA_ID: "EXCLUIR"}


def test_J_fatos_presentes_com_conteudo_zona_incluir():
    assert _estados({ZONA_ID: CONTEUDO_VALIDO}, FATO_OK) == {ZONA_ID: "INCLUIR"}


def test_J2_zona_nunca_provoca_inclusao_do_bloco_pai():
    """§6/§11: a zona pertence ao bloco; nunca o inclui. resolver_estados_
    zonas recebe os estados dos blocos já resolvidos e nunca os modifica."""
    estados_blocos = {"CALCULOS": "EXCLUIR"}
    resolver_estados_zonas(_catalogo_sintetico(), estados_blocos, None, FATO_OK)
    assert estados_blocos == {"CALCULOS": "EXCLUIR"}


# =============================================================== K-P: composição
def _compor(estado_zona, estado_bloco="INCLUIR"):
    catalogo = _catalogo_sintetico()
    composto, _ = compor_xml(_xml_sintetico(), catalogo, {"CALCULOS": estado_bloco})
    return compor_zonas_xml(composto, catalogo, {ZONA_ID: estado_zona})


def test_K_zona_vazia_remove_sdt_inteiro():
    xml, relatorio = _compor("EXCLUIR")
    assert relatorio["excluidas"] == [ZONA_ID]
    assert TOKEN not in xml
    assert ZONA_TAG not in xml
    # texto institucional ao redor permanece intocado, e contíguo
    assert "fundamento normativo fixo do topico" in xml
    assert "Trata-se, portanto, de mecanismo de recomposicao" in xml


def test_K2_zona_vazia_nao_deixa_paragrafo_residual():
    xml, _ = _compor("EXCLUIR")
    root = LET.fromstring(xml.encode("utf-8"))
    textos = [_texto(p).strip() for p in root.iter(f"{{{W}}}p")]
    assert "" not in textos, f"parágrafo vazio residual: {textos}"
    assert len(textos) == 4, textos


def test_L_zona_incluida_mantem_o_token_para_substituicao():
    xml, relatorio = _compor("INCLUIR")
    assert relatorio["incluidas"] == [ZONA_ID]
    assert TOKEN in xml
    assert ZONA_TAG not in xml, "o w:sdt deve ser desembrulhado, não mantido"


def test_M_N_O_P_substituicao_produz_paragrafos_reais_em_ff0000():
    from docx_template_engine import substituir_placeholders
    xml, _ = _compor("INCLUIR")
    final, substituidos = substituir_placeholders(xml, {ZONA_ID: CONTEUDO_VALIDO})
    assert substituidos == {ZONA_ID}
    assert TOKEN not in final, "M: nenhum token residual"
    assert 'w:val="FF0000"' in final, "O: conteúdo de zona em FF0000"

    root = LET.fromstring(final.encode("utf-8"))
    marcas = ("art. 595, III", "memória de cálculo", "tarifa vigente")
    paras = [p for p in root.iter(f"{{{W}}}p") if any(m in _texto(p) for m in marcas)]
    assert len(paras) == 3, f"P: três linhas lógicas => três <w:p> reais, obtidos {len(paras)}"
    # INV-PARAGRAFO-HERDA-TEMPLATE: o segundo parágrafo herda o w:pPr do
    # parágrafo hospedeiro (clonagem estrutural, não estilo próprio)
    for p in paras:
        jc = p.find("w:pPr/w:jc", NS)
        assert jc is not None and jc.get(f"{{{W}}}val") == "both", LET.tostring(p)
    textos = [_texto(p).strip() for p in root.iter(f"{{{W}}}p")]
    assert "" not in textos, f"N: parágrafo vazio residual: {textos}"


# =============================================================== Q-V: semântica
def _zonas_catalogo():
    return _catalogo_sintetico()["zones"]


def test_Q_excesso_de_paragrafos_rejeita():
    ok, erros = validar_densidade_zonas({ZONA_ID: "um.\ndois.\ntrês.\nquatro."}, _zonas_catalogo())
    assert not ok and any("4 parágrafos" in e for e in erros), erros


def test_R_paragrafo_acima_de_380_rejeita():
    ok, erros = validar_densidade_zonas({ZONA_ID: "a" * 381}, _zonas_catalogo())
    assert not ok and any("381 caracteres" in e for e in erros), erros


def test_S_total_acima_do_teto_agregado_rejeita():
    ok, erros = validar_densidade_zonas(
        {ZONA_ID: "a" * 350 + "\n" + "b" * 350 + "\n" + "c" * 350}, _zonas_catalogo())
    assert not ok and any("no total" in e for e in erros), erros


def test_S2_conteudo_valido_passa():
    ok, erros = validar_densidade_zonas({ZONA_ID: CONTEUDO_VALIDO}, _zonas_catalogo())
    assert ok, erros
    ok2, erros2 = validar_semantica_zonas({ZONA_ID: CONTEUDO_VALIDO})
    assert ok2, erros2


def test_S3_conteudo_para_zona_inexistente_rejeita():
    ok, erros = validar_densidade_zonas({"ZONA_QUE_NAO_EXISTE": "x"}, _zonas_catalogo())
    assert not ok and any("não existe no catálogo" in e for e in erros), erros


def test_T_prefixo_de_titulo_numerado_rejeita():
    """§17: o conteúdo da zona entra DEPOIS de validar_numeracao_final, que
    portanto nunca o enxerga — este backstop lexical é a única defesa."""
    for texto in ("3.5 - Da metodologia aplicada", "3.4.1 Metodologia",
                  "4. Do critério adotado", "3.5) critério"):
        ok, erros = validar_semantica_zonas({ZONA_ID: texto})
        assert not ok, texto
        assert any("título numerado" in e for e in erros), (texto, erros)


def test_T2_referencia_legitima_a_artigo_nao_e_confundida_com_titulo():
    """Falso positivo a evitar: a zona existe justamente para citar o
    inciso/artigo aplicado. Só o INÍCIO do parágrafo é restrito."""
    ok, erros = validar_semantica_zonas(
        {ZONA_ID: "A apuração seguiu o art. 595, III, da REN 1.000/2021."})
    assert ok, erros


def test_U_travessao_rejeita():
    ok, erros = validar_semantica_zonas({ZONA_ID: "Critério aplicado — inciso III."})
    assert not ok and any("travessão" in e for e in erros), erros


def test_V_sentinela_textual_rejeita():
    for sentinela in ("NÃO APLICÁVEL", "SEM DADOS", "VAZIO", "NÃO INFORMADO"):
        ok, erros = validar_semantica_zonas({ZONA_ID: sentinela})
        assert not ok, sentinela
        assert any("sentinela" in e for e in erros), (sentinela, erros)


# =============================================================== W-Z: contexto institucional
def test_W_X_Y_Z_contexto_da_zona_no_template_real():
    if _pular_sem_template():
        return
    from docx_context_engine import extrair_contexto_do_template
    ctx = extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    assert ZONA_ID in ctx
    ocorrencia = ctx[ZONA_ID][0]
    # W: texto institucional imediatamente anterior — parágrafo de aderência
    # ao art. 595
    assert "art. 595" in ocorrencia["antes"]
    assert "presunção de arbitrariedade" in ocorrencia["antes"]
    # X: texto institucional imediatamente posterior
    assert ocorrencia["depois"].startswith("Trata-se, portanto, de mecanismo de recomposição")
    # Y: bloco-pai real
    assert ocorrencia["bloco"] == "CALCULOS_RECUPERACAO_CONSUMO"
    assert ocorrencia["bloco_pai"] == "CALCULOS_RECUPERACAO_CONSUMO"
    # Z: contexto institucional é NÃO EDITÁVEL, e a zona se identifica como
    # zona (nunca como placeholder) e como normalmente vazia
    assert ocorrencia["contexto_editavel"] is False
    assert ocorrencia["tipo"] == "zona"
    assert ocorrencia["normalmente_vazia"] is True
    assert ocorrencia["requires_facts"] == ["METODOLOGIA_APURACAO_DOCUMENTADA"]
    assert ocorrencia["limites"]["max_caracteres_total"] == 1000


# =============================================================== catálogo real
def test_catalogo_real_tem_exatamente_a_zona_piloto():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    validar_catalogo(catalogo)
    zonas = catalogo["zones"]
    assert [z["id"] for z in zonas] == [ZONA_ID], "Etapa 5.8-B autoriza UMA zona, só"
    z = zonas[0]
    assert z["tag"] == ZONA_TAG
    assert z["bloco_pai"] == "CALCULOS_RECUPERACAO_CONSUMO"
    assert z["tipo_conteudo"] == "dado_documental"
    assert z["requires_facts"] == ["METODOLOGIA_APURACAO_DOCUMENTADA"]
    # Etapa 5.8-C: teto agregado ampliado (400 -> 1000) porque 400 tornava
    # mecanicamente impossível demonstrar a aplicação concreta do critério;
    # 380 por parágrafo permanece (INV-PARAGRAFO-380 não é relaxada).
    assert (z["max_paragrafos"], z["max_caracteres_paragrafo"], z["max_caracteres_total"]) == (3, 380, 1000)
    assert z["exige_proveniencia"] is True
    assert z["comportamento_vazia"] == "remover_sdt"
    assert token_da_zona(z) == TOKEN


def test_AE_treze_placeholders_oficiais_preservados():
    schema = json.loads(SCHEMA_REAL.read_text(encoding="utf-8"))
    catalogo = carregar_catalogo(CATALOGO_REAL)
    assert len(schema["editable_placeholders"]) == 13
    assert len(schema["placeholder_contracts"]) == 13
    ids_zona = {z["id"] for z in catalogo["zones"]}
    assert not (ids_zona & set(schema["editable_placeholders"])), \
        "zona NUNCA entra em editable_placeholders — placeholder e zona são contratos distintos"


# =============================================================== AA-AF: E2E contra o template real
def _caso_com_zona(tmp, conteudo=None, estado_fato=True):
    """Cópia da fixture happy_path acrescida de estado_processual/zonas."""
    caso = Path(tmp) / "caso"
    shutil.copytree(FIXTURES / "happy_path", caso)
    estado = {}
    caminho_estado = caso / "estado_processual.json"
    if caminho_estado.exists():
        estado = json.loads(caminho_estado.read_text(encoding="utf-8"))
    if estado_fato is not None:
        estado["METODOLOGIA_APURACAO_DOCUMENTADA"] = estado_fato
    caminho_estado.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    if conteudo is not None:
        (caso / "zonas.json").write_text(
            json.dumps({ZONA_ID: conteudo}, ensure_ascii=False), encoding="utf-8")
    return caso


def _zona(texto, fatos=None):
    """Forma estruturada de `zonas.json` (obrigatória desde a 5.8-C)."""
    return {"conteudo": texto, "fatos": FATOS_ZONA if fatos is None else fatos}


def _docx_xml(caminho):
    with zipfile.ZipFile(caminho) as z:
        return z.read("word/document.xml").decode("utf-8")


def test_AA_AC_AD_AF_e2e_zona_incluida_contra_template_real():
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, ZONA_RICA)
        saida = Path(tmp) / "com-zona.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "OK", r
        assert r["zonas_incluidas"] == [ZONA_ID], r
        assert r["zonas_excluidas"] == [], r
        # AA: Template Lock aprovado com zona INCLUIR
        assert r["template_lock"] == "OK"
        # AC/AD: blocos e numeração seguem íntegros no mesmo relatório
        assert "CALCULOS_RECUPERACAO_CONSUMO" in r["blocos_incluidos"]
        stage_engine = next(s for s in r["stages"] if s["name"] == "template_engine")
        assert stage_engine["numeracao"], "renumeração continua reportada"
        assert stage_engine["zonas"] == {ZONA_ID: "INCLUIR"}

        xml = _docx_xml(saida)
        assert TOKEN not in xml, "AF: nenhum token residual"
        assert "art. 595, III" in xml
        assert 'w:val="FF0000"' in xml
        # continuidade do texto institucional ao redor da zona
        assert "presunção de arbitrariedade" in xml
        assert "mecanismo de recomposição econômica" in xml


def test_AB_e2e_zona_vazia_contra_template_real():
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, conteudo=None)
        saida = Path(tmp) / "sem-zona.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "OK", r
        assert r["zonas_incluidas"] == [], r
        assert r["zonas_excluidas"] == [ZONA_ID], r
        assert r["template_lock"] == "OK"  # AB

        xml = _docx_xml(saida)
        assert TOKEN not in xml and ZONA_TAG not in xml
        # o tópico 3.4 continua íntegro e contínuo
        assert "presunção de arbitrariedade" in xml
        assert "mecanismo de recomposição econômica" in xml


def test_AB2_zona_vazia_produz_documento_identico_a_zona_ausente():
    """Prova estrutural de que a zona vazia não deixa vestígio: o DOCX
    gerado sem `zonas.json` e o gerado com `zonas.json` de conteúdo vazio
    têm o mesmo word/document.xml."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_a = _caso_com_zona(tmp, conteudo=None)
        saida_a = Path(tmp) / "a.docx"
        assert gerar_contestacao.gerar(caso_a, saida_a,
                                        resolver_juizo_fn=_resolver_juizo_stub)["status"] == "OK"
        shutil.rmtree(caso_a)
        caso_b = _caso_com_zona(tmp, conteudo="   ")
        saida_b = Path(tmp) / "b.docx"
        assert gerar_contestacao.gerar(caso_b, saida_b,
                                        resolver_juizo_fn=_resolver_juizo_stub)["status"] == "OK"
        assert _docx_xml(saida_a) == _docx_xml(saida_b)


def test_AA2_template_lock_reprova_alteracao_fora_da_zona():
    """Com a zona ativa, o Lock continua reprovando qualquer alteração de
    texto institucional — a cadeia de recomputação não foi afrouxada."""
    if _pular_sem_template():
        return
    from docx_template_engine import _importar_toolkit, verificar_template_lock
    from docx_block_engine import validar_e_resolver_decisoes
    from docx_numeracao_engine import renumerar_titulos
    from docx_template_engine import substituir_placeholders

    caso = FIXTURES / "happy_path"
    catalogo = carregar_catalogo(CATALOGO_REAL)
    decisoes = json.loads((caso / "decisoes_blocos.json").read_text(encoding="utf-8"))
    fatos_proc = {"METODOLOGIA_APURACAO_DOCUMENTADA": True}
    estados = validar_e_resolver_decisoes(catalogo, decisoes, fatos_proc)
    estados_zonas = resolver_estados_zonas(catalogo, estados, {ZONA_ID: CONTEUDO_VALIDO}, fatos_proc)
    dados = json.loads((caso / "placeholders.json").read_text(encoding="utf-8"))
    # JUIZO/FOTOS/TEMPESTIVIDADE são injetados pelo pipeline (DataJud,
    # marcador de pós-edição, prosa de tempestividade), não vêm da fixture.
    dados["JUIZO"] = "AO JUÍZO DA 1ª VARA CÍVEL DA COMARCA DE SALVADOR"
    dados["FOTOS_DA_IRREGULARIADE"] = gerar_contestacao.MARCADOR_FOTOS
    dados["TEMPESTIVIDADE_CASO"] = "A presente defesa é tempestiva."
    dados[ZONA_ID] = CONTEUDO_VALIDO

    def transformar(template_xml):
        composto, _ = compor_xml(template_xml, catalogo, estados)
        com_zonas, _ = compor_zonas_xml(composto, catalogo, estados_zonas)
        renumerado, _ = renumerar_titulos(com_zonas)
        return substituir_placeholders(renumerado, dados)

    unpack_mod, _ = _importar_toolkit()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copia = tmp / "t.docx"
        shutil.copy2(TEMPLATE_REAL, copia)
        template_dir = tmp / "template"
        unpack_mod.unpack(str(copia), str(template_dir))
        template_xml = (template_dir / "word" / "document.xml").read_text(encoding="utf-8")

        gerado_dir = tmp / "gerado"
        shutil.copytree(template_dir, gerado_dir)
        esperado, _ = transformar(template_xml)
        (gerado_dir / "word" / "document.xml").write_text(esperado, encoding="utf-8")
        lock_ok = verificar_template_lock(template_dir, gerado_dir, dados, transformar_xml=transformar)
        assert lock_ok["ok"], lock_ok["divergencias"]

        adulterado = esperado.replace("COELBA", "OUTRA EMPRESA QUALQUER", 1)
        assert adulterado != esperado
        (gerado_dir / "word" / "document.xml").write_text(adulterado, encoding="utf-8")
        lock_ruim = verificar_template_lock(template_dir, gerado_dir, dados, transformar_xml=transformar)
        assert not lock_ruim["ok"], "Template Lock deveria reprovar alteração de texto institucional"


def test_AB3_modelo_desatualizado_no_pipeline_real():
    """Modelo do usuário sem o SDT da zona: o pipeline aborta com o stage
    operacional próprio, não com `tag_ausente`."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        catalogo = json.loads(CATALOGO_REAL.read_text(encoding="utf-8"))
        # Simula um catálogo mais novo que o modelo do usuário: mantém a
        # zona real (senão o SDT presente no template seria acusado, antes,
        # de não catalogado) e acrescenta uma segunda que este modelo não
        # tem — exatamente o cenário do advogado com modelo desatualizado.
        nova = copy.deepcopy(catalogo["zones"][0])
        nova["id"] = "ZONA_INEXISTENTE_NO_MODELO"
        nova["tag"] = "ZONA:INEXISTENTE_NO_MODELO"
        catalogo["zones"].append(nova)
        catalogo_tmp = tmp / "blocos.json"
        catalogo_tmp.write_text(json.dumps(catalogo, ensure_ascii=False), encoding="utf-8")

        caso = _caso_com_zona(tmp, conteudo=None)
        saida = tmp / "nao_deveria_existir.docx"
        r = gerar_contestacao.gerar(caso, saida, catalogo_blocos=catalogo_tmp,
                                     resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "modelo_institucional_desatualizado", r
        assert "MODELO_INSTITUCIONAL_DESATUALIZADO" in r["reason"]
        assert not saida.exists(), "nenhum DOCX parcial pode ser gravado"


def test_pipeline_rejeita_conteudo_de_zona_invalido():
    """O estágio `zonas` barra conteúdo fora do contrato antes de qualquer
    composição — nunca gera sabendo que o limite foi violado."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        # dígitos do prefixo deliberadamente ancorados, para isolar a
        # guarda de título numerado (se não estivessem, a checagem de
        # proveniência abortaria antes e o teste não provaria nada)
        caso = _caso_com_zona(tmp, _zona(
            "596. A apuração seguiu o art. 595, III, com 6 ciclos.",
            [{"tipo": "periodo_normativo", "valor": "art. 596, §1º",
              "fonte": FONTE_MEM, "natureza": "documental"},
             {"tipo": "criterio_apuracao", "valor": "art. 595, III",
              "fonte": FONTE_MEM, "natureza": "documental"},
             {"tipo": "ciclos_periodo_apuracao", "valor": "6", "unidade": "ciclo",
              "fonte": FONTE_MEM, "natureza": "documental"}]))
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "zonas", r
        assert "título numerado" in r["reason"]
        assert not saida.exists()


def test_pipeline_aborta_com_fato_indeterminado():
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, conteudo=None, estado_fato="INDETERMINADO")
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "zonas", r
        assert "zona_indeterminada" in r["reason"]
        assert not saida.exists()


def test_pipeline_nao_pergunta_nada_sobre_zona():
    """§21: nenhuma pergunta humana para zona — diferente de RECONVENCAO
    (INV-RECONVENCAO-AUTORIZACAO-EXPRESSA) e de LICITUDE_CORTE_SUSPENSAO
    (INV-CORTE-GATE-HUMANO), que abortam pedindo decisão do advogado.
    Prova code-level: nem o estágio nem a resolução de estado da zona têm
    qualquer ramo de interação ou sinal de 'decisão ausente'."""
    import inspect
    for fn in (gerar_contestacao._etapa_zonas, resolver_estados_zonas):
        fonte = inspect.getsource(fn)
        assert "AskUserQuestion" not in fonte, fn
        assert "input(" not in fonte, fn
        assert "decisao_ausente" not in fonte, fn
    # e o catálogo não permite que a zona ganhe decisão de espécie alguma
    zona = carregar_catalogo(CATALOGO_REAL)["zones"][0]
    assert "decision_mode" not in zona


# =============================================================== Etapa 5.8-C: qualidade material e proveniência
FATOS_DO_CASO = json.loads((FIXTURES / "happy_path" / "fatos.json").read_text(encoding="utf-8"))
FONTES_DO_CASO = {f["source_document"] for f in FATOS_DO_CASO}


def _prov(texto, fatos=None, fontes=None):
    """`fontes` continua no nome do parâmetro por compatibilidade com os
    testes da 5.8-C, mas desde a 5.8-C.1 o validador recebe a base
    documental INTEIRA (`fatos.json`) — precisa dos fatos, não só dos
    nomes dos documentos, para conferir se o dado está na fonte certa."""
    from validate_fatos import validar_proveniencia_zona
    return validar_proveniencia_zona(texto, FATOS_ZONA if fatos is None else fatos,
                                      ZONA_ID, FATOS_DO_CASO if fontes else None)


def _fatos_zona(**mudancas):
    """Cópia profunda de FATOS_ZONA com um dado alterado, por `tipo`."""
    copia = [json.loads(json.dumps(f)) for f in FATOS_ZONA]
    for tipo, campos in mudancas.items():
        alvo = next(f for f in copia if f["tipo"] == tipo)
        alvo.update(campos)
    return copia


def test_5C_A_dado_documental_disponivel_e_pertinente_e_utilizado():
    """A: a fixture expõe os dados do memorial como fatos próprios, e o
    conteúdo da zona os aproveita concretamente — não só o rótulo do
    inciso."""
    fatos_fixture = json.loads((FIXTURES / "happy_path" / "fatos.json").read_text(encoding="utf-8"))
    do_memorial = [f["fact"] for f in fatos_fixture if f["source_document"] == FONTE_MEM]
    assert len(do_memorial) >= 6, "memorial de cálculo sub-extraído em fatos.json"
    for dado in ("612", "210", "402", "2.412", "1,7947", "4.328,17", "595"):
        assert dado in CONTEUDO_VALIDO, f"dado documental disponível não aproveitado: {dado}"


def test_5C_B_dado_inexistente_nao_e_inventado():
    """B: número que não consta de nenhum fato declarado é barrado."""
    inventado = CONTEUDO_VALIDO + "\nO débito venceu em 31/03/2026."
    erros = _prov(inventado, fontes=FONTES_DO_CASO)
    assert any("sem lastro documental" in e for e in erros), erros
    assert any("31" in e for e in erros), erros


def test_5C_C_numeros_identicos_a_fonte():
    """C: cada número do texto existe, literalmente, na fixture."""
    memorial = (FIXTURES / "happy_path" / "documentos" / "memorial_calculo_sintetico.txt").read_text(encoding="utf-8")
    for numero in ("612", "210", "402", "2.412", "1,7947", "4.328,17", "595", "596"):
        assert numero in memorial, f"{numero} não consta do memorial — seria invenção"


def test_5C_D_datas_nao_sao_inventadas():
    """D: a zona não afirma data alguma, porque o memorial da fixture não
    traz datas de ciclo. Omitir é o comportamento correto — nunca
    preencher lacuna por inferência."""
    import re as _re
    datas = _re.findall(r"\b\d{2}/\d{2}/\d{4}\b", CONTEUDO_VALIDO)
    assert not datas, f"data afirmada sem lastro no memorial: {datas}"
    # e se alguém inserir uma, o gate barra
    assert any("sem lastro documental" in e
               for e in _prov(CONTEUDO_VALIDO + "\nInspeção em 01/02/2030.", fontes=FONTES_DO_CASO))


def test_5C_E_dispositivo_normativo_nao_e_alterado():
    """E: art. 595, III e REN 1.000/2021 são os do memorial; trocar o
    inciso por outro número não declarado é barrado."""
    memorial = (FIXTURES / "happy_path" / "documentos" / "memorial_calculo_sintetico.txt").read_text(encoding="utf-8")
    assert "art. 595, III" in memorial and "1.000/2021" in memorial
    assert "art. 595, III" in CONTEUDO_VALIDO
    trocado = CONTEUDO_VALIDO.replace("1.000/2021", "1.001/2022")
    assert any("sem lastro documental" in e for e in _prov(trocado, fontes=FONTES_DO_CASO))


def test_5C_F_conteudo_nao_extrapola_finalidade_da_zona():
    """F: a zona é dado_documental. Conteúdo sem nenhum dado concreto é
    rejeitado — é paráfrase do texto institucional, não complementação."""
    generico = ("O procedimento foi regular e a concessionária observou a legislação "
                "aplicável, não havendo qualquer arbitrariedade na cobrança.")
    erros = _prov(generico, fatos=[], fontes=FONTES_DO_CASO)
    assert any("sem nenhum dado concreto" in e for e in erros), erros


def test_5C_F2_frase_vazia_sem_concretizacao_e_rejeitada():
    """Regressão direta do stub pobre da Etapa 5.8-B: 'Os valores constam
    do memorial de faturamento anexo.' é conclusão genérica sem dado."""
    erros = _prov("A apuração seguiu o art. 595, III.\n"
                  "Os valores constam do memorial de faturamento anexo.",
                  fatos=[{"tipo": "criterio_apuracao", "valor": "art. 595, III",
                          "fonte": FONTE_MEM, "natureza": "documental"}],
                  fontes=FONTES_DO_CASO)
    assert any("conclusão genérica" in e for e in erros), erros


def test_5C_G_H_texto_institucional_adjacente_preservado():
    """G/H: os parágrafos institucionais anterior e posterior chegam ao
    DOCX exatamente como estão no template, com e sem zona."""
    if _pular_sem_template():
        return
    from docx_template_engine import _importar_toolkit
    unpack_mod, _ = _importar_toolkit()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copia = tmp / "t.docx"
        shutil.copy2(TEMPLATE_REAL, copia)
        unpack_mod.unpack(str(copia), str(tmp / "u"))
        template_xml = (tmp / "u" / "word" / "document.xml").read_text(encoding="utf-8")
        raiz = LET.fromstring(template_xml.encode("utf-8"))
        paras = [_texto(p) for p in raiz.iter(f"{{{W}}}p")]
        anterior = next(p for p in paras if "presunção de arbitrariedade" in p)
        posterior = next(p for p in paras if p.startswith("Trata-se, portanto, de mecanismo"))

        caso = _caso_com_zona(tmp, ZONA_RICA)
        saida = tmp / "com.docx"
        assert gerar_contestacao.gerar(caso, saida,
                                        resolver_juizo_fn=_resolver_juizo_stub)["status"] == "OK"
        xml_com = _docx_xml(saida)
        shutil.rmtree(caso)
        caso2 = _caso_com_zona(tmp, conteudo=None)
        saida2 = tmp / "sem.docx"
        assert gerar_contestacao.gerar(caso2, saida2,
                                        resolver_juizo_fn=_resolver_juizo_stub)["status"] == "OK"
        xml_sem = _docx_xml(saida2)

    for xml in (xml_com, xml_sem):
        raiz = LET.fromstring(xml.encode("utf-8"))
        textos = [_texto(p) for p in raiz.iter(f"{{{W}}}p")]
        assert anterior in textos, "G: parágrafo institucional anterior alterado"
        assert posterior in textos, "H: parágrafo institucional posterior alterado"


def test_5C_I_excluir_continua_removendo_integralmente():
    """I: a mudança de contrato não afetou o caminho vazio."""
    xml, relatorio = _compor("EXCLUIR")
    assert relatorio["excluidas"] == [ZONA_ID]
    assert TOKEN not in xml and ZONA_TAG not in xml
    raiz = LET.fromstring(xml.encode("utf-8"))
    assert "" not in [_texto(p).strip() for p in raiz.iter(f"{{{W}}}p")]


def test_5C_J_informacao_insuficiente_e_fail_closed():
    """J: sem suporte fático a zona fica vazia (sem perguntar); com
    conteúdo mas sem suporte, aborta — nunca fabrica densidade."""
    assert _estados(fatos={}) == {ZONA_ID: "EXCLUIR"}
    e = _abortou(_estados, {ZONA_ID: CONTEUDO_VALIDO}, {})
    assert e and e.stage == "zona_incoerente", e


def test_5C_K_humanizer_nao_introduz_fatos_novos():
    """K: qualquer número acrescentado depois da redação (o que uma
    humanização indevida faria) é barrado pela mesma checagem de
    ancoragem, que roda sobre o texto FINAL entregue ao pipeline."""
    assert "A apuração observou o critério" in CONTEUDO_VALIDO, \
        "substring da reescrita abaixo desatualizada — CONTEUDO_VALIDO mudou de redação"
    humanizado_ok = CONTEUDO_VALIDO.replace("A apuração observou o critério",
                                             "O critério foi observado pela apuração")
    assert humanizado_ok != CONTEUDO_VALIDO, "reescrita não teve efeito — teste não exercitou nada"
    assert not _prov(humanizado_ok, fontes=FONTES_DO_CASO), "reescrita sem novo fato deve passar"
    humanizado_ruim = humanizado_ok.replace("R$ 4.328,17", "R$ 5.000,00")
    assert any("sem lastro documental" in e for e in _prov(humanizado_ruim, fontes=FONTES_DO_CASO))


def test_5C_L_proveniencia_verificavel():
    """L: fonte sem `dado`, `dado` sem fonte, e fonte fora da base
    documental do caso são todas rejeitadas."""
    assert any("sem 'fonte'" in e for e in
               _prov(CONTEUDO_VALIDO, [{"tipo": "x", "valor": "612", "natureza": "documental"}],
                     FONTES_DO_CASO))
    assert any("sem 'valor'" in e for e in
               _prov(CONTEUDO_VALIDO, [{"tipo": "x", "fonte": FONTE_MEM,
                                        "natureza": "documental"}], FONTES_DO_CASO))
    inventada = [dict(f, fonte="documento_que_nao_existe.pdf") for f in FATOS_ZONA]
    assert any("não consta da base documental" in e for e in
               _prov(CONTEUDO_VALIDO, inventada, FONTES_DO_CASO))
    # e o caminho feliz continua limpo
    assert not _prov(CONTEUDO_VALIDO, fontes=FONTES_DO_CASO)


def test_5C_texto_simples_sem_proveniencia_e_rejeitado():
    """Contrato novo: string não vazia em zonas.json não é mais aceita."""
    from validate_fatos import normalizar_conteudo_zona
    _, _, erros = normalizar_conteudo_zona("texto sem proveniência")
    assert any("texto simples" in e for e in erros), erros
    # string vazia continua sendo o jeito legítimo de dizer "zona vazia"
    assert normalizar_conteudo_zona("") == ("", [], [])
    assert normalizar_conteudo_zona(None) == ("", [], [])


def test_5C_conteudo_e_substancialmente_mais_especifico_que_5_8_B():
    """Comparação direta com o stub da Etapa 5.8-B, que motivou esta
    etapa: mais dados ancorados, e nenhuma frase de preenchimento."""
    from validate_fatos import _tokens_numericos
    stub_5_8_B = ("A apuração adotou o critério do inciso III do art. 595, com base na "
                  "média dos três maiores consumos dos doze ciclos regulares anteriores, "
                  "referentes ao período de janeiro a dezembro de 2024.\n"
                  "Os valores constam do memorial de faturamento anexo.")
    assert len(set(_tokens_numericos(CONTEUDO_VALIDO))) > len(set(_tokens_numericos(stub_5_8_B)))
    assert "constam do memorial" not in CONTEUDO_VALIDO


# =============================================================== Etapa 5.8-C.1: coerência semântica e aritmética
# Achado original: a redação de teste da 5.8-C afirmava "2.412 kWh x R$
# 1,7947/kWh = R$ 4.328,17" como se fosse a fórmula do memorial, e o
# produto real (R$ 4.328,82) divergia do que estava escrito. Antes de
# corrigir qualquer número, o GATE DE FECHAMENTO da 5.8-C.1 exigiu auditar
# o documento diretamente:
#
#   A. valor final registrado no memorial: R$ 4.328,17
#   B. tarifa registrada: R$ 1,7947/kWh
#   C. consumo recuperado registrado: 2.412 kWh (explícito: "402 kWh/ciclo
#      x 6 ciclos = 2.412 kWh")
#   D. metodologia/componente que explique diferença: o memorial só cita
#      "proporcionalizados em 30 (trinta) dias" como parte de COMO o
#      consumo médio de 612 kWh/ciclo foi obtido — não um ajuste aplicado
#      depois, sobre o produto final. Não há memorial de faturamento na
#      fixture.
#   E. os documentos apresentam "2.412 x 1,7947 = valor final" como
#      fórmula integral? NÃO — o memorial traz três fatos em linhas
#      SEPARADAS ("Diferença apurada: ... = 2.412 kWh." / "Tarifa
#      aplicável: R$ 1,7947/kWh." / "VALOR TOTAL APURADO: R$ 4.328,17"),
#      sem sinal de igual conectando tarifa x consumo ao total.
#
# Conclusão do gate: como os documentos NÃO afirmam a multiplicação como
# fórmula do total, a divergência de R$ 0,65 entre o produto simples e o
# valor documental NÃO é contradição interna da fixture — é o memorial
# sintético simplesmente não detalhando toda a apuração real (comum em
# documento de teste resumido). R$ 4.328,17 é PRESERVADO, nunca
# recalculado. O que estava errado era a REDAÇÃO/PROVENIÊNCIA de teste,
# que tinha inferido uma relação matemática que o documento não sustenta:
# corrigido removendo `operacao` do fato `valor_total_apurado` (a peça não
# afirma mais que a multiplicação produz o total) e ajustando o texto para
# apresentar tarifa e valor como fatos documentais paralelos ("aplicou a
# tarifa ... e consignou o valor"), nunca como resultado de conta
# ("do que resultou").
#
# A mecânica de aritmética (Decimal, unidades por cancelamento, as três
# regras de `_validar_aritmetica_zona`) permanece testada abaixo com
# cenários sintéticos — ela continua necessária para o dia em que uma
# peça FOR afirmar uma fórmula, só não é isso que a fixture real faz.
from decimal import Decimal

MEMORIAL = (FIXTURES / "happy_path" / "documentos" / "memorial_calculo_sintetico.txt")
FONTE_FAT = "memorial_faturamento_sintetico.txt"


def _aritmetica(fatos):
    from validate_fatos import _validar_aritmetica_zona
    return _validar_aritmetica_zona(fatos, ZONA_ID)


def test_5C1_fixture_valor_documental_e_preservado_sem_formula_explicita():
    """Regressão do achado + resultado da auditoria do gate de fechamento:
    o memorial NÃO escreve "2.412 x 1,7947 = R$ 4.328,17" em lugar algum —
    consumo, tarifa e valor total são três linhas separadas. O produto
    simples diverge do documental por R$ 0,65, e isso NÃO é tratado como
    inconsistência: `valor_total_apurado` não declara `operacao`, e o
    valor documental (R$ 4.328,17) é preservado tal como escrito."""
    texto = MEMORIAL.read_text(encoding="utf-8")
    for esperado in ("612 kWh/ciclo", "210 kWh/ciclo", "402 kWh/ciclo x 6 ciclos = 2.412 kWh",
                     "R$ 1,7947/kWh", "R$ 4.328,17"):
        assert esperado in texto, f"memorial da fixture alterado: falta {esperado!r}"
    # nenhuma linha do memorial conecta tarifa x consumo ao total por "="
    linha_tarifa = next(l for l in texto.splitlines() if "Tarifa aplicável" in l)
    linha_total = next(l for l in texto.splitlines() if "VALOR TOTAL APURADO" in l)
    assert "=" not in linha_tarifa and "1,7947" not in linha_total, \
        "memorial passou a apresentar fórmula explícita — reavaliar o gate"
    # o produto simples diverge do documental (por isso não há 'operacao')
    produto = (Decimal("2412") * Decimal("1.7947")).quantize(Decimal("0.01"))
    assert produto != Decimal("4328.17"), "produto e documental convergiram — reavaliar o teste"
    total = next(f for f in FATOS_ZONA if f["tipo"] == "valor_total_apurado")
    assert total["valor"] == "4.328,17" and "operacao" not in total
    assert not _aritmetica(FATOS_ZONA), _aritmetica(FATOS_ZONA)


def test_5C1_A_subtracao_documentada_passa():
    """§8.A: 612 - 210 = 402, declarado e conferido. Esta É uma operação
    que o memorial evidencia diretamente (612, 210 e 402 aparecem como
    consumo médio, consumo faturado e "diferença apurada", nessa ordem)."""
    assert not _prov(CONTEUDO_VALIDO, fontes=FONTES_DO_CASO)
    diferenca = next(f for f in FATOS_ZONA if f["tipo"] == "diferenca_por_ciclo")
    assert diferenca["operacao"]["op"] == "subtracao"
    assert diferenca["operacao"]["operandos"] == ["consumo_medio_apurado", "consumo_faturado"]


def test_5C1_B_multiplicacao_documentada_passa():
    """§8.B: 402 x 6 = 2.412, escrito LITERALMENTE no memorial ("402
    kWh/ciclo x 6 ciclos = 2.412 kWh") — ao contrário da multiplicação por
    tarifa, esta É apresentada como fórmula explícita, com a unidade
    cancelando (kWh/ciclo x ciclo = kWh)."""
    assert "402 kWh/ciclo x 6 ciclos = 2.412 kWh" in MEMORIAL.read_text(encoding="utf-8")
    total = next(f for f in FATOS_ZONA if f["tipo"] == "consumo_nao_registrado_total")
    assert total["operacao"] == {"op": "multiplicacao",
                                 "operandos": ["diferenca_por_ciclo", "ciclos_periodo_apuracao"]}
    assert total["unidade"] == "kWh"
    assert not _prov(CONTEUDO_VALIDO, fontes=FONTES_DO_CASO)


def test_5C1_C_operacao_afirmada_que_nao_fecha_e_fail_closed():
    """§8.C, cenário sintético: SE a peça afirmasse que a multiplicação
    produz o total (o que a redação real não faz mais, desde o gate de
    fechamento) E a conta não fechasse E nenhuma metodologia fosse
    declarada, o pipeline aborta. A mecânica precisa continuar funcionando
    mesmo não sendo usada pela fixture atual."""
    fatos = _fatos_zona(valor_total_apurado={
        "valor": "4.328,00",
        "operacao": {"op": "multiplicacao",
                     "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]}})
    erros = _aritmetica(fatos)
    assert any("não fecha com o valor documental" in e and "valor_total_apurado" in e
               for e in erros), erros
    assert any("4328.82" in e and "4328.00" in e for e in erros), erros
    # e o erro ORIENTA a consultar a metodologia documental — não manda
    # trocar o número por um cálculo da IA
    assert any("Memorial de Cálculo/Faturamento" in e for e in erros), erros


def test_5C1_D_tarifa_alterada_e_fail_closed():
    """§8.D, mesmo cenário sintético de C: mexer só na tarifa quebra a
    operação reproduzida, quando ela é afirmada."""
    fatos = _fatos_zona(valor_total_apurado={
        "valor": "4.328,17",
        "operacao": {"op": "multiplicacao",
                     "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]}},
        tarifa_aplicavel={"valor": "2,0000"})
    erros = _aritmetica(fatos)
    assert any("valor_total_apurado" in e and "não fecha" in e for e in erros), erros


def test_5C1_E_consumo_alterado_e_fail_closed():
    """§8.E: mexer no consumo médio quebra a diferença por ciclo — esta
    operação É declarada na fixture real (o memorial escreve a
    subtração/multiplicação dos ciclos explicitamente)."""
    fatos = _fatos_zona(consumo_medio_apurado={"valor": "700"})
    erros = _prov(CONTEUDO_VALIDO.replace("612", "700"), fatos, FONTES_DO_CASO)
    assert any("diferenca_por_ciclo" in e and "não fecha" in e for e in erros), erros


def test_5C1_F_unidade_incompativel_e_fail_closed():
    """§8.F: subtrair kWh/ciclo de kWh/ciclo não produz R$; e somar
    grandezas de espécies diferentes é barrado antes de qualquer conta."""
    fatos = _fatos_zona(diferenca_por_ciclo={"unidade": "R$"})
    assert any("unidade incompatível" in e for e in _prov(CONTEUDO_VALIDO, fatos, FONTES_DO_CASO))
    mistura = _fatos_zona(consumo_faturado={"unidade": "R$"})
    assert any("unidades diferentes" in e
               for e in _prov(CONTEUDO_VALIDO, mistura, FONTES_DO_CASO))


def test_5C1_G_dado_atribuido_a_fonte_errada_e_fail_closed():
    """§8.G: a tarifa consta da memória de cálculo, não do TOI. Atribuí-la
    ao TOI é fail-closed, mesmo com o número correto."""
    fatos = _fatos_zona(tarifa_aplicavel={"fonte": FONTE_TOI})
    erros = _prov(CONTEUDO_VALIDO, fatos, FONTES_DO_CASO)
    assert any("não constam desse documento" in e and FONTE_TOI in e for e in erros), erros


def test_5C1_G2_atribuicao_do_levantamento_dos_12_ciclos_e_a_real():
    """§3 do pedido original: auditoria da frase que dizia que o
    levantamento dos 12 ciclos "consta do Termo de Ocorrência e Inspeção".
    O TOI documenta que o levantamento FOI FEITO (providência do art. 590);
    o critério dos três maiores consumos e os valores estão na memória de
    cálculo. A redação foi corrigida para atribuir cada coisa ao documento
    que efetivamente a suporta."""
    toi = (FIXTURES / "happy_path" / "documentos" / "toi_sintetico.txt").read_text(encoding="utf-8")
    memorial = MEMORIAL.read_text(encoding="utf-8")
    assert "levantamento do histórico de consumo dos últimos 12 (doze) ciclos" in toi
    assert "média dos" not in toi and "612" not in toi, "o TOI não traz o critério nem os valores"
    assert "três maiores valores de consumo" in memorial
    assert "consta do Termo de Ocorrência" not in CONTEUDO_VALIDO
    assert "registrado na memória de cálculo" in CONTEUDO_VALIDO
    assert next(f for f in FATOS_ZONA
                if f["tipo"] == "ciclos_historico_levantado")["fonte"] == FONTE_TOI
    assert next(f for f in FATOS_ZONA
                if f["tipo"] == "criterio_apuracao")["fonte"] == FONTE_MEM


def test_5C1_H_dado_documental_direto_nao_sofre_recalculo():
    """§8.H: dado documental sem `operacao` é aceito como está — o
    pipeline não inventa contas que o documento não fez. Desde o gate de
    fechamento, `valor_total_apurado` É o exemplo real disso: o memorial
    não apresenta fórmula para o total, então a peça não afirma nenhuma."""
    tarifa = next(f for f in FATOS_ZONA if f["tipo"] == "tarifa_aplicavel")
    total = next(f for f in FATOS_ZONA if f["tipo"] == "valor_total_apurado")
    for fato in (tarifa, total):
        assert "operacao" not in fato and fato["natureza"] == "documental"
    assert not _aritmetica([tarifa, total])


def test_5C1_I_dado_derivado_identifica_seus_insumos():
    """§8.I: `derivado` sem `operacao` não passa; com `operacao` coerente,
    passa e os insumos são rastreáveis pelo `tipo`."""
    base = [f for f in FATOS_ZONA if f["tipo"] in
            ("diferenca_por_ciclo", "ciclos_periodo_apuracao",
             "consumo_medio_apurado", "consumo_faturado")]
    derivado = {"tipo": "consumo_nao_registrado_total_2", "valor": "2.412", "unidade": "kWh",
                "fonte": FONTE_MEM, "natureza": "derivado"}
    assert any("não declara 'operacao'" in e for e in _aritmetica(base + [derivado]))
    derivado["operacao"] = {"op": "multiplicacao",
                            "operandos": ["diferenca_por_ciclo", "ciclos_periodo_apuracao"]}
    assert not _aritmetica(base + [derivado])


def test_5C1_J_sem_componentes_nao_ha_calculo_inventado():
    """§8.J: operando não declarado aborta em vez de o pipeline estimar,
    completar ou inferir o componente que falta."""
    fatos = [f for f in _fatos_zona() if f["tipo"] != "ciclos_periodo_apuracao"]
    erros = _aritmetica(fatos)
    assert any("não declarado" in e and "ciclos_periodo_apuracao" in e for e in erros), erros
    assert not any("consumo_nao_registrado_total" in e and "não fecha" in e for e in erros), \
        "sem componente, nada é calculado — nem para reprovar"


def test_5C1_K_valor_derivado_afirmado_em_conflito_e_fail_closed():
    """§8.K: quando a peça apresenta um número como RESULTADO de uma conta
    (`derivado`) e a conta dá outro número, a afirmação é falsa — sempre,
    mesmo que o valor "derivado" coincida com o documental real."""
    conflitante = _fatos_zona() + [
        {"tipo": "valor_total_derivado", "valor": "4.328,17", "unidade": "R$",
         "fonte": FONTE_MEM, "natureza": "derivado",
         "operacao": {"op": "multiplicacao",
                      "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]}}]
    erros = _aritmetica(conflitante)
    assert any("inconsistência aritmética" in e and "valor_total_derivado" in e
               for e in erros), erros


def test_5C1_L_exclusao_da_zona_sem_regressao():
    """§8.L: nada disso tocou o caminho da zona vazia."""
    assert _estados(fatos={}) == {ZONA_ID: "EXCLUIR"}
    xml, relatorio = _compor("EXCLUIR")
    assert relatorio["excluidas"] == [ZONA_ID]
    assert TOKEN not in xml and ZONA_TAG not in xml
    from validate_fatos import normalizar_conteudo_zona
    assert normalizar_conteudo_zona(None) == ("", [], [])
    assert normalizar_conteudo_zona({"conteudo": "", "fatos": []}) == ("", [], [])


def test_5C1_media_conferida_quando_componentes_disponiveis():
    """§4: média entra no conjunto suportado, e só fecha quando todos os
    componentes estão declarados."""
    fatos = [
        {"tipo": "c1", "valor": "600", "unidade": "kWh", "fonte": FONTE_MEM, "natureza": "documental"},
        {"tipo": "c2", "valor": "612", "unidade": "kWh", "fonte": FONTE_MEM, "natureza": "documental"},
        {"tipo": "c3", "valor": "624", "unidade": "kWh", "fonte": FONTE_MEM, "natureza": "documental"},
        {"tipo": "media_tres_maiores", "valor": "612", "unidade": "kWh", "fonte": FONTE_MEM,
         "natureza": "derivado", "operacao": {"op": "media", "operandos": ["c1", "c2", "c3"]}},
    ]
    assert not _aritmetica(fatos)
    fatos[3]["valor"] = "620"
    assert any("inconsistência aritmética" in e for e in _aritmetica(fatos))


def test_5C1_dinheiro_nunca_em_float():
    """§4: valores monetários em Decimal. Uma diferença de centavos numa
    recuperação de consumo é uma afirmação falsa numa peça processual."""
    from validate_fatos import _quantidade
    import inspect
    import validate_fatos
    assert isinstance(_quantidade("R$ 4.328,17"), Decimal)
    assert _quantidade("R$ 4.328,17") == Decimal("4328.17")
    assert _quantidade("1,7947") == Decimal("1.7947")
    assert _quantidade("art. 595, III") is None, "dispositivo normativo não é quantidade"
    assert "float(" not in inspect.getsource(validate_fatos), \
        "nenhum caminho de dinheiro pode passar por float"


def test_5C1_pipeline_aborta_com_operacao_afirmada_que_nao_fecha():
    """Ponta a ponta, cenário sintético (a fixture real não afirma
    fórmula alguma para o total — ver test_5C1_fixture_...): SE uma zona
    afirmasse a multiplicação e ela não fechasse, o pipeline aborta antes
    do DOCX."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, {
            "conteudo": CONTEUDO_VALIDO.replace("4.328,17", "4.328,00"),
            "fatos": _fatos_zona(valor_total_apurado={
                "valor": "4.328,00",
                "operacao": {"op": "multiplicacao",
                             "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]}})})
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "zonas", r
        assert "não fecha com o valor documental" in r["reason"], r["reason"]
        assert not saida.exists()


# ------------------------------------------------- ajuste da 5.8-C.1: parágrafo sem espaços
def test_5C1_ajuste_A_paragrafo_ate_380_sem_espacos_passa():
    """Ajuste §6.A: 380 caracteres EFETIVOS. Um parágrafo com 380 sem
    espaços passa, mesmo tendo bem mais de 380 caracteres brutos — que era
    exatamente o que a contagem antiga reprovava."""
    from validate_paragrafos import comprimento_efetivo, validar_paragrafo_380
    p = ("ab " * 190).strip()          # 380 letras, 569 caracteres brutos
    assert comprimento_efetivo(p) == 380 and len(p) > 380
    assert not validar_paragrafo_380(p)


def test_5C1_ajuste_B_paragrafo_acima_de_380_sem_espacos_rejeita():
    """Ajuste §6.B: o limite material não foi relaxado."""
    from validate_paragrafos import comprimento_efetivo, validar_paragrafo_380
    p = ("ab " * 191).strip()          # 382 letras
    assert comprimento_efetivo(p) == 382
    erros = validar_paragrafo_380(p)
    assert erros and "382 caracteres sem espaços" in erros[0], erros


def test_5C1_ajuste_contagem_ignora_tabs_e_quebras_internas():
    """Ajuste §1: 'a mesma lógica para tabs e quebras internas'."""
    from validate_paragrafos import comprimento_efetivo
    assert comprimento_efetivo("a\tb\r c") == 3


def test_5C1_ajuste_limites_da_zona_sao_os_do_catalogo():
    """Ajuste §1 (gate de fechamento): max_paragrafos=3 e
    max_caracteres_total=1000 são DUAS CONTENÇÕES DIFERENTES e não devem
    ser uniformizadas — o teto por parágrafo mede densidade textual
    EFETIVA (sem espaços); o teto agregado é contenção global
    CONSERVADORA da zona, contado em caracteres BRUTOS."""
    from validate_paragrafos import validar_densidade_zonas, comprimento_efetivo
    zona = carregar_catalogo(CATALOGO_REAL)["zones"][0]
    assert zona["max_paragrafos"] == 3
    assert zona["max_caracteres_paragrafo"] == 380
    assert zona["max_caracteres_total"] == 1000
    paras = CONTEUDO_VALIDO.split("\n")
    assert len(paras) == 3
    assert all(comprimento_efetivo(p) <= 380 for p in paras)
    assert sum(len(p) for p in paras) <= 1000
    ok, erros = validar_densidade_zonas({ZONA_ID: CONTEUDO_VALIDO}, [zona])
    assert ok, erros

    # um parágrafo acima de 380 EFETIVOS continua reprovando na zona
    estourado = "x" * 381 + "\n" + paras[1]
    ok2, erros2 = validar_densidade_zonas({ZONA_ID: estourado}, [zona])
    assert not ok2 and any("sem espaços" in e for e in erros2), erros2

    # o teto agregado é bruto: um total com 1001 caracteres BRUTOS
    # reprova mesmo que cada parágrafo, isoladamente, caiba em 380 sem
    # espaços — as duas contagens não são a mesma métrica
    inflado = "\n".join(["x" * 380, "x" * 380, "x" * 241])
    assert all(comprimento_efetivo(p) <= 380 for p in inflado.split("\n"))
    ok3, erros3 = validar_densidade_zonas({ZONA_ID: inflado}, [zona])
    assert not ok3 and any("brutos" in e for e in erros3), erros3


# ------------------------------------------------- ajuste da 5.8-C.1: natureza da recuperação e fonte de verdade
def test_5C1_ajuste_C_valor_do_memorial_de_faturamento_e_preservado():
    """Ajuste §6.C, cenário sintético que EXERCITA o mecanismo de
    preservação (a peça real não afirma fórmula alguma para o total, ver
    test_5C1_fixture_...): SE a peça afirmasse a multiplicação E ela não
    fechasse com o valor do Memorial de Faturamento, E o fato declarasse
    `metodologia` apontando a explicação documental, o valor é
    preservado."""
    fatos = _fatos_zona(valor_total_apurado={
        "valor": "4.512,40",
        "fonte": FONTE_FAT,
        "operacao": {"op": "multiplicacao",
                     "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]},
        "metodologia": {"descricao": "valor faturado com tributos e bandeira tarifária "
                                     "aplicados sobre o montante recuperado",
                        "fonte": FONTE_FAT}})
    assert not _aritmetica(fatos), _aritmetica(fatos)


def test_5C1_ajuste_D_ia_nao_substitui_valor_documental_por_calculo_proprio():
    """Ajuste §6.D: no caminho REAL da fixture (sem `operacao` declarada),
    o validador não recalcula nada — só confere ancoragem/fonte — e os
    fatos de entrada permanecem byte-a-byte intactos após a chamada."""
    from validate_fatos import validar_proveniencia_zona
    fatos = _fatos_zona()
    antes = json.dumps(fatos, ensure_ascii=False, sort_keys=True)
    saida = validar_proveniencia_zona(CONTEUDO_VALIDO, fatos, ZONA_ID, FATOS_DO_CASO)
    assert json.dumps(fatos, ensure_ascii=False, sort_keys=True) == antes, \
        "o validador alterou os fatos de entrada — nunca deve reescrever valor"
    assert not saida, "caminho real (sem fórmula afirmada): nada a reportar"
    assert all(isinstance(e, str) for e in saida), "a saída é diagnóstico, não valor corrigido"


def test_5C1_ajuste_E_estimativa_regulamentar_nao_e_arbitrariedade():
    """Ajuste §6.E: apuração por estimativa segundo o critério da
    regulamentação é procedimento regular. Nada no pipeline trata a
    palavra 'estimativa' como defeito, e um texto de zona que descreve a
    apuração por estimativa regulamentar passa normalmente."""
    import validate_fatos
    import validate_placeholder_semantics
    for mod in (validate_fatos, validate_placeholder_semantics):
        for termo in ("estimativa", "estimado", "arbitrariedade"):
            for proibida in getattr(mod, "_FRASES_VAZIAS", ()):
                assert termo not in proibida or "arbitrariedade" in proibida
        assert "estimativa" not in getattr(mod, "_SENTINELAS_ZONA", ())

    texto = ("No caso concreto, a apuração observou o critério do art. 595, III, da "
             "Resolução ANEEL nº 1.000/2021, mediante estimativa do consumo não "
             "registrado a partir da média dos três maiores consumos dos 12 ciclos "
             "anteriores, tal como registrado na memória de cálculo.")
    fatos = [f for f in _fatos_zona()
             if f["tipo"] in ("criterio_apuracao", "ciclos_historico_levantado")]
    assert not _prov(texto, fatos, FONTES_DO_CASO)


def test_5C1_ajuste_F_divergencia_aparente_pede_metodologia_antes_do_fail_closed():
    """Ajuste §6.F, cenário sintético (a peça real não afirma fórmula
    para o total): a mesma divergência aritmética é fail-closed SEM
    metodologia documental declarada e passa COM ela — a consulta ao
    documento oficial vem antes de barrar."""
    op = {"op": "multiplicacao", "operandos": ["consumo_nao_registrado_total", "tarifa_aplicavel"]}
    sem = _fatos_zona(valor_total_apurado={"valor": "4.512,40", "operacao": op})
    assert any("não fecha com o valor documental" in e for e in _aritmetica(sem))

    com = _fatos_zona(valor_total_apurado={
        "valor": "4.512,40", "operacao": op,
        "metodologia": {"descricao": "proporcionalização em 30 dias e tributos, conforme "
                                     "a metodologia do próprio memorial",
                        "fonte": FONTE_MEM}})
    assert not _aritmetica(com)

    # mas a conciliação precisa apontar para documento da base do caso
    inventada = _fatos_zona(valor_total_apurado={
        "valor": "4.512,40", "operacao": op,
        "metodologia": {"descricao": "explicação criada pela IA", "fonte": "nao_existe.pdf"}})
    assert any("fora da base documental" in e
               for e in _prov(CONTEUDO_VALIDO, inventada, FONTES_DO_CASO))


def test_5C1_ajuste_G_contradicao_real_entre_documentos_oficiais_e_fail_closed():
    """Ajuste §6.G: Memorial de Cálculo e Memorial de Faturamento
    registrando valores diferentes para o MESMO dado é a contradição
    interna real — a defesa não escolhe um deles. Independe de qualquer
    `operacao` estar declarada: a contradição é detectada só por
    comparar registros do mesmo `tipo` entre fontes diferentes."""
    dois = _fatos_zona() + [
        {"tipo": "valor_total_apurado", "valor": "4.900,00", "unidade": "R$",
         "fonte": FONTE_FAT, "natureza": "documental"}]
    erros = _aritmetica(dois)
    assert any("contradição documental" in e for e in erros), erros
    assert any(FONTE_FAT in e and FONTE_MEM in e for e in erros), erros

    # registro repetido com o MESMO valor (o real, R$ 4.328,17) é
    # confirmação cruzada, não conflito
    confirmado = _fatos_zona() + [
        {"tipo": "valor_total_apurado", "valor": "4.328,17", "unidade": "R$",
         "fonte": FONTE_FAT, "natureza": "documental"}]
    assert not any("contradição documental" in e for e in _aritmetica(confirmado))


def test_5C1_ajuste_H_redacao_defende_a_cobranca_constituida():
    """Ajuste §6.H: a zona narra DOCUMENTAÇÃO -> CRITÉRIO -> METODOLOGIA
    APLICADA -> RESULTADO DOCUMENTADO -> LEGITIMIDADE, atribuindo cada
    número ao documento que o registra; nunca apresenta o valor como
    resultado de um cálculo feito pela peça."""
    assert "memória de cálculo" in CONTEUDO_VALIDO
    assert "art. 595, III" in CONTEUDO_VALIDO
    for verbo in ("registra", "consigna", "aplicou"):
        assert verbo in CONTEUDO_VALIDO, f"o texto não atribui o dado ao documento ({verbo})"
    assert "procedimento administrativo" in CONTEUDO_VALIDO
    assert "resultou" not in CONTEUDO_VALIDO, \
        "'resultou' apresentaria o valor como derivação de conta, não como fato documental"
    # nenhum fato da zona é apresentado como cálculo próprio da peça
    assert all(f["natureza"] == "documental" for f in FATOS_ZONA)
    # e o valor final é o do documento — SEM fórmula afirmada, porque o
    # memorial não apresenta uma (gate de fechamento, §2)
    total = next(f for f in FATOS_ZONA if f["tipo"] == "valor_total_apurado")
    assert total["valor"] == "4.328,17" and total["valor"] in CONTEUDO_VALIDO
    assert "operacao" not in total, \
        "valor_total_apurado não deve afirmar fórmula que o memorial não sustenta"
    assert total["valor"].replace(".", "").replace(",", "") in \
        MEMORIAL.read_text(encoding="utf-8").replace(".", "").replace(",", "")


# =============================================================== Etapa 5.8-E: continuidade com o texto institucional adjacente
# Achado do Teste Real 5.8-D: o parágrafo institucional imediatamente
# anterior à zona abria com "No caso concreto, a concessionária
# observou..."; o primeiro parágrafo da zona repetia a mesma abertura
# ("No caso concreto, a recuperação de consumo observou..."). Corrigido
# redigindo a zona para abrir direto no dado documental ("O Memorial de
# Faturamento identifica..."). A regra testada é GENÉRICA — o
# comparador (`paragrafos_compartilham_abertura`) não conhece a frase
# "No caso concreto"; ele só compara as N primeiras palavras normalizadas
# de dois parágrafos quaisquer.
INSTITUCIONAL_ANTERIOR_REAL = (
    "No caso concreto, a concessionária observou rigorosamente essa lógica "
    "normativa, adotando metodologia compatível com os elementos técnicos "
    "disponíveis, em total aderência à disciplina do art. 595")
ZONA_ABERTURA_ANTIGA_BUGADA = (
    "No caso concreto, a recuperação de consumo observou o critério da "
    "queda de consumo (art. 595, III, da Resolução ANEEL nº 1.000/2021)")
ZONA_ABERTURA_CORRIGIDA = (
    "O Memorial de Faturamento identifica o critério aplicado como a queda "
    "de consumo (art. 595, III, da Resolução ANEEL nº 1.000/2021)")


def test_5E_paragrafos_compartilham_abertura_e_generico():
    """A função compara as N primeiras palavras normalizadas — funciona
    para qualquer par de parágrafos, não é uma blacklist para 'No caso
    concreto'."""
    from validate_placeholder_semantics import paragrafos_compartilham_abertura as compartilham
    assert compartilham("Conforme o memorial, o critério aplicado foi X",
                         "Conforme o memorial, outro dado qualquer aqui", n_palavras=3)
    assert not compartilham("Conforme o memorial, o critério aplicado foi X",
                             "Conforme o memorial, outro dado qualquer aqui")  # 4ª palavra diverge
    assert not compartilham("Conforme o memorial, o critério aplicado foi X",
                             "O laudo técnico confirma outro dado qualquer")
    # variação de acentuação/caixa/pontuação não escapa a checagem
    assert compartilham("NO CASO CONCRETO, a apuração seguiu X",
                         "no caso concreto: a apuração seguiu Y completamente diferente")


def test_5E_achado_real_e_detectado_pelo_comparador_generico():
    """Regressão do achado real da Etapa 5.8-D: a abertura antiga da zona
    ('No caso concreto, a recuperação...') colide com a abertura do
    parágrafo institucional anterior; a corrigida ('O Memorial de
    Faturamento identifica...') não colide."""
    from validate_placeholder_semantics import paragrafos_compartilham_abertura as compartilham
    assert compartilham(INSTITUCIONAL_ANTERIOR_REAL, ZONA_ABERTURA_ANTIGA_BUGADA), \
        "o comparador deveria ter sinalizado a repetição real do Teste 5.8-D"
    assert not compartilham(INSTITUCIONAL_ANTERIOR_REAL, ZONA_ABERTURA_CORRIGIDA), \
        "a redação corrigida não deveria mais colidir com o parágrafo institucional"


def test_5E_teste_de_necessidade_nao_reduz_densidade_factual():
    """O ajuste da Etapa 5.8-E é sobre CONCLUSÃO redundante, nunca sobre
    densidade de dados: CONTEUDO_VALIDO continua com os mesmos elementos
    fáticos concretos exigidos desde a 5.8-C (não houve regressão para a
    redação pobre da 5.8-B)."""
    for dado in ("612", "210", "402", "2.412", "1,7947", "4.328,17", "595"):
        assert dado in CONTEUDO_VALIDO, f"densidade factual reduzida: falta {dado}"


# =============================================================== Etapa 5.8-D.1: gate automático de continuidade textual
# `paragrafos_compartilham_abertura` deixou de ser só utilitária de
# conferência manual: `validar_continuidade_zonas` (validate_placeholder_
# semantics.py) é chamada por `_etapa_zonas` (gerar_contestacao.py),
# alimentada por `contexto_institucional` — o MESMO dicionário que
# `_etapa_contexto_institucional` já calcula para o Redator, agora também
# repassado à etapa de zonas (a única mudança de fluxo desta etapa).
def _contexto_zona(antes="", depois=""):
    return {ZONA_ID: [{"antes": antes, "depois": depois}]}


def test_5D1_A_colisao_com_institucional_anterior_rejeita():
    """§6.A: abertura literal repetida entre parágrafo institucional
    anterior e primeiro parágrafo da zona."""
    ctx = _contexto_zona(antes=INSTITUCIONAL_ANTERIOR_REAL)
    ok, erros = validar_continuidade_zonas({ZONA_ID: ZONA_ABERTURA_ANTIGA_BUGADA}, ctx)
    assert not ok
    assert any("abertura do parágrafo institucional imediatamente anterior" in e
               for e in erros), erros


def test_5D1_B_abertura_diferente_passa():
    """§6.B: mesma situação, abertura da zona diferente."""
    ctx = _contexto_zona(antes=INSTITUCIONAL_ANTERIOR_REAL)
    ok, erros = validar_continuidade_zonas({ZONA_ID: ZONA_ABERTURA_CORRIGIDA}, ctx)
    assert ok, erros


def test_5D1_C_variacao_de_caixa_rejeita():
    """§6.C: maiúsculas/minúsculas não escapam a checagem."""
    ctx = _contexto_zona(antes=INSTITUCIONAL_ANTERIOR_REAL.upper())
    ok, erros = validar_continuidade_zonas({ZONA_ID: ZONA_ABERTURA_ANTIGA_BUGADA.lower()}, ctx)
    assert not ok, erros


def test_5D1_D_variacao_de_pontuacao_rejeita():
    """§6.D: pontuação diferente na mesma sequência de palavras."""
    ctx = _contexto_zona(antes="No... caso, concreto - a concessionária observou X")
    ok, erros = validar_continuidade_zonas(
        {ZONA_ID: "No caso: concreto, a concessionária observou Y completamente diferente"}, ctx)
    assert not ok, erros


def test_5D1_E_abertura_efetivamente_distinta_passa():
    """§6.E: zona e institucional adjacentes sem qualquer colisão de
    abertura, nos dois lados (anterior e posterior)."""
    ctx = _contexto_zona(antes=INSTITUCIONAL_ANTERIOR_REAL,
                          depois="Trata-se, portanto, de mecanismo de recomposição econômica")
    ok, erros = validar_continuidade_zonas({ZONA_ID: CONTEUDO_VALIDO}, ctx)
    assert ok, erros


def test_5D1_zona_vazia_ou_sem_contexto_nao_e_afetada():
    """Zona vazia não tem abertura a conferir; zona sem entrada em
    `contexto_zonas` (defensivo) também não é bloqueada por esta função —
    ambos os casos são tratados alhures."""
    ctx = _contexto_zona(antes=INSTITUCIONAL_ANTERIOR_REAL)
    assert validar_continuidade_zonas({ZONA_ID: ""}, ctx) == (True, [])
    assert validar_continuidade_zonas({ZONA_ID: ZONA_ABERTURA_ANTIGA_BUGADA}, {}) == (True, [])


def test_5D1_F_G_pipeline_aborta_e_nunca_toca_texto_institucional():
    """§6.F/G, ponta a ponta: zona que repete a abertura do parágrafo
    institucional imediatamente anterior aborta o pipeline ANTES do DOCX
    (fail-closed real, não simulado) — o texto institucional nunca é
    tocado; a correção necessária é sempre no conteúdo da zona."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        colidente = CONTEUDO_VALIDO.replace(
            "A apuração observou o critério",
            "No caso concreto, a apuração observou o critério")
        caso = _caso_com_zona(tmp, {"conteudo": colidente, "fatos": FATOS_ZONA})
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "zonas", r
        assert "INV-CONTINUIDADE-ZONA" in r["reason"], r["reason"]
        assert not saida.exists(), "G: nenhum DOCX parcial — nada é gravado, muito menos com "\
                                    "o texto institucional alterado"


def test_5D1_H_excluir_funciona_sem_o_gate():
    """§6.H: caminho EXCLUIR (zona vazia) continua funcionando — o gate de
    continuidade não se aplica a zona sem parágrafo algum."""
    if _pular_sem_template():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, conteudo=None)
        saida = Path(tmp) / "sem-zona.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "OK", r
        assert r["zonas_excluidas"] == [ZONA_ID], r


def test_5D1_I_fixture_corrigida_nao_colide_mais_com_template_real():
    """§6.I: CONTEUDO_VALIDO, corrigido nesta etapa, não colide mais com o
    parágrafo institucional real imediatamente anterior."""
    from validate_placeholder_semantics import paragrafos_compartilham_abertura as compartilham
    primeiro_paragrafo = CONTEUDO_VALIDO.split("\n")[0]
    assert not compartilham(INSTITUCIONAL_ANTERIOR_REAL, primeiro_paragrafo), \
        "CONTEUDO_VALIDO ainda colide com o parágrafo institucional real"


def test_5D1_J_K_L_geracao_valida_passa_pelo_gate_sem_regressao():
    """§6.J/K/L: com conteúdo de zona que NÃO colide (o caminho normal,
    após a correção da 5.8-D/5.8-E), o gate de continuidade não impede a
    geração — Template Lock OK, 13 placeholders, composição de blocos e
    numeração íntegras. Não duplica geração: reaproveita a mesma chamada
    que `test_AA_AC_AD_AF_e2e_zona_incluida_contra_template_real` já faz
    (ZONA_RICA, agora com CONTEUDO_VALIDO corrigido) — só acrescenta as
    asserções específicas deste gate que aquele teste não fazia."""
    if _pular_sem_template():
        return
    schema = json.loads((BASE / "templates" / "contestacao" / "schema.json").read_text(encoding="utf-8"))
    assert len(schema["editable_placeholders"]) == 13, "L: 13 placeholders oficiais preservados"
    with tempfile.TemporaryDirectory() as tmp:
        caso = _caso_com_zona(tmp, ZONA_RICA)
        saida = Path(tmp) / "com-zona.docx"
        r = gerar_contestacao.gerar(caso, saida, resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"  # J
        assert "CALCULOS_RECUPERACAO_CONSUMO" in r["blocos_incluidos"]  # L
        assert r["blocos_indeterminados"] == []  # L
        assert r["zonas_incluidas"] == [ZONA_ID]  # K


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)} testes passaram.")
