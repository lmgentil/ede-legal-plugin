#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_docx.py — CLI do motor de renderização (SPEC-0001 REQ-032).

Lógica real em docx_template_engine.py; este arquivo é só a interface de
linha de comando prevista na árvore de diretórios do REQ-001.

Uso:
  python render_docx.py --dados dados.json --output saida/peca.docx
  python render_docx.py --template outro-template.docx --schema outro-schema.json \
      --dados dados.json --output saida/peca.docx
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from docx_template_engine import garantir_utf8, gerar_peca  # noqa: E402

TEMPLATE_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"


def main():
    garantir_utf8()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default=str(TEMPLATE_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--dados", required=True, help="JSON com {PLACEHOLDER: valor}")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.dados, "r", encoding="utf-8") as f:
        dados = json.load(f)

    relatorio = gerar_peca(args.template, args.schema, dados, args.output)
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    sys.exit(0 if relatorio["status"] == "OK" else 1)


if __name__ == "__main__":
    main()
