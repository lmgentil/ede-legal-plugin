#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Busca híbrida (BM25 + denso) com lookup direto por artigo — RAG JURÍDICO.

Camadas de recuperação:
  1. Lookup por artigo: se a consulta cita "art. N" ou "arts. N, M e K" (com ou
     sem indicação da lei), resolve direto via index_artigos.json.
  2. Busca híbrida: score = alpha * BM25(normalizado) + (1-alpha) * cosseno denso.
     alpha padrão = 0.65 (calibrado empiricamente). Chunks de navegação
     (mestres e INDEX) ficam FORA do ranking — servem só para roteamento.

Camada de confiança (avaliar se há informação suficiente na base):
  Cada resultado híbrido traz bm25_raw (score absoluto), denso (cosseno) e
  cobertura (fração dos termos da consulta presentes no documento).
  `confianca()` classifica em alta / media / baixa. "baixa" indica que
  provavelmente NÃO há informação suficiente nos documentos — o gerador deve
  responder "Não há informação suficiente nos documentos para responder com
  segurança." "media" exige conferir se o trecho responde de fato.
  Limiares calibrados com consultas dentro/fora do escopo; método lexical tem
  separação imperfeita — trate como heurística, não como garantia.

Vetores densos: se embeddings/semantic/ existir (build_embeddings_semantic.py)
e sentence-transformers estiver instalado, usa embeddings semânticos; senão,
TF-IDF+LSA (offline).

Uso:
  python search_hybrid.py "prazo para contestação no procedimento comum"
  python search_hybrid.py "arts. 186 e 927 do código civil"
  python search_hybrid.py "suspensão de fornecimento" --corpus REN1000 -k 8

Requisitos: pandas, pyarrow, scikit-learn, joblib, rank_bm25
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

try:
    import yaml
except ImportError:
    yaml = None  # pyyaml ausente -> cai para defaults hardcoded (aviso abaixo)

BASE = Path(__file__).parent
EMB = BASE / "embeddings"
CONFIG_PATH = BASE / "config.yaml"


def _carregar_config() -> dict:
    """REQ-044 (Fase 4): parâmetros antes hardcoded agora vêm de config.yaml.
    Se pyyaml não estiver instalado ou o arquivo estiver ausente/corrompido,
    cai para os mesmos valores que já estavam hardcoded (nenhuma mudança de
    comportamento nesse caso) e avisa — mesmo estilo de degradação usada para
    o índice semântico ausente, mais abaixo neste arquivo."""
    if yaml is None:
        print("[AVISO] pyyaml não instalado; config.yaml não será lido, "
              "usando defaults hardcoded (REQ-044 não religado nesta execução).")
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[AVISO] Falha ao ler {CONFIG_PATH.name} ({e.__class__.__name__}); "
              f"usando defaults hardcoded.")
        return {}


def _cfg(caminho: list, default):
    node = _CONFIG
    for chave in caminho:
        if not isinstance(node, dict) or chave not in node:
            return default
        node = node[chave]
    return node


_CONFIG = _carregar_config()

# limiares da camada de confiança (calibrados em 2026-07, 28 consultas de teste)
# LSA (fallback offline) e SEMANTIC (embeddings mpnet) têm escalas de cosseno
# diferentes — limiares separados. SEM usa também um escore composto
# S = bm25_raw/15 + cosseno/0.6 + cobertura (baixa quando S <= baixa_S).
# Valores abaixo são os defaults hardcoded originais, usados só se config.yaml
# não puder ser lido — quando lido, rag/config.yaml é a fonte (REQ-044).
_lsa = _cfg(["confianca", "lsa"], {})
CONF_LSA = {"alta_bm": _lsa.get("alta_bm25", 10.0),
            "alta_cos": _lsa.get("alta_cosseno", 0.60),
            "alta_cob": _lsa.get("alta_cobertura", 0.85),
            "baixa_bm": _lsa.get("baixa_bm25", 6.0),
            "baixa_cos": _lsa.get("baixa_cosseno", 0.50),
            "baixa_cob": _lsa.get("baixa_cobertura", 0.50)}
_sem = _cfg(["confianca", "semantico"], {})
CONF_SEM = {"alta_bm": _sem.get("alta_bm25", 9.0),
            "alta_cob": _sem.get("alta_cobertura", 0.75),
            "alta_cos": _sem.get("alta_cosseno", 0.55),
            "baixa_S": _sem.get("baixa_score_composto", 1.4)}

ALPHA_PADRAO = _cfg(["busca_hibrida", "alpha"], 0.65)
PESO_RERANK_COBERTURA = _cfg(["busca_hibrida", "peso_rerank_cobertura"], 0.05)

# ---------------------------------------------------------------- tokenização
STOPWORDS = set("""a o e de da do das dos em no na nos nas um uma uns umas por
para com sem sob sobre entre ao aos à às que se não mais ou como ser é são foi
seu sua seus suas este esta isto esse essa isso aquele aquela pelo pela pelos
pelas nos termos caso quando houver deve devem podera poderao""".split())


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def tokenize(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", normalize(text))
            if t not in STOPWORDS and len(t) > 1]


# ------------------------------------------------------- detecção de artigos
# captura blocos "art. 186", "arts. 186, 927 e 944", "artigo 5º e 6º"
ART_BLOCK_RE = re.compile(
    r"art(?:igo)?s?\.?\s*("
    r"\d{1,4}(?:\.\d{3})?(?:\s*[º°o])?(?:\s*-\s*[A-Za-z]\b)?"
    r"(?:\s*(?:,|e)\s*\d{1,4}(?:\.\d{3})?(?:\s*[º°o])?(?:\s*-\s*[A-Za-z]\b)?)*"
    r")", re.IGNORECASE)
NUM_RE = re.compile(r"\d{1,4}(?:\.\d{3})?")

CORPUS_HINTS = {
    "CPC": ["cpc", "processo civil", "13105", "13.105"],
    "CC": ["codigo civil", "cc", "10406", "10.406"],
    "CDC": ["cdc", "consumidor", "8078", "8.078"],
    # ATENÇÃO: a dica de corpus FILTRA (exclui os demais). Usar apenas termos
    # inequívocos — "aneel", "concessao", "concessionaria" são ambíguos entre
    # REN1000, L8987 e L9427 e NÃO podem ser dica.
    "REN1000": ["ren 1000", "ren 1.000", "resolucao 1000", "resolucao 1.000",
                "resolucao normativa"],
    "L8987": ["8987", "8.987", "lei de concessoes", "lei geral de concessoes"],
    "L9427": ["9427", "9.427", "lei da aneel"],
}


def detect_articles(query: str):
    """Retorna (lista de artigos citados, corpus indicado ou None)."""
    arts = []
    for m in ART_BLOCK_RE.finditer(query):
        for n in NUM_RE.findall(m.group(1)):
            v = int(n.replace(".", ""))
            if v not in arts:
                arts.append(v)
    qn = normalize(query)
    corpus = None
    for c, hints in CORPUS_HINTS.items():
        if any(h in qn for h in hints):
            corpus = c
            break
    return arts, corpus


# --------------------------------------------------------------------- índice
class HybridSearcher:
    def __init__(self, alpha: float = ALPHA_PADRAO):
        self.alpha = alpha
        # embeddings semânticos (build_embeddings_semantic.py) têm prioridade
        sem = EMB / "semantic" / "embeddings_all.parquet"
        self.semantic = False
        # GUARDA DE DEFASAGEM: se o índice semântico tem menos chunks que o
        # LSA (corpora novos ainda não vetorizados na máquina local), NÃO usar
        # o semântico — senão os corpora novos ficam invisíveis na busca.
        if sem.exists():
            try:
                man_sem = json.load(open(EMB / "semantic" / "manifest_semantic.json",
                                         encoding="utf-8"))
                man_lsa = json.load(open(EMB / "manifest.json", encoding="utf-8"))
                if man_sem.get("total_chunks") != man_lsa.get("total_chunks"):
                    print(f"[AVISO] Índice semântico DEFASADO "
                          f"({man_sem.get('total_chunks')} chunks vs "
                          f"{man_lsa.get('total_chunks')} no LSA). Usando LSA. "
                          f"Rode RODAR_EMBEDDINGS_SEMANTICOS.bat para atualizar.")
                    sem = None
            except Exception:
                pass
        if sem is not None and sem.exists():
            try:
                from sentence_transformers import SentenceTransformer
                man = json.load(open(EMB / "semantic" / "manifest_semantic.json",
                                     encoding="utf-8"))
                self.model = SentenceTransformer(man["modelo"])
                self.query_prefix = man.get("prefixo_query", "")
                self.df = pd.read_parquet(sem)
                self.semantic = True
            except ImportError:
                pass  # sentence-transformers ausente -> fallback LSA
            except Exception as e:
                # parquet corrompido/truncado (ex.: espelho do Cowork) -> LSA
                print(f"[AVISO] Falha ao carregar índice semântico ({e.__class__.__name__}). Usando LSA.")
                self.semantic = False
        if not self.semantic:
            self.df = pd.read_parquet(EMB / "embeddings_all.parquet")
            self.vectorizer = joblib.load(EMB / "vectorizer.joblib")
            self.svd = joblib.load(EMB / "svd.joblib")
        self.E = np.vstack(self.df["embedding"].apply(np.array))
        self.bm25 = BM25Okapi([tokenize(t) for t in self.df["text"].fillna("")])
        # chunks de navegação (mestres/INDEX): fora do ranking
        names = self.df["file_name"].astype(str)
        self.nav = (names.str.contains("MESTRE") | (names == "INDEX.md")).values
        with open(BASE / "index_artigos.json", encoding="utf-8") as f:
            self.art_index = json.load(f)["corpora"]

    def _embed_query(self, query: str) -> np.ndarray:
        if self.semantic:
            v = self.model.encode([self.query_prefix + query],
                                  normalize_embeddings=True)
            return v.ravel()
        v = self.svd.transform(self.vectorizer.transform([query]))
        n = np.linalg.norm(v)
        return (v / n).ravel() if n > 0 else v.ravel()

    def _coverage(self, q_tokens: list, doc_idx: int) -> float:
        if not q_tokens:
            return 0.0
        doc_terms = self.bm25.doc_freqs[doc_idx].keys()
        return sum(1 for t in set(q_tokens) if t in doc_terms) / len(set(q_tokens))

    # -- camada 1: artigo exato ------------------------------------------
    def lookup_article(self, art: int, corpus: str = None) -> list:
        hits = []
        for c, entries in self.art_index.items():
            if corpus and c != corpus:
                continue
            for e in entries:
                if e["art_inicio"] <= art <= e["art_fim"]:
                    hits.append({"corpus": c, "file_name": e["file"],
                                 "capitulo": e.get("capitulo", ""),
                                 "match": f"art. {art} ({e['art_inicio']}-{e['art_fim']})",
                                 "score": None, "via": "indice_artigos"})
        return hits

    # -- camada 2: híbrida (fusão + reranking) -----------------------------
    @staticmethod
    def _rerank(candidatos: list, peso_cobertura: float = PESO_RERANK_COBERTURA) -> list:
        """Estágio de reranking (SPEC-0001 §15: fusão -> reranking -> contexto).
        A fusão (score = alpha*BM25 + (1-alpha)*denso) já produz a ordem
        principal; aqui os candidatos da fusão são reordenados com um
        pequeno reforço pela cobertura de termos da consulta (sinal que já
        era calculado, mas só para exibição, não para a ordem). Efeito
        pequeno por design (peso padrão 0.05) — serve para desempatar
        candidatos de score de fusão muito próximo, não para substituí-lo."""
        return sorted(candidatos,
                      key=lambda r: r["score"] + peso_cobertura * r["cobertura"],
                      reverse=True)

    def search(self, query: str, k: int = 5, corpus: str = None) -> list:
        toks = tokenize(query)
        bm_raw = np.array(self.bm25.get_scores(toks))
        bm = bm_raw / bm_raw.max() if bm_raw.max() > 0 else bm_raw

        cos = (self.E @ self._embed_query(query)).clip(min=0)

        score = self.alpha * bm + (1 - self.alpha) * cos
        score[self.nav] = -1.0
        if corpus:
            score = np.where(self.df["corpus"].values == corpus, score, -1)

        # pool maior que k para o reranking ter candidatos para reordenar
        pool = np.argsort(-score)[:max(k * 3, k)]
        candidatos = []
        for i in pool:
            if score[i] < 0:
                break
            r = self.df.iloc[i]
            candidatos.append({"corpus": r["corpus"], "file_name": r["file_name"],
                                "score": round(float(score[i]), 3),
                                "bm25": round(float(bm[i]), 3),
                                "bm25_raw": round(float(bm_raw[i]), 2),
                                "denso": round(float(cos[i]), 3),
                                "cobertura": round(self._coverage(toks, int(i)), 2),
                                "via": "hibrida"})
        return self._rerank(candidatos)[:k]

    # -- camada 3: confiança -----------------------------------------------
    def confianca(self, query: str, results: list = None) -> dict:
        """Classifica a confiança de que a base contém a resposta.
        baixa -> provavelmente não há informação suficiente nos documentos."""
        arts, _ = detect_articles(query)
        if arts and results and any(r["via"] == "indice_artigos" for r in results):
            return {"nivel": "alta", "motivo": "artigo localizado no índice"}
        hyb = [r for r in (results or self.search(query, k=3))
               if r["via"] == "hibrida"]
        if not hyb:
            return {"nivel": "baixa", "motivo": "nenhum resultado"}
        top = hyb[0]
        bm, cs, cb = top["bm25_raw"], top["denso"], top["cobertura"]
        det = {"bm25_raw": bm, "denso": cs, "cobertura": cb}
        if self.semantic:
            C = CONF_SEM
            if (cb >= C["alta_cob"] and bm >= C["alta_bm"]) or cs >= C["alta_cos"]:
                return {"nivel": "alta", **det,
                        "motivo": "boa correspondência lexical e/ou semântica"}
            S = bm / 15 + cs / 0.6 + cb
            det["escore_composto"] = round(S, 2)
            if S <= C["baixa_S"]:
                return {"nivel": "baixa", **det,
                        "motivo": "sinais lexicais e semânticos fracos"}
            return {"nivel": "media", **det,
                    "motivo": "correspondência parcial — conferir se o trecho responde"}
        C = CONF_LSA
        if cb < C["baixa_cob"] or (bm < C["baixa_bm"] and cs < C["baixa_cos"]):
            return {"nivel": "baixa", **det,
                    "motivo": "termos da consulta ausentes ou score absoluto baixo"}
        if cb >= C["alta_cob"] and (bm >= C["alta_bm"] or cs >= C["alta_cos"]):
            return {"nivel": "alta", **det, "motivo": "boa correspondência lexical e densa"}
        return {"nivel": "media", **det,
                "motivo": "correspondência parcial — conferir se o trecho responde"}

    # -- interface única ---------------------------------------------------
    def query(self, q: str, k: int = 5, corpus: str = None) -> list:
        arts, hinted = detect_articles(q)
        corpus = corpus or hinted
        results = []
        seen = set()
        for a in arts:
            for h in self.lookup_article(a, corpus):
                key = (h["corpus"], h["file_name"])
                if key not in seen:
                    seen.add(key)
                    results.append(h)
        for h in self.search(q, k=k, corpus=corpus):
            key = (h["corpus"], h["file_name"])
            if key not in seen and len(results) < k + len(arts):
                seen.add(key)
                results.append(h)
        return results[:max(k, len([r for r in results if r["via"] == "indice_artigos"]))]


def main():
    ap = argparse.ArgumentParser(description="Busca híbrida RAG Jurídico")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--corpus", choices=["CPC", "CC", "CDC", "REN1000", "L8987", "L9427"])
    ap.add_argument("--alpha", type=float, default=ALPHA_PADRAO,
                    help="peso do BM25 (0=só denso, 1=só BM25)")
    args = ap.parse_args()

    s = HybridSearcher(alpha=args.alpha)
    modo = "semântico" if s.semantic else "TF-IDF+LSA"
    res = s.query(args.query, k=args.k, corpus=args.corpus)
    conf = s.confianca(args.query, res)
    print(f"(vetores densos: {modo} | confiança: {conf['nivel']} — {conf['motivo']})")
    if conf["nivel"] == "baixa":
        print("  ⚠ Provavelmente NÃO há informação suficiente nos documentos.")
    for r in res:
        if r["via"] == "indice_artigos":
            print(f"  [ARTIGO] [{r['corpus']}] {r['file_name']}  <- {r['match']}")
        else:
            print(f"  {r['score']:.3f} (bm25_raw={r['bm25_raw']:.1f} denso={r['denso']:.2f} "
                  f"cobertura={r['cobertura']:.2f}) [{r['corpus']}] {r['file_name']}")


if __name__ == "__main__":
    main()
