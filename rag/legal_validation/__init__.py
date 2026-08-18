#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag/legal_validation/ — Fase 5 (SPEC-0001 §5-30): transforma o que o RAG
recupera em conhecimento juridicamente verificável e rastreável.

Camada POSTERIOR a rag/search_hybrid.py, não acoplada a ele (§22:
RETRIEVAL != LEGAL VALIDATION):
  search_hybrid()  ->  resultados recuperados  ->  legal_validation  ->
  resultados enriquecidos / citação validada

Regra central (§6): recuperar um trecho semanticamente relevante NÃO
significa que ele esteja automaticamente autorizado para citação
jurídica. RECUPERADO != VALIDADO.

API pública:
  validar_citacao(texto)         -> dict   (REQ-027/028, citation_validator.py)
  enriquecer_resultados(results) -> list   (REQ-024/025/026, citation_validator.py)
  fonte_juridica(...)            -> dict   (modelo canônico, §9, models.py)
  classificar_autoridade(corpus) -> str    (REQ-025, source_authority.py)
  vigencia_de(corpus, artigo)    -> str    (REQ-026, temporal_status.py)
"""
from .citation_parser import parse_citacao
from .citation_validator import enriquecer_resultados, validar_citacao
from .models import AUTHORITY_LEVELS, VALIDATION_STATUS, VIGENCIA_STATUS, fonte_juridica
from .provenance import proveniencia
from .source_authority import classificar_autoridade
from .temporal_status import vigencia_de

__all__ = [
    "validar_citacao", "enriquecer_resultados", "parse_citacao",
    "fonte_juridica", "classificar_autoridade", "vigencia_de", "proveniencia",
    "VALIDATION_STATUS", "VIGENCIA_STATUS", "AUTHORITY_LEVELS",
]
