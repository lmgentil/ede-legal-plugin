#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_placeholder_semantics.py — regressão da validação semântica
de placeholders (Etapa 3, pós-diagnóstico forense do bug real de
paginação).

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.

Uso:
  python tests/test_validate_placeholder_semantics.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from validate_placeholder_semantics import validar_semantica  # noqa: E402


# --------------------------------------------------------------- AUTOR
def test_autor_com_cpf_rejeitado():
    ok, erros = validar_semantica({"AUTOR": "Fulano de Tal, CPF 011.730.795-56"})
    assert not ok
    assert any("CPF" in e for e in erros)


def test_autor_com_qualificacao_rejeitado_bug_real():
    # Reproduz o padrão exato do bug real confirmado por diagnóstico
    # forense (dados fictícios aqui — nunca dados reais em teste).
    ok, erros = validar_semantica({
        "AUTOR": "Fulana de Tal, já qualificada nos autos, portadora do "
                 "CPF nº 011.730.795-56"})
    assert not ok
    assert any("qualificação" in e for e in erros)


def test_autor_simples_aceito():
    ok, erros = validar_semantica({"AUTOR": "MARIA JOSÉ DA CONCEIÇÃO SANTOS"})
    assert ok, erros


def test_autor_nome_longo_legitimo_nao_e_rejeitado_so_por_tamanho():
    # "Não bloquear apenas por comprimento absoluto — existem nomes
    # legitimamente longos" (instrução do gate).
    ok, erros = validar_semantica({
        "AUTOR": "MARIA DA CONCEIÇÃO DE OLIVEIRA PEREIRA ALMEIDA SANTOS DE JESUS"})
    assert ok, erros


# --------------------------------------------------------------- NUMERO_PROCESSO
def test_numero_processo_formato_cnj_valido_aceito():
    ok, erros = validar_semantica({"NUMERO_PROCESSO": "8000001-11.2026.8.05.0080"})
    assert ok, erros


def test_numero_processo_formato_invalido_rejeitado():
    ok, erros = validar_semantica({"NUMERO_PROCESSO": "processo qualquer sem formato"})
    assert not ok
    assert any("NUMERO_PROCESSO" in e for e in erros)


# --------------------------------------------------------------- VALOR_FRA
def test_valor_fra_monetario_aceito():
    ok, erros = validar_semantica({"VALOR_FRA": "R$ 4.328,17"})
    assert ok, erros


def test_valor_fra_sentinela_ausencia_aceita():
    ok, erros = validar_semantica({"VALOR_FRA": "NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."})
    assert ok, erros


def test_valor_fra_sem_digito_nem_sentinela_rejeitado():
    ok, erros = validar_semantica({"VALOR_FRA": "valor a ser apurado depois"})
    assert not ok
    assert any("VALOR_FRA" in e for e in erros)


# --------------------------------------------------------------- LOCAL_DATA
def test_local_data_curto_aceito():
    ok, erros = validar_semantica({"LOCAL_DATA": "Feira de Santana/BA, 10 de fevereiro de 2026."})
    assert ok, erros


def test_local_data_narrativo_rejeitado():
    ok, erros = validar_semantica({
        "LOCAL_DATA": "Feira de Santana/BA. Diante do exposto, requer-se o "
                       "acolhimento integral dos pedidos. Termos em que pede "
                       "deferimento."})
    assert not ok
    assert any("LOCAL_DATA" in e for e in erros)


# --------------------------------------------------------------- campos livres
def test_campos_narrativos_sem_validador_especifico_nao_bloqueiam():
    # SINOPSE_FATOS/REALIDADE_FATICA/etc. não têm heurística de conteúdo
    # (CLAUDE.md: nunca bloquear texto jurídico legítimo por comprimento).
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "Texto longo qualquer, sem restrição semântica "
                          "específica " * 20})
    assert ok, erros


def test_dados_sem_nenhum_campo_com_validador_passa():
    ok, erros = validar_semantica({"SINOPSE_FATOS": "x"})
    assert ok, erros


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
