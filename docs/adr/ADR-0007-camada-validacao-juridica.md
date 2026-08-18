# ADR-0007 — Camada de Validação Jurídica desacoplada do Retrieval

## Status

Aceito (2026-08-18) — Fase 5 (RAG Jurídico → Validação Jurídica).

## Contexto

Até a Fase 4, `rag/search_hybrid.py` entregava resultados de recuperação
(BM25 + denso + lookup por artigo) já com um score de relevância e uma
heurística de confiança (`confianca()`). Isso resolve "o que é semântica/
lexicalmente parecido com a pergunta", mas não resolve uma pergunta
diferente e mais estrita: **uma citação jurídica específica — "art. 373,
II, CPC" — corresponde de fato ao texto do corpus?**

SPEC-0001 §5-30 (Fase 5) exige distinguir explicitamente:

```text
RECUPERADO  (relevante, por score)
      ≠
VALIDADO    (existe, com correspondência exata de artigo/parágrafo/
             inciso/alínea, e tem autoridade/vigência classificadas)
```

Um resultado com `score_final = 0.94` pode ser o chunk certo para uma
busca exploratória e, ainda assim, não confirmar nenhuma citação
específica — porque nenhuma citação específica foi pedida. Já uma citação
como `art. 373, III, CPC` pode ter um candidato de altíssima similaridade
(o próprio art. 373, que existe) e mesmo assim estar errada, porque o
inciso III não existe no caput daquele artigo (só existe, com outro
sentido, dentro do § 3º). Similaridade não é identidade normativa.

## Decisão

Criar `rag/legal_validation/` como camada **posterior e desacoplada** de
`rag/search_hybrid.py`:

```text
search_hybrid.py                    legal_validation/
  (RETRIEVAL)                          (LEGAL VALIDATION)
─────────────────────           ───────────────────────────────
BM25 + denso + fusão      ─┐
+ reranking + lookup       ├──▶  enriquecer_resultados(resultados)
  por artigo               │       -> metadados (autoridade, vigência,
                            │          proveniência) sobre CADA resultado
                            │          de recuperação, sem alegação de
                            │          citação específica
                            │
citação em texto livre     ┴──▶  validar_citacao(texto)
("art. 373, II, CPC")               -> parse -> lookup exato no índice
                                     (index_artigos.json, LIDO DIRETO,
                                     sem instanciar HybridSearcher) ->
                                     confere parágrafo/inciso/alínea no
                                     TEXTO real do artigo -> veredito
                                     estruturado (nunca "quase certo")
```

Pontos centrais da decisão:

1. **`legal_validation` não importa `HybridSearcher` no caminho principal
   de `validar_citacao()`.** Validar uma citação não precisa de
   embeddings — só precisa do índice de artigos (JSON) e do texto do
   chunk. O `HybridSearcher` só é importado, tardiamente e com fallback
   silencioso, no estágio opcional de **sugestão de candidato** (SPEC-0001
   §16) quando o lookup exato falha — e mesmo aí, o candidato sugerido
   nunca é promovido a citação validada.
2. **Dois eixos independentes no modelo canônico** (`models.fonte_juridica`,
   §9/§21): `validation_status` (a citação corresponde ao texto?) e
   `vigencia`/`authority_level` (a fonte é oficial? a norma está em vigor?)
   nunca colapsam num único booleano. Hoje `vigencia` é sempre
   `NAO_VERIFICADA` para todo o corpus, por não existir, na infraestrutura
   atual, nenhuma fonte real de verificação temporal — decisão
   deliberada, não uma lacuna esquecida (ver `temporal_status.py`).
3. **Fail closed em cada ponto de decisão** (CLAUDE.md §17): artigo
   inexistente, inciso fora do escopo certo, parágrafo não encontrado,
   diploma ambíguo — tudo cai em `NAO_VALIDADA`/`AMBIGUA`/
   `FONTE_INSUFICIENTE`, nunca num valor aproximado por proximidade
   textual.

## Alternativas consideradas

- **Adicionar a validação dentro de `search_hybrid.py`.** Rejeitada:
  misturaria ranking de relevância (que deve poder mudar de algoritmo,
  parâmetro, modelo de embedding) com correspondência normativa exata
  (que não deve variar com o algoritmo de busca) — exatamente o
  acoplamento que SPEC-0001 §22 pede para evitar.
- **Validar citação inteiramente via busca híbrida (top-1 == validado).**
  Rejeitada: é o erro central que a Fase 5 existe para prevenir — usar
  similaridade semântica como prova de identidade normativa (ver teste
  `test_incompatibilidade_inciso_nao_e_promovida_por_proximidade`).
- **Um único campo booleano `validado: true/false`.** Rejeitado: perde a
  distinção entre "não achei o artigo" (fail closed determinístico),
  "achei o artigo mas não esse inciso" (correspondência específica
  falhou) e "diploma ambíguo, nem sei em qual corpus procurar" — cada um
  exige um tratamento diferente a jusante (ex.: pela Contestação, Fase 6).

## Consequências

- Futuras Skills (Contestação e além) podem consumir `validar_citacao()` e
  `enriquecer_resultados()` sem acoplamento ao algoritmo de ranking —
  trocar `alpha`, o modelo de embeddings, ou adicionar reranking mais
  sofisticado no futuro não muda o contrato de validação.
- A interface (`validar_citacao`, `enriquecer_resultados`,
  `fonte_juridica`) é suficientemente enxuta para ser exposta futuramente
  por MCP (`consultar_rag`, `buscar_dispositivo`, `validar_citacao`,
  `status_corpus` — SPEC-0001 §37) sem reescrita, mas **nenhum MCP foi
  implementado nesta fase**; se/quando isso avançar, merece ADR própria.
- `vigencia` permanecer sempre `NAO_VERIFICADA` é uma limitação real e
  visível (não escondida atrás de um campo omitido): qualquer consumidor
  desta API sabe, pelo próprio dado, que precisa tratar a norma como
  "não confirmada como vigente", não presumir.
- Indexação de jurisprudência (`PEND-002`) permanece fora de escopo; o
  modelo (`fonte_juridica`, `classificar_autoridade`) já comporta um
  `tipo="jurisprudencia"` e um nível de autoridade próprio quando essa
  pendência for resolvida, sem exigir novo modelo de dados.
