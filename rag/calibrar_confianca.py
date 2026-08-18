#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta métricas para calibrar a camada de confiança do search_hybrid.py.
Roda na máquina do usuário (usa os embeddings semânticos se disponíveis) e
grava calibracao_confianca.json com bm25_raw / cosseno / cobertura do vencedor
de cada consulta de teste, rotulada como dentro ("in") ou fora ("out") do
escopo da base (CPC, CC, CDC, REN 1000)."""
import json
from search_hybrid import HybridSearcher

IN_SCOPE = [
    "prazo para contestação no procedimento comum",
    "cobrança indevida repetição do indébito em dobro",
    "usucapião extraordinária prazo",
    "responsabilidade civil por dano moral",
    "embargos de declaração omissão contradição",
    "suspensão do fornecimento de energia por inadimplemento",
    "vício do produto prazo de reclamação",
    "ressarcimento de danos elétricos equipamentos",
    "penhora de salário",
    "guarda compartilhada dos filhos",
    "honorários de sucumbência",
    "tarifa social baixa renda",
    "medidor adulterado TOI",
    "juros de mora",
    "resposta do réu prazo",
    "negativação indevida SPC Serasa",
    "corte de energia por falta de pagamento",
    "queima de eletrodomésticos oscilação de tensão",
    "troca de titularidade da unidade consumidora",
    "prazo em dobro para a fazenda pública",
]
OUT_SCOPE = [
    "negativa de cobertura de plano de saúde",
    "demissão por justa causa verbas rescisórias",
    "imposto de renda dedução",
    "crime de estelionato pena",
    "usucapião de marca registrada",
    "licenciamento ambiental de obra",
    "visto de trabalho para estrangeiro",
    "ICMS na conta de luz",
]


def main():
    s = HybridSearcher()
    rows = []
    for label, qs in (("in", IN_SCOPE), ("out", OUT_SCOPE)):
        for q in qs:
            top = s.search(q, k=1)[0]
            rows.append({"label": label, "q": q,
                         "bm25_raw": top["bm25_raw"], "denso": top["denso"],
                         "cobertura": top["cobertura"],
                         "top": top["file_name"], "corpus": top["corpus"]})
            print(f"{label:>3} bm={top['bm25_raw']:6.2f} cos={top['denso']:.3f} "
                  f"cob={top['cobertura']:.2f} | {q[:45]}")
    json.dump({"semantic": s.semantic, "rows": rows},
              open("calibracao_confianca.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nSalvo calibracao_confianca.json (semantic={s.semantic})")


if __name__ == "__main__":
    main()
