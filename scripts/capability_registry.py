#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capability_registry.py — registro DETERMINÍSTICO server-side de
capacidades jurídicas do EDE (Gate 6.6-C, ADR-0018).

Nunca um banco de dados, nunca administração dinâmica: uma constante
Python, declarada aqui, publicada só por leitura. Adicionar uma
capacidade futura (Recurso Inominado, Contrarrazões, Embargos de
Declaração, outros modelos de Contestação) é acrescentar uma entrada
neste dicionário — nunca alterar `finalizar_peca.py`/`mcp_server/
server.py` para "saber" sobre o assunto jurídico de uma capacidade nova
(ADR-0018, "camada de entrega nunca conhece o domínio jurídico").

INV-GATE-CONTESTACAO (CLAUDE.md §27) permanece em vigor: só
`contestacao.irregularidade_consumo` está `READY`. O registro é
CONTRATO (a forma que uma capacidade futura vai assumir), não convite a
implementar peças ainda não autorizadas — nenhuma outra entrada existe
aqui, nem como rascunho `NOT_READY`.

Nunca exposto ao cliente por este módulo: bucket, objeto GCS, geração,
SHA do Modelo Oficial, path local. `official_model_required=True` só
informa que a capacidade depende do mecanismo de aquisição já existente
(ADR-0009/ADR-0017) — a resolução em si continua em
`scripts/legal_readiness.py`, nunca duplicada aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StatusCapacidade = Literal["READY", "NOT_READY", "DEPRECATED"]


@dataclass(frozen=True)
class Capacidade:
    """Uma capacidade jurídica publicável — `<familia>.<modelo>`.

    `required_scope` é redundante com `mcp_server/scope_policy.py` de
    propósito: a autorização OAuth real é decidida SÓ pelo middleware de
    escopo (fonte única, ADR-0016); este campo é só o contrato que a
    capacidade DECLARA precisar, para que o registro seja autocontido e
    auditável sem abrir o servidor MCP."""

    capability_id: str
    family: str
    display_name: str
    schema_version: str
    status: StatusCapacidade
    renderer_id: str
    official_model_required: bool
    production_final_supported: bool
    required_scope: str


ESCOPO_LEGAL = "ede:legal"

REGISTRO: dict[str, Capacidade] = {
    "contestacao.irregularidade_consumo": Capacidade(
        capability_id="contestacao.irregularidade_consumo",
        family="contestacao",
        display_name="Contestação — Irregularidade de Consumo (EDE/Coelba)",
        schema_version="1.0.0",
        status="READY",
        renderer_id="docx_block_engine.gerar_peca_com_blocos",
        official_model_required=True,
        production_final_supported=True,
        required_scope=ESCOPO_LEGAL,
    ),
}
"""Capacidade única, hoje. Nenhuma outra família/modelo é declarada aqui
sem liberação expressa do usuário (INV-GATE-CONTESTACAO) — não é uma
lista incompleta a preencher, é o estado real e integral do produto."""


def obter_capacidade(capability_id: str) -> Capacidade | None:
    """`None` quando a capacidade não existe — o chamador decide o erro
    público (`CAPABILITY_NOT_FOUND`); este módulo nunca decide isso
    sozinho, só responde ao contrato de dados."""
    return REGISTRO.get(capability_id)


def capacidades_prontas() -> tuple[Capacidade, ...]:
    """Só as `READY` — usado por uma futura tool de descoberta
    (`ede_capabilities`, ADR-0018 §29; não implementada neste gate)."""
    return tuple(c for c in REGISTRO.values() if c.status == "READY")
