# -*- coding: utf-8 -*-
"""
tests/test_preparar_contestacao.py — Gate 6.5-A: scripts/preparar_
contestacao.py (Core determinístico da primeira ferramenta jurídica).

Fixtures SINTÉTICAS apenas (Gate 6.5-A §22) — nenhum nome de litigante ou
número CNJ real em nenhum teste deste arquivo.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import preparar_contestacao as pc  # noqa: E402
import legal_readiness as lr  # noqa: E402
from test_instalar_modelo_oficial import (  # noqa: E402
    _CORPO_VALIDO,
    _partes_minimas,
    _zip_com_partes,
)

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"


def _limpar_env_modelo(monkeypatch):
    for var in (lr.ENV_MODELO_PATH, lr.ENV_MODELO_SHA256,
                lr.ENV_GCS_BUCKET, lr.ENV_GCS_OBJECT, lr.ENV_GCS_GENERATION):
        monkeypatch.delenv(var, raising=False)


def _configurar_modelo_real(monkeypatch):
    """Aponta o modo local (Gate 6.4-A) para o Modelo Oficial real, se
    presente — necessário para qualquer teste que exija
    contestacao_status=READY de verdade (contexto institucional real)."""
    if not TEMPLATE_REAL.is_file():
        return False
    sha = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(TEMPLATE_REAL))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    return True


# ------------------------------------------------------------------ fixtures

FIXTURE_A_CONSUMIDOR = {
    "fatos": [
        {"fact": "A concessionária lavrou Termo de Ocorrência de Irregularidade "
                 "na unidade consumidora em 10/03/2026.",
         "source_document": "TOI-sintetico-001.pdf", "tipo": "FATO_DOCUMENTADO"},
        {"fact": "A parte autora alega que jamais houve violação do medidor.",
         "source_document": "peticao-inicial-sintetica.pdf", "tipo": "ALEGACAO_AUTORAL"},
    ],
    "questoes_juridicas": ["inversao do onus da prova consumidor", "boa-fe contratual"],
    "estado_processual": {"GRATUIDADE_CONCEDIDA": False},
}

FIXTURE_B_OBRIGACAO_FAZER = {
    "fatos": [
        {"fact": "A autora requer o restabelecimento imediato do fornecimento.",
         "source_document": "peticao-inicial-sintetica.pdf", "tipo": "ALEGACAO_AUTORAL"},
        {"fact": "Consta aviso prévio de suspensão por inadimplência, sem "
                 "confirmação de corte efetivo nos autos.",
         "source_document": "aviso-sintetico.pdf", "tipo": "FATO_DOCUMENTADO"},
    ],
    "questoes_juridicas": ["suspensao do fornecimento de energia"],
    "estado_processual": {"CORTE_EFETIVO": "INDETERMINADO"},
}

FIXTURE_C_CAMPO_AUSENTE = {
    "fatos": [{"fact": "Fato sem documento de origem."}],
}

FIXTURE_D_SUPERDIMENSIONADA = {
    "fatos": [
        {"fact": f"Fato sintético número {i}.", "source_document": f"doc-{i}.pdf"}
        for i in range(pc.MAX_FATOS + 10)
    ],
}

FIXTURE_E_AMBIGUA = {
    "fatos": [{"fact": "x", "source_document": "y", "tipo": "TIPO_INEXISTENTE"}],
}


# --------------------------------------------------------- 1/15: caminho feliz

@pytest.mark.docx_real
def test_1_entrada_valida_produz_pacote_deterministico(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r1 = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    r2 = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r1.status == "OK", r1.motivo
    assert json.dumps(r1.pacote, sort_keys=True) == json.dumps(r2.pacote, sort_keys=True)
    assert r1.pacote["readiness"]["contestacao_status"] == "READY"
    assert len(r1.pacote["fatos_normalizados"]) == 2
    assert r1.pacote["fatos_normalizados"][0]["tipo"] == "FATO_DOCUMENTADO"


@pytest.mark.docx_real
def test_1b_fixture_obrigacao_de_fazer(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r = pc.preparar_contexto_contestacao(FIXTURE_B_OBRIGACAO_FAZER)
    assert r.status == "OK", r.motivo
    bloco_corte = next(b for b in r.pacote["blocos_modelo"] if b["id"] == "LICITUDE_CORTE_SUSPENSAO")
    assert "indeterminado" in bloco_corte["gate_status"]


# ------------------------------------------------------- 2/16/17: entrada inválida

def test_2_campo_obrigatorio_ausente_e_erro_estruturado():
    r = pc.preparar_contexto_contestacao(FIXTURE_C_CAMPO_AUSENTE)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"
    assert r.motivo is not None


def test_16_entrada_superdimensionada_e_rejeitada():
    r = pc.preparar_contexto_contestacao(FIXTURE_D_SUPERDIMENSIONADA)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"
    assert str(pc.MAX_FATOS) in r.motivo


def test_17_entrada_ambigua_tipo_invalido_e_rejeitada():
    r = pc.preparar_contexto_contestacao(FIXTURE_E_AMBIGUA)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


def test_entrada_nao_e_dict():
    r = pc.preparar_contexto_contestacao("nao sou um objeto")
    assert r.status == "PIPELINE_ABORTED"


def test_fatos_ausente():
    r = pc.preparar_contexto_contestacao({})
    assert r.status == "PIPELINE_ABORTED"


def test_fatos_vazio():
    r = pc.preparar_contexto_contestacao({"fatos": []})
    assert r.status == "PIPELINE_ABORTED"


def test_questoes_juridicas_excede_limite(monkeypatch):
    entrada = dict(FIXTURE_A_CONSUMIDOR)
    entrada["questoes_juridicas"] = [f"questao {i}" for i in range(pc.MAX_QUESTOES_JURIDICAS + 1)]
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


def test_estado_processual_valor_invalido():
    entrada = {"fatos": FIXTURE_A_CONSUMIDOR["fatos"], "estado_processual": {"X": "talvez"}}
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


# --------------------------------------------------------- 3/4/5: fail-closed

def test_3_4_5_contestacao_not_ready_falha_fechado(monkeypatch):
    _limpar_env_modelo(monkeypatch)  # nem GCS nem local -> modelo_oficial NOT_CONFIGURED
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"
    assert "rag=" in r.motivo and "modelo_oficial=" in r.motivo


def test_rag_not_ready_falha_fechado(monkeypatch, tmp_path):
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                         lambda: lr.ResultadoReadiness("NOT_READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                         lambda *a, **k: lr.ResultadoReadiness("READY", "sintético"))
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"


def test_modelo_not_ready_falha_fechado(monkeypatch):
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                         lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                         lambda *a, **k: lr.ResultadoReadiness("NOT_READY", "sintético"))
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"


# -------------------------------------------------------------- 12/13/14: RAG

def test_12_nenhuma_jurisprudencia_e_tocada():
    """§11: só os 6 diplomas legislativos são pesquisados — nunca
    jurisprudência (que sequer está no container/imagem, Gate 6.4-A/B)."""
    fontes = pc._montar_fontes_legais(["responsabilidade civil"])
    for f in fontes:
        assert "jurisprudencia" not in f["source_id"].lower()
        assert f["diploma"] is None or "jurisprud" not in f["diploma"].lower()


def test_13_fontes_contêm_proveniencia():
    fontes = pc._montar_fontes_legais(["inversao do onus da prova consumidor"])
    assert fontes, "esperava ao menos uma fonte para uma questão do CDC"
    for f in fontes:
        assert f["source_id"]
        assert f["diploma"]
        assert f["authority_level"] == "OFICIAL"
        assert f["texto"]


def test_14_retrieval_bounded_por_questao_e_no_total():
    muitas_questoes = ["consumidor", "contrato", "prova", "dano moral", "boa-fe"]
    fontes = pc._montar_fontes_legais(muitas_questoes)
    assert len(fontes) <= pc.MAX_FONTES_TOTAL
    for questao in muitas_questoes:
        assert len(pc._buscar_fontes_para_questao(questao, pc.RAG_DIR_PADRAO)) <= pc.MAX_FONTES_POR_QUESTAO


def test_sem_questoes_juridicas_nao_busca_nada():
    assert pc._montar_fontes_legais([]) == []


# ------------------------------------------------------ 10/11: privacidade

def test_10_nenhum_conteudo_de_entrada_aparece_em_log(monkeypatch, caplog):
    """§19: fatos/questões nunca aparecem em log algum. Este módulo não
    chama nenhum logger — a prova é estrutural (nenhuma chamada de
    logging/print no código-fonte), reforçada aqui checando que a
    execução real não emite nenhum registro de log contendo o conteúdo
    sintético desta entrada."""
    _limpar_env_modelo(monkeypatch)
    marcador = "MARCADOR-DE-FATO-SECRETO-DO-CASO-XYZ"
    entrada = {"fatos": [{"fact": marcador, "source_document": "doc.pdf"}]}
    with caplog.at_level("DEBUG"):
        pc.preparar_contexto_contestacao(entrada)
    assert marcador not in caplog.text


def test_10b_codigo_fonte_nao_usa_logging_nem_print():
    codigo = Path(pc.__file__).read_text(encoding="utf-8")
    assert "import logging" not in codigo
    assert re.search(r"(?<!#)\bprint\(", codigo) is None


@pytest.mark.docx_real
def test_11_modelo_oficial_nunca_aparece_no_pacote(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "OK"
    serializado = json.dumps(r.pacote, ensure_ascii=False)
    assert str(TEMPLATE_REAL) not in serializado
    assert "PK\x03\x04" not in serializado  # assinatura binária de ZIP/DOCX
    # o pacote nunca inclui o caminho local configurado, nem qualquer
    # referência a bucket/objeto GCS além do SHA (não-secreto, já público
    # nesta configuração, mesma disciplina de docs/mcp-producao-contrato.md)
    assert "EDE_MODELO_OFICIAL_PATH" not in serializado


# ------------------------------------------------------------- blocos/gate

def test_gate_status_estado_nao_informado_nunca_vira_falso_silencioso():
    catalogo = {"blocks": [{"id": "X", "tag": "T", "tipo": "CONDICIONAL_PADRAO",
                             "decision_mode": "state_linked", "linked_fact": "ALGO",
                             "cardinality": "ONE"}], "zones": []}
    blocos = pc._montar_blocos_modelo(catalogo, {})
    assert blocos[0]["gate_status"] == "estado_nao_informado (ALGO)"


def test_gate_status_indeterminado_e_explicito():
    catalogo = {"blocks": [{"id": "X", "tag": "T", "tipo": "CONDICIONAL_PADRAO",
                             "decision_mode": "humano",
                             "requires_fact": {"key": "CORTE_EFETIVO"},
                             "cardinality": "ONE"}], "zones": []}
    blocos = pc._montar_blocos_modelo(catalogo, {"CORTE_EFETIVO": "INDETERMINADO"})
    assert "indeterminado" in blocos[0]["gate_status"]


def test_montar_blocos_nunca_decide_inclusao():
    """§15: o pacote descreve, nunca decide — nenhuma chave 'INCLUIR'/
    'EXCLUIR' aparece na descrição do catálogo."""
    catalogo = json.loads((BASE / "templates" / "contestacao" / "blocos.json").read_text(encoding="utf-8"))
    blocos = pc._montar_blocos_modelo(catalogo, {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True})
    for b in blocos:
        assert "INCLUIR" not in json.dumps(b) and "EXCLUIR" not in json.dumps(b)
