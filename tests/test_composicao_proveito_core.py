#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manifesto 1.3.0 — composição do proveito econômico produzida pelo Core.

Achado do teste cross-client da 0.19.0 (mesmos documentos, mesmas 14
decisões): o Claude.ai escreveu a composição após "In casu, a petição
inicial cumula:" e chegou a R$ 14.997,63; o ChatGPT omitiu a zona
(parágrafo vazio no DOCX) e seus pedidos somaram R$ 12.097,63. O Core
aceitava as duas coisas. Agora:

- a composição sai de `pedidos_economicos` (natureza + valor) e do valor
  da causa, pelo MESMO resultado Decimal que dá a retificação;
- o host não envia mais essa zona (recusa estruturada);
- com a impugnação e o dano moral SIM, o pedido DANO_MORAL confere, em
  Decimal, com VALOR_DANO_MORAL_PRETENDIDO (recusa estruturada antes do
  render).

Black-box pela camada MCP (reaproveita o ambiente e o host ingênuo de
`test_compatibilidade_host_mcp.py`); os testes `docx_real` vão até o DOCX
com o Modelo Oficial V1 real.
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "mcp_server"))
sys.path.insert(0, str(BASE / "tests"))

import finalizar_peca as fp  # noqa: E402
import legal_readiness as lr  # noqa: E402
import proveito_economico as pe  # noqa: E402
import test_compatibilidade_host_mcp as H  # noqa: E402
import test_topic_matrix_v1 as T  # noqa: E402
from test_compatibilidade_host_mcp import ambiente, anyio_backend, cliente, modelo_v1_local  # noqa: E402,F401

ZONA = "ZONA_COMPOSICAO_PROVEITO_ECONOMICO"
IN_CASU = "In casu, a petição inicial cumula:"
TEXTO_CASO_REAL = ("A soma dos pedidos cumulados, débito de R$ 2.097,63 e danos morais estimados em "
                   "R$ 12.900,00, alcança R$ 14.997,63, e não os R$ 15.000,00 atribuídos à causa.")


def _pedido(natureza, valor, descricao="pedido da inicial"):
    return {"descricao": descricao, "natureza": natureza, "valor": valor, "fonte": "documento_01.pdf"}


PEDIDOS_REGRESSAO = [
    _pedido("DEBITO", "R$ 2.097,63", "declaração de inexistência do débito"),
    _pedido("DANO_MORAL", "R$ 12.900,00", "indenização por danos morais"),
    _pedido("OUTRO", None, "multa diária de R$ 300,00"),
]


# ================================================= Core: cálculo e redação

def test_regressao_exata_no_calculo():
    r = pe.calcular_proveito(PEDIDOS_REGRESSAO, "R$ 15.000,00")
    assert r.total == Decimal("14997.63") and r.diferenca == Decimal("2.37")
    assert r.pedidos_sem_valor == ("multa diária de R$ 300,00",) and r.cumulacao_economica
    assert r.texto_composicao() == TEXTO_CASO_REAL
    assert "diferença de R$ 2,37" in r.resumo()


def test_pedido_outro_sem_valor_nao_entra_na_soma_nem_na_frase():
    com = pe.calcular_proveito(PEDIDOS_REGRESSAO, "R$ 15.000,00")
    sem = pe.calcular_proveito(PEDIDOS_REGRESSAO[:2], "R$ 15.000,00")
    assert com.total == sem.total and com.texto_composicao() == sem.texto_composicao()
    assert "300" not in com.texto_composicao()


@pytest.mark.parametrize("pedidos, causa, esperado", [
    ([_pedido("DEBITO", "R$ 100,00"), _pedido("DEBITO", "R$ 50,00"), _pedido("OUTRO", "R$ 10,00")], "R$ 200,00",
     "A soma dos pedidos cumulados, débitos que somam R$ 150,00 e outro pedido de R$ 10,00, alcança R$ 160,00, "
     "e não os R$ 200,00 atribuídos à causa."),
    ([_pedido("DANO_MORAL", "R$ 5.000,00"), _pedido("OUTRO", "R$ 1,00"), _pedido("OUTRO", "R$ 2,00"),
      _pedido("DEBITO", "R$ 3,00")], "R$ 5.006,00",
     "A soma dos pedidos cumulados, débito de R$ 3,00, danos morais estimados em R$ 5.000,00 e outros pedidos "
     "que somam R$ 3,00, alcança R$ 5.006,00, mesmo valor atribuído à causa."),
])
def test_composicao_e_montada_so_da_natureza_e_do_valor(pedidos, causa, esperado):
    r = pe.calcular_proveito(pedidos, causa)
    assert r.texto_composicao() == esperado
    # A descrição livre do host nunca entra no texto.
    assert "pedido da inicial" not in r.texto_composicao()


# ============================================= MCP: contrato 1.3.0 do host

@pytest.mark.anyio
async def test_host_contract_publica_a_composicao_como_calculada(cliente):
    pacote = await H._preparar(cliente)
    tm = pacote["topic_matrix"]
    assert ZONA in tm["campos_calculados_pelo_sistema"]
    assert ZONA not in {p["parte"] for p in tm["partes_redigiveis_llm"]}
    pedidos = next(e for e in tm["entradas_estruturadas"] if e["chave"] == "pedidos_economicos")
    assert pedidos["naturezas"] == ["DEBITO", "DANO_MORAL", "OUTRO"] and pedidos["natureza_obrigatoria"] is True
    assert "R$ 10.000,00" not in json.dumps(tm, ensure_ascii=False)
    ferramentas = {t.name: t for t in (await cliente.list_tools()).tools}
    pedido_schema = ferramentas["ede_finalizar_peca"].input_schema["$defs"]["PedidoEconomico"]
    assert set(pedido_schema["properties"]["natureza"]["anyOf"][0]["enum"]) == {"DEBITO", "DANO_MORAL", "OUTRO"}


def _entrada(pacote, **mudancas):
    entrada = H._host_ingenuo(pacote, H.TOPICOS_CASO_REAL, H.COMPROVADOS_CASO_REAL)
    entrada["pedidos_economicos"] = PEDIDOS_REGRESSAO
    entrada.update(mudancas)
    return entrada


@pytest.mark.anyio
async def test_host_que_envia_a_zona_antiga_e_recusado(cliente):
    pacote = await H._preparar(cliente)
    zona = {"conteudo": "A soma dos pedidos alcança R$ 12.097,63.",
            "fatos": [{"tipo": "total", "valor": "R$ 12.097,63", "fonte": "documento_01.pdf", "natureza": "documental"}]}
    r = await H._finalizar(cliente, _entrada(pacote, zonas={
        "conteudo": {ZONA: zona}, "base_documental": [{"fact": "x", "source_document": "documento_01.pdf"}]}))
    assert r["status"] == "REFUSED" and r["stage"] == "zonas" and r["error_code"] == "INPUT_VALIDATION_FAILED"
    assert r["campos_calculados_enviados"] == [ZONA]


@pytest.mark.anyio
async def test_dano_moral_divergente_entre_pedidos_e_placeholder_e_recusado_antes_do_render(cliente):
    pacote = await H._preparar(cliente)
    pedidos = [PEDIDOS_REGRESSAO[0], _pedido("DANO_MORAL", "R$ 10.000,00"), PEDIDOS_REGRESSAO[2]]
    entrada = _entrada(pacote, pedidos_economicos=pedidos)
    assert entrada["placeholders"]["VALOR_DANO_MORAL_PRETENDIDO"] == "R$ 12.900,00"
    r = await H._finalizar(cliente, entrada)
    assert r["status"] == "REFUSED" and r["stage"] == "valor_da_causa" and "download_url" not in r
    assert r["inconsistencias_valores"] == [{"campo": "VALOR_DANO_MORAL_PRETENDIDO", "motivo": "DIVERGE_DOS_PEDIDOS",
                                             "valor_informado": "R$ 12.900,00", "valor_nos_pedidos": "R$ 10.000,00"}]


@pytest.mark.anyio
@pytest.mark.parametrize("pedidos, motivo", [
    ([_pedido("DEBITO", "R$ 2.097,63"), _pedido("OUTRO", "R$ 12.900,00")], "DANO_MORAL_AUSENTE"),
    ([_pedido("DEBITO", "R$ 2.097,63"), _pedido("DANO_MORAL", "R$ 12.900,00"), _pedido("DANO_MORAL", "R$ 1,00")],
     "DANO_MORAL_AMBIGUO"),
])
async def test_dano_moral_sim_exige_exatamente_um_pedido_dano_moral(cliente, pedidos, motivo):
    pacote = await H._preparar(cliente)
    entrada = _entrada(pacote, pedidos_economicos=pedidos)
    entrada["placeholders"]["VALOR_DANO_MORAL_PRETENDIDO"] = "R$ 12.900,00"
    r = await H._finalizar(cliente, entrada)
    assert r["status"] == "REFUSED" and r["stage"] == "valor_da_causa"
    assert [i["motivo"] for i in r["inconsistencias_valores"]] == [motivo]


@pytest.mark.anyio
async def test_natureza_ausente_e_recusada(cliente):
    pacote = await H._preparar(cliente)
    pedidos = [{k: v for k, v in p.items() if k != "natureza"} for p in PEDIDOS_REGRESSAO]
    r = await H._finalizar(cliente, _entrada(pacote, pedidos_economicos=pedidos))
    assert r["status"] == "REFUSED" and r["stage"] == "valor_da_causa"
    assert r["error_code"] == "INPUT_VALIDATION_FAILED" and "natureza" in r["motivo"]


@pytest.mark.anyio
async def test_dano_moral_nao_quantificado_confere_com_pedido_sem_valor(cliente):
    pacote = await H._preparar(cliente)
    pedidos = [PEDIDOS_REGRESSAO[0], _pedido("DANO_MORAL", None), PEDIDOS_REGRESSAO[2]]
    entrada = _entrada(pacote, pedidos_economicos=pedidos)
    entrada["placeholders"]["VALOR_DANO_MORAL_PRETENDIDO"] = "a ser arbitrado pelo Juízo"
    r = await H._finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r  # passou da checagem cruzada


@pytest.mark.anyio
async def test_sem_dano_moral_sim_nao_ha_checagem_cruzada(cliente):
    pacote = await H._preparar(cliente)
    topicos = {**H.TOPICOS_CASO_REAL, "descabimento_dano_moral": "NAO"}
    entrada = H._host_ingenuo(pacote, topicos, H.COMPROVADOS_CASO_REAL)
    entrada["pedidos_economicos"] = [_pedido("DEBITO", "R$ 2.097,63"), _pedido("OUTRO", "R$ 12.900,00")]
    r = await H._finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


# ================================================== DOCX real (Modelo V1)

async def _gerar_docx(monkeypatch, entrada_fn):
    from mcp import Client
    import server
    monkeypatch.setattr(lr, "avaliar_corpus_rag", lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(fp, "_agora", lambda: H.HOJE)
    capturado = {}
    original = fp.finalizar_peca

    def _capturar(entrada):
        capturado["r"] = original(entrada)
        return capturado["r"]
    monkeypatch.setattr(fp, "finalizar_peca", _capturar)
    async with Client(server.mcp, raise_exceptions=True) as c:
        pacote = await H._preparar(c)
        r = await H._finalizar(c, entrada_fn(pacote))
    assert r["status"] == "OK", r
    return capturado["r"], T._texto(T._xml(capturado["r"].documento_bytes))


def _topico_2_6(texto: str) -> str:
    """Do título do tópico (numeração dinâmica: o número varia com as
    preliminares incluídas) até o pedido de retificação."""
    inicio = texto.index("DA IMPUGNAÇÃO AO VALOR DA CAUSA")
    return texto[inicio:texto.index("recolhimento da complementação", inicio)]


@pytest.mark.docx_real
@pytest.mark.anyio
async def test_regressao_do_caso_real_no_docx_sem_o_host_enviar_a_composicao(modelo_v1_local, monkeypatch):
    def _entrada_host(pacote):
        entrada = _entrada(pacote)
        entrada["placeholders"]["VALOR_DANO_MORAL_PRETENDIDO"] = "R$ 12.900,00"
        assert "zonas" not in entrada  # o host omite a antiga zona
        return entrada
    r, texto = await _gerar_docx(monkeypatch, _entrada_host)
    for valor in ("R$ 2.097,63", "R$ 12.900,00", "R$ 14.997,63"):
        assert valor in texto, valor
    assert "12.097,63" not in texto
    linhas = texto.split("\n")
    seguinte = linhas[linhas.index(IN_CASU) + 1]
    assert seguinte == TEXTO_CASO_REAL
    assert not seguinte.startswith("A exata definição")
    assert "retificar o valor da causa para R$ 14.997,63," in texto
    assert any("diferença de R$ 2,37" in a for a in r.dados_nao_bloqueantes)


@pytest.mark.docx_real
@pytest.mark.anyio
async def test_um_pedido_so_nao_compoe_cumulacao(modelo_v1_local, monkeypatch):
    def _entrada_host(pacote):
        topicos = {**H.TOPICOS_CASO_REAL, "descabimento_dano_moral": "NAO"}
        entrada = H._host_ingenuo(pacote, topicos, H.COMPROVADOS_CASO_REAL)
        entrada["pedidos_economicos"] = [_pedido("DEBITO", "R$ 2.097,63")]
        return entrada
    _, texto = await _gerar_docx(monkeypatch, _entrada_host)
    assert IN_CASU not in texto and "A soma dos pedidos cumulados" not in texto
    assert "retificar o valor da causa para R$ 2.097,63," in texto


@pytest.mark.docx_real
@pytest.mark.anyio
async def test_dois_hosts_com_os_mesmos_dados_estruturados_geram_o_mesmo_topico_economico(
        modelo_v1_local, monkeypatch):
    """Textos livres diferentes (sinopse, descrições dos pedidos), mesmos
    dados estruturados: o tópico 2.6 sai idêntico."""
    def _host(sinopse, descricoes):
        def _entrada_host(pacote):
            pedidos = [{**p, "descricao": d} for p, d in zip(PEDIDOS_REGRESSAO, descricoes)]
            entrada = _entrada(pacote, pedidos_economicos=pedidos)
            entrada["placeholders"]["VALOR_DANO_MORAL_PRETENDIDO"] = "R$ 12.900,00"
            entrada["placeholders"]["SINOPSE_FATOS"] = sinopse
            return entrada
        return _entrada_host
    _, texto_a = await _gerar_docx(monkeypatch, _host(
        "Síntese fictícia A dos fatos narrados.", ["inexistência do débito", "danos morais", "astreinte"]))
    _, texto_b = await _gerar_docx(monkeypatch, _host(
        "Síntese fictícia B, redigida por outro host.", ["débito", "dano moral pretendido", "multa diária"]))
    assert texto_a != texto_b
    assert _topico_2_6(texto_a) == _topico_2_6(texto_b)
    assert re.search(r"R\$ 14\.997,63", _topico_2_6(texto_a))
