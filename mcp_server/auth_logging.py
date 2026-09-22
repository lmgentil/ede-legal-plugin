#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server/auth_logging.py — telemetria de segurança SOMENTE METADADO
(Gate 6.3-D2 §11, ADR-0016).

A regra do gate não é "tente não logar segredo"; é "segredo não pode
alcançar o log". Por isso o mecanismo aqui não é uma convenção de uso —
é uma ALLOWLIST FECHADA de campos (`CAMPOS_PERMITIDOS`). Emitir um evento
com qualquer chave fora dela levanta `CampoDeLogProibido` e o evento NÃO
é emitido. Um defeito futuro que tente logar `authorization`, `token`,
`cpf`, `numero_processo` ou o corpo de uma peça falha alto, em vez de
vazar em silêncio.

O que pode ser registrado (e por que é seguro):

  id_correlacao      identificador gerado LOCALMENTE (uuid4), sem relação
                     com identidade do usuário ou do processo judicial;
  evento             categoria fixa e fechada (ver EVENTOS);
  metodo_http        verbo HTTP;
  caminho            caminho da rota (nunca query string);
  status_http        código de status;
  latencia_ms        duração;
  resultado_auth     categoria de autenticação (ver RESULTADOS_AUTH);
  resultado_autz     categoria de autorização (ver RESULTADOS_AUTZ);
  ferramenta         nome da tool MCP cujo dispatch foi TENTADO;
  escopo_exigido     nome do escopo exigido (é constante pública, nunca
                     um segredo — `ede:health` / `ede:legal`);
  issuer             identificador do issuer configurado/observado; é URL
                     pública de metadados OAuth, não credencial;
  audiencias_aceitas QUANTIDADE (1 ou >1), nunca a lista — o gate pede
                     só a visibilidade da condição de migração;
  migracao_audiencia booleano derivado do anterior;
  auth_aplicacao     se a camada OAuth de aplicação está ligada;
  host_canonico      host canônico configurado;
  motivo             categoria fechada de falha (ver MOTIVOS), nunca
                     texto livre vindo do token ou do cliente.

O que NUNCA pode ser registrado — e é estruturalmente impossível, porque
não existe campo na allowlist: JWT bruto, header Authorization, refresh
token, authorization code, client secret, cookie, CPF, CNPJ, nome de
cliente, número de processo, identificador de contrato, sinopse, corpo de
peça, corpo de documento, prompt, texto jurídico gerado.

CLASSIFICAÇÃO DE GRANT TYPE — DELIBERADAMENTE AUSENTE
====================================================
O gate proíbe afirmar "humano" vs "M2M" sem uma claim assinada confiável
que estabeleça isso. O contrato de token deste gate NÃO estabelece grant
type, então NÃO existe campo para ele nesta allowlist e nenhuma
classificação é inventada. Quando (e se) o token passar a carregar uma
claim assinada que estabeleça a distinção, isto volta como decisão
explícita — nunca por inferência a partir de `sub`, `azp` ou formato de
`client_id`.
"""
from __future__ import annotations

import contextvars
import json
import logging
import uuid
from typing import Any, Final

logger = logging.getLogger("ede.mcp.seguranca")

# ------------------------------------------------------- vocabulário fechado

EVENTO_STARTUP: Final = "startup"
EVENTO_REQUISICAO_HTTP: Final = "requisicao_http"
EVENTO_AUTORIZACAO_FERRAMENTA: Final = "autorizacao_ferramenta"
EVENTO_FINALIZACAO_PECA: Final = "finalizacao_peca"

EVENTOS: Final = frozenset({
    EVENTO_STARTUP,
    EVENTO_REQUISICAO_HTTP,
    EVENTO_AUTORIZACAO_FERRAMENTA,
    EVENTO_FINALIZACAO_PECA,
})

AUTH_AUSENTE: Final = "ausente"
AUTH_MALFORMADA: Final = "malformada"
AUTH_INVALIDA: Final = "invalida"
AUTH_OK: Final = "ok"
AUTH_NAO_APLICAVEL: Final = "nao_aplicavel"

RESULTADOS_AUTH: Final = frozenset({
    AUTH_AUSENTE, AUTH_MALFORMADA, AUTH_INVALIDA, AUTH_OK, AUTH_NAO_APLICAVEL,
})

AUTZ_CONCEDIDA: Final = "concedida"
AUTZ_ESCOPO_INSUFICIENTE: Final = "escopo_insuficiente"
AUTZ_NAO_AVALIADA: Final = "nao_avaliada"

RESULTADOS_AUTZ: Final = frozenset({
    AUTZ_CONCEDIDA, AUTZ_ESCOPO_INSUFICIENTE, AUTZ_NAO_AVALIADA,
})

# Categorias fechadas de falha de verificação de token. São RÓTULOS deste
# módulo — nunca a mensagem da exceção da biblioteca, que pode carregar
# fragmento do token ou dado do cliente.
MOTIVO_BEARER_AUSENTE: Final = "bearer_ausente"
MOTIVO_JWT_MALFORMADO: Final = "jwt_malformado"
MOTIVO_CABECALHO_JOSE_PROIBIDO: Final = "cabecalho_jose_proibido"
MOTIVO_ALGORITMO_NAO_PERMITIDO: Final = "algoritmo_nao_permitido"
MOTIVO_KID_AUSENTE: Final = "kid_ausente"
MOTIVO_CHAVE_DESCONHECIDA: Final = "chave_desconhecida"
MOTIVO_JWKS_INDISPONIVEL: Final = "jwks_indisponivel"
MOTIVO_JWKS_MALFORMADO: Final = "jwks_malformado"
MOTIVO_ASSINATURA_INVALIDA: Final = "assinatura_invalida"
MOTIVO_EXPIRADO: Final = "expirado"
MOTIVO_AINDA_NAO_VALIDO: Final = "ainda_nao_valido"
MOTIVO_ISSUER_INVALIDO: Final = "issuer_invalido"
MOTIVO_AUDIENCIA_INVALIDA: Final = "audiencia_invalida"
MOTIVO_AUDIENCIA_AUSENTE: Final = "audiencia_ausente"
MOTIVO_CLAIMS_MALFORMADAS: Final = "claims_malformadas"
MOTIVO_ESCOPO_MALFORMADO: Final = "escopo_malformado"
MOTIVO_PRINCIPAL_INDETERMINADO: Final = "principal_indeterminado"

MOTIVOS: Final = frozenset({
    MOTIVO_BEARER_AUSENTE,
    MOTIVO_JWT_MALFORMADO,
    MOTIVO_CABECALHO_JOSE_PROIBIDO,
    MOTIVO_ALGORITMO_NAO_PERMITIDO,
    MOTIVO_KID_AUSENTE,
    MOTIVO_CHAVE_DESCONHECIDA,
    MOTIVO_JWKS_INDISPONIVEL,
    MOTIVO_JWKS_MALFORMADO,
    MOTIVO_ASSINATURA_INVALIDA,
    MOTIVO_EXPIRADO,
    MOTIVO_AINDA_NAO_VALIDO,
    MOTIVO_ISSUER_INVALIDO,
    MOTIVO_AUDIENCIA_INVALIDA,
    MOTIVO_AUDIENCIA_AUSENTE,
    MOTIVO_CLAIMS_MALFORMADAS,
    MOTIVO_ESCOPO_MALFORMADO,
    MOTIVO_PRINCIPAL_INDETERMINADO,
})

RESULTADO_FINALIZACAO_OK: Final = "OK"
RESULTADO_FINALIZACAO_REFUSED: Final = "REFUSED"

RESULTADOS_FINALIZACAO: Final = frozenset({RESULTADO_FINALIZACAO_OK, RESULTADO_FINALIZACAO_REFUSED})

# Vocabulário FECHADO de `capability_id`, `estagio_finalizacao` e
# `codigo_erro_finalizacao` (Gate 6.6-C, ADR-0018) — DELIBERADAMENTE
# duplicado aqui como rótulos literais, nunca importado de
# `scripts/finalizar_peca.py`: mesma disciplina já aplicada a MOTIVOS
# acima (este módulo não conhece a biblioteca que produz o evento, só o
# vocabulário fechado que decide se o campo pode ser logado). A suíte de
# testes prova que os dois conjuntos permanecem idênticos aos de
# `finalizar_peca.py` (nunca o contrário — Core nunca importa mcp_server).
CAPACIDADES_FINALIZACAO: Final = frozenset({
    "contestacao.irregularidade_consumo",
})

ESTAGIOS_FINALIZACAO: Final = frozenset({
    "capability_resolution",
    "input_validation",
    "production_final_validation",
    "official_model_readiness",
    "template_lock",
    "render",
    "post_render_fidelity",
    "round_trip",
    "artifact_delivery",
})

CODIGOS_ERRO_FINALIZACAO: Final = frozenset({
    "CAPABILITY_NOT_FOUND",
    "CAPABILITY_NOT_READY",
    "INPUT_VALIDATION_FAILED",
    "OFFICIAL_MODEL_NOT_READY",
    "MISSING_REQUIRED_FIELD",
    "MISSING_BLOCK_DECISION",
    "SYNTHETIC_SENTINEL_REJECTED",
    "TEMPLATE_LOCK_FAILED",
    "ROUND_TRIP_FAILED",
    "RENDER_FAILED",
    "ARTIFACT_TOO_LARGE",
    "ARTIFACT_STORAGE_FAILED",
    "ARTIFACT_SIGNING_FAILED",
    "ARTIFACT_DELIVERY_FAILED",
})

CAMPOS_PERMITIDOS: Final = frozenset({
    "evento",
    "id_correlacao",
    "metodo_http",
    "caminho",
    "status_http",
    "latencia_ms",
    "resultado_auth",
    "resultado_autz",
    "ferramenta",
    "escopo_exigido",
    "issuer",
    "audiencias_aceitas",
    "migracao_audiencia",
    "auth_aplicacao",
    "host_canonico",
    "motivo",
    "capability_id",
    "resultado_finalizacao",
    "estagio_finalizacao",
    "codigo_erro_finalizacao",
    "documento_tamanho_bytes",
    "artefato_id",
    "artefato_limpeza_ok",
})
"""Allowlist FECHADA. Acrescentar campo aqui é decisão de segurança
consciente, não detalhe de implementação — qualquer campo novo precisa
ser metadado, nunca conteúdo.

Gate 6.6-C: `capability_id` é identificador estável e público
(`<familia>.<modelo>`, ex. `contestacao.irregularidade_consumo`), nunca
dado de caso — mesma natureza de `ferramenta`/`escopo_exigido`.
`documento_tamanho_bytes` é só a contagem de bytes do artefato final,
nunca o conteúdo; ausente em toda resposta `REFUSED` (nenhum documento
existe para medir).

Gate 6.6-E: `artefato_id` é o identificador OPACO (uuid4 hex) do objeto
GCS efêmero — nunca o nome do objeto (`artifacts/<id>.docx`), nunca o
bucket, nunca a URL assinada (assinada ou não); presente só quando há um
artefato de fato criado (sucesso, ou recusa por `ARTIFACT_SIGNING_
FAILED` depois de um upload que teve sucesso). `artefato_limpeza_ok`
existe só junto de `ARTIFACT_SIGNING_FAILED` — booleano indicando se o
objeto órfão foi removido; NENHUM dos dois campos é ou pode conter uma
URL: `_registrar_finalizacao` (mcp_server/server.py) não recebe nem
repassa `download_url`/`expires_at` a este módulo, por construção da
própria assinatura da função."""


class CampoDeLogProibido(ValueError):
    """Tentativa de emitir evento de segurança com campo fora da
    allowlist. Fail-closed: o evento não é emitido."""


# -------------------------------------------------------- correlação

_id_correlacao: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ede_id_correlacao", default=None
)


def novo_id_correlacao() -> str:
    """Identificador gerado localmente. Nunca derivado de header do
    cliente: um `X-Request-Id` controlado pelo chamador poderia ser usado
    para injetar conteúdo no log."""
    return uuid.uuid4().hex


def definir_id_correlacao(valor: str) -> contextvars.Token[str | None]:
    return _id_correlacao.set(valor)


def limpar_id_correlacao(token: contextvars.Token[str | None]) -> None:
    _id_correlacao.reset(token)


def id_correlacao_atual() -> str | None:
    return _id_correlacao.get()


# ------------------------------------------------------------ emissão

def _validar_valor(campo: str, valor: Any) -> Any:
    if campo == "evento" and valor not in EVENTOS:
        raise CampoDeLogProibido(f"evento desconhecido: {valor!r}")
    if campo == "resultado_auth" and valor not in RESULTADOS_AUTH:
        raise CampoDeLogProibido(f"resultado de autenticação desconhecido: {valor!r}")
    if campo == "resultado_autz" and valor not in RESULTADOS_AUTZ:
        raise CampoDeLogProibido(f"resultado de autorização desconhecido: {valor!r}")
    if campo == "motivo" and valor not in MOTIVOS:
        raise CampoDeLogProibido(
            f"motivo fora do vocabulário fechado: {valor!r}. Motivo nunca é texto livre — "
            f"texto livre é o caminho pelo qual conteúdo do token/cliente chegaria ao log."
        )
    if campo == "capability_id" and valor not in CAPACIDADES_FINALIZACAO:
        raise CampoDeLogProibido(f"capability_id fora do vocabulário fechado: {valor!r}")
    if campo == "resultado_finalizacao" and valor not in RESULTADOS_FINALIZACAO:
        raise CampoDeLogProibido(f"resultado_finalizacao fora do vocabulário fechado: {valor!r}")
    if campo == "estagio_finalizacao" and valor not in ESTAGIOS_FINALIZACAO:
        raise CampoDeLogProibido(f"estagio_finalizacao fora do vocabulário fechado: {valor!r}")
    if campo == "codigo_erro_finalizacao" and valor not in CODIGOS_ERRO_FINALIZACAO:
        raise CampoDeLogProibido(f"codigo_erro_finalizacao fora do vocabulário fechado: {valor!r}")
    if campo == "documento_tamanho_bytes" and (not isinstance(valor, int) or isinstance(valor, bool) or valor < 0):
        raise CampoDeLogProibido(f"documento_tamanho_bytes deve ser um inteiro não negativo: {valor!r}")
    if campo == "artefato_id" and (not isinstance(valor, str) or "/" in valor or len(valor) > 64):
        raise CampoDeLogProibido(
            f"artefato_id deve ser um identificador opaco curto sem barras: {valor!r} "
            f"(uma barra sugeriria um caminho de objeto GCS vazando para o log)."
        )
    if campo == "artefato_limpeza_ok" and not isinstance(valor, bool):
        raise CampoDeLogProibido(f"artefato_limpeza_ok deve ser booleano: {valor!r}")
    return valor


def registrar_evento(evento: str, **campos: Any) -> dict[str, Any]:
    """Emite um evento de segurança somente-metadado e devolve o registro.

    Devolver o dicionário é o que permite à suíte provar, sobre o objeto
    real emitido (não sobre uma string formatada), que nenhum campo
    sensível está presente."""
    registro: dict[str, Any] = {"evento": evento}
    registro.update({chave: valor for chave, valor in campos.items() if valor is not None})

    proibidos = sorted(set(registro) - CAMPOS_PERMITIDOS)
    if proibidos:
        raise CampoDeLogProibido(
            f"campo(s) fora da allowlist de telemetria de segurança: {proibidos}. "
            f"Telemetria do EDE é somente metadado (Gate 6.3-D2 §11)."
        )
    for chave, valor in registro.items():
        _validar_valor(chave, valor)

    if "id_correlacao" not in registro:
        atual = id_correlacao_atual()
        if atual is not None:
            registro["id_correlacao"] = atual

    logger.info("%s", json.dumps(registro, ensure_ascii=False, sort_keys=True))
    return registro
