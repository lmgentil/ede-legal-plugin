#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_artifact_storage.py — regressão do armazenamento efêmero e da
entrega por URL opaca do EDE (Gate 6.6-E, ADR-0019; URL opaca desde o
Gate 6.6-F/G, DELIVERY-CLIENT-01).

Todos os testes de unidade usam `_FakeTransporte`, em memória — nenhum
toca rede. A prova contra GCS real é item de homologação (relatório do
gate), fora da suíte automatizada.

Histórico: até o Gate 6.6-F Fase 2 este arquivo cobria também o
algoritmo de assinatura V4 (`_construir_url_assinada_v4`). Esses testes
saíram junto com o código que testavam, quando a URL V4 exposta ao
cliente foi substituída pela URL opaca servida pelo próprio EDE — não
por enfraquecimento de cobertura (ver CHANGELOG)."""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import artifact_storage as ast  # noqa: E402


# ------------------------------------------------------------- fake transporte

class _FakeTransporte:
    """Backend em memória com gerações, como o GCS: cada `enviar` cria
    uma geração nova; `baixar` só devolve a geração pedida."""

    def __init__(self, falhar_envio=False, falhar_exclusao=False, falhar_leitura=False):
        self.objetos: dict[str, tuple[bytes, str, dict, str]] = {}
        self.chamadas_enviar = []
        self.chamadas_baixar = []
        self.chamadas_excluir = []
        self._geracao = 1000
        self._falhar_envio = falhar_envio
        self._falhar_exclusao = falhar_exclusao
        self._falhar_leitura = falhar_leitura

    def enviar(self, object_name, dados, content_type, metadata):
        self.chamadas_enviar.append((object_name, len(dados), content_type, dict(metadata)))
        if self._falhar_envio:
            raise ast.ErroArmazenamentoArtefato("gcs_status_inesperado")
        self._geracao += 1
        self.objetos[object_name] = (dados, content_type, dict(metadata), str(self._geracao))

    def obter_metadado(self, object_name):
        if self._falhar_leitura:
            raise ast.ErroArmazenamentoArtefato("rede_falhou")
        if object_name not in self.objetos:
            return None
        _, content_type, metadata, geracao = self.objetos[object_name]
        return dict(metadata), geracao, content_type

    def baixar(self, object_name, generation):
        self.chamadas_baixar.append((object_name, generation))
        if object_name not in self.objetos:
            return None
        dados, _, _, geracao = self.objetos[object_name]
        return dados if geracao == generation else None

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
BASE_URL = "https://ede-mcp-homolog-000000000000.southamerica-east1.run.app"


def _entregar(transporte=None):
    transporte = transporte if transporte is not None else _FakeTransporte()
    entrega = ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte, base_url=BASE_URL)
    return transporte, entrega


def _token(entrega):
    prefixo = f"{BASE_URL}{ast.PREFIXO_ROTA_DOWNLOAD}"
    assert entrega.download_url.startswith(prefixo)
    return entrega.download_url[len(prefixo):]


# ============================================================= entrega

def test_url_e_do_proprio_ede_sem_query_string_assinada():
    _, entrega = _entregar()
    token = _token(entrega)
    assert entrega.download_url == f"{BASE_URL}/download/{token}"
    assert "?" not in entrega.download_url
    assert "storage.googleapis.com" not in entrega.download_url
    assert "X-Goog" not in entrega.download_url


def test_token_tem_256_bits_formato_base64url_de_43_caracteres():
    _, entrega = _entregar()
    token = _token(entrega)
    assert len(token) == 43
    assert ast.token_bem_formado(token)
    assert ast._TOKEN_BYTES == 32  # 256 bits de entropia do gerador do sistema


def test_objeto_e_identificado_por_sha256_do_token_nunca_pelo_token():
    transporte, entrega = _entregar()
    token = _token(entrega)
    esperado = hashlib.sha256(token.encode("ascii")).hexdigest()
    assert entrega.artefato_id == esperado
    (nome_objeto, _, _, metadata), = transporte.chamadas_enviar
    assert nome_objeto == f"artifacts/{esperado}.docx"
    # o token em claro não é persistido em lugar nenhum do armazenamento
    assert token not in nome_objeto
    assert token not in json.dumps(metadata)


def test_token_nao_aparece_no_repr_da_entrega():
    _, entrega = _entregar()
    assert _token(entrega) not in repr(entrega)


def test_tokens_e_objetos_sao_unicos_entre_chamadas_mesmo_documento():
    transporte = _FakeTransporte()
    tokens = {_token(_entregar(transporte)[1]) for _ in range(50)}
    assert len(tokens) == 50
    assert len(transporte.objetos) == 50


def test_url_e_objeto_nao_contem_dado_de_caso_nem_filename():
    transporte, entrega = _entregar()
    (nome_objeto, _, _, _), = transporte.chamadas_enviar
    for texto in (entrega.download_url, nome_objeto):
        assert SHA_FAKE not in texto
        assert "Contestacao" not in texto
    assert ".docx" not in entrega.download_url


def test_bytes_enviados_sao_exatamente_os_recebidos_sha_confere():
    transporte, entrega = _entregar()
    dados, content_type, metadata, _ = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    assert dados == DOCX_FAKE
    assert content_type == ast.CONTENT_TYPE_DOCX
    assert metadata["sha256"] == SHA_FAKE


def test_metadado_contem_so_campos_seguros():
    transporte, entrega = _entregar()
    _, _, metadata, _ = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    assert set(metadata) == {"artifact_id", "created_at", "expires_at", "sha256", "filename"}
    assert metadata["artifact_id"] == entrega.artefato_id
    assert metadata["filename"] == FILENAME


def test_ttl_e_constante_de_24h_nunca_parametro():
    import inspect

    assinatura = inspect.signature(ast.entregar_artefato_efemero)
    assert "ttl" not in "".join(assinatura.parameters).lower()
    assert ast.TTL_DOWNLOAD_SEGUNDOS == 24 * 60 * 60
    assert ast.LIMPEZA_ELEGIVEL_SEGUNDOS == ast.TTL_DOWNLOAD_SEGUNDOS


def test_expires_at_e_exatamente_24h_apos_created_at():
    transporte = _FakeTransporte()
    antes = dt.datetime.now(dt.timezone.utc)
    _, entrega = _entregar(transporte)
    _, _, metadata, _ = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    criado = ast._ler_data(metadata["created_at"])
    expira = ast._ler_data(metadata["expires_at"])
    assert expira - criado == dt.timedelta(seconds=ast.TTL_DOWNLOAD_SEGUNDOS)
    assert entrega.expires_at == metadata["expires_at"]
    assert 86399 <= (expira - antes).total_seconds() <= 86401


def test_falha_de_upload_propaga_e_nao_devolve_link():
    transporte = _FakeTransporte(falhar_envio=True)
    with pytest.raises(ast.ErroArmazenamentoArtefato) as exc:
        _entregar(transporte)
    assert exc.value.motivo == "gcs_status_inesperado"
    assert transporte.objetos == {}


@pytest.mark.parametrize("base_url", [
    None, "", "   ",
    "http://ede.example.test",
    "https://",
    "https://ede.example.test/mcp",
    "https://ede.example.test/download",
    "https://ede.example.test?x=1",
    "https://ede.example.test#frag",
    "https://user@ede.example.test",
    "https://ede.example.test:8443",
    "ede.example.test",
])
def test_base_url_malformada_falha_fechado_antes_do_upload(base_url):
    transporte = _FakeTransporte()
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, FILENAME, transporte, base_url=base_url)
    assert transporte.chamadas_enviar == []


def test_base_url_valida_e_normalizada_para_origem():
    assert ast.validar_base_url_download("https://Ede.Example.Test/") == "https://ede.example.test"
    assert ast.obter_base_url_download_do_ambiente(
        {ast.ENV_ARTEFATOS_DOWNLOAD_BASE_URL: BASE_URL}
    ) == BASE_URL
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.obter_base_url_download_do_ambiente({})


@pytest.mark.parametrize("filename", ['x".docx', "a b.docx", "../x.docx", "x.docx;y=1", "x.pdf", ""])
def test_filename_fora_do_formato_seguro_falha_fechado_antes_do_upload(filename):
    transporte = _FakeTransporte()
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.entregar_artefato_efemero(DOCX_FAKE, SHA_FAKE, filename, transporte, base_url=BASE_URL)
    assert transporte.chamadas_enviar == []


def test_transporte_real_exige_so_o_bucket():
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.TransporteGcsReal(bucket="")
    with pytest.raises(ast.ErroConfiguracaoArtefato):
        ast.obter_transporte_do_ambiente({})
    transporte = ast.obter_transporte_do_ambiente({ast.ENV_ARTEFATOS_GCS_BUCKET: "ede-legal-mcp-01-artefatos-efemeros"})
    assert transporte._bucket == "ede-legal-mcp-01-artefatos-efemeros"


def test_arquitetura_nao_depende_de_assinatura_v4():
    """Gate 6.6-F/G — a entrega não usa `signBlob`, auto-impersonation
    nem `EDE_ARTEFATOS_SIGNER_SA`: nenhum desses conceitos existe mais
    no módulo, e a variável, se presente, é ignorada."""
    for nome in ("ENV_ARTEFATOS_SIGNER_SA", "ErroAssinaturaArtefato", "_construir_url_assinada_v4"):
        assert not hasattr(ast, nome)
    assert not hasattr(ast.TransporteGcsReal, "assinar_url")
    fonte = Path(ast.__file__).read_text(encoding="utf-8")
    assert "iamcredentials" not in fonte
    assert ":signBlob" not in fonte
    transporte = ast.obter_transporte_do_ambiente({
        ast.ENV_ARTEFATOS_GCS_BUCKET: "b", "EDE_ARTEFATOS_SIGNER_SA": "sa@x.iam.gserviceaccount.com",
    })
    assert isinstance(transporte, ast.TransporteGcsReal)


# ============================================================= download

def test_download_valido_devolve_os_bytes_exatos_sha_conferido():
    transporte, entrega = _entregar()
    r = ast.resolver_download(_token(entrega), transporte)
    assert r.status == ast.DOWNLOAD_ENTREGUE
    assert r.dados == DOCX_FAKE
    assert hashlib.sha256(r.dados).hexdigest() == SHA_FAKE == r.sha256
    assert r.filename == FILENAME
    assert r.artefato_id == entrega.artefato_id


def test_mesmo_token_baixado_varias_vezes_dentro_da_janela():
    transporte, entrega = _entregar()
    token = _token(entrega)
    resultados = [ast.resolver_download(token, transporte) for _ in range(3)]
    assert all(r.status == ast.DOWNLOAD_ENTREGUE for r in resultados)
    assert {r.dados for r in resultados} == {DOCX_FAKE}
    # ainda válido um segundo antes de expirar
    expira = ast._ler_data(entrega.expires_at)
    r = ast.resolver_download(token, transporte, agora=expira - dt.timedelta(seconds=1))
    assert r.status == ast.DOWNLOAD_ENTREGUE


def test_le_a_geracao_observada_no_metadado():
    transporte, entrega = _entregar()
    ast.resolver_download(_token(entrega), transporte)
    _, _, _, geracao = transporte.objetos[f"artifacts/{entrega.artefato_id}.docx"]
    assert transporte.chamadas_baixar == [(f"artifacts/{entrega.artefato_id}.docx", geracao)]


@pytest.mark.parametrize("token_ruim", [
    "",
    "a" * 42,                   # truncado
    "a" * 44,                   # longo demais
    "a" * 42 + "!",             # caractere inválido
    "a" * 42 + "=",             # padding base64 não é emitido
    "a" * 21 + "/" + "a" * 21,  # barra
    "a" * 42 + ".",
    "a" * 42 + "%",
    "a" * 41 + "éa",       # não-ASCII
])
def test_token_malformado_e_nao_encontrado_sem_nenhum_io(token_ruim):
    transporte = _FakeTransporte(falhar_leitura=True)  # qualquer I/O explodiria
    r = ast.resolver_download(token_ruim, transporte)
    assert r.status == ast.DOWNLOAD_NAO_ENCONTRADO
    assert r.motivo == ast.MOTIVO_TOKEN_MALFORMADO
    assert r.dados is None and r.artefato_id is None


def test_token_truncado_de_um_token_real_e_nao_encontrado():
    transporte, entrega = _entregar()
    r = ast.resolver_download(_token(entrega)[:-1], transporte)
    assert r.status == ast.DOWNLOAD_NAO_ENCONTRADO
    assert r.motivo == ast.MOTIVO_TOKEN_MALFORMADO


def test_token_bem_formado_desconhecido_e_nao_encontrado():
    transporte, _ = _entregar()
    r = ast.resolver_download(ast._novo_token(), transporte)
    assert r.status == ast.DOWNLOAD_NAO_ENCONTRADO
    assert r.motivo == ast.MOTIVO_OBJETO_INEXISTENTE
    assert r.dados is None


def test_expirado_e_nao_encontrado_na_borda_exata():
    transporte, entrega = _entregar()
    expira = ast._ler_data(entrega.expires_at)
    for agora in (expira, expira + dt.timedelta(days=1)):
        r = ast.resolver_download(_token(entrega), transporte, agora=agora)
        assert r.status == ast.DOWNLOAD_NAO_ENCONTRADO
        assert r.motivo == ast.MOTIVO_EXPIRADO
        assert r.dados is None
    assert transporte.chamadas_baixar == []  # expirado nunca lê conteúdo


def _corromper_metadado(transporte, entrega, **alteracoes):
    nome = f"artifacts/{entrega.artefato_id}.docx"
    dados, content_type, metadata, geracao = transporte.objetos[nome]
    for chave, valor in alteracoes.items():
        if valor is None:
            metadata.pop(chave, None)
        else:
            metadata[chave] = valor
    transporte.objetos[nome] = (dados, content_type, metadata, geracao)


@pytest.mark.parametrize("alteracoes", [
    {"expires_at": None},
    {"created_at": None},
    {"sha256": None},
    {"filename": None},
    {"artifact_id": None},
    {"expires_at": "amanha"},
    {"created_at": "2026-13-45T99:99:99Z"},
    {"sha256": "nao-e-hex"},
    {"sha256": "A" * 64},
    {"filename": 'x".docx'},
    {"filename": "../../etc/passwd"},
    {"artifact_id": "0" * 64},
    # janela maior que o contrato de 24h — nunca alongada por metadado
    {"expires_at": "2999-01-01T00:00:00Z"},
])
def test_metadado_ausente_ou_malformado_e_nao_encontrado(alteracoes):
    transporte, entrega = _entregar()
    _corromper_metadado(transporte, entrega, **alteracoes)
    r = ast.resolver_download(_token(entrega), transporte)
    assert r.status == ast.DOWNLOAD_NAO_ENCONTRADO
    assert r.motivo == ast.MOTIVO_METADADO_INVALIDO
    assert r.dados is None
    assert transporte.chamadas_baixar == []


def test_metadado_totalmente_ausente_e_nao_encontrado():
    transporte, entrega = _entregar()
    nome = f"artifacts/{entrega.artefato_id}.docx"
    dados, content_type, _, geracao = transporte.objetos[nome]
    transporte.objetos[nome] = (dados, content_type, {}, geracao)
    r = ast.resolver_download(_token(entrega), transporte)
    assert (r.status, r.motivo) == (ast.DOWNLOAD_NAO_ENCONTRADO, ast.MOTIVO_METADADO_INVALIDO)


def test_content_type_do_objeto_diferente_de_docx_e_nao_encontrado():
    transporte, entrega = _entregar()
    nome = f"artifacts/{entrega.artefato_id}.docx"
    dados, _, metadata, geracao = transporte.objetos[nome]
    transporte.objetos[nome] = (dados, "text/html", metadata, geracao)
    r = ast.resolver_download(_token(entrega), transporte)
    assert (r.status, r.motivo) == (ast.DOWNLOAD_NAO_ENCONTRADO, ast.MOTIVO_METADADO_INVALIDO)


def test_sha_divergente_falha_fechado_sem_bytes():
    transporte, entrega = _entregar()
    nome = f"artifacts/{entrega.artefato_id}.docx"
    _, content_type, metadata, geracao = transporte.objetos[nome]
    transporte.objetos[nome] = (DOCX_FAKE + b"adulterado", content_type, metadata, geracao)
    r = ast.resolver_download(_token(entrega), transporte)
    assert r.status == ast.DOWNLOAD_INTEGRIDADE_DIVERGENTE
    assert r.dados is None and r.filename is None


def test_hard_delete_pela_limpeza_torna_o_download_nao_encontrado():
    transporte, entrega = _entregar()
    token = _token(entrega)
    assert ast.resolver_download(token, transporte).status == ast.DOWNLOAD_ENTREGUE
    depois = ast._ler_data(entrega.expires_at) + dt.timedelta(seconds=1)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=depois)
    assert resultado["excluidos"] == 1
    assert transporte.objetos == {}
    # mesmo com um relógio "anterior" à expiração, o objeto não existe mais
    r = ast.resolver_download(token, transporte, agora=depois - dt.timedelta(hours=2))
    assert (r.status, r.motivo) == (ast.DOWNLOAD_NAO_ENCONTRADO, ast.MOTIVO_OBJETO_INEXISTENTE)


def test_objeto_excluido_entre_metadado_e_conteudo_e_nao_encontrado():
    transporte, entrega = _entregar()
    original_baixar = transporte.baixar

    def _baixar_apos_exclusao(nome, geracao):
        transporte.objetos.pop(nome, None)
        return original_baixar(nome, geracao)

    transporte.baixar = _baixar_apos_exclusao
    r = ast.resolver_download(_token(entrega), transporte)
    assert (r.status, r.motivo) == (ast.DOWNLOAD_NAO_ENCONTRADO, ast.MOTIVO_OBJETO_INEXISTENTE)


def test_falha_operacional_do_armazenamento_e_indisponivel_nunca_404():
    transporte, entrega = _entregar()
    transporte._falhar_leitura = True
    r = ast.resolver_download(_token(entrega), transporte)
    assert r.status == ast.DOWNLOAD_INDISPONIVEL
    assert r.dados is None


# ==================================================== limpeza

def _objeto_com_idade(transporte, artefato_id, idade_segundos, agora, expira_em=None):
    criado_em = agora - dt.timedelta(seconds=idade_segundos)
    if expira_em is None:
        expira_em = criado_em + dt.timedelta(seconds=ast.TTL_DOWNLOAD_SEGUNDOS)
    nome = ast._nome_objeto(artefato_id)
    transporte.objetos[nome] = (
        DOCX_FAKE, ast.CONTENT_TYPE_DOCX,
        {"artifact_id": artefato_id, "created_at": criado_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "expires_at": expira_em if isinstance(expira_em, str) else expira_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "sha256": SHA_FAKE, "filename": FILENAME},
        "1",
    )
    return nome


def test_limpeza_remove_objeto_expirado_e_preserva_objeto_recente():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    velho = _objeto_com_idade(transporte, "a" * 64, 100000, agora)
    novo = _objeto_com_idade(transporte, "b" * 64, 60, agora)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert velho not in transporte.objetos
    assert novo in transporte.objetos
    assert resultado == {"inspecionados": 2, "excluidos": 1, "falhas": 0}


def test_limpeza_um_segundo_antes_do_limiar_ainda_nao_e_elegivel():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    nome = _objeto_com_idade(transporte, "c" * 64, ast.LIMPEZA_ELEGIVEL_SEGUNDOS - 1, agora)
    ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert nome in transporte.objetos


def test_limpeza_ignora_objeto_sem_expires_at():
    transporte = _FakeTransporte()
    nome = "artifacts/sem-metadado.docx"
    transporte.objetos[nome] = (DOCX_FAKE, ast.CONTENT_TYPE_DOCX, {"sha256": SHA_FAKE}, "1")
    resultado = ast.limpar_artefatos_elegiveis(transporte)
    assert nome in transporte.objetos
    assert resultado["excluidos"] == 0


def test_limpeza_ignora_objeto_com_expires_at_malformado():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    nome = _objeto_com_idade(transporte, "d" * 64, 100000, agora, expira_em="isto-nao-e-uma-data")
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert nome in transporte.objetos
    assert resultado["excluidos"] == 0


def test_limpeza_nunca_exclui_antes_da_autorizacao_de_download_expirar():
    """A decisão é sempre por `expires_at` — a MESMA fonte de verdade da
    rota de download — nunca recalculada a partir de `created_at`."""
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    nome = _objeto_com_idade(transporte, "e" * 64, ast.TTL_DOWNLOAD_SEGUNDOS + 100, agora,
                              expira_em=agora + dt.timedelta(seconds=5))
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert nome in transporte.objetos
    assert resultado["excluidos"] == 0


def test_limpeza_exclui_assim_que_expires_at_e_ultrapassado():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    nome = _objeto_com_idade(transporte, "f" * 64, 10, agora, expira_em=agora - dt.timedelta(seconds=1))
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert nome not in transporte.objetos
    assert resultado["excluidos"] == 1


def test_limpeza_nunca_inspeciona_fora_do_prefixo_artifacts():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    transporte.objetos["outro-prefixo/coisa.docx"] = (
        DOCX_FAKE, ast.CONTENT_TYPE_DOCX,
        {"expires_at": (agora - dt.timedelta(seconds=100000)).strftime("%Y-%m-%dT%H:%M:%SZ")}, "1",
    )
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["inspecionados"] == 0
    assert "outro-prefixo/coisa.docx" in transporte.objetos


def test_limpeza_respeita_teto_de_objetos_por_varredura():
    transporte = _FakeTransporte()
    agora = dt.datetime.now(dt.timezone.utc)
    for i in range(ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA + 5):
        _objeto_com_idade(transporte, f"{i:064x}", 100000, agora)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["inspecionados"] == ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA
    assert resultado["excluidos"] == ast.LIMPEZA_MAX_OBJETOS_POR_VARREDURA
    assert len(transporte.objetos) == 5


def test_limpeza_registra_falha_sem_propagar_excecao():
    transporte = _FakeTransporte(falhar_exclusao=True)
    agora = dt.datetime.now(dt.timezone.utc)
    _objeto_com_idade(transporte, "9" * 64, 100000, agora)
    resultado = ast.limpar_artefatos_elegiveis(transporte, agora=agora)
    assert resultado["falhas"] == 1
    assert resultado["excluidos"] == 0
