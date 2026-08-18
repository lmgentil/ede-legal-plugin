#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citation_validator.py — REQ-027/028 (Fase 5): resolve uma citação jurídica
em texto livre contra o corpus indexado e retorna um veredito estruturado.

Fluxo (SPEC-0001 §16-17):
  citação -> parse -> lookup exato do artigo (index_artigos.json, já
  existente desde a Fase 4 — lido direto aqui, SEM instanciar
  HybridSearcher: validar uma citação não precisa carregar embeddings) ->
  se achou, confere parágrafo/inciso/alínea dentro do TEXTO real do artigo
  (o artigo existir não basta — §15/§18: correspondência exata, não
  proximidade semântica) -> se não achou por lookup exato, busca híbrida
  DIRECIONADA só para SUGERIR candidato (§16 — nunca promovida a citação
  validada) -> fail closed: qualquer situação não confirmada é
  NAO_VALIDADA/AMBIGUA/FONTE_INSUFICIENTE, nunca um dado fabricado (§17).

RETRIEVAL != LEGAL VALIDATION (§22): este módulo não importa search_hybrid
no caminho principal — só no fallback opcional de sugestão, sob demanda.
"""
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .models import fonte_juridica
from .provenance import proveniencia
from .source_authority import classificar_autoridade
from .temporal_status import vigencia_de

BASE = Path(__file__).resolve().parent.parent  # rag/

# --------------------------------------------------------- leitura de chunk
_FRONTMATTER_FIM_RE = re.compile(r"\n---\s*\n")


def _ler_chunk(caminho: Path):
    """Retorna (frontmatter: dict, corpo: str). Sem pyyaml, frontmatter
    fica {} (degradação: perde diploma/norma "bonitos", mas a validação de
    existência/inciso/parágrafo — que só depende do corpo — continua
    funcionando)."""
    texto = caminho.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        return {}, texto
    m = _FRONTMATTER_FIM_RE.search(texto, 3)
    if not m:
        return {}, texto
    bloco_fm, corpo = texto[3:m.start()], texto[m.end():]
    if yaml is None:
        return {}, corpo
    try:
        return (yaml.safe_load(bloco_fm) or {}), corpo
    except Exception:
        return {}, corpo


def _diploma_norma_de(frontmatter: dict):
    """Corpora "lei"-based (CPC/CC/CDC/L8987/L9427): campo único
    "Lei nº X — Nome do Diploma", separa em (diploma, norma). REN1000 usa
    campo "norma" direto, sem nome de diploma separado no frontmatter."""
    lei = frontmatter.get("lei")
    if lei:
        for sep in (" — ", " - "):
            if sep in lei:
                norma, diploma = lei.split(sep, 1)
                return diploma.strip(), norma.strip()
        return lei, lei
    norma = frontmatter.get("norma")
    return (norma, norma) if norma else (None, None)


# ------------------------------------------------- extração de bloco de texto
def _marcador_artigo_re(n: int) -> re.Pattern:
    # Fase 7 (E2E): a pontuação após o número varia entre corpora — CPC/REN1000
    # usam "Art. 335." (ponto colado), CDC usa "Art. 6º São direitos..." (sem
    # ponto, ordinal seguido de espaço e texto). Em vez de exigir pontuação
    # específica, usa negative lookahead \D (não-dígito) para não casar
    # "Art. 6" dentro de "Art. 60" — funciona para os dois estilos.
    return re.compile(rf"(?:^|\n)\s*Art\.\s*{n}[º°oO]?(?!\d)", re.MULTILINE)


def extrair_bloco_artigo(corpo: str, artigo: int):
    """Texto do "Art. N." até o próximo "Art. N+1." (ou fim do chunk, se N
    for o último artigo nele). None se o marcador não for localizado."""
    ini = _marcador_artigo_re(artigo).search(corpo)
    if not ini:
        return None
    fim = _marcador_artigo_re(artigo + 1).search(corpo, ini.end())
    return corpo[ini.start():fim.start()] if fim else corpo[ini.start():]


_PARAGRAFO_MARCADOR_RE = re.compile(
    r"(?:^|\n)\s*(§\s*(\d{1,3})\s*[º°oO]?|Par[aá]grafo\s+[uú]nico)", re.MULTILINE)
_INCISO_MARCADOR_RE = re.compile(r"(?:^|\n)\s*([IVXLCDM]+)\s*-\s", re.MULTILINE)
_ALINEA_MARCADOR_RE = re.compile(r"(?:^|\n)\s*([a-z])\)\s", re.MULTILINE)


def bloco_caput(bloco_artigo: str) -> str:
    """Texto do artigo até o primeiro "§"/"Parágrafo único" — escopo onde
    incisos "soltos" (não dentro de um parágrafo específico) são
    procurados."""
    m = _PARAGRAFO_MARCADOR_RE.search(bloco_artigo)
    return bloco_artigo[:m.start()] if m else bloco_artigo


def bloco_paragrafo(bloco_artigo: str, alvo: str):
    """alvo: "unico" ou string do número ("1", "2", ...). None se o
    parágrafo pedido não existir no artigo."""
    marcadores = list(_PARAGRAFO_MARCADOR_RE.finditer(bloco_artigo))
    for i, m in enumerate(marcadores):
        eh_unico = "nico" in m.group(1).lower()
        bate = (alvo == "unico" and eh_unico) or (alvo != "unico" and m.group(2) == alvo)
        if bate:
            fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(bloco_artigo)
            return bloco_artigo[m.start():fim]
    return None


def incisos_em(bloco: str) -> set:
    return {m.group(1).upper() for m in _INCISO_MARCADOR_RE.finditer(bloco)}


def bloco_inciso(bloco: str, alvo: str):
    marcadores = list(_INCISO_MARCADOR_RE.finditer(bloco))
    for i, m in enumerate(marcadores):
        if m.group(1).upper() == alvo:
            fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(bloco)
            return bloco[m.start():fim]
    return None


def alineas_em(bloco: str) -> set:
    return {m.group(1).lower() for m in _ALINEA_MARCADOR_RE.finditer(bloco)}


# ------------------------------------------------------------- índice/busca
def _carregar_indice_artigos() -> dict:
    with open(BASE / "index_artigos.json", encoding="utf-8") as f:
        return json.load(f)["corpora"]


_searcher_cache = {}


def _sugerir_candidato(texto_citacao: str, corpus: str):
    """Camada 2 do fluxo do §16: busca híbrida DIRECIONADA ao corpus, só
    para sugerir um candidato quando o lookup exato falhou. Nunca é
    promovida a citação validada — quem chama isto já retorna
    NAO_VALIDADA independentemente do resultado aqui. Import tardio de
    HybridSearcher (pesa embeddings) e falha graciosamente (retorna None)
    se o índice de busca não estiver disponível — sugestão é
    complementar, não é o caminho fail-closed principal."""
    try:
        if "s" not in _searcher_cache:
            sys.path.insert(0, str(BASE))
            from search_hybrid import HybridSearcher
            _searcher_cache["s"] = HybridSearcher()
        s = _searcher_cache["s"]
        res = s.search(texto_citacao, k=1, corpus=corpus)
        if not res:
            return None
        r = res[0]
        return {"corpus": r["corpus"], "file_name": r["file_name"], "score": r["score"]}
    except Exception:
        return None


# --------------------------------------------------------------- validação
def validar_citacao(texto: str, sugerir_candidato: bool = True) -> dict:
    """Ponto de entrada principal (REQ-027/028). Retorna sempre:
      {input, status, source_id, confidence, motivo, parsed, fonte}
    e, quando status == NAO_VALIDADA por artigo não encontrado e
    sugerir_candidato=True, também "sugestao" (dict ou None) — nunca usada
    para mudar `status`."""
    # import tardio para não obrigar quem só usa parse/blocos a puxar isso
    from .citation_parser import parse_citacao

    p = parse_citacao(texto)
    base = {"input": texto, "parsed": p, "fonte": None}

    # ordem importa: sem artigo nenhum, a citação é insuficiente mesmo que
    # por acaso o corpus tenha sido identificado (raro) — FONTE_INSUFICIENTE
    # é mais específico que AMBIGUA nesse caso (não é "ambíguo entre
    # corpora", é "não há o que resolver").
    if p["artigo"] is None:
        return {**base, "status": "FONTE_INSUFICIENTE", "source_id": None, "confidence": 0.0,
                "motivo": "nenhum número de artigo identificado na citação."}
    if p["corpus"] is None:
        return {**base, "status": "AMBIGUA", "source_id": None, "confidence": 0.0,
                "motivo": "diploma/corpus não identificado na citação — "
                          "impossível resolver sem ambiguidade entre corpora."}

    corpus, artigo = p["corpus"], p["artigo"]
    indice = _carregar_indice_artigos()
    matches = [e for e in indice.get(corpus, [])
               if e["art_inicio"] <= artigo <= e["art_fim"]]

    if not matches:
        resultado = {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                     "motivo": f"art. {artigo} não encontrado no corpus {corpus}."}
        if sugerir_candidato:
            resultado["sugestao"] = _sugerir_candidato(texto, corpus)
        return resultado
    if len(matches) > 1:
        return {**base, "status": "AMBIGUA", "source_id": None, "confidence": 0.0,
                "motivo": f"art. {artigo} corresponde a mais de uma entrada em "
                          f"{corpus} no índice — inconsistência de dados, não "
                          f"resolvida automaticamente."}

    entrada = matches[0]
    caminho = BASE / f"chunks_{corpus}" / entrada["file"]
    if not caminho.exists():
        return {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                "motivo": f"arquivo do chunk não encontrado: {entrada['file']}."}

    frontmatter, corpo = _ler_chunk(caminho)
    bloco_art = extrair_bloco_artigo(corpo, artigo)
    if bloco_art is None:
        return {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                "motivo": f"art. {artigo} está no intervalo do chunk {entrada['file']} "
                          f"segundo o índice, mas o marcador 'Art. {artigo}.' não foi "
                          f"localizado no texto — divergência índice/conteúdo, não presumida."}

    if p["paragrafo"]:
        escopo = bloco_paragrafo(bloco_art, p["paragrafo"])
        if escopo is None:
            return {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                    "motivo": f"§ {p['paragrafo']} não encontrado no art. {artigo} de {corpus}."}
        rotulo_escopo = "parágrafo único" if p["paragrafo"] == "unico" else f"§ {p['paragrafo']}º"
    else:
        escopo = bloco_caput(bloco_art)
        rotulo_escopo = "caput"

    texto_final = escopo.strip()
    status = "VALIDADA"

    if p["inciso"]:
        incisos = incisos_em(escopo)
        if p["inciso"] not in incisos:
            return {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                    "motivo": f"inciso {p['inciso']} não encontrado no {rotulo_escopo} do "
                              f"art. {artigo} de {corpus} (incisos presentes: "
                              f"{sorted(incisos) or 'nenhum'})."}
        b_inciso = bloco_inciso(escopo, p["inciso"])
        if b_inciso is None:
            # regex de listagem confirmou o inciso, mas não deu para isolar
            # o bloco (formatação fora do padrão) — degradação honesta,
            # não fabricamos o texto do inciso.
            status = "PARCIALMENTE_VALIDADA"
        else:
            texto_final = b_inciso.strip()
            if p["alinea"]:
                alineas = alineas_em(b_inciso)
                if p["alinea"] not in alineas:
                    return {**base, "status": "NAO_VALIDADA", "source_id": None, "confidence": 0.0,
                            "motivo": f"alínea '{p['alinea']}' não encontrada no inciso "
                                      f"{p['inciso']} do art. {artigo} de {corpus} "
                                      f"(alíneas presentes: {sorted(alineas) or 'nenhuma'})."}
                # existência confirmada, mas não isolamos o texto exato só
                # da alínea dentro do bloco do inciso — não afirmar
                # precisão de texto que não temos.
                status = "PARCIALMENTE_VALIDADA"

    diploma, norma = _diploma_norma_de(frontmatter)
    fonte_str = frontmatter.get("fonte") or norma

    source_id = f"{corpus.lower()}-art-{artigo}"
    if p["paragrafo"]:
        source_id += f"-par-{p['paragrafo']}"
    if p["inciso"]:
        source_id += f"-{p['inciso'].lower()}"
    if p["alinea"]:
        source_id += f"-{p['alinea']}"

    fonte = fonte_juridica(
        source_id=source_id, tipo="legislacao", diploma=diploma, norma=norma,
        artigo=str(artigo), paragrafo=p["paragrafo"], inciso=p["inciso"],
        alinea=p["alinea"], texto=texto_final, fonte=fonte_str,
        vigencia=vigencia_de(corpus, artigo),
        authority_level=classificar_autoridade(corpus),
        validation_status=status,
    )
    fonte["_proveniencia"] = proveniencia(corpus, entrada["file"], diploma, artigo)

    return {**base, "status": status, "source_id": source_id,
            "confidence": 1.0 if status == "VALIDADA" else 0.6,
            "motivo": "referência corresponde ao texto localizado no corpus."
                      if status == "VALIDADA" else
                      "existência confirmada, mas o texto exato do trecho pedido "
                      "não pôde ser isolado com segurança — não fabricado.",
            "fonte": fonte}


# ------------------------------------------------------------ enriquecimento
def enriquecer_resultados(resultados: list) -> list:
    """REQ-024/025/026 + §21 (Fase 5): recebe a saída de
    HybridSearcher.query()/search() (lista de dicts com corpus/file_name/
    via/score/...) e devolve cada item envolvido no modelo canônico de
    fonte jurídica, com autoridade/vigência/proveniência preenchidos.

    IMPORTANTE (§21): isto é enriquecimento de METADADOS de um resultado
    de RECUPERAÇÃO, não validação de uma citação específica (não há
    inciso/parágrafo alegado para conferir aqui). `validation_status`
    reflete só o tipo de correspondência que já produziu o resultado:
      - via == "indice_artigos": o artigo foi localizado por identificador
        exato (SPEC-0001 REQ correspondência exata) -> VALIDADA no nível
        "este artigo existe e é este arquivo", sem alegação de
        inciso/parágrafo.
      - via == "hibrida": resultado de ranking semântico/lexical — por
        mais alto que seja o score, isso é RELEVÂNCIA, não confirmação de
        que o texto responde à pergunta -> NAO_VALIDADA (mesmo com
        score_final alto; ver teste `test_score_alto_nao_implica_validado`).
    `vigencia` é sempre NAO_VERIFICADA (ver `temporal_status.py`) —
    independente do `via` ou do score.
    """
    indice = _carregar_indice_artigos()
    saida = []
    for r in resultados:
        corpus, arquivo = r["corpus"], r["file_name"]
        caminho = BASE / f"chunks_{corpus}" / arquivo
        frontmatter = {}
        if caminho.exists():
            frontmatter, _ = _ler_chunk(caminho)
        diploma, norma = _diploma_norma_de(frontmatter)

        artigo = None
        for e in indice.get(corpus, []):
            if e["file"] == arquivo:
                artigo = e["art_inicio"]
                break

        validado = r.get("via") == "indice_artigos"
        fonte = fonte_juridica(
            source_id=f"{corpus.lower()}-{arquivo}",
            tipo="legislacao", diploma=diploma, norma=norma,
            artigo=str(artigo) if artigo is not None else None,
            fonte=frontmatter.get("fonte") or norma,
            vigencia=vigencia_de(corpus, artigo),
            authority_level=classificar_autoridade(corpus),
            validation_status="VALIDADA" if validado else "NAO_VALIDADA",
            score_semantico=r.get("denso"), score_lexical=r.get("bm25"),
            score_final=r.get("score"),
        )
        fonte["_proveniencia"] = proveniencia(corpus, arquivo, diploma, artigo)
        saida.append(fonte)
    return saida
