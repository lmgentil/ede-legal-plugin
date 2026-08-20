#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_paragrafos.py — regressão de INV-PARAGRAFO-380 (Etapa 5.2).

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.

Uso:
  python tests/test_validate_paragrafos.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from validate_paragrafos import (  # noqa: E402
    PARAGRAFO_MAXIMO,
    validar_paragrafo_380,
    validar_paragrafos_placeholders,
)

SCHEMA_MINIMO = {"placeholder_contracts": {
    "SINOPSE_FATOS": {"multiline": True},
    "REALIDADE_FATICA": {"multiline": True},
    "AUTOR": {"multiline": False},
}}


# --------------------------------------------------------------- limite exato (379/380/381)
def test_379_caracteres_passa():
    assert validar_paragrafo_380("a" * 379) == []


def test_380_caracteres_passa():
    assert validar_paragrafo_380("a" * 380) == []


def test_381_caracteres_falha():
    erros = validar_paragrafo_380("a" * 381)
    assert len(erros) == 1
    assert "381" in erros[0] and str(PARAGRAFO_MAXIMO) in erros[0]


# --------------------------------------------------------------- múltiplos parágrafos
def test_varios_paragrafos_todos_no_limite_passa():
    texto = "\n".join(["a" * 380, "b" * 100, "c" * 380])
    assert validar_paragrafo_380(texto) == []


def test_um_paragrafo_estourado_entre_varios_e_detectado():
    texto = "\n".join(["a" * 100, "b" * 381, "c" * 50])
    erros = validar_paragrafo_380(texto)
    assert len(erros) == 1
    assert "parágrafo 2" in erros[0]


def test_linhas_em_branco_nao_contam_como_paragrafo():
    texto = "a" * 100 + "\n\n\n" + "b" * 100
    assert validar_paragrafo_380(texto) == []


# --------------------------------------------------------------- integração com schema (multiline)
def test_placeholder_nao_multiline_nao_e_validado():
    dados = {"AUTOR": "x" * 500}  # não é multiline — não é "parágrafo"
    ok, erros = validar_paragrafos_placeholders(dados, SCHEMA_MINIMO)
    assert ok, erros


def test_placeholder_multiline_estourado_e_detectado():
    dados = {"SINOPSE_FATOS": "x" * 400}
    ok, erros = validar_paragrafos_placeholders(dados, SCHEMA_MINIMO)
    assert not ok
    assert any("SINOPSE_FATOS" in e for e in erros)


def test_placeholder_ausente_dos_dados_e_ignorado():
    ok, erros = validar_paragrafos_placeholders({}, SCHEMA_MINIMO)
    assert ok, erros


def test_multiplos_placeholders_multiline_validados_independentemente():
    dados = {
        "SINOPSE_FATOS": "a" * 380,          # ok
        "REALIDADE_FATICA": "b" * 381,       # falha
    }
    ok, erros = validar_paragrafos_placeholders(dados, SCHEMA_MINIMO)
    assert not ok
    assert len(erros) == 1
    assert "REALIDADE_FATICA" in erros[0]
    assert not any("SINOPSE_FATOS" in e for e in erros)


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
