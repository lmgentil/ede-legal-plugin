#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera embeddings (TF-IDF + LSA/TruncatedSVD, 100% local/offline) para os chunks
jurídicos do projeto RAG JURÍDICO (CPC, CC, CDC, REN 1000/2021 ANEEL).

Saídas (em outputs/embeddings/):
  - embeddings_all.parquet      -> todos os chunks das 4 leis, com metadados + vetor
  - embeddings_<CORPUS>.parquet -> um parquet por corpus (CPC, CC, CDC, REN1000)
  - vectorizer.joblib           -> TfidfVectorizer treinado (necessário p/ embutir novas queries)
  - svd.joblib                  -> TruncatedSVD treinado (reduz TF-IDF -> vetor denso)
  - manifest.json                -> metadados da execução (nº chunks, dimensão, etc.)
"""
import os
import re
import json
import yaml
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

# Caminhos relativos ao próprio script (rag/embeddings/build_embeddings.py)
BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORPORA = {
    "CPC": BASE_DIR / "chunks_CPC",
    "CC": BASE_DIR / "chunks_CC",
    "CDC": BASE_DIR / "chunks_CDC",
    "REN1000": BASE_DIR / "chunks_REN1000",
    "L8987": BASE_DIR / "chunks_L8987",
    "L9427": BASE_DIR / "chunks_L9427",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

N_COMPONENTS = 256  # dimensão do embedding denso final (LSA)


def parse_chunk(path: Path, corpus: str) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(raw)
    if m:
        fm_text, body = m.group(1), m.group(2)
        try:
            meta = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            meta = {}
    else:
        meta, body = {}, raw

    body = body.strip()
    record = {
        "corpus": corpus,
        "file_name": path.name,
        "text": body,
        "n_chars": len(body),
    }
    # normaliza campos de metadado (nem todo corpus tem os mesmos campos)
    for k, v in meta.items():
        record[f"meta_{k}"] = "" if v is None else str(v)
    return record


def load_all_chunks() -> pd.DataFrame:
    rows = []
    for corpus, folder in CORPORA.items():
        files = sorted(folder.glob("*.md"))
        for f in files:
            rows.append(parse_chunk(f, corpus))
    df = pd.DataFrame(rows)
    return df


def build_embeddings(df: pd.DataFrame):
    texts = df["text"].fillna("").tolist()

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents=None,  # mantém acentuação (relevante em PT-BR jurídico)
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9,
        sublinear_tf=True,
        norm="l2",
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    n_comp = min(N_COMPONENTS, tfidf_matrix.shape[1] - 1, tfidf_matrix.shape[0] - 1)
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    dense = svd.fit_transform(tfidf_matrix)

    # normaliza L2 os vetores densos finais (facilita similaridade por cosseno / dot product)
    norms = np.linalg.norm(dense, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    dense_norm = dense / norms

    return vectorizer, svd, dense_norm


def main():
    df = load_all_chunks()
    print(f"Total de chunks carregados: {len(df)}")
    print(df.groupby("corpus").size())

    vectorizer, svd, embeddings = build_embeddings(df)
    print(f"Dimensão do embedding: {embeddings.shape[1]}")
    print(f"Variância explicada acumulada (LSA): {svd.explained_variance_ratio_.sum():.4f}")

    df["embedding"] = list(embeddings.astype(np.float32))

    # salva parquet combinado
    combined_path = OUT_DIR / "embeddings_all.parquet"
    df_to_save = df.copy()
    df_to_save["embedding"] = df_to_save["embedding"].apply(lambda v: v.tolist())
    df_to_save.to_parquet(combined_path, index=False)
    print(f"Salvo: {combined_path} ({len(df_to_save)} linhas)")

    # salva um parquet por corpus também
    for corpus in df["corpus"].unique():
        sub = df_to_save[df_to_save["corpus"] == corpus]
        p = OUT_DIR / f"embeddings_{corpus}.parquet"
        sub.to_parquet(p, index=False)
        print(f"Salvo: {p} ({len(sub)} linhas)")

    # salva vectorizer e svd para permitir embutir novas queries no futuro
    joblib.dump(vectorizer, OUT_DIR / "vectorizer.joblib")
    joblib.dump(svd, OUT_DIR / "svd.joblib")

    manifest = {
        "total_chunks": int(len(df)),
        "chunks_por_corpus": df.groupby("corpus").size().to_dict(),
        "embedding_dim": int(embeddings.shape[1]),
        "metodo": "TF-IDF (1-2 gramas) + TruncatedSVD (LSA), 100% local/offline",
        "variancia_explicada_acumulada": float(svd.explained_variance_ratio_.sum()),
        "arquivos": {
            "combinado": "embeddings_all.parquet",
            "por_corpus": [f"embeddings_{c}.parquet" for c in df["corpus"].unique()],
            "vectorizer": "vectorizer.joblib",
            "svd": "svd.joblib",
        },
    }
    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("Manifest salvo.")


if __name__ == "__main__":
    main()
