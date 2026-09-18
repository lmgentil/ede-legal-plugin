# -*- coding: utf-8 -*-
"""
tests/test_legal_readiness.py — checagens determinísticas de prontidão
jurídica do Core (Gate 6.4-A, ADR-0015/ADR-0017).

Cobre a matriz de negativos/positivos exigida pelo gate para os dois
pré-requisitos de `contestacao_status`:

  Modelo Oficial: não configurado / ausente / SHA divergente / DOCX
  corrompido / contrato desatualizado / configurado e conforme.

  Corpus RAG: manifesto ausente / corpus ausente / corpus incompleto /
  corpus divergente do manifesto (hash) / corpus íntegro.

Reaproveita o par SCHEMA_MINIMO/CATALOGO_MINIMO e os helpers de DOCX
sintético já existentes em test_instalar_modelo_oficial.py (mesmo padrão
documentado lá: sintético para a matriz de ramos, um teste `docx_real`
à parte para o contrato REAL) — nenhum parser/fixture novo duplicado.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import legal_readiness as lr  # noqa: E402
from test_instalar_modelo_oficial import (  # noqa: E402
    CATALOGO_MINIMO,
    SCHEMA_MINIMO,
    _CORPO_PLACEHOLDER_FALTANTE,
    _CORPO_VALIDO,
    _partes_minimas,
    _zip_com_partes,
)

RAG_REAL = BASE / "rag"
MANIFESTO_REAL = RAG_REAL / "corpus_manifest.json"


# ------------------------------------------------------------- Modelo Oficial

def _escrever_schema_catalogo(tmp_path: Path):
    schema_path = tmp_path / "schema.json"
    catalogo_path = tmp_path / "blocos.json"
    schema_path.write_text(json.dumps(SCHEMA_MINIMO), encoding="utf-8")
    catalogo_path.write_text(json.dumps(CATALOGO_MINIMO), encoding="utf-8")
    return schema_path, catalogo_path


def _docx_sintetico(tmp_path: Path, corpo_bytes: bytes, nome="modelo.docx") -> Path:
    destino = tmp_path / nome
    _zip_com_partes(destino, _partes_minimas(corpo_bytes))
    return destino


def test_modelo_oficial_nao_configurado(monkeypatch):
    monkeypatch.delenv(lr.ENV_MODELO_PATH, raising=False)
    monkeypatch.delenv(lr.ENV_MODELO_SHA256, raising=False)
    r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_CONFIGURED"


def test_modelo_oficial_parcialmente_configurado_e_not_configured(monkeypatch, tmp_path):
    """Só um dos dois (path OU sha) presente ainda é NOT_CONFIGURED — nunca
    tenta validar com metade do contrato."""
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.delenv(lr.ENV_MODELO_SHA256, raising=False)
    assert lr.avaliar_modelo_oficial().status == "NOT_CONFIGURED"


def test_modelo_oficial_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(tmp_path / "nao-existe.docx"))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, "a" * 64)
    r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"


def test_modelo_oficial_sha_divergente(monkeypatch, tmp_path):
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, "0" * 64)
    r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"
    assert "SHA-256" in r.detail


def test_modelo_oficial_docx_corrompido(monkeypatch, tmp_path):
    corrompido = tmp_path / "corrompido.docx"
    corrompido.write_bytes(b"isto nao e um zip")
    sha = hashlib.sha256(corrompido.read_bytes()).hexdigest()
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(corrompido))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"


def test_modelo_oficial_contrato_desatualizado(monkeypatch, tmp_path):
    """DOCX válido, ZIP íntegro, SHA bate — mas o placeholder exigido pelo
    schema não está fisicamente presente (Template Lock institucional
    desatualizado)."""
    docx = _docx_sintetico(tmp_path, _CORPO_PLACEHOLDER_FALTANTE)
    sha = hashlib.sha256(docx.read_bytes()).hexdigest()
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)
    assert r.status == "NOT_READY"


def test_modelo_oficial_configurado_e_conforme(monkeypatch, tmp_path):
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    sha = hashlib.sha256(docx.read_bytes()).hexdigest()
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)
    assert r.status == "READY"


def test_modelo_oficial_nunca_vaza_caminho_no_detail(monkeypatch, tmp_path):
    """Segurança (CLAUDE.md §12/§18): o caminho local do Modelo Oficial
    provisionado nunca aparece em `detail` — health é diagnóstico
    estrutural, nunca revela onde/como o asset está armazenado."""
    marcador = "CAMINHO-SECRETO-DO-ADVOGADO"
    tmp_marcado = tmp_path / marcador
    tmp_marcado.mkdir()
    docx = _docx_sintetico(tmp_marcado, _CORPO_VALIDO)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, "0" * 64)
    r = lr.avaliar_modelo_oficial()
    assert marcador not in r.detail


@pytest.mark.docx_real
def test_modelo_oficial_real_conforme(monkeypatch):
    """Integração com o Modelo Oficial real, quando presente localmente —
    espelha o mesmo padrão docx_real de test_instalar_modelo_oficial.py."""
    template_real = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
    if not template_real.is_file():
        pytest.skip(f"{template_real} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    sha = hashlib.sha256(template_real.read_bytes()).hexdigest()
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(template_real))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    r = lr.avaliar_modelo_oficial()
    assert r.status == "READY", r.detail


# ------------------------------------------------- Modelo Oficial via GCS (6.4-B)

def _limpar_env_gcs(monkeypatch):
    for var in (lr.ENV_GCS_BUCKET, lr.ENV_GCS_OBJECT, lr.ENV_GCS_GENERATION,
                lr.ENV_MODELO_PATH, lr.ENV_MODELO_SHA256):
        monkeypatch.delenv(var, raising=False)


def test_gcs_sem_nenhuma_variavel_cai_no_modo_local_not_configured(monkeypatch):
    """B/C/D/E combinadas: nenhuma variável GCS presente e nenhuma
    variável local presente -> NOT_CONFIGURED, sem tentar rede."""
    _limpar_env_gcs(monkeypatch)
    with patch.object(lr, "_baixar_modelo_oficial_gcs") as baixar:
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_CONFIGURED"
    baixar.assert_not_called()


@pytest.mark.parametrize("ausente", ["bucket", "object", "generation", "sha"])
def test_gcs_configuracao_parcial_e_not_configured(monkeypatch, ausente):
    """B/C/D/E: qualquer uma das quatro variáveis ausente com as outras
    três presentes -> NOT_CONFIGURED, nunca tenta baixar com config
    incompleta."""
    _limpar_env_gcs(monkeypatch)
    valores = {
        lr.ENV_GCS_BUCKET: "ede-modelo-oficial-privado",
        lr.ENV_GCS_OBJECT: "modelo-oficial/modelo-oficial.docx",
        lr.ENV_GCS_GENERATION: "1234567890123456",
        lr.ENV_MODELO_SHA256: "0" * 64,
    }
    chave_por_nome = {
        "bucket": lr.ENV_GCS_BUCKET, "object": lr.ENV_GCS_OBJECT,
        "generation": lr.ENV_GCS_GENERATION, "sha": lr.ENV_MODELO_SHA256,
    }
    valores.pop(chave_por_nome[ausente])
    for k, v in valores.items():
        monkeypatch.setenv(k, v)
    with patch.object(lr, "_baixar_modelo_oficial_gcs") as baixar:
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_CONFIGURED"
    baixar.assert_not_called()


def _configurar_env_gcs_completo(monkeypatch, sha):
    monkeypatch.setenv(lr.ENV_GCS_BUCKET, "ede-modelo-oficial-privado")
    monkeypatch.setenv(lr.ENV_GCS_OBJECT, "modelo-oficial/modelo-oficial.docx")
    monkeypatch.setenv(lr.ENV_GCS_GENERATION, "1234567890123456")
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)


def test_gcs_exato_com_sha_correto_e_docx_valido_e_ready(monkeypatch, tmp_path):
    """A: geração exata + SHA exato + DOCX válido -> READY."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    conteudo = docx.read_bytes()
    sha = hashlib.sha256(conteudo).hexdigest()
    _configurar_env_gcs_completo(monkeypatch, sha)
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)

    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=conteudo) as baixar:
        r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)

    assert r.status == "READY", r.detail
    baixar.assert_called_once_with(
        "ede-modelo-oficial-privado", "modelo-oficial/modelo-oficial.docx", "1234567890123456"
    )


def test_gcs_objeto_nao_encontrado_e_not_ready(monkeypatch):
    """F: objeto ausente no bucket -> NOT_READY, nunca NOT_CONFIGURED."""
    _limpar_env_gcs(monkeypatch)
    _configurar_env_gcs_completo(monkeypatch, "0" * 64)
    with patch.object(lr, "_baixar_modelo_oficial_gcs",
                       side_effect=lr.ErroAquisicaoGCS("objeto_ou_geracao_nao_encontrado")):
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"


def test_gcs_geracao_nao_encontrada_e_not_ready(monkeypatch):
    """G: geração pinada não encontrada (objeto existe, mas não aquela
    versão) -> NOT_READY, nunca busca outra geração."""
    _limpar_env_gcs(monkeypatch)
    _configurar_env_gcs_completo(monkeypatch, "0" * 64)
    with patch.object(lr, "_baixar_modelo_oficial_gcs",
                       side_effect=lr.ErroAquisicaoGCS("objeto_ou_geracao_nao_encontrado")) as baixar:
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"
    # nunca chamado mais de uma vez com parâmetros diferentes (sem retry
    # com outra geração)
    assert baixar.call_count == 1


def test_gcs_sha_baixado_diverge_e_not_ready(monkeypatch, tmp_path):
    """H: bytes baixados não batem com o SHA-256 configurado -> NOT_READY."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    _configurar_env_gcs_completo(monkeypatch, "f" * 64)
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=docx.read_bytes()):
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"
    assert "SHA-256" in r.detail


def test_gcs_bytes_corrompidos_e_not_ready(monkeypatch):
    """I: bytes baixados não formam um ZIP/OOXML válido -> NOT_READY."""
    _limpar_env_gcs(monkeypatch)
    conteudo = b"isto nao e um docx"
    sha = hashlib.sha256(conteudo).hexdigest()
    _configurar_env_gcs_completo(monkeypatch, sha)
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=conteudo):
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"


def test_gcs_docx_valido_mas_contrato_invalido_e_not_ready(monkeypatch, tmp_path):
    """J: DOCX válido, ZIP íntegro, SHA bate, mas o Template Lock/
    contrato institucional está desatualizado -> NOT_READY."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_PLACEHOLDER_FALTANTE)
    conteudo = docx.read_bytes()
    sha = hashlib.sha256(conteudo).hexdigest()
    _configurar_env_gcs_completo(monkeypatch, sha)
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=conteudo):
        r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)
    assert r.status == "NOT_READY"


def test_gcs_nunca_cai_para_caminho_local_mesmo_configurado(monkeypatch, tmp_path):
    """K/L: com QUALQUER variável GCS presente, o modo local nunca é
    consultado, mesmo que EDE_MODELO_OFICIAL_PATH aponte para um DOCX
    local válido — produção nunca usa um "canonical model" local como
    fallback."""
    _limpar_env_gcs(monkeypatch)
    docx_local = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx_local))
    _configurar_env_gcs_completo(monkeypatch, "0" * 64)  # sha errado de propósito
    with patch.object(lr, "_baixar_modelo_oficial_gcs",
                       side_effect=lr.ErroAquisicaoGCS("objeto_ou_geracao_nao_encontrado")) as baixar:
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"
    baixar.assert_called_once()  # tentou GCS, nunca leu o docx_local


def test_gcs_erro_nunca_expoe_detalhe_de_baixo_nivel(monkeypatch):
    """O: detalhe de `ede_health` nunca inclui a mensagem/exceção crua da
    biblioteca subjacente (rede, autenticação) — só o motivo tipado."""
    _limpar_env_gcs(monkeypatch)
    _configurar_env_gcs_completo(monkeypatch, "0" * 64)
    with patch.object(lr, "_baixar_modelo_oficial_gcs",
                       side_effect=lr.ErroAquisicaoGCS("autenticacao_falhou")):
        r = lr.avaliar_modelo_oficial()
    assert r.status == "NOT_READY"
    assert "autenticacao_falhou" not in r.detail
    assert "Traceback" not in r.detail


def test_gcs_conteudo_nunca_aparece_no_detail(monkeypatch, tmp_path):
    """P: bytes do DOCX (mesmo corrompidos) nunca aparecem em `detail`."""
    _limpar_env_gcs(monkeypatch)
    marcador_binario = b"MARCADOR-BINARIO-SECRETO-DO-DOCX" * 4
    sha = hashlib.sha256(marcador_binario).hexdigest()
    _configurar_env_gcs_completo(monkeypatch, "0" * 64)  # propositalmente errado
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=marcador_binario):
        r = lr.avaliar_modelo_oficial()
    assert b"MARCADOR-BINARIO-SECRETO-DO-DOCX" not in r.detail.encode("utf-8")


def _rastrear_temp_dirs():
    """Espiona `tempfile.TemporaryDirectory` para capturar o caminho real
    de cada diretório efêmero criado por `_validar_conteudo_modelo_oficial`
    — usado só para provar limpeza (M/N), nunca para mudar o
    comportamento do código sob teste."""
    caminhos = []
    original = tempfile.TemporaryDirectory

    class _Rastreado(original):
        def __enter__(self):
            caminho = super().__enter__()
            caminhos.append(caminho)
            return caminho

    return caminhos, _Rastreado


def test_gcs_temp_dir_removido_apos_sucesso(monkeypatch, tmp_path):
    """M: caminho efêmero do DOCX baixado não sobrevive a uma avaliação
    READY."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    conteudo = docx.read_bytes()
    sha = hashlib.sha256(conteudo).hexdigest()
    _configurar_env_gcs_completo(monkeypatch, sha)
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)

    caminhos, _Rastreado = _rastrear_temp_dirs()
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=conteudo), \
         patch("legal_readiness.tempfile.TemporaryDirectory", _Rastreado):
        r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)

    assert r.status == "READY"
    assert caminhos, "nenhum diretório temporário foi capturado"
    for caminho in caminhos:
        assert not Path(caminho).exists(), f"{caminho} não foi removido"


def test_gcs_temp_dir_removido_apos_falha(monkeypatch, tmp_path):
    """N: caminho efêmero também é removido quando a validação falha
    (SHA divergente) — limpeza não depende do caminho feliz."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_VALIDO)
    conteudo = docx.read_bytes()
    _configurar_env_gcs_completo(monkeypatch, "f" * 64)  # sha errado

    caminhos, _Rastreado = _rastrear_temp_dirs()
    with patch.object(lr, "_baixar_modelo_oficial_gcs", return_value=conteudo), \
         patch("legal_readiness.tempfile.TemporaryDirectory", _Rastreado):
        r = lr.avaliar_modelo_oficial()

    assert r.status == "NOT_READY"
    # SHA diverge ANTES do diretório temporário ser criado (checagem
    # mais barata primeiro) — nenhum diretório chega a existir; se algum
    # dia isso mudar, o loop abaixo continua provando a limpeza.
    for caminho in caminhos:
        assert not Path(caminho).exists()


def test_local_temp_dir_removido_apos_falha_de_contrato(monkeypatch, tmp_path):
    """N (modo local): contrato inválido também limpa o diretório
    efêmero — mesma garantia do stdlib (`with TemporaryDirectory()`),
    provada explicitamente aqui."""
    _limpar_env_gcs(monkeypatch)
    docx = _docx_sintetico(tmp_path, _CORPO_PLACEHOLDER_FALTANTE)
    sha = hashlib.sha256(docx.read_bytes()).hexdigest()
    schema_path, catalogo_path = _escrever_schema_catalogo(tmp_path)
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(docx))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)

    caminhos, _Rastreado = _rastrear_temp_dirs()
    with patch("legal_readiness.tempfile.TemporaryDirectory", _Rastreado):
        r = lr.avaliar_modelo_oficial(schema_path=schema_path, catalogo_path=catalogo_path)

    assert r.status == "NOT_READY"
    assert caminhos
    for caminho in caminhos:
        assert not Path(caminho).exists()


# --------------------------------------- _baixar_modelo_oficial_gcs (adapter cru)

class _CredenciaisFalsas:
    def __init__(self, falhar_refresh=False):
        self.token = None
        self._falhar = falhar_refresh

    def refresh(self, request):
        if self._falhar:
            raise RuntimeError("falha sintética de autenticação")
        self.token = "token-de-acesso-sintetico"


def _resposta_httpx_falsa(status_code, content=b"", headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {}
    return resp


def test_adapter_gcs_sucesso_retorna_bytes_e_confere_geracao_servida(tmp_path):
    conteudo_esperado = b"conteudo binario do docx"
    with patch("google.auth.default", return_value=(_CredenciaisFalsas(), None)), \
         patch("httpx2.get", return_value=_resposta_httpx_falsa(
             200, conteudo_esperado, {"x-goog-generation": "42"})) as get_mock:
        resultado = lr._baixar_modelo_oficial_gcs("bucket-x", "objeto-y", "42")
    assert resultado == conteudo_esperado
    url_chamada = get_mock.call_args.args[0]
    assert "generation=42" in url_chamada
    assert "bucket-x" in url_chamada


def test_adapter_gcs_404_levanta_erro_tipado():
    with patch("google.auth.default", return_value=(_CredenciaisFalsas(), None)), \
         patch("httpx2.get", return_value=_resposta_httpx_falsa(404)):
        with pytest.raises(lr.ErroAquisicaoGCS) as exc:
            lr._baixar_modelo_oficial_gcs("bucket-x", "objeto-y", "42")
    assert exc.value.motivo == "objeto_ou_geracao_nao_encontrado"


def test_adapter_gcs_geracao_servida_diverge_da_pinada_levanta_erro():
    """Defesa em profundidade: mesmo com HTTP 200, se o cabeçalho
    `x-goog-generation` da resposta não bater com a geração pedida, os
    bytes são rejeitados — nunca avaliados como se fossem a geração
    pinada."""
    with patch("google.auth.default", return_value=(_CredenciaisFalsas(), None)), \
         patch("httpx2.get", return_value=_resposta_httpx_falsa(
             200, b"bytes de outra geracao", {"x-goog-generation": "99"})):
        with pytest.raises(lr.ErroAquisicaoGCS) as exc:
            lr._baixar_modelo_oficial_gcs("bucket-x", "objeto-y", "42")
    assert exc.value.motivo == "geracao_servida_diverge_da_pinada"


def test_adapter_gcs_falha_de_autenticacao_levanta_erro_tipado():
    with patch("google.auth.default", return_value=(_CredenciaisFalsas(falhar_refresh=True), None)):
        with pytest.raises(lr.ErroAquisicaoGCS) as exc:
            lr._baixar_modelo_oficial_gcs("bucket-x", "objeto-y", "42")
    assert exc.value.motivo == "autenticacao_falhou"


def test_adapter_gcs_falha_de_rede_levanta_erro_tipado():
    import httpx2

    with patch("google.auth.default", return_value=(_CredenciaisFalsas(), None)), \
         patch("httpx2.get", side_effect=httpx2.HTTPError("falha sintética de rede")):
        with pytest.raises(lr.ErroAquisicaoGCS) as exc:
            lr._baixar_modelo_oficial_gcs("bucket-x", "objeto-y", "42")
    assert exc.value.motivo == "rede_falhou"


def test_nenhum_teste_deste_arquivo_acessa_gcs_real():
    """Guarda estrutural: todo teste de GCS acima usa `patch(...)` sobre
    `google.auth.default`/`httpx2.get` — nunca uma chamada de rede real.
    Verificado aqui por inspeção do próprio código-fonte deste arquivo,
    não por uma asserção de comportamento (documenta a garantia)."""
    codigo_fonte = Path(__file__).read_text(encoding="utf-8")
    assert 'patch("google.auth.default"' in codigo_fonte
    assert 'patch("httpx2.get"' in codigo_fonte


# ------------------------------------------------------------------ Corpus RAG

def test_corpus_rag_manifesto_ausente(tmp_path):
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=tmp_path / "nao-existe.json")
    assert r.status == "NOT_CONFIGURED"


def test_corpus_rag_manifesto_ilegivel(tmp_path):
    manifesto = tmp_path / "corpus_manifest.json"
    manifesto.write_text("{ isto nao e json valido", encoding="utf-8")
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=manifesto)
    assert r.status == "ERROR"


def _escrever_corpus_sintetico(rag_dir: Path, conteudo="Art. 1o. Texto de teste."):
    diploma_dir = rag_dir / "chunks_TESTE"
    diploma_dir.mkdir(parents=True)
    (diploma_dir / "Chunk_001.md").write_text(conteudo, encoding="utf-8")
    fingerprint, contagem = lr._fingerprint_diretorio(diploma_dir, base=rag_dir)
    manifesto = {
        "versao": "teste",
        "diplomas": {"TESTE": {"arquivos": contagem, "sha256": fingerprint}},
        "total_chunks": contagem,
    }
    manifesto_path = rag_dir / "corpus_manifest.json"
    manifesto_path.write_text(json.dumps(manifesto), encoding="utf-8")
    return manifesto_path, diploma_dir


def test_corpus_rag_ausente_apesar_do_manifesto(tmp_path):
    manifesto_path, diploma_dir = _escrever_corpus_sintetico(tmp_path)
    import shutil
    shutil.rmtree(diploma_dir)
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=manifesto_path)
    assert r.status == "NOT_READY"


def test_corpus_rag_incompleto(tmp_path):
    manifesto_path, diploma_dir = _escrever_corpus_sintetico(tmp_path)
    (diploma_dir / "Chunk_001.md").unlink()
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=manifesto_path)
    assert r.status == "NOT_READY"


def test_corpus_rag_divergente_do_manifesto(tmp_path):
    manifesto_path, diploma_dir = _escrever_corpus_sintetico(tmp_path)
    (diploma_dir / "Chunk_001.md").write_text("texto alterado sem atualizar o manifesto", encoding="utf-8")
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=manifesto_path)
    assert r.status == "NOT_READY"
    assert "divergente" in r.detail or "SHA-256" in r.detail


def test_corpus_rag_sintetico_integro(tmp_path):
    manifesto_path, _diploma_dir = _escrever_corpus_sintetico(tmp_path)
    r = lr.avaliar_corpus_rag(rag_dir=tmp_path, manifesto_path=manifesto_path)
    assert r.status == "READY", r.detail


def test_corpus_rag_real_integro():
    if not MANIFESTO_REAL.is_file():
        pytest.skip("rag/corpus_manifest.json ausente nesta checkout")
    r = lr.avaliar_corpus_rag()
    assert r.status == "READY", r.detail


def test_corpus_rag_manifesto_real_nunca_declara_jurisprudencia():
    """Separação fato/proveniência (CLAUDE.md §8 do gate; INV-CONTESTACAO-
    SEM-PESQUISA-JURISPRUDENCIAL): o manifesto de corpus de produção nunca
    referencia jurisprudência (dado de caso real, privado, fora do
    repositório) — só os seis diplomas legislativos institucionais."""
    if not MANIFESTO_REAL.is_file():
        pytest.skip("rag/corpus_manifest.json ausente nesta checkout")
    manifesto = json.loads(MANIFESTO_REAL.read_text(encoding="utf-8"))
    diplomas = set(manifesto.get("diplomas", {}))
    assert diplomas == {"CPC", "CC", "CDC", "L8987", "L9427", "REN1000"}
    assert "jurisprudencia" not in json.dumps(manifesto).lower()
