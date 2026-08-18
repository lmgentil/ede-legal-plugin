#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
provenance.py — REQ-029 (Fase 5): proveniência jurídica.

Responde "de onde veio este fundamento?" com um caminho rastreável até o
arquivo real no corpus — nunca um identificador opaco sem trilha.
"""
from pathlib import Path


def proveniencia(corpus: str, arquivo: str, diploma: str = None,
                  artigo: int = None) -> dict:
    return {
        "corpus": corpus,
        "arquivo_origem": arquivo,
        "caminho_relativo": str(Path(f"chunks_{corpus}") / arquivo),
        "diploma": diploma,
        "dispositivo": f"art. {artigo}" if artigo is not None else None,
    }
