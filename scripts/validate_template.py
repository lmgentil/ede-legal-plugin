#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_template.py — CLI do Template Lock (SPEC-0001 REQ-016, TEST-001,
TEST-002), como checagem independente do pipeline de geração (útil para
regressão/CI: valida um .docx já gerado contra o template, a qualquer
momento depois).

Estratégia: regenera uma peça de referência com os MESMOS dados via
gerar_peca() (mesmo pipeline, mesmo número de ciclos pack/unpack) e compara
contra o .docx auditado. Isso evita falso-positivo por ruído de
formatação do minidom (o pretty-print/condense do toolkit OOXML não é
perfeitamente idempotente entre gerações — confirmado nesta auditoria: uma
comparação ingênua contra um único unpack do template acusava divergência
puramente de espaço em branco entre tags, fora de qualquer <w:t>). Com a
mesma quantidade de ciclos dos dois lados, a comparação fica exata.

Uso:
  python validate_template.py --gerado saida/peca.docx --dados dados.json
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from docx_template_engine import _importar_toolkit, garantir_utf8, gerar_peca  # noqa: E402

TEMPLATE_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"


def _diff_diretorios(dir_a: Path, dir_b: Path, rotulo_a: str, rotulo_b: str) -> list:
    arquivos_a = {f.relative_to(dir_a) for f in dir_a.rglob("*") if f.is_file()}
    arquivos_b = {f.relative_to(dir_b) for f in dir_b.rglob("*") if f.is_file()}
    divergencias = [f"arquivo em {rotulo_a} ausente em {rotulo_b}: {r}" for r in sorted(arquivos_a - arquivos_b)]
    divergencias += [f"arquivo novo em {rotulo_b} (ausente em {rotulo_a}): {r}" for r in sorted(arquivos_b - arquivos_a)]
    for rel in sorted(arquivos_a & arquivos_b):
        if (dir_a / rel).read_bytes() != (dir_b / rel).read_bytes():
            divergencias.append(f"arquivo difere entre {rotulo_a} e {rotulo_b}: {rel}")
    return divergencias


def main():
    garantir_utf8()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default=str(TEMPLATE_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--gerado", required=True, help=".docx já gerado a auditar")
    ap.add_argument("--dados", required=True, help="JSON com os dados usados na geração original")
    args = ap.parse_args()

    with open(args.dados, "r", encoding="utf-8") as f:
        dados = json.load(f)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        referencia = tmp / "referencia.docx"
        relatorio_geracao = gerar_peca(args.template, args.schema, dados, referencia)
        if relatorio_geracao["status"] != "OK":
            print(json.dumps({"ok": False, "divergencias": [
                "não foi possível gerar peça de referência para comparação",
                *relatorio_geracao.get("erros", []),
            ]}, ensure_ascii=False, indent=2))
            sys.exit(1)

        unpack_mod, _pack_mod = _importar_toolkit()
        ref_dir, aud_dir = tmp / "ref_unpacked", tmp / "aud_unpacked"
        unpack_mod.unpack(str(referencia), str(ref_dir))
        unpack_mod.unpack(args.gerado, str(aud_dir))

        divergencias = _diff_diretorios(ref_dir, aud_dir, "referência", "auditado")
        resultado = {"ok": not divergencias, "divergencias": divergencias}

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    sys.exit(0 if resultado["ok"] else 1)


if __name__ == "__main__":
    main()
