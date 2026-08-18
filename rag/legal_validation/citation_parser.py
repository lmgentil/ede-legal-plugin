#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citation_parser.py — Fase 5: parseia uma referência jurídica em texto livre
para (corpus/diploma, artigo, parágrafo, inciso, alínea) estruturados.

Reaproveita rag/search_hybrid.py para detecção de artigo(s) e diploma
(`detect_articles`, que já usa ART_BLOCK_RE + CORPUS_HINTS, calibrados e
testados desde a Fase 4) em vez de duplicar essa lógica — só acrescenta o
que search_hybrid.py não precisa para busca: parágrafo/inciso/alínea.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # rag/
from search_hybrid import CORPUS_HINTS, detect_articles  # noqa: E402

PARAGRAFO_UNICO_RE = re.compile(r"par[aá]grafo\s+[uú]nico", re.IGNORECASE)
PARAGRAFO_RE = re.compile(r"§\s*(\d{1,3})\s*[º°oO]?")
INCISO_PALAVRA_RE = re.compile(r"inciso\s+([IVXLCDM]+)\b", re.IGNORECASE)
ALINEA_PALAVRA_RE = re.compile(r"al[ií]nea\s+[\"']?([a-zA-Z])[\"']?", re.IGNORECASE)
# inciso citado sem a palavra "inciso", como token isolado entre vírgulas —
# "art. 373, II, CPC". Só aceito como token INTEIRO (evita casar "III"
# dentro de outra palavra) e nunca se coincidir com uma sigla de corpus
# (ex.: "CC" é, ao mesmo tempo, Código Civil e o numeral romano 200).
TOKEN_ROMANO_RE = re.compile(r"^[IVXLCDM]+$")
_SIGLAS_CORPUS = {c.lower() for c in CORPUS_HINTS}


def parse_citacao(texto: str) -> dict:
    """Retorna dict com:
      raw            — texto original
      artigo         — int do primeiro artigo citado, ou None
      outros_artigos — demais artigos citados na mesma referência (raro)
      corpus         — sigla do corpus (CPC/CC/CDC/L8987/L9427/REN1000) ou
                        None se não identificável sem ambiguidade
      paragrafo      — "unico", string do número, ou None
      inciso         — numeral romano maiúsculo, ou None
      alinea         — letra minúscula, ou None
    """
    artigos, corpus = detect_articles(texto)

    paragrafo = None
    if PARAGRAFO_UNICO_RE.search(texto):
        paragrafo = "unico"
    else:
        m = PARAGRAFO_RE.search(texto)
        if m:
            paragrafo = m.group(1)

    inciso = None
    m = INCISO_PALAVRA_RE.search(texto)
    if m:
        inciso = m.group(1).upper()
    else:
        for token in re.split(r"[,;]", texto):
            token = token.strip().strip(".")
            if not token or token.lower() in _SIGLAS_CORPUS:
                continue
            if TOKEN_ROMANO_RE.match(token.upper()):
                inciso = token.upper()
                break

    alinea = None
    m = ALINEA_PALAVRA_RE.search(texto)
    if m:
        alinea = m.group(1).lower()

    return {
        "raw": texto,
        "artigo": artigos[0] if artigos else None,
        "outros_artigos": artigos[1:] if len(artigos) > 1 else [],
        "corpus": corpus,
        "paragrafo": paragrafo,
        "inciso": inciso,
        "alinea": alinea,
    }
