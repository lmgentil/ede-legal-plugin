#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_paragrafos.py — validação estrutural de INV-PARAGRAFO-380 (Etapa
5.2, pós-Teste Real 01: parágrafos gerados pela IA excessivamente
extensos).

Regra: todo parágrafo de conteúdo NOVO (gerado pela IA para os placeholders
multiline) deve ter no máximo 380 caracteres com espaços. A contagem inclui
letras, números, espaços e pontuação.

Escopo deliberadamente restrito: só valida os placeholders marcados
"multiline": true em templates/contestacao/schema.json
(placeholder_contracts) — exatamente os campos de texto livre produzidos
pelo redator/humanizer. Placeholders curtos (JUIZO, AUTOR, VALOR_FRA,
LOCAL_DATA...) não são "parágrafo" e ficam fora. O conteúdo-base
institucional fixo do template (fora dos placeholders) nunca é lido aqui —
não há como este validador causar falso positivo nele (CLAUDE.md §17).

"Parágrafo", para este validador, é cada trecho separado por quebra de
linha ("\\n") dentro do valor do placeholder — a mesma convenção que
docx_template_engine.substituir_placeholders() usa para inserir <w:br/>
entre linhas de um mesmo placeholder multiline. Linhas em branco (só
espaço) são ignoradas — não contam como parágrafo vazio.

Não corta texto mecanicamente: só reporta a violação (parágrafo, índice,
tamanho) para o pipeline abortar (PIPELINE_ABORTED, stage=paragrafo_380) —
decompor o raciocínio em mais parágrafos é trabalho do redator, não deste
script (CLAUDE.md §5 do prompt da Etapa 5.2).

Uso:
  python scripts/validate_paragrafos.py --dados dados.json --schema schema.json
"""
import argparse
import json
import sys
from pathlib import Path

PARAGRAFO_MAXIMO = 380


def paragrafos(texto: str) -> list:
    """Quebra o valor de um placeholder multiline em parágrafos, ignorando
    linhas em branco (separadores de espaçamento, não conteúdo)."""
    return [p for p in str(texto).split("\n") if p.strip()]


def validar_paragrafo_380(texto: str) -> list:
    """Retorna a lista de erros (vazia se todos os parágrafos de `texto`
    respeitam o limite de 380 caracteres)."""
    erros = []
    for i, p in enumerate(paragrafos(texto)):
        if len(p) > PARAGRAFO_MAXIMO:
            preview = p[:60] + ("…" if len(p) > 60 else "")
            erros.append(
                f"parágrafo {i + 1} tem {len(p)} caracteres (máximo "
                f"{PARAGRAFO_MAXIMO}, INV-PARAGRAFO-380): {preview!r}")
    return erros


def validar_paragrafos_placeholders(dados: dict, schema: dict) -> tuple:
    """Valida INV-PARAGRAFO-380 só nos placeholders declarados 'multiline':
    true em schema['placeholder_contracts']. Retorna (ok, erros) — cada
    erro já identifica o placeholder de origem."""
    contratos = schema.get("placeholder_contracts", {})
    erros = []
    for nome, contrato in contratos.items():
        if not contrato.get("multiline"):
            continue
        valor = dados.get(nome)
        if valor is None:
            continue
        for e in validar_paragrafo_380(valor):
            erros.append(f"{nome}: {e}")
    return (len(erros) == 0), erros


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dados", required=True, help="JSON com {PLACEHOLDER: valor}")
    ap.add_argument("--schema", required=True, help="templates/contestacao/schema.json")
    args = ap.parse_args()

    dados = json.loads(Path(args.dados).read_text(encoding="utf-8"))
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    ok, erros = validar_paragrafos_placeholders(dados, schema)
    if ok:
        print("OK — todos os parágrafos respeitam o limite de 380 caracteres (INV-PARAGRAFO-380).")
        sys.exit(0)
    print(f"FALHA — {len(erros)} parágrafo(s) acima do limite:")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)


if __name__ == "__main__":
    main()
