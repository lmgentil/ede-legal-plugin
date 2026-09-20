#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/server.py — EDE MCP Server (Etapa 6.1, ADR-0015; readiness
jurídica desde o Gate 6.4-A).

Adapter remoto fino sobre o EDE Core, nos termos da Opção A aprovada no
Gate da Etapa 6.0 e formalizada em ADR-0015: este servidor NUNCA chama a
API Claude/qualquer LLM e NUNCA reimplementa o raciocínio de
`estrategista-contestacao-ede`, `redator-peca-processual-elite` ou
`humanizer-pt-br` — essas Skills continuam rodando no host Claude. Este
servidor ainda expõe SOMENTE a tool `ede_health`: nenhuma geração de
Contestação é feita por este módulo. Desde o Gate 6.4-A, `ede_health`
chama `scripts/legal_readiness.py` (Core) para reportar verdade sobre
dois pré-requisitos determinísticos — corpus RAG (legislação já pública/
versionada) e Modelo Oficial (asset privado, ADR-0009) — mas nenhum dos
dois é lido/gerado/validado por lógica própria deste módulo; a validação
inteira vive no Core, reaproveitada, nunca duplicada (ADR-0015). O Modelo
Oficial continua nunca descoberto/reconstruído automaticamente — só lido
de um caminho local explicitamente configurado via variável de ambiente
(`EDE_MODELO_OFICIAL_PATH`/`_SHA256`); a aquisição a partir de
armazenamento privado remoto (Arquitetura A′, ADR-0017) é matéria de um
gate de implementação futuro, quando o bucket existir.

Transporte: Streamable HTTP, conforme a especificação MCP 2026-07-28
(núcleo do protocolo stateless; headers Mcp-Method/Mcp-Name resolvidos
pelo próprio SDK). Nenhum protocolo é implementado manualmente e nenhuma
abstração MCP própria é criada aqui — toda a conformidade vem do SDK
Python oficial `mcp` (pip, `mcp==2.2.0`; ver mcp_server/requirements.txt e
ADR-0015 para a justificativa da escolha/versão). `mcp.server.MCPServer`
é a classe que substitui `FastMCP` na major 2.x do SDK.

Host-agnostic, no mesmo espírito já adotado pelo EDE Core (ADR-0014):
nenhuma dependência de CLAUDE_PLUGIN_ROOT, SKILL.md, ~/.claude/~/.agents
ou de qualquer estado específico do host Claude. `BASE` é resolvido só a
partir da posição deste arquivo no repositório.

SERVICE_READY vs CONTESTACAO_READY:
  service_status      -> só diz se ESTE PROCESSO está de pé e conseguiu
                          calcular o diagnóstico sem exceção. Não depende
                          de RAG nem de Modelo Oficial.
  contestacao_status  -> diz se o pipeline determinístico da Contestação
                          teria como rodar. Só READY quando `process`,
                          `rag` e `modelo_oficial` estiverem todos READY
                          (ver `checks`) — hoje isso ainda depende de
                          `EDE_MODELO_OFICIAL_PATH`/`_SHA256` estarem
                          configurados e apontarem para um Modelo Oficial
                          provisionado e íntegro.
Os dois nunca são fundidos num único campo "status" — um servidor pode
estar operacional (service_status=READY) sem estar apto a gerar uma
Contestação (contestacao_status=NOT_READY); ver ADR-0015 e SPEC-0001.

Fail-closed (CLAUDE.md §17): qualquer exceção interna ao calcular o
diagnóstico vira service_status="ERROR" estruturado — nunca "READY", e o
detalhe exposto ao chamador nunca inclui stack trace ou mensagem bruta da
exceção (mesma disciplina de log/segurança do restante do EDE Core).

Dependências desde o Gate 6.4-A: além do SDK MCP, `legal_readiness.py`
importa `lxml` (contrato do Modelo Oficial — mesma dependência já usada
pelo instalador local) e lê `rag/corpus_manifest.json` + `rag/chunks_*/`
com a biblioteca padrão (hashlib/pathlib) — nenhuma dependência de
análise/busca (pandas, numpy, pyarrow, scikit-learn, scipy, rank_bm25,
joblib, sentence-transformers) entra neste servidor: a checagem de saúde
verifica presença/integridade estrutural do corpus, nunca constrói o
índice de busca híbrida (isso continua fora do escopo do MCP — nenhuma
ferramenta de busca/geração é exposta por este gate, ver §16 do pedido
do Gate 6.4-A).

Não confundir com o healthcheck de container/Cloud Run: aquele verifica
só "processo vivo" e não deve carregar nada deste módulo além do processo
já estar de pé — `ede_health` é o diagnóstico funcional do EDE, mais caro
e mais informativo, nunca o mesmo mecanismo (item 6 do pedido).

OAUTH DE APLICAÇÃO (Gate 6.3-D2, ADR-0016)
==========================================
O EDE é RESOURCE SERVER; Descope é o Authorization Server. Este módulo
não implementa Authorization Server algum — só liga as peças do SDK MCP
2.2.0 (`AuthSettings`, `TokenVerifier`, Protected Resource Metadata,
`WWW-Authenticate` com `resource_metadata`, exigência de escopo) à
configuração canônica validada em `mcp_server/auth_config.py`.

Distinção que não pode ser borrada: IAM do Cloud Run é autorização de
INFRAESTRUTURA (quem consegue abrir conexão), OAuth é autorização de
APLICAÇÃO (quem pode executar o quê). Identidade Google nunca é tratada
como autorização EDE. Com a camada OAuth ligada, sem token de aplicação
válido não há dispatch protegido — ponto.

A camada é ligada por `EDE_MCP_AUTH_ENABLED`. Desligada, o
comportamento é exatamente o das Etapas 6.1/6.2 (staging protegido só
por IAM de infraestrutura), e o startup DIZ isso na telemetria — estado
declarado, nunca disfarçado. Configuração pela metade (variável de auth
presente sem a chave ligada) recusa a subida: nunca degrada para
anônimo. Ver mcp_server/auth_config.py para o contrato completo.
"""
from __future__ import annotations

import importlib.metadata
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings

from auth_config import EdeAuthConfig, carregar_config_do_ambiente
from http_telemetry import TelemetriaSegurancaMiddleware, registrar_startup
from prm_override import MetadadosRecursoProtegidoMiddleware
from scope_policy import (
    FERRAMENTA_CONTESTACAO,
    FERRAMENTA_HEALTH,
    EscopoFerramentaMiddleware,
    contar_dispatch,
    escopos_anunciaveis,
)
from token_verifier import EdeTokenVerifier

BASE = Path(__file__).resolve().parent.parent
VERSION_FILE = BASE / "VERSION"

# Gate 6.4-A (ADR-0015, ADR-0017): checagens determinísticas de
# prontidão jurídica vivem em scripts/legal_readiness.py (Core) — este
# módulo só importa e traduz o resultado, nunca reimplementa validação.
# `scripts/` é adicionado ao sys.path aqui, no mesmo espírito do resto do
# EDE Core: cada módulo resolve seu próprio caminho, sem depender de
# CLAUDE_PLUGIN_ROOT nem de instalação via pip.
sys.path.insert(0, str(BASE / "scripts"))
import legal_readiness  # noqa: E402

# Gate 6.5-A (ADR-0015): primeira ferramenta jurídica real (`ede:legal`,
# não `ede:health`) — scripts/preparar_contestacao.py é CORE puro
# (nenhum raciocínio jurídico, nenhuma redação, nenhum LLM); este módulo
# só traduz entrada/saída MCP, mesma disciplina de `legal_readiness`
# acima. Escopo de acesso é decidido só por scope_policy.py; registrar a
# tool aqui não a torna alcançável por um principal sem `ede:legal`.
import preparar_contestacao  # noqa: E402

NOME_SERVIDOR = "EDE Legal Plugin — MCP Server"


class CheckStatus(str, Enum):
    """Estado de uma checagem individual dentro de `ede_health.checks`."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class HealthCheck(BaseModel):
    """Uma checagem nomeada (ex.: "rag", "modelo_oficial") e seu motivo."""

    status: CheckStatus
    detail: str


class EdeHealthResponse(BaseModel):
    """Schema de resposta de `ede_health` (Etapa 6.1, item 5 do pedido).

    `service_status` e `contestacao_status` são deliberadamente dois
    campos separados, nunca um único "status" genérico — ver docstring do
    módulo e ADR-0015.
    """

    service_status: Literal["READY", "DEGRADED", "ERROR"]
    contestacao_status: Literal["READY", "NOT_READY"]
    version: str
    runtime: str
    checks: dict[str, HealthCheck]


def _versao_plugin() -> str:
    """Versão do EDE Legal Plugin (arquivo VERSION na raiz do repo).

    Somente leitura; nunca falha o diagnóstico inteiro por conta disto —
    devolve um valor sentinela em vez de propagar a exceção, porque a
    ausência do arquivo VERSION não impede o processo de responder."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "desconhecida"


def _runtime_info() -> str:
    """Identificação do runtime deste servidor (Python + SDK MCP)."""
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    try:
        mcp_version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        mcp_version = "desconhecida"
    return f"python {py} / mcp {mcp_version} / EDE MCP Server"


@contar_dispatch(FERRAMENTA_HEALTH)
def ede_health() -> EdeHealthResponse:
    """Diagnóstico funcional do EDE MCP Server.

    Desde o Gate 6.4-A (ADR-0015, ADR-0017), `rag` e `modelo_oficial`
    deixaram de ser stubs fixos: cada um chama a checagem determinística
    correspondente em `scripts/legal_readiness.py` (Core) — nenhuma
    lógica de validação vive neste módulo. `contestacao_status` só chega
    a READY quando TODAS as checagens abaixo estiverem READY; hoje isso
    depende de provisionamento externo (corpus já pode ficar READY sem
    nada adicional — é asset público já versionado; Modelo Oficial só
    fica READY quando `EDE_MODELO_OFICIAL_PATH`/`_SHA256` apontarem para
    um arquivo provisionado, íntegro e conforme o contrato — nunca
    descoberto automaticamente, CLAUDE.md §13).

    Uma exceção ao chamar `legal_readiness` (bug, schema/catálogo do
    próprio plugin corrompido) nunca vira READY — cai no `except`
    genérico da função e o diagnóstico inteiro vira `ERROR`, mesma
    disciplina de fail-closed já aplicada ao restante desta função."""
    try:
        rag_resultado = legal_readiness.avaliar_corpus_rag()
        modelo_resultado = legal_readiness.avaliar_modelo_oficial()

        checks = {
            "process": HealthCheck(
                status=CheckStatus.READY,
                detail="Processo do EDE MCP Server ativo e respondendo.",
            ),
            "rag": HealthCheck(
                status=CheckStatus(rag_resultado.status),
                detail=rag_resultado.detail,
            ),
            "modelo_oficial": HealthCheck(
                status=CheckStatus(modelo_resultado.status),
                detail=modelo_resultado.detail,
            ),
        }

        contestacao_pronta = all(c.status == CheckStatus.READY for c in checks.values())

        return EdeHealthResponse(
            service_status="READY",
            contestacao_status="READY" if contestacao_pronta else "NOT_READY",
            version=_versao_plugin(),
            runtime=_runtime_info(),
            checks=checks,
        )
    except Exception:
        # Fail-closed (CLAUDE.md §17): erro interno nunca vira READY. O
        # detalhe exposto ao chamador é genérico de propósito — nunca a
        # mensagem/stack trace bruta da exceção. Nunca reinvocar aqui
        # _versao_plugin()/_runtime_info() (ou qualquer outro helper do
        # bloco acima): se a falha original veio de um deles, chamá-los
        # de novo no próprio tratamento de erro derrotaria o fail-closed
        # inteiro — achado real do teste desta etapa
        # (test_erro_interno_nunca_vira_ready). Este caminho usa só
        # valores literais, incondicionalmente seguros.
        return EdeHealthResponse(
            service_status="ERROR",
            contestacao_status="NOT_READY",
            version="desconhecida",
            runtime="desconhecida",
            checks={
                "process": HealthCheck(
                    status=CheckStatus.ERROR,
                    detail="Falha interna ao calcular o diagnóstico do servidor.",
                ),
            },
        )


# ===================================================================
# ede_preparar_contestacao — Gate 6.5-A (escopo ede:legal)
# ===================================================================

class FatoEntrada(BaseModel):
    """Um fato do caso, com proveniência — mesmo contrato de fatos.json
    (REQ-030, scripts/validate_fatos.py), reaproveitado sem alteração.

    Gate 6.5-B3 §15: os limites abaixo (`max_length`/`ge`/`le`) fazem o
    JSON Schema PUBLICADO desta tool (o que `tools/list` expõe) refletir
    os MESMOS limites que `scripts/preparar_contestacao.py` já exigia em
    runtime (`MAX_FACT_CHARS`/`MAX_SOURCE_DOCUMENT_CHARS`) — lidos
    daquele módulo, nunca redeclarados como um segundo número solto que
    poderia divergir. Antes deste gate, um cliente só descobria esses
    limites por tentativa e erro (uma chamada rejeitada); agora o
    schema já os declara."""

    fact: str = Field(..., max_length=preparar_contestacao.MAX_FACT_CHARS)
    source_document: str = Field(..., max_length=preparar_contestacao.MAX_SOURCE_DOCUMENT_CHARS)
    page: int | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tipo: Literal[
        "FATO_DOCUMENTADO", "ALEGACAO_AUTORAL", "INFERENCIA", "DADO_NAO_INFORMADO"
    ] | None = None


class PrepararContestacaoEntrada(BaseModel):
    """Entrada estruturada — nunca um campo "prompt" livre (Gate 6.5-A
    §6). Nenhum dado pessoal (CPF/RG/endereço/telefone/email) é aceito;
    nenhum nome de parte é exigido (o pacote não preenche placeholders,
    só prepara contexto para o host redigir)."""

    fatos: Annotated[
        list[FatoEntrada], Field(min_length=1, max_length=preparar_contestacao.MAX_FATOS)
    ]
    questoes_juridicas: Annotated[
        list[Annotated[str, Field(max_length=preparar_contestacao.MAX_QUESTAO_CHARS)]],
        Field(max_length=preparar_contestacao.MAX_QUESTOES_JURIDICAS),
    ] = []
    estado_processual: dict[str, bool | Literal["INDETERMINADO"]] = {}


class PrepararContestacaoResposta(BaseModel):
    """Pacote de Contexto da Contestação — nunca prosa jurídica pronta,
    nunca bytes/XML do Modelo Oficial, nunca dado sensível de terceiro.
    Campos livres (`dict`/`list[dict]`) refletem exatamente
    scripts/preparar_contestacao.py — nenhuma lógica de negócio duplicada
    aqui, só o contrato de schema MCP."""

    status: Literal["OK", "PIPELINE_ABORTED"]
    stage: str | None = None
    motivo: str | None = None
    pacote: dict | None = None


@contar_dispatch(FERRAMENTA_CONTESTACAO)
def ede_preparar_contestacao(entrada: PrepararContestacaoEntrada) -> PrepararContestacaoResposta:
    """Prepara o Pacote de Contexto autoritativo da Contestação — fatos
    normalizados, fontes legais do corpus institucional (com
    proveniência), catálogo de blocos/zonas condicionais, contexto
    institucional dos placeholders redigíveis e as regras/invariantes
    que a redação deve respeitar.

    Esta ferramenta NÃO redige a peça, NÃO decide teses/preliminares/
    Reconvenção, NÃO pesquisa jurisprudência e NÃO consulta DataJud. O
    HOST (Claude/ChatGPT) usa o pacote devolvido para raciocinar e
    redigir; a geração do DOCX final é etapa posterior, fora deste gate.

    Fail-closed: recusa com `PIPELINE_ABORTED` (nunca um pacote parcial
    apresentado como completo) se `contestacao_status` não estiver
    READY, se a entrada for inválida/exceder limites, ou se o
    schema/catálogo institucional do próprio plugin estiver corrompido.

    Privacidade: a entrada (fatos, questões jurídicas) é efêmera por
    requisição — nunca gravada em disco, nunca adicionada ao RAG, nunca
    logada."""
    try:
        resultado = preparar_contestacao.preparar_contexto_contestacao(
            entrada.model_dump(exclude_none=False)
        )
    except Exception:
        # Fail-closed (CLAUDE.md §17): mesma disciplina de ede_health —
        # exceção genuína nunca vira um pacote parcial nem expõe
        # stack trace/detalhe interno ao chamador.
        return PrepararContestacaoResposta(
            status="PIPELINE_ABORTED",
            stage="internal_error",
            motivo="Falha interna ao preparar o contexto da Contestação.",
        )

    return PrepararContestacaoResposta(
        status=resultado.status,
        stage=resultado.stage,
        motivo=resultado.motivo,
        pacote=resultado.pacote,
    )


def criar_servidor(
    config: EdeAuthConfig | None, verificador: TokenVerifier | None = None
) -> MCPServer:
    """Monta a instância `MCPServer` — com ou sem a camada OAuth.

    Fábrica, e não construção no nível do módulo, porque a identidade
    OAuth é dado de RUNTIME (o Resource canônico de produção é injetado
    quando o serviço `ede-mcp` existir) e porque a suíte precisa montar
    servidores com configuração sintética sem tocar o ambiente do
    processo.

    `config=None` reproduz exatamente o servidor das Etapas 6.1/6.2:
    sem `AuthSettings`, sem verificador, sem middleware de escopo. Isso
    é deliberado — uma segunda política implícita "meio ligada" seria
    pior que nenhuma.

    `verificador` é a costura de injeção de dependência usada pelo
    harness sintético (tests/oauth_harness.py), que precisa apontar a
    busca de JWKS para uma app ASGI em processo em vez da internet. Em
    produção ele é sempre `None` e o `EdeTokenVerifier` real é construído
    a partir da configuração — nunca existe um caminho em que a ausência
    de verificador signifique "sem verificação"."""
    if config is None:
        servidor = MCPServer(NOME_SERVIDOR)
        servidor.add_tool(ede_health)
        servidor.add_tool(ede_preparar_contestacao)
        return servidor

    servidor = MCPServer(
        NOME_SERVIDOR,
        token_verifier=verificador if verificador is not None else EdeTokenVerifier(config),
        auth=AuthSettings(
            # Descope é o Authorization Server; o EDE nunca emite token.
            issuer_url=config.issuer,
            # UM ÚNICO Resource anunciado no PRM (RFC 9728), sempre — a
            # eventual lista de audiences de migração não aparece aqui.
            resource_server_url=config.canonical_resource,
            required_scopes=list(config.required_scopes),
            # Checagem redundante do SDK (`AccessToken.resource` ==
            # `resource_server_url`) ligada na operação normal: duas
            # verificações exatas independentes da mesma audience.
            # Numa janela de migração EXPLÍCITA com mais de uma audience
            # autorizada, ela é desligada — ela compara com um único
            # valor e recusaria a audience legada autorizada. O rigor não
            # cai: quem valida a pertinência exata é o EdeTokenVerifier,
            # e a condição fica visível na telemetria de startup.
            validate_token_resource=not config.migracao_de_audiencia_ativa,
        ),
        middleware=[EscopoFerramentaMiddleware()],
    )
    servidor.add_tool(ede_health)
    servidor.add_tool(ede_preparar_contestacao)
    return servidor


def seguranca_de_transporte(config: EdeAuthConfig) -> TransportSecuritySettings:
    """Política de Host/Origin (Gate 6.3-D2 §10).

    Host: SOMENTE o host canônico, derivado do Resource. Um hostname
    alternativo do Cloud Run pode até rotear para este serviço, mas não é
    anunciado no PRM e não é aceito aqui — roteamento não é identidade.

    Origin: AUSENTE é aceito e segue para a validação OAuth. Isto não é
    relaxamento: é o que a prova viva do Gate 6.3-D0c mostrou sobre
    Claude e ChatGPT, que não mandam Origin de navegador. Origin PRESENTE
    e inesperada é rejeitada (a proteção contra DNS rebinding continua
    valendo para chamador de navegador). Curinga é recusado na validação
    da configuração, nunca aqui."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[config.canonical_host],
        allowed_origins=list(config.allowed_origins),
    )


def construir_app_http(servidor: MCPServer, config: EdeAuthConfig):
    """Aplicação ASGI servida em produção, com a telemetria por fora.

    A telemetria precisa ser a camada MAIS EXTERNA para observar também
    os 401/403 que o `RequireAuthMiddleware` do SDK devolve antes de
    qualquer dispatch. Envolver o app (em vez de `add_middleware`) mantém
    o lifespan do Starlette intacto: escopos que não são `http` passam
    direto.

    `MetadadosRecursoProtegidoMiddleware` (Gate 6.5-B2) fica IMEDIATAMENTE
    por dentro da telemetria (que continua, literalmente, a camada mais
    externa) e por fora de toda a app do SDK: ele só substitui a resposta
    do Protected Resource Metadata pelo catálogo completo de escopos
    (`scope_policy.escopos_anunciaveis`) — `config.required_scopes`
    (base do transporte, `AuthSettings.required_scopes`) permanece
    inalterado, só `ede:health`."""
    app = servidor.streamable_http_app(
        streamable_http_path=config.caminho_mcp,
        transport_security=seguranca_de_transporte(config),
    )
    app = MetadadosRecursoProtegidoMiddleware(
        app, config, escopos_anunciaveis(config.required_scopes)
    )
    return TelemetriaSegurancaMiddleware(app, config)


# Configuração resolvida UMA vez, no import. Erro de configuração
# propaga de propósito: um servidor cuja identidade OAuth está
# malformada não deve chegar a existir (CLAUDE.md §17). O contrário —
# capturar o erro e seguir sem auth — é exatamente a degradação
# silenciosa que o gate proíbe.
CONFIG_AUTH = carregar_config_do_ambiente()

mcp = criar_servidor(CONFIG_AUTH)


DEFAULT_HOST_LOCAL = "127.0.0.1"
DEFAULT_PORT_LOCAL = 8765
"""Endereço/porta default da EXECUÇÃO LOCAL SEM CONFIGURAÇÃO (não do
container/Cloud Run -- ver main()). Decisão de arquitetura registrada
nesta rodada: a porta usada por esta constante ANTES desta mudança
(ver `git log -p` do commit que a alterou para a Etapa 6.2) passou a
estar reservada a outro serviço no ambiente local do projeto e NUNCA
deve voltar a ser o default do EDE MCP -- 8765 é, daqui em diante, a
única porta local default do EDE MCP; nenhum outro ponto deste módulo
hardcoda um valor de substituição."""


def main() -> None:
    """Entrypoint de processo — único lugar que decide transporte/porta.

    Streamable HTTP conforme a especificação MCP 2026-07-28. Nenhuma
    lógica de protocolo é escrita aqui; `mcp.run()` é fornecido pelo SDK.

    Host/porta são sempre lidos do ambiente primeiro -- distinção
    obrigatória entre dois cenários (não confundir um com o outro):

      EXECUÇÃO LOCAL SEM CONFIGURAÇÃO -> 127.0.0.1:8765
        (DEFAULT_HOST_LOCAL/DEFAULT_PORT_LOCAL acima; usado só quando
        HOST/PORT não estão definidas no ambiente)

      CONTAINER/CLOUD RUN -> 0.0.0.0:${PORT}
        (a plataforma injeta PORT; o Dockerfile define HOST=0.0.0.0;
        este código nunca decide isso por conta própria nem substitui a
        PORT fornecida por um valor fixo -- só cai nos defaults locais
        quando a variável correspondente está mesmo ausente)

    O default local mudou para 127.0.0.1:8765 nesta rodada (commit
    25791cd tinha introduzido a leitura de ambiente preservando ainda o
    valor antigo como fallback) porque a porta antiga passou a ser
    reservada a outro serviço do ambiente local -- decisão de
    arquitetura explícita do usuário, não uma escolha técnica deste
    módulo. Nenhum outro ponto deste arquivo hardcoda um valor de
    substituição.

    DOIS CAMINHOS DE SUBIDA (Gate 6.3-D2):

      SEM OAuth de aplicação (CONFIG_AUTH is None) -> `mcp.run(...)`,
        byte a byte o que as Etapas 6.1/6.2 já faziam. Nada muda para o
        staging atual, protegido por IAM de infraestrutura.

      COM OAuth de aplicação -> a app ASGI é montada explicitamente
        (`construir_app_http`) para que a telemetria de segurança fique
        POR FORA da autenticação do SDK e observe também os 401/403.
        `mcp.run()` não expõe esse ponto de extensão; usar a API pública
        `streamable_http_app()` + uvicorn é o caminho suportado, não um
        contorno do SDK."""
    registrar_startup(CONFIG_AUTH)
    host = os.environ.get("HOST", DEFAULT_HOST_LOCAL)
    port = int(os.environ.get("PORT", DEFAULT_PORT_LOCAL))

    if CONFIG_AUTH is None:
        mcp.run(transport="streamable-http", host=host, port=port)
        return

    import uvicorn

    uvicorn.Server(
        uvicorn.Config(
            construir_app_http(mcp, CONFIG_AUTH),
            host=host,
            port=port,
            log_level=mcp.settings.log_level.lower(),
        )
    ).run()


if __name__ == "__main__":
    main()
