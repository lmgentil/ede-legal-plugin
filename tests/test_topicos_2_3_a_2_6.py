#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_topicos_2_3_a_2_6.py — regressão dos quatro tópicos preliminares
acrescentados na Etapa 5.8-G (2.3 ausência de interesse de agir, 2.4
ilegitimidade ativa por titularidade de terceiro, 2.5 inépcia da inicial,
2.6 impugnação ao valor da causa) e dos dois subblocos aninhados neles
(AUSENCIA_TRANSFERENCIA_TITULARIDADE em 2.4, CUMULACAO_PEDIDOS em 2.6) e
das quatro zonas de complementação novas.

Mesmo padrão dos demais testes do projeto: asserts + `if __name__ ==
"__main__"`, sem framework, pytest opcional só para os marcadores/skip.

Cobre a matriz A-X do pedido da Etapa 5.8-G:
  - A-C: decisão 2.3 (state_linked, AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA)
  - D-G: decisão 2.4 (state_linked) + subbloco AUSENCIA_TRANSFERENCIA_TITULARIDADE
  - H-K: decisão 2.5 (estrategista) + proveniência da zona
  - L-P: decisão 2.6 (state_linked) + subbloco CUMULACAO_PEDIDOS + zona não recalcula
  - Q: renumeração sem buracos (docx_numeracao_engine, complementa o
    self-test já existente naquele módulo)
  - R-S, W-X: LOCAL_ONLY contra o DOCX real (modelo-oficial_topicos-2.3-
    a-2.6_contratados.docx) — SKIP explícito se ausente
  - T-U: densidade (380 sem espaços) e continuidade textual das 4 zonas novas
  - V: bloco excluído remove zona/subbloco em cascata (SDT aninhado real)

Catálogo sintético (CATALOGO_5_8_G) usado nos testes A-V para isolar a
lógica de decisão/ativação do arquivo DOCX real — mesma estratégia já
comprovada em tests/test_zonas_complementacao.py (CATALOGO_SIMPLES/
_catalogo_sintetico). Os testes R/S/W/X, que precisam mesmo do SDT físico,
usam o catálogo REAL (templates/contestacao/blocos.json) contra o DOCX
novo — os dois já estão em sincronia (Etapa 5.8-G).

Uso:
  python tests/test_topicos_2_3_a_2_6.py
"""
import sys
import tempfile
from pathlib import Path

import lxml.etree as LET
import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    compor_blocos,
    gerar_peca_com_blocos,
    resolver_estados_zonas,
    validar_catalogo,
    validar_e_resolver_decisoes,
)
from validate_fatos import validar_proveniencia_zona  # noqa: E402
from validate_paragrafos import validar_densidade_zonas  # noqa: E402
from validate_placeholder_semantics import validar_continuidade_zonas  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

TEMPLATE_2_3_A_2_6 = BASE / "templates" / "contestacao" / "modelo-oficial_topicos-2.3-a-2.6_contratados.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"

FONTE = "peticao_inicial_sintetica.txt"


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except ComposicaoAbortada as e:
        return e


def _pular_sem_template():
    """Etapa 5.10, Commit 5: pytest.skip() explícito — nunca conta como
    PASSED quando o asset não está instalado (falso verde corrigido)."""
    if not TEMPLATE_2_3_A_2_6.exists():
        pytest.skip(f"{TEMPLATE_2_3_A_2_6} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")


# ============================================================== catálogo sintético
CATALOGO_5_8_G = {
    "blocks": [
        {"id": "PRELIMINARES", "tag": "BLOCO:PRELIMINARES", "tipo": "CONTAINER_DERIVED",
         "parent": None,
         "children": ["PRELIMINAR_AUSENCIA_INTERESSE_AGIR", "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
                       "PRELIMINAR_INEPCIA_INICIAL", "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"],
         "decision_mode": "derived", "derived_rule": "ANY_CHILD_INCLUDED",
         "placeholders": [], "dependencies": [], "cardinality": "ONE"},
        {"id": "PRELIMINAR_AUSENCIA_INTERESSE_AGIR", "tag": "BLOCO:PRELIMINAR_AUSENCIA_INTERESSE_AGIR",
         "tipo": "CONDICIONAL_PADRAO", "parent": "PRELIMINARES", "children": [],
         "decision_mode": "state_linked", "linked_fact": "AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA",
         "placeholders": [], "dependencies": [], "cardinality": "ONE"},
        {"id": "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO", "tag": "BLOCO:PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
         "tipo": "CONDICIONAL_PADRAO", "parent": "PRELIMINARES", "children": [],
         "decision_mode": "state_linked", "linked_fact": "UC_TITULARIDADE_TERCEIRO_COMPROVADA",
         "placeholders": ["CONTA_CONTRATO", "NOME_TITULAR_DA_UC", "TELAS_DA_TITULARIDADE"],
         "dependencies": [], "cardinality": "ONE"},
        {"id": "SUBBLOCO_AUSENCIA_TRANSFERENCIA_TITULARIDADE", "tag": "SUBBLOCO:AUSENCIA_TRANSFERENCIA_TITULARIDADE",
         "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [],
         "decision_mode": "state_linked", "linked_fact": "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA",
         "placeholders": [], "dependencies": [], "cardinality": "ONE"},
        {"id": "PRELIMINAR_INEPCIA_INICIAL", "tag": "BLOCO:PRELIMINAR_INEPCIA_INICIAL",
         "tipo": "CONDICIONAL_PADRAO", "parent": "PRELIMINARES", "children": [],
         "decision_mode": "estrategista",
         "placeholders": ["SINOPSE_FATOS_NUCLEO_OBJETO"], "dependencies": [], "cardinality": "ONE"},
        {"id": "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA", "tag": "BLOCO:PRELIMINAR_IMPUGNACAO_VALOR_CAUSA",
         "tipo": "CONDICIONAL_PADRAO", "parent": "PRELIMINARES", "children": [],
         "decision_mode": "state_linked", "linked_fact": "EXISTE_DISCREPANCIA_VALOR_CAUSA",
         "placeholders": ["VALOR_DA_CAUSA"], "dependencies": [], "cardinality": "ONE"},
        {"id": "SUBBLOCO_CUMULACAO_PEDIDOS", "tag": "SUBBLOCO:CUMULACAO_PEDIDOS",
         "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [],
         "decision_mode": "state_linked", "linked_fact": "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS",
         "placeholders": [], "dependencies": [], "cardinality": "ONE"},
    ],
    "zones": [
        {"id": "ZONA_PRETENSAO_RESISTIDA", "tag": "ZONA:PRETENSAO_RESISTIDA",
         "bloco_pai": "PRELIMINAR_AUSENCIA_INTERESSE_AGIR",
         "finalidade": "individualizar a ausência de pretensão resistida",
         "tipo_conteudo": "dado_documental",
         "requires_facts": ["AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA"],
         "max_paragrafos": 2, "max_caracteres_paragrafo": 380, "max_caracteres_total": 700,
         "exige_proveniencia": True, "comportamento_vazia": "remover_sdt"},
        {"id": "ZONA_TITULARIDADE_UC", "tag": "ZONA:TITULARIDADE_UC",
         "bloco_pai": "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
         "finalidade": "individualizar a divergência de titularidade da UC",
         "tipo_conteudo": "dado_documental",
         "requires_facts": ["UC_TITULARIDADE_TERCEIRO_COMPROVADA"],
         "max_paragrafos": 2, "max_caracteres_paragrafo": 380, "max_caracteres_total": 700,
         "exige_proveniencia": True, "comportamento_vazia": "remover_sdt"},
        {"id": "ZONA_FUNDAMENTACAO_INEPCIA", "tag": "ZONA:FUNDAMENTACAO_INEPCIA",
         "bloco_pai": "PRELIMINAR_INEPCIA_INICIAL",
         "finalidade": "listar deficiências concretas da inicial",
         "tipo_conteudo": "dado_documental",
         "requires_facts": ["DEFICIENCIAS_INICIAL_DOCUMENTADAS"],
         "max_paragrafos": 3, "max_caracteres_paragrafo": 380, "max_caracteres_total": 1000,
         "exige_proveniencia": True, "comportamento_vazia": "remover_sdt"},
        {"id": "ZONA_COMPOSICAO_PROVEITO_ECONOMICO", "tag": "ZONA:COMPOSICAO_PROVEITO_ECONOMICO",
         "bloco_pai": "SUBBLOCO_CUMULACAO_PEDIDOS",
         "finalidade": "descrever a composição documental do proveito econômico",
         "tipo_conteudo": "dado_documental",
         "requires_facts": ["EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS"],
         "max_paragrafos": 3, "max_caracteres_paragrafo": 380, "max_caracteres_total": 1000,
         "exige_proveniencia": True, "comportamento_vazia": "remover_sdt"},
    ],
}


def test_catalogo_sintetico_e_estruturalmente_valido():
    validar_catalogo(CATALOGO_5_8_G)


# CATALOGO_5_8_G tem UM bloco manual (PRELIMINAR_INEPCIA_INICIAL,
# decision_mode='estrategista') — ele SEMPRE exige uma entrada em
# `decisoes` (decisao_ausente, senão), mesmo nos testes A-G/L-P que não
# têm nada a ver com o tópico 2.5. `_resolver` fixa essa decisão em
# EXCLUIR por padrão (irrelevante ao cenário testado) para isolar
# exclusivamente a lógica que cada teste realmente quer exercitar —
# sobrescrevível via `decisoes_extra` para os testes H-K/decisão-manual
# que precisam de outro valor ali.
def _resolver(decisoes_extra=None, fatos=None):
    decisoes = {"PRELIMINAR_INEPCIA_INICIAL": {"decisao": "EXCLUIR"}}
    if decisoes_extra:
        decisoes.update(decisoes_extra)
    return validar_e_resolver_decisoes(CATALOGO_5_8_G, decisoes, fatos or {})


def _resolver_abortou(decisoes_extra=None, fatos=None):
    return _abortou(_resolver, decisoes_extra, fatos)


# =============================================================== A-C: tópico 2.3
def test_A_ausencia_tentativa_administrativa_inclui():
    estados = _resolver(fatos={"AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA": True})
    assert estados["PRELIMINAR_AUSENCIA_INTERESSE_AGIR"] == "INCLUIR"


def test_B_pretensao_resistida_exclui_sem_perguntar():
    for fatos in ({}, {"AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA": False}):
        estados = _resolver(fatos=dict(fatos))
        assert estados["PRELIMINAR_AUSENCIA_INTERESSE_AGIR"] == "EXCLUIR"


def test_C_indeterminado_aborta():
    e = _resolver_abortou(fatos={"AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA": "INDETERMINADO"})
    assert e and e.stage == "decisao_indeterminada"


def test_decisao_manual_para_state_linked_e_rejeitada():
    # PRELIMINAR_AUSENCIA_INTERESSE_AGIR, PRELIMINAR_ILEGITIMIDADE_ATIVA_
    # TERCEIRO, PRELIMINAR_IMPUGNACAO_VALOR_CAUSA e os dois subblocos nunca
    # aceitam decisão manual — mesmo tratamento fail-closed de
    # PRELIMINAR_REVOGACAO_GRATUIDADE (INV-GRATUIDADE-LINKED).
    for bid in ("PRELIMINAR_AUSENCIA_INTERESSE_AGIR", "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
                "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA", "SUBBLOCO_AUSENCIA_TRANSFERENCIA_TITULARIDADE",
                "SUBBLOCO_CUMULACAO_PEDIDOS"):
        e = _resolver_abortou(decisoes_extra={bid: {"decisao": "INCLUIR"}})
        assert e and e.stage == "decisao_invalida", bid


# =============================================================== D-G: tópico 2.4 + subbloco
def test_D_titularidade_terceiro_inclui():
    estados = _resolver(fatos={"UC_TITULARIDADE_TERCEIRO_COMPROVADA": True})
    assert estados["PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO"] == "INCLUIR"


def test_E_titular_e_a_propria_autora_exclui():
    for fatos in ({}, {"UC_TITULARIDADE_TERCEIRO_COMPROVADA": False}):
        estados = _resolver(fatos=dict(fatos))
        assert estados["PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO"] == "EXCLUIR"


def test_F_titularidade_indeterminada_aborta():
    e = _resolver_abortou(fatos={"UC_TITULARIDADE_TERCEIRO_COMPROVADA": "INDETERMINADO"})
    assert e and e.stage == "decisao_indeterminada"


def test_G_subbloco_transferencia_so_aparece_quando_suportado():
    # ausência de transferência comprovada -> subbloco INCLUIR
    estados = _resolver(fatos={"AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA": True})
    assert estados["SUBBLOCO_AUSENCIA_TRANSFERENCIA_TITULARIDADE"] == "INCLUIR"
    # transferência comprovada (ou fato ausente) -> subbloco EXCLUIR, sem pergunta
    for fatos in ({}, {"AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA": False}):
        estados = _resolver(fatos=dict(fatos))
        assert estados["SUBBLOCO_AUSENCIA_TRANSFERENCIA_TITULARIDADE"] == "EXCLUIR"
    # fato do subbloco é INDEPENDENTE do fato do bloco-pai — pode INCLUIR o
    # subbloco mesmo com o pai EXCLUIR (a fisicalidade do SDT aninhado é
    # quem garante que o subbloco nunca sobrevive sozinho — ver teste V).
    estados = _resolver(fatos={"UC_TITULARIDADE_TERCEIRO_COMPROVADA": False,
                                "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA": True})
    assert estados["PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO"] == "EXCLUIR"
    assert estados["SUBBLOCO_AUSENCIA_TRANSFERENCIA_TITULARIDADE"] == "INCLUIR"


# =============================================================== H-K: tópico 2.5 + zona
def test_H_inicial_inepta_decidida_pelo_estrategista_inclui():
    estados = _resolver(decisoes_extra={"PRELIMINAR_INEPCIA_INICIAL": {"decisao": "INCLUIR"}})
    assert estados["PRELIMINAR_INEPCIA_INICIAL"] == "INCLUIR"


def test_I_inicial_individualizada_exclui():
    estados = _resolver(decisoes_extra={"PRELIMINAR_INEPCIA_INICIAL": {"decisao": "EXCLUIR"}})
    assert estados["PRELIMINAR_INEPCIA_INICIAL"] == "EXCLUIR"


def test_J_decisao_ausente_ou_indeterminada_aborta():
    # decisões completamente ausentes (não via _resolver, que sempre fixa
    # um valor default) -> decisao_ausente é o único bloco manual do
    # catálogo sintético, então é ele quem o motor cobra primeiro.
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_5_8_G, {}, {})
    assert e and e.stage == "decisao_ausente"
    e = _resolver_abortou(decisoes_extra={"PRELIMINAR_INEPCIA_INICIAL": {"decisao": "INDETERMINADO"}})
    assert e and e.stage == "decisao_indeterminada"


def test_K_zona_inepcia_exige_proveniencia_completa():
    # fato sem 'fonte' — rejeitado
    erros = validar_proveniencia_zona(
        "A inicial não individualiza a data do fato geral.",
        [{"tipo": "ausencia_individualizacao", "valor": "data do fato",
          "natureza": "documental"}],  # falta 'fonte'
        "ZONA_FUNDAMENTACAO_INEPCIA", fatos_do_caso=[])
    assert erros and any("fonte" in e for e in erros)
    # fato citando fonte fora da base documental do caso — rejeitado
    erros = validar_proveniencia_zona(
        "A inicial não junta o comprovante de residência.",
        [{"tipo": "documento_ausente", "valor": "comprovante de residência",
          "fonte": "documento_inexistente.pdf", "natureza": "documental"}],
        "ZONA_FUNDAMENTACAO_INEPCIA",
        fatos_do_caso=[{"fact": "petição inicial protocolada", "source_document": FONTE}])
    assert erros and any("não consta da base documental" in e for e in erros)


# =============================================================== L-P: tópico 2.6 + subbloco + zona
def test_L_discrepancia_comprovada_inclui():
    estados = _resolver(fatos={"EXISTE_DISCREPANCIA_VALOR_CAUSA": True})
    assert estados["PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"] == "INCLUIR"


def test_M_valor_correto_exclui():
    for fatos in ({}, {"EXISTE_DISCREPANCIA_VALOR_CAUSA": False}):
        estados = _resolver(fatos=dict(fatos))
        assert estados["PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"] == "EXCLUIR"


def test_N_calculo_indeterminado_aborta():
    e = _resolver_abortou(fatos={"EXISTE_DISCREPANCIA_VALOR_CAUSA": "INDETERMINADO"})
    assert e and e.stage == "decisao_indeterminada"


def test_O_zona_composicao_nao_exige_nem_recalcula_operacao():
    # a zona aceita fatos puramente documentais, sem NENHUMA 'operacao' —
    # ela demonstra a composição, não recalcula EXISTE_DISCREPANCIA_VALOR_
    # CAUSA (que é resolvida à parte, fora do motor documental).
    erros = validar_proveniencia_zona(
        "A petição inicial cumula pedido de repetição de indébito no valor de "
        "R$ 1.200,00 e pedido de indenização por dano moral estimado em R$ 10.000,00.",
        [{"tipo": "pedido_repeticao_indebito", "valor": "1.200,00", "unidade": "R$",
          "fonte": FONTE, "natureza": "documental"},
         {"tipo": "pedido_dano_moral_estimado", "valor": "10.000,00", "unidade": "R$",
          "fonte": FONTE, "natureza": "documental"}],
        "ZONA_COMPOSICAO_PROVEITO_ECONOMICO",
        fatos_do_caso=[{
            "fact": "A inicial formula pedido de repetição de indébito no valor de R$ 1.200,00 "
                    "e pedido de indenização por dano moral estimado em R$ 10.000,00.",
            "source_document": FONTE,
        }])
    assert erros == [], erros


def test_P_subbloco_cumulacao_funciona():
    estados = _resolver(fatos={"EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS": True})
    assert estados["SUBBLOCO_CUMULACAO_PEDIDOS"] == "INCLUIR"
    for fatos in ({}, {"EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS": False}):
        estados = _resolver(fatos=dict(fatos))
        assert estados["SUBBLOCO_CUMULACAO_PEDIDOS"] == "EXCLUIR"
    # cascata da zona: subbloco EXCLUIR -> zona EXCLUIR automaticamente
    estados_zonas = resolver_estados_zonas(CATALOGO_5_8_G, estados, {}, {})
    assert estados_zonas["ZONA_COMPOSICAO_PROVEITO_ECONOMICO"] == "EXCLUIR"


# =============================================================== Q: renumeração (complementa docx_numeracao_engine.py)
def test_Q_renumeracao_2_3_a_2_6_sem_buracos():
    from docx_numeracao_engine import renumerar_titulos, validar_numeracao_final

    def _p_badge(t):
        return ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="17"/></w:numPr></w:pPr>'
                f'<w:r><w:t>{t}</w:t></w:r></w:p>')

    def _p(t):
        return f'<w:p><w:r><w:t>{t}</w:t></w:r></w:p>'

    xml = (
        f'<w:document xmlns:w="{W}"><w:body>'
        + _p_badge("TEMPESTIVIDADE") + _p_badge("PRELIMINARES")
        + _p("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR")
        # 2.2 (GRATUIDADE) e 2.4 (ILEGITIMIDADE) ausentes — simula EXCLUIR
        + _p("2.3. DA AUSÊNCIA DE INTERESSE DE AGIR (RESTO)")
        + _p("2.5. DA INÉPCIA DA PETIÇÃO INICIAL (RESTO)")
        + _p("2.6. DA IMPUGNAÇÃO AO VALOR DA CAUSA (RESTO)")
        + _p_badge("MÉRITO")
        + _p("3.1 - LEGALIDADE DOS PROCEDIMENTOS")
        + _p("3.1.1 - SINOPSE DOS FATOS")
        + _p("3.1.2 - REALIDADE FÁTICA")
        + '</w:body></w:document>'
    )
    novo, rel = renumerar_titulos(xml)
    assert rel["numeracao"]["PRELIMINAR_CDC_INAPLICAVEL"] == "2.1"
    assert rel["numeracao"]["PRELIMINAR_AUSENCIA_INTERESSE_AGIR"] == "2.2"
    assert rel["numeracao"]["PRELIMINAR_INEPCIA_INICIAL"] == "2.3"
    assert rel["numeracao"]["PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"] == "2.4"
    assert "PRELIMINAR_REVOGACAO_GRATUIDADE" not in rel["numeracao"]
    assert "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO" not in rel["numeracao"]
    assert validar_numeracao_final(novo) == []


# =============================================================== T-U: densidade e continuidade
def test_T_zona_acima_de_380_sem_espacos_e_rejeitada():
    paragrafo_longo = "a" * 381  # 381 caracteres efetivos, sem espaço
    ok, erros = validar_densidade_zonas(
        {"ZONA_PRETENSAO_RESISTIDA": paragrafo_longo}, CATALOGO_5_8_G["zones"])
    assert not ok
    assert any("380" in e for e in erros)


def test_T2_zona_dentro_de_380_sem_espacos_passa():
    paragrafo_ok = "a" * 380
    ok, erros = validar_densidade_zonas(
        {"ZONA_PRETENSAO_RESISTIDA": paragrafo_ok}, CATALOGO_5_8_G["zones"])
    assert ok, erros


def test_U_continuidade_zona_rejeita_colisao_de_abertura():
    contexto = {
        "ZONA_TITULARIDADE_UC": [{
            "antes": "No caso concreto, a divergência de titularidade é evidente nos autos.",
            "depois": "Diante disso, impõe-se o reconhecimento da ilegitimidade ativa.",
        }],
    }
    ok, erros = validar_continuidade_zonas(
        {"ZONA_TITULARIDADE_UC": "No caso concreto, a divergência de titularidade é confirmada pela fatura."},
        contexto)
    assert not ok
    assert any("ZONA_TITULARIDADE_UC" in e for e in erros)


def test_U2_continuidade_zona_sem_colisao_passa():
    contexto = {
        "ZONA_TITULARIDADE_UC": [{
            "antes": "No caso concreto, a divergência de titularidade é evidente nos autos.",
            "depois": "Diante disso, impõe-se o reconhecimento da ilegitimidade ativa.",
        }],
    }
    ok, erros = validar_continuidade_zonas(
        {"ZONA_TITULARIDADE_UC": "A fatura nº 123 registra a UC em nome de terceiro desde 2022."},
        contexto)
    assert ok, erros


# =============================================================== V: cascata bloco excluído -> subbloco+zona somem
# Catálogo TRIMADO (não CATALOGO_5_8_G inteiro) — compor_blocos() só lê
# tags_catalogo/estados, nunca cruza contra parent/zones; usar o catálogo
# cheio aqui exigiria que a XML sintética contivesse as 7 SDTs de bloco +
# 4 de zona (ela só tem 2+1, de propósito, para isolar a cascata) e
# `validar_sdts_contra_catalogo` abortaria por `tag_ausente` antes de
# testar coisa alguma — mesma armadilha já corrigida em
# docx_numeracao_engine.py (self-test caso D, Etapa 5.8-G).
_CATALOGO_V = {"blocks": [
    {"id": "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA", "tag": "BLOCO:PRELIMINAR_IMPUGNACAO_VALOR_CAUSA",
     "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [], "decision_mode": "state_linked",
     "linked_fact": "EXISTE_DISCREPANCIA_VALOR_CAUSA", "placeholders": [], "dependencies": [], "cardinality": "ONE"},
    {"id": "SUBBLOCO_CUMULACAO_PEDIDOS", "tag": "SUBBLOCO:CUMULACAO_PEDIDOS",
     "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [], "decision_mode": "state_linked",
     "linked_fact": "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS", "placeholders": [], "dependencies": [], "cardinality": "ONE"},
]}


def test_V_bloco_excluido_remove_subbloco_e_zona_aninhados():
    # Reproduz a topologia física real auditada no DOCX: ZONA:COMPOSICAO_
    # PROVEITO_ECONOMICO aninhada DENTRO de SUBBLOCO:CUMULACAO_PEDIDOS,
    # que por sua vez está DENTRO de BLOCO:PRELIMINAR_IMPUGNACAO_VALOR_CAUSA.
    xml = (
        f'<w:document xmlns:w="{W}"><w:body>'
        '<w:p><w:r><w:t>texto antes</w:t></w:r></w:p>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"/></w:sdtPr>'
        '<w:sdtContent>'
        '<w:p><w:r><w:t>2.6 texto fixo do topico</w:t></w:r></w:p>'
        '<w:sdt><w:sdtPr><w:tag w:val="SUBBLOCO:CUMULACAO_PEDIDOS"/></w:sdtPr>'
        '<w:sdtContent>'
        '<w:p><w:r><w:t>texto fixo do subbloco</w:t></w:r></w:p>'
        '<w:sdt><w:sdtPr><w:tag w:val="ZONA:COMPOSICAO_PROVEITO_ECONOMICO"/></w:sdtPr>'
        '<w:sdtContent><w:p><w:r><w:t>{{ZONA_COMPOSICAO_PROVEITO_ECONOMICO}}</w:t></w:r></w:p></w:sdtContent>'
        '</w:sdt>'
        '</w:sdtContent></w:sdt>'
        '</w:sdtContent></w:sdt>'
        '<w:p><w:r><w:t>texto depois</w:t></w:r></w:p>'
        '</w:body></w:document>'
    )
    root = LET.fromstring(xml.encode("utf-8"))
    # bloco 2.6 EXCLUIR, mesmo que o subbloco (fisicamente dentro dele)
    # tenha sido resolvido como INCLUIR — a fisicalidade remove os dois
    # juntos, sem exigir regra adicional. compor_blocos() nunca vê a tag
    # ZONA:* (fica intocada por design, resolvida depois por compor_zonas)
    # — ela é removida aqui só porque é descendente física do <w:sdt>
    # removido, não por nenhuma lógica de zona.
    estados = {"PRELIMINAR_IMPUGNACAO_VALOR_CAUSA": "EXCLUIR", "SUBBLOCO_CUMULACAO_PEDIDOS": "INCLUIR"}
    compor_blocos(root, _CATALOGO_V, estados)
    saida = LET.tostring(root).decode("utf-8")
    assert "texto fixo do topico" not in saida
    assert "texto fixo do subbloco" not in saida
    assert "{{ZONA_COMPOSICAO_PROVEITO_ECONOMICO}}" not in saida
    assert "<w:sdt>" not in saida
    assert "texto antes" in saida and "texto depois" in saida


def test_V2_bloco_incluido_subbloco_excluido_zona_some_mas_topico_permanece():
    xml = (
        f'<w:document xmlns:w="{W}"><w:body>'
        '<w:sdt><w:sdtPr><w:tag w:val="BLOCO:PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"/></w:sdtPr>'
        '<w:sdtContent>'
        '<w:p><w:r><w:t>2.6 texto fixo do topico</w:t></w:r></w:p>'
        '<w:sdt><w:sdtPr><w:tag w:val="SUBBLOCO:CUMULACAO_PEDIDOS"/></w:sdtPr>'
        '<w:sdtContent>'
        '<w:p><w:r><w:t>texto fixo do subbloco</w:t></w:r></w:p>'
        '<w:sdt><w:sdtPr><w:tag w:val="ZONA:COMPOSICAO_PROVEITO_ECONOMICO"/></w:sdtPr>'
        '<w:sdtContent><w:p><w:r><w:t>{{ZONA_COMPOSICAO_PROVEITO_ECONOMICO}}</w:t></w:r></w:p></w:sdtContent>'
        '</w:sdt>'
        '</w:sdtContent></w:sdt>'
        '</w:sdtContent></w:sdt>'
        '</w:body></w:document>'
    )
    root = LET.fromstring(xml.encode("utf-8"))
    estados = {"PRELIMINAR_IMPUGNACAO_VALOR_CAUSA": "INCLUIR", "SUBBLOCO_CUMULACAO_PEDIDOS": "EXCLUIR"}
    compor_blocos(root, _CATALOGO_V, estados)
    saida = LET.tostring(root).decode("utf-8")
    assert "texto fixo do topico" in saida  # 2.6 sobrevive
    assert "texto fixo do subbloco" not in saida  # subbloco excluído some
    assert "{{ZONA_COMPOSICAO_PROVEITO_ECONOMICO}}" not in saida  # zona vai junto (descendente do subbloco)
    assert "<w:sdt>" not in saida


# =============================================================== R/S/W/X: LOCAL_ONLY contra o DOCX real
def _dados_e_decisoes_completos():
    """{19 placeholders} + decisões/fatos cobrindo TODOS os blocos do
    catálogo real (templates/contestacao/blocos.json), tudo incluído."""
    catalogo = carregar_catalogo(CATALOGO_REAL)
    dados = {
        "JUIZO": "1ª Vara Cível da Comarca de Salvador/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "**ligação direta** (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
        "CONTA_CONTRATO": "0000000000 (dado fictício de teste)",
        "NOME_TITULAR_DA_UC": "CICLANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TELAS_DA_TITULARIDADE": "[INSERIR MANUALMENTE AS TELAS/DOCUMENTOS DA TITULARIDADE DA UC]",
        "SINOPSE_FATOS_NUCLEO_OBJETO": "pedido fictício de teste do núcleo do objeto da demanda",
        "VALOR_DA_CAUSA": "R$ 10.000,00",
        # Correção pontual de 09/09/2026: exigido por PRELIMINAR_IMPUGNACAO_
        # VALOR_CAUSA (2.6), que este cenário inclui — ver schema.json
        # _nota_valor_total_proveito_economico.
        "VALOR_TOTAL_PROVEITO_ECONOMICO": "R$ 15.000,00 (dado fictício de teste)",
    }
    fatos_processuais = {
        "GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True,
        "AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA": True,
        "UC_TITULARIDADE_TERCEIRO_COMPROVADA": True,
        "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA": True,
        "EXISTE_DISCREPANCIA_VALOR_CAUSA": True,
        "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS": True,
    }
    decisoes = {b["id"]: {"decisao": "INCLUIR"} for b in catalogo["blocks"]
                if b["decision_mode"] in ("estrategista", "humano")}
    return catalogo, dados, decisoes, fatos_processuais


@pytest.mark.docx_real
def test_R_S_texto_fixo_preservado_e_template_lock_ok_com_2_3_a_2_6_incluidos():
    if _pular_sem_template():
        return
    catalogo, dados, decisoes, fatos = _dados_e_decisoes_completos()
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "com-2-3-a-2-6.docx"
        r = gerar_peca_com_blocos(TEMPLATE_2_3_A_2_6, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes, saida, fatos_processuais=fatos)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"  # S
        for bid in ("PRELIMINAR_AUSENCIA_INTERESSE_AGIR", "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
                    "PRELIMINAR_INEPCIA_INICIAL", "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"):
            assert bid in r["blocos_incluidos"], bid
        assert r["zonas"].get("ZONA_PRETENSAO_RESISTIDA") == "EXCLUIR"  # sem conteúdo de zona -> vazia, estado normal

        import zipfile
        with zipfile.ZipFile(saida) as z:
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        # R: texto institucional fixo dos quatro tópicos novos preservado
        assert "AUSÊNCIA DE INTERESSE DE AGIR" in gerado_xml
        assert "ILEGITIMIDADE ATIVA AD CAUSAM" in gerado_xml
        assert "INÉPCIA DA PETIÇÃO INICIAL" in gerado_xml
        assert "IMPUGNAÇÃO AO VALOR DA CAUSA" in gerado_xml


@pytest.mark.docx_real
def test_W_nenhum_sdt_ou_tag_residual():
    if _pular_sem_template():
        return
    catalogo, dados, decisoes, fatos = _dados_e_decisoes_completos()
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "sem-residuo.docx"
        r = gerar_peca_com_blocos(TEMPLATE_2_3_A_2_6, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes, saida, fatos_processuais=fatos)
        assert r["status"] == "OK", r
        import zipfile
        with zipfile.ZipFile(saida) as z:
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        assert "<w:sdt>" not in gerado_xml
        assert "BLOCO:" not in gerado_xml
        assert "SUBBLOCO:" not in gerado_xml
        assert "ZONA:" not in gerado_xml
        assert "{{" not in gerado_xml


@pytest.mark.docx_real
def test_X_e2e_combinacoes_distintas():
    if _pular_sem_template():
        return
    catalogo, dados, decisoes_tudo, fatos_tudo = _dados_e_decisoes_completos()

    # combinação 1: nenhuma das quatro novas preliminares aplica —
    # PRELIMINARES continua existindo se 2.1/2.2 estiverem incluídas.
    decisoes_min = dict(decisoes_tudo)
    fatos_min = dict(fatos_tudo)
    for k in ("AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA", "UC_TITULARIDADE_TERCEIRO_COMPROVADA",
              "EXISTE_DISCREPANCIA_VALOR_CAUSA", "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA",
              "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS"):
        fatos_min[k] = False
    decisoes_min["PRELIMINAR_INEPCIA_INICIAL"] = {"decisao": "EXCLUIR"}
    with tempfile.TemporaryDirectory() as tmp:
        saida1 = Path(tmp) / "combo1.docx"
        r1 = gerar_peca_com_blocos(TEMPLATE_2_3_A_2_6, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_min, saida1, fatos_processuais=fatos_min)
        assert r1["status"] == "OK", r1
        for bid in ("PRELIMINAR_AUSENCIA_INTERESSE_AGIR", "PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO",
                    "PRELIMINAR_INEPCIA_INICIAL", "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"):
            assert bid in r1["blocos_excluidos"], bid
        # PRELIMINARES continua INCLUIR: 2.1 (CDC) ainda está INCLUIR neste cenário
        assert r1["containers_derivados"]["PRELIMINARES"] == "INCLUIR"

        # combinação 2: só 2.3 e 2.6 aplicam (2.4/2.5 excluídas) — badge
        # PRELIMINARES sobrevive mesmo que 2.1/2.2/2.4/2.5 estejam todas
        # EXCLUIR, PROVANDO o fix do container (§ achado real Etapa 5.8-G).
        decisoes_2 = dict(decisoes_min)
        fatos_2 = dict(fatos_min)
        decisoes_2["PRELIMINAR_CDC_INAPLICAVEL"] = {"decisao": "EXCLUIR"}
        # GRATUIDADE_CONCEDIDA precisa ir para False aqui também — senão o
        # badge sobreviveria só por causa dela (state_linked, INCLUIR
        # automático), e o teste deixaria de provar que é 2.3/2.6 quem
        # sustenta PRELIMINARES sozinhos.
        fatos_2["GRATUIDADE_CONCEDIDA"] = False
        fatos_2["AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA"] = True
        fatos_2["EXISTE_DISCREPANCIA_VALOR_CAUSA"] = True
        saida2 = Path(tmp) / "combo2.docx"
        r2 = gerar_peca_com_blocos(TEMPLATE_2_3_A_2_6, SCHEMA_REAL, CATALOGO_REAL,
                                    dados, decisoes_2, saida2, fatos_processuais=fatos_2)
        assert r2["status"] == "OK", r2
        assert r2["containers_derivados"]["PRELIMINARES"] == "INCLUIR", (
            "regressão do achado real: badge PRELIMINARES precisa sobreviver quando só "
            "2.3/2.6 aplicam, mesmo com 2.1/2.2/2.4/2.5 todas EXCLUIR")
        assert "PRELIMINAR_AUSENCIA_INTERESSE_AGIR" in r2["blocos_incluidos"]
        assert "PRELIMINAR_IMPUGNACAO_VALOR_CAUSA" in r2["blocos_incluidos"]
        assert "PRELIMINAR_CDC_INAPLICAVEL" in r2["blocos_excluidos"]


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
