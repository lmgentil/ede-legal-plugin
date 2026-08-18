#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_fatos.py — validação estrutural de fatos extraídos com proveniência
(SPEC-0001 REQ-030), usada pela Skill `contestacao` (Fase 6).

A extração de fatos em si é tarefa do agente (leitura dos documentos do
processo fornecidos pelo advogado) — não é algo deterministicamente
automatizável, por isso não há um "extrator" de código aqui (ver
skills/contestacao/SKILL.md, seção de extração factual). O que ESTE script
garante é que, uma vez que o agente produziu a lista de fatos, ela respeita
o contrato mínimo de proveniência antes de alimentar o redator — fail
closed (CLAUDE.md §17): fato sem proveniência não é fato utilizável.

Contrato de cada fato (SPEC-0001 §20, REQ-030):
  {
    "fact": "A linha foi cancelada em 12/11/2025.",
    "source_document": "documento-x.pdf",
    "page": 4,             # opcional, inteiro se presente
    "confidence": 0.99     # opcional, mas se presente deve estar em [0, 1]
  }

Uso:
  python scripts/validate_fatos.py --dados fatos.json
"""
import argparse
import json
import sys

CAMPOS_OBRIGATORIOS = ("fact", "source_document")


def validar_fatos(fatos) -> tuple:
    """Retorna (ok: bool, erros: list[str]). Nunca lança para entrada mal
    formada — reporta como erro de validação, não como exceção não tratada
    (quem chama isso é, tipicamente, um passo de pipeline que precisa de
    uma resposta estruturada, não de um traceback)."""
    if not isinstance(fatos, list):
        return False, ["a entrada deve ser uma lista de fatos"]

    erros = []
    for i, f in enumerate(fatos):
        if not isinstance(f, dict):
            erros.append(f"fato[{i}]: não é um objeto")
            continue
        for campo in CAMPOS_OBRIGATORIOS:
            valor = f.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                erros.append(f"fato[{i}]: campo obrigatório '{campo}' ausente ou vazio")
        if f.get("confidence") is not None:
            c = f["confidence"]
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not (0.0 <= c <= 1.0):
                erros.append(f"fato[{i}]: confidence deve ser número entre 0 e 1, recebeu {c!r}")
        if f.get("page") is not None:
            p = f["page"]
            if isinstance(p, bool) or not isinstance(p, int):
                erros.append(f"fato[{i}]: page deve ser inteiro, recebeu {p!r}")
    return (len(erros) == 0), erros


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dados", required=True, help="JSON com lista de fatos")
    args = ap.parse_args()

    with open(args.dados, encoding="utf-8") as f:
        fatos = json.load(f)

    ok, erros = validar_fatos(fatos)
    if ok:
        print(f"OK — {len(fatos)} fato(s), todos com proveniência válida.")
        sys.exit(0)
    print(f"FALHA — {len(erros)} problema(s):")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)


if __name__ == "__main__":
    main()
