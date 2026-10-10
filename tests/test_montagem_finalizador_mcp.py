"""
Gate de discoverability do host (0.21.x) — testes BLACK-BOX pela camada MCP.

Achado do teste real com o ChatGPT na 0.21.0: o host nunca chegou a chamar
`ede_finalizar_peca` (nenhum evento de dispatch no Homolog) e devolveu ao
advogado "finalização pendente de adequação dos campos ao contrato
técnico". Não soube montar `marco_tempestividade` e `pedidos_economicos`:
`descricao` era obrigatória sem constar de nenhuma orientação, `natureza`
era "obrigatória" na descrição e opcional no schema, e a orientação ficava
no fim de um pacote de mais de 100 KB.

Aqui o "host" só enxerga o que um cliente MCP novo enxerga: `tools/list`,
o pacote de `ede_preparar_contestacao`, os documentos (sintéticos), as 14
decisões e "Citação: 21/09/2026". Nenhum módulo do Core é importado para
montar a chamada — só as fixtures de ambiente (Modelo Oficial local,
DataJud/relógio simulados, armazenamento falso).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

import test_topic_matrix_v1 as T  # noqa: E402  (só fixtures de ambiente e dados sintéticos)
from test_topic_matrix_v1 import modelo_v1_local  # noqa: E402,F401

HOJE = datetime(2026, 10, 10, 12, 0, tzinfo=ZoneInfo("America/Bahia"))

# ----------------------------------------------- o que o advogado fornece
INSTRUCAO_ADVOGADO = """Utilize o EDE Legal MCP Homolog e elabore e finalize a contestação.
Minhas decisões são:
1. inaplicabilidade_cdc = NAO
2. revogacao_gratuidade = NAO
3. ausencia_interesse_agir = NAO
4. ilegitimidade_ativa_titularidade = NAO
5. inepcia_inicial = NAO
6. impugnacao_valor_causa = SIM
7. evolucao_consumo = NAO
8. dever_legal_fiscalizacao = NAO
9. desnecessidade_aviso_previo = NAO
10. calculos_recuperacao_consumo = NAO
11. licitude_cobranca_corte = NAO
12. nexo_causal_indemonstrado = NAO
13. descabimento_dano_moral = SIM
14. reconvencao_cobranca_debito = NAO

Citação: 21/09/2026."""

# Pedidos como aparecem na inicial sintética (o host lê o documento).
PEDIDOS_DA_INICIAL = [
    "declaração de inexistência do débito de R$ 2.097,63",
    "indenização por danos morais de R$ 12.900,00",
    "multa diária de R$ 300,00 por dia em caso de suspensão do fornecimento",
]
DOCUMENTOS = {
    "PEDIDO_DANO_MORAL_NA_INICIAL": True, "PROCEDIMENTO_ART_590_DOCUMENTADO": True,
    "VALOR_DA_CAUSA": "R$ 15.000,00", "VALOR_DANO_MORAL_PRETENDIDO": "R$ 12.900,00",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def ambiente(modelo_v1_local, monkeypatch):
    import finalizar_peca as fp  # ambiente apenas: relógio da execução
    monkeypatch.setattr(fp, "_agora", lambda: HOJE)


async def _cliente():
    from mcp import Client
    import server
    return Client(server.mcp, raise_exceptions=False)


async def _tools(c) -> dict:
    return {t.name: t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in (await c.list_tools()).tools}


async def _pacote(c) -> dict:
    r = await c.call_tool("ede_preparar_contestacao", {"entrada": {"fatos": [
        {"fact": "TOI registra desvio de energia antes do medidor (sintético).", "source_document": "toi",
         "tipo": "FATO_DOCUMENTADO"}]}})
    corpo = r.structured_content
    assert corpo["status"] == "OK", corpo
    return corpo["pacote"]


def _schema_finalizador(tools: dict) -> dict:
    return tools["ede_finalizar_peca"]["inputSchema"]


def _def(tools: dict, nome: str) -> dict:
    return _schema_finalizador(tools)["$defs"][nome]


# ======================================================== host ingênuo

def _host_marco(instrucao: str, montagem: dict) -> dict:
    """Só a regra publicada: citação/intimação/ciência -> CIENCIA."""
    m = re.search(r"(Citação|Intimação|Ciência)\s*:\s*(\d{2}/\d{2}/\d{4})", instrucao, re.I)
    assert m and "CIENCIA" in montagem["marco_tempestividade"]["regra"]
    return {"tipo": montagem["marco_tempestividade"]["exemplo"]["host_envia"]["tipo"], "data": m.group(2)}


def _host_pedidos(montagem: dict) -> list:
    """O host lê a inicial e infere a natureza; usa os campos e a regra de
    valor null publicados em montagem_finalizador."""
    campos = montagem["pedidos_economicos"]["campos_obrigatorios"]
    assert campos == ["descricao", "natureza", "valor", "fonte"]
    pedidos = []
    for texto in PEDIDOS_DA_INICIAL:
        natureza = ("DANO_MORAL" if "danos morais" in texto else
                    "DEBITO" if "débito" in texto else "OUTRO")
        assert natureza in montagem["pedidos_economicos"]["naturezas"]
        valor = None if "por dia" in texto else re.search(r"R\$ [\d.]+,\d{2}", texto).group(0)
        pedidos.append({"descricao": texto, "natureza": natureza, "valor": valor, "fonte": "Petição inicial"})
    return pedidos


def _host_topicos(instrucao: str) -> dict:
    return dict(re.findall(r"\d+\.\s*([a-z_]+)\s*=\s*(SIM|NAO)", instrucao))


def _host_entrada(pacote: dict, marco, pedidos) -> dict:
    placeholders = {**T._placeholders(), "VALOR_DA_CAUSA": DOCUMENTOS["VALOR_DA_CAUSA"],
                    "VALOR_DANO_MORAL_PRETENDIDO": DOCUMENTOS["VALOR_DANO_MORAL_PRETENDIDO"]}
    estado = {k: v for k, v in DOCUMENTOS.items() if isinstance(v, bool)}
    return {"capability_id": pacote["capability_id"], "topicos": _host_topicos(INSTRUCAO_ADVOGADO),
            "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": estado,
            "placeholders": placeholders, "marco_tempestividade": marco, "pedidos_economicos": pedidos}


async def _finalizar(c, entrada) -> tuple[bool, dict | str]:
    r = await c.call_tool("ede_finalizar_peca", {"entrada": entrada})
    texto = r.content[0].text
    if r.is_error:
        return False, texto
    return True, json.loads(texto)


# ============================================================ T1-T3

@pytest.mark.anyio
async def test_T1_pedido_economico_publica_campos_obrigatorios_e_enum(ambiente):
    async with await _cliente() as c:
        pedido = _def(await _tools(c), "PedidoEconomico")
    assert set(pedido["required"]) == {"descricao", "natureza", "fonte"}
    assert pedido["properties"]["natureza"]["enum"] == ["DEBITO", "DANO_MORAL", "OUTRO"]
    assert "default" not in pedido["properties"]["natureza"]
    assert {t.get("type") for t in pedido["properties"]["valor"]["anyOf"]} == {"string", "null"}


@pytest.mark.anyio
async def test_T1_orientacoes_publicas_citam_os_quatro_campos(ambiente):
    async with await _cliente() as c:
        tools = await _tools(c)
        pacote = await _pacote(c)
    entrada = _schema_finalizador(tools)["$defs"]["EdeFinalizarPecaEntrada"]["properties"]
    textos = [entrada["pedidos_economicos"]["description"], tools["ede_finalizar_peca"]["description"],
              pacote["montagem_finalizador"]["pedidos_economicos"]["regra"], pacote["topic_matrix"]["orientacao"]]
    for texto in textos:
        for campo in ("descricao", "natureza", "valor", "fonte"):
            assert campo in texto, (campo, texto[:120])


@pytest.mark.anyio
async def test_T2_marco_publica_tipo_data_enum_formato_e_regra_da_citacao(ambiente):
    async with await _cliente() as c:
        tools = await _tools(c)
    marco = _def(tools, "MarcoTempestividade")
    assert set(marco["required"]) == {"tipo", "data"}
    assert set(marco["properties"]["tipo"]["enum"]) == {"CIENCIA", "DISPONIBILIZACAO"}
    assert marco["properties"]["data"]["pattern"] == r"^\d{2}/\d{2}/\d{4}$"
    desc = _schema_finalizador(tools)["$defs"]["EdeFinalizarPecaEntrada"]["properties"]["marco_tempestividade"]
    for trecho in ("Citação", "Intimação", "Ciência", "CIENCIA", "DD/MM/AAAA", "DJe"):
        assert trecho in desc["description"]
    assert "Citação: 21/09/2026" in tools["ede_finalizar_peca"]["description"]
    assert "MONTAGEM PELO HOST" in tools["ede_finalizar_peca"]["description"]


@pytest.mark.anyio
async def test_T3_exemplos_publicados_validam_contra_o_proprio_schema(ambiente):
    async with await _cliente() as c:
        tools = await _tools(c)
        pacote = await _pacote(c)
    schema = _schema_finalizador(tools)
    defs = schema["$defs"]
    props = defs["EdeFinalizarPecaEntrada"]["properties"]
    exemplos_marco = defs["MarcoTempestividade"]["examples"] + props["marco_tempestividade"]["examples"]
    exemplos_pedidos = props["pedidos_economicos"]["examples"] + [defs["PedidoEconomico"]["examples"]]
    exemplos_pedidos.append(pacote["montagem_finalizador"]["pedidos_economicos"]["exemplos"])
    exemplos_marco.append(pacote["montagem_finalizador"]["marco_tempestividade"]["exemplo"]["host_envia"])
    assert any(p["valor"] is None for p in exemplos_pedidos[0])
    for marco in exemplos_marco:
        for pedidos in exemplos_pedidos:
            jsonschema.validate({"entrada": {"capability_id": "x", "marco_tempestividade": marco,
                                             "pedidos_economicos": pedidos}}, schema)
    # nenhum valor de caso real nem a fixture recorrente R$ 10.000,00
    bruto = json.dumps(exemplos_pedidos, ensure_ascii=False)
    for proibido in ("2.097,63", "12.900,00", "10.000,00", "15.000,00"):
        assert proibido not in bruto


# ================================================================ T4

@pytest.mark.anyio
async def test_T4_montagem_finalizador_entre_as_primeiras_chaves_do_pacote(ambiente):
    async with await _cliente() as c:
        r = await c.call_tool("ede_preparar_contestacao", {"entrada": {"fatos": [
            {"fact": f"Fato sintético {i}.", "source_document": f"doc_{i}", "tipo": "FATO_DOCUMENTADO"}
            for i in range(30)]}})
    texto = r.content[0].text
    pacote = json.loads(texto)["pacote"]
    assert list(pacote).index("montagem_finalizador") <= 1
    posicao = texto.find('"montagem_finalizador"')
    assert 0 <= posicao < 1000, posicao  # bytes iniciais, antes das seções volumosas
    montagem = pacote["montagem_finalizador"]
    assert len(json.dumps(montagem, ensure_ascii=False)) < 4000  # curto
    fluxo = " ".join(montagem["fluxo_obrigatorio_host"])
    for passo in ("PREPARAR", "DERIVAR", "FINALIZAR", "AUTOCORRIGIR", "PERGUNTAR"):
        assert passo in fluxo
    assert any("adequação dos campos" in p for p in montagem["proibido"])


# ============================================================ T5-T7

@pytest.mark.anyio
@pytest.mark.docx_real
async def test_T5_T6_host_ingenuo_monta_marco_e_pedidos_e_finaliza(ambiente):
    async with await _cliente() as c:
        tools = await _tools(c)
        pacote = await _pacote(c)
        montagem = pacote["montagem_finalizador"]
        marco = _host_marco(INSTRUCAO_ADVOGADO, montagem)
        pedidos = _host_pedidos(montagem)
        assert marco == {"tipo": "CIENCIA", "data": "21/09/2026"}
        assert [(p["natureza"], p["valor"]) for p in pedidos] == [
            ("DEBITO", "R$ 2.097,63"), ("DANO_MORAL", "R$ 12.900,00"), ("OUTRO", None)]
        entrada = _host_entrada(pacote, marco, pedidos)
        jsonschema.validate({"entrada": entrada}, _schema_finalizador(tools))
        ok, corpo = await _finalizar(c, entrada)
    assert ok and corpo["status"] == "OK", corpo
    assert any("R$ 14.997,63" in aviso and "R$ 2,37" in aviso for aviso in corpo["dados_nao_bloqueantes"])


@pytest.mark.anyio
@pytest.mark.docx_real
@pytest.mark.parametrize("estrago", ["marco_citacao", "marco_string", "pedido_sem_natureza",
                                     "pedido_sem_descricao", "valor_textual_da_multa"])
async def test_T7_primeira_tentativa_malformada_e_autocorrigida_pelo_contrato(ambiente, estrago):
    async with await _cliente() as c:
        pacote = await _pacote(c)
        montagem = pacote["montagem_finalizador"]
        marco, pedidos = _host_marco(INSTRUCAO_ADVOGADO, montagem), _host_pedidos(montagem)
        ruim_marco, ruim_pedidos = dict(marco), [dict(p) for p in pedidos]
        if estrago == "marco_citacao":
            ruim_marco["tipo"] = "CITACAO"
        elif estrago == "marco_string":
            ruim_marco = "21/09/2026"
        elif estrago == "pedido_sem_natureza":
            del ruim_pedidos[0]["natureza"]
        elif estrago == "pedido_sem_descricao":
            del ruim_pedidos[1]["descricao"]
        else:
            ruim_pedidos[2]["valor"] = "R$ 300,00 por dia"
        ok, primeira = await _finalizar(c, _host_entrada(pacote, ruim_marco, ruim_pedidos))
        assert not ok or primeira["status"] == "REFUSED"
        # A falha aponta o campo técnico — matéria do host, nunca do advogado.
        texto = primeira if isinstance(primeira, str) else json.dumps(primeira, ensure_ascii=False)
        assert any(c_ in texto for c_ in ("marco_tempestividade", "pedidos_economicos"))
        # Correção só com o contrato publicado: refaz pela regra de montagem.
        ok, segunda = await _finalizar(c, _host_entrada(pacote, _host_marco(INSTRUCAO_ADVOGADO, montagem),
                                                        _host_pedidos(montagem)))
    assert ok and segunda["status"] == "OK", segunda


# ================================================================ T8

@pytest.mark.anyio
async def test_T8_pendencia_factual_real_continua_needs_input_sem_campo_tecnico(ambiente):
    async with await _cliente() as c:
        pacote = await _pacote(c)
        montagem = pacote["montagem_finalizador"]
        entrada = _host_entrada(pacote, _host_marco(INSTRUCAO_ADVOGADO, montagem), _host_pedidos(montagem))
        entrada["estado_processual"]["PEDIDO_DANO_MORAL_NA_INICIAL"] = False  # documento não sustenta
        ok, corpo = await _finalizar(c, entrada)
    assert ok and corpo["status"] == "NEEDS_INPUT", corpo
    for pendencia in corpo["pendencias"]:
        assert not T.TERMOS_INTERNOS.search(pendencia), pendencia
        for tecnico in ("CIENCIA", "DEBITO", "DANO_MORAL", "natureza", "marco_tempestividade", "{"):
            assert tecnico not in pendencia, pendencia


# ================================================== exemplos só de formato

AVISO = "Os valores dos exemplos são exclusivamente ilustrativos de formato"


@pytest.mark.anyio
async def test_exemplos_publicados_sao_marcados_como_apenas_formato(ambiente):
    """Contrato publicado, não validação: os valores dos exemplos podem
    existir num caso real e nunca são recusados por si."""
    async with await _cliente() as c:
        tools = await _tools(c)
        pacote = await _pacote(c)
    defs = _schema_finalizador(tools)["$defs"]
    props = defs["EdeFinalizarPecaEntrada"]["properties"]
    for publicado in (props["marco_tempestividade"]["description"], props["pedidos_economicos"]["description"],
                      defs["MarcoTempestividade"]["x-aviso-exemplos"], defs["PedidoEconomico"]["x-aviso-exemplos"]):
        assert AVISO in publicado and "Nunca copie valores de exemplo para uma peça" in publicado
    assert "nunca os copie para a peça" in tools["ede_finalizar_peca"]["description"]
    montagem = pacote["montagem_finalizador"]
    for publicado in (montagem["aviso_exemplos"], montagem["marco_tempestividade"]["exemplo"]["aviso"],
                      montagem["pedidos_economicos"]["aviso_exemplos"]):
        assert AVISO in publicado and "Extraia descricao, natureza, valor e fonte dos documentos do caso" in publicado


@pytest.mark.anyio
@pytest.mark.docx_real
async def test_valores_iguais_aos_dos_exemplos_nao_sao_recusados(ambiente):
    """R$ 1.234,56 pode ser o débito real de um caso: nenhum bloqueio."""
    async with await _cliente() as c:
        pacote = await _pacote(c)
        montagem = pacote["montagem_finalizador"]
        pedidos = [{"descricao": "declaração de inexistência do débito", "natureza": "DEBITO",
                    "valor": "R$ 1.234,56", "fonte": "Petição inicial"},
                   {"descricao": "indenização por danos morais", "natureza": "DANO_MORAL",
                    "valor": "R$ 12.900,00", "fonte": "Petição inicial"}]
        ok, corpo = await _finalizar(c, _host_entrada(pacote, _host_marco(INSTRUCAO_ADVOGADO, montagem), pedidos))
    assert ok and corpo["status"] == "OK", corpo
