#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_instalacao.py — validação pós-instalação/pós-atualização do EDE
Legal Plugin (Fase 8, SPEC-0001 §34/§35).

Usado por: skills/atualizar-ede/SKILL.md (após o advogado rodar a
atualização oficial do Claude Code) e por quem quiser conferir uma
instalação nova. Fail closed: qualquer item OBRIGATÓRIO ausente/inválido
resulta em status UPDATE_FAILED — nunca "sucesso" quando algo essencial
falta (CLAUDE.md §17, SPEC-0001 Fase 8 §35).

O template institucional real (`templates/contestacao/modelo-oficial.docx`)
é verificado, mas NÃO é obrigatório para este script reportar sucesso: é
asset institucional privado (ADR-0006), instalado separadamente pelo
escritório — sua ausência é esperada logo após instalar o plugin público.

Uso:
  python scripts/validar_instalacao.py
  python scripts/validar_instalacao.py --json
"""
import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

SKILLS_ESSENCIAIS = [
    "contestacao",
    "estrategista-contestacao-ede",
    "redator-peca-processual-elite",
    "humanizer-pt-br",
    "calendario-forense-tjba-2026",
]


def _json_valido(caminho: Path) -> bool:
    if not caminho.exists():
        return False
    try:
        json.loads(caminho.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def validar_instalacao(base: Path = BASE) -> dict:
    checagens = []

    for nome in SKILLS_ESSENCIAIS:
        caminho = base / "skills" / nome / "SKILL.md"
        checagens.append({"item": f"skill:{nome}", "ok": caminho.exists(),
                           "obrigatorio": True})

    checagens.append({"item": "template:schema.json",
                       "ok": _json_valido(base / "templates" / "contestacao" / "schema.json"),
                       "obrigatorio": True})

    checagens.append({
        "item": "template:modelo-oficial.docx (asset institucional privado — ADR-0006)",
        "ok": (base / "templates" / "contestacao" / "modelo-oficial.docx").exists(),
        "obrigatorio": False})

    checagens.append({"item": "rag:config.yaml",
                       "ok": (base / "rag" / "config.yaml").exists(),
                       "obrigatorio": True})
    checagens.append({"item": "rag:index_artigos.json",
                       "ok": _json_valido(base / "rag" / "index_artigos.json"),
                       "obrigatorio": True})

    plugin_json = base / ".claude-plugin" / "plugin.json"
    version_file = base / "VERSION"
    versao_plugin = None
    versao_sincronizada = False
    if _json_valido(plugin_json) and version_file.exists():
        versao_plugin = json.loads(plugin_json.read_text(encoding="utf-8")).get("version")
        versao_sincronizada = versao_plugin == version_file.read_text(encoding="utf-8").strip()
    checagens.append({"item": "versao:VERSION == plugin.json", "ok": versao_sincronizada,
                       "obrigatorio": True})

    obrigatorias_falhando = [c["item"] for c in checagens
                              if c["obrigatorio"] and not c["ok"]]
    status = "OK" if not obrigatorias_falhando else "UPDATE_FAILED"

    return {
        "status": status,
        "versao": versao_plugin,
        "checagens": checagens,
        "obrigatorias_falhando": obrigatorias_falhando,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    resultado = validar_instalacao()

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"EDE Legal Plugin — versão {resultado['versao']}")
        for c in resultado["checagens"]:
            marca = "OK " if c["ok"] else ("FALHA" if c["obrigatorio"] else "opcional ausente")
            print(f"  [{marca}] {c['item']}")
        print(f"\nSTATUS: {resultado['status']}")
        if resultado["obrigatorias_falhando"]:
            print("Itens obrigatórios ausentes/inválidos:")
            for item in resultado["obrigatorias_falhando"]:
                print(f"  - {item}")

    sys.exit(0 if resultado["status"] == "OK" else 1)


if __name__ == "__main__":
    main()
