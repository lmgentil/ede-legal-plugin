#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_placeholders.py — CLI do validador de placeholders (SPEC-0001
REQ-034). TEST-003 (placeholder desconhecido) / TEST-004 (residual).

Lógica real em docx_template_engine.py (validar_placeholders). Este arquivo
é só a interface de linha de comando prevista no REQ-001. Não desempacota
via toolkit externo — só precisa ler o document.xml para conferir os
placeholders, então funciona mesmo sem o skill "docx" instalado.

Uso:
  python validate_placeholders.py --dados dados.json
  python validate_placeholders.py --template outro.docx --schema outro.json --dados dados.json
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from docx_template_engine import carregar_schema, validar_placeholders  # noqa: E402

TEMPLATE_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"


def _ler_document_xml(docx_path) -> str:
    with zipfile.ZipFile(docx_path) as z:
        return z.read("word/document.xml").decode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default=str(TEMPLATE_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--dados", help="JSON com {PLACEHOLDER: valor}; se omitido, valida só o schema x template")
    args = ap.parse_args()

    schema = carregar_schema(args.schema)
    template_xml = _ler_document_xml(args.template)
    dados = {}
    if args.dados:
        with open(args.dados, "r", encoding="utf-8") as f:
            dados = json.load(f)

    resultado = validar_placeholders(template_xml, dados, schema)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    sys.exit(0 if resultado["ok"] else 1)


if __name__ == "__main__":
    main()
