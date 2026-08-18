#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
source_authority.py — REQ-025 (Fase 5): classificação determinística de
autoridade das fontes, por corpus.

Autoridade da fonte != vigência da norma (SPEC-0001 §10): este módulo só
responde "o quão oficial é a origem deste texto" (é o compilado do
Planalto? é um enunciado de súmula? é um blog?) — nunca "está em vigor",
isso é `temporal_status.py`. Não usar domínio/URL como prova de vigência.
"""
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .models import AUTHORITY_LEVELS

BASE = Path(__file__).resolve().parent.parent  # rag/
CONFIG_PATH = BASE / "config.yaml"

# Todos os 6 corpora legislativos atuais são compilados oficiais (Planalto
# para as leis federais; ANEEL para a REN 1.000) — OFICIAL. Corpus fora
# deste mapa (ex.: jurisprudência, ainda não indexada — PEND-002) cai em
# NAO_VERIFICADA por padrão: fail closed, nunca um nível de confiança
# inventado para corpus desconhecido.
_DEFAULT_AUTORIDADE_POR_CORPUS = {
    "CPC": "OFICIAL",
    "CC": "OFICIAL",
    "CDC": "OFICIAL",
    "L8987": "OFICIAL",
    "L9427": "OFICIAL",
    "REN1000": "OFICIAL",
}


def _carregar_mapa() -> dict:
    """REQ-044: configurável via rag/config.yaml (chave
    `validacao_juridica.autoridade_por_corpus`). Sem pyyaml, sem o arquivo,
    ou sem a chave, usa o mapa default acima — mesmo estilo de degradação
    de rag/search_hybrid.py."""
    if yaml is None:
        return dict(_DEFAULT_AUTORIDADE_POR_CORPUS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        mapa = cfg.get("validacao_juridica", {}).get("autoridade_por_corpus")
        return dict(mapa) if mapa else dict(_DEFAULT_AUTORIDADE_POR_CORPUS)
    except Exception:
        return dict(_DEFAULT_AUTORIDADE_POR_CORPUS)


_MAPA = _carregar_mapa()


def classificar_autoridade(corpus: str) -> str:
    """Determinística: o mesmo corpus sempre retorna o mesmo nível.
    Corpus fora do mapa -> NAO_VERIFICADA (fail closed, nunca inventado)."""
    nivel = _MAPA.get(corpus, "NAO_VERIFICADA")
    assert nivel in AUTHORITY_LEVELS, f"nível de autoridade inválido em config: {nivel!r}"
    return nivel
