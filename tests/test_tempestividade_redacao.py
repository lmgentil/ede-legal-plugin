#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_tempestividade_redacao.py — Etapa 5.5 §25: cálculo e redação da
tempestividade são coisas diferentes. Cobre a lista A-K do achado real
(redação robótica com dump de memória de cálculo, datas ISO, menção
indevida a Lei 9.099/95) e a regra fixa INV-TEMPESTIVIDADE-PROCEDIMENTO-
COMUM (sempre procedimento comum do CPC, 15 dias úteis) contra
scripts/gerar_contestacao.py.

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.

Uso:
  python tests/test_tempestividade_redacao.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"
sys.path.insert(0, str(BASE / "scripts"))
from gerar_contestacao import (  # noqa: E402
    PRAZO_LEGAL_DIAS_PADRAO,
    TIPO_PRAZO_PADRAO,
    _etapa_tempestividade,
)

_DATA_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_TEMPESTIVIDADE_BASE = json.loads(
    (FIXTURES / "happy_path" / "tempestividade.json").read_text(encoding="utf-8"))


def _rodar(overrides=None, remover=()):
    """Grava um tempestividade.json sintético num caso temporário e roda
    _etapa_tempestividade sobre ele — retorna (resultado, stages)."""
    dados = dict(_TEMPESTIVIDADE_BASE)
    dados.update(overrides or {})
    for k in remover:
        dados.pop(k, None)
    with tempfile.TemporaryDirectory() as tmp:
        caso = Path(tmp)
        (caso / "tempestividade.json").write_text(json.dumps(dados), encoding="utf-8")
        stages = []
        resultado = _etapa_tempestividade(caso, stages)
        return resultado, stages


def _abortou(overrides=None, remover=()):
    r, stages = _rodar(overrides, remover)
    if isinstance(r, dict) and r.get("status") == "PIPELINE_ABORTED":
        return r
    return None


# A. prazo=15 dias
def test_A_prazo_15_dias_explicito_e_aceito():
    texto, _ = _rodar({"prazo_legal_dias": 15})
    assert isinstance(texto, str)


def test_A_prazo_diferente_de_15_aborta():
    e = _abortou({"prazo_legal_dias": 5})
    assert e and e["stage"] == "tempestividade"
    assert "prazo_legal_dias" in e["reason"]


def test_A_prazo_ausente_recebe_padrao_15():
    texto, stages = _rodar(remover=("prazo_legal_dias",))
    assert isinstance(texto, str)
    assert PRAZO_LEGAL_DIAS_PADRAO == 15


# B. unidade=dias úteis
def test_B_tipo_prazo_uteis_explicito_e_aceito():
    texto, _ = _rodar({"tipo_prazo": "uteis"})
    assert isinstance(texto, str)


def test_B_tipo_prazo_diferente_de_uteis_aborta():
    e = _abortou({"tipo_prazo": "corridos"})
    assert e and e["stage"] == "tempestividade"
    assert "tipo_prazo" in e["reason"]


def test_B_tipo_prazo_ausente_recebe_padrao_uteis():
    texto, _ = _rodar(remover=("tipo_prazo",))
    assert isinstance(texto, str)
    assert TIPO_PRAZO_PADRAO == "uteis"


# C. procedimento comum
def test_C_fundamento_normativo_ausente_recebe_padrao_procedimento_comum():
    texto, stages = _rodar(remover=("fundamento_normativo",))
    assert isinstance(texto, str)
    tempestividade_stage = next(s for s in stages if s["name"] == "tempestividade")
    assert "art. 335" in tempestividade_stage["memoria_calculo"]["fundamento_normativo"]


def test_C_fundamento_normativo_compativel_e_aceito():
    texto, _ = _rodar({"fundamento_normativo": "art. 335, caput, do CPC"})
    assert isinstance(texto, str)


# D. cálculo interno preserva memória completa
def test_D_memoria_de_calculo_completa_no_stage_interno():
    _, stages = _rodar()
    tempestividade_stage = next(s for s in stages if s["name"] == "tempestividade")
    assert tempestividade_stage["status"] == "ok"
    memoria = tempestividade_stage["memoria_calculo"]
    for campo in ("termo_inicial", "termo_final", "prazo_legal_dias",
                  "tipo_prazo", "fundamento_normativo", "status"):
        assert campo in memoria, f"memória de cálculo sem {campo!r}"


# E. DOCX não recebe dump da memória de cálculo
def test_E_redacao_final_nao_e_dump_da_memoria():
    texto, _ = _rodar()
    assert "prazo_legal_dias" not in texto
    assert "fundamento_normativo" not in texto
    assert "memoria_calculo" not in texto


# F. DOCX não contém "TEMPESTIVO:"
def test_F_redacao_nao_contem_prefixo_tempestivo_dois_pontos():
    texto, _ = _rodar()
    assert "TEMPESTIVO:" not in texto
    assert "INTEMPESTIVO:" not in texto


# G. DOCX não contém "termo inicial" em formato de relatório
def test_G_redacao_nao_contem_termo_inicial_em_formato_de_relatorio():
    texto, _ = _rodar()
    assert "termo inicial" not in texto.lower()
    assert "termo final" not in texto.lower()


# H. DOCX não contém datas ISO YYYY-MM-DD
def test_H_redacao_nao_contem_data_iso():
    texto, _ = _rodar()
    assert not _DATA_ISO_RE.search(texto), texto


# I. DOCX não menciona aplicação subsidiária da Lei 9.099/95
def test_I_redacao_nao_menciona_lei_9099():
    texto, _ = _rodar()
    v = texto.lower()
    assert "9.099" not in v and "9099" not in v and "juizado especial" not in v


def test_I_fundamento_normativo_mencionando_9099_aborta():
    e = _abortou({"fundamento_normativo": "art. 335, aplicado subsidiariamente "
                                           "ao rito da Lei 9.099/1995"})
    assert e and e["stage"] == "tempestividade"
    assert "9.099" in e["reason"] or "9099" in e["reason"]


# J. redação final é frase jurídica natural
def test_J_redacao_e_frase_juridica_natural_tempestivo():
    texto, _ = _rodar()
    assert texto.startswith("A presente Contestação é tempestiva")
    assert "advogado" not in texto.lower()
    assert "sistema" not in texto.lower()
    assert "json" not in texto.lower()
    assert "algoritmo" not in texto.lower()


def test_J_redacao_e_frase_juridica_natural_intempestivo():
    # marco distante o bastante do prazo de 15 dias úteis para ultrapassar
    # o termo final — cenário sintético, sem dados reais de caso algum.
    texto, _ = _rodar({"data_ciencia": "2025-01-06", "data_pratica_ato": "2026-02-10"})
    assert "intempestiva" in texto.lower()
    assert not _DATA_ISO_RE.search(texto)


# K. cálculo indeterminado continua fail-closed
def test_K_marco_ausente_continua_fail_closed():
    e = _abortou(remover=("data_ciencia", "data_publicacao"))
    assert e and e["stage"] == "tempestividade"


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    ok = 0
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
        ok += 1
    print(f"\n{ok}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
