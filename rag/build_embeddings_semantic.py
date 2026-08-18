#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera embeddings SEMÂNTICOS para os chunks do RAG JURÍDICO.

⚠ Este script NÃO roda no sandbox do Claude (download de modelos bloqueado).
  Rode na sua máquina, nesta pasta:

    pip install sentence-transformers pandas pyarrow
    python build_embeddings_semantic.py

Modelo padrão: paraphrase-multilingual-mpnet-base-v2 (~1 GB, bom PT-BR).
Alternativas (edite MODEL_NAME abaixo):
  - "intfloat/multilingual-e5-large"  -> melhor qualidade, mais pesado
    (com E5, descomente os prefixos "passage: "/"query: " indicados)
  - "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" -> leve/rápido

Saída: embeddings/semantic/embeddings_all.parquet + manifest_semantic.json
O search_hybrid.py detecta essa pasta automaticamente e passa a usar os
vetores semânticos no lugar do LSA (requer sentence-transformers instalado
na máquina onde a busca roda).
"""
import json
import re
from pathlib import Path

import pandas as pd
import yaml
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
BASE = Path(__file__).parent
OUT = BASE / "embeddings" / "semantic"
OUT.mkdir(parents=True, exist_ok=True)

CORPORA = {"CPC": "chunks_CPC", "CC": "chunks_CC",
           "CDC": "chunks_CDC", "REN1000": "chunks_REN1000",
           "L8987": "chunks_L8987", "L9427": "chunks_L9427"}
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_chunks():
    rows = []
    for corpus, folder in CORPORA.items():
        for f in sorted((BASE / folder).glob("*.md")):
            raw = f.read_text(encoding="utf-8")
            m = FM_RE.match(raw)
            body = raw[m.end():].strip() if m else raw.strip()
            meta = yaml.safe_load(m.group(1)) if m else {}
            rows.append({"corpus": corpus, "file_name": f.name, "text": body,
                         "arts_range": str(meta.get("arts_range", ""))})
    return pd.DataFrame(rows)


def main():
    df = load_chunks()
    print(f"{len(df)} chunks carregados")
    model = SentenceTransformer(MODEL_NAME)

    texts = df["text"].tolist()
    # Para modelos E5, use: texts = ["passage: " + t for t in texts]
    emb = model.encode(texts, batch_size=16, show_progress_bar=True,
                       normalize_embeddings=True)
    df["embedding"] = [e.tolist() for e in emb]
    df.to_parquet(OUT / "embeddings_all.parquet", index=False)

    json.dump({"modelo": MODEL_NAME, "total_chunks": len(df),
               "embedding_dim": int(emb.shape[1]),
               "normalizado_l2": True,
               "prefixo_query": ""},  # p/ E5: "query: "
              open(OUT / "manifest_semantic.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Salvo em {OUT} | dim {emb.shape[1]}")


if __name__ == "__main__":
    main()
