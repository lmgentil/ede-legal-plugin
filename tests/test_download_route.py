#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_download_route.py — rota pública `/download/<token>` (Gate 6.6-F/G,
ADR-0019, DELIVERY-CLIENT-01).

Exercita a app ASGI REAL (`server.construir_app_http`, a mesma que
`main()` serve com OAuth ligado), com armazenamento em memória injetado
no ponto único do Core (`artifact_storage.obter_transporte_do_ambiente`)
— nenhuma rede. Cobre o contrato aprovado: query string ignorada
(inclusive `?utm_source=chatgpt.com`), 404 uniforme, SHA divergente ->
5xx sem bytes, hard delete -> 404, cabeçalhos exigidos, exceção de
autenticação explícita e restrita (`/mcp` continua 401 sem OAuth), e
nenhuma ocorrência do token em log/telemetria/stdout/stderr."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
for caminho in (str(BASE / "mcp_server"), str(BASE / "scripts"), str(BASE / "tests")):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

import oauth_harness as h  # noqa: E402
import server as ede  # noqa: E402
import artifact_storage as ast  # noqa: E402
import auth_logging as telemetria  # noqa: E402
import http_telemetry  # noqa: E402
from token_verifier import EdeTokenVerifier  # noqa: E402

DOCX = b"PK\x03\x04" + b"conteudo sintetico de teste, nunca um DOCX real " * 200
SHA = hashlib.sha256(DOCX).hexdigest()
FILENAME = "EDE-Contestacao-Irregularidade.docx"

CABECALHOS_EXIGIDOS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


class _Armazenamento:
    """Fake em memória com gerações (mesmo contrato de TransporteArtefato)."""

    def __init__(self):
        self.objetos = {}
        self.falhar = False
        self._geracao = 0

    def enviar(self, nome, dados, content_type, metadata):
        self._geracao += 1
        self.objetos[nome] = (dados, content_type, dict(metadata), str(self._geracao))

    def obter_metadado(self, nome):
        if self.falhar:
            raise ast.ErroArmazenamentoArtefato("rede_falhou")
        if nome not in self.objetos:
            return None
        _, content_type, metadata, geracao = self.objetos[nome]
        return dict(metadata), geracao, content_type

    def baixar(self, nome, geracao):
        if nome not in self.objetos:
            return None
        dados, _, _, g = self.objetos[nome]
        return dados if g == geracao else None

    def excluir(self, nome):
        self.objetos.pop(nome, None)
        return True

    def listar(self, prefixo, limite):
        nomes = sorted(n for n in self.objetos if n.startswith(prefixo))[:limite]
        return [(n, self.objetos[n][2]) for n in nomes]


@pytest.fixture
def armazenamento(monkeypatch):
    fake = _Armazenamento()
    monkeypatch.setattr(ast, "obter_transporte_do_ambiente", lambda env: fake)
    return fake


@asynccontextmanager
async def _app():
    config = h.config_canonica()
    async with h.cliente_jwks(h.AppJwks()) as cliente:
        verificador = EdeTokenVerifier(config, cliente_http=cliente)
        app = ede.construir_app_http(ede.criar_servidor(config, verificador), config)
        async with h.ciclo_de_vida(app):
            async with h.cliente_mcp(app, config) as http:
                yield http, config


def _publicar(armazenamento, config):
    entrega = ast.entregar_artefato_efemero(
        DOCX, SHA, FILENAME, armazenamento, base_url=f"https://{config.canonical_host}",
    )
    caminho = entrega.download_url[len(f"https://{config.canonical_host}"):]
    token = caminho[len("/download/"):]
    return entrega, caminho, token


def _metadado(armazenamento, entrega):
    return armazenamento.objetos[f"artifacts/{entrega.artefato_id}.docx"][2]


def _assert_docx_ok(resposta):
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == ast.CONTENT_TYPE_DOCX
    assert resposta.headers["content-disposition"] == f'attachment; filename="{FILENAME}"'
    for chave, valor in CABECALHOS_EXIGIDOS.items():
        assert resposta.headers[chave] == valor
    assert hashlib.sha256(resposta.content).hexdigest() == SHA
    assert resposta.content == DOCX


# ================================================================ entrega

@pytest.mark.anyio
async def test_get_entrega_docx_com_cabecalhos_exigidos(armazenamento):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        resposta = await http.get(caminho)
    _assert_docx_ok(resposta)
    assert resposta.headers["content-length"] == str(len(DOCX))


@pytest.mark.anyio
async def test_utm_source_chatgpt_entrega_exatamente_os_mesmos_bytes(armazenamento):
    """DELIVERY-CLIENT-01 — prova obrigatória do gate."""
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        puro = await http.get(caminho)
        com_utm = await http.get(f"{caminho}?utm_source=chatgpt.com")
    _assert_docx_ok(puro)
    _assert_docx_ok(com_utm)
    assert com_utm.content == puro.content


@pytest.mark.anyio
@pytest.mark.parametrize("query", [
    "?utm_source=chatgpt.com&utm_medium=referral&utm_campaign=x",
    "?a=1&b=2&c=3&a=4",
    "?X-Goog-Signature=deadbeef&X-Goog-Expires=1",
    "?next=%2Fdownload%2Foutro&v=%E2%9C%93&q=a%26b%3Dc",
    "?",
    "?%00=%FF",
])
async def test_query_params_arbitrarios_e_codificados_sao_ignorados(armazenamento, query):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        resposta = await http.get(f"{caminho}{query}")
    _assert_docx_ok(resposta)


@pytest.mark.anyio
async def test_mesmo_token_baixado_mais_de_uma_vez(armazenamento):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        respostas = [await http.get(caminho) for _ in range(3)]
    for resposta in respostas:
        _assert_docx_ok(resposta)


@pytest.mark.anyio
async def test_head_devolve_cabecalhos_sem_corpo(armazenamento):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        resposta = await http.head(f"{caminho}?utm_source=chatgpt.com")
    assert resposta.status_code == 200
    assert resposta.content == b""
    assert resposta.headers["content-type"] == ast.CONTENT_TYPE_DOCX
    assert resposta.headers["content-disposition"] == f'attachment; filename="{FILENAME}"'
    assert resposta.headers["content-length"] == str(len(DOCX))
    for chave, valor in CABECALHOS_EXIGIDOS.items():
        assert resposta.headers[chave] == valor


@pytest.mark.anyio
async def test_authorization_invalido_nao_interfere_no_download(armazenamento):
    """A rota não consulta OAuth: um Bearer lixo não vira 401 nem 400."""
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        resposta = await http.get(caminho, headers={"Authorization": "Bearer lixo"})
    _assert_docx_ok(resposta)


# ================================================================ 404 uniforme

async def _respostas_404(http, armazenamento, config):
    """Uma resposta por cenário de recusa — todas precisam ser idênticas."""
    respostas = {}

    entrega, caminho, token = _publicar(armazenamento, config)
    respostas["caractere_invalido"] = await http.get(f"/download/{token[:-1]}%21")
    respostas["truncado"] = await http.get(f"/download/{token[:-1]}")
    respostas["longo"] = await http.get(f"/download/{token}a")
    respostas["segmento_extra"] = await http.get(f"{caminho}/x")
    respostas["barra_final"] = await http.get(f"{caminho}/")
    respostas["vazio"] = await http.get("/download/")
    respostas["inexistente"] = await http.get(f"/download/{ast._novo_token()}")

    entrega, caminho, _ = _publicar(armazenamento, config)
    meta = _metadado(armazenamento, entrega)
    passado = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    meta["created_at"] = (passado - dt.timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["expires_at"] = passado.strftime("%Y-%m-%dT%H:%M:%SZ")
    respostas["expirado"] = await http.get(caminho)

    entrega, caminho, _ = _publicar(armazenamento, config)
    _metadado(armazenamento, entrega).clear()
    respostas["metadado_ausente"] = await http.get(caminho)

    entrega, caminho, _ = _publicar(armazenamento, config)
    _metadado(armazenamento, entrega)["expires_at"] = "amanha"
    respostas["metadado_malformado"] = await http.get(caminho)

    entrega, caminho, _ = _publicar(armazenamento, config)
    armazenamento.excluir(f"artifacts/{entrega.artefato_id}.docx")
    respostas["objeto_excluido"] = await http.get(caminho)
    return respostas


@pytest.mark.anyio
async def test_toda_recusa_e_o_mesmo_404_uniforme(armazenamento):
    async with _app() as (http, config):
        respostas = await _respostas_404(http, armazenamento, config)
    assinaturas = set()
    for cenario, resposta in respostas.items():
        assert resposta.status_code == 404, cenario
        assert "content-disposition" not in resposta.headers, cenario
        assert DOCX[:40] not in resposta.content, cenario
        assinaturas.add((resposta.content, resposta.headers["content-type"],
                         resposta.headers.get("cache-control"), resposta.headers.get("x-content-type-options"),
                         resposta.headers.get("referrer-policy")))
    assert len(assinaturas) == 1, assinaturas


@pytest.mark.anyio
async def test_hard_delete_pela_limpeza_faz_o_download_falhar(armazenamento):
    async with _app() as (http, config):
        entrega, caminho, _ = _publicar(armazenamento, config)
        _assert_docx_ok(await http.get(caminho))
        depois = ast._ler_data(entrega.expires_at) + dt.timedelta(seconds=1)
        assert ast.limpar_artefatos_elegiveis(armazenamento, agora=depois)["excluidos"] == 1
        assert armazenamento.objetos == {}
        resposta = await http.get(caminho)
    assert resposta.status_code == 404


@pytest.mark.anyio
async def test_sha_divergente_e_5xx_sem_nenhum_byte_do_documento(armazenamento):
    async with _app() as (http, config):
        entrega, caminho, _ = _publicar(armazenamento, config)
        nome = f"artifacts/{entrega.artefato_id}.docx"
        _, ct, meta, g = armazenamento.objetos[nome]
        adulterado = DOCX[:-1] + b"X"
        armazenamento.objetos[nome] = (adulterado, ct, meta, g)
        resposta = await http.get(caminho)
    assert resposta.status_code == 500
    assert resposta.content == b"Internal Server Error"
    assert "content-disposition" not in resposta.headers
    assert resposta.headers["content-type"].startswith("text/plain")
    assert b"PK" not in resposta.content and SHA.encode() not in resposta.content


@pytest.mark.anyio
async def test_armazenamento_indisponivel_e_503(armazenamento):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        armazenamento.falhar = True
        resposta = await http.get(caminho)
    assert resposta.status_code == 503
    assert "content-disposition" not in resposta.headers


@pytest.mark.anyio
async def test_metodo_diferente_de_get_head_e_405(armazenamento):
    async with _app() as (http, config):
        _, caminho, _ = _publicar(armazenamento, config)
        resposta = await http.post(caminho)
    assert resposta.status_code == 405
    assert resposta.headers["allow"] == "GET, HEAD"


# ================================================================ auth

@pytest.mark.anyio
async def test_mcp_sem_oauth_continua_401_com_a_rota_de_download_montada(armazenamento):
    async with _app() as (http, config):
        _publicar(armazenamento, config)
        resposta = await http.post(config.caminho_mcp, json=h.corpo_tools_list(),
                                   headers=h.CABECALHOS_JSONRPC)
    assert resposta.status_code == 401
    assert "resource_metadata" in resposta.headers.get("www-authenticate", "")


@pytest.mark.anyio
async def test_prefixo_parecido_nao_e_rota_de_download(armazenamento):
    """Só `/download/` é a exceção — `/downloadx/...` e `/download` seguem
    para a app do SDK (404 dela, nunca o handler de download)."""
    async with _app() as (http, config):
        _, _, token = _publicar(armazenamento, config)
        r1 = await http.get(f"/downloadx/{token}")
        r2 = await http.get("/download")
    for r in (r1, r2):
        assert r.status_code == 404
        assert "referrer-policy" not in r.headers  # não passou pelo handler de download


def test_validacao_de_configuracao_de_download_na_subida():
    config = h.config_canonica()
    env = ast.ENV_ARTEFATOS_DOWNLOAD_BASE_URL
    ede.validar_configuracao_download(config, {})  # ausente: nada a validar
    ede.validar_configuracao_download(config, {env: f"https://{config.canonical_host}"})
    with pytest.raises(ede.ConfiguracaoDownloadInvalida):
        ede.validar_configuracao_download(config, {env: f"https://{h.HOST_ALTERNATIVO}"})
    with pytest.raises(ede.ConfiguracaoDownloadInvalida):
        ede.validar_configuracao_download(config, {env: f"http://{config.canonical_host}"})
    with pytest.raises(ede.ConfiguracaoDownloadInvalida):
        ede.validar_configuracao_download(config, {env: f"https://{config.canonical_host}/mcp"})
    with pytest.raises(ede.ConfiguracaoDownloadInvalida):
        # sem OAuth a rota /download/ nem é montada -> link morto
        ede.validar_configuracao_download(None, {env: f"https://{config.canonical_host}"})


# ================================================================ logs

@pytest.mark.anyio
async def test_token_nunca_aparece_em_log_telemetria_stdout_ou_stderr(armazenamento, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    async with _app() as (http, config):
        entrega, caminho, token = _publicar(armazenamento, config)
        await http.get(caminho)
        await http.get(f"{caminho}?utm_source=chatgpt.com")
        await http.head(caminho)
        await http.get(f"/download/{token[:-1]}")          # malformado
        await http.post(caminho)                            # 405
        armazenamento.falhar = True
        await http.get(caminho)                             # 503
        armazenamento.falhar = False
        nome = f"artifacts/{entrega.artefato_id}.docx"
        _, ct, meta, g = armazenamento.objetos[nome]
        armazenamento.objetos[nome] = (b"PKadulterado", ct, meta, g)
        await http.get(caminho)                             # 500

    capturado = capsys.readouterr()
    textos = [capturado.out, capturado.err]
    for registro in caplog.records:
        # O `AsyncClient` DO TESTE loga a URL que ele mesmo requisitou
        # (logger httpx2, "HTTP Request: GET https://<host do EDE>/...").
        # Isso é o lado cliente, não o servidor — excluído só quando a
        # linha é uma requisição para o próprio host do EDE. Chamadas
        # httpx2 do SERVIDOR (ao GCS) continuam dentro da verificação.
        if registro.name.startswith("httpx") and f"https://{config.canonical_host}/" in registro.getMessage():
            continue
        textos.append(registro.getMessage())
        textos.append(str(registro.args))
        if registro.exc_text:
            textos.append(registro.exc_text)
    tudo = "\n".join(textos)
    assert token not in tudo
    assert token[:-1] not in tudo
    assert "utm_source" not in tudo

    eventos = [json.loads(r.getMessage()) for r in caplog.records if r.name == "ede.mcp.seguranca"]
    http_eventos = [e for e in eventos if e["evento"] == telemetria.EVENTO_REQUISICAO_HTTP
                    and e.get("caminho", "").startswith("/download")]
    assert http_eventos and all(e["caminho"] == telemetria.CAMINHO_DOWNLOAD_REDIGIDO for e in http_eventos)
    downloads = [e for e in eventos if e["evento"] == telemetria.EVENTO_DOWNLOAD_ARTEFATO]
    resultados = {e["resultado_download"] for e in downloads}
    assert resultados == {"entregue", "nao_encontrado", "indisponivel", "integridade_divergente"}
    assert all(e.get("artefato_id") in (None, entrega.artefato_id) for e in downloads)


def test_telemetria_recusa_caminho_de_download_nao_redigido():
    token = ast._novo_token()
    with pytest.raises(telemetria.CampoDeLogProibido) as exc:
        telemetria.registrar_evento(telemetria.EVENTO_REQUISICAO_HTTP, caminho=f"/download/{token}")
    assert token not in str(exc.value)
    registro = telemetria.registrar_evento(
        telemetria.EVENTO_REQUISICAO_HTTP, caminho=telemetria.CAMINHO_DOWNLOAD_REDIGIDO,
    )
    assert registro["caminho"] == "/download/<redacted>"
    assert http_telemetry.caminho_para_log(f"/download/{token}") == "/download/<redacted>"
    assert http_telemetry.caminho_para_log("/mcp") == "/mcp"


def test_vocabulario_de_download_da_telemetria_espelha_o_core():
    assert telemetria.RESULTADOS_DOWNLOAD == {
        ast.DOWNLOAD_ENTREGUE, ast.DOWNLOAD_NAO_ENCONTRADO,
        ast.DOWNLOAD_INTEGRIDADE_DIVERGENTE, ast.DOWNLOAD_INDISPONIVEL,
    }
    assert telemetria.MOTIVOS_DOWNLOAD == {
        ast.MOTIVO_TOKEN_MALFORMADO, ast.MOTIVO_OBJETO_INEXISTENTE,
        ast.MOTIVO_METADADO_INVALIDO, ast.MOTIVO_EXPIRADO,
    }
    assert telemetria.PREFIXO_CAMINHO_DOWNLOAD == ast.PREFIXO_ROTA_DOWNLOAD


def test_uvicorn_access_log_desligado_no_caminho_com_oauth():
    """O access log do uvicorn grava caminho + query — o token vazaria.
    Verificação estrutural sobre o código de subida (não sobe servidor)."""
    import inspect

    fonte = inspect.getsource(ede.main)
    assert "access_log=False" in fonte
