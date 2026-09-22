#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_capability_registry.py — regressão do registro determinístico de
capacidades jurídicas (Gate 6.6-C, ADR-0018).
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import capability_registry as cr  # noqa: E402


def test_obter_capacidade_conhecida():
    cap = cr.obter_capacidade("contestacao.irregularidade_consumo")
    assert cap is not None
    assert cap.capability_id == "contestacao.irregularidade_consumo"
    assert cap.status == "READY"
    assert cap.required_scope == cr.ESCOPO_LEGAL == "ede:legal"


def test_obter_capacidade_desconhecida_devolve_none():
    assert cr.obter_capacidade("recurso.inominado") is None
    assert cr.obter_capacidade("") is None
    assert cr.obter_capacidade("contestacao.irregularidade_consumo ") is None


def test_capacidades_prontas_contem_so_a_unica_ready():
    prontas = cr.capacidades_prontas()
    assert len(prontas) == 1
    assert prontas[0].capability_id == "contestacao.irregularidade_consumo"


def test_registro_tem_exatamente_uma_entrada_inv_gate_contestacao():
    """INV-GATE-CONTESTACAO (CLAUDE.md §27): nenhuma peça além da
    Contestação está liberada para desenvolvimento — o registro nunca
    deve conter uma segunda entrada, nem `NOT_READY`, como rascunho."""
    assert len(cr.REGISTRO) == 1


def test_capacidade_e_dataclass_congelada():
    import dataclasses
    cap = cr.obter_capacidade("contestacao.irregularidade_consumo")
    assert dataclasses.is_dataclass(cap)
    try:
        cap.status = "NOT_READY"
        assert False, "Capacidade deveria ser imutável (frozen=True)"
    except dataclasses.FrozenInstanceError:
        pass


def test_capacidade_nunca_expoe_infraestrutura():
    """Nenhum campo da dataclass carrega bucket/objeto/geração/SHA/path
    do Modelo Oficial — a aquisição em si continua só em
    scripts/legal_readiness.py (ADR-0018, `capability_registry.py`
    docstring)."""
    campos = {f.name for f in __import__("dataclasses").fields(cr.Capacidade)}
    for termo in ("bucket", "gcs", "sha", "path", "hash"):
        assert not any(termo in c.lower() for c in campos), campos
