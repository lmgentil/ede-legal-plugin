#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
finalizar_peca.py — Core determinístico do finalizador genérico
(Gate 6.6-C, ADR-0018).

`entrada estruturada (capability_id + placeholders + decisões de bloco +
estado processual) -> validação de rascunho -> composição de blocos ->
modo produção-final -> render do Modelo Oficial -> fidelidade
independente -> round-trip -> bytes do DOCX`.

Este módulo é CORE puro (nenhum acoplamento a MCP/host) — o adapter
(`mcp_server/server.py`) só traduz Pydantic <-> dict e embrulha o
resultado num `EmbeddedResource`. Nenhuma lógica de negócio duplicada no
adapter (mesma disciplina de `preparar_contestacao.py`, ADR-0015).

SEMPRE modo PRODUÇÃO-FINAL (CLAUDE.md/ADR-0018 §7): este módulo nunca
aceita um parâmetro que relaxe validação, pule uma etapa ou force um
resultado — não existe `skip_validation`/`already_validated`/`force` em
lugar nenhum da assinatura pública. O modo de aceite/teste (que permite
sentinelas explícitas, Gate 6.6-A) é outro caminho de código
inteiramente — `scripts/docx_block_engine.gerar_peca_com_blocos`
diretamente, nunca por aqui.

Fail-closed (CLAUDE.md §17): toda condição de negócio esperada devolve
`ResultadoFinalizacao` com `status`/`stage`/`motivo` explícitos — nunca
levanta para o chamador. Uma exceção genuína (bug, corrupção do próprio
catálogo/schema do plugin) propaga sem mascaramento, mesma disciplina de
`preparar_contestacao.py`.

Privacidade: bytes do DOCX nunca são logados; o caminho temporário do
arquivo gerado é sempre apagado no `finally`, nunca reaproveitado entre
chamadas, nunca um path estável."""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(BASE / "skills" / "calendario-forense-tjba-2026" / "scripts"))

import artifact_storage as ast  # noqa: E402
import capability_registry as cr  # noqa: E402
import datajud_client  # noqa: E402
import dados_derivados as dd  # noqa: E402
import proveito_economico as pe  # noqa: E402
import tempestividade_texto as tt  # noqa: E402
import zonas_conteudo as zc  # noqa: E402
from calcular_tempestividade import (INTEMPESTIVO, PENDENTE, calcular_tempestividade,  # noqa: E402
                                     derivar_publicacao)
from docx_context_engine import ContextoAbortada, extrair_contexto_do_template  # noqa: E402
from validate_fatos import normalizar_conteudo_zona  # noqa: E402
import docx_block_engine as be  # noqa: E402
import docx_fidelidade_independente as fi  # noqa: E402
import docx_round_trip as rt  # noqa: E402
import legal_readiness as lr  # noqa: E402
import modelo_oficial_versoes as mov  # noqa: E402
import topic_matrix as tm  # noqa: E402
import validate_paragrafos as vp  # noqa: E402
import validate_placeholder_semantics as vs  # noqa: E402
from docx_block_engine import ComposicaoAbortada, carregar_catalogo, validar_catalogo  # noqa: E402
from docx_package import PacoteDocxAbortada, extrair_pacote_docx  # noqa: E402
from docx_template_engine import carregar_schema  # noqa: E402

SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"

MAX_DOCX_BYTES = 8 * 1024 * 1024
"""Teto v1 de entrega inline (Gate 6.6-B/6.6-C, ADR-0018) — acima disso,
o documento nunca é codificado em base64; a resposta é `ARTIFACT_TOO_
LARGE` sem nenhum byte do conteúdo."""

# Defesa em profundidade no PERÍMETRO (schema Pydantic de
# `mcp_server/server.py`, reaproveitado de lá — mesma disciplina de
# `PrepararContestacaoEntrada`/`preparar_contestacao.MAX_FACT_CHARS`,
# nunca um número solto redeclarado no adapter). Generoso e genérico —
# muito acima de qualquer valor legítimo de um único placeholder (maior
# `max_total_chars` declarado em `validate_paragrafos.LIMITES_DENSIDADE_
# BLOCO` é 700) e não hardcoded à contagem exata de campos de UMA
# capacidade hoje (19 placeholders, 8 decisões, 2 fatos), para não
# obrigar reabrir este número a cada capacidade nova. A validação
# ESTRUTURAL de verdade (380/densidade/semântica/produção-final) é
# sempre a de `_validar_rascunho_estruturado`/`_validar_producao_final`
# acima — nunca este teto.
MAX_PLACEHOLDER_CHARS = 5000
MAX_CHAVES_POR_DICIONARIO_ENTRADA = 64

FILENAME_POR_CAPACIDADE = {
    "contestacao.irregularidade_consumo": "EDE-Contestacao-Irregularidade.docx",
}
"""Nome de arquivo NEUTRO e determinístico, por capacidade (Gate 6.6-C
§15) — nunca nome de parte, número de processo, CPF/CNPJ. Não há chave de
objeto de armazenamento no v1 (entrega inline, sem persistência) que
pudesse vazar isso; o nome de arquivo é só metadado de exibição para o
cliente."""

# ------------------------------------------------------------------ erros

Status = Literal["OK", "REFUSED", "NEEDS_INPUT"]
"""`NEEDS_INPUT` (ADR-0020): falta uma resposta SIM/NÃO da Topic Matrix
ou o suporte factual de um tópico marcado SIM — nunca documento, nunca
inclusão silenciosa; `pendencias` diz, em linguagem jurídica, o que
perguntar ao advogado. Desde a ADR-0021 também: data de disponibilização
ausente, resultado intempestivo, DataJud indisponível (sem confirmação)
ou divergente da confirmação do advogado."""

CODIGOS_ERRO = frozenset({
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
    "ARTIFACT_DELIVERY_FAILED",
    "DERIVED_DATA_UNAVAILABLE",
})
"""Vocabulário FECHADO (Gate 6.6-C §18/§21; Gate 6.6-E acrescentou
ARTIFACT_STORAGE_FAILED) — o adapter MCP nunca devolve um código fora
desta lista, e nenhuma mensagem de erro carrega stack trace, path
privado, identificador GCS/bucket/objeto, token de download ou corpo da
requisição. ARTIFACT_STORAGE_FAILED é entrega efêmera não configurada ou
upload ao bucket falhou (nenhum link é devolvido).
ARTIFACT_DELIVERY_FAILED permanece só para a falha pré-existente de
reabrir o DOCX gerado para fidelidade independente.
DERIVED_DATA_UNAVAILABLE (ADR-0021): um dado que o sistema calcula
(tempestividade, endereçamento) não pôde ser obtido com segurança —
calendário fora da cobertura verificada, processo não localizado no
DataJud etc. Nunca vira "gerar mesmo assim".

Histórico: `ARTIFACT_SIGNING_FAILED` (Gate 6.6-E) existiu enquanto a
entrega dependia de assinatura V4 (`signBlob`); removido do vocabulário
quando a URL V4 exposta foi substituída pela URL opaca servida pelo
próprio EDE (Gate 6.6-F/G, DELIVERY-CLIENT-01) — sem assinatura, esse
modo de falha deixou de existir."""

ETAPAS = frozenset({
    "capability_resolution",
    "input_validation",
    "production_final_validation",
    "official_model_readiness",
    "template_lock",
    "render",
    "post_render_fidelity",
    "round_trip",
    "artifact_delivery",
    "topic_matrix",
    "tempestividade",
    "enderecamento",
    "valor_da_causa",
    "zonas",
})
"""Estágio seguro (Gate 6.6-C §19) — identifica ONDE, nunca O QUÊ (nunca
conteúdo de fato/placeholder)."""


@dataclass(frozen=True)
class ResultadoFinalizacao:
    status: Status
    capability_id: str | None = None
    schema_version: str | None = None
    stage: str | None = None
    error_code: str | None = None
    motivo: str | None = None
    documento_bytes: bytes | None = field(default=None, repr=False)
    documento_sha256: str | None = None
    documento_tamanho: int | None = None
    filename: str | None = None
    warnings: tuple[str, ...] = ()
    download_url: str | None = field(default=None, repr=False)
    """`https://<host canônico do EDE>/download/<token opaco>` (Gate
    6.6-F/G — substitui a URL V4 assinada do GCS, DELIVERY-CLIENT-01).
    Contém a capacidade portadora: `repr=False`, e nunca repassada à
    telemetria. `None` em toda resposta REFUSED; presente sempre que
    `status == "OK"`."""
    download_expires_at: str | None = None
    """ISO-8601 UTC, sufixo 'Z' — momento em que `download_url` deixa de
    autorizar download. Não confundir com exclusão do objeto: o link
    para de funcionar neste instante; o objeto é excluído pela limpeza
    (~24-25h) ou, no pior caso, pelo backstop de lifecycle."""
    pendencias: tuple[str, ...] = ()
    """Só em `NEEDS_INPUT`: perguntas/pendências em linguagem jurídica
    (nunca id de bloco, tag, placeholder ou chave de estado interno)."""
    dados_nao_bloqueantes: tuple[str, ...] = ()
    """Só em `OK`: trechos factuais omitidos por falta de prova (a peça
    foi gerada sem eles; o advogado decide se complementa)."""
    artefato_id: str | None = None
    """`sha256(token)` — identificador do objeto que não permite
    reconstruir o link. NUNCA serializado na resposta pública ao cliente
    MCP; existe só para telemetria somente-metadado."""


def _recusado(stage: str, error_code: str, motivo: str, capability_id: str | None = None) -> ResultadoFinalizacao:
    assert stage in ETAPAS, stage  # defensivo: nunca um estágio inventado ad hoc
    assert error_code in CODIGOS_ERRO, error_code
    return ResultadoFinalizacao(status="REFUSED", capability_id=capability_id,
                                 stage=stage, error_code=error_code, motivo=motivo)


# error_code -> estágio seguro, para os códigos cujo estágio é dedutível
# só a partir do próprio código (todo código aqui só é produzido em UM
# estágio do pipeline). RENDER_FAILED fica de fora deliberadamente: é o
# único código que dois estágios distintos podem produzir (`render` e
# `post_render_fidelity`) — quem levanta RENDER_FAILED nesse segundo
# caso passa o `stage` explicitamente, não por este mapa.
_ETAPA_POR_CODIGO = {
    "CAPABILITY_NOT_FOUND": "capability_resolution",
    "CAPABILITY_NOT_READY": "capability_resolution",
    "INPUT_VALIDATION_FAILED": "input_validation",
    "MISSING_BLOCK_DECISION": "input_validation",
    "MISSING_REQUIRED_FIELD": "production_final_validation",
    "SYNTHETIC_SENTINEL_REJECTED": "production_final_validation",
    "OFFICIAL_MODEL_NOT_READY": "official_model_readiness",
    "TEMPLATE_LOCK_FAILED": "template_lock",
    "ROUND_TRIP_FAILED": "round_trip",
    "ARTIFACT_TOO_LARGE": "artifact_delivery",
    "ARTIFACT_STORAGE_FAILED": "artifact_delivery",
    "ARTIFACT_DELIVERY_FAILED": "artifact_delivery",
}


def _recusado_por_codigo(error_code: str, motivo: str, capability_id: str | None = None,
                          stage: str | None = None) -> ResultadoFinalizacao:
    return _recusado(stage or _ETAPA_POR_CODIGO[error_code], error_code, motivo, capability_id)


def _obter_base_url_download() -> str:
    """Origem pública do link de download (`EDE_ARTEFATOS_DOWNLOAD_BASE_
    URL`, validada pelo Core) — mesmo ponto de injeção de
    `_obter_transporte_artefato`; o cliente MCP nunca a escolhe."""
    return ast.obter_base_url_download_do_ambiente(os.environ)


def _obter_transporte_artefato() -> ast.TransporteArtefato:
    """Ponto único de injeção do transporte de armazenamento (Gate
    6.6-E) — produção resolve `EDE_ARTEFATOS_GCS_BUCKET` do ambiente
    real; testes usam
    `monkeypatch` sobre esta função (mesma disciplina de
    `legal_readiness.adquirir_bytes_modelo_oficial`, nunca variável de
    ambiente vazada entre testes). Nenhum parâmetro público de
    `finalizar_peca()` expõe ou permite escolher o transporte (Gate
    6.6-E §48 — o cliente MCP não escolhe bucket/TTL/modo de entrega)."""
    return ast.obter_transporte_do_ambiente(os.environ)


# ------------------------------------------------- mapeamento de estágios

# Espelha DELIBERADAMENTE a classificação canônica já usada em
# `gerar_contestacao.py::_etapa_template` (mesmos prefixos de
# `etapa`/`e.stage`) — nunca uma segunda taxonomia paralela. Diferença
# única: aqui o resultado é um código de erro público (vocabulário
# fechado, Gate 6.6-C), não um nome de stage interno de auditoria.
_PREFIXOS_BLOCK_COMPOSITION = ("catalogo", "decisao", "sdt_", "tag_", "cardinalidade", "estado")

# Dentro de block_composition: estágios causados pela ENTRADA do cliente
# (decisão/estado_processual) recebem um código acionável pelo cliente;
# os demais (integridade do próprio catálogo/template — nunca algo que o
# cliente possa ter causado) viram OFFICIAL_MODEL_NOT_READY.
_ESTAGIOS_BLOCK_COMPOSITION_CLIENTE = {
    "decisao_ausente": ("MISSING_BLOCK_DECISION", "Decisão obrigatória de bloco condicional ausente."),
    "decisao_indeterminada": ("MISSING_BLOCK_DECISION", "Decisão de bloco condicional permanece indeterminada."),
    "decisao_invalida": ("INPUT_VALIDATION_FAILED", "Decisão de bloco fornecida para um bloco que não aceita decisão manual."),
    "estado_invalido": ("INPUT_VALIDATION_FAILED", "estado_processual contém um valor não reconhecido."),
    "gate_fatico_nao_satisfeito": ("INPUT_VALIDATION_FAILED",
                                    "Inclusão de bloco sem o suporte fático exigido em estado_processual."),
}

_ESTAGIOS_ZONA_CLIENTE = {
    "zona_indeterminada": ("INPUT_VALIDATION_FAILED",
                            "estado_processual contém um fato indeterminado que bloqueia a composição."),
    "zona_incoerente": ("INPUT_VALIDATION_FAILED",
                         "Conteúdo informado para zona cujo tópico não foi incluído ou sem o suporte "
                         "factual exigido."),
}


def _classificar_etapa_engine(etapa: str) -> tuple[str, str]:
    """`etapa` é `ComposicaoAbortada.stage` OU `relatorio['etapa']` de
    `gerar_peca_com_blocos` — mesmo vocabulário nos dois casos (mesma
    função interna produz ambos)."""
    if etapa == "modelo_institucional_desatualizado":
        return "OFFICIAL_MODEL_NOT_READY", "Modelo Oficial não confere com o contrato institucional do catálogo."
    if etapa == "gate_fatico_nao_satisfeito" or etapa.startswith(_PREFIXOS_BLOCK_COMPOSITION):
        if etapa in _ESTAGIOS_BLOCK_COMPOSITION_CLIENTE:
            return _ESTAGIOS_BLOCK_COMPOSITION_CLIENTE[etapa]
        return "OFFICIAL_MODEL_NOT_READY", "Catálogo/template institucional não está em condições de uso."
    if etapa.startswith("zona"):
        if etapa in _ESTAGIOS_ZONA_CLIENTE:
            return _ESTAGIOS_ZONA_CLIENTE[etapa]
        return "OFFICIAL_MODEL_NOT_READY", "Catálogo/template institucional não está em condições de uso."
    if etapa == "template_lock":
        return "TEMPLATE_LOCK_FAILED", "Verificação de integridade do Modelo Oficial reprovou o resultado."
    return "RENDER_FAILED", "Falha ao renderizar a peça."


# ---------------------------------------------------------- validação de entrada

def _validar_forma_entrada(entrada: dict) -> ResultadoFinalizacao | None:
    if not isinstance(entrada, dict):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED", "entrada deve ser um objeto JSON")
    capability_id = entrada.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id:
        return _recusado("capability_resolution", "CAPABILITY_NOT_FOUND", "capability_id ausente ou vazio")
    placeholders = entrada.get("placeholders")
    if not isinstance(placeholders, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in placeholders.items()):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'placeholders' deve ser um objeto {NOME: valor textual}", capability_id)
    block_decisions = entrada.get("block_decisions") or {}
    if not isinstance(block_decisions, dict) or not all(v in ("INCLUIR", "EXCLUIR") for v in block_decisions.values()):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'block_decisions' deve ser {BLOCO_ID: 'INCLUIR'|'EXCLUIR'}", capability_id)
    estado_processual = entrada.get("estado_processual") or {}
    if not isinstance(estado_processual, dict) or not all(
        isinstance(v, bool) or v == "INDETERMINADO" for v in estado_processual.values()
    ):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'estado_processual' deve ser {FATO: true|false|'INDETERMINADO'}", capability_id)
    for campo in ("topicos", "fatos_publicos"):
        valor = entrada.get(campo) or {}
        if not isinstance(valor, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in valor.items()):
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              f"'{campo}' deve ser {{CHAVE_PUBLICA: 'SIM'|'NAO'}}", capability_id)
    # ADR-0021: entradas estruturadas próprias (nunca dentro da Topic Matrix).
    marco = entrada.get("marco_tempestividade")
    if marco is not None and not (isinstance(marco, dict)
                                  and all(isinstance(marco.get(k), str) for k in ("tipo", "data"))):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'marco_tempestividade' deve ser {tipo: 'DISPONIBILIZACAO', data: 'DD/MM/AAAA'}",
                          capability_id)
    pedidos = entrada.get("pedidos_economicos")
    if pedidos is not None and not (isinstance(pedidos, list) and all(isinstance(x, dict) for x in pedidos)):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'pedidos_economicos' deve ser uma lista de {descricao, valor, fonte}", capability_id)
    zonas = entrada.get("zonas")
    if zonas is not None and not (isinstance(zonas, dict)
                                  and isinstance(zonas.get("conteudo") or {}, dict)
                                  and isinstance(zonas.get("base_documental") or [], list)):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'zonas' deve ser {conteudo: {ZONA: {conteudo, fatos}}, base_documental: [...]}",
                          capability_id)
    juizo_confirmado = entrada.get("juizo_confirmado_advogado")
    if juizo_confirmado is not None and not isinstance(juizo_confirmado, str):
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                          "'juizo_confirmado_advogado' deve ser texto", capability_id)
    return None


def _validar_rascunho_estruturado(placeholders: dict, schema: dict, capability_id: str) -> ResultadoFinalizacao | None:
    """Reaproveita os validadores CANÔNICOS já existentes — nenhuma regra
    paralela (parágrafo 380, densidade de bloco, semântica por campo,
    travessão, não-repetição fática). Nunca chamado em modo que relaxe
    qualquer um deles."""
    ok, erros = vp.validar_paragrafos_placeholders(placeholders, schema)
    if not ok:
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED", "; ".join(erros)[:500], capability_id)
    ok, erros = vp.validar_densidade_blocos(placeholders)
    if not ok:
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED", "; ".join(erros)[:500], capability_id)
    ok, erros = vs.validar_semantica(placeholders)
    if not ok:
        return _recusado("input_validation", "INPUT_VALIDATION_FAILED", "; ".join(erros)[:500], capability_id)
    return None


def _validar_producao_final(placeholders: dict, estados_blocos: dict, capability_id: str,
                            bloco_dono_extra: dict | None = None) -> ResultadoFinalizacao | None:
    erros = vs.validar_modo_producao_final(placeholders, estados_blocos, bloco_dono_extra)
    if not erros:
        return None
    if any("sentinela de modo ACEITE" in e for e in erros):
        return _recusado("production_final_validation", "SYNTHETIC_SENTINEL_REJECTED",
                          "Valor de aceite/teste detectado — não permitido em modo produção-final.", capability_id)
    return _recusado("production_final_validation", "MISSING_REQUIRED_FIELD",
                      "Placeholder obrigatório ausente ou vazio para esta composição.", capability_id)


# ------------------------------------------ dados derivados (ADR-0021, V1)

CAMPOS_NOVOS_V1 = ("marco_tempestividade", "pedidos_economicos", "zonas", "juizo_confirmado_advogado")
"""Entradas estruturadas do contrato com manifesto (ADR-0021) — fora da
Topic Matrix por invariante (INV-TOPIC-MATRIX-SO-SIM-NAO)."""

DERIVADOS_ADR_0021 = frozenset({"JUIZO", "TEMPESTIVIDADE_CASO", "LOCAL_DATA", "VALOR_TOTAL_PROVEITO_ECONOMICO"})
"""Placeholders que o finalizador V1 deriva e recusa do host. Outras
partes que o manifesto marca como do Core (ex.: marcadores manuais de
fotos/telas) seguem o tratamento anterior — fora do escopo da ADR-0021."""

TIPOS_MARCO_SUPORTADOS = ("DISPONIBILIZACAO",)
PRAZO_CONTESTACAO_DIAS = 15
FUNDAMENTO_PRAZO = "art. 335 do CPC (procedimento comum)"
MAX_JUIZO_CONFIRMADO_CHARS = 300
MAX_PEDIDOS_ECONOMICOS = pe.MAX_PEDIDOS
MAX_ZONAS = 8
MAX_BASE_DOCUMENTAL = 30


def _agora():
    """Relógio injetável (testes). `None` = agora, em America/Bahia: é a
    data da peça e a data do ato para a tempestividade."""
    return None


def _obter_resolvedor_juizo():
    """Ponto único de injeção do DataJud — testes nunca chamam a API real."""
    return datajud_client.resolver_juizo


def _partes_do_manifesto(manifesto: dict):
    for t in manifesto.get("topicos_decisao_advogado") or []:
        for c in t.get("conteudo") or []:
            yield t, c
    for sec in manifesto.get("secoes_incondicionais") or []:
        for c in sec.get("conteudo") or []:
            yield None, c


def _placeholders_calculados(manifesto: dict) -> set:
    return {c["parte"] for _, c in _partes_do_manifesto(manifesto)
            if c.get("modo") == "CALCULADO_PELO_CORE" and not c["parte"].startswith("ZONA_")}


def _zonas_autorizadas(manifesto: dict) -> set:
    return {c["parte"] for _, c in _partes_do_manifesto(manifesto)
            if c["parte"].startswith("ZONA_") and c.get("modo") == "VARIAVEL_LLM_AUTORIZADA"}


def _placeholders_com_simbolo_no_texto_fixo(manifesto: dict) -> set:
    return {c["parte"] for _, c in _partes_do_manifesto(manifesto) if c.get("simbolo_monetario_no_texto_fixo")}


def _topico_do_proveito(manifesto: dict):
    for t in manifesto.get("topicos_decisao_advogado") or []:
        if t.get("entrada_estruturada") == "pedidos_economicos":
            return t
    return None


def _data_br(d) -> str:
    return d.strftime("%d/%m/%Y")


def _parse_data_br(texto):
    from datetime import datetime as _dt
    try:
        return _dt.strptime(str(texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _derivar_tempestividade(marco, hoje, capability_id):
    """-> (texto | None, pendencia | None, recusa | None). Intempestivo
    nunca gera texto nem peça: vira pendência com marco, publicação e
    termo final (ADR-0021, Decisão 4)."""
    from datetime import date as _date
    if not marco:
        return None, ("Informe a data de disponibilização da intimação/citação no Diário de Justiça "
                      "eletrônico (DD/MM/AAAA), para o cálculo da tempestividade."), None
    if marco.get("tipo") not in TIPOS_MARCO_SUPORTADOS:
        return None, None, _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                                     "marco_tempestividade: nesta versão só o tipo DISPONIBILIZACAO é suportado.",
                                     capability_id)
    disponibilizacao = _parse_data_br(marco.get("data"))
    if disponibilizacao is None:
        return None, None, _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                                     "marco_tempestividade: data inválida; use DD/MM/AAAA.", capability_id)
    if disponibilizacao > hoje:
        return None, None, _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                                     "marco_tempestividade: a data de disponibilização é posterior à data atual.",
                                     capability_id)
    publicacao, motivo = derivar_publicacao(disponibilizacao)
    if publicacao is None:
        return None, None, _recusado("tempestividade", "DERIVED_DATA_UNAVAILABLE",
                                     f"Tempestividade não calculada: {motivo}.", capability_id)
    r = calcular_tempestividade(data_pratica_ato=hoje, data_publicacao=publicacao,
                                prazo_legal_dias=PRAZO_CONTESTACAO_DIAS, tipo_prazo="uteis",
                                fundamento_normativo=FUNDAMENTO_PRAZO, verificar_cobertura=True)
    if r.status == PENDENTE:
        return None, None, _recusado("tempestividade", "DERIVED_DATA_UNAVAILABLE",
                                     f"Tempestividade não calculada: {r.motivo_pendencia}.", capability_id)
    if r.status == INTEMPESTIVO:
        termo_final = _date.fromisoformat(r.termo_final)
        return None, (f"Pelo cálculo automático, com disponibilização em {_data_br(disponibilizacao)} e "
                      f"publicação em {_data_br(publicacao)}, o prazo de 15 (quinze) dias úteis para a "
                      f"contestação (art. 335 do CPC) encerrou-se em {_data_br(termo_final)}. A peça não "
                      f"foi gerada: confirme a data de disponibilização informada ou decida como "
                      f"prosseguir."), None
    return tt._redigir_tempestividade_natural(r), None, None


def _derivar_juizo(numero_processo, confirmado, capability_id):
    """-> (juizo | None, pendencia | None, recusa | None, aviso | None).
    DataJud respondendo é autoritativo; confirmação humana só vale se ele
    estiver indisponível NESTA chamada (ADR-0021, exceção da
    INV-JUIZO-DATAJUD)."""
    resolver = _obter_resolvedor_juizo()
    confirmado = (confirmado or "").strip()
    try:
        with tempfile.TemporaryDirectory() as tmp:  # sem cache persistente entre requisições
            juizo = resolver(numero_processo, cache_path=Path(tmp) / "juizo_cache.json")["juizo"]
    except datajud_client.JuizoResolutionError as e:
        if e.codigo == datajud_client.TAG_INDISPONIVEL:
            if confirmado:
                return (confirmado, None, None,
                        "O DataJud/CNJ estava indisponível; o endereçamento usado foi o confirmado pelo advogado.")
            return None, ("O serviço DataJud/CNJ está indisponível no momento, e o endereçamento não pôde ser "
                          "obtido automaticamente. Tente novamente mais tarde ou confirme a unidade judiciária "
                          "(juízo e comarca) do processo."), None, None
        if e.codigo == datajud_client.TAG_ERRO_AUTENTICACAO:
            motivo = "O DataJud/CNJ recusou a credencial pública do sistema; é necessária atualização do plugin."
        else:
            motivo = f"Endereçamento não identificado com segurança pelo DataJud/CNJ: {e.motivo}"
        return None, None, _recusado("enderecamento", "DERIVED_DATA_UNAVAILABLE", motivo[:500], capability_id), None
    if confirmado and confirmado.upper() != juizo.strip().upper():
        return None, (f"O endereçamento obtido do DataJud/CNJ (\"{juizo}\") diverge do confirmado "
                      f"(\"{confirmado}\"). O DataJud está respondendo normalmente; confirme qual é o "
                      f"correto antes de prosseguir."), None, None
    return juizo, None, None, None


def _derivar_proveito(pedidos, valor_da_causa, capability_id):
    """-> (valor_total_formatado, cumulacao, aviso), ou uma recusa."""
    try:
        r = pe.calcular_proveito(pedidos, valor_da_causa)
    except pe.EntradaProveitoInvalida as e:
        return _recusado("valor_da_causa", "INPUT_VALIDATION_FAILED", f"pedidos_economicos: {e}", capability_id)
    if r.pedidos_quantificados == 0:
        return _recusado("valor_da_causa", "MISSING_REQUIRED_FIELD",
                         "Nenhum pedido com valor quantificado na petição inicial; o proveito econômico não "
                         "pode ser calculado a partir dos autos.", capability_id)
    return pe.formatar_brl(r.total), r.cumulacao_economica, f"Impugnação ao valor da causa: {r.resumo()}"


# --------------------------------------------------------------- adaptador

def _finalizar_contestacao_irregularidade_consumo(entrada: dict, capacidade: cr.Capacidade) -> ResultadoFinalizacao:
    capability_id = capacidade.capability_id
    placeholders: dict = entrada["placeholders"]
    block_decisions: dict = entrada.get("block_decisions") or {}
    estado_processual: dict = entrada.get("estado_processual") or {}

    # ADR-0020: o contrato (catálogo + manifesto) é o da versão do Modelo
    # Oficial pinada no ambiente — nunca escolhido pelo cliente.
    versao = mov.resolver_versao_do_ambiente()
    try:
        manifesto = mov.carregar_manifesto(versao)
        catalogo = carregar_catalogo(versao.catalogo_path)
        validar_catalogo(catalogo)
        schema = carregar_schema(SCHEMA_PADRAO)
        if manifesto is not None:
            tm.verificar_compatibilidade(manifesto, catalogo)
    except (OSError, ValueError, ComposicaoAbortada, mov.IntegridadeVersaoModelo, tm.ManifestoIncompativel):
        return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                          "Catálogo/schema institucional do plugin não está em condições de uso.", capability_id)

    topicos: dict = entrada.get("topicos") or {}
    fatos_publicos: dict = entrada.get("fatos_publicos") or {}
    novos = [c for c in CAMPOS_NOVOS_V1 if entrada.get(c) not in (None, "", [], {})]
    avisos: list = []
    conteudo_zonas: dict = {}
    base_documental: list = []
    textos_zonas_previos: dict = {}
    simbolo_no_texto_fixo: set = set()
    if manifesto is None:
        if topicos or fatos_publicos or novos:
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              "O Modelo Oficial configurado não usa a matriz de tópicos nem as entradas "
                              "estruturadas; informe as decisões em 'block_decisions'.", capability_id)
    else:
        if block_decisions:
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              "Com o Modelo Oficial configurado, as decisões são informadas por tópico "
                              "('topicos', SIM/NAO), nunca por bloco.", capability_id)

        # ADR-0021: o que o sistema calcula nunca vem do host.
        calculados = DERIVADOS_ADR_0021
        if not calculados <= _placeholders_calculados(manifesto):
            return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                              "Manifesto não declara como calculados pelo Core os campos que o sistema deriva.",
                              capability_id)
        enviados = sorted(calculados & set(placeholders))
        if enviados:
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              f"Os campos {enviados} são calculados pelo sistema e não devem ser enviados "
                              f"pelo host.", capability_id)
        reservados = sorted(set(manifesto.get("estados_reservados_ao_core") or []) & set(estado_processual))
        if reservados:
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              f"Os estados {reservados} são derivados pelo sistema e não devem ser enviados "
                              f"pelo host.", capability_id)

        # Zonas: só as autorizadas pelo manifesto; a validação completa
        # (proveniência, limites, semântica, continuidade) roda depois,
        # quando o texto institucional adjacente já pode ser lido.
        zonas_in = entrada.get("zonas") or {}
        conteudo_zonas = dict(zonas_in.get("conteudo") or {})
        base_documental = list(zonas_in.get("base_documental") or [])
        nao_autorizadas = sorted(set(conteudo_zonas) - _zonas_autorizadas(manifesto))
        if nao_autorizadas:
            return _recusado("zonas", "INPUT_VALIDATION_FAILED",
                              f"Zona(s) não autorizada(s) pelo manifesto: {nao_autorizadas}.", capability_id)
        if len(conteudo_zonas) > MAX_ZONAS or len(base_documental) > MAX_BASE_DOCUMENTAL:
            return _recusado("zonas", "INPUT_VALIDATION_FAILED", "Entrada de zonas acima do limite.", capability_id)
        textos_zonas_previos = {z: normalizar_conteudo_zona(v)[0] for z, v in conteudo_zonas.items()}
        if any(textos_zonas_previos.values()) and not base_documental:
            return _recusado("zonas", "INPUT_VALIDATION_FAILED",
                              "Conteúdo de zona exige a base documental do caso (fatos com fonte).", capability_id)

        traducao = tm.traduzir(manifesto, catalogo, topicos, fatos_publicos, estado_processual)
        if traducao.status == "INVALID":
            return _recusado("input_validation", "INPUT_VALIDATION_FAILED",
                              "; ".join(traducao.erros)[:500], capability_id)
        if traducao.status == "NEEDS_INPUT":
            return ResultadoFinalizacao(
                status="NEEDS_INPUT", capability_id=capability_id, stage="topic_matrix",
                motivo="Faltam decisões ou suporte factual para compor a peça.",
                pendencias=traducao.pendencias,
            )
        block_decisions = traducao.block_decisions
        estado_processual = dict(traducao.estado_processual_motor)
        avisos.extend(traducao.avisos)
        placeholders = dict(placeholders)
        simbolo_no_texto_fixo = _placeholders_com_simbolo_no_texto_fixo(manifesto)

        # Proveito econômico (tópico com entrada estruturada `pedidos_economicos`).
        topico_proveito = _topico_do_proveito(manifesto)
        pedidos = entrada.get("pedidos_economicos") or []
        if topico_proveito is not None and topicos.get(topico_proveito["chave"]) == "SIM":
            if not pedidos:
                return _recusado("valor_da_causa", "MISSING_REQUIRED_FIELD",
                                  "Com a impugnação ao valor da causa, informe em 'pedidos_economicos' os pedidos "
                                  "extraídos da petição inicial, com valor e fonte.", capability_id)
            if not str(placeholders.get("VALOR_DA_CAUSA") or "").strip():
                return _recusado("valor_da_causa", "MISSING_REQUIRED_FIELD",
                                  "Valor atribuído à causa ausente.", capability_id)
            resultado = _derivar_proveito(pedidos, placeholders["VALOR_DA_CAUSA"], capability_id)
            if isinstance(resultado, ResultadoFinalizacao):
                return resultado
            total, cumulacao, aviso = resultado
            placeholders["VALOR_TOTAL_PROVEITO_ECONOMICO"] = total
            estado_processual["EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS"] = cumulacao
            avisos.append(aviso)
        elif pedidos:
            return _recusado("valor_da_causa", "INPUT_VALIDATION_FAILED",
                              "'pedidos_economicos' informado, mas a impugnação ao valor da causa não foi "
                              "incluída.", capability_id)

        # Tempestividade e endereçamento: pendências juntas, uma pergunta só.
        hoje = dd.hoje_institucional(_agora())
        pendencias, etapa_pendencia = [], None
        texto_tempestividade, pendencia, recusa = _derivar_tempestividade(
            entrada.get("marco_tempestividade"), hoje, capability_id)
        if recusa is not None:
            return recusa
        if pendencia:
            pendencias.append(pendencia)
            etapa_pendencia = "tempestividade"
        numero_processo = str(placeholders.get("NUMERO_PROCESSO") or "").strip()
        if not numero_processo:
            return _recusado("production_final_validation", "MISSING_REQUIRED_FIELD",
                              "Número do processo ausente; é necessário para o endereçamento.", capability_id)
        juizo, pendencia, recusa, aviso = _derivar_juizo(
            numero_processo, entrada.get("juizo_confirmado_advogado"), capability_id)
        if recusa is not None:
            return recusa
        if pendencia:
            pendencias.append(pendencia)
            etapa_pendencia = etapa_pendencia or "enderecamento"
        if aviso:
            avisos.append(aviso)
        if pendencias:
            return ResultadoFinalizacao(
                status="NEEDS_INPUT", capability_id=capability_id, stage=etapa_pendencia,
                motivo="Faltam dados para calcular a tempestividade ou o endereçamento.",
                pendencias=tuple(pendencias),
            )
        placeholders["TEMPESTIVIDADE_CASO"] = texto_tempestividade
        placeholders["JUIZO"] = juizo
        placeholders["LOCAL_DATA"] = f"{dd.LOCAL_INSTITUCIONAL}, {dd.data_por_extenso(hoje)}"

    erro = _validar_rascunho_estruturado(placeholders, schema, capability_id)
    if erro is not None:
        return erro

    decisoes_blocos = {bid: {"decisao": estado} for bid, estado in block_decisions.items()}
    try:
        estados_blocos = be.validar_e_resolver_decisoes(catalogo, decisoes_blocos, estado_processual)
    except ComposicaoAbortada as e:
        codigo, motivo = _classificar_etapa_engine(e.stage)
        return _recusado_por_codigo(codigo, motivo, capability_id)

    try:
        estados_zonas = be.resolver_estados_zonas(catalogo, estados_blocos, textos_zonas_previos or None,
                                                  estado_processual)
    except ComposicaoAbortada as e:
        codigo, motivo = _classificar_etapa_engine(e.stage)
        return _recusado_por_codigo(codigo, motivo, capability_id)

    erro = _validar_producao_final(placeholders, estados_blocos, capability_id,
                                   versao.placeholder_bloco_dono_extra)
    if erro is not None:
        return erro

    # PEND-018: onde o texto fixo já traz "R$" antes do placeholder, o valor
    # (validado acima no formato "R$ 1.234,56") entra no documento sem o
    # símbolo — declarado no manifesto, nunca adivinhado. Legado inalterado.
    placeholders_render = {
        k: (re.sub(r"^\s*R\$\s?", "", v) if k in simbolo_no_texto_fixo else v)
        for k, v in placeholders.items()
    }

    resultado_modelo = lr.avaliar_modelo_oficial(SCHEMA_PADRAO, versao.catalogo_path)
    if resultado_modelo.status != "READY":
        return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                          f"Modelo Oficial não está pronto (status={resultado_modelo.status}).", capability_id)

    try:
        modelo_bytes = lr.adquirir_bytes_modelo_oficial()
    except lr.ModeloOficialIndisponivel:
        return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                          "Modelo Oficial não pôde ser adquirido do armazenamento configurado.", capability_id)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        template_efemero = tmp / "modelo-oficial.docx"
        template_efemero.write_bytes(modelo_bytes)
        saida = tmp / "peca-finalizada.docx"

        texto_por_zona = None
        if any(textos_zonas_previos.values()):
            try:
                contexto = extrair_contexto_do_template(template_efemero, versao.catalogo_path)
            except (ContextoAbortada, ComposicaoAbortada):
                return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                                  "Contexto institucional das zonas não pôde ser lido do Modelo Oficial.",
                                  capability_id)
            texto_por_zona, _, erro_zonas = zc.validar_conteudo_zonas(
                conteudo_zonas, catalogo, base_documental, contexto)
            if erro_zonas is not None:
                return _recusado("zonas", "INPUT_VALIDATION_FAILED", erro_zonas[:500], capability_id)

        relatorio = be.gerar_peca_com_blocos(
            template_efemero, SCHEMA_PADRAO, versao.catalogo_path, placeholders_render, decisoes_blocos, saida,
            fatos_processuais=estado_processual, conteudo_zonas=texto_por_zona,
        )
        if relatorio["status"] != "OK":
            etapa_engine = relatorio.get("etapa", "")
            codigo, motivo = _classificar_etapa_engine(etapa_engine)
            stage = "render" if codigo == "RENDER_FAILED" else None
            return _recusado_por_codigo(codigo, motivo, capability_id, stage=stage)

        documento_bytes = saida.read_bytes()
        if len(documento_bytes) > MAX_DOCX_BYTES:
            return _recusado("artifact_delivery", "ARTIFACT_TOO_LARGE",
                              f"Documento gerado ({len(documento_bytes)} bytes) excede o limite de "
                              f"entrega inline ({MAX_DOCX_BYTES} bytes).", capability_id)

        try:
            unpacked_template = tmp / "template_unpacked"
            unpacked_gerado = tmp / "gerado_unpacked"
            extrair_pacote_docx(template_efemero, unpacked_template)
            extrair_pacote_docx(saida, unpacked_gerado)
            template_xml = (unpacked_template / "word" / "document.xml").read_text(encoding="utf-8")
            gerado_xml = (unpacked_gerado / "word" / "document.xml").read_text(encoding="utf-8")
        except (PacoteDocxAbortada, OSError):
            return _recusado_por_codigo("RENDER_FAILED",
                                         "Documento gerado não pôde ser reaberto para verificação.",
                                         capability_id, stage="post_render_fidelity")

        divergencias = fi.verificar_sequencia_locked(template_xml, gerado_xml, catalogo, estados_blocos, estados_zonas)
        divergencias += fi.verificar_sdts_bloco(gerado_xml, catalogo, estados_blocos)
        divergencias += [f"token residual: {t}" for t in fi.escanear_tokens_residuais(gerado_xml)]
        if divergencias:
            return _recusado_por_codigo("RENDER_FAILED",
                                         "Verificação independente de fidelidade reprovou o documento gerado.",
                                         capability_id, stage="post_render_fidelity")

        extraido = rt.extrair_valores_gerados(template_xml, gerado_xml, catalogo, estados_blocos, estados_zonas,
                                               nomes=list(placeholders_render))
        sempre_visiveis, bloco_dono = vs.placeholders_por_visibilidade(versao.placeholder_bloco_dono_extra)
        alcancaveis = set(sempre_visiveis) | {
            nome for nome, bloco in bloco_dono.items() if estados_blocos.get(bloco) == "INCLUIR"
        }
        alcancaveis &= set(placeholders_render)
        divergencias_rt = rt.comparar_round_trip(placeholders_render, extraido, alcancaveis)
        if divergencias_rt:
            return _recusado("round_trip", "ROUND_TRIP_FAILED",
                              "O conteúdo do documento gerado não corresponde ao rascunho aceito.", capability_id)

        sha256 = hashlib.sha256(documento_bytes).hexdigest()
        filename = FILENAME_POR_CAPACIDADE[capability_id]

        # Entrega v2 (Gate 6.6-E, ADR-0019; URL opaca desde o Gate
        # 6.6-F/G). Envia exatamente `documento_bytes` (já aprovado por
        # Template Lock/fidelidade/round-trip acima, nunca reaberto/
        # reconstruído) a um objeto GCS privado e efêmero e devolve
        # `https://<host do EDE>/download/<token>` — o próprio EDE serve
        # o objeto, conferindo o SHA-256 antes de entregar.
        try:
            entrega = ast.entregar_artefato_efemero(
                documento_bytes, sha256, filename,
                transporte=_obter_transporte_artefato(), base_url=_obter_base_url_download(),
            )
        except ast.ErroConfiguracaoArtefato:
            return _recusado("artifact_delivery", "ARTIFACT_STORAGE_FAILED",
                              "Armazenamento efêmero de artefatos não está configurado.", capability_id)
        except ast.ErroArmazenamentoArtefato:
            return _recusado("artifact_delivery", "ARTIFACT_STORAGE_FAILED",
                              "Falha ao armazenar o artefato gerado.", capability_id)

        # Limpeza oportunista (Gate 6.6-E, continuação §8/§9) —
        # exclusão NORMAL de artefatos antigos, best-effort: dispara só
        # depois que ESTA finalização já tem uma resposta de sucesso
        # pronta. Qualquer falha aqui (rede, autenticação, listagem)
        # nunca reverte nem degrada a resposta já bem-sucedida — o
        # backstop de lifecycle (~1 dia) continua ativo independente
        # disso. Resultado agregado (contadores, nunca nome de objeto)
        # fica disponível só para telemetria futura, se necessário.
        try:
            ast.limpar_artefatos_elegiveis(_obter_transporte_artefato())
        except Exception:
            pass

        return ResultadoFinalizacao(
            status="OK",
            capability_id=capability_id,
            schema_version=capacidade.schema_version,
            documento_bytes=documento_bytes,
            documento_sha256=sha256,
            documento_tamanho=len(documento_bytes),
            filename=filename,
            download_url=entrega.download_url,
            download_expires_at=entrega.expires_at,
            artefato_id=entrega.artefato_id,
            dados_nao_bloqueantes=(tm.dados_nao_bloqueantes(manifesto, estados_blocos) + tuple(avisos)
                                   if manifesto else ()),
        )


_ADAPTADORES = {
    "contestacao.irregularidade_consumo": _finalizar_contestacao_irregularidade_consumo,
}
"""Um adaptador por capacidade `READY` — nunca um `if`/`elif` genérico
espalhado; capacidade nova = nova entrada aqui, nunca reescrita do
despacho. A CAMADA DE ENTREGA (tamanho, SHA, `filename`, resposta MCP)
fica fora do adaptador, em `finalizar_peca()` abaixo — o adaptador só
devolve bytes/erro (ADR-0018, separação de conhecimento jurídico x
entrega)."""


# ------------------------------------------------------------------- núcleo

def finalizar_peca(entrada: dict) -> ResultadoFinalizacao:
    """Ponto de entrada único do finalizador genérico. SEMPRE modo
    produção-final — não existe parâmetro que mude isso."""
    erro = _validar_forma_entrada(entrada)
    if erro is not None:
        return erro

    capability_id = entrada["capability_id"]
    capacidade = cr.obter_capacidade(capability_id)
    if capacidade is None:
        return _recusado("capability_resolution", "CAPABILITY_NOT_FOUND",
                          f"Capacidade desconhecida: {capability_id!r}", capability_id)
    if capacidade.status != "READY":
        return _recusado("capability_resolution", "CAPABILITY_NOT_READY",
                          f"Capacidade {capability_id!r} não está pronta (status={capacidade.status}).",
                          capability_id)

    adaptador = _ADAPTADORES.get(capability_id)
    if adaptador is None:
        # Defensivo: capacidade READY no registro sem adaptador implementado
        # é inconsistência interna do próprio plugin, nunca causa do cliente.
        return _recusado("capability_resolution", "CAPABILITY_NOT_READY",
                          f"Capacidade {capability_id!r} não tem implementação disponível.", capability_id)

    return adaptador(entrada, capacidade)
