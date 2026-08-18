#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
avaliar_recuperacao.py — Avaliação de qualidade da recuperação do RAG EDE.

Mede top-1 e top-3 do search_hybrid contra o gold-set (rag/gold_set.json).
Cada consulta do gold indica corpus + artigo(s); o chunk correto é resolvido
via index_artigos.json (art -> arquivo). Uma consulta "acerta o top-1" quando
o 1º resultado é um dos chunks esperados.

Rode SEMPRE após mudar embeddings, alpha ou o re-chunking — é o guarda contra
regressão silenciosa de recuperação (ex.: "prazo para contestação" retornando
liquidação de sentença).

Uso:
  python3 rag/avaliar_recuperacao.py
  python3 rag/avaliar_recuperacao.py --alpha 0.5 -k 5
  python3 rag/avaliar_recuperacao.py --gold rag/gold_set.json --verbose
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from search_hybrid import ALPHA_PADRAO, HybridSearcher  # noqa: E402


def arts_to_files(art_index, corpus, arts):
    """Resolve (corpus, artigos) -> conjunto de arquivos-chunk via index_artigos."""
    files = set()
    for e in art_index.get(corpus, []):
        for a in arts:
            if e["art_inicio"] <= a <= e["art_fim"]:
                files.add(e["file"])
    return files


def main():
    ap = argparse.ArgumentParser(description="Avaliação de recuperação do RAG EDE")
    ap.add_argument("--alpha", type=float, default=ALPHA_PADRAO)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--gold", default=os.path.join(BASE, "gold_set.json"))
    ap.add_argument("--verbose", action="store_true",
                    help="mostra os top-k de cada consulta")
    args = ap.parse_args()

    gold = json.load(open(args.gold, encoding="utf-8"))["consultas"]
    art_index = json.load(
        open(os.path.join(BASE, "index_artigos.json"), encoding="utf-8"))["corpora"]

    s = HybridSearcher(alpha=args.alpha)
    modo = "semântico" if s.semantic else "TF-IDF+LSA"

    n = len(gold)
    h1 = h3 = 0
    falhas = []
    sem_gabarito = []

    print(f"=== AVALIAÇÃO DE RECUPERAÇÃO ===")
    print(f"consultas={n} | vetores={modo} | alpha={args.alpha} | k={args.k}\n")

    for g in gold:
        exp = set(g.get("files", []))
        exp |= arts_to_files(art_index, g["corpus"], g.get("arts", []))
        if not exp:
            sem_gabarito.append(g["q"])
            continue
        res = s.query(g["q"], k=args.k, corpus=None)
        got = [r["file_name"] for r in res]
        top1 = bool(got) and got[0] in exp
        top3 = any(f in exp for f in got[:3])
        h1 += int(top1)
        h3 += int(top3)
        if not top1:
            falhas.append((g["q"], sorted(exp), got[:3]))
        flag = "OK " if top1 else ("~3 " if top3 else "XX ")
        print(f"[{flag}] {g['q'][:54]:54} -> {got[0] if got else '—'}")
        if args.verbose:
            for r in res:
                print(f"        {r.get('score','')} [{r['corpus']}] {r['file_name']}")

    aval = n - len(sem_gabarito)
    print(f"\ntop-1: {h1}/{aval} = {h1/aval:.0%}   |   top-3: {h3}/{aval} = {h3/aval:.0%}")
    if sem_gabarito:
        print(f"(⚠ {len(sem_gabarito)} consulta(s) sem gabarito resolvível — revisar gold_set)")

    if falhas:
        print("\n--- ERRARAM O TOP-1 (candidatos a re-chunk / ajuste de alpha) ---")
        for q, exp, got in falhas:
            print(f"  • {q}")
            print(f"      esperado: {exp}")
            print(f"      obteve  : {got}")

    # sinaliza regressão para uso em CI/manual: top-1 abaixo de 60% retorna != 0
    sys.exit(0 if aval == 0 or h1 / aval >= 0.60 else 2)


if __name__ == "__main__":
    main()
