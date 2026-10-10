"""
Privacidade do gate de fidelidade ao comando (manifesto 1.4.0).

Prova, sobre os logs REAIS de requisições reais à app HTTP autenticada
(a mesma que `server.main()` serve), que nada do conteúdo da peça nem das
orientações do advogado alcança logs ou telemetria: texto e termos de
`orientacoes_advogado`, o trecho que contraria TRATAR_APENAS_COMO_FATO,
SINOPSE_FATOS, REALIDADE_FATICA, DESENVOLVIMENTO_TECNICO_IRREGULARIDADE,
PEDIDOS_FINAIS, conteúdo de zonas e fatos/documentos do processo.

Cada campo carrega um marcador único; todos os registros de TODOS os
loggers (nível DEBUG) e toda a saída do processo (stdout/stderr) são
varridos. A telemetria de finalização só pode conter campos da allowlist
fechada de `auth_logging` — nenhum campo de orientação existe nela.
"""
from __future__ import annotations

import io
import json
import logging
import sys
import zipfile
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

import oauth_harness as h  # noqa: E402
import auth_logging as telemetria  # noqa: E402
import finalizar_peca as fp  # noqa: E402
import test_mcp_oauth as O  # noqa: E402
import test_topic_matrix_v1 as T  # noqa: E402
from auth_config import ESCOPO_HEALTH, ESCOPO_LEGAL  # noqa: E402
from test_topic_matrix_v1 import modelo_v1_local  # noqa: E402,F401

MARCADORES = {
    "SINOPSE_FATOS": "Privsinopse7781",
    "REALIDADE_FATICA": "Privrealidade7782",
    "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Privdesenv7783",
    "PEDIDOS_FINAIS": "Privpedidos7784",
    "termo_nao_mencionar": "privtermo7785",
    "zona": "Privzona7786",
    "fato": "Privfato7787",
    "documento": "Privdoc7788",
    "tratar_como_fato": "Privcorte7789",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _placeholders(**extra):
    ph = {**T._placeholders(),
          "SINOPSE_FATOS": f"A autora relata a cobrança {MARCADORES['SINOPSE_FATOS']}.",
          "REALIDADE_FATICA": f"A inspeção seguiu o procedimento {MARCADORES['REALIDADE_FATICA']}.",
          "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": f"Derivação no ramal {MARCADORES['DESENVOLVIMENTO_TECNICO_IRREGULARIDADE']}.",
          "PEDIDOS_FINAIS": f"a) julgar improcedentes os pedidos {MARCADORES['PEDIDOS_FINAIS']}."}
    ph.update(extra)
    return ph


def _entrada(placeholders, orientacoes, zonas=None):
    topicos = T._todos("NAO")
    entrada = {"capability_id": T.CAP, "placeholders": placeholders, "topicos": topicos,
               "fatos_publicos": {"corte_efetivo": "NAO"},
               "estado_processual": {f: True for f in T.FATOS_SUBBLOCOS.values()},
               "orientacoes_advogado": orientacoes, **T._extras(topicos)}
    if zonas:
        entrada["zonas"] = zonas
    return entrada


ORIENTACOES = [
    {"tipo": "NAO_MENCIONAR", "termos": [MARCADORES["termo_nao_mencionar"]]},
    {"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "corte_suspensao"},
    {"tipo": "ENFATIZAR"},
]


def _varrer(textos: list[str]) -> list[str]:
    bruto = "\n".join(textos).lower()
    return [nome for nome, m in MARCADORES.items() if m.lower() in bruto]


@pytest.mark.anyio
@pytest.mark.docx_real
async def test_orientacoes_e_conteudo_da_peca_nunca_alcancam_logs_nem_telemetria(
        modelo_v1_local, caplog, capfd):
    token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
    sucesso = _entrada(_placeholders(), ORIENTACOES)
    violacao = _entrada(
        _placeholders(SINOPSE_FATOS=f"A autora cita {MARCADORES['termo_nao_mencionar']} na inicial.",
                      REALIDADE_FATICA=f"O fornecimento foi suspenso e o corte foi legítimo "
                                       f"{MARCADORES['tratar_como_fato']}."),
        ORIENTACOES)
    rejeitada = _entrada(
        _placeholders(), [{"tipo": "INCLUIR_TOPICO"}, *ORIENTACOES],
        zonas={"conteudo": {"ZONA_METODOLOGIA_APURACAO": {
                   "conteudo": f"Consumo recuperado de 2.412 kWh {MARCADORES['zona']}.",
                   "fatos": [{"tipo": "consumo_recuperado", "valor": "2.412", "unidade": "kWh",
                              "fonte": f"{MARCADORES['documento']}.pdf", "natureza": "documental"}]}},
               "base_documental": [{"fact": f"Memorial de cálculo {MARCADORES['fato']}.",
                                    "tipo": "FATO_DOCUMENTADO", "source_document": f"{MARCADORES['documento']}.pdf"}]})
    preparar = {"fatos": [{"fact": f"TOI lavrado na inspeção {MARCADORES['fato']}.",
                           "tipo": "FATO_DOCUMENTADO", "source_document": f"{MARCADORES['documento']}.pdf"}]}

    with caplog.at_level(logging.DEBUG):
        async with O.app_autenticada() as (app, config):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                r_prep = await cliente.call_tool("ede_preparar_contestacao", {"entrada": preparar})
                respostas = [json.loads((await cliente.call_tool("ede_finalizar_peca", {"entrada": e}))
                                        .content[0].text)
                             for e in (sucesso, violacao, rejeitada)]
    saida = capfd.readouterr()

    # As três chamadas exercitaram o caminho certo (senão a prova é vazia).
    ok, refused_violacao, refused_orientacao = respostas
    assert ok["status"] == "OK", ok
    assert [o["tipo"] for o in ok["orientacoes_aplicadas"]] == ["NAO_MENCIONAR", "TRATAR_APENAS_COMO_FATO"]
    assert refused_violacao["stage"] == "fidelidade_comando"
    assert {v["regra"] for v in refused_violacao["violacoes_fidelidade"]} == {"NAO_MENCIONAR",
                                                                               "TRATAR_APENAS_COMO_FATO"}
    assert refused_orientacao["stage"] == "fidelidade_comando"
    assert refused_orientacao["orientacoes_rejeitadas"][0]["motivo_codigo"] == "ALTERA_TOPICO"
    assert r_prep.is_error is not True and r_prep.structured_content["status"] in ("OK", "PIPELINE_ABORTED")

    # 1. Nenhum marcador em nenhum registro de nenhum logger do SERVIDOR, em
    # nenhum campo, mesmo em DEBUG (produção roda em INFO). Os registros de
    # `mcp.client.*` são do cliente MCP deste teste (o papel do ChatGPT/
    # Claude), que loga em DEBUG o que ENVIA — servem de controle positivo:
    # provam que a varredura detecta os marcadores quando eles estão num log.
    def _textos(registros):
        textos = []
        for r in registros:
            textos.append(r.getMessage())
            textos.extend(str(v) for v in vars(r).values())
        return textos

    cliente_harness = [r for r in caplog.records if r.name.startswith("mcp.client")]
    servidor = [r for r in caplog.records if not r.name.startswith("mcp.client")]
    assert set(_varrer(_textos(cliente_harness))) == set(MARCADORES), "controle positivo da varredura"
    assert servidor, "as requisições precisam produzir logs no servidor para a prova ter conteúdo"
    assert _varrer(_textos(servidor)) == []

    # 2. Nenhum marcador na saída do processo (stdout/stderr).
    assert _varrer([saida.out, saida.err]) == []

    # 3. Telemetria de finalização: só a allowlist fechada; nada de orientação.
    eventos = [json.loads(r.getMessage()) for r in caplog.records if r.name == "ede.mcp.seguranca"]
    finalizacoes = [e for e in eventos if e["evento"] == telemetria.EVENTO_FINALIZACAO_PECA]
    assert [e["resultado_finalizacao"] for e in finalizacoes] == ["OK", "REFUSED", "REFUSED"]
    for e in eventos:
        assert set(e) <= telemetria.CAMPOS_PERMITIDOS
        assert not any("orienta" in campo or "violac" in campo for campo in e)
    assert not any("orienta" in c or "termo" in c for c in telemetria.CAMPOS_PERMITIDOS)


@pytest.mark.docx_real
def test_orientacao_nao_e_gravada_no_docx_nem_em_artefato(modelo_v1_local, monkeypatch):
    """O único artefato persistido (o DOCX entregue) contém a peça, nunca
    a orientação: nem o termo, nem o tipo, nem o conceito."""
    armazenado = {}

    class _Transporte:
        def enviar(self, object_name, dados, content_type, metadata):
            armazenado[object_name] = (dados, dict(metadata))

        def excluir(self, object_name):
            return True

        def listar(self, prefixo, limite):
            return []

    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: _Transporte())
    r = fp.finalizar_peca(_entrada(_placeholders(), ORIENTACOES))
    assert r.status == "OK", (r.stage, r.motivo)
    (dados, metadata), = armazenado.values()
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        xml = "\n".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
    for rastro in (MARCADORES["termo_nao_mencionar"], "NAO_MENCIONAR", "TRATAR_APENAS_COMO_FATO",
                   "corte_suspensao", "ENFATIZAR"):
        assert rastro not in xml
        assert rastro not in json.dumps(metadata)


@pytest.mark.anyio
@pytest.mark.docx_real
async def test_chave_desconhecida_e_campo_ausente_nao_vazam_para_logs(modelo_v1_local, caplog, capfd):
    """Gate de discoverability (0.22.x): o erro de schema por chave
    desconhecida devolve ao HOST o valor recebido (mensagem do validador) e
    MISSING_REQUIRED_FIELD devolve campos_ausentes — nenhum dos dois pode
    alcançar log ou telemetria do servidor."""
    token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
    marcador_extra = "Privextra7790 R$ 15.000,00"
    extra = _entrada(_placeholders(), [])
    extra["VALOR_DA_CAUSA"] = marcador_extra
    ausente = _entrada(_placeholders(PEDIDOS_FINAIS=""), [])
    with caplog.at_level(logging.DEBUG):
        async with O.app_autenticada() as (app, config):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                r_extra = await cliente.call_tool("ede_finalizar_peca", {"entrada": extra})
                r_ausente = await cliente.call_tool("ede_finalizar_peca", {"entrada": ausente})
    saida = capfd.readouterr()
    assert r_extra.is_error and "Privextra7790" in r_extra.content[0].text  # o host recebe para corrigir
    corpo = json.loads(r_ausente.content[0].text)
    assert corpo["error_code"] == "MISSING_REQUIRED_FIELD" and corpo["campos_ausentes"][0]["campo"] == "PEDIDOS_FINAIS"
    servidor = [r for r in caplog.records if not r.name.startswith("mcp.client")]
    textos = [r.getMessage() for r in servidor] + [str(v) for r in servidor for v in vars(r).values()]
    for marcador in ("Privextra7790", *MARCADORES.values()):
        assert marcador.lower() not in "\n".join(textos).lower(), marcador
        assert marcador.lower() not in (saida.out + saida.err).lower(), marcador
    eventos = [json.loads(r.getMessage()) for r in caplog.records if r.name == "ede.mcp.seguranca"]
    assert all(set(e) <= telemetria.CAMPOS_PERMITIDOS for e in eventos)
    assert not any("ausente" in campo for campo in telemetria.CAMPOS_PERMITIDOS)
