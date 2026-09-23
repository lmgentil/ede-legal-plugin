#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_finalizar_peca.py — regressão do finalizador MCP genérico
(Gate 6.6-C, ADR-0018).

Dois níveis, mesmo padrão de tests/test_docx_block_engine.py e
tests/test_docx_fidelidade_e_round_trip.py:

  1. Testes de unidade SEMPRE executam — vocabulário fechado de erro,
     classificação de estágio, validação de forma da entrada, recusa de
     capacidade desconhecida/não pronta — nenhum depende do Modelo
     Oficial real.
  2. `docx_real` — ponta a ponta contra o Modelo Oficial real
     (`templates/contestacao/modelo-oficial.docx`, asset externo,
     ADR-0009): SKIP explícito se o arquivo não estiver instalado
     localmente. Fixture de dados idêntica à já validada em
     `test_docx_block_engine.py::test_pipeline_completo_com_blocos_
     contra_template_real` (cenário "tudo incluído"), reaproveitada
     deliberadamente — não uma segunda fixture divergente.
"""
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import artifact_storage as ast  # noqa: E402
import capability_registry as cr  # noqa: E402
import finalizar_peca as fp  # noqa: E402

sys.path.insert(0, str(BASE / "mcp_server"))
import auth_logging as telemetria  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


# ============================================ espelho auth_logging <-> Core

def test_vocabulario_de_telemetria_espelha_exatamente_o_do_core():
    """`mcp_server/auth_logging.py` DELIBERADAMENTE duplica (nunca
    importa) o vocabulário fechado de `finalizar_peca.py` — esta prova
    trava a duplicata contra deriva silenciosa (ver comentário de
    `CAPACIDADES_FINALIZACAO`/`ESTAGIOS_FINALIZACAO`/`CODIGOS_ERRO_
    FINALIZACAO` em auth_logging.py)."""
    assert telemetria.ESTAGIOS_FINALIZACAO == fp.ETAPAS
    assert telemetria.CODIGOS_ERRO_FINALIZACAO == fp.CODIGOS_ERRO
    assert telemetria.CAPACIDADES_FINALIZACAO == set(cr.REGISTRO)


# ============================================================= vocabulário

def test_todo_codigo_de_erro_referenciado_no_mapa_esta_no_vocabulario_fechado():
    for codigo in fp._ETAPA_POR_CODIGO:
        assert codigo in fp.CODIGOS_ERRO, codigo
    for codigo, stage in fp._ETAPA_POR_CODIGO.items():
        assert stage in fp.ETAPAS, (codigo, stage)


def test_recusado_rejeita_estagio_ou_codigo_fora_do_vocabulario():
    with pytest.raises(AssertionError):
        fp._recusado("estagio_inventado", "INPUT_VALIDATION_FAILED", "x")
    with pytest.raises(AssertionError):
        fp._recusado("input_validation", "CODIGO_INVENTADO", "x")


# ================================================== classificação de estágio

@pytest.mark.parametrize("etapa,codigo_esperado", [
    ("decisao_ausente", "MISSING_BLOCK_DECISION"),
    ("decisao_indeterminada", "MISSING_BLOCK_DECISION"),
    ("decisao_invalida", "INPUT_VALIDATION_FAILED"),
    ("estado_invalido", "INPUT_VALIDATION_FAILED"),
    ("gate_fatico_nao_satisfeito", "INPUT_VALIDATION_FAILED"),
    ("zona_indeterminada", "INPUT_VALIDATION_FAILED"),
    ("modelo_institucional_desatualizado", "OFFICIAL_MODEL_NOT_READY"),
    ("catalogo_invalido", "OFFICIAL_MODEL_NOT_READY"),
    ("sdt_sem_tag", "OFFICIAL_MODEL_NOT_READY"),
    ("tag_ausente", "OFFICIAL_MODEL_NOT_READY"),
    ("cardinalidade_invalida", "OFFICIAL_MODEL_NOT_READY"),
    ("zona_nao_catalogada", "OFFICIAL_MODEL_NOT_READY"),
    ("template_lock", "TEMPLATE_LOCK_FAILED"),
    ("numeracao_final", "RENDER_FAILED"),
    ("validacao_placeholders", "RENDER_FAILED"),
    ("erro_interno", "RENDER_FAILED"),
])
def test_classificar_etapa_engine(etapa, codigo_esperado):
    codigo, motivo = fp._classificar_etapa_engine(etapa)
    assert codigo == codigo_esperado
    assert motivo and "\n" not in motivo


def test_classificacao_nunca_vaza_o_texto_bruto_do_stage_interno():
    # a mensagem pública é fixa por categoria — nunca ecoa o `stage`
    # interno cru (que poderia por acidente carregar detalhe de
    # implementação) como se fosse a explicação ao cliente.
    _, motivo = fp._classificar_etapa_engine("tag_desconhecida")
    assert "tag_desconhecida" not in motivo


# ==================================================== validação de forma

def test_entrada_nao_dict_e_recusada():
    r = fp.finalizar_peca([])
    assert r.status == "REFUSED" and r.error_code == "INPUT_VALIDATION_FAILED"


def test_capability_id_ausente():
    r = fp.finalizar_peca({})
    assert r.status == "REFUSED" and r.error_code == "CAPABILITY_NOT_FOUND"
    assert r.stage == "capability_resolution"


def test_capability_id_desconhecida():
    r = fp.finalizar_peca({"capability_id": "recurso.inominado", "placeholders": {}})
    assert r.error_code == "CAPABILITY_NOT_FOUND"


def test_placeholders_com_tipo_errado_e_recusado():
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo",
                            "placeholders": {"X": 123}})
    assert r.error_code == "INPUT_VALIDATION_FAILED"


def test_placeholders_ausente_e_recusado():
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo"})
    assert r.error_code == "INPUT_VALIDATION_FAILED"


def test_block_decisions_com_estado_invalido_e_recusado():
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo",
                            "placeholders": {}, "block_decisions": {"X": "TALVEZ"}})
    assert r.error_code == "INPUT_VALIDATION_FAILED"


def test_estado_processual_com_valor_nao_booleano_e_recusado():
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo",
                            "placeholders": {}, "estado_processual": {"X": "SIM"}})
    assert r.error_code == "INPUT_VALIDATION_FAILED"


def test_estado_processual_aceita_indeterminado_como_valor_de_forma_valida():
    # forma válida (não é erro de FORMATO) — o abort de fato, se houver,
    # vem depois, do motor de composição, não da validação de forma.
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo",
                            "placeholders": {}, "estado_processual": {"CORTE_EFETIVO": "INDETERMINADO"}})
    assert r.status == "REFUSED"
    # não deve ser rejeitado já na validação de FORMA (o abort real, se
    # houver, vem do motor de composição — MISSING_BLOCK_DECISION aqui,
    # já que `placeholders`/`block_decisions` estão vazios):
    assert r.motivo != "'estado_processual' deve ser {FATO: true|false|'INDETERMINADO'}"


def test_nenhuma_excecao_vaza_para_o_chamador_em_entrada_hostil():
    entradas_hostis = [
        None, 1, "string", [],
        {"capability_id": None},
        {"capability_id": ""},
        {"capability_id": "contestacao.irregularidade_consumo", "placeholders": None},
        {"capability_id": "contestacao.irregularidade_consumo", "placeholders": {}, "block_decisions": []},
        {"capability_id": "contestacao.irregularidade_consumo", "placeholders": {}, "estado_processual": []},
    ]
    for entrada in entradas_hostis:
        r = fp.finalizar_peca(entrada)  # nunca deve levantar
        assert r.status == "REFUSED"


# ======================================================= registro de capacidades

def test_capacidade_pronta_resolve_via_registro():
    cap = cr.obter_capacidade("contestacao.irregularidade_consumo")
    assert cap is not None and cap.status == "READY"


def test_capacidade_nao_ready_e_recusada(monkeypatch):
    import dataclasses
    cap_fake = dataclasses.replace(cr.REGISTRO["contestacao.irregularidade_consumo"], status="NOT_READY")
    monkeypatch.setitem(cr.REGISTRO, "contestacao.irregularidade_consumo", cap_fake)
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo", "placeholders": {}})
    assert r.error_code == "CAPABILITY_NOT_READY"
    assert r.stage == "capability_resolution"


def test_capacidade_ready_sem_adaptador_e_recusada_como_not_ready(monkeypatch):
    monkeypatch.setitem(fp._ADAPTADORES, "contestacao.irregularidade_consumo", None)
    r = fp.finalizar_peca({"capability_id": "contestacao.irregularidade_consumo", "placeholders": {}})
    assert r.error_code == "CAPABILITY_NOT_READY"


# ============================================================= limite de tamanho

def test_max_docx_bytes_e_exatamente_8_mebibytes():
    assert fp.MAX_DOCX_BYTES == 8 * 1024 * 1024
    assert fp.MAX_DOCX_BYTES == 8388608


# ================================================================== docx_real

@pytest.fixture
def modelo_oficial_local(monkeypatch):
    """Configura `EDE_MODELO_OFICIAL_PATH`/`_SHA256` para o Modelo
    Oficial real deste checkout, só para a duração do teste
    (`monkeypatch` desfaz automaticamente ao final) — nunca depende do
    desenvolvedor ter exportado essas variáveis no shell, e nunca vaza
    para outros testes do mesmo processo pytest (achado real: sem este
    isolamento, `test_mcp_oauth.py::test_token_valido_alcanca_o_
    dispatch_da_health`, que assume ambiente limpo, quebrava). SKIP
    explícito se o asset externo (ADR-0009) não estiver instalado
    localmente — mesma condição, agora também cobrindo a CONFIGURAÇÃO,
    não só a presença do arquivo."""
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — asset institucional externo (ADR-0009).")
    import hashlib
    sha = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    monkeypatch.setenv("EDE_MODELO_OFICIAL_PATH", str(TEMPLATE_REAL))
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", sha)


class _TransporteArtefatoFake:
    """Gate 6.6-E — mesmo papel de `test_artifact_storage._FakeTransporte`,
    redefinido aqui (não importado de lá) para não acoplar os dois
    arquivos de teste: um DOCX_real ponta a ponta não deve depender de
    detalhe interno da suíte de unidade de outro módulo."""

    def __init__(self):
        self.objetos = {}

    def enviar(self, object_name, dados, content_type, metadata):
        self.objetos[object_name] = (dados, content_type, dict(metadata))

    def excluir(self, object_name):
        self.objetos.pop(object_name, None)
        return True

    def listar(self, prefixo, limite):
        self.chamadas_listar = getattr(self, "chamadas_listar", 0) + 1
        nomes = sorted(n for n in self.objetos if n.startswith(prefixo))[:limite]
        return [(n, self.objetos[n][2]) for n in nomes]


@pytest.fixture
def transporte_artefato_fake(monkeypatch):
    """Injeta um transporte em memória no ponto único de injeção do
    Core (`fp._obter_transporte_artefato`) — os testes `docx_real`
    exercitam o RENDER real do Modelo Oficial (Template Lock, fidelidade,
    round-trip), mas nunca precisam de GCS/IAM real para isso: a entrega
    do artefato é testada isoladamente, com rede real, em
    `tests/test_artifact_storage.py` (fake) e no relatório de
    homologação do Gate 6.6-E (real, fora da suíte automatizada)."""
    fake = _TransporteArtefatoFake()
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: fake)
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: BASE_URL_TESTE)
    return fake


BASE_URL_TESTE = "https://ede.example.test"


def _dados_tudo_incluido():
    return {
        "JUIZO": "AO JUÍZO DA VARA CÍVEL DA COMARCA DE SALVADOR/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "ligação direta (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
        "SINOPSE_FATOS_NUCLEO_OBJETO": "Objeto fictício de teste (dado fictício de teste).",
    }


def _block_decisions_tudo_incluido():
    catalogo = json.loads(CATALOGO_REAL.read_text(encoding="utf-8"))
    return {b["id"]: "INCLUIR" for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}


@pytest.mark.docx_real
def test_pipeline_completo_ok_contra_modelo_oficial_real(modelo_oficial_local, transporte_artefato_fake):
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    assert r.capability_id == "contestacao.irregularidade_consumo"
    assert r.documento_bytes and len(r.documento_bytes) == r.documento_tamanho
    assert r.documento_tamanho <= fp.MAX_DOCX_BYTES
    assert r.documento_sha256 and len(r.documento_sha256) == 64
    import hashlib
    assert hashlib.sha256(r.documento_bytes).hexdigest() == r.documento_sha256
    assert r.filename == "EDE-Contestacao-Irregularidade.docx"
    # bytes de um pacote ZIP/OOXML válido
    assert r.documento_bytes[:2] == b"PK"

    # Entrega v2 (Gate 6.6-E; URL opaca desde o Gate 6.6-F/G): link do
    # PRÓPRIO EDE, artefato realmente "enviado" ao transporte (fake),
    # bytes armazenados idênticos aos bytes renderizados/aprovados, e o
    # objeto identificado por sha256(token) — nunca o token em claro.
    prefixo = f"{BASE_URL_TESTE}/download/"
    assert r.download_url and r.download_url.startswith(prefixo)
    token = r.download_url[len(prefixo):]
    assert ast.token_bem_formado(token)
    assert "?" not in r.download_url and "storage.googleapis.com" not in r.download_url
    assert r.download_expires_at and r.download_expires_at.endswith("Z")
    assert r.artefato_id == ast.id_artefato_do_token(token)
    assert token not in repr(r)
    object_name = f"artifacts/{r.artefato_id}.docx"
    assert object_name in transporte_artefato_fake.objetos
    dados_armazenados, content_type, metadata = transporte_artefato_fake.objetos[object_name]
    assert dados_armazenados == r.documento_bytes
    assert content_type == ast.CONTENT_TYPE_DOCX
    assert metadata["sha256"] == r.documento_sha256
    # nenhum dado de caso no metadado do objeto (Gate 6.6-E §20) — o
    # nome de arquivo é o institucional neutro, e o token não aparece
    assert set(metadata) == {"artifact_id", "created_at", "expires_at", "sha256", "filename"}
    assert metadata["filename"] == r.filename
    assert token not in json.dumps(metadata)

    # Gate 6.6-E, continuação §8 — limpeza oportunista roda depois de
    # todo sucesso (best-effort; aqui só provamos que foi chamada).
    assert transporte_artefato_fake.chamadas_listar == 1


@pytest.mark.docx_real
def test_pipeline_rejeita_sentinela_de_aceite_em_modo_producao_final(modelo_oficial_local):
    dados = _dados_tudo_incluido()
    dados["SINOPSE_FATOS"] = "[PENDENTE: aguardando documento]"
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": dados,
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "SYNTHETIC_SENTINEL_REJECTED"
    assert r.stage == "production_final_validation"
    assert r.documento_bytes is None


@pytest.mark.docx_real
def test_pipeline_rejeita_placeholder_sempre_visivel_ausente(modelo_oficial_local):
    dados = _dados_tudo_incluido()
    del dados["AUTOR"]
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": dados,
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "MISSING_REQUIRED_FIELD"
    assert r.stage == "production_final_validation"


@pytest.mark.docx_real
def test_pipeline_rejeita_decisao_de_bloco_ausente(modelo_oficial_local):
    decisoes = _block_decisions_tudo_incluido()
    del decisoes["RECONVENCAO"]
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": decisoes,
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "MISSING_BLOCK_DECISION"
    assert r.stage == "input_validation"


@pytest.mark.docx_real
def test_pipeline_rejeita_travessao_via_validacao_estrutural(modelo_oficial_local):
    dados = _dados_tudo_incluido()
    dados["REALIDADE_FATICA"] = "Fato ocorrido — conforme documentos."
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": dados,
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "INPUT_VALIDATION_FAILED"
    assert r.stage == "input_validation"


@pytest.mark.docx_real
def test_pipeline_rejeita_documento_acima_do_limite_de_tamanho(modelo_oficial_local, monkeypatch,
                                                                 transporte_artefato_fake):
    monkeypatch.setattr(fp, "MAX_DOCX_BYTES", 1)  # qualquer DOCX real excede 1 byte
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "ARTIFACT_TOO_LARGE"
    assert r.stage == "artifact_delivery"
    assert r.documento_bytes is None
    assert str(fp.MAX_DOCX_BYTES) in r.motivo
    # Gate 6.6-E §16 — nunca envia um artefato para só depois recusar por
    # tamanho: a checagem acontece antes de qualquer chamada ao transporte.
    assert transporte_artefato_fake.objetos == {}


@pytest.mark.docx_real
def test_pipeline_rejeita_por_falha_de_armazenamento_do_artefato(modelo_oficial_local, monkeypatch):
    class _TransporteFalhaEnvio:
        def enviar(self, object_name, dados, content_type, metadata):
            raise ast.ErroArmazenamentoArtefato("gcs_status_inesperado")

        def excluir(self, *a, **k):
            raise AssertionError("nunca deveria haver o que limpar — upload nem chegou a existir")

    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: _TransporteFalhaEnvio())
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: BASE_URL_TESTE)
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "ARTIFACT_STORAGE_FAILED"
    assert r.stage == "artifact_delivery"
    assert r.download_url is None
    assert r.documento_bytes is None


@pytest.mark.docx_real
def test_pipeline_sem_base_url_de_download_recusa_sem_subir_objeto(modelo_oficial_local, monkeypatch):
    """Gate 6.6-F/G — substitui o teste de falha de assinatura (modo de
    falha que deixou de existir junto com a URL V4). Sem
    `EDE_ARTEFATOS_DOWNLOAD_BASE_URL` o link não poderia ser composto:
    recusa fail-closed ANTES do upload — nenhum objeto órfão."""
    fake = _TransporteArtefatoFake()
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: fake)
    monkeypatch.delenv(ast.ENV_ARTEFATOS_DOWNLOAD_BASE_URL, raising=False)
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "REFUSED"
    assert r.error_code == "ARTIFACT_STORAGE_FAILED"
    assert r.stage == "artifact_delivery"
    assert r.download_url is None
    assert r.documento_bytes is None
    assert fake.objetos == {}


@pytest.mark.docx_real
def test_pipeline_nunca_gera_arquivo_temporario_residual(modelo_oficial_local, transporte_artefato_fake):
    import glob
    import tempfile
    antes = set(glob.glob(str(Path(tempfile.gettempdir()) / "**"), recursive=False))
    entrada = {
        "capability_id": "contestacao.irregularidade_consumo",
        "placeholders": _dados_tudo_incluido(),
        "block_decisions": _block_decisions_tudo_incluido(),
        "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
    }
    r = fp.finalizar_peca(entrada)
    assert r.status == "OK"
    depois = set(glob.glob(str(Path(tempfile.gettempdir()) / "**"), recursive=False))
    assert depois - antes == set(), "TemporaryDirectory deve ser limpo mesmo em sucesso"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
