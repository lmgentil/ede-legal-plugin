#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preparar_contestacao.py — Core determinístico do Gate 6.5-A.

Objetivo do gate: expor, através do EDE MCP, o primeiro pré-processamento
jurídico REAL (não mais só readiness) — um Pacote de Contexto da
Contestação que o HOST (Claude/ChatGPT) usa para RACIOCINAR e REDIGIR.

FRONTEIRA ARQUITETURAL (mandatória, ADR-0015, este gate):
  HOST   — raciocínio jurídico, síntese estratégica, redação, prosa.
  CORE   — regras institucionais, corpus legal autoritativo, recuperação
           determinística, contrato de template/schema, validação
           determinística, preparação de contexto estruturado,
           proveniência.

Este módulo NUNCA:
  - decide teses, preliminares ou blocos condicionais (isso é do
    estrategista/advogado — INV-RECONVENCAO-AUTORIZACAO-EXPRESSA,
    INV-CORTE-GATE-HUMANO, CLAUDE.md §7);
  - pesquisa jurisprudência ou faz busca externa
    (INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL, CLAUDE.md §10);
  - consulta DataJud/CNJ automaticamente (Gate 6.5-A §11 — decisão
    explícita deste gate, distinta de INV-JUIZO-DATAJUD, que é para a
    geração final do DOCX, fora de escopo aqui);
  - chama um LLM, gera prosa jurídica ou redige qualquer trecho da peça;
  - lê/recebe/armazena documento bruto do caso (PDF/DOCX de petição
    inicial, laudo, TOI) — a extração factual continua tarefa do HOST
    (mesma limitação já documentada em gerar_contestacao.py).

Fail-closed (CLAUDE.md §17): `preparar_contexto_contestacao()` nunca
levanta exceção para uma condição de negócio esperada (readiness ausente,
entrada inválida, limite excedido) — sempre devolve `ResultadoPreparacao`
com `status` explícito. Uma exceção genuína (bug, schema/catálogo do
próprio plugin corrompido) propaga sem mascaramento.

Privacidade (Gate 6.5-A §7/§19): a entrada (fatos, questões jurídicas) é
efêmera por requisição — nunca gravada em disco, nunca adicionada ao RAG,
nunca cacheada, nunca logada. Este módulo não grava arquivo algum.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_block_engine import ComposicaoAbortada, carregar_catalogo, validar_catalogo  # noqa: E402
from docx_context_engine import ContextoAbortada, extrair_contexto  # noqa: E402
from docx_package import PacoteDocxAbortada, extrair_pacote_docx  # noqa: E402
from docx_template_engine import carregar_schema  # noqa: E402
from validate_fatos import validar_fatos  # noqa: E402

import legal_readiness as lr  # noqa: E402

# `rag/legal_validation/models.py` é reaproveitado DIRETAMENTE como
# módulo solto (nunca via `from legal_validation import ...`, que
# passaria por legal_validation/__init__.py -> citation_parser.py ->
# `from search_hybrid import ...` -> pandas/numpy/scikit-learn/pyarrow/
# rank_bm25 inteiros). `models.py` não tem NENHUM import relativo — é
# seguro carregá-lo como módulo top-level via sys.path, sem tocar
# `__init__.py`. Mesma disciplina de footprint mínimo do MCP desde o
# Gate 6.4-A (RNF-CUSTO-001) — nenhuma dependência de análise/busca
# pesada entra por causa deste módulo.
sys.path.insert(0, str(BASE / "rag" / "legal_validation"))
from models import fonte_juridica  # noqa: E402

SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"
RAG_DIR_PADRAO = BASE / "rag"

Status = Literal["OK", "PIPELINE_ABORTED"]

# --------------------------------------------------------------- limites
# Gate 6.5-A §20/§22: nenhum cliente pode pedir um dump irrestrito do
# corpus nem um pacote de tamanho não-determinístico. Todos os limites
# abaixo são deliberadamente pequenos para uma PRIMEIRA versão — ampliar
# exige decisão própria, nunca um valor "generoso por precaução".
MAX_FATOS = 30
MAX_FACT_CHARS = 500
MAX_SOURCE_DOCUMENT_CHARS = 200
MAX_QUESTOES_JURIDICAS = 5
MAX_QUESTAO_CHARS = 120
MAX_FONTES_POR_QUESTAO = 3
MAX_FONTES_TOTAL = 10
MAX_EXCERPT_CHARS = 400
MAX_CONTEXTO_INSTITUCIONAL_CHARS = 300

# Diplomas do corpus de produção — mesma lista de rag/config.yaml
# (`corpus.diplomas`) e de `rag/corpus_manifest.json`, repetida aqui como
# constante fechada (nunca lida de config.yaml, que exigiria pyyaml —
# dependência que o MCP não carrega desde o Gate 6.4-A).
DIPLOMAS = ("CPC", "CC", "CDC", "L8987", "L9427", "REN1000")

# Espelha `rag/legal_validation/source_authority.py::_DEFAULT_AUTORIDADE_
# POR_CORPUS` — reimplementado aqui (não importado) pelo mesmo motivo de
# `models.py` acima: `source_authority.py` tem `from .models import
# AUTHORITY_LEVELS` (import RELATIVO), que só funciona carregado como
# parte do pacote `legal_validation` — e importar o PACOTE aciona
# `__init__.py` -> a cadeia pesada que este módulo existe para evitar.
# Todos os 6 diplomas atuais são compilados oficiais (Planalto/ANEEL);
# ver docstring de source_authority.py para a justificativa completa —
# não duplicada aqui.
AUTORIDADE_POR_DIPLOMA = {d: "OFICIAL" for d in DIPLOMAS}

# Placeholders efetivamente redigidos pela IA (schema.json,
# placeholder_contracts.tipo) — mesma classificação e mesmo motivo de
# scripts/gerar_contestacao.py::TIPOS_GERATIVOS (não importado de lá:
# gerar_contestacao.py importa datajud_client e `from legal_validation
# import validar_citacao`, esta última acionando a mesma cadeia pesada
# acima). Só esses recebem contexto institucional — identificadores/
# valores/marcadores manuais são dado documental determinístico, nunca
# redação da IA.
TIPOS_GERATIVOS = ("TEXTO_TECNICO", "TEXTO_LONGO")

# Regras institucionais determinísticas relevantes à redação — cada uma
# já existe como invariante documentada (CLAUDE.md/SPEC-0001); esta lista
# só as torna legíveis pelo HOST sem que ele precise ler o repositório.
# Nenhuma regra nova é criada aqui (Gate 6.5-A §13: "Do not invent new
# institutional policy").
REGRAS_INSTITUCIONAIS = (
    "INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL: a Contestação nunca "
    "pesquisa jurisprudência (RAG, web ou qualquer outro meio) — só a "
    "legislação do corpus institucional e o texto fixo do modelo.",
    "INV-SINOPSE-ESTRITAMENTE-AUTORAL: a síntese dos fatos é exclusivamente "
    "a narrativa da petição inicial (fatos alegados + pedidos), nunca a "
    "versão ou impugnação da parte ré.",
    "INV-NAO-REPETICAO-FATICA: o mesmo fato técnico não deve ser "
    "reapresentado em vários parágrafos apenas com palavras diferentes — "
    "cada campo narrativo tem função própria e exclusiva.",
    "INV-PARAGRAFO-380: todo parágrafo de conteúdo variável tem no máximo "
    "380 caracteres efetivos (letras/números/pontuação, sem espaços).",
    "INV-NAO-REDUNDANCIA: o limite de parágrafo não pode ser contornado "
    "multiplicando parágrafos artificialmente — cada parágrafo novo deve "
    "acrescentar um elemento argumentativo útil.",
    "INV-CONTESTACAO-SEM-TRAVESSAO: nenhum conteúdo redigido usa o "
    "caractere travessão (—) como recurso estilístico.",
    "INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA: PRESERVAR > COMPLEMENTAR > "
    "CRIAR — o texto fixo do modelo institucional nunca é reescrito, "
    "resumido ou parafraseado; a redação nova só preenche o que falta.",
    "INV-NAO-REDUNDANCIA-NORMATIVA: a redação variável não repete "
    "dispositivo normativo já presente no texto fixo do modelo.",
    "Decisões de inclusão/exclusão de blocos condicionais (teses, "
    "preliminares, Reconvenção) são reservadas ao estrategista/advogado — "
    "este pacote nunca decide isso, só descreve o catálogo disponível.",
    "A estratégia jurídica completa (quando produzida) deve conter as 15 "
    "seções do contrato de estrategista-contestacao-ede: I. Diagnóstico "
    "executivo; II. Fatos relevantes; III. Pedidos do autor; "
    "IV. Preliminares recomendadas; V. Tese central de mérito; "
    "VI. Teses complementares; VII. Teses subsidiárias; "
    "VIII. Fundamentação na REN ANEEL; IX. Fundamentação processual; "
    "X. Impugnação dos pedidos; XI. Provas; XII. Riscos; "
    "XIII. Documentos a destacar; XIV. Pontos que não devem ser "
    "alegados; XV. Estrutura da contestação.",
)


@dataclass(frozen=True)
class ResultadoPreparacao:
    status: Status
    pacote: dict | None = None
    stage: str | None = None
    motivo: str | None = None


def _abortado(stage: str, motivo: str) -> ResultadoPreparacao:
    return ResultadoPreparacao(status="PIPELINE_ABORTED", stage=stage, motivo=motivo)


# ------------------------------------------------------- validação de entrada

def _validar_entrada(entrada: dict) -> ResultadoPreparacao | None:
    """Validação estrutural + limites (Gate 6.5-A §6/§20) — devolve
    `ResultadoPreparacao` de erro, ou `None` quando a entrada é aceitável.
    Nunca decide conteúdo, só forma/tamanho."""
    if not isinstance(entrada, dict):
        return _abortado("input_validation", "entrada deve ser um objeto JSON")

    fatos = entrada.get("fatos")
    if not isinstance(fatos, list) or not fatos:
        return _abortado("input_validation",
                          "'fatos' é obrigatório e deve ser uma lista não vazia "
                          "(contrato de fatos.json, REQ-030: fact + source_document)")
    if len(fatos) > MAX_FATOS:
        return _abortado("input_validation",
                          f"'fatos' excede o limite de {MAX_FATOS} itens por requisição")
    for i, f in enumerate(fatos):
        if isinstance(f, dict):
            if len(str(f.get("fact", ""))) > MAX_FACT_CHARS:
                return _abortado("input_validation",
                                  f"fatos[{i}].fact excede {MAX_FACT_CHARS} caracteres")
            if len(str(f.get("source_document", ""))) > MAX_SOURCE_DOCUMENT_CHARS:
                return _abortado("input_validation",
                                  f"fatos[{i}].source_document excede "
                                  f"{MAX_SOURCE_DOCUMENT_CHARS} caracteres")
    ok, erros = validar_fatos(fatos)
    if not ok:
        return _abortado("input_validation", f"'fatos' estruturalmente inválido: {erros}")

    questoes = entrada.get("questoes_juridicas", [])
    if questoes is None:
        questoes = []
    if not isinstance(questoes, list) or not all(isinstance(q, str) for q in questoes):
        return _abortado("input_validation",
                          "'questoes_juridicas' deve ser uma lista de strings")
    if len(questoes) > MAX_QUESTOES_JURIDICAS:
        return _abortado("input_validation",
                          f"'questoes_juridicas' excede o limite de "
                          f"{MAX_QUESTOES_JURIDICAS} itens por requisição")
    for q in questoes:
        if not q.strip() or len(q) > MAX_QUESTAO_CHARS:
            return _abortado("input_validation",
                              f"questão jurídica inválida ou excede "
                              f"{MAX_QUESTAO_CHARS} caracteres: {q[:40]!r}...")

    estado = entrada.get("estado_processual", {})
    if estado is None:
        estado = {}
    if not isinstance(estado, dict):
        return _abortado("input_validation", "'estado_processual' deve ser um objeto")
    for chave, valor in estado.items():
        if not (isinstance(valor, bool) or valor == "INDETERMINADO"):
            return _abortado("input_validation",
                              f"estado_processual[{chave!r}] deve ser true/false/"
                              f"\"INDETERMINADO\", recebeu {valor!r}")

    return None


# ---------------------------------------------------------- fontes legais

_PALAVRA_RE = re.compile(r"[a-zà-ú0-9]+", re.IGNORECASE)


def _tokens(texto: str) -> set:
    return set(_PALAVRA_RE.findall(texto.lower()))


def _ler_frontmatter(texto: str) -> dict:
    """Parser mínimo do frontmatter YAML plano (chave: valor, sem
    aninhamento) já usado em todo chunk de rag/chunks_*/ — evita
    depender de PyYAML só para isto (mesma disciplina de footprint do
    Gate 6.4-A). Nunca falha: frontmatter ausente/malformado devolve {}."""
    if not texto.startswith("---"):
        return {}
    fim = texto.find("\n---", 3)
    if fim == -1:
        return {}
    bloco = texto[3:fim]
    dados = {}
    for linha in bloco.splitlines():
        if ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        valor = valor.strip().strip('"')
        if valor and valor != "null":
            dados[chave.strip()] = valor
    return dados


def _buscar_fontes_para_questao(questao: str, rag_dir: Path) -> list:
    """Recuperação lexical determinística e limitada (Gate 6.5-A §12):
    pontua cada chunk pela sobreposição de palavras com a questão
    jurídica (contagem simples, sem embeddings/BM25 — aquilo é
    rag/search_hybrid.py, fora do escopo deste MCP por footprint,
    RNF-CUSTO-001) e devolve os `MAX_FONTES_POR_QUESTAO` melhores.
    Nenhum corpus fora dos 6 diplomas institucionais é tocado; nenhuma
    jurisprudência, nenhuma busca externa."""
    termos_questao = _tokens(questao)
    if not termos_questao:
        return []

    candidatos = []
    for diploma in DIPLOMAS:
        dirp = rag_dir / f"chunks_{diploma}"
        if not dirp.is_dir():
            continue
        for arquivo in sorted(dirp.glob("*.md")):
            texto = arquivo.read_text(encoding="utf-8")
            # `chunk_mestre` é o índice/mapa sistemático do diploma, não
            # dispositivo legal — nunca uma fonte citável (achado do
            # smoke test deste gate: seu texto de nota genérica competia
            # em score com dispositivos reais por pura extensão).
            if _ler_frontmatter(texto).get("tipo") == "chunk_mestre":
                continue
            score = len(termos_questao & _tokens(texto))
            if score > 0:
                candidatos.append((score, diploma, arquivo, texto))

    candidatos.sort(key=lambda c: (-c[0], c[1], c[2].name))

    fontes = []
    for score, diploma, arquivo, texto in candidatos[:MAX_FONTES_POR_QUESTAO]:
        meta = _ler_frontmatter(texto)
        corpo = texto.split("\n---", 1)
        corpo_sem_frontmatter = corpo[1] if len(corpo) > 1 and texto.startswith("---") else texto
        excerto = corpo_sem_frontmatter.strip()[:MAX_EXCERPT_CHARS]
        fontes.append(fonte_juridica(
            source_id=f"{diploma}/{arquivo.name}",
            tipo="dispositivo_legal",
            diploma=meta.get("lei", diploma),
            artigo=meta.get("arts_range"),
            texto=excerto,
            fonte="corpus institucional EDE (compilado oficial)",
            authority_level=AUTORIDADE_POR_DIPLOMA.get(diploma, "NAO_VERIFICADA"),
            validation_status="NAO_VALIDADA",
            score_lexical=float(score),
        ))
    return fontes


def _montar_fontes_legais(questoes: list) -> list:
    todas = []
    vistos = set()
    for questao in questoes:
        for fonte in _buscar_fontes_para_questao(questao, RAG_DIR_PADRAO):
            if fonte["source_id"] in vistos:
                continue
            vistos.add(fonte["source_id"])
            todas.append(fonte)
            if len(todas) >= MAX_FONTES_TOTAL:
                return todas
    return todas


# --------------------------------------------------------- catálogo de blocos

def _gate_status_bloco(bloco: dict, estado: dict) -> str:
    """Descreve, sem decidir, a situação do gate factual de um bloco
    (Gate 6.5-A §15: o pacote nunca decide inclusão/exclusão — só
    informa o estado já fornecido). Nunca inventa um estado ausente:
    chave não fornecida é sempre 'estado_nao_informado', nunca tratada
    como false silencioso."""
    chave = None
    if bloco.get("decision_mode") == "state_linked":
        chave = bloco.get("linked_fact")
    elif bloco.get("requires_fact"):
        chave = bloco["requires_fact"].get("key")
    if chave is None:
        return "sem_gate_fatico"
    if chave not in estado:
        return f"estado_nao_informado ({chave})"
    valor = estado[chave]
    if valor == "INDETERMINADO":
        return f"indeterminado ({chave})"
    return f"{'satisfeito' if valor else 'nao_satisfeito'} ({chave}={valor!r})"


def _montar_blocos_modelo(catalogo: dict, estado: dict) -> list:
    resultado = []
    for b in catalogo.get("blocks", []):
        resultado.append({
            "id": b["id"],
            "tag": b["tag"],
            "tipo": b["tipo"],
            "parent": b.get("parent"),
            "children": b.get("children", []),
            "decision_mode": b["decision_mode"],
            "cardinality": b.get("cardinality"),
            "gate_status": _gate_status_bloco(b, estado),
        })
    for z in catalogo.get("zones", []):
        resultado.append({
            "id": z["id"],
            "tag": z["tag"],
            "tipo": "ZONA_COMPLEMENTACAO",
            "parent": z.get("bloco_pai"),
            "children": [],
            "decision_mode": "zona",
            "cardinality": None,
            "requires_facts": z.get("requires_facts", []),
            "gate_status": ", ".join(
                _gate_status_bloco({"requires_fact": {"key": k}}, estado)
                for k in z.get("requires_facts", [])
            ) or "sem_gate_fatico",
        })
    return resultado


# ---------------------------------------------------- contexto institucional

def _obter_contexto_institucional_gerativo(schema: dict, catalogo: dict) -> dict | None:
    """Contexto institucional (título/texto fixo ao redor) só dos
    placeholders GERATIVOS (Gate 6.5-A §14: nunca o DOCX inteiro, nunca
    XML, nunca bytes/caminho do Modelo Oficial — só o contrato
    estrutural necessário à redação). Devolve `None` (nunca aborta o
    pacote inteiro) se a extração falhar por qualquer motivo — o pacote
    ainda é útil sem este campo; `alertas` registra a ausência."""
    try:
        conteudo = lr.adquirir_bytes_modelo_oficial()
    except lr.ModeloOficialIndisponivel:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        pacote_dir = Path(tmp) / "unpacked"
        try:
            caminho_efemero = Path(tmp) / "modelo.docx"
            caminho_efemero.write_bytes(conteudo)
            extrair_pacote_docx(caminho_efemero, pacote_dir)
            document_xml = (pacote_dir / "word" / "document.xml").read_text(encoding="utf-8")
            contexto_completo = extrair_contexto(document_xml, catalogo)
        except (PacoteDocxAbortada, ContextoAbortada, OSError):
            return None

    contratos = schema.get("placeholder_contracts", {})
    resultado = {}
    for nome, ocorrencias in contexto_completo.items():
        if contratos.get(nome, {}).get("tipo") not in TIPOS_GERATIVOS:
            continue
        if not ocorrencias:
            continue
        primeira = ocorrencias[0]
        resultado[nome] = {
            "titulo_secao": primeira.get("titulo"),
            "texto_fixo_anterior": (primeira.get("antes") or "")[:MAX_CONTEXTO_INSTITUCIONAL_CHARS],
            "texto_fixo_posterior": (primeira.get("depois") or "")[:MAX_CONTEXTO_INSTITUCIONAL_CHARS],
            "bloco_ancestral": primeira.get("bloco"),
        }
    return resultado


# ------------------------------------------------------------------- núcleo

def preparar_contexto_contestacao(
    entrada: dict,
    schema_path: Path = SCHEMA_PADRAO,
    catalogo_path: Path = CATALOGO_PADRAO,
) -> ResultadoPreparacao:
    """Núcleo determinístico do Gate 6.5-A — CORE puro, sem I/O de rede
    além da aquisição (já validada) do Modelo Oficial. Chamada pelo
    adapter MCP (`mcp_server/server.py`), que só traduz o resultado —
    nenhuma lógica de negócio vive duplicada no adapter (ADR-0015).

    Ordem deliberada: forma da entrada primeiro (pura, sem I/O), depois
    readiness (envolve GCS/corpus) — uma requisição malformada nunca
    precisa que o sistema esteja pronto para ser rejeitada, e os dois
    tipos de falha (`input_validation` vs `readiness`) ficam
    independentemente testáveis, sem precisar coconfigurar a outra
    condição só para alcançar o `stage` que se quer exercitar."""
    erro_entrada = _validar_entrada(entrada)
    if erro_entrada is not None:
        return erro_entrada

    resultado_rag = lr.avaliar_corpus_rag()
    resultado_modelo = lr.avaliar_modelo_oficial(schema_path, catalogo_path)
    contestacao_pronta = resultado_rag.status == "READY" and resultado_modelo.status == "READY"

    if not contestacao_pronta:
        return _abortado(
            "readiness",
            f"contestacao_status não está READY (rag={resultado_rag.status}, "
            f"modelo_oficial={resultado_modelo.status}) — preparação de "
            f"contexto recusada (fail-closed, nunca produz pacote parcial "
            f"apresentado como completo).",
        )

    try:
        schema = carregar_schema(schema_path)
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
    except (OSError, ValueError, ComposicaoAbortada) as e:
        return _abortado("institutional_schema",
                          f"schema/catálogo institucional do próprio plugin "
                          f"inválido: {e}")

    fatos = entrada["fatos"]
    fatos_normalizados = [
        {
            "fact": f["fact"],
            "source_document": f["source_document"],
            "page": f.get("page"),
            "confidence": f.get("confidence"),
            "tipo": f.get("tipo") or "FATO_DOCUMENTADO",
        }
        for f in fatos
    ]

    questoes = entrada.get("questoes_juridicas") or []
    estado = entrada.get("estado_processual") or {}

    fontes_legais = _montar_fontes_legais(questoes)
    blocos_modelo = _montar_blocos_modelo(catalogo, estado)
    contexto_institucional = _obter_contexto_institucional_gerativo(schema, catalogo)

    alertas = []
    if questoes and not fontes_legais:
        alertas.append("Nenhuma fonte legal do corpus institucional encontrada "
                        "para as questões jurídicas informadas — refine os termos "
                        "ou trate como lacuna a suprir pelo raciocínio do host.")
    if contexto_institucional is None:
        alertas.append("Contexto institucional (texto fixo ao redor dos "
                        "placeholders) não pôde ser extraído nesta chamada — "
                        "o pacote permanece válido sem ele.")
    tipos_presentes = {f.get("tipo") or "FATO_DOCUMENTADO" for f in fatos}
    if tipos_presentes <= {"ALEGACAO_AUTORAL"}:
        alertas.append("Todos os fatos fornecidos são ALEGACAO_AUTORAL (nenhum "
                        "FATO_DOCUMENTADO) — a defesa terá base fática "
                        "predominantemente contestável, não comprovada.")

    pacote = {
        "readiness": {
            "contestacao_status": "READY",
            "rag": resultado_rag.status,
            "modelo_oficial": resultado_modelo.status,
        },
        "fatos_normalizados": fatos_normalizados,
        "questoes_juridicas": questoes,
        "fontes_legais": fontes_legais,
        "blocos_modelo": blocos_modelo,
        "contexto_institucional": contexto_institucional or {},
        "regras_institucionais": list(REGRAS_INSTITUCIONAIS),
        "restricoes": {
            "max_fatos": MAX_FATOS,
            "max_questoes_juridicas": MAX_QUESTOES_JURIDICAS,
            "max_fontes_por_questao": MAX_FONTES_POR_QUESTAO,
            "max_fontes_total": MAX_FONTES_TOTAL,
        },
        "alertas": alertas,
        "proveniencia": {
            "corpus_diplomas": list(DIPLOMAS),
            "modelo_oficial_sha256": os.environ.get(lr.ENV_MODELO_SHA256),
        },
    }
    return ResultadoPreparacao(status="OK", pacote=pacote)
