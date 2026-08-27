#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrato executável dos segmentos da suíte pytest."""

import os
import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).parent.parent
SEGMENTOS = {
    "fast": "not rag and not docx_real and not pipeline_e2e and not network",
    "rag": "rag",
    "docx_real": "docx_real",
    "pipeline_e2e": "pipeline_e2e",
    "network": "network",
}


def _pytest(*args: str) -> subprocess.CompletedProcess[str]:
    ambiente = dict(os.environ)
    ambiente["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=BASE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ambiente,
        timeout=120,
    )


def _coletar(expressao: str | None = None) -> set[str]:
    args = ["--collect-only", "-q"]
    if expressao is not None:
        args.extend(["-m", expressao])
    resultado = _pytest(*args)
    assert resultado.returncode in (0, 5), resultado.stdout + resultado.stderr
    return {
        linha.strip().replace("\\", "/")
        for linha in resultado.stdout.splitlines()
        if "::" in linha
    }


def test_marcadores_publicos_estao_registrados_no_pytest():
    """Quebra capturada: remover o registro torna os comandos não auditáveis."""
    resultado = _pytest("--markers")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    for marcador in ("rag", "docx_real", "pipeline_e2e", "network"):
        assert f"@pytest.mark.{marcador}:" in resultado.stdout


def test_segmentos_formam_particao_da_coleta_e_classificam_os_pesados():
    """Quebra capturada: teste pesado voltar silenciosamente ao grupo rápido."""
    coleta_total = _coletar()
    coletas = {nome: _coletar(expr) for nome, expr in SEGMENTOS.items()}

    assert "tests/test_comparar_versao.py::test_versoes_iguais_retorna_zero" in coletas["fast"]
    assert "tests/test_rag_search.py::test_regressao_gold_set" in coletas["rag"]
    assert (
        "tests/test_template_engine.py::test_pipeline_completo_contra_template_real"
        in coletas["docx_real"]
    )
    assert (
        "tests/test_e2e_contestacao.py::test_happy_path_pipeline_completo"
        in coletas["pipeline_e2e"]
    )
    assert coletas["network"] == set(), "network deve permanecer opt-in e vazio até existir smoke real"

    nomes = list(coletas)
    for indice, nome in enumerate(nomes):
        for outro in nomes[indice + 1 :]:
            assert coletas[nome].isdisjoint(coletas[outro]), (
                f"segmentos {nome} e {outro} se sobrepõem"
            )
    assert set().union(*coletas.values()) == coleta_total
