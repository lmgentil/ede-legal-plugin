#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
temporal_status.py — REQ-026 (Fase 5): estado de vigência.

Não há, na infraestrutura atual, nenhuma fonte de verificação de vigência
(nenhum serviço consultado, nenhuma data de checagem registrada por
dispositivo — os corpora são compilados do Planalto/ANEEL baixados numa
data, não uma assinatura "vigente em X"). SPEC-0001 §11 e CLAUDE.md §17
(Fail Closed) exigem que, nessa condição, o estado seja NAO_VERIFICADA —
nunca VIGENTE por presunção de que "o texto existe no corpus".

Este módulo existe para tornar essa decisão explícita e testável (um único
ponto no código que decide isso), não para escondê-la dentro do validador
de citação.
"""
from .models import VIGENCIA_STATUS


def vigencia_de(corpus: str, artigo: int = None) -> str:
    """Hoje sempre NAO_VERIFICADA, para qualquer corpus/artigo: nenhum
    dado de vigência foi verificado. A assinatura já aceita corpus/artigo
    para que, quando uma fonte de verificação real existir (ex.: consulta
    a um serviço de legislação consolidada), a mudança fique isolada
    aqui — nenhum outro módulo precisa mudar."""
    resultado = "NAO_VERIFICADA"
    assert resultado in VIGENCIA_STATUS
    return resultado
