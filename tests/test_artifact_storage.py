#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_artifact_storage.py — regressão do armazenamento efêmero + entrega
assinada (Gate 6.6-E, ADR-0019).

Todos os testes de unidade usam `_FakeTransporte`, em memória — nenhum
toca rede (Gate 6.6-E §43). A verificação de comportamento REAL contra
GCS/IAM Credentials (byte-identidade fim a fim, negação de acesso não
assinado, expiração, enumeração) é um item de homologação separado,
registrado como risco residual no relatório do gate (bloqueado nesta
sessão por um guard de concessão de IAM do próprio harness — nunca
contornado)."""
import datetime as dt
import hashlib
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import artifact_storage as ast  # noqa: E402


# ------------------------------------------------------------- fake transporte

class _FakeTransporte:
    """Backend em memória — grava o que `enviar`/`assinar_url`/`excluir`
    receberam para as asserções, e permite forçar cada falha do Gate
    6.6-E §44 (matriz negativa)."""

    def __init__(self, falhar_envio=False, falhar_assinatura=False, falhar_exclusao=False):
        self.objetos: dict[str, tuple[bytes, str, dict]] = {}
        self.chamadas_enviar = []
        self.chamadas_assinar = []
        self.chamadas_excluir = []
        self._falhar_envio = falhar_envio
        self._falhar_assinatura = falhar_assinatura
        self._falhar_exclusao = falhar_exclusao

    def enviar(self, object_name, dados, content_type, metadata):
        self.chamadas_enviar.append((object_name, len(dados), content_type, dict(metadata)))
        if self._falhar_envio:
            raise ast.ErroArmazenamentoArtefato("gcs_status_inesperado")
        self.objetos[object_name] = (dados, content_type, dict(metadata))

    def assinar_url(self, object_name, ttl_segundos, content_disposition):
        self.chamadas_assinar.append((object_name, ttl_segundos, content_disposition))
        if self._falhar_assinatura:
            raise ast.ErroAssinaturaArtefato("iam_signblob_status_inesperado", artefato_id="", limpeza_ok=None)
        return f"https://storage.googleapis.com/bucket-fake/{object_name}?assinado=1"

    def excluir(self, object_name):
        self.chamadas_excluir.append(object_name)
        if self._falhar_exclusao:
            return False
        self.objetos.pop(object_name, None)
        return True

    def listar(self, prefixo, limite):
        nomes = sorted(n for n in self.objetos if n.startswith(prefixo))[:limite]
        return [(n, self.objetos[n][2]) for n in nomes]


DOCX_FAKE = b"PK\x03\x04-- bytes de teste, nunca um DOCX real --" * 50
SHA_FAKE = hashlib.sha256(DOCX_FAKE).hexdigest()
FILENAME = "EDE-Contestacao-Irregularidade.docx"


# ============================================================= caminho feliz

def test_entrega_bem_sucedida_devolve_url_expiracao_e_id_opaco():
    transporte = _FakeTransporte()
    entrega = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)

    assert entrega.download_url.startswith("https://")
    assert entrega.artefato_id and "/" not in entrega.artefato_id
    assert entrega.expires_at.endswith("Z")

    (nome_objeto, tamanho, content_type, metadata), = transporte.chamadas_enviar
    assert content_type == ast.CONTENT_TYPE_DOCX
    assert tamanho == len(DOCX_FAKE)
    assert nome_objeto == f"artifacts/{entrega.artefato_id}.docx"


def test_bytes_enviados_sao_exatamente_os_recebidos_sha_confere():
    """Gate 6.6-E §14/§15 — nunca reabre/reconstrói; o SHA-256 do byte
    armazenado bate com o SHA-256 que o chamador já tinha calculado."""
    transporte = _FakeTransporte()
    entrega = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    dados_armazenados, _, metadata = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    assert dados_armazenados == DOCX_FAKE
    assert hashlib.sha256(dados_armazenados).hexdigest() == SHA_FAKE
    assert metadata["sha256"] == SHA_FAKE


def test_object_key_e_opaco_sem_dado_de_caso():
    """Gate 6.6-E §11/§26 — nenhum vestígio do SHA do documento, do nome
    de arquivo do cliente, nem de qualquer outro dado de chamada aparece
    no NOME DO OBJETO (só no metadado do objeto, nunca no key)."""
    transporte = _FakeTransporte()
    entrega1 = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    entrega2 = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    assert entrega1.artefato_id != entrega2.artefato_id  # mesmo SHA, objetos diferentes (§26)
    for artefato_id in (entrega1.artefato_id, entrega2.artefato_id):
        assert SHA_FAKE not in artefato_id
        assert "EDE-Contestacao" not in artefato_id
        assert len(artefato_id) == 32  # uuid4().hex


def test_object_metadata_contem_so_campos_seguros():
    transporte = _FakeTransporte()
    entrega = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    _, _, metadata = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    assert set(metadata) == {"artifact_id", "created_at", "expires_at", "sha256"}


def test_content_disposition_usa_o_nome_de_arquivo_neutro_do_cliente():
    transporte = _FakeTransporte()
    ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    (_, _, disposicao), = transporte.chamadas_assinar
    assert disposicao == f'attachment; filename="{FILENAME}"'


# ==================================================================== TTL

def test_ttl_de_producao_e_sempre_a_constante_do_modulo():
    """Gate 6.6-E §8/§29/§48 — `entregar_artefato_efemero` não aceita
    nenhum parâmetro de TTL: o único jeito de mudar o TTL usado é chamar
    `TTL_DOWNLOAD_SEGUNDOS` diferente, e isso é uma constante do módulo,
    nunca lida de entrada externa nem de variável de ambiente."""
    import inspect

    assinatura = inspect.signature(ast.entregar_artefato_efemero)
    assert "ttl" not in "".join(assinatura.parameters).lower()
    assert ast.TTL_DOWNLOAD_SEGUNDOS == 24 * 60 * 60

    transporte = _FakeTransporte()
    ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    (_, ttl_usado, _), = transporte.chamadas_assinar
    assert ttl_usado == 86400


# =========================================================== matriz negativa

def test_falha_de_upload_nao_gera_url_nem_tenta_assinar():
    transporte = _FakeTransporte(falhar_envio=True)
    with pytest.raises(ast.ErroArmazenamentoArtefato) as exc:
        ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    assert exc.value.motivo == "gcs_status_inesperado"
    assert transporte.chamadas_assinar == []
    assert transporte.objetos == {}


def test_falha_de_assinatura_apos_upload_tenta_limpar_e_propaga_erro_com_id():
    transporte = _FakeTransporte(falhar_assinatura=True)
    with pytest.raises(ast.ErroAssinaturaArtefato) as exc:
        ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    assert exc.value.artefato_id  # opaco, não vazio
    assert exc.value.limpeza_ok is True
    assert len(transporte.chamadas_excluir) == 1
    assert transporte.chamadas_excluir[0] == f"artifacts/{exc.value.artefato_id}.docx"
    assert transporte.objetos == {}  # objeto órfão foi de fato removido do fake


def test_falha_de_assinatura_e_falha_de_limpeza_reporta_limpeza_ok_falso():
    """Gate 6.6-E §22 — cleanup também falhando nunca é silencioso nem
    vira sucesso disfarçado; o chamador sabe exatamente o que aconteceu."""
    transporte = _FakeTransporte(falhar_assinatura=True, falhar_exclusao=True)
    with pytest.raises(ast.ErroAssinaturaArtefato) as exc:
        ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    assert exc.value.limpeza_ok is False
    # o objeto órfão continua no backend real (fake não removeu) --
    # nunca uma URL foi devolvida para ele.
    assert len(transporte.objetos) == 1


def test_configuracao_ausente_e_erro_tipado_distinto_de_falha_operacional():
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.TransporteGcsReal(bucket="", signer_sa="")
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.TransporteGcsReal(bucket="algum-bucket", signer_sa="")
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.TransporteGcsReal(bucket="", signer_sa="alguma-sa@x.iam.gserviceaccount.com")


def test_obter_transporte_do_ambiente_le_as_duas_variaveis_esperadas():
    env = {
        ast.ENV_ARTEFATOS_GCS_BUCKET: "ede-legal-mcp-01-artefatos-efemeros",
        ast.ENV_ARTEFATOS_SIGNER_SA: "ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com",
    }
    transporte = ast.obter_transporte_do_ambiente(env)
    assert isinstance(transporte, ast.TransporteGcsReal)
    assert transporte._bucket == env[ast.ENV_ARTEFATOS_GCS_BUCKET]
    assert transporte._signer_sa == env[ast.ENV_ARTEFATOS_SIGNER_SA]


def test_obter_transporte_do_ambiente_sem_configuracao_falha_fechado():
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.obter_transporte_do_ambiente({})


# ===================================================== algoritmo de assinatura V4

def test_construir_url_assinada_v4_estrutura_e_determinismo_do_string_to_sign():
    """Não depende de rede: verifica que o MESMO conjunto de entradas
    (inclusive timestamp fixo, injetado via monkeypatch do relógio não
    necessário aqui porque cravamos os parâmetros manualmente abaixo)
    produz um `string_to_sign` byte-idêntico — e que a função de
    assinatura injetada recebe exatamente esses bytes, nunca os bytes do
    documento nem qualquer outro dado."""
    capturados = {}

    def _assinar_fake(string_to_sign: bytes) -> bytes:
        capturados["string_to_sign"] = string_to_sign
        return b"\x01\x02\x03"  # assinatura fake determinística

    url = ast._construir_url_assinada_v4(
        bucket="meu-bucket", object_name="artifacts/abc123.docx",
        signer_sa="sa@proj.iam.gserviceaccount.com", ttl_segundos=900,
        content_disposition='attachment; filename="x.docx"',
        assinar_bytes=_assinar_fake,
    )

    assert url.startswith("https://storage.googleapis.com/meu-bucket/artifacts/abc123.docx?")
    assert "X-Goog-Algorithm=GOOG4-RSA-SHA256" in url
    assert "X-Goog-Expires=900" in url
    assert "response-content-disposition=" in url
    assert url.endswith("&X-Goog-Signature=010203")

    sts = capturados["string_to_sign"].decode("utf-8")
    linhas = sts.split("\n")
    assert linhas[0] == "GOOG4-RSA-SHA256"
    assert linhas[2].endswith("/auto/storage/goog4_request")  # região literal "auto" (Gate 6.6-E)
    assert len(linhas[3]) == 64  # hash SHA-256 em hex


def test_canonical_uri_preserva_barras_internas_do_object_name():
    """`artifacts/<uuid>.docx` tem uma barra interna que precisa
    sobreviver ao escapamento (safe="/~"), nunca virar %2F."""
    capturado = {}

    def _assinar_fake(sts):
        capturado["sts"] = sts
        return b"\x00"

    url = ast._construir_url_assinada_v4(
        "b", "artifacts/deadbeef.docx", "sa@x.iam.gserviceaccount.com", 900, None, _assinar_fake
    )
    assert "/b/artifacts/deadbeef.docx?" in url
    assert "%2F" not in url.split("?")[0]


def test_credencial_no_x_goog_credential_e_percent_encoded_com_barras():
    """O valor de `X-Goog-Credential` (que contém `/`) DEVE ter as barras
    escapadas na query string (Gate 6.6-E — verificado ponto a ponto
    contra a documentação oficial do algoritmo V4)."""
    url = ast._construir_url_assinada_v4(
        "b", "artifacts/x.docx", "sa@x.iam.gserviceaccount.com", 900, None,
        lambda sts: b"\x00",
    )
    assert "X-Goog-Credential=sa%40x.iam.gserviceaccount.com%2F" in url


def test_sem_content_disposition_nao_inclui_o_parametro():
    url = ast._construir_url_assinada_v4(
        "b", "artifacts/x.docx", "sa@x.iam.gserviceaccount.com", 900, None,
        lambda sts: b"\x00",
    )
    assert "response-content-disposition" not in url


# ============================================================== nome do objeto

def test_nome_objeto_segue_o_padrao_artifacts_uuid_docx():
    artefato_id = ast._novo_id_artefato()
    assert ast._nome_objeto(artefato_id) == f"artifacts/{artefato_id}.docx"
    assert len(artefato_id) == 32
    int(artefato_id, 16)  # é hexadecimal puro -- levanta ValueError se não for


def test_ids_sao_unicos_entre_chamadas():
    ids = {ast._novo_id_artefato() for _ in range(200)}
    assert len(ids) == 200


# ===================================================== expires_at / created_at

def test_expires_at_e_exatamente_ttl_de_producao_apos_agora():
    transporte = _FakeTransporte()
    antes = dt.datetime.now(dt.timezone.utc)
    entrega = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte)
    depois = dt.datetime.now(dt.timezone.utc)

    expira = dt.datetime.strptime(entrega.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    delta_min = (expira - antes).total_seconds()
    delta_max = (expira - depois).total_seconds()
    assert 86399 <= delta_min <= 86401
    assert 86399 <= delta_max <= 86401


# ==================================================== limpeza oportunista

def _objeto_com_idade(transporte, artefato_id, idade_segundos, agora):
    """Insere um objeto fake diretamente no backend, com `created_at`
    calculado para ter exatamente `idade_segundos` em relação a `agora`
    — sem passar por `entregar_artefato_efemero` (que sempre usa "agora"
    real)."""
    criado_em = agora - dt.timedelta(seconds=idade_segundos)
    nome = ast._nome_objeto(artefato_id)
    transporte.objetos[nome] = (
        DOCX_FAKE, ast.CONTENT_TYPE_DOCX,
        {"artifact_id": artefato_id, "created_at": criado_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "expires_at": "irrelevante-para-este-teste", "sha256": SHA_FAKE},
    )
    return nome


def test_limpeza_remove_objeto_alem_do_limiar_e_preserva_objeto_recente():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    velho = _objeto_com_idade(transporte, "velho00000000000000000000000000", 100000, agora)  # > 93600s (26h)
    novo = _objeto_com_idade(transporte, "novo00000000000000000000000000000"[:32], 60, agora)  # bem recente

    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)

    assert velho not in transporte.objetos
    assert novo in transporte.objetos
    assert resultado["inspecionados"] == 2
    assert resultado["excluidos"] == 1
    assert resultado["falhas"] == 0


def test_limpeza_no_limiar_exato_ainda_nao_e_elegivel():
    """< LIMPEZA_ELEGIVEL_SEGUNDOS nunca é excluído -- só >= (checado
    pela borda: 1 segundo antes do limiar sobrevive)."""
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    nome = _objeto_com_idade(transporte, "bordaaaaaaaaaaaaaaaaaaaaaaaaaaaa", ast.LIMPEZA_ELEGIVEL_SEGUNDOS - 1, agora)
    ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert nome in transporte.objetos


def test_limpeza_ignora_objeto_sem_metadado_created_at():
    transporte = _FakeTransporte()
    nome = "artifacts/sem-metadado.docx"
    transporte.objetos[nome] = (DOCX_FAKE, ast.CONTENT_TYPE_DOCX, {"sha256": SHA_FAKE})
    resultado = ast.limpar_artefatos_elegiveis(transporte)
    assert nome in transporte.objetos
    assert resultado["inspecionados"] == 1
    assert resultado["excluidos"] == 0


def test_limpeza_nunca_inspeciona_fora_do_prefixo_artifacts():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    transporte.objetos["outro-prefixo/coisa.docx"] = (
        DOCX_FAKE, ast.CONTENT_TYPE_DOCX,
        {"created_at": (agora - dt.timedelta(seconds=100000)).strftime("%Y-%m-%dT%H:%M:%SZ")},
    )
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["inspecionados"] == 0
    assert "outro-prefixo/coisa.docx" in transporte.objetos


def test_limpeza_respeita_teto_de_objetos_por_varredura():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    for i in range(ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA + 5):
        _objeto_com_idade(transporte, f"obj{i:029d}", 100000, agora)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["inspecionados"] == ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA
    assert resultado["excluidos"] == ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA
    assert len(transporte.objetos) == 5


def test_limpeza_registra_falha_sem_propagar_excecao():
    transporte = _FakeTransporte(falhar_exclusao=True)
    agora = dt.datetime.now(dt.timezone.utc)
    _objeto_com_idade(transporte, "falhaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 100000, agora)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["falhas"] == 1
    assert resultado["excluidos"] == 0


def test_limiar_de_elegibilidade_e_exatamente_o_ttl_de_download():
    """Elegibilidade = exatamente `TTL_DOWNLOAD_SEGUNDOS` (24h), sem
    margem adicional -- decisão explícita do usuário (Gate 6.6-E,
    continuação "HARD DELETE REQUIRED": elegível "imediatamente após a
    janela de 24h expirar"). A retenção normal (~24-25h) vem da cadência
    de varredura (ex.: agendamento horário via
    `scripts/limpar_artefatos_agendado.py`), não de uma margem embutida
    neste limiar."""
    assert ast.LIMPEZA_ELEGIVEL_SEGUNDOS == ast.TTL_DOWNLOAD_SEGUNDOS
