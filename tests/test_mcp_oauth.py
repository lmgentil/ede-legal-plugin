# -*- coding: utf-8 -*-
"""
tests/test_mcp_oauth.py — contrato executável do OAuth de aplicação do
EDE MCP Server (Gate 6.3-D2 §15/§16/§17).

Cinco camadas, todas determinísticas e sem rede:

  CONFIGURAÇÃO   — identidade canônica; fail-closed.
  JWT / JOSE     — a cadeia de verificação do token.
  ESCOPOS        — autorização separada de autenticação.
  HTTP / MCP     — contrato de erro, PRM, Host/Origin, proteção das rotas.
  TELEMETRIA     — metadado apenas; segredo nenhum.

Tudo sintético (tests/oauth_harness.py): chaves RSA geradas no processo,
JWKS servido por app ASGI em memória, issuer e Resource em domínios
`.invalid`. NENHUM segredo real do Descope, NENHUMA dependência de
internet, NENHUM socket.

PROVA DE DISPATCH ZERO
======================
Cada caso negativo compara `CONTADOR_DISPATCH` antes e depois: o corpo da
tool NUNCA executa quando a autenticação ou a autorização falha. O caso
positivo exige incremento de exatamente 1. Sem isso, "401" provaria só
que a resposta foi 401 — não que o EDE deixou de executar a operação.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
MCP_SERVER_DIR = BASE / "mcp_server"
for caminho in (str(TESTS_DIR), str(MCP_SERVER_DIR)):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

import oauth_harness as h  # noqa: E402
import server as ede  # noqa: E402
import auth_logging as telemetria  # noqa: E402
from auth_config import (  # noqa: E402
    ESCOPO_HEALTH,
    ESCOPO_LEGAL,
    NOME_SERVICO_PRODUCAO,
    VAR_K_SERVICE,
    ConfiguracaoAuthInvalida,
    EdeAuthConfig,
    ProducaoSemAuthInvalida,
    carregar_config_do_ambiente,
    separar_escopos,
)
from scope_policy import CONTADOR_DISPATCH, EscopoFerramentaMiddleware  # noqa: E402
from token_verifier import CacheJwks, EdeTokenVerifier, ErroJwks  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def dispatch_zerado():
    """Isolamento do contador entre testes — ele é global ao processo."""
    CONTADOR_DISPATCH.zerar()
    yield
    CONTADOR_DISPATCH.zerar()


# =====================================================================
# 1. CONFIGURAÇÃO
# =====================================================================

def test_configuracao_canonica_valida():
    """A configuração de referência é aceita e deriva host, caminho e uma
    única audience a partir do Resource — nunca de campos paralelos."""
    config = h.config_canonica()
    assert config.canonical_host == h.HOST_CANONICO
    assert config.caminho_mcp == "/mcp"
    assert config.accepted_audiences == (h.RESOURCE_CANONICO,)
    assert config.migracao_de_audiencia_ativa is False
    assert config.required_scopes == (ESCOPO_HEALTH,)
    assert config.clock_skew_seconds == 60


@pytest.mark.parametrize(
    "sobrescrita",
    [
        pytest.param({"canonical_resource": ""}, id="resource_ausente"),
        pytest.param({"canonical_resource": "nao-e-uma-uri"}, id="resource_malformado"),
        pytest.param(
            {
                "canonical_resource": "http://ede-mcp.example.invalid/mcp",
                "accepted_audiences": ("http://ede-mcp.example.invalid/mcp",),
            },
            id="resource_nao_https",
        ),
        pytest.param({"issuer": ""}, id="issuer_ausente"),
        pytest.param({"issuer": "ftp://x"}, id="issuer_malformado"),
        pytest.param({"jwks_uri": ""}, id="jwks_ausente"),
        pytest.param({"accepted_audiences": ()}, id="audiencias_vazias"),
        pytest.param(
            {"accepted_audiences": ("https://*.run.app/mcp",)}, id="audiencia_curinga"
        ),
        pytest.param(
            {"accepted_audiences": (h.RESOURCE_CANONICO, h.RESOURCE_CANONICO)},
            id="audiencia_duplicada",
        ),
        pytest.param(
            {"accepted_audiences": (h.RESOURCE_LEGADO,)}, id="resource_fora_das_audiencias"
        ),
        pytest.param({"canonical_host": "outro.example.invalid"}, id="host_inconsistente"),
        pytest.param({"required_scopes": ()}, id="sem_escopo_exigido"),
        pytest.param({"required_scopes": ("escopo com espaco",)}, id="escopo_malformado"),
        pytest.param({"allowed_origins": ("*",)}, id="origin_curinga"),
        pytest.param({"jwks_timeout_seconds": 0}, id="timeout_ilimitado"),
    ],
)
def test_configuracao_invalida_recusada(sobrescrita):
    """Fail-closed de configuração: cada uma destas combinações impede o
    servidor de existir, em vez de produzir identidade OAuth duvidosa."""
    with pytest.raises(ConfiguracaoAuthInvalida):
        h.config_canonica(**sobrescrita)


def test_uma_audiencia_por_padrao_e_duas_so_quando_explicito():
    """O alargamento de audience NUNCA acontece por omissão — só quando a
    lista é declarada de propósito, e a condição fica visível."""
    normal = h.config_canonica()
    assert len(normal.accepted_audiences) == 1
    assert normal.migracao_de_audiencia_ativa is False

    migracao = h.config_migracao()
    assert migracao.accepted_audiences == (h.RESOURCE_CANONICO, h.RESOURCE_LEGADO)
    assert migracao.migracao_de_audiencia_ativa is True
    # Mesmo em migração, o Resource ANUNCIADO continua sendo um só.
    assert migracao.canonical_resource == h.RESOURCE_CANONICO


def test_ambiente_sem_auth_devolve_none():
    assert carregar_config_do_ambiente({}) is None
    assert carregar_config_do_ambiente({"EDE_MCP_AUTH_ENABLED": "0"}) is None


def test_ambiente_com_config_pela_metade_recusa_subir():
    """Achado que esta trava existe para impedir: variável de auth
    presente e chave desligada NUNCA pode virar servidor anônimo."""
    with pytest.raises(ConfiguracaoAuthInvalida):
        carregar_config_do_ambiente({"EDE_MCP_RESOURCE": h.RESOURCE_CANONICO})


def test_ambiente_habilitado_exige_configuracao_completa():
    with pytest.raises(ConfiguracaoAuthInvalida):
        carregar_config_do_ambiente({"EDE_MCP_AUTH_ENABLED": "1"})


def test_ambiente_habilitado_monta_configuracao():
    config = carregar_config_do_ambiente({
        "EDE_MCP_AUTH_ENABLED": "true",
        "EDE_MCP_RESOURCE": h.RESOURCE_CANONICO,
        "EDE_MCP_ISSUER": h.ISSUER,
        "EDE_MCP_JWKS_URI": h.JWKS_URI,
    })
    assert config is not None
    assert config.accepted_audiences == (h.RESOURCE_CANONICO,)
    assert config.required_scopes == (ESCOPO_HEALTH,)


def test_ambiente_aceita_lista_explicita_de_duas_audiencias():
    config = carregar_config_do_ambiente({
        "EDE_MCP_AUTH_ENABLED": "1",
        "EDE_MCP_RESOURCE": h.RESOURCE_CANONICO,
        "EDE_MCP_ISSUER": h.ISSUER,
        "EDE_MCP_JWKS_URI": h.JWKS_URI,
        "EDE_MCP_ACCEPTED_AUDIENCES": f"{h.RESOURCE_CANONICO} {h.RESOURCE_LEGADO}",
    })
    assert config is not None
    assert config.migracao_de_audiencia_ativa is True


# =====================================================================
# 2. JWT / JOSE
# =====================================================================

def _verificador(config=None, *, app_jwks=None):
    """Verificador com o JWKS sintético atrás de um transporte ASGI."""
    config = config or h.config_canonica()
    app = app_jwks if app_jwks is not None else h.AppJwks()
    cliente = h.cliente_jwks(app)
    return EdeTokenVerifier(config, cliente_http=cliente), app, cliente


@pytest.mark.anyio
async def test_token_rs256_valido_aceito():
    verificador, _, cliente = _verificador()
    async with cliente:
        acesso = await verificador.verify_token(h.emitir_token())
    assert acesso is not None
    assert acesso.scopes == [ESCOPO_HEALTH]
    assert acesso.resource == h.RESOURCE_CANONICO
    assert acesso.subject == "usuario-sintetico"
    assert acesso.client_id == "cliente-sintetico"
    # Só `iss` é propagado do payload — nunca o token inteiro.
    assert acesso.claims == {"iss": h.ISSUER}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fabricar",
    [
        pytest.param(lambda: h.token_alg_none(), id="alg_none"),
        pytest.param(lambda: h.token_confusao_de_algoritmo(), id="confusao_de_algoritmo"),
        pytest.param(lambda: "nao.e.um.jwt", id="malformado_pontos"),
        pytest.param(lambda: "abcdef", id="malformado_sem_pontos"),
        pytest.param(lambda: "", id="vazio"),
        pytest.param(
            lambda: h.emitir_token(assinar_com=h.chaves("intruso")), id="assinatura_invalida"
        ),
        pytest.param(lambda: h.emitir_token(exp_em=-120), id="expirado"),
        pytest.param(lambda: h.emitir_token(nbf_em=600), id="nbf_futuro_demais"),
        pytest.param(
            lambda: h.emitir_token(issuer="https://outro.example.invalid/oauth"),
            id="issuer_errado",
        ),
        pytest.param(lambda: h.emitir_token(omitir_audiencia=True), id="aud_ausente"),
        pytest.param(lambda: h.emitir_token(omitir_exp=True), id="exp_ausente"),
        pytest.param(
            lambda: h.emitir_token(audiencia=h.RESOURCE_LEGADO), id="aud_nao_relacionada"
        ),
        pytest.param(
            lambda: h.emitir_token(audiencia=[h.RESOURCE_LEGADO, "https://x.example.invalid"]),
            id="aud_lista_so_com_estranhos",
        ),
        pytest.param(
            lambda: h.emitir_token(audiencia=h.RESOURCE_CANONICO + "/extra"),
            id="ataque_de_prefixo",
        ),
        pytest.param(
            lambda: h.emitir_token(
                audiencia="https://ede-mcp-000000000000.southamerica-east1.run.app"
            ),
            id="ataque_so_hostname",
        ),
        pytest.param(
            lambda: h.emitir_token(audiencia=h.HOST_CANONICO), id="ataque_de_substring"
        ),
        pytest.param(
            lambda: h.emitir_token(audiencia="https://*.run.app/mcp"), id="ataque_curinga"
        ),
        pytest.param(
            lambda: h.emitir_token(
                cabecalhos_extra={"jku": "https://atacante.example.invalid/jwks"}
            ),
            id="jku_do_atacante",
        ),
        pytest.param(
            lambda: h.emitir_token(cabecalhos_extra={"jwk": h.chaves("intruso").jwk()}),
            id="jwk_do_atacante",
        ),
        pytest.param(
            lambda: h.emitir_token(
                cabecalhos_extra={"x5u": "https://atacante.example.invalid/cert"}
            ),
            id="x5u_do_atacante",
        ),
        pytest.param(lambda: h.emitir_token(escopo="escopo\\invalido"), id="escopo_malformado"),
        pytest.param(
            lambda: h.emitir_token(sub=None, azp=None), id="principal_indeterminado"
        ),
    ],
)
async def test_token_invalido_sempre_recusado(fabricar):
    """Toda rejeição é `None` — o SDK traduz em 401 e nenhum handler roda.

    Os casos de audience cobrem explicitamente as formas de casamento
    aproximado que NUNCA podem valer: prefixo, substring, só hostname e
    curinga."""
    verificador, _, cliente = _verificador()
    async with cliente:
        assert await verificador.verify_token(fabricar()) is None
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_aud_como_string_exata_aceita():
    verificador, _, cliente = _verificador()
    async with cliente:
        acesso = await verificador.verify_token(h.emitir_token(audiencia=h.RESOURCE_CANONICO))
    assert acesso is not None


@pytest.mark.anyio
async def test_aud_como_lista_contendo_o_resource_aceita():
    verificador, _, cliente = _verificador()
    async with cliente:
        acesso = await verificador.verify_token(
            h.emitir_token(audiencia=["https://outro.example.invalid", h.RESOURCE_CANONICO])
        )
    assert acesso is not None
    assert acesso.resource == h.RESOURCE_CANONICO


@pytest.mark.anyio
async def test_nbf_dentro_do_skew_aceito():
    """60s de tolerância: `nbf` 30s no futuro passa, 600s não (coberto
    acima)."""
    verificador, _, cliente = _verificador()
    async with cliente:
        assert await verificador.verify_token(h.emitir_token(nbf_em=30)) is not None


@pytest.mark.anyio
async def test_migracao_aceita_audiencia_legada_so_quando_declarada():
    """A audience legada só vale sob configuração de migração EXPLÍCITA —
    e nunca vale sob a configuração normal."""
    normal, _, cliente_normal = _verificador()
    async with cliente_normal:
        assert await normal.verify_token(h.emitir_token(audiencia=h.RESOURCE_LEGADO)) is None

    migrando, _, cliente_migrando = _verificador(h.config_migracao())
    async with cliente_migrando:
        acesso = await migrando.verify_token(h.emitir_token(audiencia=h.RESOURCE_LEGADO))
    assert acesso is not None
    assert acesso.resource == h.RESOURCE_LEGADO


# ---------------------------------------------------------------- JWKS

@pytest.mark.anyio
async def test_jwks_kid_desconhecido_dispara_refresh_bem_sucedido():
    """Rotação de chave: o `kid` novo não está em cache, o refresh o traz."""
    app = h.AppJwks()
    verificador, _, cliente = _verificador(app_jwks=app)
    async with cliente:
        assert await verificador.verify_token(h.emitir_token()) is not None
        assert verificador.cache.buscas_realizadas == 1

        rotacionada = h.chaves("ede-teste-2")
        app.servir({"keys": [h.chaves().jwk(), rotacionada.jwk()]})
        verificador.cache._ultima_tentativa_em = None  # ignora o rate limit neste caso
        acesso = await verificador.verify_token(h.emitir_token(chave=rotacionada))
    assert acesso is not None
    assert verificador.cache.buscas_realizadas == 2


@pytest.mark.anyio
async def test_jwks_kid_desconhecido_com_refresh_sem_a_chave_rejeita():
    app = h.AppJwks()
    verificador, _, cliente = _verificador(app_jwks=app)
    async with cliente:
        assert (
            await verificador.verify_token(h.emitir_token(kid="kid-que-nao-existe")) is None
        )
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_jwks_malformado_rejeita():
    for corpo in ("{ nao e json", json.dumps({}), json.dumps({"keys": []}),
                  json.dumps({"keys": [{"kty": "RSA"}]})):
        app = h.AppJwks(corpo=corpo)
        verificador, _, cliente = _verificador(app_jwks=app)
        async with cliente:
            assert await verificador.verify_token(h.emitir_token()) is None


@pytest.mark.anyio
async def test_jwks_acima_do_limite_de_chaves_rejeita():
    """Resposta gigante não pode consumir memória nem empurrar chaves."""
    config = h.config_canonica(jwks_max_keys=1)
    app = h.AppJwks()
    app.servir({"keys": [h.chaves().jwk(), h.chaves("ede-teste-3").jwk()]})
    verificador, _, cliente = _verificador(config, app_jwks=app)
    async with cliente:
        assert await verificador.verify_token(h.emitir_token()) is None


@pytest.mark.anyio
async def test_jwks_indisponivel_sem_cache_falha_fechado():
    app = h.AppJwksIndisponivel()
    verificador, _, cliente = _verificador(app_jwks=app)
    async with cliente:
        assert await verificador.verify_token(h.emitir_token()) is None
    assert app.requisicoes == 1, "uma única tentativa — nunca laço de retry"
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_cache_evita_rede_e_expira_com_o_ttl():
    """Semântica documentada do cache: dentro do TTL não há rede; fora do
    TTL o refresh é obrigatório."""
    relogio = {"agora": 1000.0}
    config = h.config_canonica(jwks_cache_ttl_seconds=100.0,
                               jwks_min_refresh_interval_seconds=0.0)
    app = h.AppJwks()
    cliente = h.cliente_jwks(app)
    cache = CacheJwks(config, cliente_http=cliente, relogio=lambda: relogio["agora"])
    verificador = EdeTokenVerifier(config, cache=cache)

    async with cliente:
        assert await verificador.verify_token(h.emitir_token()) is not None
        assert cache.buscas_realizadas == 1

        relogio["agora"] += 50.0  # dentro do TTL
        assert await verificador.verify_token(h.emitir_token()) is not None
        assert cache.buscas_realizadas == 1, "cache fresco não deve ir à rede"

        relogio["agora"] += 100.0  # fora do TTL
        assert await verificador.verify_token(h.emitir_token()) is not None
        assert cache.buscas_realizadas == 2


@pytest.mark.anyio
async def test_cache_dentro_do_ttl_tolera_queda_do_jwks_mas_nunca_alem_dele():
    """A única tolerância a indisponibilidade é limitada pelo TTL — fora
    dele, rejeita. Nada de fail-open com chave velha."""
    relogio = {"agora": 1000.0}
    config = h.config_canonica(jwks_cache_ttl_seconds=100.0,
                               jwks_min_refresh_interval_seconds=0.0)
    app_ok = h.AppJwks()
    cliente_ok = h.cliente_jwks(app_ok)
    cache = CacheJwks(config, cliente_http=cliente_ok, relogio=lambda: relogio["agora"])
    verificador = EdeTokenVerifier(config, cache=cache)

    async with cliente_ok:
        assert await verificador.verify_token(h.emitir_token()) is not None

    caido = h.cliente_jwks(h.AppJwksIndisponivel())
    async with caido:
        cache._cliente_http = caido
        relogio["agora"] += 50.0  # dentro do TTL -> chave em cache serve
        assert await verificador.verify_token(h.emitir_token()) is not None

        relogio["agora"] += 100.0  # fora do TTL -> refresh obrigatório falha
        assert await verificador.verify_token(h.emitir_token()) is None


@pytest.mark.anyio
async def test_rate_limit_impede_refresh_ilimitado_por_kid_desconhecido():
    """`kid` aleatório não pode virar amplificador de tráfego contra o
    Authorization Server."""
    relogio = {"agora": 1000.0}
    config = h.config_canonica(jwks_min_refresh_interval_seconds=30.0)
    app = h.AppJwks()
    cliente = h.cliente_jwks(app)
    cache = CacheJwks(config, cliente_http=cliente, relogio=lambda: relogio["agora"])

    async with cliente:
        await cache.obter_chave(h.chaves().kid)
        assert cache.buscas_realizadas == 1
        for _ in range(5):
            with pytest.raises(ErroJwks):
                await cache.obter_chave("kid-aleatorio")
        assert cache.buscas_realizadas == 1, "rate limit deve segurar o refresh"

        relogio["agora"] += 31.0
        with pytest.raises(ErroJwks):
            await cache.obter_chave("kid-aleatorio")
        assert cache.buscas_realizadas == 2


@pytest.mark.anyio
async def test_jwks_malformado_nao_destroi_cache_valido():
    relogio = {"agora": 1000.0}
    config = h.config_canonica(jwks_cache_ttl_seconds=100.0,
                               jwks_min_refresh_interval_seconds=0.0)
    app = h.AppJwks()
    cliente = h.cliente_jwks(app)
    cache = CacheJwks(config, cliente_http=cliente, relogio=lambda: relogio["agora"])

    async with cliente:
        await cache.obter_chave(h.chaves().kid)
        app.corpo = "{ corrompido"
        relogio["agora"] += 10.0
        # `kid` conhecido e cache fresco: nem chega a buscar.
        assert await cache.obter_chave(h.chaves().kid) is not None
        assert cache.kids_em_cache == (h.chaves().kid,)


def test_user_agent_e_timeout_sao_explicitos():
    from token_verifier import USER_AGENT_JWKS

    assert USER_AGENT_JWKS == "ede-legal-mcp/jwks-client"
    assert h.config_canonica().jwks_timeout_seconds > 0


# =====================================================================
# 3. ESCOPOS
# =====================================================================

FERRAMENTA_LEGAL_SINTETICA = "ferramenta_legal_sintetica"
"""Tool de TESTE, existente só neste módulo, para provar que `ede:health`
não alcança uma ferramenta `ede:legal`. Não é funcionalidade jurídica e
não existe no produto — o Gate 6.3-D2 proíbe implementar Core jurídico."""


def test_escopos_multiplos_separados_por_espaco():
    """Semântica padrão de OAuth: `scope` é lista separada por espaço."""
    assert separar_escopos("ede:health ede:legal") == (ESCOPO_HEALTH, ESCOPO_LEGAL)
    assert separar_escopos("  ede:health   ede:legal  ") == (ESCOPO_HEALTH, ESCOPO_LEGAL)
    assert separar_escopos("ede:health ede:health") == (ESCOPO_HEALTH,)
    assert separar_escopos("") == ()
    assert separar_escopos(None) == ()


@pytest.mark.parametrize("bruto", ['ede:health "aspas"', "ede:health barra\\invertida"])
def test_escopo_malformado_rejeitado_por_inteiro(bruto):
    """Rejeita a LEITURA inteira — nunca aproveita os tokens válidos e
    descarta o resto, que seria degradar a autorização em silêncio."""
    with pytest.raises(ConfiguracaoAuthInvalida):
        separar_escopos(bruto)


def test_matriz_de_escopos_por_ferramenta():
    """As duas direções da independência entre escopos, mais o
    fail-closed de ferramenta sem política declarada."""
    politica = EscopoFerramentaMiddleware({
        "ede_health": ESCOPO_HEALTH,
        FERRAMENTA_LEGAL_SINTETICA: ESCOPO_LEGAL,
    })

    # ede:health autoriza health...
    assert politica.decidir("ede_health", (ESCOPO_HEALTH,)) == (True, ESCOPO_HEALTH)
    # ...e NÃO autoriza a ferramenta legal.
    assert politica.decidir(FERRAMENTA_LEGAL_SINTETICA, (ESCOPO_HEALTH,)) == (
        False, ESCOPO_LEGAL,
    )
    # ede:legal NÃO autoriza health.
    assert politica.decidir("ede_health", (ESCOPO_LEGAL,)) == (False, ESCOPO_HEALTH)
    # Sem escopo nenhum (inclusive "autenticou, mas sem escopo"): nada.
    assert politica.decidir("ede_health", ()) == (False, ESCOPO_HEALTH)
    # Ferramenta fora do mapa nunca nasce acessível por omissão.
    assert politica.decidir("ferramenta_nao_catalogada", (ESCOPO_HEALTH, ESCOPO_LEGAL)) == (
        False, None,
    )


def test_mapa_do_produto_reflete_exatamente_as_tres_ferramentas_atuais():
    """Trava de escopo (atualizada no Gate 6.5-A: `ede_preparar_
    contestacao` passou a existir, exigindo `ede:legal`; e no Gate 6.6-C:
    `ede_finalizar_peca`, reaproveitando o MESMO `ede:legal`, nunca um
    escopo próprio — Decisão 6 da ADR-0018). O mapa nunca pode conter uma
    quarta entrada por acidente, e `ede_health` continua o único apontando
    para um escopo DIFERENTE — nenhuma das três se implica mutuamente
    (item central do Gate 6.5-A §4/§18, estendido pelo Gate 6.6-C)."""
    from scope_policy import (
        FERRAMENTA_CONTESTACAO,
        FERRAMENTA_FINALIZAR_PECA,
        FERRAMENTA_HEALTH,
        MAPA_ESCOPO_POR_FERRAMENTA,
    )

    assert dict(MAPA_ESCOPO_POR_FERRAMENTA) == {
        FERRAMENTA_HEALTH: ESCOPO_HEALTH,
        FERRAMENTA_CONTESTACAO: ESCOPO_LEGAL,
        FERRAMENTA_FINALIZAR_PECA: ESCOPO_LEGAL,
    }


def test_escopo_de_base_do_transporte_permanece_so_health():
    """Gate 6.5-A §5: a existência de `ede_preparar_contestacao` no mapa
    por-ferramenta NUNCA amplia o escopo de base exigido pela CAMADA
    HTTP (`AuthSettings.required_scopes`) — só `ede:health` continua
    necessário para qualquer dispatch alcançar o servidor MCP. Sem isso,
    um token só-`ede:legal` sem `ede:health` seria barrado na camada
    HTTP antes mesmo de a política por-ferramenta entrar em jogo — a
    mesma garantia dupla já documentada em scope_policy.py."""
    from auth_config import ESCOPOS_EXIGIDOS_PADRAO

    assert ESCOPOS_EXIGIDOS_PADRAO == (ESCOPO_HEALTH,)


# =====================================================================
# 4. HTTP / MCP
# =====================================================================

@asynccontextmanager
async def app_autenticada(config=None, app_jwks=None, servidor=None):
    """App ASGI REAL (a mesma que `main()` serve), com JWKS sintético."""
    config = config or h.config_canonica()
    app_jwks = app_jwks if app_jwks is not None else h.AppJwks()
    cliente = h.cliente_jwks(app_jwks)
    async with cliente:
        verificador = EdeTokenVerifier(config, cliente_http=cliente)
        alvo = servidor(config, verificador) if servidor else ede.criar_servidor(
            config, verificador
        )
        app = ede.construir_app_http(alvo, config)
        async with h.ciclo_de_vida(app):
            yield app, config


def _servidor_com_tool_legal(config, verificador):
    """Servidor de teste com uma segunda tool exigindo `ede:legal`."""
    from mcp.server import MCPServer
    from mcp.server.auth.settings import AuthSettings
    from scope_policy import contar_dispatch

    @contar_dispatch(FERRAMENTA_LEGAL_SINTETICA)
    def ferramenta_legal_sintetica() -> str:
        return "jamais deveria executar sem ede:legal"

    servidor = MCPServer(
        "EDE MCP — servidor sintético de teste",
        token_verifier=verificador,
        auth=AuthSettings(
            issuer_url=config.issuer,
            resource_server_url=config.canonical_resource,
            required_scopes=list(config.required_scopes),
            validate_token_resource=not config.migracao_de_audiencia_ativa,
        ),
        middleware=[
            EscopoFerramentaMiddleware({
                "ede_health": ESCOPO_HEALTH,
                FERRAMENTA_LEGAL_SINTETICA: ESCOPO_LEGAL,
            })
        ],
    )
    servidor.add_tool(ede.ede_health)
    servidor.add_tool(ferramenta_legal_sintetica)
    return servidor


@pytest.mark.anyio
async def test_prm_disponivel_e_anuncia_exatamente_um_resource():
    """RFC 9728: o PRM existe, é anônimo (o cliente precisa lê-lo para
    descobrir onde se autenticar) e anuncia UM Resource — nunca o
    hostname alternativo, nem a lista de audiences.

    Gate 6.5-B2: `scopes_supported` passou a anunciar `ede:health` E
    `ede:legal` (catálogo completo, via `MetadadosRecursoProtegidoMiddleware`
    / `scope_policy.escopos_anunciaveis`) — a correção exata do bloqueio
    root-caused no Gate 6.5-B1 (cliente conforme ao protocolo nunca pedia
    `ede:legal` porque o PRM nunca o anunciava)."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resource"] == h.RESOURCE_CANONICO
    assert corpo["authorization_servers"] == [h.ISSUER]
    assert corpo["scopes_supported"] == [ESCOPO_HEALTH, ESCOPO_LEGAL]
    assert h.HOST_ALTERNATIVO not in json.dumps(corpo)


def test_escopos_anunciaveis_deriva_do_mapa_sem_duplicata():
    """Gate 6.5-B2: o catálogo anunciado no PRM é SEMPRE base + todo
    escopo distinto do mapa por-ferramenta — determinístico, sem
    duplicata, nunca um escopo extra inventado nem um esquecido. Fonte
    única (scope_policy.escopos_anunciaveis); nenhuma lista paralela."""
    from scope_policy import escopos_anunciaveis

    assert escopos_anunciaveis((ESCOPO_HEALTH,)) == (ESCOPO_HEALTH, ESCOPO_LEGAL)
    # sem duplicata mesmo se a base já contivesse o escopo da tool.
    assert escopos_anunciaveis((ESCOPO_HEALTH, ESCOPO_LEGAL)) == (ESCOPO_HEALTH, ESCOPO_LEGAL)


def test_nenhum_escopo_desconhecido_e_anunciado():
    """O catálogo anunciado nunca extrapola o vocabulário fechado de
    escopos que este servidor realmente reconhece (auth_config.
    ESCOPOS_CONHECIDOS) — anunciar um escopo inexistente seria oferecer
    ao cliente algo que o servidor nunca saberia autorizar."""
    from scope_policy import escopos_anunciaveis
    from auth_config import ESCOPOS_CONHECIDOS

    assert set(escopos_anunciaveis((ESCOPO_HEALTH,))) <= set(ESCOPOS_CONHECIDOS)


@pytest.mark.anyio
async def test_prm_nao_amplia_o_escopo_de_base_do_transporte_de_verdade():
    """Complementa test_escopo_de_base_do_transporte_permanece_so_health
    (que só verifica a CONSTANTE de configuração): aqui é o objeto
    `AuthSettings` de verdade, dentro do servidor REAL construído por
    `criar_servidor`, que precisa continuar exigindo só `ede:health` —
    mesmo depois de o PRM passar a anunciar `ede:legal` também. Anunciar
    (descoberta) e exigir (camada HTTP) são coisas diferentes por
    construção, nunca só por coincidência de teste."""
    async with app_autenticada() as (app, config):
        pass
    assert config.required_scopes == (ESCOPO_HEALTH,)


@pytest.mark.anyio
async def test_descoberta_de_cliente_conforme_agora_seleciona_ede_legal():
    """Gate 6.5-B1 (diagnóstico) provou a causa raiz reproduzindo o
    algoritmo real de seleção de escopo de um cliente OAuth conforme ao
    protocolo (`mcp.client.auth.utils.get_client_metadata_scopes`): ele
    escolhe o que pedir na autorização A PARTIR do PRM, nunca pedindo um
    escopo que não viu anunciado ali. Este teste roda o MESMO algoritmo
    do SDK cliente contra o PRM real deste servidor, pós Gate 6.5-B2, e
    prova que ele agora seleciona `ede:health ede:legal` — a causa raiz
    do bloqueio do Gate 6.5-B1 deixou de existir."""
    from mcp.client.auth.utils import get_client_metadata_scopes
    from mcp.shared.auth import ProtectedResourceMetadata

    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.get("/.well-known/oauth-protected-resource/mcp")
    prm = ProtectedResourceMetadata.model_validate(r.json())

    escopo_selecionado = get_client_metadata_scopes(
        www_authenticate_scope=None,
        protected_resource_metadata=prm,
    )
    assert escopo_selecionado is not None
    assert set(escopo_selecionado.split()) == {ESCOPO_HEALTH, ESCOPO_LEGAL}


@pytest.mark.anyio
async def test_prm_da_migracao_continua_anunciando_um_unico_resource():
    """Mesmo com duas audiences autorizadas, o PRM anuncia um Resource."""
    async with app_autenticada(h.config_migracao()) as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.get("/.well-known/oauth-protected-resource/mcp")
    corpo = r.json()
    assert corpo["resource"] == h.RESOURCE_CANONICO
    assert h.RESOURCE_LEGADO not in json.dumps(corpo)


@pytest.mark.anyio
@pytest.mark.parametrize("metodo", ["tools/list", "tools/call"])
async def test_sem_authorization_401_com_www_authenticate(metodo):
    """Rota protegida NUNCA é anonimamente chamável — nem descoberta
    (`tools/list`), nem execução (`tools/call`)."""
    corpo = h.corpo_tools_list() if metodo == "tools/list" else h.corpo_tools_call()
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post("/mcp", json=corpo, headers=h.CABECALHOS_JSONRPC)
    assert r.status_code == 401
    desafio = r.headers["www-authenticate"]
    assert desafio.startswith("Bearer ")
    assert 'error="invalid_token"' in desafio
    assert (
        'resource_metadata="https://ede-mcp-000000000000.southamerica-east1.run.app'
        '/.well-known/oauth-protected-resource/mcp"'
    ) in desafio
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "autorizacao",
    [
        pytest.param("", id="vazio"),
        pytest.param("Bearer", id="sem_credencial"),
        pytest.param("Bearer ", id="credencial_vazia"),
        pytest.param("Basic dXNlcjpzZW5oYQ==", id="esquema_errado"),
        pytest.param("Token abc.def.ghi", id="esquema_desconhecido"),
        pytest.param("Bearerabc", id="sem_espaco"),
        pytest.param("Bearer nao.e.um.jwt", id="jwt_lixo"),
    ],
)
async def test_bearer_malformado_401_sem_dispatch(autorizacao):
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={"Authorization": autorizacao, **h.CABECALHOS_JSONRPC},
            )
    assert r.status_code == 401
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fabricar",
    [
        pytest.param(lambda: h.emitir_token(audiencia=h.RESOURCE_LEGADO), id="aud_errada"),
        pytest.param(lambda: h.emitir_token(omitir_audiencia=True), id="aud_ausente"),
        pytest.param(lambda: h.emitir_token(exp_em=-60), id="expirado"),
        pytest.param(lambda: h.emitir_token(nbf_em=3600), id="nbf_invalido"),
        pytest.param(
            lambda: h.emitir_token(issuer="https://falso.example.invalid/oauth"),
            id="issuer_errado",
        ),
        pytest.param(
            lambda: h.emitir_token(assinar_com=h.chaves("intruso")), id="assinatura_invalida"
        ),
        pytest.param(lambda: h.token_alg_none(), id="alg_none"),
        pytest.param(lambda: h.token_confusao_de_algoritmo(), id="confusao_de_algoritmo"),
        pytest.param(
            lambda: h.emitir_token(
                cabecalhos_extra={"jku": "https://atacante.example.invalid/jwks"}
            ),
            id="jku_do_atacante",
        ),
    ],
)
async def test_token_invalido_401_sem_dispatch(fabricar):
    """Contrato de erro do gate, ponta a ponta: 401 e ZERO dispatch."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={"Authorization": f"Bearer {fabricar()}", **h.CABECALHOS_JSONRPC},
            )
    assert r.status_code == 401
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_jwks_indisponivel_falha_fechado_no_http():
    async with app_autenticada(app_jwks=h.AppJwksIndisponivel()) as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={
                    "Authorization": f"Bearer {h.emitir_token()}",
                    **h.CABECALHOS_JSONRPC,
                },
            )
    assert r.status_code == 401
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_escopo_insuficiente_403_sem_dispatch():
    """Token PERFEITAMENTE válido, mas sem o escopo exigido: 403 com
    semântica `insufficient_scope`, não 401 — autenticou, não autorizou."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={
                    "Authorization": f"Bearer {h.emitir_token(escopo=ESCOPO_LEGAL)}",
                    **h.CABECALHOS_JSONRPC,
                },
            )
    assert r.status_code == 403
    assert 'error="insufficient_scope"' in r.headers["www-authenticate"]
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_token_sem_escopo_algum_403():
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={
                    "Authorization": f"Bearer {h.emitir_token(escopo=None)}",
                    **h.CABECALHOS_JSONRPC,
                },
            )
    assert r.status_code == 403
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_corpo_de_erro_nunca_vaza_o_token():
    """O gate proíbe vazar detalhe do token na resposta de erro."""
    token = h.emitir_token(exp_em=-60)
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={"Authorization": f"Bearer {token}", **h.CABECALHOS_JSONRPC},
            )
    corpo_completo = r.text + json.dumps(dict(r.headers))
    assert token not in corpo_completo
    for fragmento in token.split("."):
        assert fragmento not in corpo_completo
    assert "expirado" not in corpo_completo.lower()


@pytest.mark.anyio
async def test_token_valido_alcanca_o_dispatch_da_health():
    """Caminho POSITIVO com cliente MCP oficial: exatamente UM dispatch.
    O contrato de transporte/OAuth (service_status, exatamente um
    dispatch) é o baseline imutável deste teste — `checks.rag` deixou de
    ser NOT_CONFIGURED fixo a partir do Gate 6.4-A (ADR-0017 §6: corpus
    RAG público/versionado pode ser embutido na imagem), então esta
    checagem reflete o corpus real do checkout, não mais um stub.
    `modelo_oficial` continua NOT_CONFIGURED aqui porque o processo de
    teste não define EDE_MODELO_OFICIAL_PATH/_SHA256 — mesmo estado real
    de produção hoje (ADR-0017 §6: Modelo Oficial não é embutido na
    imagem, é asset privado externo, ADR-0009)."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            resultado = await cliente.call_tool("ede_health", {})

    assert resultado.is_error is not True
    dados = resultado.structured_content
    assert dados["service_status"] == "READY"
    assert dados["contestacao_status"] == "NOT_READY"
    assert dados["checks"]["modelo_oficial"]["status"] == "NOT_CONFIGURED"
    assert dados["version"] == (BASE / "VERSION").read_text(encoding="utf-8").strip()
    assert CONTADOR_DISPATCH.de("ede_health") == 1
    assert CONTADOR_DISPATCH.total() == 1


@pytest.mark.anyio
async def test_tools_list_com_token_valido_lista_a_health():
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            listagem = await cliente.list_tools()
    assert {t.name for t in listagem.tools} == {"ede_health"}
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_health_nao_descobre_nem_alcanca_ferramenta_legal():
    """§7 do gate: um principal só com `ede:health` não obtém acesso
    utilizável a uma tool `ede:legal` — nem por descoberta, nem por
    chamada direta, e sem nenhum dispatch."""
    async with app_autenticada(servidor=_servidor_com_tool_legal) as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            listagem = await cliente.list_tools()
            nomes = {t.name for t in listagem.tools}
            assert nomes == {"ede_health"}, "a tool ede:legal não pode ser descoberta"

            with pytest.raises(Exception) as excecao:
                await cliente.call_tool(FERRAMENTA_LEGAL_SINTETICA, {})
            assert "insufficient_scope" in str(excecao.value)

    assert CONTADOR_DISPATCH.de(FERRAMENTA_LEGAL_SINTETICA) == 0


# =====================================================================
# 5. ede_preparar_contestacao — Gate 6.5-A (servidor REAL, não sintético)
# =====================================================================
#
# Testes 6-9 da matriz do gate. Diferente do bloco acima (que usa um
# servidor sintético só para provar o MECANISMO do middleware antes de
# qualquer tool ede:legal existir de verdade), estes testes usam
# `app_autenticada()` sem override — o MESMO servidor real que produção
# serve, com a tool `ede_preparar_contestacao` de verdade registrada.

FATO_MINIMO_SINTETICO = {
    "fatos": [{"fact": "Fato sintético de teste.", "source_document": "doc-teste.pdf"}],
}


@pytest.mark.anyio
async def test_health_only_nao_descobre_ferramenta_legal_real():
    """6: escopo só-health não lista `ede_preparar_contestacao`."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            listagem = await cliente.list_tools()
    assert {t.name for t in listagem.tools} == {"ede_health"}


@pytest.mark.anyio
async def test_health_only_chamada_direta_a_ferramenta_legal_e_negada():
    """7: escopo só-health chamando `ede_preparar_contestacao` diretamente
    (mesmo sem descobri-la) é negado ANTES do dispatch — contador
    inalterado."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            with pytest.raises(Exception) as excecao:
                await cliente.call_tool("ede_preparar_contestacao", {"entrada": FATO_MINIMO_SINTETICO})
            assert "insufficient_scope" in str(excecao.value)
    assert CONTADOR_DISPATCH.de("ede_preparar_contestacao") == 0


@pytest.mark.anyio
async def test_escopo_legal_descobre_ferramenta_legal_real():
    """8: escopo `ede:legal` (+ `ede:health`, exigido pela camada de
    transporte — ver test_escopo_de_base_do_transporte_permanece_so_
    health) lista as TRÊS ferramentas (Gate 6.6-C: `ede_finalizar_peca`
    reaproveita `ede:legal`, mesmo escopo de `ede_preparar_contestacao`)."""
    token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, token) as cliente:
            listagem = await cliente.list_tools()
    assert {t.name for t in listagem.tools} == {
        "ede_health", "ede_preparar_contestacao", "ede_finalizar_peca",
    }


@pytest.mark.anyio
async def test_escopo_apenas_legal_nao_alcanca_camada_de_transporte():
    """Direção oposta (scope_policy.py, "as duas direções são
    independentes"): um token só `ede:legal`, SEM `ede:health` (o escopo
    de BASE do transporte), é recusado pela camada HTTP do SDK antes de
    qualquer coisa — nunca alcança nem `ede_health` nem `ede_preparar_
    contestacao`."""
    token = h.emitir_token(escopo=ESCOPO_LEGAL)
    async with app_autenticada() as (app, config):
        with pytest.raises(Exception):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                await cliente.list_tools()
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
@pytest.mark.docx_real
async def test_escopo_legal_chamada_autorizada_tem_sucesso():
    """9: escopo `ede:legal` chamando `ede_preparar_contestacao` com
    entrada válida tem sucesso e despacha exatamente uma vez. Requer o
    Modelo Oficial real (mesmo padrão docx_real do resto da suíte) —
    sem ele, `contestacao_status` nunca fica READY e a ferramenta
    recusa com PIPELINE_ABORTED (comportamento fail-closed, não um erro
    de autorização — testado à parte em test_preparar_contestacao.py)."""
    template_real = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
    if not template_real.is_file():
        pytest.skip(f"{template_real} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    import hashlib
    sha = hashlib.sha256(template_real.read_bytes()).hexdigest()
    os.environ["EDE_MODELO_OFICIAL_PATH"] = str(template_real)
    os.environ["EDE_MODELO_OFICIAL_SHA256"] = sha
    try:
        token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
        async with app_autenticada() as (app, config):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                resultado = await cliente.call_tool(
                    "ede_preparar_contestacao", {"entrada": FATO_MINIMO_SINTETICO}
                )
    finally:
        os.environ.pop("EDE_MODELO_OFICIAL_PATH", None)
        os.environ.pop("EDE_MODELO_OFICIAL_SHA256", None)

    assert resultado.is_error is not True
    dados = resultado.structured_content
    assert dados["status"] == "OK"
    assert dados["pacote"]["readiness"]["contestacao_status"] == "READY"
    assert CONTADOR_DISPATCH.de("ede_preparar_contestacao") == 1


@pytest.mark.anyio
async def test_migracao_aceita_audiencia_legada_ponta_a_ponta():
    """A janela de migração funciona de verdade no HTTP — e a mesma
    audience continua recusada sob a configuração normal."""
    async with app_autenticada(h.config_migracao()) as (app, config):
        async with h.cliente_mcp_protocolo(
            app, config, h.emitir_token(audiencia=h.RESOURCE_LEGADO)
        ) as cliente:
            resultado = await cliente.call_tool("ede_health", {})
    assert resultado.is_error is not True
    assert CONTADOR_DISPATCH.de("ede_health") == 1


# =====================================================================
# 5. HOST / ORIGIN
# =====================================================================

@pytest.mark.anyio
async def test_host_canonico_aceito():
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            resultado = await cliente.call_tool("ede_health", {})
    assert resultado.is_error is not True


@pytest.mark.anyio
async def test_host_inesperado_rejeitado_mesmo_com_token_valido():
    """Um hostname alternativo do Cloud Run pode ROTEAR para este
    serviço; isso nunca o torna canônico. 421 (Misdirected Request),
    com token perfeitamente válido, e nenhum dispatch."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={
                    "Authorization": f"Bearer {h.emitir_token()}",
                    "Host": h.HOST_ALTERNATIVO,
                    **h.CABECALHOS_JSONRPC,
                },
            )
    assert r.status_code == 421
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
async def test_origin_ausente_segue_para_a_validacao_oauth():
    """Claude e ChatGPT não mandam Origin de navegador (prova viva do
    Gate 6.3-D0c). Origin ausente NÃO pode ser bloqueado no transporte —
    tem que chegar ao OAuth, que é quem decide."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            sem_token = await cliente.post(
                "/mcp", json=h.corpo_tools_call(), headers=h.CABECALHOS_JSONRPC
            )
            assert sem_token.status_code == 401, "rejeitado pelo OAuth, não pelo Origin"

        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            resultado = await cliente.call_tool("ede_health", {})
    assert resultado.is_error is not True


@pytest.mark.anyio
async def test_origin_inesperada_rejeitada():
    """Proteção contra DNS rebinding continua valendo para chamador de
    navegador: Origin presente e não autorizada é recusada."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            r = await cliente.post(
                "/mcp",
                json=h.corpo_tools_call(),
                headers={
                    "Authorization": f"Bearer {h.emitir_token()}",
                    "Origin": "https://atacante.example.invalid",
                    **h.CABECALHOS_JSONRPC,
                },
            )
    assert r.status_code == 403
    assert CONTADOR_DISPATCH.total() == 0


def test_seguranca_de_transporte_fixa_o_host_canonico_e_nao_usa_curinga():
    politica = ede.seguranca_de_transporte(h.config_canonica())
    assert politica.enable_dns_rebinding_protection is True
    assert politica.allowed_hosts == [h.HOST_CANONICO]
    assert politica.allowed_origins == []
    assert not any("*" in origem for origem in politica.allowed_origins)


# =====================================================================
# 6. TELEMETRIA DE SEGURANÇA
# =====================================================================

def test_campo_fora_da_allowlist_e_recusado():
    """A garantia não é convenção de uso: é estrutural."""
    for campo in ("authorization", "token", "jwt", "cpf", "numero_processo",
                  "client_secret", "cookie", "sinopse"):
        with pytest.raises(telemetria.CampoDeLogProibido):
            telemetria.registrar_evento(
                telemetria.EVENTO_REQUISICAO_HTTP, **{campo: "valor sensível"}
            )


def test_motivo_e_vocabulario_fechado():
    """Motivo nunca é texto livre — texto livre é o caminho pelo qual
    conteúdo do token/cliente chegaria ao log."""
    with pytest.raises(telemetria.CampoDeLogProibido):
        telemetria.registrar_evento(
            telemetria.EVENTO_REQUISICAO_HTTP, motivo="token eyJhbGciOi... rejeitado"
        )


def test_allowlist_nao_contem_nenhum_campo_de_conteudo():
    proibidos = {
        "authorization", "token", "jwt", "access_token", "refresh_token",
        "authorization_code", "client_secret", "cookie", "cpf", "cnpj",
        "cliente", "numero_processo", "contrato", "sinopse", "peca",
        "documento", "prompt", "texto", "corpo", "query",
    }
    assert telemetria.CAMPOS_PERMITIDOS.isdisjoint(proibidos)


@pytest.mark.anyio
async def test_telemetria_http_registra_metadado_e_nunca_o_token(caplog):
    """Prova sobre o log REAL emitido durante uma requisição real."""
    token = h.emitir_token()
    with caplog.at_level(logging.INFO, logger="ede.mcp.seguranca"):
        async with app_autenticada() as (app, config):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                await cliente.call_tool("ede_health", {})

    registros = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "ede.mcp.seguranca"
    ]
    assert registros, "a requisição precisa produzir telemetria de segurança"

    bruto = json.dumps(registros, ensure_ascii=False)
    assert token not in bruto
    for fragmento in token.split("."):
        assert fragmento not in bruto
    assert "Bearer" not in bruto
    assert "authorization" not in bruto.lower()

    http = [
        r
        for r in registros
        if r["evento"] == telemetria.EVENTO_REQUISICAO_HTTP and r["metodo_http"] == "POST"
    ]
    assert http, "evento de requisição ausente"
    assert all(r["status_http"] == 200 for r in http)
    assert all(r["resultado_auth"] == telemetria.AUTH_OK for r in http)
    # Cada requisição recebe um id próprio, gerado localmente.
    assert len({r["id_correlacao"] for r in http}) == len(http)
    alvo = http[-1]
    assert alvo["id_correlacao"]
    assert alvo["status_http"] == 200
    assert alvo["resultado_auth"] == telemetria.AUTH_OK
    assert alvo["audiencias_aceitas"] == 1
    assert alvo["migracao_audiencia"] is False
    assert "latencia_ms" in alvo
    # Nenhuma classificação inventada de grant type (§11 do gate).
    assert "grant_type" not in alvo
    assert set(alvo) <= telemetria.CAMPOS_PERMITIDOS


@pytest.mark.anyio
async def test_telemetria_de_rejeicao_usa_categoria_fechada(caplog):
    with caplog.at_level(logging.INFO, logger="ede.mcp.seguranca"):
        async with app_autenticada() as (app, config):
            async with h.cliente_mcp(app, config) as cliente:
                await cliente.post(
                    "/mcp",
                    json=h.corpo_tools_call(),
                    headers={
                        "Authorization": f"Bearer {h.emitir_token(exp_em=-60)}",
                        **h.CABECALHOS_JSONRPC,
                    },
                )
    registros = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "ede.mcp.seguranca"
    ]
    motivos = [r["motivo"] for r in registros if "motivo" in r]
    assert telemetria.MOTIVO_EXPIRADO in motivos
    assert all(m in telemetria.MOTIVOS for m in motivos)


def test_startup_declara_explicitamente_auth_desligada(caplog):
    """A ausência de autorização de aplicação precisa ser VISÍVEL —
    identidade de infraestrutura do Google Cloud não é autorização EDE."""
    from http_telemetry import registrar_startup

    with caplog.at_level(logging.INFO, logger="ede.mcp.seguranca"):
        registro = registrar_startup(None)
    assert registro["auth_aplicacao"] is False

    registro = registrar_startup(h.config_migracao())
    assert registro["auth_aplicacao"] is True
    assert registro["audiencias_aceitas"] == 2
    assert registro["migracao_audiencia"] is True
    assert registro["host_canonico"] == h.HOST_CANONICO


# =====================================================================
# 7. PROVA AGREGADA DE DISPATCH ZERO
# =====================================================================

@pytest.mark.anyio
async def test_nenhum_caso_negativo_alcanca_o_dispatch_e_o_positivo_conta_um():
    """Fecho do §17: uma bateria de negativos seguida de um positivo, no
    MESMO processo e com o MESMO contador. Prova a afirmação inteira de
    uma vez — não só caso a caso."""
    negativos = [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic dXNlcjpzZW5oYQ=="},
        {"Authorization": f"Bearer {h.emitir_token(audiencia=h.RESOURCE_LEGADO)}"},
        {"Authorization": f"Bearer {h.emitir_token(exp_em=-60)}"},
        {"Authorization": f"Bearer {h.emitir_token(assinar_com=h.chaves('intruso'))}"},
        {"Authorization": f"Bearer {h.token_alg_none()}"},
        {"Authorization": f"Bearer {h.emitir_token(escopo=ESCOPO_LEGAL)}"},
        {"Authorization": f"Bearer {h.emitir_token()}", "Host": h.HOST_ALTERNATIVO},
        {
            "Authorization": f"Bearer {h.emitir_token()}",
            "Origin": "https://atacante.example.invalid",
        },
    ]

    async with app_autenticada() as (app, config):
        async with h.cliente_mcp(app, config) as cliente:
            for cabecalhos in negativos:
                resposta = await cliente.post(
                    "/mcp",
                    json=h.corpo_tools_call(),
                    headers={**cabecalhos, **h.CABECALHOS_JSONRPC},
                )
                assert resposta.status_code in (401, 403, 421), (
                    f"caso negativo respondeu {resposta.status_code}: {cabecalhos}"
                )
                assert CONTADOR_DISPATCH.total() == 0, (
                    f"DISPATCH ALCANÇADO por caso negativo: {cabecalhos}"
                )

        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            resultado = await cliente.call_tool("ede_health", {})

    assert resultado.is_error is not True
    assert CONTADOR_DISPATCH.total() == 1


# =====================================================================
# 8. INSUMOS DE BUILD (allowlist do container)
# =====================================================================

def test_todo_modulo_do_servidor_entra_no_contexto_de_build():
    """`.dockerignore` é ALLOWLIST e o `Dockerfile` copia arquivo a
    arquivo: um módulo novo esquecido em qualquer um dos dois não chega à
    imagem e o container quebra no import.

    Este teste é a trava contra esse esquecimento — sem ele, a falha só
    apareceria num build remoto (Etapa 6.2-B em diante), longe da
    alteração que a causou."""
    modulos = sorted(
        caminho.name
        for caminho in MCP_SERVER_DIR.glob("*.py")
        if not caminho.name.startswith("_")
    )
    assert "server.py" in modulos
    assert "token_verifier.py" in modulos, "camada OAuth precisa existir"

    dockerignore = (BASE / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (MCP_SERVER_DIR / "Dockerfile").read_text(encoding="utf-8")

    for modulo in modulos:
        assert f"!mcp_server/{modulo}" in dockerignore, (
            f"{modulo} não está liberado na allowlist de .dockerignore"
        )
        assert f"mcp_server/{modulo} mcp_server/{modulo}" in dockerfile, (
            f"{modulo} não é copiado pelo mcp_server/Dockerfile"
        )


def test_requirements_declara_a_dependencia_jwt_e_nada_de_bloat():
    """A dependência JWT é declarada; nenhum framework web, Authorization
    Server ou SDK de nuvem completo entra no container. `lxml` (Gate
    6.4-A, ADR-0017 §6 — contrato do Modelo Oficial), `google-auth`
    (Gate 6.4-B, mesmo ADR — só `google.auth.default()` para obter a
    identidade da service account de runtime) e `requests` (Gate 6.4-C1
    — achado real de um rollback de produção: `google.auth.
    compute_engine._metadata`, a detecção de ambiente Cloud Run/GCE
    usada internamente por `google.auth.default()`, tem `import
    requests` incondicional, não opcional; sem ela a identidade da
    service account nunca é detectada e o Modelo Oficial nunca fica
    READY) são as ÚNICAS exceções à lista fixa anterior. `requests`
    entra só pela árvore de `google-auth` — nenhuma linha do EDE a
    importa diretamente; a leitura do objeto GCS em si continua usando
    `httpx2`, já transitivo via `mcp`. NUNCA `google-cloud-storage` (o
    SDK completo, que traria google-api-core/google-cloud-core/
    google-resumable-media). RAG (análise/busca — pandas, numpy,
    pyarrow, scikit-learn, scipy, rank_bm25, sentence-transformers) e
    qualquer SDK de nuvem completo continuam proibidos: a checagem de
    saúde do corpus usa só biblioteca padrão
    (scripts/legal_readiness.py), nunca constrói índice de busca."""
    requirements = (MCP_SERVER_DIR / "requirements.txt").read_text(encoding="utf-8")
    ativas = [
        linha.strip()
        for linha in requirements.splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]
    assert ativas == [
        "mcp==2.2.0", "pyjwt[crypto]==2.13.0", "lxml==6.1.3", "google-auth==2.58.0",
        "requests==2.34.2",
    ]

    proibidas = (
        "flask", "django", "fastapi", "authlib", "python-jose", "oauthlib",
        "google-cloud", "boto3", "pyarrow", "rank_bm25", "sentence_transformers",
        "pandas", "numpy", "scikit-learn", "scipy", "joblib", "python-docx",
        "grpc", "protobuf",
    )
    for proibida in proibidas:
        assert not any(proibida in linha.lower() for linha in ativas), proibida


# =====================================================================
# 9. GUARD DE PRODUÇÃO — K_SERVICE == "ede-mcp" (Gate 6.3-D3.1, ADR-0017)
# =====================================================================
#
# Achado do Gate 6.3-D3.0: com toda variável EDE_MCP_* ausente, a auth
# desliga por design (ADR-0016) — aceitável para staging/local, nunca
# para o serviço de produção. `K_SERVICE` é injetada pela própria
# plataforma Cloud Run, nunca por configuração externa esquecível.

def test_A_sem_k_service_e_sem_config_preserva_compatibilidade():
    """K_SERVICE ausente é o caso local/teste de sempre — nenhuma
    mudança de comportamento."""
    assert carregar_config_do_ambiente({}) is None


def test_B_staging_sem_config_preserva_compatibilidade():
    """K_SERVICE=ede-mcp-staging nunca aciona o guard — o nome é
    comparado por igualdade exata, não por prefixo."""
    assert carregar_config_do_ambiente({VAR_K_SERVICE: "ede-mcp-staging"}) is None


def test_C_producao_sem_auth_enabled_recusa():
    with pytest.raises(ProducaoSemAuthInvalida):
        carregar_config_do_ambiente({VAR_K_SERVICE: NOME_SERVICO_PRODUCAO})


def test_D_producao_com_auth_enabled_false_recusa():
    with pytest.raises(ProducaoSemAuthInvalida):
        carregar_config_do_ambiente({
            VAR_K_SERVICE: NOME_SERVICO_PRODUCAO,
            "EDE_MCP_AUTH_ENABLED": "false",
        })


def test_E_producao_habilitada_sem_variaveis_obrigatorias_recusa():
    """O guard nunca substitui a validação existente de EdeAuthConfig —
    ele só fecha a lacuna de "tudo ausente"."""
    with pytest.raises(ConfiguracaoAuthInvalida) as excinfo:
        carregar_config_do_ambiente({
            VAR_K_SERVICE: NOME_SERVICO_PRODUCAO,
            "EDE_MCP_AUTH_ENABLED": "true",
        })
    assert not isinstance(excinfo.value, ProducaoSemAuthInvalida)


def test_F_producao_com_configuracao_completa_e_valida_sobe():
    config = carregar_config_do_ambiente({
        VAR_K_SERVICE: NOME_SERVICO_PRODUCAO,
        "EDE_MCP_AUTH_ENABLED": "true",
        "EDE_MCP_RESOURCE": h.RESOURCE_CANONICO,
        "EDE_MCP_ISSUER": h.ISSUER,
        "EDE_MCP_JWKS_URI": h.JWKS_URI,
    })
    assert config is not None
    assert config.canonical_resource == h.RESOURCE_CANONICO


def test_G_producao_com_configuracao_malformada_recusa():
    with pytest.raises(ConfiguracaoAuthInvalida) as excinfo:
        carregar_config_do_ambiente({
            VAR_K_SERVICE: NOME_SERVICO_PRODUCAO,
            "EDE_MCP_AUTH_ENABLED": "true",
            "EDE_MCP_RESOURCE": "http://" + h.HOST_CANONICO + "/mcp",  # não-HTTPS
            "EDE_MCP_ISSUER": h.ISSUER,
            "EDE_MCP_JWKS_URI": h.JWKS_URI,
        })
    assert not isinstance(excinfo.value, ProducaoSemAuthInvalida)


def test_guard_e_especifico_do_nome_de_producao_nao_generico():
    """O guard não deve disparar para nenhum outro nome de serviço —
    nem por semelhança textual, nem por conter o nome de produção como
    substring."""
    for nome in (
        "ede-mcp-staging",
        "ede-oauth-proof-disposable",
        "ede-mcp-dev",
        "outro-ede-mcp",
        "",
    ):
        assert carregar_config_do_ambiente({VAR_K_SERVICE: nome}) is None, nome


def test_producao_sem_auth_e_subclasse_de_configuracao_invalida():
    """`ProducaoSemAuthInvalida` é sempre capturável por quem já trata
    `ConfiguracaoAuthInvalida` — o guard não introduz um segundo
    contrato de erro paralelo."""
    assert issubclass(ProducaoSemAuthInvalida, ConfiguracaoAuthInvalida)


# =====================================================================
# 10. ede_finalizar_peca — Gate 6.6-C (servidor REAL, ADR-0018)
# =====================================================================
#
# Mesmo padrão do bloco 5 (ede_preparar_contestacao): servidor REAL, sem
# override sintético — a tool `ede_finalizar_peca` de verdade, mesmo
# escopo `ede:legal`, mesmo CONTADOR_DISPATCH.

CAPABILITY_ID_TESTE = "contestacao.irregularidade_consumo"


def _entrada_minima_finalizar_peca() -> dict:
    """Entrada estruturalmente válida, mas incompleta de propósito (sem
    `block_decisions`) — o suficiente para provar dispatch/escopo sem
    depender do Modelo Oficial real; o resultado esperado é sempre
    REFUSED (`MISSING_BLOCK_DECISION`), nunca uma exceção de transporte."""
    return {"capability_id": CAPABILITY_ID_TESTE, "placeholders": {}}


@pytest.mark.anyio
async def test_escopo_so_health_nao_descobre_nem_alcanca_finalizar_peca_real():
    """`ede_finalizar_peca` exige `ede:legal` — um token só-`ede:health`
    não a descobre e não consegue despachá-la, mesmo servidor real."""
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, h.emitir_token()) as cliente:
            listagem = await cliente.list_tools()
            assert "ede_finalizar_peca" not in {t.name for t in listagem.tools}

            with pytest.raises(Exception) as excecao:
                await cliente.call_tool("ede_finalizar_peca", {"entrada": _entrada_minima_finalizar_peca()})
            assert "insufficient_scope" in str(excecao.value)
    assert CONTADOR_DISPATCH.de("ede_finalizar_peca") == 0


@pytest.mark.anyio
async def test_escopo_legal_alcanca_finalizar_peca_e_despacha_uma_vez_mesmo_recusado():
    """Escopo `ede:legal` alcança `ede_finalizar_peca`; uma entrada
    incompleta é RECUSADA pelo Core (não um erro de transporte) e ainda
    assim conta como dispatch real — a prova de dispatch zero é só sobre
    autenticação/autorização, nunca sobre o resultado de negócio."""
    token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
    async with app_autenticada() as (app, config):
        async with h.cliente_mcp_protocolo(app, config, token) as cliente:
            resultado = await cliente.call_tool(
                "ede_finalizar_peca", {"entrada": _entrada_minima_finalizar_peca()}
            )
    assert resultado.is_error is not True
    texto = resultado.content[0].text
    dados = json.loads(texto)
    assert dados["status"] == "REFUSED"
    assert dados["error_code"] == "MISSING_BLOCK_DECISION"
    assert len(resultado.content) == 1  # nenhum EmbeddedResource em recusa
    assert CONTADOR_DISPATCH.de("ede_finalizar_peca") == 1


@pytest.mark.anyio
async def test_escopo_apenas_legal_sem_health_nao_alcanca_finalizar_peca():
    """Mesma garantia dupla de `test_escopo_apenas_legal_nao_alcanca_
    camada_de_transporte` (bloco 5), agora para `ede_finalizar_peca`:
    `ede:legal` sozinho não basta — falta o escopo de BASE do transporte."""
    token = h.emitir_token(escopo=ESCOPO_LEGAL)
    async with app_autenticada() as (app, config):
        with pytest.raises(Exception):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                await cliente.list_tools()
    assert CONTADOR_DISPATCH.total() == 0


@pytest.mark.anyio
@pytest.mark.docx_real
async def test_escopo_legal_finaliza_peca_com_sucesso_real():
    """Caminho de sucesso completo, através do transporte MCP protegido:
    entrada válida -> `EdeFinalizarPecaResposta` (primeiro content block)
    -> `EmbeddedResource` com o DOCX real (segundo content block),
    `annotations.audience == ["user"]`. Requer o Modelo Oficial real
    (mesmo padrão docx_real do resto da suíte)."""
    template_real = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
    if not template_real.is_file():
        pytest.skip(f"{template_real} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    import hashlib
    import json as _json

    sha = hashlib.sha256(template_real.read_bytes()).hexdigest()
    os.environ["EDE_MODELO_OFICIAL_PATH"] = str(template_real)
    os.environ["EDE_MODELO_OFICIAL_SHA256"] = sha
    try:
        catalogo = _json.loads(
            (BASE / "templates" / "contestacao" / "blocos.json").read_text(encoding="utf-8")
        )
        block_decisions = {
            b["id"]: "INCLUIR" for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")
        }
        entrada = {
            "capability_id": CAPABILITY_ID_TESTE,
            "placeholders": {
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
            },
            "block_decisions": block_decisions,
            "estado_processual": {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True},
        }
        token = h.emitir_token(escopo=f"{ESCOPO_HEALTH} {ESCOPO_LEGAL}")
        async with app_autenticada() as (app, config):
            async with h.cliente_mcp_protocolo(app, config, token) as cliente:
                resultado = await cliente.call_tool("ede_finalizar_peca", {"entrada": entrada})
    finally:
        os.environ.pop("EDE_MODELO_OFICIAL_PATH", None)
        os.environ.pop("EDE_MODELO_OFICIAL_SHA256", None)

    assert resultado.is_error is not True
    assert len(resultado.content) == 2
    metadado = json.loads(resultado.content[0].text)
    assert metadado["status"] == "OK"
    assert metadado["capability_id"] == CAPABILITY_ID_TESTE
    assert metadado["document_size"] and metadado["document_size"] <= 8 * 1024 * 1024

    recurso = resultado.content[1]
    assert recurso.type == "resource"
    assert recurso.annotations.audience == ["user"]
    assert recurso.resource.mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    import base64
    bruto = base64.b64decode(recurso.resource.blob)
    assert bruto[:2] == b"PK"
    assert hashlib.sha256(bruto).hexdigest() == metadado["document_sha256"]
    assert CONTADOR_DISPATCH.de("ede_finalizar_peca") == 1
