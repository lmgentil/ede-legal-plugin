#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate de ativação do Modelo Oficial V1 no homolog (ADR-0020): registro de
versões por SHA pinado, contrato V1 (catálogo + manifesto fixados por
SHA-256), Topic Matrix pública (14 decisões SIM/NÃO + fato de corte),
gates factuais -> NEEDS_INPUT, subblocos A1/A2 e renderer real.

Cenários do gate: A (tudo NÃO), B (tudo SIM com fatos), C (SIM sem gate),
D (corte fato SIM / tópico NÃO), E (corte fato NÃO / tópico SIM), F/G
(CDC SIM/NÃO), H/I (evolução com/sem histórico), J (reconvenção sem
FRA), K/L (subbloco factual presente/ausente), M (placeholder residual),
N (Template Lock), O (fidelidade), P (round-trip).

A-J, e as provas de contrato, rodam sem o .docx. K-P (e B/F/G/H no
render) exigem o Modelo Oficial V1 real, asset privado externo
(ADR-0009): `templates/contestacao/v1/modelo-oficial.docx` (gitignored)
ou `EDE_TEST_MODELO_V1_PATH`; SKIP explícito se ausente ou com SHA-256
diferente do aprovado.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "mcp_server"))

import docx_block_engine as be  # noqa: E402
import docx_fidelidade_independente as fi  # noqa: E402
import docx_round_trip as rt  # noqa: E402
import finalizar_peca as fp  # noqa: E402
import modelo_oficial_versoes as mov  # noqa: E402
import topic_matrix as tm  # noqa: E402
import validate_placeholder_semantics as vs  # noqa: E402
from docx_package import extrair_pacote_docx  # noqa: E402

V1 = mov.VERSAO_V1
MANIFESTO = json.loads(V1.manifesto_path.read_text(encoding="utf-8"))
CATALOGO = json.loads(V1.catalogo_path.read_text(encoding="utf-8"))
CAP = "contestacao.irregularidade_consumo"

TOPICOS_DO_GATE = {
    "Inaplicabilidade do CDC",
    "Revogação da gratuidade de justiça",
    "Ausência de interesse de agir",
    "Ilegitimidade ativa: UC em nome de terceiro",
    "Inépcia da petição inicial",
    "Impugnação ao valor da causa",
    "Evolução do consumo após a regularização",
    "Dever legal de fiscalização",
    "Desnecessidade de aviso prévio à inspeção",
    "Regularidade dos cálculos de recuperação",
    "Licitude da cobrança e do corte/suspensão",
    "Nexo causal indemonstrado",
    "Descabimento de dano moral",
    "Reconvenção para cobrança do débito",
}
CHAVES = [t["chave"] for t in MANIFESTO["topicos_decisao_advogado"]]
GATES = sorted({f for t in MANIFESTO["topicos_decisao_advogado"] for f in t["gate_factual"]} - {"CORTE_EFETIVO"})
FATOS_SUBBLOCOS = {
    "SUBBLOCO_CONFORMIDADE_ART_590": "PROCEDIMENTO_ART_590_DOCUMENTADO",
    "SUBBLOCO_REGISTRO_FOTOGRAFICO": "REGISTRO_FOTOGRAFICO_DOCUMENTADO",
    "SUBBLOCO_ACOMPANHAMENTO_INSPECAO": "INSPECAO_ACOMPANHADA_DOCUMENTADA",
    "SUBBLOCO_NOTIFICACAO_ADMINISTRATIVA": "NOTIFICACAO_AUTORA_DOCUMENTADA",
    "SUBBLOCO_LEVANTAMENTO_CARGA": "LEVANTAMENTO_CARGA_DOCUMENTADO",
}
FRASES = {
    "SUBBLOCO_CONFORMIDADE_ART_590": "todos esses elementos foram integralmente observados",
    "SUBBLOCO_REGISTRO_FOTOGRAFICO": "Vejamos imagens da inspeção realizada",
    "SUBBLOCO_ACOMPANHAMENTO_INSPECAO": "a inspeção foi acompanhada pelo representante",
    "SUBBLOCO_NOTIFICACAO_ADMINISTRATIVA": "A parte Autora também recebeu a documentação",
    "SUBBLOCO_LEVANTAMENTO_CARGA": "procedeu ao levantamento de carga",
    "SUBBLOCO_ONUS_NAO_DESTINATARIO_FINAL": "utilizam a energia como insumo",
    "SUBBLOCO_ONUS_ENTES_ESTRUTURADOS": "Tampouco se justifica, sem peculiaridade concreta",
}
SEMPRE = (
    "A distribuição do ônus da prova, por se tratar de regra de julgamento",
    "Não é juridicamente aceitável transferir ao Réu",
    "Nos termos do art. 590 da referida Resolução",
    "MARCELO SALLES DE MENDONÇA",
)
TERMOS_INTERNOS = re.compile(r"BLOCO|SUBBLOCO|ZONA|\{\{|[A-Z]{3,}_[A-Z_]{3,}")


def _todos(resposta):
    return {k: resposta for k in CHAVES}


INFORMATIVOS = {t["suporte_informativo"]["fato"] for t in MANIFESTO["topicos_decisao_advogado"]
                if t.get("suporte_informativo")}


def _fatos_todos_verdadeiros():
    return {**{g: True for g in GATES}, **{f: True for f in FATOS_SUBBLOCOS.values()},
            **{f: True for f in INFORMATIVOS},
            "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA": True,
            "EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS": True}


# ADR-0021: o finalizador V1 deriva JUIZO (DataJud, injetado), a
# tempestividade (a partir da disponibilização), a data da peça (relógio
# injetado) e o proveito econômico (a partir dos pedidos).
MARCO = {"tipo": "DISPONIBILIZACAO", "data": "01/09/2026"}
JUIZO_FAKE = "AO JUÍZO DA VARA DE TESTE DA COMARCA DE SALVADOR"
PEDIDOS = [{"descricao": "declaração de inexistência do débito", "valor": "R$ 2.097,63", "fonte": "inicial"},
           {"descricao": "indenização por danos morais", "valor": "R$ 12.900,00", "fonte": "inicial"}]
RESERVADOS = set(MANIFESTO["estados_reservados_ao_core"])


def _injetar_derivados(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(fp, "_obter_resolvedor_juizo",
                        lambda: (lambda numero, cache_path=None: {"juizo": JUIZO_FAKE}))
    monkeypatch.setattr(fp, "_agora", lambda: datetime(2026, 9, 10, 12, 0, tzinfo=ZoneInfo("America/Bahia")))


def _extras(topicos):
    extras = {"marco_tempestividade": MARCO}
    if topicos.get("impugnacao_valor_causa") == "SIM":
        extras["pedidos_economicos"] = PEDIDOS
    return extras


# ====================================================== contrato versionado

def test_catalogo_e_manifesto_v1_batem_com_os_sha256_aprovados():
    assert hashlib.sha256(V1.catalogo_path.read_bytes()).hexdigest() == \
        "3d710366ab4b06a223712c304ebfb3cfef9ea9206ff025dcd6eb8f973d7b2ac2"
    assert hashlib.sha256(V1.manifesto_path.read_bytes()).hexdigest() == \
        "42308f8a3f7c52461b0094979426e67fcdb577629fd7683e6d48d048c37c28d6"
    # ADR-0020: manifesto imutável — o 1.0.0 continua no repositório, byte a byte.
    assert hashlib.sha256((V1.manifesto_path.parent / "manifesto.json").read_bytes()).hexdigest() == \
        "f703966d0e05ad0ae79a7bd680ada6b2d720bff76125c4793b42d3cec0414a5b"
    assert V1.modelo_sha256 == "1e2aa2a52c3341e680acd674658b41c27004a27f5f99c7343643d4d254747a9e"
    mov.verificar_integridade(V1)


def test_manifesto_v1_definitivo_e_environment_neutral():
    assert MANIFESTO["manifesto_versao"] == "1.1.0"
    assert MANIFESTO["modelo_oficial"]["status"] == "APROVADO"
    assert MANIFESTO["modelo_oficial"]["catalogo_blocos"] == "blocos.json"
    texto = V1.manifesto_path.read_text(encoding="utf-8")
    for proibido in ("HOMOLOG", "PRODUCAO", "CANDIDATO", "ede-mcp", "gs://"):
        assert proibido not in texto, proibido


def test_versao_e_resolvida_pelo_sha_pinado_e_legado_permanece_intacto():
    assert mov.resolver_versao(V1.modelo_sha256) is V1
    assert mov.resolver_versao(V1.modelo_sha256.upper()) is V1
    assert mov.resolver_versao(mov.VERSAO_LEGADA.modelo_sha256) is mov.VERSAO_LEGADA
    assert mov.resolver_versao("0" * 64) is mov.VERSAO_LEGADA
    assert mov.resolver_versao(None) is mov.VERSAO_LEGADA
    assert mov.VERSAO_LEGADA.catalogo_path == BASE / "templates" / "contestacao" / "blocos.json"
    assert mov.carregar_manifesto(mov.VERSAO_LEGADA) is None


def test_integridade_falha_fechado_se_catalogo_divergir(tmp_path):
    copia = tmp_path / "blocos.json"
    copia.write_bytes(V1.catalogo_path.read_bytes() + b" ")
    adulterada = mov.VersaoModelo(**{**V1.__dict__, "catalogo_path": copia})
    with pytest.raises(mov.IntegridadeVersaoModelo):
        mov.verificar_integridade(adulterada)


def test_manifesto_e_catalogo_sao_compativeis_e_cobrem_os_14_topicos_do_gate():
    tm.verificar_compatibilidade(MANIFESTO, CATALOGO)
    assert {t["nome_publico"] for t in MANIFESTO["topicos_decisao_advogado"]} == TOPICOS_DO_GATE
    assert [e["chave"] for e in MANIFESTO["entradas_factuais_publicas"]] == ["corte_efetivo"]
    for novo in ("DEFICIENCIAS_INICIAL_DOCUMENTADAS", "FATURA_RECUPERACAO_DOCUMENTADA"):
        assert novo in GATES


def test_topic_matrix_publica_nao_expoe_ids_tags_placeholders_ou_estados():
    publico = tm.descrever_topic_matrix_publica(MANIFESTO)
    texto = json.dumps(publico, ensure_ascii=False)
    for t in MANIFESTO["topicos_decisao_advogado"]:
        assert t["topic_id"] not in texto
    assert not re.search(r"BLOCO:|SUBBLOCO|\{\{|CORTE_EFETIVO|GRATUIDADE_CONCEDIDA", texto)
    assert len(publico["topicos"]) == 14 and len(publico["fatos_publicos"]) == 1


# ========================================================= tradução (A-J)

def test_A_todos_os_topicos_nao():
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("NAO"), {"corte_efetivo": "NAO"}, {})
    assert r.status == "OK", r.pendencias
    assert set(r.block_decisions.values()) == {"EXCLUIR"}
    estados = be.validar_e_resolver_decisoes(CATALOGO, {k: {"decisao": v} for k, v in r.block_decisions.items()},
                                              r.estado_processual_motor)
    for t in MANIFESTO["topicos_decisao_advogado"]:
        assert estados[t["topic_id"]] == "EXCLUIR", t["chave"]
    assert estados["PRELIMINARES"] == "EXCLUIR"


def test_B_todos_os_topicos_sim_com_fatos_suficientes_traduz_para_incluir():
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("SIM"), {"corte_efetivo": "SIM"}, _fatos_todos_verdadeiros())
    assert r.status == "OK", r.pendencias
    estados = be.validar_e_resolver_decisoes(CATALOGO, {k: {"decisao": v} for k, v in r.block_decisions.items()},
                                              r.estado_processual_motor)
    for t in MANIFESTO["topicos_decisao_advogado"]:
        assert estados[t["topic_id"]] == "INCLUIR", t["chave"]


@pytest.mark.parametrize("gate", GATES)
def test_C_sim_sem_suporte_factual_devolve_needs_input_em_linguagem_juridica(gate):
    fatos = _fatos_todos_verdadeiros()
    fatos.pop(gate)
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("SIM"), {"corte_efetivo": "SIM"}, fatos)
    assert r.status == "NEEDS_INPUT"
    assert not r.block_decisions
    assert len(r.pendencias) == 1
    assert tm.DESCRICAO_SUPORTE_FACTUAL[gate] in r.pendencias[0]
    assert not TERMOS_INTERNOS.search(r.pendencias[0]), r.pendencias[0]


@pytest.mark.parametrize("valor", [False, "INDETERMINADO"])
def test_C_fato_falso_ou_indeterminado_nunca_vira_inclusao(valor):
    fatos = {**_fatos_todos_verdadeiros(), "EVOLUCAO_CONSUMO_DOCUMENTADA": valor}
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("SIM"), {"corte_efetivo": "SIM"}, fatos)
    assert r.status == "NEEDS_INPUT"


def test_D_corte_fato_sim_e_topico_nao_exclui_o_topico_sem_negar_o_fato():
    topicos = {**_todos("NAO"), "licitude_cobranca_corte": "NAO"}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "SIM"}, {})
    assert r.status == "OK"
    assert r.block_decisions["LICITUDE_CORTE_SUSPENSAO"] == "EXCLUIR"
    assert r.estado_processual_motor["CORTE_EFETIVO"] is True


def test_E_corte_fato_nao_e_topico_sim_devolve_needs_input():
    topicos = {**_todos("NAO"), "licitude_cobranca_corte": "SIM"}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {})
    assert r.status == "NEEDS_INPUT"
    assert "não houve corte ou suspensão efetiva" in r.pendencias[0]


def test_corte_nunca_e_inferido_da_decisao_do_topico_nem_o_inverso():
    r = tm.traduzir(MANIFESTO, CATALOGO, {**_todos("NAO"), "licitude_cobranca_corte": "SIM"}, {}, {})
    assert r.status == "NEEDS_INPUT"
    assert any("Houve corte ou suspensão efetiva" in p for p in r.pendencias)
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("NAO"), {"corte_efetivo": "SIM"}, {})
    assert r.block_decisions["LICITUDE_CORTE_SUSPENSAO"] == "EXCLUIR"


def test_corte_divergente_entre_resposta_e_documentos_devolve_needs_input():
    r = tm.traduzir(MANIFESTO, CATALOGO, _todos("NAO"), {"corte_efetivo": "SIM"}, {"CORTE_EFETIVO": False})
    assert r.status == "NEEDS_INPUT"


@pytest.mark.parametrize("resposta", ["SIM", "NAO"])
def test_F_G_cdc_espelha_nos_subblocos_do_onus(resposta):
    topicos = {**_todos("NAO"), "inaplicabilidade_cdc": resposta}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {})
    estados = be.validar_e_resolver_decisoes(CATALOGO, {k: {"decisao": v} for k, v in r.block_decisions.items()},
                                              r.estado_processual_motor)
    esperado = "INCLUIR" if resposta == "SIM" else "EXCLUIR"
    assert estados["SUBBLOCO_ONUS_NAO_DESTINATARIO_FINAL"] == esperado
    assert estados["SUBBLOCO_ONUS_ENTES_ESTRUTURADOS"] == esperado


def test_H_evolucao_sim_com_historico_inclui():
    topicos = {**_todos("NAO"), "evolucao_consumo": "SIM"}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {"EVOLUCAO_CONSUMO_DOCUMENTADA": True})
    assert r.status == "OK" and r.block_decisions["EVOLUCAO_CONSUMO"] == "INCLUIR"


def test_I_evolucao_sim_sem_historico_devolve_needs_input():
    topicos = {**_todos("NAO"), "evolucao_consumo": "SIM"}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {})
    assert r.status == "NEEDS_INPUT"
    assert "Evolução do consumo após a regularização" in r.pendencias[0]


def test_J_reconvencao_sim_sem_fra_devolve_needs_input():
    topicos = {**_todos("NAO"), "reconvencao_cobranca_debito": "SIM"}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {})
    assert r.status == "NEEDS_INPUT"
    assert "valor do débito apurado" in r.pendencias[0]


def test_state_linked_nao_do_advogado_prevalece_sobre_fato_verdadeiro():
    topicos = {**_todos("NAO")}
    r = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, {"GRATUIDADE_CONCEDIDA": True})
    estados = be.validar_e_resolver_decisoes(CATALOGO, {k: {"decisao": v} for k, v in r.block_decisions.items()},
                                              r.estado_processual_motor)
    assert estados["PRELIMINAR_REVOGACAO_GRATUIDADE"] == "EXCLUIR"


def test_respostas_faltantes_listam_todas_as_perguntas():
    r = tm.traduzir(MANIFESTO, CATALOGO, {}, {}, {})
    assert r.status == "NEEDS_INPUT"
    assert len(r.pendencias) == 15
    assert all(p.startswith("Responda SIM ou NÃO: ") for p in r.pendencias)


def test_chave_desconhecida_ou_resposta_invalida_e_input_invalido():
    assert tm.traduzir(MANIFESTO, CATALOGO, {"tese_nova": "SIM"}, {}, {}).status == "INVALID"
    assert tm.traduzir(MANIFESTO, CATALOGO, {"inaplicabilidade_cdc": "TALVEZ"}, {}, {}).status == "INVALID"


def test_todo_fato_de_gate_tem_descricao_publica():
    for t in MANIFESTO["topicos_decisao_advogado"]:
        for f in t["gate_factual"]:
            assert f in tm.DESCRICAO_SUPORTE_FACTUAL


# ====================================================== finalizador (sem docx)

@pytest.fixture
def ambiente_v1(monkeypatch):
    monkeypatch.delenv("EDE_MODELO_OFICIAL_GCS_BUCKET", raising=False)
    monkeypatch.delenv("EDE_MODELO_OFICIAL_GCS_OBJECT", raising=False)
    monkeypatch.delenv("EDE_MODELO_OFICIAL_GCS_GENERATION", raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", V1.modelo_sha256)
    _injetar_derivados(monkeypatch)


def test_finalizador_v1_devolve_needs_input_antes_de_qualquer_render(ambiente_v1):
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": {}, "topicos": _todos("NAO")})
    assert r.status == "NEEDS_INPUT" and r.stage == "topic_matrix"
    assert r.documento_bytes is None and r.download_url is None
    assert any("corte ou suspensão" in p for p in r.pendencias)


def test_finalizador_v1_recusa_decisao_por_bloco(ambiente_v1):
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": {},
                           "block_decisions": {"PRELIMINAR_CDC_INAPLICAVEL": "INCLUIR"}})
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


def test_finalizador_legado_recusa_topicos(monkeypatch):
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", mov.VERSAO_LEGADA.modelo_sha256)
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": {}, "topicos": _todos("NAO")})
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


def test_adapter_mcp_serializa_needs_input(ambiente_v1):
    import server
    resposta = server.ede_finalizar_peca(server.EdeFinalizarPecaEntrada(
        capability_id=CAP, topicos=_todos("NAO"), fatos_publicos={}))
    corpo = json.loads(resposta[0].text)
    assert corpo["status"] == "NEEDS_INPUT"
    assert corpo["pendencias"] and "download_url" not in corpo


def test_telemetria_aceita_needs_input_e_estagio_topic_matrix():
    import auth_logging as telemetria
    assert "NEEDS_INPUT" in telemetria.RESULTADOS_FINALIZACAO
    assert telemetria.ESTAGIOS_FINALIZACAO == fp.ETAPAS


# ======================================================== render real (B, F-P)

CAMINHO_MODELO_V1 = Path(os.environ.get("EDE_TEST_MODELO_V1_PATH")
                         or BASE / "templates" / "contestacao" / "v1" / "modelo-oficial.docx")


def _caminho_modelo_v1() -> Path:
    """SKIP (razão canônica ADR-0009) só quando o asset não está
    instalado; presente com SHA diferente do aprovado é FALHA — nunca um
    modelo errado escondido atrás de um SKIP."""
    if not CAMINHO_MODELO_V1.is_file():
        pytest.skip(f"{CAMINHO_MODELO_V1} não instalado localmente — asset institucional externo (ADR-0009).")
    sha = hashlib.sha256(CAMINHO_MODELO_V1.read_bytes()).hexdigest()
    if sha != V1.modelo_sha256:
        pytest.fail(f"Modelo V1 local com SHA-256 {sha} diferente do aprovado {V1.modelo_sha256}.")
    return CAMINHO_MODELO_V1


class _TransporteFake:
    def __init__(self):
        self.objetos = {}

    def enviar(self, object_name, dados, content_type, metadata):
        self.objetos[object_name] = (dados, content_type, dict(metadata))

    def excluir(self, object_name):
        self.objetos.pop(object_name, None)
        return True

    def listar(self, prefixo, limite):
        return []


@pytest.fixture
def modelo_v1_local(monkeypatch):
    caminho = _caminho_modelo_v1()
    for var in ("EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT", "EDE_MODELO_OFICIAL_GCS_GENERATION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_PATH", str(caminho))
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", V1.modelo_sha256)
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: _TransporteFake())
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: "https://ede.example.test")
    _injetar_derivados(monkeypatch)
    return caminho


def _placeholders():
    return {
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "ligação direta (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]",
        "VALOR_FRA": "R$ 1.234,56 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 10.000,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "SINOPSE_FATOS_NUCLEO_OBJETO": "Objeto fictício de teste (dado fictício de teste).",
        "CONTA_CONTRATO": "0000000000 (dado fictício de teste)",
        "NOME_TITULAR_DA_UC": "CICLANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TELAS_DA_TITULARIDADE": "[INSERIR MANUALMENTE AS TELAS/DOCUMENTOS DA TITULARIDADE DA UC]",
        "VALOR_DA_CAUSA": "R$ 10.000,00",
    }


def _placeholders_legado():
    """Contrato legado (produção): o host continua enviando os quatro
    campos que o V1 deriva — ADR-0021 não muda o legado."""
    return {**_placeholders(),
            "JUIZO": "AO JUÍZO DA VARA CÍVEL DA COMARCA DE SALVADOR/BA (DADOS FICTÍCIOS DE TESTE)",
            "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
            "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
            "VALOR_TOTAL_PROVEITO_ECONOMICO": "R$ 15.000,00 (dado fictício de teste)"}


def _finalizar(topicos, corte, fatos):
    fatos = {k: v for k, v in fatos.items() if k not in RESERVADOS}  # derivados pelo Core (ADR-0021)
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": _placeholders(), "topicos": topicos,
                           "fatos_publicos": {"corte_efetivo": corte}, "estado_processual": fatos,
                           **_extras(topicos)})
    assert r.status == "OK", (r.status, r.stage, r.error_code, r.motivo, r.pendencias)
    return r


def _xml(documento: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        docx = Path(tmp) / "g.docx"
        docx.write_bytes(documento)
        extrair_pacote_docx(docx, Path(tmp) / "g")
        return (Path(tmp) / "g" / "word" / "document.xml").read_text(encoding="utf-8")


def _texto(xml: str) -> str:
    return "\n".join(re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S))


def _checar_documento(r, estados_esperados_subblocos):
    xml = _xml(r.documento_bytes)
    corpo = _texto(xml)
    # M: nenhum placeholder nem marca de composição residual
    assert "{{" not in xml and "}}" not in xml
    assert not re.search(r'w:val="(BLOCO|SUBBLOCO|ZONA|INLINE):', xml)
    for sb, presente in estados_esperados_subblocos.items():
        assert (FRASES[sb] in corpo) == presente, sb
    for frase in SEMPRE:
        assert frase in corpo, frase
    assert hashlib.sha256(r.documento_bytes).hexdigest() == r.documento_sha256
    return corpo


@pytest.mark.docx_real
def test_B_K_M_O_P_tudo_sim_com_fatos_gera_docx_completo(modelo_v1_local):
    r = _finalizar(_todos("SIM"), "SIM", _fatos_todos_verdadeiros())
    corpo = _checar_documento(r, {sb: True for sb in FRASES})
    # único aviso: o resultado da conferência do valor da causa (ADR-0021)
    assert len(r.dados_nao_bloqueantes) == 1
    assert r.dados_nao_bloqueantes[0].startswith("Impugnação ao valor da causa:")
    assert "A média de consumo da unidade consumidora aumentou" in corpo
    assert "COM RECONVENÇÃO" in corpo.upper()


@pytest.mark.docx_real
def test_A_M_tudo_nao_gera_docx_so_com_o_nucleo_incondicional(modelo_v1_local):
    r = _finalizar(_todos("NAO"), "NAO", {f: True for f in FATOS_SUBBLOCOS.values()})
    corpo = _checar_documento(r, {**{sb: True for sb in FATOS_SUBBLOCOS if sb != "SUBBLOCO_LEVANTAMENTO_CARGA"},
                                  "SUBBLOCO_LEVANTAMENTO_CARGA": False,
                                  "SUBBLOCO_ONUS_NAO_DESTINATARIO_FINAL": False,
                                  "SUBBLOCO_ONUS_ENTES_ESTRUTURADOS": False})
    assert "DAS PRELIMINARES" not in corpo.upper()
    assert "A média de consumo da unidade consumidora aumentou" not in corpo


@pytest.mark.docx_real
@pytest.mark.parametrize("cdc", ["SIM", "NAO"])
def test_F_G_cdc_no_documento(modelo_v1_local, cdc):
    topicos = {**_todos("NAO"), "inaplicabilidade_cdc": cdc}
    r = _finalizar(topicos, "NAO", {f: True for f in FATOS_SUBBLOCOS.values()})
    presente = cdc == "SIM"
    _checar_documento(r, {"SUBBLOCO_ONUS_NAO_DESTINATARIO_FINAL": presente,
                          "SUBBLOCO_ONUS_ENTES_ESTRUTURADOS": presente})


@pytest.mark.docx_real
def test_H_K_evolucao_com_historico_e_levantamento_de_carga(modelo_v1_local):
    topicos = {**_todos("NAO"), "evolucao_consumo": "SIM"}
    fatos = {"EVOLUCAO_CONSUMO_DOCUMENTADA": True, **{f: True for f in FATOS_SUBBLOCOS.values()}}
    r = _finalizar(topicos, "NAO", fatos)
    corpo = _checar_documento(r, {"SUBBLOCO_LEVANTAMENTO_CARGA": True})
    assert "A média de consumo da unidade consumidora aumentou" in corpo


@pytest.mark.docx_real
def test_L_subbloco_sem_prova_sai_sozinho_e_gera_dado_nao_bloqueante(modelo_v1_local):
    topicos = {**_todos("NAO"), "evolucao_consumo": "SIM"}
    fatos = {"EVOLUCAO_CONSUMO_DOCUMENTADA": True, "REGISTRO_FOTOGRAFICO_DOCUMENTADO": True,
             "NOTIFICACAO_AUTORA_DOCUMENTADA": True}
    r = _finalizar(topicos, "NAO", fatos)
    corpo = _checar_documento(r, {
        "SUBBLOCO_CONFORMIDADE_ART_590": False, "SUBBLOCO_REGISTRO_FOTOGRAFICO": True,
        "SUBBLOCO_ACOMPANHAMENTO_INSPECAO": False, "SUBBLOCO_NOTIFICACAO_ADMINISTRATIVA": True,
        "SUBBLOCO_LEVANTAMENTO_CARGA": False,
    })
    assert "A média de consumo da unidade consumidora aumentou" in corpo  # resto do tópico preservado
    assert len(r.dados_nao_bloqueantes) == 3
    assert any("art. 590" in a for a in r.dados_nao_bloqueantes)
    assert any("levantamento de carga" in a for a in r.dados_nao_bloqueantes)
    assert not any(TERMOS_INTERNOS.search(a) for a in r.dados_nao_bloqueantes)


@pytest.mark.docx_real
def test_L_sem_prova_fotografica_o_placeholder_de_fotos_nao_e_exigido(modelo_v1_local):
    dados = _placeholders()
    dados.pop("FOTOS_DA_IRREGULARIADE")
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": dados, "topicos": _todos("NAO"),
                           "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": {},
                           "marco_tempestividade": MARCO})
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    assert any("fotografias" in a for a in r.dados_nao_bloqueantes)


def _adulterador(original, so_primeira_chamada):
    chamadas = []

    def adulterar(xml, dados):
        gerado, n = original(xml, dados)
        chamadas.append(1)
        if so_primeira_chamada and len(chamadas) > 1:
            return gerado, n
        return gerado.replace("Nos termos do art. 590", "Nos termos do art. 591"), n
    return adulterar


@pytest.mark.docx_real
def test_N_template_lock_reprova_alteracao_de_texto_fixo(modelo_v1_local, monkeypatch):
    # 1ª chamada = geração; 2ª = recomputação independente do Template Lock.
    monkeypatch.setattr(be, "substituir_placeholders", _adulterador(be.substituir_placeholders, True))
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": _placeholders(), "topicos": _todos("NAO"),
                           "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": {},
                           "marco_tempestividade": MARCO})
    assert r.status == "REFUSED" and r.error_code == "TEMPLATE_LOCK_FAILED"
    assert r.documento_bytes is None


@pytest.mark.docx_real
def test_O_fidelidade_independente_pega_adulteracao_que_engana_o_lock(modelo_v1_local, monkeypatch):
    # Adulteração nos dois lados engana o Template Lock (mesma função);
    # a fidelidade independente, que nunca chama o renderer, reprova.
    monkeypatch.setattr(be, "substituir_placeholders", _adulterador(be.substituir_placeholders, False))
    r = fp.finalizar_peca({"capability_id": CAP, "placeholders": _placeholders(), "topicos": _todos("NAO"),
                           "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": {},
                           "marco_tempestividade": MARCO})
    assert r.status == "REFUSED" and r.stage == "post_render_fidelity"
    assert r.documento_bytes is None


@pytest.mark.docx_real
def test_O_P_fidelidade_e_round_trip_independentes_sobre_o_documento_final(modelo_v1_local):
    topicos = {**_todos("NAO"), "inaplicabilidade_cdc": "SIM", "evolucao_consumo": "SIM"}
    fatos = {"EVOLUCAO_CONSUMO_DOCUMENTADA": True, "REGISTRO_FOTOGRAFICO_DOCUMENTADO": True}
    r = _finalizar(topicos, "NAO", fatos)
    trad = tm.traduzir(MANIFESTO, CATALOGO, topicos, {"corte_efetivo": "NAO"}, fatos)
    estados = be.validar_e_resolver_decisoes(
        CATALOGO, {k: {"decisao": v} for k, v in trad.block_decisions.items()}, trad.estado_processual_motor)
    zonas = be.resolver_estados_zonas(CATALOGO, estados, None, trad.estado_processual_motor)
    with tempfile.TemporaryDirectory() as tmp:
        extrair_pacote_docx(modelo_v1_local, Path(tmp) / "t")
        template_xml = (Path(tmp) / "t" / "word" / "document.xml").read_text(encoding="utf-8")
    gerado_xml = _xml(r.documento_bytes)
    assert fi.verificar_sequencia_locked(template_xml, gerado_xml, CATALOGO, estados, zonas) == []
    assert fi.verificar_sdts_bloco(gerado_xml, CATALOGO, estados) == []
    assert fi.escanear_tokens_residuais(gerado_xml) == []
    sempre, dono = vs.placeholders_por_visibilidade(V1.placeholder_bloco_dono_extra)
    dados = _placeholders()
    alcancaveis = (set(sempre) | {n for n, b in dono.items() if estados.get(b) == "INCLUIR"}) & set(dados)
    extraido = rt.extrair_valores_gerados(template_xml, gerado_xml, CATALOGO, estados, zonas, nomes=list(dados))
    assert rt.comparar_round_trip(dados, extraido, alcancaveis) == []
    assert "FOTOS_DA_IRREGULARIADE" in alcancaveis
