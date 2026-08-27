#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comparar_versao.py — comparação SemVer (MAJOR.MINOR.PATCH) usada por
skills/atualizar-ede/SKILL.md (Etapa 5.9-I) para decidir se a versão
instalada está atualizada em relação à versão publicada no GitHub.

Comparação NUMÉRICA por componente, nunca lexicográfica de string: como
string, "0.10.10" < "0.10.9" (o caractere '1' vem antes de '9'), mas como
versão 0.10.10 é MAIOR que 0.10.9. Sem dependência externa (`packaging`
não é dependência do projeto, CLAUDE.md §20) — MAJOR.MINOR.PATCH puro
(REQ-040) não precisa de mais que isso.

Uso:
  python scripts/comparar_versao.py 0.10.0 0.10.1   # imprime -1
"""
import re
import sys

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def eh_semver_valido(versao: str) -> bool:
    return bool(_SEMVER.match((versao or "").strip()))


def comparar_semver(a: str, b: str) -> int:
    """-1 se a<b, 0 se a==b, 1 se a>b. ValueError se algum não for SemVer válido."""
    for v in (a, b):
        if not eh_semver_valido(v):
            raise ValueError(f"versão não é SemVer válido (MAJOR.MINOR.PATCH): {v!r}")
    ta = tuple(int(x) for x in a.split("."))
    tb = tuple(int(x) for x in b.split("."))
    return (ta > tb) - (ta < tb)


def _demo():
    assert eh_semver_valido("0.10.0")
    assert not eh_semver_valido("0.10")
    assert not eh_semver_valido("v0.10.0")
    assert comparar_semver("0.10.0", "0.10.0") == 0
    assert comparar_semver("0.10.0", "0.10.1") == -1
    assert comparar_semver("0.10.1", "0.10.0") == 1
    assert comparar_semver("0.10.9", "0.10.10") == -1  # nunca comparação de string
    assert comparar_semver("0.10.10", "0.10.9") == 1
    assert comparar_semver("0.11.0", "0.10.9") == 1
    print("OK — comparar_versao self-check passou.")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        print(comparar_semver(sys.argv[1], sys.argv[2]))
    else:
        _demo()
