#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate de compatibilidade host (emenda da ADR-0021, SPEC-0001 §64.8).

Achado real (primeiro teste simples no ChatGPT, 28/09/2026): o advogado
deu só as 14 decisões SIM/NÃO e a data da citação; o host tinha os
documentos, mas `ede_finalizar_peca` devolveu NEEDS_INPUT para cálculos,
dano moral e reconvenção porque nenhuma ferramenta MCP publicava quais
chaves de `estado_processual` sustentam esses tópicos.

Todos os testes daqui são BLACK-BOX pela camada MCP: `tools/list` e
`tools/call` pelo cliente oficial in-memory do SDK (`mcp.Client`), sem
importar o Core para montar a entrada. O "host ingênuo" abaixo só sabe
o que o pacote de `ede_preparar_contestacao` diz, mais a conclusão
sintética da sua leitura semântica dos anexos (arquivos de nome
arbitrário) — nada do repositório, nenhuma taxonomia de documentos.

Sem o .docx do Modelo Oficial V1 a composição para depois das etapas de
entrada (o que já prova a Topic Matrix, a tempestividade e o
endereçamento); o teste `docx_real` vai até o DOCX final.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "mcp_server"))
sys.path.insert(0, str(BASE / "tests"))

import finalizar_peca as fp  # noqa: E402
import legal_readiness as lr  # noqa: E402
import test_topic_matrix_v1 as T  # noqa: E402

CAP = T.CAP
TERMOS_INTERNOS = T.TERMOS_INTERNOS
HOJE = datetime(2026, 9, 28, 12, 0, tzinfo=ZoneInfo("America/Bahia"))

# A instrução real do advogado, literal (só SIM/NÃO + "Citação 21/09/2026").
TOPICOS_CASO_REAL = {
    "inaplicabilidade_cdc": "NAO", "revogacao_gratuidade": "SIM", "ausencia_interesse_agir": "NAO",
    "ilegitimidade_ativa_titularidade": "NAO", "inepcia_inicial": "NAO", "impugnacao_valor_causa": "SIM",
    "evolucao_consumo": "NAO", "dever_legal_fiscalizacao": "SIM", "desnecessidade_aviso_previo": "SIM",
    "calculos_recuperacao_consumo": "SIM", "licitude_cobranca_corte": "NAO", "nexo_causal_indemonstrado": "SIM",
    "descabimento_dano_moral": "SIM", "reconvencao_cobranca_debito": "SIM",
}
CITACAO = {"tipo": "CIENCIA", "data": "21/09/2026"}
TOPICOS_QUE_FALHARAM = ("calculos_recuperacao_consumo", "descabimento_dano_moral", "reconvencao_cobranca_debito")

# O que o host (a LLM) concluiu lendo o CONTEÚDO de cada anexo, à luz do
# `requisito` publicado de cada chave. Nomes de arquivo arbitrários: nem o
# host nem o Core dependem deles. É o único conhecimento do host além do
# pacote; a leitura semântica em si é da LLM, aqui só simulada.
LEITURA_DO_HOST = {
    "documento_01.pdf": {"PEDIDO_DANO_MORAL_NA_INICIAL"},  # a petição inicial
    "documento_04.pdf": {"PROCEDIMENTO_ART_590_DOCUMENTADO", "INSPECAO_ACOMPANHADA_DOCUMENTADA"},  # o TOI
    "documento_07.pdf": {"FATURA_RECUPERACAO_DOCUMENTADA", "METODOLOGIA_APURACAO_DOCUMENTADA",
                         "VALOR_FRA_DOCUMENTADO"},  # demonstrativo da recuperação
}
COMPROVADOS_CASO_REAL = set().union(*LEITURA_DO_HOST.values())

# Valores que o host "extraiu" de cada documento (sintéticos).
VALORES_EXTRAIDOS = {**T._placeholders(), "VALOR_FRA": "R$ 2.097,63", "VALOR_DA_CAUSA": "R$ 15.000,00",
                     "VALOR_DANO_MORAL_PRETENDIDO": "R$ 12.900,00"}  # o mesmo valor do pedido (manifesto 1.3.0)
PEDIDOS = [{"descricao": "declaração de inexistência do débito", "natureza": "DEBITO", "valor": "R$ 2.097,63",
            "fonte": "documento_01.pdf"},
           {"descricao": "indenização por danos morais", "natureza": "DANO_MORAL", "valor": "R$ 12.900,00",
            "fonte": "documento_01.pdf"},
           {"descricao": "multa diária de R$ 300,00", "natureza": "OUTRO", "valor": None,
            "fonte": "documento_01.pdf"}]
FATOS_SINTETICOS = [
    {"fact": "Memorial de cálculo aplica o art. 595, III, e apura R$ 2.097,63.",
     "source_document": "memorial_calculo", "tipo": "FATO_DOCUMENTADO"},
    {"fact": "A inicial pede indenização por danos morais.", "source_document": "peticao_inicial",
     "tipo": "ALEGACAO_AUTORAL"},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def ambiente(monkeypatch):
    """V1 pinado; readiness READY; sem .docx (o contexto institucional
    sai vazio, o pacote continua válido); DataJud e relógio injetados."""
    for var in ("EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT",
                "EDE_MODELO_OFICIAL_GCS_GENERATION", "EDE_MODELO_OFICIAL_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", T.V1.modelo_sha256)
    monkeypatch.setattr(lr, "avaliar_corpus_rag", lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial", lambda *a, **k: lr.ResultadoReadiness("READY", "sintético"))

    def _sem_modelo():
        raise lr.ModeloOficialIndisponivel("NOT_CONFIGURED", "sintético")
    monkeypatch.setattr(lr, "adquirir_bytes_modelo_oficial", _sem_modelo)
    T._injetar_derivados(monkeypatch)
    monkeypatch.setattr(fp, "_agora", lambda: HOJE)


@pytest.fixture
async def cliente(ambiente):
    from mcp import Client
    import server
    async with Client(server.mcp, raise_exceptions=True) as c:
        yield c


async def _preparar(cliente) -> dict:
    r = await cliente.call_tool("ede_preparar_contestacao", {"entrada": {"fatos": FATOS_SINTETICOS}})
    corpo = r.structured_content
    assert corpo["status"] == "OK", corpo
    return corpo["pacote"]


async def _finalizar(cliente, entrada: dict) -> dict:
    r = await cliente.call_tool("ede_finalizar_peca", {"entrada": entrada})
    return json.loads(r.content[0].text)


def _grupos_host(pacote: dict) -> list[dict]:
    tm = pacote["topic_matrix"]
    return [*tm["topicos"], *tm["secoes_incondicionais_host"]]


def _exigido(cond: dict, topicos: dict, estado: dict) -> bool:
    if cond.get("opcional"):
        return False
    if "topico" in cond and topicos.get(cond["topico"]) != cond["resposta"]:
        return False
    if "chave_estado" in cond and estado.get(cond["chave_estado"]) is not cond["valor"]:
        return False
    return True


def _host_ingenuo(pacote: dict, topicos: dict, comprovados: set, contraditorios: set = frozenset()) -> dict:
    """Um host que só lê o pacote: para cada chave publicada, true se sua
    leitura dos documentos satisfez o requisito, INDETERMINADO se os
    documentos se contradizem, false caso contrário; e envia só os campos
    cujo `exigido_quando` se cumpre. Nenhuma chave vem de fora do pacote."""
    publicadas = set(pacote["topic_matrix"]["chaves_estado_host"])
    assert comprovados <= publicadas and contraditorios <= publicadas
    estado = {c: "INDETERMINADO" if c in contraditorios else c in comprovados for c in publicadas}
    placeholders = {}
    for grupo in _grupos_host(pacote):
        for d in grupo["dados_documentais_host"]:
            if _exigido(d["exigido_quando"], topicos, estado):
                placeholders[d["campo"]] = VALORES_EXTRAIDOS[d["campo"]]
    for parte in pacote["topic_matrix"]["partes_redigiveis_llm"]:
        if parte["campo_finalizador"] == "placeholders" and _exigido(parte["exigido_quando"], topicos, estado):
            placeholders[parte["parte"]] = VALORES_EXTRAIDOS[parte["parte"]]
    entrada = {"capability_id": pacote["capability_id"], "topicos": topicos, "estado_processual": estado,
               "placeholders": placeholders, "marco_tempestividade": CITACAO}
    if topicos.get("impugnacao_valor_causa") == "SIM":
        entrada["pedidos_economicos"] = PEDIDOS
    return entrada


def _sem_termos_internos(textos) -> None:
    for t in textos:
        assert not TERMOS_INTERNOS.search(t), t


# ================================================ 1-4: o pacote publica o contrato

@pytest.mark.anyio
async def test_1_todo_gate_factual_do_manifesto_aparece_no_pacote(cliente):
    pacote = await _preparar(cliente)
    por_chave = {t["chave"]: t for t in pacote["topic_matrix"]["topicos"]}
    for t in T.MANIFESTO["topicos_decisao_advogado"]:
        publicados = {e["chave_estado"]: e for e in por_chave[t["chave"]]["suporte_factual_host"]
                      if e["papel"] == "gate_factual"}
        assert set(publicados) == set(t["gate_factual"]), t["chave"]
        for e in publicados.values():
            assert e["descricao"] and e["requisito"] and isinstance(e["documentos_sugeridos"], list)
            assert {"true", "false", "INDETERMINADO"} <= set(e["regra"])
    for chave, gate in (("calculos_recuperacao_consumo", "FATURA_RECUPERACAO_DOCUMENTADA"),
                        ("descabimento_dano_moral", "PEDIDO_DANO_MORAL_NA_INICIAL"),
                        ("reconvencao_cobranca_debito", "VALOR_FRA_DOCUMENTADO")):
        assert gate in {e["chave_estado"] for e in por_chave[chave]["suporte_factual_host"]}
    assert pacote["capability_id"] == CAP


@pytest.mark.anyio
async def test_2_todo_dado_documental_aparece_no_pacote(cliente):
    pacote = await _preparar(cliente)
    publicados = {d["campo"]: d for g in _grupos_host(pacote) for d in g["dados_documentais_host"]}
    esperados = {c["parte"] for g in [*T.MANIFESTO["topicos_decisao_advogado"], *T.MANIFESTO["secoes_incondicionais"]]
                 for c in g.get("conteudo") or [] if c["modo"] == "DADO_DOCUMENTAL"}
    assert esperados <= set(publicados), esperados - set(publicados)
    # Marcadores de pós-edição manual são do Core, nunca pedidos ao host.
    calculados = set(pacote["topic_matrix"]["campos_calculados_pelo_sistema"])
    assert {"FOTOS_DA_IRREGULARIADE", "TELAS_DA_TITULARIDADE", "JUIZO", "TEMPESTIVIDADE_CASO"} <= calculados
    assert not calculados & set(publicados)
    for d in publicados.values():
        assert d["descricao"] and d["campo_finalizador"] == "placeholders" and d["exigido_quando"]
    dano = next(d for d in next(t for t in pacote["topic_matrix"]["topicos"]
                                if t["chave"] == "descabimento_dano_moral")["dados_documentais_host"])
    assert dano["campo"] == "VALOR_DANO_MORAL_PRETENDIDO"
    assert dano["exigido_quando"] == {"topico": "descabimento_dano_moral", "resposta": "SIM"}


@pytest.mark.anyio
async def test_2_contrato_publicado_de_irregularidade_e_valor_fra_bate_com_o_core(cliente):
    """Revisão de 28/09/2026: o host recebe o contrato atômico da
    irregularidade (Etapa 5.3-B) e nenhuma orientação de usar a sentinela
    de ausência em VALOR_FRA."""
    pacote = await _preparar(cliente)
    publicados = [d for g in _grupos_host(pacote) for d in g["dados_documentais_host"]]
    for d in (d for d in publicados if d["campo"] == "IRREGULARIDADE_ENCONTRADA"):
        assert d["descricao"].startswith("Somente o nome ou tipo da irregularidade")
        assert any("não repetir o texto fixo" in r for r in d["restricoes"])
        assert d["documentos_sugeridos"] == ["toi"]
    fra = next(d for d in publicados if d["campo"] == "VALOR_FRA")
    texto = json.dumps(fra, ensure_ascii=False)
    assert "sinalizado como ausente" not in texto and "deve conter dígito" not in texto
    assert any(r.startswith("nunca usar sentinela") for r in fra["restricoes"])
    assert any("INDETERMINADO" in r for r in fra["restricoes"])


@pytest.mark.anyio
async def test_contrato_e_semantico_sem_taxonomia_de_documentos(cliente):
    """Direção de 28/09/2026: requisito semântico; sugestão de documento é
    orientação, nunca enum nem condição de validade."""
    pacote = await _preparar(cliente)
    tm = pacote["topic_matrix"]
    assert "tipos_documentais_host" not in tm
    for g in _grupos_host(pacote):
        for e in g["suporte_factual_host"]:
            assert "qualquer que seja o nome, o formato ou o tipo do arquivo" in e["requisito"]
            assert "documentos_fonte" not in e
    assert "nunca lista fechada" in tm["orientacao"]
    # Nada no schema do finalizador restringe nome ou tipo de documento.
    ferramentas = {t.name: t for t in (await cliente.list_tools()).tools}
    schema = json.dumps(ferramentas["ede_finalizar_peca"].input_schema, ensure_ascii=False)
    for termo in ("memorial_calculo", "memorial_faturamento", "peticao_inicial", "fatura_recuperacao"):
        assert termo not in schema


@pytest.mark.anyio
async def test_3_estados_de_zona_e_subbloco_aparecem_no_pacote(cliente):
    pacote = await _preparar(cliente)
    tm = pacote["topic_matrix"]
    publicados = {e["chave_estado"]: e for g in _grupos_host(pacote) for e in g["suporte_factual_host"]}
    reservados = set(tm["estados_calculados_pelo_sistema"])
    usados_pelo_catalogo = {b.get("linked_fact") for b in T.CATALOGO["blocks"]} | \
        {(b.get("requires_fact") or {}).get("key") for b in T.CATALOGO["blocks"]} | \
        {f for z in T.CATALOGO["zones"] for f in z["requires_facts"]}
    usados_pelo_catalogo -= {None}
    assert usados_pelo_catalogo - reservados <= set(publicados)
    for chave in ("METODOLOGIA_APURACAO_DOCUMENTADA", "PROCEDIMENTO_ART_590_DOCUMENTADO",
                  "REGISTRO_FOTOGRAFICO_DOCUMENTADO", "INSPECAO_ACOMPANHADA_DOCUMENTADA",
                  "NOTIFICACAO_AUTORA_DOCUMENTADA", "LEVANTAMENTO_CARGA_DOCUMENTADO"):
        e = publicados[chave]
        assert e["descricao"] and e["requisito"] and {"true", "false", "INDETERMINADO"} <= set(e["regra"])
    assert publicados["METODOLOGIA_APURACAO_DOCUMENTADA"]["papel"] == "zona"
    assert publicados["PROCEDIMENTO_ART_590_DOCUMENTADO"]["papel"] == "subbloco"
    # Contrato fechado: a lista de chaves aceitas é exatamente a publicada,
    # sem nenhum estado que o sistema calcula.
    assert set(tm["chaves_estado_host"]) == set(publicados)
    assert not reservados & set(publicados)
    assert reservados == {"EXISTE_DISCREPANCIA_VALOR_CAUSA", "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS"}


@pytest.mark.anyio
async def test_4_nenhum_bloco_com_gate_do_manifesto_aparece_sem_gate(cliente):
    pacote = await _preparar(cliente)
    por_id = {b["id"]: b for b in pacote["blocos_modelo"]}
    for t in T.MANIFESTO["topicos_decisao_advogado"]:
        status = por_id[t["topic_id"]]["gate_status"]
        if t["gate_factual"]:
            assert status != "sem_gate_fatico", t["topic_id"]
            for f in t["gate_factual"]:
                assert f in status, (t["topic_id"], status)
    # Estado reservado ao Core nunca aparece como "a informar".
    assert por_id["PRELIMINAR_IMPUGNACAO_VALOR_CAUSA"]["gate_status"] == \
        "calculado_pelo_sistema (EXISTE_DISCREPANCIA_VALOR_CAUSA)"


@pytest.mark.anyio
async def test_schema_publicado_aponta_para_o_contrato_do_host(cliente):
    ferramentas = {t.name: t for t in (await cliente.list_tools()).tools}
    entrada = ferramentas["ede_finalizar_peca"].input_schema["$defs"]["EdeFinalizarPecaEntrada"]
    descricao = entrada["properties"]["estado_processual"]["description"]
    assert "chaves_estado_host" in descricao and "ede_preparar_contestacao" in descricao
    assert "suporte_factual_host" in ferramentas["ede_preparar_contestacao"].description
    assert "capability_id" in ferramentas["ede_finalizar_peca"].description


@pytest.mark.anyio
async def test_orientacao_do_pacote_manda_derivar_e_nunca_perguntar_as_chaves(cliente):
    pacote = await _preparar(cliente)
    orientacao = pacote["topic_matrix"]["orientacao"]
    for termo in ("derive 'estado_processual' lendo o conteúdo dos documentos",
                  "somente as chaves de chaves_estado_host", "exigido_quando",
                  "INDETERMINADO", "Nunca pergunte essas chaves ao advogado", "suporte_ausente",
                  "linguagem comum", "capability_id"):
        assert termo in orientacao, termo
    # O que o host mostra ao advogado continua sem nenhum identificador interno.
    tm = pacote["topic_matrix"]
    _sem_termos_internos([t["nome_publico"] for t in tm["topicos"]] + [t["pergunta"] for t in tm["topicos"]]
                         + [f["pergunta"] for f in tm["fatos_publicos"]])


# ===================================== 5: host ingênuo, só pacote + evidência

@pytest.mark.anyio
async def test_5_host_ingenuo_passa_da_topic_matrix_com_a_instrucao_real(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    for gate in ("FATURA_RECUPERACAO_DOCUMENTADA", "PEDIDO_DANO_MORAL_NA_INICIAL", "VALOR_FRA_DOCUMENTADO"):
        assert entrada["estado_processual"][gate] is True
    r = await _finalizar(cliente, entrada)
    # Sem o .docx a composição para na readiness do Modelo Oficial —
    # depois da Topic Matrix, da tempestividade, do endereçamento e do
    # valor da causa, sem nenhuma pergunta ao advogado.
    assert r["status"] == "REFUSED" and r["stage"] == "official_model_readiness", r
    assert "pendencias" not in r and "suporte_ausente" not in r


@pytest.mark.anyio
async def test_5_reproducao_do_teste_real_sem_estado_processual(cliente):
    """O que o ChatGPT fez: só as 14 respostas + citação. Continua
    NEEDS_INPUT (a regra jurídica não mudou), agora com suporte_ausente."""
    pacote = await _preparar(cliente)
    r = await _finalizar(cliente, {"capability_id": pacote["capability_id"], "topicos": TOPICOS_CASO_REAL,
                                   "fatos_publicos": {"corte_efetivo": "NAO"}, "marco_tempestividade": CITACAO})
    assert r["status"] == "NEEDS_INPUT" and r["stage"] == "topic_matrix"
    assert len(r["pendencias"]) == 3
    assert {(s["topico"], s["chave_estado"], s["motivo"]) for s in r["suporte_ausente"]} == {
        ("calculos_recuperacao_consumo", "FATURA_RECUPERACAO_DOCUMENTADA", "AUSENTE"),
        ("descabimento_dano_moral", "PEDIDO_DANO_MORAL_NA_INICIAL", "AUSENTE"),
        ("reconvencao_cobranca_debito", "VALOR_FRA_DOCUMENTADO", "AUSENTE"),
    }


# ============================== anexo de nome arbitrário, leitura pelo conteúdo

CONTEUDO_DOCUMENTO_07 = (
    "DEMONSTRATIVO DA RECUPERAÇÃO — ciclo 03/2026: consumo faturado 150 kWh; consumo apurado 420 kWh; "
    "diferença 270 kWh; tarifa R$ 0,79/kWh; valor R$ 213,30. [...] Total da recuperação: R$ 2.097,63.")


@pytest.mark.anyio
async def test_anexo_com_nome_arbitrario_satisfaz_o_requisito_pelo_conteudo(cliente):
    """`documento_07.pdf` é um demonstrativo de faturamento da recuperação.
    O host o relaciona ao requisito publicado de FATURA_RECUPERACAO_
    DOCUMENTADA pelo conteúdo; nem o nome nem um tipo catalogado entram na
    chamada, e o Core aceita."""
    pacote = await _preparar(cliente)
    fatura = next(e for t in pacote["topic_matrix"]["topicos"] if t["chave"] == "calculos_recuperacao_consumo"
                  for e in t["suporte_factual_host"] if e["chave_estado"] == "FATURA_RECUPERACAO_DOCUMENTADA")
    assert "recuperação de consumo" in fatura["requisito"]
    assert "Total da recuperação" in CONTEUDO_DOCUMENTO_07  # o que a leitura do host reconhece
    comprovados = LEITURA_DO_HOST["documento_07.pdf"]
    topicos = {**{k: "NAO" for k in TOPICOS_CASO_REAL}, "calculos_recuperacao_consumo": "SIM"}
    entrada = _host_ingenuo(pacote, topicos, comprovados)
    assert "documento_07" not in json.dumps(entrada)
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r  # passou da Topic Matrix


@pytest.mark.anyio
async def test_campos_de_bloco_excluido_nao_sao_exigidos(cliente):
    """Com ilegitimidade e inépcia NÃO, o host não envia telas, conta-contrato,
    titular nem núcleo do objeto, e a finalização não os cobra."""
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    for campo in ("TELAS_DA_TITULARIDADE", "CONTA_CONTRATO", "NOME_TITULAR_DA_UC", "SINOPSE_FATOS_NUCLEO_OBJETO",
                  "FOTOS_DA_IRREGULARIADE"):
        assert campo not in entrada["placeholders"], campo
    partes = {p["parte"]: p["exigido_quando"] for p in pacote["topic_matrix"]["partes_redigiveis_llm"]}
    assert partes["SINOPSE_FATOS_NUCLEO_OBJETO"] == {"topico": "inepcia_inicial", "resposta": "SIM"}
    assert partes["SINOPSE_FATOS"] == {"sempre": True}
    assert partes["ZONA_METODOLOGIA_APURACAO"]["opcional"] is True
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


# ================================ marcadores do Core e valor real da Reconvenção

TOPICOS_TITULARIDADE = {**TOPICOS_CASO_REAL, "ilegitimidade_ativa_titularidade": "SIM"}
COMPROVADOS_TITULARIDADE = COMPROVADOS_CASO_REAL | {"UC_TITULARIDADE_TERCEIRO_COMPROVADA",
                                                    "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA"}


@pytest.mark.anyio
async def test_ilegitimidade_sim_telas_preenchido_pelo_core(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_TITULARIDADE, COMPROVADOS_TITULARIDADE)
    assert "TELAS_DA_TITULARIDADE" not in entrada["placeholders"]
    assert {"CONTA_CONTRATO", "NOME_TITULAR_DA_UC"} <= set(entrada["placeholders"])
    r = await _finalizar(cliente, entrada)
    # Passou da validação de produção-final (que cobraria o campo) sem o host enviá-lo.
    assert r["stage"] == "official_model_readiness", r


@pytest.mark.anyio
async def test_marcador_enviado_pelo_host_diferente_do_institucional_e_recusado(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_TITULARIDADE, COMPROVADOS_TITULARIDADE)
    entrada["placeholders"]["TELAS_DA_TITULARIDADE"] = "Ver telas anexas."
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "REFUSED" and r["error_code"] == "INPUT_VALIDATION_FAILED"
    assert "preenchido pelo sistema" in r["motivo"]


@pytest.mark.anyio
async def test_fotos_documentadas_marcador_preenchido_pelo_core(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL | {"REGISTRO_FOTOGRAFICO_DOCUMENTADO"})
    assert "FOTOS_DA_IRREGULARIADE" not in entrada["placeholders"]
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


@pytest.mark.anyio
@pytest.mark.parametrize("valor", ["NÃO INFORMADO", "NAO INFORMADO", "não informado nos autos", "a apurar",
                                   "[PENDENTE: valor]", "R$ a definir"])
async def test_reconvencao_sim_com_valor_fra_provisorio_e_recusada(cliente, valor):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    assert entrada["estado_processual"]["VALOR_FRA_DOCUMENTADO"] is True
    entrada["placeholders"]["VALOR_FRA"] = valor
    r = await _finalizar(cliente, entrada)
    # Recusado antes de qualquer render. Valor sem nenhum dígito já cai na
    # validação semântica de entrada (preexistente); a sentinela de
    # ausência, que ela deixava passar, cai agora na produção-final.
    assert r["status"] == "REFUSED" and "download_url" not in r
    if "INFORMADO" in valor.upper():
        assert (r["stage"], r["error_code"]) == ("production_final_validation", "MISSING_REQUIRED_FIELD"), r
    else:
        assert r["stage"] in ("input_validation", "production_final_validation"), r


@pytest.mark.anyio
async def test_reconvencao_sim_com_valor_fra_documental_segue(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    assert entrada["placeholders"]["VALOR_FRA"] == "R$ 2.097,63"
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


# ============================================ 6-9: fail-closed e suporte_ausente

@pytest.mark.anyio
@pytest.mark.parametrize("topico", TOPICOS_QUE_FALHARAM)
async def test_6_sim_com_suporte_false_devolve_needs_input(cliente, topico):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    gate = next(t for t in T.MANIFESTO["topicos_decisao_advogado"] if t["chave"] == topico)["gate_factual"][0]
    entrada["estado_processual"][gate] = False
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT" and r["stage"] == "topic_matrix"
    assert r["suporte_ausente"] == [{"topico": topico, "chave_estado": gate, "motivo": "FALSE"}]
    assert "não há suporte documental" in r["pendencias"][0]
    _sem_termos_internos(r["pendencias"])


@pytest.mark.anyio
@pytest.mark.parametrize("topico", TOPICOS_QUE_FALHARAM)
async def test_7_sim_com_suporte_indeterminado_devolve_needs_input_por_contradicao(cliente, topico):
    pacote = await _preparar(cliente)
    gate = next(t for t in T.MANIFESTO["topicos_decisao_advogado"] if t["chave"] == topico)["gate_factual"][0]
    requisito = next(e for t in pacote["topic_matrix"]["topicos"] if t["chave"] == topico
                     for e in t["suporte_factual_host"] if e["chave_estado"] == gate)["requisito"]
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    entrada["estado_processual"][gate] = "INDETERMINADO"
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT" and r["stage"] == "topic_matrix"
    assert r["suporte_ausente"] == [{"topico": topico, "chave_estado": gate, "motivo": "INDETERMINADO"}]
    assert "contraditórios" in r["pendencias"][0]
    _sem_termos_internos(r["pendencias"])
    assert requisito  # o host sabe o que procurar para resolver a contradição


@pytest.mark.anyio
@pytest.mark.parametrize("chave", ["CALCULOS_RECUPERACAO_CONSUMO", "fatura_recuperacao_documentada",
                                   "calculos_recuperacao_consumo", "PEDIDO_DANO_MORAL"])
async def test_8_chave_desconhecida_e_recusada_nunca_ignorada(cliente, chave):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    entrada["estado_processual"][chave] = True
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "REFUSED" and r["error_code"] == "INPUT_VALIDATION_FAILED"
    assert r["stage"] == "input_validation" and r["chaves_estado_desconhecidas"] == [chave]
    assert "download_url" not in r


@pytest.mark.anyio
async def test_8_estado_calculado_pelo_sistema_continua_recusado(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    entrada["estado_processual"]["EXISTE_DISCREPANCIA_VALOR_CAUSA"] = True
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "REFUSED" and r["error_code"] == "INPUT_VALIDATION_FAILED"
    assert "derivados pelo sistema" in r["motivo"]


@pytest.mark.anyio
async def test_9_suporte_ausente_permite_ao_host_se_corrigir_sem_perguntar(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, set())  # host ainda não leu os documentos
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT" and r["suporte_ausente"]
    assert {s["motivo"] for s in r["suporte_ausente"]} == {"FALSE"}
    # Com a chave devolvida, o host relê os documentos à luz do requisito
    # publicado e reenvia, sem pergunta técnica ao advogado.
    for s in r["suporte_ausente"]:
        assert s["chave_estado"] in COMPROVADOS_CASO_REAL
        entrada["estado_processual"][s["chave_estado"]] = True
    r2 = await _finalizar(cliente, entrada)
    assert r2["stage"] != "topic_matrix", r2


# ===================================================== 10-11: tempestividade

@pytest.mark.anyio
async def test_10_ciencia_21_09_2026_sem_conversao(cliente, monkeypatch):
    def _proibido(*a, **k):
        raise AssertionError("CIENCIA não pode derivar publicação")
    monkeypatch.setattr(fp, "derivar_publicacao", _proibido)
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    assert entrada["marco_tempestividade"] == {"tipo": "CIENCIA", "data": "21/09/2026"}
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r  # passou da tempestividade


@pytest.mark.anyio
async def test_11_disponibilizacao_sem_regressao(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    entrada["marco_tempestividade"] = {"tipo": "DISPONIBILIZACAO", "data": "18/09/2026"}
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


# ============================================= 12: corte_efetivo inalterado

@pytest.mark.anyio
async def test_12_corte_sem_resposta_nem_documento_continua_perguntado(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    del entrada["estado_processual"]["CORTE_EFETIVO"]
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT" and r["stage"] == "topic_matrix"
    assert r["pendencias"] == ["Responda SIM ou NÃO: Houve corte ou suspensão efetiva do fornecimento?"]
    assert "suporte_ausente" not in r


@pytest.mark.anyio
async def test_12_corte_documental_divergente_da_resposta_do_advogado(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    assert entrada["estado_processual"]["CORTE_EFETIVO"] is False
    entrada["fatos_publicos"] = {"corte_efetivo": "SIM"}
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT"
    assert any("diverge do que consta dos documentos" in p for p in r["pendencias"])


@pytest.mark.anyio
async def test_12_licitude_sim_com_corte_nao_e_o_fato_nunca_e_inferido_do_topico(cliente):
    pacote = await _preparar(cliente)
    entrada = _host_ingenuo(pacote, {**TOPICOS_CASO_REAL, "licitude_cobranca_corte": "SIM"}, COMPROVADOS_CASO_REAL)
    del entrada["estado_processual"]["CORTE_EFETIVO"]
    entrada["fatos_publicos"] = {"corte_efetivo": "NAO"}
    r = await _finalizar(cliente, entrada)
    assert r["status"] == "NEEDS_INPUT"
    assert any("foi informado que não houve corte" in p for p in r["pendencias"])
    # Licitude NÃO com corte SIM: o tópico sai, o fato não é negado.
    entrada = _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL)
    del entrada["estado_processual"]["CORTE_EFETIVO"]
    entrada["fatos_publicos"] = {"corte_efetivo": "SIM"}
    r = await _finalizar(cliente, entrada)
    assert r["stage"] == "official_model_readiness", r


@pytest.mark.anyio
async def test_12_regra_publicada_do_corte_e_a_da_inv_corte_gate_humano(cliente):
    pacote = await _preparar(cliente)
    licitude = next(t for t in pacote["topic_matrix"]["topicos"] if t["chave"] == "licitude_cobranca_corte")
    corte = next(e for e in licitude["suporte_factual_host"] if e["chave_estado"] == "CORTE_EFETIVO")
    assert "Alegação da autora" in corte["regra"]["true"] and "nunca inferido" in corte["regra"]["nota"]
    assert corte["documentos_sugeridos"] == ["registro_operacional_corte"]
    assert [f["chave"] for f in pacote["topic_matrix"]["fatos_publicos"]] == ["corte_efetivo"]
    assert pacote["topic_matrix"]["fatos_publicos"][0]["obrigatorio"] is True


# ======================================= 13: Modelo Oficial e textos intactos

def test_13_modelo_oficial_manifesto_e_catalogo_inalterados():
    assert T.V1.modelo_sha256 == "1e2aa2a52c3341e680acd674658b41c27004a27f5f99c7343643d4d254747a9e"
    assert hashlib.sha256(T.V1.manifesto_path.read_bytes()).hexdigest() == \
        "4b204acc352836ee2a09cc2408bfae7cd10196fed994c009e7db41b0ea50d46a"
    assert hashlib.sha256(T.V1.catalogo_path.read_bytes()).hexdigest() == \
        "3d710366ab4b06a223712c304ebfb3cfef9ea9206ff025dcd6eb8f973d7b2ac2"


@pytest.mark.docx_real
@pytest.mark.anyio
async def test_13_host_ingenuo_gera_o_docx_com_texto_fixo_intacto(modelo_v1_local, monkeypatch):
    """Fim a fim: pacote -> host ingênuo -> DOCX, com Template Lock,
    fidelidade e round-trip do próprio finalizador, e o texto fixo
    incondicional presente."""
    from mcp import Client
    import server
    monkeypatch.setattr(lr, "avaliar_corpus_rag", lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(fp, "_agora", lambda: HOJE)
    capturado = {}
    original = fp.finalizar_peca

    def _capturar(entrada):
        r = original(entrada)
        capturado["r"] = r
        return r
    monkeypatch.setattr(fp, "finalizar_peca", _capturar)
    async with Client(server.mcp, raise_exceptions=True) as cliente:
        pacote = await _preparar(cliente)
        assert pacote["proveniencia"]["modelo_oficial_sha256"] == T.V1.modelo_sha256
        r = await _finalizar(cliente, _host_ingenuo(pacote, TOPICOS_CASO_REAL, COMPROVADOS_CASO_REAL))
    assert r["status"] == "OK", r
    corpo = T._checar_documento(capturado["r"], {
        "SUBBLOCO_CONFORMIDADE_ART_590": True, "SUBBLOCO_ACOMPANHAMENTO_INSPECAO": True,
        "SUBBLOCO_REGISTRO_FOTOGRAFICO": False, "SUBBLOCO_NOTIFICACAO_ADMINISTRATIVA": False})
    assert "R$ 2.097,63" in corpo and "A presente Contestação é tempestiva" in corpo


@pytest.mark.docx_real
@pytest.mark.anyio
async def test_marcadores_de_telas_e_fotos_saem_no_docx_sem_o_host_enviar(modelo_v1_local, monkeypatch):
    from mcp import Client
    import server
    import validate_placeholder_semantics as vs
    monkeypatch.setattr(lr, "avaliar_corpus_rag", lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(fp, "_agora", lambda: HOJE)
    capturado = {}
    original = fp.finalizar_peca

    def _capturar(entrada):
        capturado["r"] = original(entrada)
        return capturado["r"]
    monkeypatch.setattr(fp, "finalizar_peca", _capturar)
    async with Client(server.mcp, raise_exceptions=True) as cliente:
        pacote = await _preparar(cliente)
        entrada = _host_ingenuo(pacote, TOPICOS_TITULARIDADE,
                                COMPROVADOS_TITULARIDADE | {"REGISTRO_FOTOGRAFICO_DOCUMENTADO"})
        assert not {"TELAS_DA_TITULARIDADE", "FOTOS_DA_IRREGULARIADE"} & set(entrada["placeholders"])
        r = await _finalizar(cliente, entrada)
    assert r["status"] == "OK", r
    corpo = T._texto(T._xml(capturado["r"].documento_bytes))
    for marcador in vs.MARCADORES_MANUAIS.values():
        assert marcador in corpo, marcador


@pytest.fixture
def modelo_v1_local(monkeypatch):
    caminho = T._caminho_modelo_v1()
    for var in ("EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT", "EDE_MODELO_OFICIAL_GCS_GENERATION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_PATH", str(caminho))
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", T.V1.modelo_sha256)
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: T._TransporteFake())
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: "https://ede.example.test")
    T._injetar_derivados(monkeypatch)
    return caminho
