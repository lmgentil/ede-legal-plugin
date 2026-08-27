#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_comparar_versao.py — Etapa 5.9-I: guarda funcional de
scripts/comparar_versao.py, usado por skills/atualizar-ede/SKILL.md para
decidir status de versão sem comparação lexicográfica de string.

Mesmo padrão sem framework do resto do repositório (asserts +
`if __name__ == "__main__"`).
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from comparar_versao import comparar_semver, eh_semver_valido  # noqa: E402


def test_versoes_iguais_retorna_zero():
    assert comparar_semver("0.10.0", "0.10.0") == 0


def test_github_maior_retorna_negativo():
    assert comparar_semver("0.10.0", "0.10.1") == -1


def test_instalada_maior_retorna_positivo():
    assert comparar_semver("0.10.1", "0.10.0") == 1


def test_semver_0_10_10_maior_que_0_10_9():
    # item F do contrato: nunca comparação lexicográfica de string
    # ("0.10.10" < "0.10.9" como string, mas é versão MAIOR).
    assert comparar_semver("0.10.10", "0.10.9") == 1
    assert comparar_semver("0.10.9", "0.10.10") == -1


def test_minor_maior_vence_patch_menor():
    assert comparar_semver("0.11.0", "0.10.9") == 1


def test_eh_semver_valido_aceita_major_minor_patch():
    assert eh_semver_valido("0.10.0")
    assert eh_semver_valido("12.34.56")


def test_eh_semver_valido_rejeita_formatos_invalidos():
    for invalido in ("0.10", "v0.10.0", "0.10.0-beta", "", "abc", None):
        assert not eh_semver_valido(invalido)


def test_comparar_semver_rejeita_versao_invalida():
    try:
        comparar_semver("0.10.0", "não é versão")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
