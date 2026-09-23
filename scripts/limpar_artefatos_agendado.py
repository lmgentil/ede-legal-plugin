#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpar_artefatos_agendado.py — entrypoint standalone da limpeza NORMAL
de artefatos efêmeros (Gate 6.6-E, continuação, ADR-0019).

Motivo de existir: a limpeza oportunista disparada de dentro de
`finalizar_peca.py` (a cada finalização bem-sucedida) cobre o caso
comum, mas sozinha não garante retenção normal de ~24-25h durante
períodos SEM tráfego — um artefato gerado pela última finalização do
dia ficaria armazenado até a próxima finalização (podendo ser no dia
seguinte) se nada mais o varresse. Este script existe para ser invocado
por um mecanismo de agendamento EXTERNO, independente de tráfego —
Cloud Scheduler acionando um Cloud Run Job (ou um endpoint autenticado
dedicado), com cadência horária, é o desenho recomendado em
`docs/adr/ADR-0019-entrega-de-artefato-multi-cliente.md`.

**Este script, sozinho, NÃO é uma prova de que o agendamento está
ativo** — ele só executa a varredura quando alguém (um operador, um
teste, ou eventualmente o Cloud Scheduler) o chama. Nenhuma
infraestrutura de agendamento (Cloud Scheduler, Cloud Run Job, gatilho
HTTP) foi provisionada por este gate — ver o relatório do Gate 6.6-E
para o item em aberto.

Chama `artifact_storage.limpar_artefatos_elegiveis` em laço, respeitando
`LIMPEZA_MAX_OBJETOS_POR_VARREDURA` por rodada, até uma rodada não
encontrar mais nada a excluir ou até `MAX_RODADAS_POR_EXECUCAO` ser
atingido (defesa contra uma execução única varrer indefinidamente se o
backlog for anormalmente grande — nesse caso a próxima execução
agendada continua de onde esta parou).

Uso:
    python scripts/limpar_artefatos_agendado.py [--json]

Variável de ambiente exigida: a mesma do serviço
(`EDE_ARTEFATOS_GCS_BUCKET`) — nunca um caminho de configuração
paralelo. (`EDE_ARTEFATOS_SIGNER_SA` só existia para a assinatura V4,
substituída no Gate 6.6-F/G; é ignorada se presente.)"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import artifact_storage as ast  # noqa: E402

MAX_RODADAS_POR_EXECUCAO = 10
"""Teto de rodadas de varredura por execução do script — cada rodada já
tem seu próprio teto de objetos (`LIMPEZA_MAX_OBJETOS_POR_VARREDURA`);
isto é uma segunda defesa contra uma única invocação rodar por tempo
indefinido num backlog anormal."""


def executar(env: dict) -> dict:
    """Núcleo testável (sem `sys.exit`) — devolve o agregado de todas as
    rodadas. `ErroConfiguracaoArtefato`/`ErroArmazenamentoArtefato`
    propagam para o chamador (o `main()` deste script os transforma em
    saída de erro; um mecanismo de agendamento real deve tratar um
    código de saída != 0 como falha da execução agendada, nunca como
    "nada a fazer")."""
    transporte = ast.obter_transporte_do_ambiente(env)
    agregado = {"rodadas": 0, "inspecionados": 0, "excluidos": 0, "falhas": 0}
    for _ in range(MAX_RODADAS_POR_EXECUCAO):
        resultado = ast.limpar_artefatos_elegiveis(transporte)
        agregado["rodadas"] += 1
        agregado["inspecionados"] += resultado["inspecionados"]
        agregado["excluidos"] += resultado["excluidos"]
        agregado["falhas"] += resultado["falhas"]
        if resultado["inspecionados"] < ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA:
            break  # rodada não encheu o teto -- não há mais backlog imediato
    return agregado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="saída em JSON (para logs estruturados)")
    args = parser.parse_args()

    try:
        agregado = executar(os.environ)
    except ast.ErroConfiguracaoArtefato as e:
        if args.json:
            print(json.dumps({"status": "ERRO_CONFIGURACAO", "motivo": str(e)}))
        else:
            print(f"ERRO: armazenamento de artefatos não configurado: {e}", file=sys.stderr)
        return 2
    except ast.ErroArmazenamentoArtefato as e:
        if args.json:
            print(json.dumps({"status": "ERRO_ARMAZENAMENTO", "motivo": e.motivo}))
        else:
            print(f"ERRO: falha ao acessar o armazenamento: {e.motivo}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"status": "OK", **agregado}))
    else:
        print(f"OK — {agregado['rodadas']} rodada(s), "
              f"{agregado['inspecionados']} inspecionado(s), "
              f"{agregado['excluidos']} excluído(s), "
              f"{agregado['falhas']} falha(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
