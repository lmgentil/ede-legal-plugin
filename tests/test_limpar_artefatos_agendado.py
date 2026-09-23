#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_limpar_artefatos_agendado.py — regressão do entrypoint standalone
de limpeza agendada (Gate 6.6-E, continuação, ADR-0019).

Só usa fake em memória (Gate 6.6-E §43) — nenhum teste de unidade toca
rede. `executar()` é o núcleo testável (sem `sys.exit`); `main()` só
adapta isso a código de saída/stdout, coberto separadamente."""
import datetime as dt
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import artifact_storage as ast  # noqa: E402
import limpar_artefatos_agendado as lae  # noqa: E402


class _FakeTransporte:
    def __init__(self):
        self.objetos = {}
        self.chamadas_excluir = 0

    def enviar(self, object_name, dados, content_type, metadata):
        self.objetos[object_name] = (dados, content_type, dict(metadata))

    def assinar_url(self, *a, **k):
        raise AssertionError("limpeza agendada nunca deveria assinar URL")

    def excluir(self, object_name):
        self.chamadas_excluir += 1
        self.objetos.pop(object_name, None)
        return True

    def listar(self, prefixo, limite):
        nomes = sorted(n for n in self.objetos if n.startswith(prefixo))[:limite]
        return [(n, self.objetos[n][2]) for n in nomes]


def _inserir_objeto_velho(transporte, artefato_id, idade_segundos, agora):
    """`expires_at` (não só `created_at`) é o campo decisivo desde o
    hardening pós-fechamento do Gate 6.6-E — objeto sem ele é ignorado
    por fail-safe, nunca excluído."""
    criado_em = agora - dt.timedelta(seconds=idade_segundos)
    expira_em = criado_em + dt.timedelta(seconds=ast.TTL_DOWNLOAD_SEGUNDOS)
    nome = ast._nome_objeto(artefato_id)
    transporte.objetos[nome] = (
        b"x", ast.CONTENT_TYPE_DOCX,
        {"artifact_id": artefato_id, "created_at": criado_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "expires_at": expira_em.strftime("%Y-%m-%dT%H:%M:%SZ")},
    )


def test_executar_usa_o_transporte_do_ambiente(monkeypatch):
    transporte = _FakeTransporte()
    monkeypatch.setattr(ast, "obter_transporte_do_ambiente", lambda env: transporte)
    agregado = lae.executar({
        ast.ENV_ARTEFATOS_GCS_BUCKET: "b",
        ast.ENV_ARTEFATOS_SIGNER_SA: "sa@x.iam.gserviceaccount.com",
    })
    assert agregado == {"rodadas": 1, "inspecionados": 0, "excluidos": 0, "falhas": 0}


def test_executar_repete_ate_esgotar_o_backlog(monkeypatch):
    """Backlog maior que o teto por rodada -- `executar()` continua
    chamando até uma rodada não encher o teto (ou até
    MAX_RODADAS_POR_EXECUCAO)."""
    transporte = _FakeTransporte()
    monkeypatch.setattr(ast, "obter_transporte_do_ambiente", lambda env: transporte)
    agora = dt.datetime.now(dt.timezone.utc)
    total = ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA + 3
    for i in range(total):
        _inserir_objeto_velho(transporte, f"obj{i:029d}", 100000, agora)

    agregado = lae.executar({
        ast.ENV_ARTEFATOS_GCS_BUCKET: "b",
        ast.ENV_ARTEFATOS_SIGNER_SA: "sa@x.iam.gserviceaccount.com",
    })
    assert agregado["rodadas"] == 2  # cheia + parcial
    assert agregado["excluidos"] == total
    assert transporte.objetos == {}


def test_executar_respeita_teto_de_rodadas_por_execucao(monkeypatch):
    """Mesmo com backlog maior que MAX_RODADAS_POR_EXECUCAO x teto por
    rodada, esta execução para no teto -- a próxima execução agendada
    continua de onde esta parou (nunca uma execução única sem limite)."""
    transporte = _FakeTransporte()
    monkeypatch.setattr(ast, "obter_transporte_do_ambiente", lambda env: transporte)
    agora = dt.datetime.now(dt.timezone.utc)
    total = lae.MAX_RODADAS_POR_EXECUCAO * ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA + 5
    for i in range(total):
        _inserir_objeto_velho(transporte, f"obj{i:029d}", 100000, agora)

    agregado = lae.executar({
        ast.ENV_ARTEFATOS_GCS_BUCKET: "b",
        ast.ENV_ARTEFATOS_SIGNER_SA: "sa@x.iam.gserviceaccount.com",
    })
    assert agregado["rodadas"] == lae.MAX_RODADAS_POR_EXECUCAO
    assert agregado["excluidos"] == lae.MAX_RODADAS_POR_EXECUCAO * ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA
    assert len(transporte.objetos) == 5  # sobra fica para a próxima execução


def test_configuracao_ausente_e_codigo_de_saida_dois(monkeypatch, capsys):
    monkeypatch.setattr(ast, "obter_transporte_do_ambiente",
                         lambda env: (_ for _ in ()).throw(ast.ErroConfiguracaoArtefato("x")))
    monkeypatch.setattr(sys, "argv", ["limpar_artefatos_agendado.py"])
    codigo = lae.main()
    assert codigo == 2
