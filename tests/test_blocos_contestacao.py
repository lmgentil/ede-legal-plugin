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
