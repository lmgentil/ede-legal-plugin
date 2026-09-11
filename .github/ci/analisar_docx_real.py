#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.github/ci/analisar_docx_real.py — Etapa 6.2-B, ajuste obrigatório do
usuário sobre `pytest -m docx_real` no runner efêmero.

Em clone limpo (sem templates/contestacao/modelo-oficial.docx, gitignored
e nunca commitado — ADR-0009/CLAUDE.md §13), o resultado ESPERADO é SKIP:
cada teste marcado docx_real chama `pytest.skip(...)` explicitamente
quando o arquivo não existe (mesmo padrão em toda a suíte, confirmado por
grep nesta rodada — texto idêntico caractere a caractere em todo arquivo
de teste: "não instalado localmente — asset institucional externo
(ADR-0009)."). Mas "sem execução"/"sem asserção" NUNCA pode virar
sinônimo de sucesso por omissão — exigência explícita do usuário. Este
script lê o relatório JUnit XML real produzido por
`pytest -m docx_real --junit-xml=...` e classifica o resultado em UMA das
categorias abaixo, falhando (exit 1) em todas menos a primeira:

  A. SKIP LEGÍTIMO — todo teste coletado foi skip, e TODO skip tem a
     razão padronizada de ausência do Modelo Oficial. ÚNICO resultado
     aceito.
  B. erro de coleta (collection error) — <testsuite errors="N"> com N>0.
  C. marker inexistente — pytest.ini já registra "docx_real" com
     addopts=--strict-markers; se o marker não existisse, pytest sairia
     com EXIT_USAGEERROR (4) antes de gerar XML válido — cai em F.
  D. import failure — mesma assinatura de B (aparece como "errors").
  E. teste não descoberto — zero <testcase> no relatório.
  F. erro de configuração/execução — exit code de uso incorreto (4),
     interno (3), interrompido (2), XML ausente/malformado, teste que
     falhou de verdade (não por ausência do asset), ou SKIP com razão
     fora do padrão esperado (skip por motivo diferente do ADR-0009).

Nunca decide "ausência de saída = sucesso": toda categoria fora de A é
reportada com o motivo específico e falha o processo. Escreve um resumo
em Markdown em $GITHUB_STEP_SUMMARY quando a variável existir (fora do
GitHub Actions, só imprime em stdout).

Uso:
    python analisar_docx_real.py <relatorio-junit.xml> <exit-code-do-pytest>
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RAZAO_LEGITIMA = re.compile(
    r"não instalado localmente\s*—\s*asset institucional externo \(ADR-0009\)\."
)


def _carregar_testsuite(caminho: Path) -> ET.Element | None:
    """Retorna o elemento <testsuite> (agregado, se houver várias) ou
    None se o arquivo estiver ausente/malformado — sinal de falha de
    execução antes mesmo da geração do relatório (categoria F)."""
    if not caminho.exists():
        return None
    try:
        raiz = ET.parse(caminho).getroot()
    except ET.ParseError:
        return None
    if raiz.tag == "testsuite":
        return raiz
    if raiz.tag == "testsuites":
        suites = raiz.findall("testsuite")
        if not suites:
            return None
        if len(suites) == 1:
            return suites[0]
        # Agregação defensiva caso o pytest algum dia particione em mais
        # de um <testsuite> — soma os atributos numéricos relevantes.
        agregado = ET.Element("testsuite")
        for chave in ("tests", "failures", "errors", "skipped"):
            agregado.set(chave, str(sum(int(s.get(chave, 0)) for s in suites)))
        for s in suites:
            agregado.extend(s.findall("testcase"))
        return agregado
    return None


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: analisar_docx_real.py <relatorio-junit.xml> <exit-code>")
        return 2

    caminho_xml = Path(sys.argv[1])
    try:
        exit_code = int(sys.argv[2])
    except ValueError:
        exit_code = -1

    suite = _carregar_testsuite(caminho_xml)

    categoria: str
    motivo: str
    coletados = passed = skipped = failed = errors = 0
    razoes_skip: list[str] = []
    razoes_ilegitimas: list[str] = []

    if suite is None:
        categoria = "F"
        motivo = (
            f"relatório JUnit XML ausente ou malformado em {caminho_xml} "
            f"(exit code do pytest: {exit_code}) — execução não produziu "
            "resultado analisável; tratar como erro de configuração/execução, "
            "nunca como sucesso por omissão."
        )
    else:
        coletados = int(suite.get("tests", "0"))
        failed = int(suite.get("failures", "0"))
        errors = int(suite.get("errors", "0"))
        skipped = int(suite.get("skipped", "0"))
        passed = coletados - failed - errors - skipped

        for caso in suite.findall("testcase"):
            skip_el = caso.find("skipped")
            if skip_el is not None:
                msg = skip_el.get("message", "")
                razoes_skip.append(f"{caso.get('classname')}::{caso.get('name')} -> {msg}")
                if not RAZAO_LEGITIMA.search(msg):
                    razoes_ilegitimas.append(f"{caso.get('classname')}::{caso.get('name')} -> {msg}")

        if exit_code in (2, 3, 4):
            categoria = "F"
            motivo = {
                2: "pytest interrompido (EXIT_INTERRUPTED) — não é o SKIP legítimo esperado.",
                3: "erro interno do pytest (EXIT_INTERNALERROR).",
                4: "erro de uso/configuração (EXIT_USAGEERROR) — inclui marker inexistente (categoria C).",
            }[exit_code]
        elif errors > 0:
            categoria = "B/D"
            motivo = f"{errors} erro(s) de coleta/import reportado(s) pelo pytest — nunca skip legítimo."
        elif coletados == 0:
            categoria = "E"
            motivo = "nenhum teste coletado para o marker docx_real (teste não descoberto)."
        elif failed > 0:
            categoria = "F"
            motivo = f"{failed} teste(s) falharam de verdade — regressão real, não ausência de asset."
        elif razoes_ilegitimas:
            categoria = "F"
            motivo = (
                f"{len(razoes_ilegitimas)} SKIP(s) com razão fora do padrão ADR-0009 "
                "esperado — skip por motivo inesperado, não é o skip legítimo."
            )
        elif skipped == 0:
            categoria = "F"
            motivo = (
                "nenhum SKIP ocorreu (tudo passou sem o Modelo Oficial) — "
                "contraria a premissa do marker docx_real; revisar manualmente "
                "antes de aceitar."
            )
        elif exit_code != 0:
            categoria = "F"
            motivo = f"exit code inesperado ({exit_code}) apesar de só passed/skipped nas contagens."
        else:
            categoria = "A"
            motivo = (
                "todos os testes coletados foram SKIP, todos com a razão "
                "padronizada de ausência do Modelo Oficial (ADR-0009)."
            )

    linhas = [
        "### `pytest -m docx_real` — análise do resultado (clone limpo, runner efêmero)",
        "```",
        f"exit code pytest:  {exit_code}",
        f"coletados:         {coletados}",
        f"passed:            {passed}",
        f"skipped:           {skipped}",
        f"failed:            {failed}",
        f"errors:            {errors}",
        f"categoria:         {categoria}",
        f"motivo:            {motivo}",
        "```",
    ]
    if razoes_skip:
        linhas.append("Razões de SKIP observadas (até 20):")
        linhas.append("```")
        linhas.extend(razoes_skip[:20])
        linhas.append("```")

    texto = "\n".join(linhas)
    print(texto)

    caminho_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if caminho_summary:
        with open(caminho_summary, "a", encoding="utf-8") as f:
            f.write(texto + "\n")

    if categoria != "A":
        print(f"\nGATE FALHOU: resultado de docx_real não é o SKIP legítimo esperado (categoria {categoria}).")
        return 1

    print("\nOK — SKIP legítimo confirmado: ausência do Modelo Oficial, conforme ADR-0009.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
