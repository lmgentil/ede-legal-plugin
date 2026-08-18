# CONTEXTO_RAG.md — Base de conhecimento RAG Jurídico (migrada do projeto "RAG JURÍDICO")

> Este arquivo exporta a memória do projeto original para que qualquer sessão no projeto EDE
> recupere o contexto completo da base. Leia-o antes de mexer em qualquer arquivo desta pasta.

## Visão geral

Base de recuperação (RAG) com **434 chunks** cobrindo 6 corpora legislativos, índice de artigos
com cobertura 100% e busca híbrida BM25 + vetores densos.

| Corpus | Pasta | Arquivos | Artigos | Observações |
|--------|-------|----------|---------|-------------|
| CPC (Lei 13.105/2015) | `chunks_CPC/` | 130 | — | frontmatter YAML + breadcrumb + texto por capítulo |
| REN ANEEL 1.000/2021 | `chunks_REN1000/` | 67 | 675 | 1 chunk mestre (Index A) + 66 por capítulo/parte (Index B) |
| Código Civil | `chunks_CC/` | 198 | 2.046 | dual-index; nível hierárquico extra "Subtítulo" |
| CDC (Lei 8.078/1990) | `chunks_CDC/` | 18 | 119 | dual-index; hierarquia simples Título/Capítulo |
| Lei 8.987/1995 (Concessões) | `chunks_L8987/` | 13 | 47 | dual-index; 12 capítulos + mestre; notas "Contexto EDE" por capítulo |
| Lei 9.427/1996 (ANEEL) | `chunks_L9427/` | 8 | 35 | dual-index; 5 capítulos (2 divididos em _Pnn) + mestre; notas "Contexto EDE" |

## Arquitetura dual-index

- **Index A (chunk mestre):** 1 arquivo por corpus com o sumário/estrutura completa da norma.
- **Index B (chunks complementares):** 1 arquivo por capítulo/agrupamento com o texto integral
  dos artigos, frontmatter YAML (corpus, hierarquia, faixa de artigos) e breadcrumb hierárquico.
- Chunks maiores que ~15k caracteres foram divididos em partes (`_P01`, `_P02`, ...).

## Componentes

- `index_artigos.json` — mapeia todo artigo de cada corpus para o chunk que o contém
  (cobertura 100%). Usado para lookup direto por número de artigo.
- `search_hybrid.py` — busca híbrida BM25 + denso (alpha 0.65), com lookup por artigo,
  score de confiança calibrado e detecção de cobertura de termos. Caminhos relativos
  (`Path(__file__).parent`) — funciona em qualquer pasta.
  Dependências: `joblib`, `scikit-learn`, `pandas`, `pyarrow`, `rank_bm25`.
- `embeddings/` — vetores TF-IDF+LSA (fallback offline). Gerados no sandbox do Cowork,
  que bloqueia HuggingFace/OpenAI.
- `build_embeddings_semantic.py` + `RODAR_EMBEDDINGS_SEMANTICOS.bat` — gera embeddings
  semânticos (sentence-transformers/mpnet) **na máquina local do usuário**; quando
  `embeddings/semantic/` existir, o `search_hybrid.py` os usa automaticamente com prioridade.
- `calibrar_confianca.py` + `calibracao_confianca.json` — calibração dos limiares de confiança
  exibidos na busca (alta/média/baixa).
- `_originais_pre_split/` — versões dos chunks antes da divisão por tamanho (proveniência).

## Uso típico

```bash
# busca semântica/lexical
python search_hybrid.py "responsabilidade da distribuidora por interrupção" -k 5

# lookup direto por artigo
python search_hybrid.py "art. 373 CPC"
```

## Regras de resposta RAG (herdadas do projeto original)

1. Responder com base **exclusivamente** nos chunks recuperados; nunca inventar conteúdo normativo.
2. Citar sempre a fonte: corpus + chunk + artigo (ex.: `(Fonte: REN 1000, TII_C04_P02.md, art. 356)`).
3. Se o contexto recuperado não bastar: declarar "Não há informação suficiente nos documentos
   para responder com segurança."
4. Em conflito entre documentos, sinalizar a divergência e priorizar o mais recente/específico.

## Histórico

- Fase 4 (2026-08-18, EDE Legal Plugin): `search_hybrid.py` passou a ler
  `rag/config.yaml` (REQ-044) em vez de constantes hardcoded — mesmos
  valores, sem mudança de comportamento (validado contra `gold_set.json`:
  top-1 75%, top-3 88%, idêntico ao baseline). Adicionado estágio explícito
  de reranking (SPEC-0001 §15) que reordena os top-3k candidatos da fusão
  por um pequeno reforço de cobertura de termos antes do corte final em k.
  Indexação de jurisprudência (REQ-018) **adiada por decisão do usuário**
  — ver `PEND-002` em `docs/PENDENCIAS.md` e `ADR-0006`.
- Migrado do projeto Cowork "RAG JURÍDICO" em 2026-07-01/02.
- v1: 346 chunks vetorizados TF-IDF+LSA. v2: re-chunking para 413 chunks,
  `index_artigos.json` completo, busca híbrida calibrada.
- v3 (2026-07-09, estado atual): incorporadas **Lei 8.987/1995** (corpus `L8987`, 13 chunks,
  arts. 1-47) e **Lei 9.427/1996** (corpus `L9427`, 8 chunks, arts. 1-35), a partir dos
  compilados do Planalto (originais em `_originais_pre_split/L8987__planalto_compilado.md` e
  `L9427__planalto_compilado.md`). Total: 434 chunks, 6 corpora. Cada chunk complementar traz
  nota "Contexto EDE" ligando o capítulo às teses do contencioso de energia.
  `search_hybrid.py` ganhou guarda de defasagem: se `embeddings/semantic/` tiver contagem de
  chunks diferente do manifest LSA, cai para LSA com aviso — **rodar
  `RODAR_EMBEDDINGS_SEMANTICOS.bat` na máquina local após qualquer novo corpus**.
  Corrigido também o caminho fixo da sessão antiga em `embeddings/build_embeddings.py`
  (agora relativo ao script).
