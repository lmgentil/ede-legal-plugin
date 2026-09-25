#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_datajud_client.py — regressão de scripts/datajud_client.py
(INV-JUIZO-DATAJUD).

Nunca depende da disponibilidade real da API DataJud/CNJ nem da API do
IBGE — todas as respostas HTTP são mockadas via monkeypatch de
`datajud_client._post_json`/`_get_json` (funções internas já isoladas
para isso). Um teste de integração real, isolado e controlado, roda à
parte (ver relatório da correção) — não faz parte desta suíte.

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.
"""
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import datajud_client as dj  # noqa: E402


def _cache_tmp():
    return Path(tempfile.mkdtemp()) / "cache.json"


class _RespostaFalsa:
    """Substitui datajud_client._post_json/_get_json durante o teste."""

    def __init__(self, resposta_datajud=None, resposta_ibge=None, erro=None):
        self.resposta_datajud = resposta_datajud
        self.resposta_ibge = resposta_ibge
        self.erro = erro
        self.chamadas_datajud = 0
        self.chamadas_ibge = 0

    def post(self, url, body, headers, timeout, tentativas, nome_servico):
        self.chamadas_datajud += 1
        if self.erro:
            raise self.erro
        return self.resposta_datajud

    def get(self, url, timeout, tentativas, nome_servico):
        self.chamadas_ibge += 1
        return self.resposta_ibge


def _instalar(fake: _RespostaFalsa):
    original_post, original_get = dj._post_json, dj._get_json
    dj._post_json = fake.post
    dj._get_json = fake.get
    return (original_post, original_get)


def _restaurar(originais):
    dj._post_json, dj._get_json = originais


_RESPOSTA_TJBA_OK = {
    "hits": {
        "total": {"value": 1},
        "hits": [{"_source": {
            "numeroProcesso": "80000991120268050080",
            "tribunal": "TJBA",
            "orgaoJulgador": {
                "nome": "2ª VARA DE FEITOS DE REL DE CONS. CÍVEL E COMERCIAIS",
                "codigo": 50076,
                "codigoMunicipioIBGE": 2932903,
            },
        }}],
    }
}
_RESPOSTA_IBGE_VALENCA = {"id": 2932903, "nome": "Valença"}


# A. processo TJBA válido -> alias correto.
def test_A_processo_tjba_valido_alias_correto():
    numero = dj.normalizar_numero_processo("8000099-11.2026.8.05.0080")
    assert dj.identificar_alias(numero) == "api_publica_tjba"


# B. número com pontuação -> normalização correta.
def test_B_numero_com_pontuacao_normalizado():
    assert dj.normalizar_numero_processo("8000099-11.2026.8.05.0080") == "80000991120268050080"


# C. número sem pontuação -> aceito.
def test_C_numero_sem_pontuacao_aceito():
    assert dj.normalizar_numero_processo("80000991120268050080") == "80000991120268050080"


# D. órgão julgador retornado -> {{JUIZO}} correto.
def test_D_orgao_julgador_retornado_juizo_correto():
    fake = _RespostaFalsa(resposta_datajud=_RESPOSTA_TJBA_OK, resposta_ibge=_RESPOSTA_IBGE_VALENCA)
    originais = _instalar(fake)
    try:
        r = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="chave-de-teste", cache_path=_cache_tmp())
    finally:
        _restaurar(originais)
    assert r["tribunal"] == "TJBA"
    assert r["orgao_julgador_nome"] == "2ª VARA DE FEITOS DE REL DE CONS. CÍVEL E COMERCIAIS"
    assert r["comarca"] == "Valença"
    assert r["juizo"] == "AO JUÍZO DA 2ª VARA DE FEITOS DE REL DE CONS. CÍVEL E COMERCIAIS DA COMARCA DE VALENÇA"


# E. caixa alta -> obrigatório.
def test_E_juizo_final_sempre_em_caixa_alta():
    resposta = {
        "hits": {"total": {"value": 1}, "hits": [{"_source": {
            "tribunal": "tjba",
            "orgaoJulgador": {"nome": "vara cível de teste", "codigo": 1, "codigoMunicipioIBGE": 1},
        }}]},
    }
    fake = _RespostaFalsa(resposta_datajud=resposta, resposta_ibge={"nome": "salvador"})
    originais = _instalar(fake)
    try:
        r = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
    finally:
        _restaurar(originais)
    assert r["juizo"] == "AO JUÍZO DA VARA CÍVEL DE TESTE DA COMARCA DE SALVADOR"
    assert r["juizo"] == r["juizo"].upper()


# F. DataJud indisponível -> fail-closed.
def test_F_datajud_indisponivel_fail_closed():
    # simula o que _post_json já faz internamente após esgotar as
    # tentativas de retry em falha transitória (URLError/timeout/5xx).
    fake = _RespostaFalsa(erro=dj.JuizoResolutionError("DataJud indisponível após 3 tentativa(s): simulado"))
    originais = _instalar(fake)
    try:
        try:
            dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "DataJud" in e.motivo or "indisponível" in e.motivo.lower() or "simulado" in e.motivo
    finally:
        _restaurar(originais)


# erro de autenticação (chave inválida/expirada) é marcado com
# TAG_ERRO_AUTENTICACAO e nunca degrada para um JUIZO parcial/inventado.
def test_erro_de_autenticacao_marcado_e_nunca_degrada():
    fake = _RespostaFalsa(erro=dj.JuizoResolutionError(
        "DataJud rejeitou a credencial (HTTP 401: Unauthorized).", codigo=dj.TAG_ERRO_AUTENTICACAO))
    originais = _instalar(fake)
    try:
        try:
            resultado = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
            assert False, f"deveria ter levantado JuizoResolutionError, retornou: {resultado!r}"
        except dj.JuizoResolutionError as e:
            assert e.codigo == dj.TAG_ERRO_AUTENTICACAO
    finally:
        _restaurar(originais)


# G. processo inexistente -> fail-closed.
def test_G_processo_inexistente_fail_closed():
    resposta_vazia = {"hits": {"total": {"value": 0}, "hits": []}}
    fake = _RespostaFalsa(resposta_datajud=resposta_vazia)
    originais = _instalar(fake)
    try:
        try:
            dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "não encontrado" in e.motivo
    finally:
        _restaurar(originais)


# H. resposta sem órgão julgador -> fail-closed.
def test_H_resposta_sem_orgao_julgador_fail_closed():
    resposta = {"hits": {"total": {"value": 1}, "hits": [{"_source": {
        "tribunal": "TJBA", "orgaoJulgador": {},
    }}]}}
    fake = _RespostaFalsa(resposta_datajud=resposta)
    originais = _instalar(fake)
    try:
        try:
            dj.resolver_orgao_julgador("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "órgão julgador" in e.motivo
    finally:
        _restaurar(originais)


# I. múltiplos resultados incompatíveis -> fail-closed.
def test_I_multiplos_resultados_incompativeis_fail_closed():
    resposta = {"hits": {"total": {"value": 2}, "hits": [
        {"_source": {"tribunal": "TJBA", "orgaoJulgador": {"nome": "VARA A", "codigo": 1, "codigoMunicipioIBGE": 1}}},
        {"_source": {"tribunal": "TJBA", "orgaoJulgador": {"nome": "VARA B", "codigo": 2, "codigoMunicipioIBGE": 2}}},
    ]}}
    fake = _RespostaFalsa(resposta_datajud=resposta)
    originais = _instalar(fake)
    try:
        try:
            dj.resolver_orgao_julgador("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "múltiplos resultados" in e.motivo or "incompatíveis" in e.motivo
    finally:
        _restaurar(originais)


def test_I_multiplos_resultados_identicos_nao_e_erro():
    # dois hits, mesmo orgaoJulgador -> não é ambiguidade real.
    org = {"nome": "VARA A", "codigo": 1, "codigoMunicipioIBGE": 2932903}
    resposta = {"hits": {"total": {"value": 2}, "hits": [
        {"_source": {"tribunal": "TJBA", "orgaoJulgador": dict(org)}},
        {"_source": {"tribunal": "TJBA", "orgaoJulgador": dict(org)}},
    ]}}
    fake = _RespostaFalsa(resposta_datajud=resposta, resposta_ibge=_RESPOSTA_IBGE_VALENCA)
    originais = _instalar(fake)
    try:
        r = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
        assert r["orgao_julgador_nome"] == "VARA A"
    finally:
        _restaurar(originais)


# K. cache evita nova chamada para o mesmo processo.
def test_K_cache_evita_nova_chamada():
    fake = _RespostaFalsa(resposta_datajud=_RESPOSTA_TJBA_OK, resposta_ibge=_RESPOSTA_IBGE_VALENCA)
    originais = _instalar(fake)
    cache_path = _cache_tmp()
    try:
        r1 = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=cache_path)
        assert fake.chamadas_datajud == 1 and fake.chamadas_ibge == 1
        r2 = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=cache_path)
        assert fake.chamadas_datajud == 1 and fake.chamadas_ibge == 1  # sem nova chamada
        assert r1["juizo"] == r2["juizo"]
    finally:
        _restaurar(originais)


def test_K_cache_funciona_sem_api_key_apos_primeira_resolucao():
    fake = _RespostaFalsa(resposta_datajud=_RESPOSTA_TJBA_OK, resposta_ibge=_RESPOSTA_IBGE_VALENCA)
    originais = _instalar(fake)
    cache_path = _cache_tmp()
    try:
        dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=cache_path)
        # segunda chamada, SEM api_key -> deve vir do cache, não falhar por
        # falta de credencial.
        r2 = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key=None, cache_path=cache_path)
        assert r2["comarca"] == "Valença"
    finally:
        _restaurar(originais)


# fail-closed adicional: sem DATAJUD_API_KEY (nem argumento, nem ambiente) -> erro claro.
# Etapa 5.5: sem DATAJUD_API_KEY no ambiente (nem api_key explícito), o
# cliente usa a chave canônica versionada (DATAJUD_API_KEY_PADRAO)
# automaticamente — plugin autossuficiente, sem configuração manual.
def test_sem_datajud_api_key_no_ambiente_usa_chave_canonica_automaticamente():
    import os
    valor_original = os.environ.pop("DATAJUD_API_KEY", None)
    fake = _RespostaFalsa(resposta_datajud=_RESPOSTA_TJBA_OK, resposta_ibge=_RESPOSTA_IBGE_VALENCA)
    originais = _instalar(fake)
    try:
        r = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key=None, cache_path=_cache_tmp())
        assert r["comarca"] == "Valença"
    finally:
        _restaurar(originais)
        if valor_original is not None:
            os.environ["DATAJUD_API_KEY"] = valor_original


# ausência da chave canônica (e de qualquer override) continua fail-closed
# — coberto em detalhe por tests/test_pacote_distribuicao.py (teste D),
# checagem direta aqui também por completude do módulo.
def test_ausencia_total_de_chave_fail_closed():
    original = dj.DATAJUD_API_KEY_PADRAO
    dj.DATAJUD_API_KEY_PADRAO = ""
    try:
        try:
            dj.resolver_orgao_julgador("8000099-11.2026.8.05.0080", api_key=None, cache_path=_cache_tmp())
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "chave" in e.motivo.lower()
    finally:
        dj.DATAJUD_API_KEY_PADRAO = original


# fail-closed: segmento de justiça não suportado.
def test_segmento_nao_suportado_fail_closed():
    numero = dj.normalizar_numero_processo("0000123-45.2024.5.02.0000")  # segmento 5 = Trabalho
    try:
        dj.identificar_alias(numero)
        assert False, "deveria ter levantado JuizoResolutionError"
    except dj.JuizoResolutionError as e:
        assert "segmento" in e.motivo.lower()


# Política 0.17.1 (pós-smoke da ADR-0021): UMA requisição por consulta,
# conexão 5 s, leitura 65 s, nenhum retry. 429/5xx/timeout/conexão =
# indisponibilidade (TAG_INDISPONIVEL, abre o fallback humano no
# finalizador); 401/403 e demais 4xx = falha definitiva. Todos os testes
# substituem `_abrir_url`, o único ponto de rede do módulo: nenhum chega
# à API real nem ao DNS.

class _Resposta:
    def __init__(self, corpo: bytes):
        self._corpo = corpo
        self.headers = {}

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _com_abrir(fake):
    original = dj._abrir_url
    dj._abrir_url = fake
    return original


def _erro_http(codigo):
    import urllib.error
    return urllib.error.HTTPError("https://x", codigo, "simulado", {}, None)


def test_politica_de_limites_e_uma_tentativa():
    assert dj._TIMEOUT_CONEXAO_PADRAO == 5
    assert dj._TIMEOUT_PADRAO == 65
    assert dj._TENTATIVAS_PADRAO == 1


def test_A_resposta_lenta_dentro_de_65s_e_aceita_sem_fallback():
    """Resposta que chega depois de 10 s (latência real observada: 21 a
    57 s) é aceita: o socket só desiste depois do limite de leitura."""
    chamadas = []

    def abrir(req, timeout_conexao, timeout_leitura):
        chamadas.append((timeout_conexao, timeout_leitura))
        assert timeout_leitura > 57  # maior latência útil medida
        return _Resposta(b'{"ok": true}')
    original = _com_abrir(abrir)
    try:
        assert dj._get_json("https://x/y", timeout=dj._TIMEOUT_PADRAO, tentativas=3, nome_servico="T") == {"ok": True}
    finally:
        dj._abrir_url = original
    assert chamadas == [(5, 65)]


def test_B_timeout_de_leitura_vira_indisponibilidade_sem_segunda_chamada():
    chamadas = []

    def abrir(req, timeout_conexao, timeout_leitura):
        chamadas.append(1)
        raise TimeoutError("The read operation timed out")
    original = _com_abrir(abrir)
    try:
        try:
            dj._get_json("https://x/y", timeout=65, tentativas=3, nome_servico="T")
            assert False, "deveria ter levantado"
        except dj.JuizoResolutionError as e:
            assert e.codigo == dj.TAG_INDISPONIVEL
    finally:
        dj._abrir_url = original
    assert len(chamadas) == 1  # mesmo pedindo 3 tentativas: nenhum retry


def test_C_429_vira_indisponibilidade_sem_segunda_chamada():
    chamadas = []

    def abrir(req, timeout_conexao, timeout_leitura):
        chamadas.append(1)
        raise _erro_http(429)
    original = _com_abrir(abrir)
    try:
        try:
            dj._post_json("https://x/y", {}, {}, 65, 3, "DataJud")
            assert False, "deveria ter levantado"
        except dj.JuizoResolutionError as e:
            assert e.codigo == dj.TAG_INDISPONIVEL and "429" in e.motivo
    finally:
        dj._abrir_url = original
    assert len(chamadas) == 1


def test_D_5xx_vira_indisponibilidade_sem_segunda_chamada():
    for codigo in (500, 502, 503, 504):
        chamadas = []

        def abrir(req, timeout_conexao, timeout_leitura):
            chamadas.append(1)
            raise _erro_http(codigo)
        original = _com_abrir(abrir)
        try:
            try:
                dj._post_json("https://x/y", {}, {}, 65, 3, "DataJud")
                assert False, "deveria ter levantado"
            except dj.JuizoResolutionError as e:
                assert e.codigo == dj.TAG_INDISPONIVEL and str(codigo) in e.motivo
        finally:
            dj._abrir_url = original
        assert len(chamadas) == 1, codigo


def test_D2_erro_de_conexao_vira_indisponibilidade_sem_segunda_chamada():
    import urllib.error
    chamadas = []

    def abrir(req, timeout_conexao, timeout_leitura):
        chamadas.append(1)
        raise urllib.error.URLError("conexão simulada")
    original = _com_abrir(abrir)
    try:
        try:
            dj._get_json("https://x/y", timeout=65, tentativas=3, nome_servico="T")
            assert False, "deveria ter levantado"
        except dj.JuizoResolutionError as e:
            assert e.codigo == dj.TAG_INDISPONIVEL
    finally:
        dj._abrir_url = original
    assert len(chamadas) == 1


def test_E_200_faz_uma_unica_chamada_por_servico():
    """Resolução completa: exatamente uma chamada ao DataJud e uma ao IBGE."""
    urls = []
    resposta_dj = (b'{"hits": {"total": {"value": 1}, "hits": [{"_source": {"tribunal": "TJBA", '
                   b'"orgaoJulgador": {"nome": "VARA DE TESTE", "codigo": 1, "codigoMunicipioIBGE": 2927408}}}]}}')

    def abrir(req, timeout_conexao, timeout_leitura):
        urls.append(req.full_url)
        return _Resposta(resposta_dj if "datajud" in req.full_url else b'{"nome": "Salvador"}')
    original = _com_abrir(abrir)
    try:
        r = dj.resolver_juizo("8000099-11.2026.8.05.0080", api_key="x", cache_path=_cache_tmp())
    finally:
        dj._abrir_url = original
    assert r["juizo"] == "AO JUÍZO DA VARA DE TESTE DA COMARCA DE SALVADOR"
    assert len(urls) == 2
    assert sum("datajud" in u for u in urls) == 1 and sum("ibge" in u for u in urls) == 1


def test_4xx_e_credencial_continuam_falha_definitiva_sem_segunda_chamada():
    for codigo, tag in ((404, None), (400, None), (401, dj.TAG_ERRO_AUTENTICACAO), (403, dj.TAG_ERRO_AUTENTICACAO)):
        chamadas = []

        def abrir(req, timeout_conexao, timeout_leitura):
            chamadas.append(1)
            raise _erro_http(codigo)
        original = _com_abrir(abrir)
        try:
            try:
                dj._get_json("https://x/y", timeout=65, tentativas=3, nome_servico="T")
                assert False, "deveria ter levantado"
            except dj.JuizoResolutionError as e:
                assert e.codigo == tag and e.codigo != dj.TAG_INDISPONIVEL
        finally:
            dj._abrir_url = original
        assert len(chamadas) == 1, codigo


def test_conexao_aplica_limite_de_leitura_depois_de_conectar():
    """Limites separados de verdade: o construtor recebe o de conexão (5 s)
    e, conectado o socket, passa a valer o de leitura (65 s)."""
    import http.client

    class _Sock:
        def __init__(self):
            self.timeouts = []

        def settimeout(self, t):
            self.timeouts.append(t)

    def connect_falso(self):
        self.sock = _Sock()
    original = http.client.HTTPSConnection.connect
    http.client.HTTPSConnection.connect = connect_falso
    try:
        c = dj._ConexaoHTTPS("exemplo.invalido", timeout=5, timeout_leitura=65)
        assert c.timeout == 5
        c.connect()
        assert c.sock.timeouts == [65]
    finally:
        http.client.HTTPSConnection.connect = original


def test_F_nenhum_outro_ponto_de_rede_no_modulo():
    """A suíte só consegue garantir que não toca a API real se `_abrir_url`
    for o único caminho de rede: nenhum urlopen/socket direto no módulo."""
    fonte = (BASE / "scripts" / "datajud_client.py").read_text(encoding="utf-8")
    assert fonte.count("urllib.request.urlopen(") == 0
    assert "opener.open(" in fonte and fonte.count(".open(req") == 1


# fail-closed: número CNJ malformado (não 20 dígitos).
def test_numero_malformado_fail_closed():
    try:
        dj.normalizar_numero_processo("123-45")
        assert False, "deveria ter levantado JuizoResolutionError"
    except dj.JuizoResolutionError as e:
        assert "20 dígitos" in e.motivo


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
