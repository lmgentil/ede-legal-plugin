#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dados_derivados.py — campos da Contestação que o próprio sistema deriva,
nunca o host nem o advogado (ADR-0021, SPEC-0001 §64).

Core puro e determinístico (ADR-0015): relógio, calendário e aritmética.
Nada de LLM, nada de rede — a consulta DataJud continua em
`datajud_client.py`, o cálculo de prazo em `calcular_tempestividade.py`
e a soma do proveito econômico em `proveito_economico.py`.

`LOCAL_DATA`: "Salvador, <data corrente>" no fuso IANA `America/Bahia`
(nunca offset fixo). O local é sempre Salvador, qualquer que seja a
comarca (CLAUDE.md §14, Etapa 5.3); o ponto final vem do texto fixo do
modelo ("{{LOCAL_DATA}}.").
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_INSTITUCIONAL = ZoneInfo("America/Bahia")
LOCAL_INSTITUCIONAL = "Salvador"

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")


def hoje_institucional(agora: datetime | None = None) -> date:
    """Data corrente em `America/Bahia`. `agora` sem fuso é recusado —
    uma data "ingênua" não diz em que dia se está."""
    if agora is None:
        agora = datetime.now(FUSO_INSTITUCIONAL)
    if agora.tzinfo is None:
        raise ValueError("agora precisa ter fuso horário (datetime aware)")
    return agora.astimezone(FUSO_INSTITUCIONAL).date()


def data_por_extenso(d: date) -> str:
    dia = "1º" if d.day == 1 else str(d.day)
    return f"{dia} de {MESES[d.month - 1]} de {d.year}"


def gerar_local_data(agora: datetime | None = None) -> str:
    return f"{LOCAL_INSTITUCIONAL}, {data_por_extenso(hoje_institucional(agora))}"
