#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_blocos_contestacao.py — regressão do catálogo de blocos condicionais
(Etapa 5, INV-COMPOSICAO-BLOCOS — SPEC-0001 §5).

Mesmo padrão de tests/test_template_engine.py: sem framework de teste,
asserts + `if __name__ == "__main__"`.

Cobre:
  1. o catálogo real (templates/contestacao/blocos.json) carrega e passa
     na validação estrutural — sempre roda, é o único artefato que
     precisa existir publicamente (não depende do .docx institucional);
  2. validação estrutural pura (validar_catalogo) — casos negativos A-H:
     parent/child inexistente, ciclo, tipo/decision_mode incompatível,
     leaf com children, dependency malformada, ids/tags duplicados;
  3. validação/resolução de decisões (validar_e_resolver_decisoes) —
     decisão ausente, INDETERMINADO, estado inválido não normalizado,
     decisão manual em bloco derived/linked, resolução correta de
     CONTAINER_DERIVED (4 combinações) e 'linked'.

Uso:
  python tests/test_blocos_contestacao.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    validar_catalogo,
    validar_e_resolver_decisoes,
)

CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


def _base_bloco(**over):
    b = {
        "id": "X", "tag": "BLOCO:X", "tipo": "CONDICIONAL_PADRAO",
        "parent": None, "children": [], "decision_mode": "estrategista",
        "placeholders": [], "dependencies": [], "cardinality": "ONE",
    }
    b.update(over)
    return b


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except ComposicaoAbortada as e:
        return e


# --------------------------------------------------------------- catálogo real
def test_catalogo_real_carrega_e_valida():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    validar_catalogo(catalogo)  # não deve levantar
    ids = {b["id"] for b in catalogo["blocks"]}
    esperado = {
        "PRELIMINARES", "PRELIMINAR_CDC_INAPLICAVEL", "PRELIMINAR_REVOGACAO_GRATUIDADE",
        "DEVER_LEGAL_FISCALIZACAO", "DESNECESSIDADE_AVISO_PREVIO", "CALCULOS_RECUPERACAO_CONSUMO",
        "EVOLUCAO_CONSUMO", "LICITUDE_CORTE_SUSPENSAO", "NEXO_CAUSAL_INDEMONSTRADO",
        "DESCABIMENTO_DANO_MORAL", "RECONVENCAO", "INLINE_COM_RECONVENCAO",
    }
    assert ids == esperado, ids


def test_catalogo_real_preliminares_e_container_derived():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["PRELIMINARES"]["tipo"] == "CONTAINER_DERIVED"
    assert por_id["PRELIMINARES"]["derived_rule"] == "ANY_CHILD_INCLUDED"
    assert set(por_id["PRELIMINARES"]["children"]) == {
        "PRELIMINAR_CDC_INAPLICAVEL", "PRELIMINAR_REVOGACAO_GRATUIDADE"}


def test_catalogo_real_evolucao_consumo_e_hibrido_com_placeholder():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["EVOLUCAO_CONSUMO"]["tipo"] == "CONDICIONAL_HIBRIDO"
    assert "ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA" in por_id["EVOLUCAO_CONSUMO"]["placeholders"]


def test_catalogo_real_reconvencao_e_inline_vinculados():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["RECONVENCAO"]["tipo"] == "CONDICIONAL_HIBRIDO"
    assert "VALOR_FRA" in por_id["RECONVENCAO"]["placeholders"]
    assert por_id["INLINE_COM_RECONVENCAO"]["decision_mode"] == "linked"
    assert por_id["INLINE_COM_RECONVENCAO"]["linked_to"] == "RECONVENCAO"
    assert por_id["INLINE_COM_RECONVENCAO"]["cardinality"] == "MC_PAIR"


# --------------------------------------------------------------- Etapa 5.2
def test_catalogo_real_reconvencao_e_decision_mode_humano():
    # INV-RECONVENCAO-AUTORIZACAO-EXPRESSA: não pode mais ser decidida pela
    # análise estratégica sozinha.
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["RECONVENCAO"]["decision_mode"] == "humano"


def test_catalogo_real_gratuidade_e_state_linked():
    # INV-GRATUIDADE-LINKED (correção pontual): vínculo determinístico
    # estado processual -> bloco, NÃO gate + decisão estratégica.
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["PRELIMINAR_REVOGACAO_GRATUIDADE"]["decision_mode"] == "state_linked"
    assert por_id["PRELIMINAR_REVOGACAO_GRATUIDADE"]["linked_fact"] == "GRATUIDADE_CONCEDIDA"
    assert "requires_fact" not in por_id["PRELIMINAR_REVOGACAO_GRATUIDADE"]


def test_catalogo_real_corte_tem_requires_fact():
    # INV-CORTE-EFETIVO: continua GATE + decisão estratégica (preservado
    # intocado pela correção pontual — só a gratuidade mudou de mecanismo).
    catalogo = carregar_catalogo(CATALOGO_REAL)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    assert por_id["LICITUDE_CORTE_SUSPENSAO"]["decision_mode"] == "estrategista"
    assert por_id["LICITUDE_CORTE_SUSPENSAO"]["requires_fact"]["key"] == "CORTE_EFETIVO"
    # os demais blocos condicionais não ganharam gate/vínculo algum por acidente
    sem_gate = {"PRELIMINAR_CDC_INAPLICAVEL", "DEVER_LEGAL_FISCALIZACAO",
                "DESNECESSIDADE_AVISO_PREVIO", "CALCULOS_RECUPERACAO_CONSUMO",
                "EVOLUCAO_CONSUMO", "NEXO_CAUSAL_INDEMONSTRADO", "DESCABIMENTO_DANO_MORAL"}
    for bid in sem_gate:
        assert "requires_fact" not in por_id[bid], bid
        assert por_id[bid]["decision_mode"] not in ("state_linked", "linked"), bid


def test_decisao_manual_em_bloco_humano_e_aceita_como_estrategista():
    catalogo = {"blocks": [_base_bloco(id="H", tag="BLOCO:H", decision_mode="humano")]}
    estados = validar_e_resolver_decisoes(catalogo, {"H": {"decisao": "INCLUIR"}})
    assert estados == {"H": "INCLUIR"}


def test_bloco_humano_sem_decisao_aborta_decisao_ausente():
    catalogo = {"blocks": [_base_bloco(id="H", tag="BLOCO:H", decision_mode="humano")]}
    e = _abortou(validar_e_resolver_decisoes, catalogo, {})
    assert e and e.stage == "decisao_ausente"


def test_bloco_humano_indeterminado_aborta():
    # Cenário A/CENÁRIO 6 do prompt: reconvenção sem resposta -> aborta.
    catalogo = {"blocks": [_base_bloco(id="H", tag="BLOCO:H", decision_mode="humano")]}
    e = _abortou(validar_e_resolver_decisoes, catalogo, {"H": {"decisao": "INDETERMINADO"}})
    assert e and e.stage == "decisao_indeterminada"


CATALOGO_COM_GATE = {"blocks": [
    _base_bloco(id="GATED", tag="BLOCO:GATED",
                requires_fact={"key": "ESTADO_X"}),
]}


def test_requires_fact_bloqueia_incluir_sem_fato():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "INCLUIR"}})
    assert e and e.stage == "gate_fatico_nao_satisfeito"


def test_requires_fact_bloqueia_incluir_com_fato_falso():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "INCLUIR"}}, {"ESTADO_X": False})
    assert e and e.stage == "gate_fatico_nao_satisfeito"


def test_requires_fact_bloqueia_incluir_com_fato_ausente_do_dict():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "INCLUIR"}}, {"OUTRO_ESTADO": True})
    assert e and e.stage == "gate_fatico_nao_satisfeito"


def test_requires_fact_permite_incluir_com_fato_verdadeiro():
    estados = validar_e_resolver_decisoes(CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "INCLUIR"}}, {"ESTADO_X": True})
    assert estados["GATED"] == "INCLUIR"


def test_requires_fact_aceita_forma_com_proveniencia():
    estados = validar_e_resolver_decisoes(CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "INCLUIR"}},
                  {"ESTADO_X": {"valor": True, "fonte_documento": "decisao.pdf"}})
    assert estados["GATED"] == "INCLUIR"


def test_requires_fact_nao_bloqueia_excluir():
    # o gate só restringe INCLUIR — EXCLUIR nunca precisa de suporte fático.
    estados = validar_e_resolver_decisoes(CATALOGO_COM_GATE,
                  {"GATED": {"decisao": "EXCLUIR"}})
    assert estados["GATED"] == "EXCLUIR"


def test_requires_fact_malformado_e_catalogo_invalido():
    catalogo = {"blocks": [_base_bloco(id="G", tag="BLOCO:G", requires_fact={})]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "requires_fact" in e.motivo


def test_requires_fact_em_bloco_derived_e_catalogo_invalido():
    catalogo = {"blocks": [
        _base_bloco(id="PAI", tag="BLOCO:PAI", tipo="CONTAINER_DERIVED",
                    decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
                    children=["FILHO"], requires_fact={"key": "X"}),
        _base_bloco(id="FILHO", tag="BLOCO:FILHO", parent="PAI"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "requires_fact" in e.motivo


# ------------------------------------------ Etapa 5.2 (correção): state_linked
CATALOGO_STATE_LINKED = {"blocks": [
    _base_bloco(id="GRAT", tag="BLOCO:GRAT", decision_mode="state_linked",
                linked_fact="GRATUIDADE_CONCEDIDA"),
]}


def test_state_linked_sem_linked_fact_e_catalogo_invalido():
    catalogo = {"blocks": [_base_bloco(id="G", tag="BLOCO:G", decision_mode="state_linked")]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "linked_fact" in e.motivo


def test_linked_fact_fora_de_state_linked_e_catalogo_invalido():
    catalogo = {"blocks": [_base_bloco(id="G", tag="BLOCO:G", linked_fact="X")]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "linked_fact" in e.motivo


def test_state_linked_A_fato_verdadeiro_inclui_sem_decisao_do_estrategista():
    estados = validar_e_resolver_decisoes(CATALOGO_STATE_LINKED, {},
                                           {"GRATUIDADE_CONCEDIDA": True})
    assert estados == {"GRAT": "INCLUIR"}


def test_state_linked_B_fato_falso_exclui_sem_decisao_do_estrategista():
    estados = validar_e_resolver_decisoes(CATALOGO_STATE_LINKED, {},
                                           {"GRATUIDADE_CONCEDIDA": False})
    assert estados == {"GRAT": "EXCLUIR"}


def test_state_linked_C_mero_pedido_sem_concessao_exclui():
    # "mero pedido" não é modelado como um valor especial — é
    # simplesmente ausência de GRATUIDADE_CONCEDIDA=true (fail closed).
    estados = validar_e_resolver_decisoes(CATALOGO_STATE_LINKED, {}, {})
    assert estados == {"GRAT": "EXCLUIR"}


def test_state_linked_D_ausencia_total_do_dict_tambem_exclui():
    estados = validar_e_resolver_decisoes(CATALOGO_STATE_LINKED, {}, None)
    assert estados == {"GRAT": "EXCLUIR"}


def test_state_linked_E_indeterminado_aborta():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_STATE_LINKED, {},
                  {"GRATUIDADE_CONCEDIDA": "INDETERMINADO"})
    assert e and e.stage == "decisao_indeterminada"


def test_state_linked_F_decisao_excluir_do_estrategista_e_rejeitada_mesmo_com_fato_verdadeiro():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_STATE_LINKED,
                  {"GRAT": {"decisao": "EXCLUIR"}}, {"GRATUIDADE_CONCEDIDA": True})
    assert e and e.stage == "decisao_invalida" and "não aceita decisão manual" in e.motivo


def test_state_linked_G_decisao_incluir_do_estrategista_e_rejeitada_mesmo_com_fato_falso():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_STATE_LINKED,
                  {"GRAT": {"decisao": "INCLUIR"}}, {"GRATUIDADE_CONCEDIDA": False})
    assert e and e.stage == "decisao_invalida" and "não aceita decisão manual" in e.motivo


def test_state_linked_valor_nao_reconhecido_aborta_estado_processual_invalido():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_STATE_LINKED, {},
                  {"GRATUIDADE_CONCEDIDA": "talvez"})
    assert e and e.stage == "estado_processual_invalido"


def test_state_linked_como_filho_de_container_derived_resolve_antes():
    catalogo = {"blocks": [
        _base_bloco(id="OUTRO_FILHO", tag="BLOCO:OF", parent="PAI"),
        _base_bloco(id="GRAT", tag="BLOCO:GRAT", parent="PAI",
                    decision_mode="state_linked", linked_fact="GRATUIDADE_CONCEDIDA"),
        _base_bloco(id="PAI", tag="BLOCO:PAI", tipo="CONTAINER_DERIVED",
                    decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
                    children=["OUTRO_FILHO", "GRAT"]),
    ]}
    estados = validar_e_resolver_decisoes(catalogo, {"OUTRO_FILHO": {"decisao": "EXCLUIR"}},
                                           {"GRATUIDADE_CONCEDIDA": True})
    assert estados["GRAT"] == "INCLUIR"
    assert estados["PAI"] == "INCLUIR"  # ANY_CHILD_INCLUDED via GRAT


# --------------------------------------------------------------- validação estrutural (A-H)
def test_A_parent_inexistente():
    catalogo = {"blocks": [_base_bloco(id="A", parent="NAO_EXISTE")]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "parent inexistente" in e.motivo


def test_B_child_inexistente():
    catalogo = {"blocks": [_base_bloco(
        id="PAI", tag="BLOCO:PAI", tipo="CONTAINER_DERIVED",
        decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
        children=["FILHO_FANTASMA"])]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "child inexistente" in e.motivo


def test_C_ciclo_A_para_B_para_A():
    catalogo = {"blocks": [
        _base_bloco(id="A", tag="BLOCO:A", tipo="CONTAINER_DERIVED",
                    decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
                    children=["B"], parent="B"),
        _base_bloco(id="B", tag="BLOCO:B", tipo="CONTAINER_DERIVED",
                    decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
                    children=["A"], parent="A"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "ciclo" in e.motivo


def test_D_container_derived_declarado_incompativel():
    # CONTAINER_DERIVED com decision_mode='estrategista' (deveria ser 'derived')
    catalogo = {"blocks": [
        _base_bloco(id="PAI", tag="BLOCO:PAI", tipo="CONTAINER_DERIVED",
                    decision_mode="estrategista", children=["FILHO"]),
        _base_bloco(id="FILHO", tag="BLOCO:FILHO", parent="PAI"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "CONTAINER_DERIVED" in e.motivo


def test_E_leaf_declarando_children_indevidamente():
    catalogo = {"blocks": [
        _base_bloco(id="FOLHA", tag="BLOCO:FOLHA", tipo="CONDICIONAL_PADRAO",
                    children=["OUTRO"]),
        _base_bloco(id="OUTRO", tag="BLOCO:OUTRO", parent="FOLHA"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "apenas CONTAINER_DERIVED" in e.motivo


def test_F_ids_duplicados():
    catalogo = {"blocks": [
        _base_bloco(id="DUP", tag="BLOCO:UM"),
        _base_bloco(id="DUP", tag="BLOCO:DOIS"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "id duplicado" in e.motivo


def test_G_tags_duplicadas():
    catalogo = {"blocks": [
        _base_bloco(id="UM", tag="BLOCO:DUP"),
        _base_bloco(id="DOIS", tag="BLOCO:DUP"),
    ]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "tag duplicada" in e.motivo


def test_H_dependency_placeholder_inexistente():
    catalogo = {"blocks": [_base_bloco(
        id="HIB", tag="BLOCO:HIB", tipo="CONDICIONAL_HIBRIDO",
        placeholders=["VALOR_FRA"],
        dependencies=[{"placeholder": "PLACEHOLDER_NAO_DECLARADO", "quando": "INCLUIR", "regra": "obrigatorio_preenchido"}],
    )]}
    e = _abortou(validar_catalogo, catalogo)
    assert e and e.stage == "catalogo_invalido" and "não declarado" in e.motivo


# --------------------------------------------------------------- decisões
CATALOGO_SIMPLES = {"blocks": [
    _base_bloco(id="FOLHA_A", tag="BLOCO:A"),
    _base_bloco(id="FOLHA_B", tag="BLOCO:B"),
    _base_bloco(id="CONTAINER", tag="BLOCO:C", tipo="CONTAINER_DERIVED",
                decision_mode="derived", derived_rule="ANY_CHILD_INCLUDED",
                children=["FOLHA_A", "FOLHA_B"]),
]}
# corrige parent das folhas para apontar para CONTAINER (contrato bidirecional)
for _b in CATALOGO_SIMPLES["blocks"]:
    if _b["id"] in ("FOLHA_A", "FOLHA_B"):
        _b["parent"] = "CONTAINER"


def test_decisao_ausente():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_SIMPLES,
                  {"FOLHA_A": {"decisao": "INCLUIR"}})
    assert e and e.stage == "decisao_ausente"


def test_decisao_indeterminada_aborta_mesmo_com_irmao_decidido():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_SIMPLES,
                  {"FOLHA_A": {"decisao": "INCLUIR"}, "FOLHA_B": {"decisao": "INDETERMINADO"}})
    assert e and e.stage == "decisao_indeterminada"


def test_estado_invalido_nao_normalizado():
    for estado_ruim in (True, 1, "SIM", "sim", "incluir"):
        e = _abortou(validar_e_resolver_decisoes, CATALOGO_SIMPLES,
                      {"FOLHA_A": {"decisao": estado_ruim}, "FOLHA_B": {"decisao": "EXCLUIR"}})
        assert e and e.stage == "decisao_invalida", f"deveria rejeitar {estado_ruim!r}"


def test_decisao_manual_em_bloco_derived_e_erro():
    e = _abortou(validar_e_resolver_decisoes, CATALOGO_SIMPLES,
                  {"FOLHA_A": {"decisao": "INCLUIR"}, "FOLHA_B": {"decisao": "EXCLUIR"},
                   "CONTAINER": {"decisao": "INCLUIR"}})
    assert e and e.stage == "decisao_invalida" and "não aceita decisão manual" in e.motivo


def test_container_derived_any_child_included_4_combinacoes():
    casos = [
        ("INCLUIR", "INCLUIR", "INCLUIR"),
        ("INCLUIR", "EXCLUIR", "INCLUIR"),
        ("EXCLUIR", "INCLUIR", "INCLUIR"),
        ("EXCLUIR", "EXCLUIR", "EXCLUIR"),
    ]
    for a, b, esperado_container in casos:
        estados = validar_e_resolver_decisoes(CATALOGO_SIMPLES, {
            "FOLHA_A": {"decisao": a}, "FOLHA_B": {"decisao": b}})
        assert estados["CONTAINER"] == esperado_container, (a, b, estados)


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
