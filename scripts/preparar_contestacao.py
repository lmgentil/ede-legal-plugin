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

import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_block_engine import ComposicaoAbortada, carregar_catalogo, validar_catalogo  # noqa: E402
from docx_context_engine import ContextoAbortada, extrair_contexto  # noqa: E402
from docx_package import PacoteDocxAbortada, extrair_pacote_docx  # noqa: E402
from docx_template_engine import carregar_schema  # noqa: E402
from validate_fatos import tipo_de, validar_fatos  # noqa: E402

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
    for i, q in enumerate(questoes):
        if not q.strip():
            return _abortado("input_validation",
                              f"questoes_juridicas[{i}] está vazia")
        if len(q) > MAX_QUESTAO_CHARS:
            # Gate 6.5-B3 §16: metadado estrutural (índice, limite,
            # tamanho recebido) — nunca o conteúdo da questão em si. O
            # texto da questão jurídica é conteúdo de requisição, nunca
            # pertence a uma mensagem de erro (mesma disciplina de
            # auth_logging.py, aplicada aqui à validação de entrada).
            return _abortado("input_validation",
                              f"questoes_juridicas[{i}] excede "
                              f"{MAX_QUESTAO_CHARS} caracteres (recebeu {len(q)})")

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

# Gate 6.5-B3 §4/§5: lista fechada de palavras gramaticais (artigos,
# preposições, conjunções, pronomes) e de termos processuais tão
# genéricos que aparecem em praticamente todo chunk do corpus,
# independente do assunto — nenhuma delas carrega poder discriminativo
# de relevância. Achado real (diagnóstico do Gate 6.5-B3): a pontuação
# original (sobreposição bruta, sem filtro) dava peso IDÊNTICO a "de"/
# "da"/"em" e a "irregularidade"/"faturamento", fazendo capítulos longos
# e genéricos (conexão, pré-pagamento, prazos administrativos) superarem
# o capítulo central de Procedimentos Irregulares só por serem mais
# extensos — nunca por serem mais relevantes. Nunca remove palavra de
# conteúdo (substantivo/verbo/adjetivo do domínio) — só função
# gramatical e meta-vocabulário estrutural.
#
# Gate 6.5-C1: a lista sempre foi escrita SEM acento ("nao", "ate", "ja"),
# mas o texto era comparado só com `.lower()` — "não"/"até"/"já" do corpus
# nunca casavam com ela. Agora o texto é normalizado (sem acento) antes
# da comparação, então a lista passa a funcionar como sempre foi escrita.
STOPWORDS_LEXICAS = frozenset({
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "por",
    "para", "com", "sem", "e", "ou", "a", "o", "as", "os", "um", "uma",
    "uns", "umas", "que", "se", "ao", "aos", "seu", "sua", "seus", "suas",
    "este", "esta", "esse", "essa", "isso", "isto", "aquele", "aquela",
    "quando", "como", "mais", "menos", "muito", "tambem", "ja", "nao",
    "nem", "entre", "sobre", "ate", "apos", "antes", "deve", "devera",
    "pode", "podera", "ser", "estar", "ter", "seja", "sejam", "ela", "ele",
    "eles", "elas", "cujo", "cuja", "tal", "qual", "quais", "outro",
    "outra", "outros", "outras", "mesmo", "mesma", "caso", "casos",
    "forma", "conforme", "respectivo", "respectiva", "art", "artigo",
    "paragrafo", "inciso", "alinea", "lei", "resolucao", "referida",
    "referido", "presente", "assim", "dessa", "desse", "nesta", "neste",
    "nessa", "nesse", "sao", "eh", "foi", "foram", "tem", "tinha",
    "havia", "houve", "onde",
})

BONUS_TITULO_POR_TERMO = 2
"""Peso do termo da questão que também aparece no título/capítulo do
chunk (frontmatter `titulo`/`capitulo`) — sinal de relevância mais forte
que ocorrência solta no corpo (Gate 6.5-B3 §5, "title/article-heading
weighting"). Desde o Gate 6.5-C1 o termo vale seu IDF, multiplicado por
este fator."""

BONUS_FRASE_POR_BIGRAMA = 2
"""Peso por bigrama da questão (dois termos de conteúdo consecutivos no
texto original, nunca atravessando uma stopword) que aparece também no
chunk — sinal de correspondência de expressão, não só de palavra solta
(Gate 6.5-B3 §5, "exact-phrase bonuses"). Desde o Gate 6.5-C1 a
comparação é feita sobre radicais (`procedimento irregular` casa com
`procedimentos irregulares`) e o bônus é multiplicado pelo IDF médio do
par."""

PESO_TERMO_EXPANDIDO = 0.5
"""Peso relativo de um termo vindo de `CONCEITOS_JURIDICOS` (Gate 6.5-C1)
em relação a um termo escrito pelo próprio advogado (peso 1). O conceito
só ajuda a alcançar o vocabulário do diploma; nunca pode valer mais que o
que foi de fato perguntado."""

_RE_ARTIGO = re.compile(r"\bArt\.?\s*(\d+)", re.IGNORECASE)
_PALAVRA_RE = re.compile(r"[a-z0-9]+")


def _normalizar(texto: str) -> str:
    """Caixa baixa e sem diacríticos (`apuração` -> `apuracao`). Único
    ponto de normalização do scorer: consulta, título e corpo passam por
    aqui, então "Recuperação" digitada sem acento ainda casa o corpus
    acentuado (e vice-versa)."""
    decomposto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


# Sufixos de plural, do mais longo ao mais curto: (sufixo, substituto).
_PLURAIS = (("coes", "cao"), ("oes", "ao"), ("aes", "ao"), ("ais", "al"),
            ("eis", "el"), ("ores", "or"), ("res", "r"), ("ns", "m"))
_SUFIXOS_DERIVACIONAIS = ("mente", "idade", "cao")
_INFINITIVOS = ("ar", "er", "ir")


def _radical(token: str) -> str:
    """Radical determinístico e deliberadamente CONSERVADOR de um token já
    normalizado (Gate 6.5-C1): plural -> sufixo derivacional (-idade,
    -mente, -ção) -> infinitivo -> vogal temática final. Objetivo único:
    fazer `procedimento`/`procedimentos`, `irregularidade`/`irregulares`/
    `irregular`, `indenização`/`indenizar` e `consumidor`/`consumidora`
    convergirem — nunca análise morfológica geral. Números e tokens
    curtos passam intactos. Não é um stemmer linguístico (sem dicionário,
    sem exceções): erra para o lado de NÃO unir palavras distintas."""
    if len(token) <= 3 or token.isdigit():
        return token
    for sufixo, troca in _PLURAIS:
        if token.endswith(sufixo) and len(token) - len(sufixo) >= 3:
            token = token[: -len(sufixo)] + troca
            break
    else:
        if token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
    for sufixo in _SUFIXOS_DERIVACIONAIS:
        if token.endswith(sufixo) and len(token) - len(sufixo) >= 3:
            token = token[: -len(sufixo)]
            break
    for sufixo in _INFINITIVOS:
        if token.endswith(sufixo) and len(token) - len(sufixo) >= 4:
            token = token[: -len(sufixo)]
            break
    if len(token) > 4 and token[-1] in "aeo":
        token = token[:-1]
    return token


def _sequencia_radicais(texto: str) -> list:
    """Uma entrada por palavra do texto, na ordem original: o radical,
    ou `None` para stopword/token de 1 caractere. `None` preserva o
    "buraco" onde a stopword estava — é ele que impede um bigrama de
    atravessar uma stopword (adjacência que o texto não tem)."""
    saida = []
    for palavra in _PALAVRA_RE.findall(_normalizar(texto)):
        if palavra in STOPWORDS_LEXICAS or len(palavra) <= 1:
            saida.append(None)
        else:
            saida.append(_radical(palavra))
    return saida


def _radicais_uteis(texto: str) -> set:
    return {r for r in _sequencia_radicais(texto) if r}


def _bigramas_radicais(texto: str) -> set:
    """Pares de radicais de palavras CONSECUTIVAS no texto original onde
    nenhuma das duas é stopword (ex.: "de consumo" não vira bigrama;
    "unidade consumidora" vira)."""
    seq = _sequencia_radicais(texto)
    return {f"{a} {b}" for a, b in zip(seq, seq[1:]) if a and b}


# ------------------------------------------------- conceitos jurídicos
# Gate 6.5-C1: tabela PEQUENA, explícita e revisável de aliases de
# domínio. Existe só para transpor uma lacuna de TERMINOLOGIA entre a
# forma como uma questão abstrata é formulada e o vocabulário do
# diploma que trata do assunto (ex.: "proteção do consumidor" nunca
# aparece no título do capítulo "Dos Direitos Básicos do Consumidor").
#
# Regras de uso (todas verificadas por teste):
#   - um conceito só dispara se a questão contiver TODOS os radicais de
#     ao menos um de seus gatilhos — nunca por presença solta de uma
#     palavra genérica;
#   - disparar não inclui NENHUM diploma nem chunk: só acrescenta termos
#     de consulta com peso reduzido (`PESO_TERMO_EXPANDIDO`); a
#     relevância continua sendo textual, medida contra o corpus;
#   - nenhum conceito nomeia diploma: "consumidor -> sempre CDC" e
#     "dano -> sempre CC" são expressamente vedados (Gate 6.5-C1 §5);
#   - um conceito só entra na tabela com EVIDÊNCIA de necessidade: a
#     normalização (acento/plural/derivação), o IDF e a saturação de
#     frequência já resolvem sozinhos a maior parte das lacunas. Ablation
#     do Gate 6.5-C1 sobre 17 paráfrases (irregularidade, consumidor, dano
#     moral): sem tabela nenhuma, 17/17 ainda recuperam a fonte esperada;
#     só "proteção do consumidor" mostrou ganho mensurável (a fonte do CDC
#     sobe de 2º para 1º e o ruído da REN1000 sai do top-3 da questão
#     abstrata). Conceitos de "procedimento irregular" e de
#     "responsabilidade civil/dano" foram avaliados e DESCARTADOS por
#     ganho zero — não reintroduzir sem nova evidência.
CONCEITOS_JURIDICOS = (
    {
        "id": "PROTECAO_DO_CONSUMIDOR",
        "gatilhos": (("protecao", "consumidor"), ("defesa", "consumidor"),
                     ("direitos", "consumidor"), ("relacao", "consumo"),
                     ("relacoes", "consumo")),
        "expansao": ("fornecedor", "servico", "vulnerabilidade",
                     "direitos basicos", "politica nacional", "relacoes consumo"),
    },
)


def _conceitos_compilados() -> tuple:
    """Gatilhos/expansões reduzidos a radicais UMA vez, na mesma função
    (`_radical`) que processa a questão — nunca duas normalizações que
    poderiam divergir."""
    def rad(frase: str) -> tuple:
        return tuple(_radical(p) for p in _PALAVRA_RE.findall(_normalizar(frase)))
    compilados = []
    for c in CONCEITOS_JURIDICOS:
        compilados.append({
            "id": c["id"],
            "gatilhos": [frozenset(rad(" ".join(g))) for g in c["gatilhos"]],
            "expansao": [rad(e) for e in c["expansao"]],
        })
    return tuple(compilados)


_CONCEITOS = _conceitos_compilados()


def _termos_da_consulta(questao: str) -> tuple:
    """Devolve `(pesos, bigramas, conceitos_ativos)`: `pesos` mapeia radical
    -> peso (1 para o que o advogado escreveu; `PESO_TERMO_EXPANDIDO` para
    termo trazido por conceito ativo, e nunca sobrescrevendo um termo
    direto)."""
    diretos = _radicais_uteis(questao)
    pesos = {r: 1.0 for r in diretos}
    ativos = []
    for conceito in _CONCEITOS:
        if any(g and g <= diretos for g in conceito["gatilhos"]):
            ativos.append(conceito["id"])
            for frase in conceito["expansao"]:
                for r in frase:
                    if r and len(r) > 1 and r not in pesos:
                        pesos[r] = PESO_TERMO_EXPANDIDO
    return pesos, _bigramas_radicais(questao), ativos


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


_CACHE_VERSAO_CORPUS: dict = {}


def _versao_corpus(rag_dir: Path) -> str | None:
    """Versão declarada em rag/corpus_manifest.json (Gate 6.5-B3 §10) —
    lida uma vez e cacheada em memória por diretório; nunca falha o
    pacote inteiro se o manifesto estiver ausente/malformado (a
    checagem de READY já validou isso em `avaliar_corpus_rag`; aqui só
    se quer o texto da versão para proveniência, não revalidar)."""
    chave = str(rag_dir)
    if chave not in _CACHE_VERSAO_CORPUS:
        try:
            manifesto = json.loads((rag_dir / "corpus_manifest.json").read_text(encoding="utf-8"))
            _CACHE_VERSAO_CORPUS[chave] = manifesto.get("versao")
        except (OSError, ValueError):
            _CACHE_VERSAO_CORPUS[chave] = None
    return _CACHE_VERSAO_CORPUS[chave]


def _truncar_com_limite_de_frase(texto: str, limite: int) -> tuple:
    """Corta em até `limite` caracteres preferindo o último fim de frase
    (. ; : ! ?) dentro do limite — nunca no meio de uma frase quando um
    ponto de corte melhor existir (Gate 6.5-B3 §8). Devolve
    `(excerto, truncado)`; `truncado=True` sempre que o texto original
    for maior que o excerto devolvido, mesmo quando o corte caiu num
    fim de frase — o host precisa saber que o corpo integral do chunk
    continua além do que foi devolvido."""
    if len(texto) <= limite:
        return texto, False
    bruto = texto[:limite]
    ultimo_fim = -1
    for m in re.finditer(r"[.;:!?](?=\s|$)", bruto):
        ultimo_fim = m.end()
    if ultimo_fim > 0:
        return bruto[:ultimo_fim].rstrip(), True
    corte_palavra = bruto.rfind(" ")
    if corte_palavra > 0:
        return bruto[:corte_palavra].rstrip(), True
    return bruto.rstrip(), True


def _artigo_preciso(excerto: str) -> str | None:
    """Primeiro "Art. N" literal encontrado no EXCERTO efetivamente
    devolvido (Gate 6.5-B3 §7) — nunca inventado, nunca extrapolado do
    range do chunk (`arts_range`, que continua disponível em `artigo`
    como piso menos preciso). `None` quando o excerto não abre nem
    contém um marcador de artigo determinável (ex.: começa num
    parágrafo/inciso que dá sequência a um artigo de um chunk anterior)
    — a limitação fica explícita pela ausência do campo, nunca por um
    número chutado."""
    m = _RE_ARTIGO.search(excerto)
    return m.group(1) if m else None


_CACHE_INDICE_CORPUS: dict = {}


def _indice_corpus(rag_dir: Path) -> dict:
    """Índice lexical em memória do corpus (Gate 6.5-C1), construído uma
    vez por diretório: por chunk, os radicais do texto, do título/capítulo
    e os bigramas; e o IDF de cada radical sobre o corpus inteiro.

    O IDF (`ln(1 + N/df)`) é o que impede vocabulário genérico do SETOR
    ("energia", "elétrica", "distribuidora", presentes em centenas de
    chunks da REN1000) de dominar a pontuação — sem lista manual de
    "palavras do setor", que precisaria de curadoria e nunca seria
    completa: o próprio corpus diz o que é comum. O corpus é asset
    estático da revisão (versionado por `corpus_manifest.json`), então
    o cache nunca serve dado defasado dentro de um processo."""
    chave = str(rag_dir)
    if chave in _CACHE_INDICE_CORPUS:
        return _CACHE_INDICE_CORPUS[chave]

    chunks = []
    df: Counter = Counter()
    for diploma in DIPLOMAS:
        dirp = rag_dir / f"chunks_{diploma}"
        if not dirp.is_dir():
            continue
        for arquivo in sorted(dirp.glob("*.md")):
            texto = arquivo.read_text(encoding="utf-8")
            meta = _ler_frontmatter(texto)
            # `chunk_mestre` é o índice/mapa sistemático do diploma, não
            # dispositivo legal — nunca uma fonte citável (achado do
            # smoke test do Gate 6.5-A: seu texto de nota genérica
            # competia em score com dispositivos reais por pura extensão).
            if meta.get("tipo") == "chunk_mestre":
                continue
            frequencias = Counter(r for r in _sequencia_radicais(texto) if r)
            df.update(frequencias.keys())
            chunks.append({
                "diploma": diploma,
                "arquivo": arquivo,
                "texto": texto,
                "meta": meta,
                "frequencias": frequencias,
                "radicais_titulo": _radicais_uteis(
                    f"{meta.get('titulo', '')} {meta.get('capitulo', '')}"),
                "bigramas": _bigramas_radicais(texto),
            })
    total = max(len(chunks), 1)
    idf = {r: math.log(1 + total / n) for r, n in df.items()}
    indice = {"chunks": chunks, "idf": idf}
    _CACHE_INDICE_CORPUS[chave] = indice
    return indice


TF_SATURACAO_K1 = 2.0
"""Parâmetro de saturação da frequência do termo no corpo do chunk (mesma
família do `k1` do BM25). Um chunk que REPETE o termo trata do assunto; um
que o menciona uma vez apenas o cita — mas a repetição satura, então um
capítulo enorme não vence só por extensão (o achado original do Gate
6.5-B3)."""


def _saturar(tf: int) -> float:
    return tf * (TF_SATURACAO_K1 + 1) / (tf + TF_SATURACAO_K1)


def _ranquear_candidatos(questao: str, rag_dir: Path) -> list:
    """Candidatos da questão em ordem decrescente de relevância, cada um
    `(score_total, score_lexico, chunk)`. Determinístico: a soma percorre
    os radicais em ordem alfabética e o desempate é (diploma, nome do
    arquivo) — nunca a ordem de inserção de um `set`."""
    pesos, bigramas_questao, _ = _termos_da_consulta(questao)
    if not pesos:
        return []
    indice = _indice_corpus(rag_dir)
    idf = indice["idf"]
    termos = sorted(r for r in pesos if r in idf)
    if not termos:
        return []

    candidatos = []
    for chunk in indice["chunks"]:
        freq = chunk["frequencias"]
        lexico = sum(pesos[r] * idf[r] * _saturar(freq[r]) for r in termos if r in freq)
        # Título: IDF ao QUADRADO. Um título é a declaração mais forte do
        # assunto do chunk, mas só quando o termo identifica assunto: "energia
        # elétrica" no título do capítulo de pré-pagamento é vocabulário do
        # domínio inteiro e não deve valer quase o mesmo que "procedimentos
        # irregulares" (achado do Gate 6.5-C1). Sem limiar/corte: a raridade
        # simplesmente pesa duas vezes, então termo comum ainda conta, pouco.
        titulo = BONUS_TITULO_POR_TERMO * sum(
            pesos[r] * idf[r] * idf[r] for r in termos if r in chunk["radicais_titulo"])
        frase = BONUS_FRASE_POR_BIGRAMA * sum(
            (idf.get(a, 0.0) + idf.get(b, 0.0)) / 2
            for a, b in (bg.split(" ") for bg in sorted(bigramas_questao))
            if f"{a} {b}" in chunk["bigramas"])
        total = round(lexico + titulo + frase, 6)
        if total > 0:
            candidatos.append((total, round(lexico, 6), chunk))
    candidatos.sort(key=lambda c: (-c[0], c[2]["diploma"], c[2]["arquivo"].name))
    return candidatos[:MAX_FONTES_POR_QUESTAO]


def _fonte_de_candidato(candidato: tuple, corpus_versao: str | None, indice_questao: int) -> dict:
    score_total, score_lexico, chunk = candidato
    diploma, arquivo, texto, meta = (chunk["diploma"], chunk["arquivo"],
                                     chunk["texto"], chunk["meta"])
    corpo = texto.split("\n---", 1)
    corpo_sem_frontmatter = corpo[1] if len(corpo) > 1 and texto.startswith("---") else texto
    excerto, truncado = _truncar_com_limite_de_frase(
        corpo_sem_frontmatter.strip(), MAX_EXCERPT_CHARS
    )
    fonte = fonte_juridica(
        source_id=f"{diploma}/{arquivo.name}",
        tipo="dispositivo_legal",
        diploma=meta.get("lei", diploma),
        artigo=meta.get("arts_range"),
        texto=excerto,
        fonte="corpus institucional EDE (compilado oficial)",
        authority_level=AUTORIDADE_POR_DIPLOMA.get(diploma, "NAO_VERIFICADA"),
        validation_status="NAO_VALIDADA",
        score_lexical=float(score_lexico),
        score_final=float(score_total),
    )
    # Campos além do modelo canônico compartilhado (rag/legal_validation/
    # models.py) — adicionados aqui, nunca no modelo canônico em si:
    # `fonte_juridica()` é contrato COMPARTILHADO com
    # citation_validator.py/outros consumidores (Fase 5, SPEC-0001 §9);
    # estender o dict já construído mantém este pacote (Gate 6.5-A/B3)
    # sem alterar um contrato de fora do seu próprio escopo de
    # autoridade (Gate 6.5-B3 §7/§10).
    fonte["capitulo"] = meta.get("capitulo")
    fonte["artigo_preciso"] = _artigo_preciso(excerto)
    fonte["corpus_versao"] = corpus_versao
    fonte["truncado"] = truncado
    fonte["questoes_relacionadas"] = [indice_questao]
    return fonte


def _buscar_fontes_para_questao(questao: str, rag_dir: Path, indice_questao: int) -> list:
    """Recuperação lexical determinística e limitada (Gate 6.5-A §12,
    recalibrada nos Gates 6.5-B3 e 6.5-C1). Três sinais, todos
    determinísticos e sem embeddings/BM25 (aquilo é rag/search_hybrid.py,
    fora do escopo deste MCP por footprint, RNF-CUSTO-001):

      1. sobreposição lexical ponderada por IDF, sobre radicais (acento,
         caixa, plural e derivação `-idade`/`-ção` normalizados);
      2. bônus por termo que também aparece no título/capítulo do chunk;
      3. bônus por bigrama de conteúdo da questão presente no chunk.

    Termos vindos de `CONCEITOS_JURIDICOS` entram com peso reduzido.
    Devolve os `MAX_FONTES_POR_QUESTAO` melhores. Nenhum corpus fora dos
    6 diplomas institucionais é tocado; nenhuma jurisprudência, nenhuma
    busca externa. `indice_questao` semeia `questoes_relacionadas` — a
    fusão entre questões que recuperam a MESMA fonte acontece em
    `_montar_fontes_legais`, nunca aqui."""
    corpus_versao = _versao_corpus(rag_dir)
    return [_fonte_de_candidato(c, corpus_versao, indice_questao)
            for c in _ranquear_candidatos(questao, rag_dir)]


def _montar_fontes_legais(questoes: list) -> list:
    """Agrega fontes de todas as questões, deduplicando por `source_id`
    — uma fonte que responde a MAIS de uma questão não é descartada na
    segunda ocorrência: seu índice é ACRESCENTADO a `questoes_relacionadas`
    (Gate 6.5-B3 §6).

    Gate 6.5-C1 — seleção por RODADAS entre questões: primeiro o melhor
    candidato de cada questão, depois o segundo de cada uma, e assim por
    diante, até `MAX_FONTES_TOTAL`. Antes, as questões eram esgotadas em
    ordem e o teto global era consumido pelas primeiras (achado real do
    Gate 6.5-C: com 5 questões, a 4ª recebia 1 fonte e a 5ª nenhuma). Uma
    fonte já selecionada por outra questão só ganha o vínculo e não
    consome vaga."""
    corpus_versao = _versao_corpus(RAG_DIR_PADRAO)
    ranking = [_ranquear_candidatos(q, RAG_DIR_PADRAO) for q in questoes]
    por_source_id: dict = {}
    ordem = []
    for rodada in range(MAX_FONTES_POR_QUESTAO):
        for indice, candidatos in enumerate(ranking):
            if rodada >= len(candidatos):
                continue
            chunk = candidatos[rodada][2]
            source_id = f"{chunk['diploma']}/{chunk['arquivo'].name}"
            existente = por_source_id.get(source_id)
            if existente is not None:
                if indice not in existente["questoes_relacionadas"]:
                    existente["questoes_relacionadas"].append(indice)
                continue
            if len(ordem) >= MAX_FONTES_TOTAL:
                continue
            fonte = _fonte_de_candidato(candidatos[rodada], corpus_versao, indice)
            por_source_id[source_id] = fonte
            ordem.append(fonte)
    return ordem


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
            # Gate 6.5-B3 §14: auditada contra o contrato canônico de
            # fatos.json (scripts/validate_fatos.py, Fase 7/SPEC-0001
            # §9) — "tipo" omitido já é EXPLICITAMENTE, e desde antes
            # deste gate, definido como FATO_DOCUMENTADO por
            # `validate_fatos.tipo_de()`. Não é uma classificação nova
            # inventada aqui; é reúso do MESMO helper canônico, em vez
            # de reimplementar a mesma regra inline pela segunda vez.
            "tipo": tipo_de(f),
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
    elif questoes:
        # Gate 6.5-C1: uma questão sem NENHUMA fonte não pode passar em
        # silêncio só porque outras questões recuperaram fontes. Só o
        # índice, nunca o texto da questão (mesma disciplina do 6.5-B3 §16).
        sem_fonte = [i for i in range(len(questoes))
                     if not any(i in f["questoes_relacionadas"] for f in fontes_legais)]
        if sem_fonte:
            alertas.append("Nenhuma fonte legal do corpus institucional foi "
                            f"recuperada para questoes_juridicas{sem_fonte} — "
                            "refine os termos ou trate como lacuna a suprir "
                            "pelo raciocínio do host.")
    if contexto_institucional is None:
        alertas.append("Contexto institucional (texto fixo ao redor dos "
                        "placeholders) não pôde ser extraído nesta chamada — "
                        "o pacote permanece válido sem ele.")
    tipos_presentes = {tipo_de(f) for f in fatos}
    if tipos_presentes <= {"ALEGACAO_AUTORAL"}:
        alertas.append("Todos os fatos fornecidos são ALEGACAO_AUTORAL (nenhum "
                        "FATO_DOCUMENTADO) — a defesa terá base fática "
                        "predominantemente contestável, não comprovada.")
    # Gate 6.5-B3 §9: propagação determinística de alerta quando alguma
    # fonte legal selecionada não está com a citação validada ou a
    # vigência confirmada. Nunca eleva silenciosamente o status (a
    # fonte continua NAO_VALIDADA/NAO_VERIFICADA nela mesma) — só torna
    # a incerteza visível no nível do pacote, onde o host efetivamente
    # decide se cita a fonte.
    fontes_nao_validadas = [f["source_id"] for f in fontes_legais
                             if f.get("validation_status") != "VALIDADA"]
    if fontes_nao_validadas:
        alertas.append(
            "As seguintes fontes legais recuperadas ainda não têm a citação "
            "validada (validation_status != VALIDADA) — confirme o dispositivo "
            f"antes de citá-lo como definitivo: {fontes_nao_validadas}."
        )
    fontes_vigencia_incerta = [f["source_id"] for f in fontes_legais
                                if f.get("vigencia") != "VIGENTE"]
    if fontes_vigencia_incerta:
        alertas.append(
            "As seguintes fontes legais recuperadas não têm vigência confirmada "
            f"(vigencia != VIGENTE): {fontes_vigencia_incerta}."
        )

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
            "corpus_versao": _versao_corpus(RAG_DIR_PADRAO),
            "modelo_oficial_sha256": os.environ.get(lr.ENV_MODELO_SHA256),
        },
    }
    return ResultadoPreparacao(status="OK", pacote=pacote)
