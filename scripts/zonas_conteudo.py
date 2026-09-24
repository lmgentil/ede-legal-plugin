#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zonas_conteudo.py — validação do conteúdo das Zonas de Complementação,
compartilhada pelo fluxo local (`gerar_contestacao._etapa_zonas`) e pelo
finalizador MCP (ADR-0021, PEND-015).

Extraída de `gerar_contestacao._etapa_zonas` SEM mudança de regra nem de
ordem (INV-ZONA-COMPLEMENTACAO, ADR-0010, SPEC-0001 §58): forma
estruturada {"conteudo", "fatos"} -> proveniência contra a base
documental do caso -> limites do catálogo -> semântica -> continuidade
com o texto institucional adjacente. Não decide inclusão (isso é
`docx_block_engine.resolver_estados_zonas`), não redige, não apara texto
e nunca toca o texto institucional.
"""
from __future__ import annotations

from validate_fatos import normalizar_conteudo_zona, validar_proveniencia_zona
from validate_paragrafos import validar_densidade_zonas
from validate_placeholder_semantics import validar_continuidade_zonas, validar_semantica_zonas


def validar_conteudo_zonas(conteudo: dict, catalogo: dict, fatos_do_caso=None,
                           contexto_institucional: dict | None = None):
    """Devolve (texto_por_zona, proveniencia, erro). `erro` é None quando
    tudo passa; senão, a mensagem de recusa (mesmo texto que o fluxo local
    já usava)."""
    zonas_catalogo = {z["id"]: z for z in catalogo.get("zones", [])}
    texto_por_zona, proveniencia, erros_proveniencia = {}, {}, []
    for zid, bruto in sorted(conteudo.items()):
        texto, fatos_zona, erros_forma = normalizar_conteudo_zona(bruto)
        erros_proveniencia.extend(f"{zid}: {e}" for e in erros_forma)
        texto_por_zona[zid] = texto
        if not texto:
            continue
        proveniencia[zid] = fatos_zona
        if zonas_catalogo.get(zid, {}).get("exige_proveniencia", True):
            erros_proveniencia.extend(validar_proveniencia_zona(texto, fatos_zona, zid, fatos_do_caso))
    if erros_proveniencia:
        return texto_por_zona, proveniencia, f"proveniência do conteúdo de zona inválida: {erros_proveniencia}"

    ok, erros = validar_densidade_zonas(texto_por_zona, catalogo.get("zones", []))
    if not ok:
        return texto_por_zona, proveniencia, f"conteúdo de zona fora dos limites do catálogo: {erros}"

    ok, erros = validar_semantica_zonas(texto_por_zona)
    if not ok:
        return texto_por_zona, proveniencia, f"conteúdo de zona semanticamente inválido: {erros}"

    ok, erros = validar_continuidade_zonas(texto_por_zona, contexto_institucional or {})
    if not ok:
        return texto_por_zona, proveniencia, (f"zona repete abertura do texto institucional adjacente "
                                              f"(INV-CONTINUIDADE-ZONA): {erros}")
    return texto_por_zona, proveniencia, None
