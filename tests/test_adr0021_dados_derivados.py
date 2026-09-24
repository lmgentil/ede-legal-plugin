#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADR-0021 — dados derivados pelo sistema no finalizador MCP (V1).

Core: LOCAL_DATA em America/Bahia; publicação derivada da
disponibilização; trava de cobertura do calendário (PEND-017);
proveito econômico em Decimal; redação da tempestividade compartilhada.

Finalizador V1: recusa os campos derivados vindos do host; Topic Matrix
continua só SIM/NÃO; tempestividade (pendência, intempestivo, fora da
cobertura); DataJud injetado (normal, indisponível, confirmação,
divergência, não encontrado); gratuidade sem gate com aviso; proveito
econômico; zonas genéricas; contrato legado inalterado.

Render real (docx_real, Modelo V1 local): tópico 2.6 sem "R$ R$"
(PEND-018), zona de composição do proveito preenchida, aviso da
gratuidade, endereçamento confirmado pelo advogado.

Nenhum teste chama a API real do DataJud.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "mcp_server"))
sys.path.insert(0, str(BASE / "tests"))
sys.path.insert(0, str(BASE / "skills" / "calendario-forense-tjba-2026" / "scripts"))

import calcular_tempestividade as ct  # noqa: E402
import dados_derivados as dd  # noqa: E402
import datajud_client  # noqa: E402
import finalizar_peca as fp  # noqa: E402
import gerar_contestacao as gc  # noqa: E402
import modelo_oficial_versoes as mov  # noqa: E402
import preparar_contestacao as pc  # noqa: E402
import proveito_economico as pe  # noqa: E402
import tempestividade_texto as tt  # noqa: E402
import test_topic_matrix_v1 as T  # noqa: E402
import topic_matrix as tm  # noqa: E402

BAHIA = ZoneInfo("America/Bahia")
HOJE = datetime(2026, 9, 10, 12, 0, tzinfo=BAHIA)
CAP = T.CAP
MARCO = {"tipo": "DISPONIBILIZACAO", "data": "01/09/2026"}
PEDIDOS_CASO_REAL = [
    {"descricao": "declaração de inexistência do débito", "valor": "R$ 2.097,63", "fonte": "Petição inicial"},
    {"descricao": "indenização por danos morais", "valor": "R$ 12.900,00", "fonte": "Petição inicial"},
]


# ============================================================ Core: LOCAL_DATA

def test_zoneinfo_america_bahia_resolve_no_runtime():
    z = ZoneInfo("America/Bahia")
    assert datetime(2026, 9, 10, 12, tzinfo=z).utcoffset().total_seconds() == -3 * 3600


@pytest.mark.parametrize("agora, esperado", [
    (datetime(2026, 9, 1, 15, 0, tzinfo=BAHIA), "Salvador, 1º de setembro de 2026"),
    (datetime(2026, 9, 24, 9, 0, tzinfo=BAHIA), "Salvador, 24 de setembro de 2026"),
    # 02:30 UTC de 01/10 ainda é 30/09 em Salvador: nunca a data UTC.
    (datetime(2026, 10, 1, 2, 30, tzinfo=timezone.utc), "Salvador, 30 de setembro de 2026"),
    (datetime(2026, 3, 1, 0, 1, tzinfo=BAHIA), "Salvador, 1º de março de 2026"),
])
def test_local_data_no_padrao_do_modelo(agora, esperado):
    assert dd.gerar_local_data(agora) == esperado
    import validate_placeholder_semantics as vs
    assert vs._validar_local_data(esperado) == []


def test_local_data_recusa_data_sem_fuso():
    with pytest.raises(ValueError):
        dd.gerar_local_data(datetime(2026, 9, 1, 12, 0))


# ================================================ Core: publicação e cobertura

@pytest.mark.parametrize("disponibilizacao, publicacao", [
    (date(2026, 9, 11), date(2026, 9, 14)),   # sexta -> segunda
    (date(2026, 10, 9), date(2026, 10, 13)),  # sexta -> 12/10 feriado -> terça
    (date(2026, 1, 5), date(2026, 1, 21)),    # recesso e suspensão até 20/01
    (date(2026, 9, 2), date(2026, 9, 3)),     # quarta -> quinta
])
def test_publicacao_e_primeiro_dia_util_seguinte(disponibilizacao, publicacao):
    assert ct.derivar_publicacao(disponibilizacao) == (publicacao, None)


@pytest.mark.parametrize("disponibilizacao", [date(2025, 12, 10), date(2026, 12, 18), date(2026, 12, 21)])
def test_publicacao_fora_da_cobertura_e_recusada(disponibilizacao):
    publicacao, motivo = ct.derivar_publicacao(disponibilizacao)
    assert publicacao is None and "cobert" in motivo


def test_trava_de_cobertura_so_no_fluxo_que_a_pede():
    args = dict(data_pratica_ato="2026-12-10", data_publicacao="2026-12-01", prazo_legal_dias=15,
                tipo_prazo="uteis", fundamento_normativo="art. 335 do CPC")
    com = ct.calcular_tempestividade(**args, verificar_cobertura=True)
    assert com.status == ct.PENDENTE and "ultrapassa" in com.motivo_pendencia
    # fluxo local da Skill: comportamento anterior preservado (PEND-017 segue aberta lá)
    assert ct.calcular_tempestividade(**args).status == ct.TEMPESTIVO


def test_calendario_declara_janela_ate_19_de_dezembro():
    cal = ct.carregar_calendario()
    assert ct.cobertura_do_calendario(cal) == (date(2026, 1, 1), date(2026, 12, 19))


def test_redacao_da_tempestividade_e_a_mesma_nos_dois_fluxos():
    assert gc._redigir_tempestividade_natural is tt._redigir_tempestividade_natural


# ======================================================= Core: proveito econômico

def test_proveito_do_caso_real_em_decimal():
    r = pe.calcular_proveito(PEDIDOS_CASO_REAL, "R$ 15.000,00")
    assert r.total == Decimal("14997.63") and r.valor_da_causa == Decimal("15000.00")
    assert r.diferenca == Decimal("2.37")
    assert r.cumulacao_economica
    resumo = r.resumo()
    for trecho in ("R$ 14.997,63", "R$ 15.000,00", "diferença de R$ 2,37"):
        assert trecho in resumo
    assert "relevante" not in resumo.lower() and "material" not in resumo.lower()  # sem juízo em Python


def test_pedido_sem_valor_nunca_vira_zero():
    pedidos = PEDIDOS_CASO_REAL + [{"descricao": "multa diária", "valor": None, "fonte": "Petição inicial"}]
    r = pe.calcular_proveito(pedidos, "R$ 15.000,00")
    assert r.total == Decimal("14997.63") and r.pedidos_sem_valor == ("multa diária",)
    assert "1 pedido(s) sem valor quantificado" in r.resumo()


@pytest.mark.parametrize("pedido", [
    {"descricao": "x", "valor": "1500", "fonte": "inicial"},
    {"descricao": "x", "valor": "R$ 1.500,00", "fonte": ""},
    {"descricao": "", "valor": "R$ 1.500,00", "fonte": "inicial"},
])
def test_pedido_malformado_e_recusado(pedido):
    with pytest.raises(pe.EntradaProveitoInvalida):
        pe.calcular_proveito([pedido], "R$ 15.000,00")


def test_formatar_brl():
    assert pe.formatar_brl(Decimal("1234567.8")) == "R$ 1.234.567,80"
    assert pe.formatar_brl(Decimal("2.37"), com_simbolo=False) == "2,37"


# ================================================= finalizador V1 (sem .docx)

class _Resolvedor:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, numero, cache_path=None):
        self.chamadas.append((numero, cache_path))
        r = self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]
        if isinstance(r, Exception):
            raise r
        return {"juizo": r}


INDISPONIVEL = datajud_client.JuizoResolutionError("DataJud indisponível", codigo=datajud_client.TAG_INDISPONIVEL)
NAO_ENCONTRADO = datajud_client.JuizoResolutionError("processo não encontrado no DataJud")
AUTH = datajud_client.JuizoResolutionError("credencial", codigo=datajud_client.TAG_ERRO_AUTENTICACAO)


@pytest.fixture
def v1(monkeypatch):
    for var in ("EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT",
                "EDE_MODELO_OFICIAL_GCS_GENERATION", "EDE_MODELO_OFICIAL_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", mov.VERSAO_V1.modelo_sha256)
    monkeypatch.setattr(fp, "_agora", lambda: HOJE)
    resolvedor = _Resolvedor([T.JUIZO_FAKE])
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: resolvedor)
    return resolvedor


def _entrada(**extra):
    base = {"capability_id": CAP, "placeholders": T._placeholders(), "topicos": T._todos("NAO"),
            "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": {}, "marco_tempestividade": MARCO}
    base.update(extra)
    return base


@pytest.mark.parametrize("campo", sorted(fp.DERIVADOS_ADR_0021))
def test_v1_recusa_campo_derivado_vindo_do_host(v1, campo):
    ph = {**T._placeholders(), campo: "R$ 1,00" if "VALOR" in campo else "Salvador, qualquer"}
    r = fp.finalizar_peca(_entrada(placeholders=ph))
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED" and campo in r.motivo


@pytest.mark.parametrize("estado", sorted(T.MANIFESTO["estados_reservados_ao_core"]))
def test_v1_recusa_estado_reservado_ao_core(v1, estado):
    r = fp.finalizar_peca(_entrada(estado_processual={estado: True}))
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


@pytest.mark.parametrize("campo, valor", [
    ("topicos", {"inaplicabilidade_cdc": "01/09/2026"}),
    ("fatos_publicos", {"corte_efetivo": "01/09/2026"}),
    ("topicos", {"marco_tempestividade": "SIM"}),
])
def test_topic_matrix_continua_so_sim_nao(v1, campo, valor):
    base = _entrada()
    base[campo] = {**base[campo], **valor}
    r = fp.finalizar_peca(base)
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


def test_manifesto_nao_pode_declarar_entrada_factual_que_nao_seja_sim_nao():
    m = json.loads(json.dumps(T.MANIFESTO))
    m["entradas_factuais_publicas"].append({"chave": "data_x", "tipo": "DATA", "alimenta_fato": "X"})
    with pytest.raises(tm.ManifestoIncompativel):
        tm.verificar_compatibilidade(m, T.CATALOGO)


def test_sem_marco_pede_so_a_data_de_disponibilizacao(v1):
    r = fp.finalizar_peca(_entrada(marco_tempestividade=None))
    assert r.status == "NEEDS_INPUT" and r.stage == "tempestividade"
    assert len(r.pendencias) == 1 and "data de disponibilização" in r.pendencias[0]
    assert r.documento_bytes is None


def test_sem_marco_e_datajud_indisponivel_pergunta_tudo_de_uma_vez(v1, monkeypatch):
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: _Resolvedor([INDISPONIVEL]))
    r = fp.finalizar_peca(_entrada(marco_tempestividade=None))
    assert r.status == "NEEDS_INPUT" and len(r.pendencias) == 2
    assert any("disponibilização" in p for p in r.pendencias)
    assert any("DataJud" in p for p in r.pendencias)


@pytest.mark.parametrize("marco", [
    {"tipo": "CITACAO", "data": "01/09/2026"},
    {"tipo": "DISPONIBILIZACAO", "data": "2026-09-01"},
    {"tipo": "DISPONIBILIZACAO", "data": "31/02/2026"},
    {"tipo": "DISPONIBILIZACAO", "data": "11/09/2026"},  # depois de "hoje"
])
def test_marco_invalido_e_recusado(v1, marco):
    r = fp.finalizar_peca(_entrada(marco_tempestividade=marco))
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


def test_intempestivo_nao_gera_peca_nem_texto_de_intempestividade(v1):
    r = fp.finalizar_peca(_entrada(marco_tempestividade={"tipo": "DISPONIBILIZACAO", "data": "01/07/2026"}))
    assert r.status == "NEEDS_INPUT" and r.stage == "tempestividade"
    assert r.documento_bytes is None and r.download_url is None
    texto = " ".join(r.pendencias)
    # 02 e 03/07 são feriados no calendário TJBA: publicação em 06/07
    for trecho in ("01/07/2026", "06/07/2026", "encerrou-se em 27/07/2026", "A peça não foi gerada"):
        assert trecho in texto
    assert "é intempestiva" not in texto
    assert not T.TERMOS_INTERNOS.search(texto)


def test_marco_fora_da_cobertura_do_calendario_e_recusado(v1):
    r = fp.finalizar_peca(_entrada(marco_tempestividade={"tipo": "DISPONIBILIZACAO", "data": "10/12/2025"}))
    assert r.status == "REFUSED" and r.error_code == "DERIVED_DATA_UNAVAILABLE" and r.stage == "tempestividade"


def test_datajud_normal_passa_da_etapa_de_derivados_sem_cache_persistente(v1):
    r = fp.finalizar_peca(_entrada())
    # sem Modelo Oficial provisionado neste teste: para na prontidão do
    # modelo, DEPOIS de derivar juízo/tempestividade/data sem pendência.
    assert r.status == "REFUSED" and r.error_code == "OFFICIAL_MODEL_NOT_READY"
    numero, cache_path = v1.chamadas[0]
    assert numero == T._placeholders()["NUMERO_PROCESSO"]
    assert cache_path is not None and BASE not in Path(cache_path).parents


def test_datajud_indisponivel_sem_confirmacao_pede_confirmacao(v1, monkeypatch):
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: _Resolvedor([INDISPONIVEL]))
    r = fp.finalizar_peca(_entrada())
    assert r.status == "NEEDS_INPUT" and r.stage == "enderecamento"
    assert "indisponível" in r.pendencias[0]


def test_datajud_indisponivel_com_confirmacao_segue(v1, monkeypatch):
    resolvedor = _Resolvedor([INDISPONIVEL])
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: resolvedor)
    r = fp.finalizar_peca(_entrada(juizo_confirmado_advogado=T.JUIZO_FAKE))
    assert r.error_code == "OFFICIAL_MODEL_NOT_READY"  # passou do endereçamento
    assert len(resolvedor.chamadas) == 1  # tentou o DataJud de novo nesta chamada


def test_datajud_de_volta_e_divergente_nunca_escolhe_sozinho(v1):
    r = fp.finalizar_peca(_entrada(juizo_confirmado_advogado="AO JUÍZO DA OUTRA VARA DA COMARCA DE ILHÉUS"))
    assert r.status == "NEEDS_INPUT" and r.stage == "enderecamento" and "diverge" in r.pendencias[0]


def test_datajud_de_volta_e_igual_a_confirmacao_segue(v1):
    r = fp.finalizar_peca(_entrada(juizo_confirmado_advogado=T.JUIZO_FAKE.lower()))
    assert r.error_code == "OFFICIAL_MODEL_NOT_READY"


@pytest.mark.parametrize("erro", [NAO_ENCONTRADO, AUTH])
def test_falha_nao_transitoria_do_datajud_nao_abre_excecao_humana(v1, monkeypatch, erro):
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: _Resolvedor([erro]))
    r = fp.finalizar_peca(_entrada(juizo_confirmado_advogado=T.JUIZO_FAKE))
    assert r.status == "REFUSED" and r.error_code == "DERIVED_DATA_UNAVAILABLE" and r.stage == "enderecamento"


def test_gratuidade_sim_sem_decisao_concessiva_nao_bloqueia(v1):
    topicos = {**T._todos("NAO"), "revogacao_gratuidade": "SIM"}
    r = fp.finalizar_peca(_entrada(topicos=topicos))
    assert r.status != "NEEDS_INPUT"
    trad = tm.traduzir(T.MANIFESTO, T.CATALOGO, topicos, {"corte_efetivo": "NAO"}, {})
    assert trad.status == "OK"
    assert trad.avisos == ("Não foi localizado nos documentos o suporte documental ao deferimento da "
                           "gratuidade de justiça.",)
    com_decisao = tm.traduzir(T.MANIFESTO, T.CATALOGO, topicos, {"corte_efetivo": "NAO"},
                              {"GRATUIDADE_CONCEDIDA": True})
    assert com_decisao.status == "OK" and com_decisao.avisos == ()


def test_impugnacao_sim_exige_pedidos(v1):
    topicos = {**T._todos("NAO"), "impugnacao_valor_causa": "SIM"}
    r = fp.finalizar_peca(_entrada(topicos=topicos))
    assert r.status == "REFUSED" and r.error_code == "MISSING_REQUIRED_FIELD" and r.stage == "valor_da_causa"


def test_impugnacao_sim_sem_nenhum_valor_quantificado(v1):
    topicos = {**T._todos("NAO"), "impugnacao_valor_causa": "SIM"}
    pedidos = [{"descricao": "multa diária", "valor": None, "fonte": "Petição inicial"}]
    r = fp.finalizar_peca(_entrada(topicos=topicos, pedidos_economicos=pedidos))
    assert r.status == "REFUSED" and r.error_code == "MISSING_REQUIRED_FIELD"


def test_pedidos_sem_impugnacao_e_incoerente(v1):
    r = fp.finalizar_peca(_entrada(pedidos_economicos=PEDIDOS_CASO_REAL))
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED" and r.stage == "valor_da_causa"


def test_zona_nao_autorizada_e_recusada(v1):
    r = fp.finalizar_peca(_entrada(zonas={"conteudo": {"ZONA_INVENTADA": {"conteudo": "x", "fatos": []}},
                                          "base_documental": []}))
    assert r.status == "REFUSED" and r.stage == "zonas"


def test_zona_sem_base_documental_e_recusada(v1):
    zona = {"ZONA_METODOLOGIA_APURACAO": {"conteudo": "Texto com 2.003,88 kWh.", "fatos": []}}
    r = fp.finalizar_peca(_entrada(zonas={"conteudo": zona, "base_documental": []}))
    assert r.status == "REFUSED" and r.stage == "zonas"


def test_zona_de_topico_excluido_e_recusada(v1):
    zona = {"ZONA_METODOLOGIA_APURACAO": {
        "conteudo": "Apurados 2.003,88 kWh.",
        "fatos": [{"tipo": "kwh", "valor": "2.003,88", "unidade": "kWh", "fonte": "Memorial", "natureza": "documental"}]}}
    base = [{"fact": "Devido 2.003,88 kWh.", "source_document": "Memorial"}]
    r = fp.finalizar_peca(_entrada(zonas={"conteudo": zona, "base_documental": base},
                                   estado_processual={"METODOLOGIA_APURACAO_DOCUMENTADA": True}))
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


# ============================================================ contrato legado

def test_legado_recusa_as_entradas_novas(monkeypatch):
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", mov.VERSAO_LEGADA.modelo_sha256)
    for campo, valor in (("marco_tempestividade", MARCO), ("pedidos_economicos", PEDIDOS_CASO_REAL),
                         ("zonas", {"conteudo": {}, "base_documental": [{"fact": "x", "source_document": "y"}]}),
                         ("juizo_confirmado_advogado", "AO JUÍZO DA VARA")):
        r = fp.finalizar_peca({"capability_id": CAP, "placeholders": {}, campo: valor})
        assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED", campo


def test_legado_nunca_consulta_datajud_nem_deriva_campos(monkeypatch):
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", mov.VERSAO_LEGADA.modelo_sha256)

    def proibido():
        raise AssertionError("contrato legado não pode chamar o DataJud")
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", proibido)
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": T._placeholders_legado(),
                           "block_decisions": {}, "estado_processual": {}})
    assert r.status == "REFUSED" and r.stage in ("input_validation", "production_final_validation",
                                                  "official_model_readiness")


# ================================================================ schema MCP

def test_schema_publico_tem_os_campos_novos_e_topicos_so_sim_nao():
    import server
    s = server.EdeFinalizarPecaEntrada.model_json_schema()
    props = s["properties"]
    for campo in ("marco_tempestividade", "pedidos_economicos", "zonas", "juizo_confirmado_advogado"):
        assert campo in props
    assert props["topicos"]["additionalProperties"]["enum"] == ["SIM", "NAO"]
    assert props["fatos_publicos"]["additionalProperties"]["enum"] == ["SIM", "NAO"]
    marco = s["$defs"]["MarcoTempestividade"]["properties"]
    assert marco["tipo"]["const"] == "DISPONIBILIZACAO" and marco["data"]["pattern"]
    with pytest.raises(Exception):
        server.EdeFinalizarPecaEntrada(capability_id=CAP, marco_tempestividade={"tipo": "CITACAO", "data": "01/09/2026"})


def test_telemetria_espelha_estagios_e_codigos():
    import auth_logging as telemetria
    assert telemetria.ESTAGIOS_FINALIZACAO == fp.ETAPAS
    assert telemetria.CODIGOS_ERRO_FINALIZACAO == fp.CODIGOS_ERRO


def test_preparacao_orienta_o_host_a_nao_perguntar_o_derivavel():
    publico = pc._montar_topic_matrix(T.MANIFESTO)
    assert [e["chave"] for e in publico["entradas_estruturadas"]] == [
        "marco_tempestividade", "pedidos_economicos", "zonas", "juizo_confirmado_advogado"]
    for termo in ("Nunca pergunte o juízo", "data da peça", "disponibilização"):
        assert termo in publico["orientacao"]
    assert all(t.keys() == {"chave", "nome_publico", "pergunta"} for t in publico["topicos"])


# ======================================================= render real (V1 local)

def _texto_docx(documento: bytes) -> str:
    x = zipfile.ZipFile(io.BytesIO(documento)).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", x))


@pytest.mark.docx_real
def test_valor_da_causa_sem_r_duplicado_e_com_zona_de_composicao(T_modelo):
    topicos = {**T._todos("NAO"), "impugnacao_valor_causa": "SIM"}
    ph = {**T._placeholders(), "VALOR_DA_CAUSA": "R$ 15.000,00"}
    base = [{"fact": "Pedidos da inicial: inexistência do débito de R$ 2.097,63 e danos morais estimados "
                     "em R$ 12.900,00; valor da causa R$ 15.000,00.", "source_document": "Petição inicial"}]
    zona = {"ZONA_COMPOSICAO_PROVEITO_ECONOMICO": {
        "conteudo": "a) a declaração de inexistência do débito de R$ 2.097,63; e b) a indenização por danos "
                    "morais, estimada em R$ 12.900,00.",
        "fatos": [{"tipo": "debito", "valor": "R$ 2.097,63", "unidade": "R$", "fonte": "Petição inicial",
                   "natureza": "documental"},
                  {"tipo": "dano_moral", "valor": "R$ 12.900,00", "unidade": "R$", "fonte": "Petição inicial",
                   "natureza": "documental"}]}}
    r = fp.finalizar_peca(_entrada(placeholders=ph, topicos=topicos, pedidos_economicos=PEDIDOS_CASO_REAL,
                                   zonas={"conteudo": zona, "base_documental": base}))
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    texto = _texto_docx(r.documento_bytes)
    assert not re.search(r"R\$\s*R\$", texto)  # PEND-018
    assert "montante de R$ 15.000,00," in texto
    assert "valor da causa para R$ 14.997,63," in texto
    depois = texto[texto.index("In casu, a petição inicial cumula:"):]
    assert "a) a declaração de inexistência do débito de R$ 2.097,63" in depois.split("\n")[1]
    aviso = [a for a in r.dados_nao_bloqueantes if a.startswith("Impugnação ao valor da causa:")]
    assert aviso and "diferença de R$ 2,37" in aviso[0]
    assert "Salvador, 10 de setembro de 2026" in texto
    assert T.JUIZO_FAKE in texto
    assert "A presente Contestação é tempestiva" in texto and "02/09/2026" in texto


@pytest.mark.docx_real
def test_gratuidade_sim_sem_decisao_gera_peca_com_aviso(T_modelo):
    topicos = {**T._todos("NAO"), "revogacao_gratuidade": "SIM"}
    r = fp.finalizar_peca(_entrada(topicos=topicos))
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    assert "REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA" in _texto_docx(r.documento_bytes).upper()
    assert ("Não foi localizado nos documentos o suporte documental ao deferimento da gratuidade de justiça."
            in r.dados_nao_bloqueantes)


@pytest.mark.docx_real
def test_endereçamento_confirmado_quando_datajud_indisponivel(T_modelo, monkeypatch):
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo", lambda: _Resolvedor([INDISPONIVEL]))
    confirmado = "AO JUÍZO DA VARA CONFIRMADA DA COMARCA DE VALENÇA"
    r = fp.finalizar_peca(_entrada(juizo_confirmado_advogado=confirmado))
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    assert confirmado in _texto_docx(r.documento_bytes)
    assert any("confirmado pelo advogado" in a for a in r.dados_nao_bloqueantes)


@pytest.fixture
def T_modelo(v1, monkeypatch):
    caminho = T._caminho_modelo_v1()
    monkeypatch.setenv("EDE_MODELO_OFICIAL_PATH", str(caminho))
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: T._TransporteFake())
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: "https://ede.example.test")
    return caminho
