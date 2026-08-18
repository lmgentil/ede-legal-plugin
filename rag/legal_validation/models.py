#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
models.py — modelo canônico de fonte jurídica (Fase 5, SPEC-0001 §9).

Um dict com chaves fixas, construído só por `fonte_juridica()` — sem
dataclass/schema library própria (pydantic etc.): não há necessidade real
de validação de tipos além dos enums abaixo, e um dict serializa direto
para JSON sem passo extra (YAGNI).

Os três enums abaixo são eixos INDEPENDENTES (SPEC-0001 §21): um resultado
pode ter `authority_level = OFICIAL`, `validation_status = VALIDADA` e
ainda assim `vigencia = NAO_VERIFICADA` — recuperar/validar a existência
textual de um dispositivo não é o mesmo que confirmar que ele está em
vigor hoje.
"""

# SPEC-0001 §14 — estados de validação de uma CITAÇÃO (existência/
# correspondência textual do dispositivo apontado, não sua vigência).
VALIDATION_STATUS = ("VALIDADA", "PARCIALMENTE_VALIDADA", "NAO_VALIDADA",
                      "AMBIGUA", "FONTE_INSUFICIENTE")

# SPEC-0001 §11 — estado temporal (vigência) de uma NORMA.
VIGENCIA_STATUS = ("VIGENTE", "ALTERADA", "REVOGADA", "SUSPENSA",
                    "HISTORICA", "NAO_VERIFICADA")

# SPEC-0001 §10 — autoridade da FONTE (de onde veio o texto), não da norma.
AUTHORITY_LEVELS = ("OFICIAL", "INSTITUCIONAL", "SECUNDARIA_CONFIAVEL",
                     "NAO_VERIFICADA")


def fonte_juridica(*, source_id, tipo, diploma=None, norma=None, artigo=None,
                    paragrafo=None, inciso=None, alinea=None, texto=None,
                    fonte=None, url=None, orgao=None,
                    vigencia="NAO_VERIFICADA", data_verificacao=None,
                    authority_level="NAO_VERIFICADA",
                    validation_status="NAO_VALIDADA",
                    score_semantico=None, score_lexical=None,
                    score_final=None) -> dict:
    """Constrói o modelo canônico. Levanta ValueError se um dos três enums
    receber um valor fora da lista — falha explícita (CLAUDE.md §17)
    em vez de deixar um estado inventado silenciosamente entrar no
    pipeline."""
    if vigencia not in VIGENCIA_STATUS:
        raise ValueError(f"vigencia inválida: {vigencia!r}")
    if authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"authority_level inválido: {authority_level!r}")
    if validation_status not in VALIDATION_STATUS:
        raise ValueError(f"validation_status inválido: {validation_status!r}")
    return {
        "source_id": source_id,
        "tipo": tipo,
        "orgao": orgao,
        "diploma": diploma,
        "norma": norma,
        "artigo": artigo,
        "paragrafo": paragrafo,
        "inciso": inciso,
        "alinea": alinea,
        "texto": texto,
        "fonte": fonte,
        "url": url,
        "vigencia": vigencia,
        "data_verificacao": data_verificacao,
        "authority_level": authority_level,
        "validation_status": validation_status,
        "retrieval": {
            "score_semantico": score_semantico,
            "score_lexical": score_lexical,
            "score_final": score_final,
        },
    }
