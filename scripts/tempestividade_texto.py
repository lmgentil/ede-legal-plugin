#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tempestividade_texto.py — redação jurídica curta de `TEMPESTIVIDADE_CASO`
a partir do resultado determinístico de `calcular_tempestividade()`.

Extraído de `gerar_contestacao.py` sem mudança de texto (ADR-0021): o
fluxo local da Skill e o finalizador MCP usam a mesma redação. Cálculo e
redação continuam separados (Etapa 5.5): a memória de cálculo nunca
entra na peça.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "calendario-forense-tjba-2026" / "scripts"))

from calcular_tempestividade import INTEMPESTIVO, TEMPESTIVO  # noqa: E402


def _data_br(data_iso: str) -> str:
    """"YYYY-MM-DD" -> "DD/MM/YYYY" (nunca ISO na redação final)."""
    from datetime import datetime as _dt
    return _dt.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def _redigir_tempestividade_natural(r) -> str:
    """Transforma o resultado determinístico de calcular_tempestividade()
    em prosa jurídica curta e institucional (Etapa 5.5 §3) — nunca
    algoritmo/cálculo interno/input/advogado/sistema/JSON/calendário como
    ferramenta/proveniência verbalizados na peça.

    r.status já não pode ser PENDENTE aqui (_etapa_tempestividade aborta
    antes de chamar esta função) — só resta TEMPESTIVO/INTEMPESTIVO, e o
    resultado precisa declarar explicitamente qual dos dois é o caso
    (nunca uma frase ambígua que sirva para ambos — regressão real do
    formato robótico antigo, que ao menos prefixava "INTEMPESTIVO:")."""
    marco = _data_br(r.termo_inicial)
    termo_final = _data_br(r.termo_final)
    if r.status == TEMPESTIVO:
        return (
            f"A presente Contestação é tempestiva. Considerado o marco "
            f"processual ocorrido em {marco} e a contagem do prazo de 15 "
            f"(quinze) dias úteis, nos termos do art. 335 do Código de "
            f"Processo Civil, o prazo defensivo encerra-se em "
            f"{termo_final}, razão pela qual a defesa é apresentada "
            f"tempestivamente.")
    if r.status == INTEMPESTIVO:
        return (
            f"Considerado o marco processual ocorrido em {marco} e a "
            f"contagem do prazo de 15 (quinze) dias úteis, nos termos do "
            f"art. 335 do Código de Processo Civil, o prazo defensivo "
            f"encerrou-se em {termo_final}, de modo que a presente "
            f"Contestação é intempestiva.")
    raise ValueError(f"status de tempestividade não reconhecido: {r.status!r} — "
                      f"fail-closed, nunca gerar redação para um status "
                      f"desconhecido/ambíguo.")
