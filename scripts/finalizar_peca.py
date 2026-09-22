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
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import capability_registry as cr  # noqa: E402
import docx_block_engine as be  # noqa: E402
import docx_fidelidade_independente as fi  # noqa: E402
import docx_round_trip as rt  # noqa: E402
import legal_readiness as lr  # noqa: E402
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

Status = Literal["OK", "REFUSED"]

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
    "ARTIFACT_DELIVERY_FAILED",
})
"""Vocabulário FECHADO (Gate 6.6-C §18/§21) — o adapter MCP nunca
devolve um código fora desta lista, e nenhuma mensagem de erro carrega
stack trace, path privado, identificador GCS ou corpo da requisição."""

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
    "ARTIFACT_DELIVERY_FAILED": "artifact_delivery",
}


def _recusado_por_codigo(error_code: str, motivo: str, capability_id: str | None = None,
                          stage: str | None = None) -> ResultadoFinalizacao:
    return _recusado(stage or _ETAPA_POR_CODIGO[error_code], error_code, motivo, capability_id)


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


def _validar_producao_final(placeholders: dict, estados_blocos: dict, capability_id: str) -> ResultadoFinalizacao | None:
    erros = vs.validar_modo_producao_final(placeholders, estados_blocos)
    if not erros:
        return None
    if any("sentinela de modo ACEITE" in e for e in erros):
        return _recusado("production_final_validation", "SYNTHETIC_SENTINEL_REJECTED",
                          "Valor de aceite/teste detectado — não permitido em modo produção-final.", capability_id)
    return _recusado("production_final_validation", "MISSING_REQUIRED_FIELD",
                      "Placeholder obrigatório ausente ou vazio para esta composição.", capability_id)


# --------------------------------------------------------------- adaptador

def _finalizar_contestacao_irregularidade_consumo(entrada: dict, capacidade: cr.Capacidade) -> ResultadoFinalizacao:
    capability_id = capacidade.capability_id
    placeholders: dict = entrada["placeholders"]
    block_decisions: dict = entrada.get("block_decisions") or {}
    estado_processual: dict = entrada.get("estado_processual") or {}

    try:
        catalogo = carregar_catalogo(CATALOGO_PADRAO)
        validar_catalogo(catalogo)
        schema = carregar_schema(SCHEMA_PADRAO)
    except (OSError, ValueError, ComposicaoAbortada) as e:
        return _recusado("official_model_readiness", "OFFICIAL_MODEL_NOT_READY",
                          "Catálogo/schema institucional do plugin não está em condições de uso.", capability_id)

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
        estados_zonas = be.resolver_estados_zonas(catalogo, estados_blocos, None, estado_processual)
    except ComposicaoAbortada as e:
        codigo, motivo = _classificar_etapa_engine(e.stage)
        return _recusado_por_codigo(codigo, motivo, capability_id)

    erro = _validar_producao_final(placeholders, estados_blocos, capability_id)
    if erro is not None:
        return erro

    resultado_modelo = lr.avaliar_modelo_oficial(SCHEMA_PADRAO, CATALOGO_PADRAO)
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

        relatorio = be.gerar_peca_com_blocos(
            template_efemero, SCHEMA_PADRAO, CATALOGO_PADRAO, placeholders, decisoes_blocos, saida,
            fatos_processuais=estado_processual,
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
                                               nomes=list(placeholders))
        alcancaveis = set(vs.PLACEHOLDERS_SEMPRE_VISIVEIS) | {
            nome for nome, bloco in vs.PLACEHOLDER_BLOCO_DONO.items() if estados_blocos.get(bloco) == "INCLUIR"
        }
        alcancaveis &= set(placeholders)
        divergencias_rt = rt.comparar_round_trip(placeholders, extraido, alcancaveis)
        if divergencias_rt:
            return _recusado("round_trip", "ROUND_TRIP_FAILED",
                              "O conteúdo do documento gerado não corresponde ao rascunho aceito.", capability_id)

        sha256 = hashlib.sha256(documento_bytes).hexdigest()
        return ResultadoFinalizacao(
            status="OK",
            capability_id=capability_id,
            schema_version=capacidade.schema_version,
            documento_bytes=documento_bytes,
            documento_sha256=sha256,
            documento_tamanho=len(documento_bytes),
            filename=FILENAME_POR_CAPACIDADE[capability_id],
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
