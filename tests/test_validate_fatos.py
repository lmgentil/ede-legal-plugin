#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_fatos.py — regressão de scripts/validate_fatos.py (REQ-030,
Fase 6). Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from validate_fatos import validar_fatos  # noqa: E402


def test_fato_completo_valido():
    ok, erros = validar_fatos([
        {"fact": "A linha foi cancelada em 12/11/2025.",
         "source_document": "documento-x.pdf", "page": 4, "confidence": 0.99},
    ])
    assert ok and erros == []


def test_fato_minimo_valido_sem_opcionais():
    ok, erros = validar_fatos([{"fact": "x", "source_document": "y.pdf"}])
    assert ok and erros == []


def test_lista_vazia_e_valida():
    ok, erros = validar_fatos([])
    assert ok and erros == []


def test_entrada_nao_e_lista_falha():
    ok, erros = validar_fatos({"fact": "x"})
    assert not ok and len(erros) == 1


def test_fato_sem_source_document_falha():
    ok, erros = validar_fatos([{"fact": "x"}])
    assert not ok
    assert any("source_document" in e for e in erros)


def test_fato_sem_fact_falha():
    ok, erros = validar_fatos([{"source_document": "y.pdf"}])
    assert not ok
    assert any("'fact'" in e for e in erros)


def test_fact_vazio_ou_so_espaco_falha():
    ok, erros = validar_fatos([{"fact": "   ", "source_document": "y.pdf"}])
    assert not ok


def test_confidence_fora_do_intervalo_falha():
    ok, erros = validar_fatos([
        {"fact": "x", "source_document": "y.pdf", "confidence": 1.5},
    ])
    assert not ok
    assert any("confidence" in e for e in erros)


def test_confidence_bool_falha():
    # bool é subclasse de int em Python — guarda explícita contra isso.
    ok, erros = validar_fatos([
        {"fact": "x", "source_document": "y.pdf", "confidence": True},
    ])
    assert not ok


def test_page_nao_inteiro_falha():
    ok, erros = validar_fatos([
        {"fact": "x", "source_document": "y.pdf", "page": "4"},
    ])
    assert not ok
    assert any("page" in e for e in erros)


def test_item_que_nao_e_objeto_falha():
    ok, erros = validar_fatos(["não é um dict"])
    assert not ok
    assert any("não é um objeto" in e for e in erros)


def test_multiplos_fatos_mistos_reporta_so_o_invalido():
    ok, erros = validar_fatos([
        {"fact": "x", "source_document": "a.pdf"},
        {"fact": "y"},  # falta source_document
    ])
    assert not ok
    assert len(erros) == 1
    assert "fato[1]" in erros[0]


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
