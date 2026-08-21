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
    LIMITES_DENSIDADE_BLOCO,
    PARAGRAFO_MAXIMO,
    validar_densidade_bloco,
    validar_densidade_blocos,
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


# --------------------------------------------------------------- densidade por bloco (Etapa 5.3)
def test_densidade_bloco_dentro_do_limite_passa():
    limite = {"max_paragrafos": 3, "max_total_chars": 600}
    texto = "\n".join(["a" * 100, "b" * 100, "c" * 100])
    assert validar_densidade_bloco(texto, limite) == []


def test_densidade_bloco_excesso_de_paragrafos_detectado():
    limite = {"max_paragrafos": 2, "max_total_chars": 10000}
    texto = "\n".join(["a" * 10, "b" * 10, "c" * 10])
    erros = validar_densidade_bloco(texto, limite)
    assert len(erros) == 1 and "parágrafos" in erros[0]


def test_densidade_bloco_excesso_de_caracteres_totais_detectado():
    # cada parágrafo individualmente ≤380, mas a soma estoura o bloco —
    # exatamente o achado do Teste Real 01-B (acumulação, não tamanho unitário).
    limite = {"max_paragrafos": 10, "max_total_chars": 200}
    texto = "\n".join(["a" * 100, "b" * 100, "c" * 100])
    erros = validar_densidade_bloco(texto, limite)
    assert len(erros) == 1 and "caracteres no total" in erros[0]


def test_densidade_blocos_placeholder_sem_limite_declarado_nao_e_checado():
    ok, erros = validar_densidade_blocos({"AUTOR": "x" * 10000})
    assert ok, erros


def test_densidade_blocos_pedidos_finais_prolixo_e_rejeitado():
    # Regressão direta do padrão observado no Teste Real 01-B: pedidos
    # respondendo individualmente a cada questão da inicial.
    limite = LIMITES_DENSIDADE_BLOCO["PEDIDOS_FINAIS"]
    texto = "\n".join(["Requer item %d da lista de pedidos." % i * 5 for i in range(6)])
    ok, erros = validar_densidade_blocos({"PEDIDOS_FINAIS": texto})
    assert not ok
    assert any("PEDIDOS_FINAIS" in e for e in erros)


def test_densidade_blocos_sinopse_compacta_aceita():
    texto = "\n".join([
        "A autora narra ter recebido fatura de recuperação de consumo após TOI.",
        "Requer a declaração de inexigibilidade e indenização por danos morais.",
    ])
    ok, erros = validar_densidade_blocos({"SINOPSE_FATOS": texto})
    assert ok, erros


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
