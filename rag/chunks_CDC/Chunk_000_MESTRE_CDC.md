---
chunk_id: "000"
tipo: chunk_mestre
lei: "Lei nº 8.078/1990 — Código de Defesa do Consumidor"
descricao: "Mapa sistemático completo do CDC para roteamento e contexto em RAG jurídico"
total_chunks: 17
artigos_cobertos: "1 – 119 (incl. 54-A a 54-G e 104-A a 104-C)"
indice: A
---


> ⚠ **NOTA (atualização 2026-07):** chunks grandes foram divididos em partes (sufixo `_Pnn`). Tabelas antigas deste arquivo podem citar nomes que não existem mais. Para roteamento, use o **MAPA ATUALIZADO DE CHUNKS** ao final deste arquivo ou o `index_artigos.json`.
# CHUNK MESTRE — Código de Defesa do Consumidor (Lei nº 8.078/1990)

> **Propósito deste arquivo:** Fornecer contexto sistemático global para o sistema RAG. Use este chunk para identificar *em qual chunk buscar* a resposta a uma pergunta sobre o CDC, e para compreender a estrutura lógica da lei antes de recuperar artigos específicos. Este é o **Index A** da arquitetura dual-index; os chunks complementares (Chunk_001 a Chunk_17) formam o **Index B**.

---

## 1. VISÃO GERAL DA LEI

| Item | Dado |
|------|------|
| Lei | Lei nº 8.078, de 11 de setembro de 1990 |
| Nome | Código de Defesa do Consumidor (CDC) |
| Vigência | 180 dias após a publicação (março/1991) |
| Total de artigos | 119 (numeração oficial; alguns artigos possuem desdobramentos com sufixo de letra: 54-A a 54-G — superendividamento, incluídos pela Lei nº 14.181/2021; 104-A a 104-C — conciliação no superendividamento) |
| Total de chunks nesta base | 17 (Chunk_000 = mestre; Chunk_001 a Chunk_17 = complementares) |
| Estrutura | 6 Títulos, sem Livros ou Partes |
| Hierarquia interna | Título › Capítulo (Seções mantidas dentro do chunk do capítulo) |

---

## 2. MAPA HIERÁRQUICO COMPLETO

#### TÍTULO I — Dos Direitos do Consumidor (Arts. 1–60)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [001] | Cap. I — Disposições Gerais | 1–3 |
| [002] | Cap. II — Da Política Nacional de Relações de Consumo | 4–5 |
| [003] | Cap. III — Dos Direitos Básicos do Consumidor | 6–7 |
| [004] | Cap. IV — Da Qualidade de Produtos e Serviços, da Prevenção e da Reparação dos Danos | 8–28 |
| [005] | Cap. V — Das Práticas Comerciais | 29–45 |
| [006] | Cap. VI — Da Proteção Contratual | 46–54 |
| [007] | Cap. VI-A — DA PREVENÇÃO E DO TRATAMENTO DO SUPERENDIVIDAMENTO | 54-A–54-G |
| [008] | Cap. VII — Das Sanções Administrativas | 55–60 |

#### TÍTULO II — Das Infrações Penais (Arts. 61–80)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [009] | *(título integral, sem capítulos)* | 61–80 |

#### TÍTULO III — Da Defesa do Consumidor em Juízo (Arts. 81–104-C)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [010] | Cap. I — Disposições Gerais | 81–90 |
| [011] | Cap. II — Das Ações Coletivas Para a Defesa de Interesses Individuais Homogêneos | 91–100 |
| [012] | Cap. III — Das Ações de Responsabilidade do Fornecedor de Produtos e Serviços | 101–102 |
| [013] | Cap. IV — Da Coisa Julgada | 103–104 |
| [014] | Cap. V — DA CONCILIAÇÃO NO SUPERENDIVIDAMENTO | 104-A–104-C |

#### TÍTULO IV — Do Sistema Nacional de Defesa do Consumidor (Arts. 105–106)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [015] | *(título integral, sem capítulos)* | 105–106 |

#### TÍTULO V — Da Convenção Coletiva de Consumo (Arts. 107–108)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [016] | *(título integral, sem capítulos)* | 107–108 |

#### TÍTULO VI — Disposições Finais (Arts. 109–119)

| Chunk | Capítulo | Artigos |
|-------|----------|---------|
| [017] | *(título integral, sem capítulos)* | 109–119 |

---

## 3. ÍNDICE TEMÁTICO RÁPIDO

Use este índice para identificar o(s) chunk(s) correto(s) pela temática da pergunta:

| Tema | Chunk(s) |
|------|----------|
| Conceitos básicos (consumidor, fornecedor, produto, serviço) | 001 |
| Política Nacional das Relações de Consumo / princípios | 002 |
| Direitos básicos do consumidor | 003 |
| Qualidade de produtos e serviços / prevenção e reparação de danos | 004 |
| Responsabilidade pelo fato do produto/serviço (vício, defeito) | 004 |
| Vícios de qualidade / decadência e prescrição (Arts. 26-27) | 004 |
| Práticas comerciais — oferta, publicidade, práticas abusivas | 005 |
| Publicidade enganosa e abusiva | 005 |
| Cobrança de dívidas / bancos de dados e cadastros de consumidores | 005 |
| Proteção contratual — cláusulas abusivas, contratos de adesão | 006 |
| Direito de arrependimento (Art. 49) | 006 |
| Garantia contratual | 006 |
| Superendividamento — prevenção e tratamento (crédito responsável) | 007 |
| Repactuação de dívidas / conciliação no superendividamento | 007, 014 |
| Sanções administrativas | 008 |
| Infrações penais / crimes contra o consumidor | 009 |
| Defesa do consumidor em juízo — disposições gerais / legitimidade | 010 |
| Ações coletivas — interesses difusos, coletivos e individuais homogêneos | 011 |
| Inversão do ônus da prova | 010 |
| Responsabilidade do fornecedor em juízo / desconsideração da personalidade jurídica | 012 |
| Coisa julgada nas ações coletivas | 013 |
| Sistema Nacional de Defesa do Consumidor (SNDC) / Procons | 015 |
| Convenção coletiva de consumo | 016 |
| Disposições finais | 017 |

---

## 4. REGRAS DE ROTEAMENTO PARA O SISTEMA RAG

```
SE a pergunta menciona:
  - artigo específico (ex: "art. 18", "art. 51", "art. 54-A") → localizar no Mapa Hierárquico (Seção 2) o chunk cujo range inclui o número
  - "quem é consumidor", "quem é fornecedor", "produto", "serviço" (definições) → Chunk 001
  - "princípios", "vulnerabilidade do consumidor" → Chunk 002
  - "direitos básicos do consumidor" → Chunk 003
  - "vício do produto", "vício do serviço", "defeito", "responsabilidade objetiva", "decadência", "prescrição" (danos ao consumidor) → Chunk 004
  - "oferta", "publicidade enganosa", "publicidade abusiva", "práticas abusivas", "cobrança de dívidas", "cadastro de consumidores", "SPC", "Serasa" → Chunk 005
  - "cláusula abusiva", "contrato de adesão", "direito de arrependimento", "garantia" → Chunk 006
  - "superendividamento", "crédito responsável", "repactuação de dívidas" → Chunks 007, 014
  - "sanções administrativas", "multa administrativa" → Chunk 008
  - "crime contra o consumidor", "infração penal" → Chunk 009
  - "ação coletiva", "interesse difuso", "interesse coletivo", "interesse individual homogêneo" → Chunk 011
  - "inversão do ônus da prova", "legitimidade para agir" → Chunk 010
  - "desconsideração da personalidade jurídica" (CDC, Art. 28) → Chunk 012
  - "coisa julgada" (ações coletivas) → Chunk 013
  - "conciliação no superendividamento" → Chunk 014
  - "Procon", "SNDC", "Sistema Nacional de Defesa do Consumidor" → Chunk 015
  - "convenção coletiva de consumo" → Chunk 016
  - "disposições finais", "alterações na Lei da Ação Civil Pública" → Chunk 017
```

---

## 5. INSTRUÇÕES DE USO DO DUAL-INDEX

**Index A (este chunk — Chunk_000_MESTRE_CDC.md):**
- Usar para responder perguntas sobre: *qual a estrutura do CDC / em que título-capítulo está tal matéria / quais chunks preciso combinar*.
- Contém o mapa hierárquico completo (Seção 2) e o índice temático (Seção 3).
- Sempre carregar em conjunto com o(s) chunk(s) do Index B relevante(s) ao tema da pergunta.

**Index B (Chunk_001.md … Chunk_17.md):**
- Usar para recuperar o texto integral dos artigos sobre um tema específico.
- Cada chunk corresponde a um Capítulo (ou, na ausência de Capítulo, ao Título integral).
- Frontmatter de cada chunk contém: `titulo`, `capitulo`, `arts_range`, `art_inicio`, `art_fim`, `linha_inicio`, `linha_fim`.
- Selecionar pelo `chunk_id` indicado nas Seções 2–4 deste chunk mestre.
- Combinar sempre com o chunk mestre para contextualização sistemática.

---

*Gerado automaticamente a partir de OpenL-2607011446.md (texto compilado da Lei nº 8.078/1990, Presidência da República/Casa Civil, consultado em 01/07/2026) — Base: 17 chunks complementares, Arts. 1–119 (incl. 54-A–54-G e 104-A–104-C).*

<!-- MAPA_ATUALIZADO_INICIO -->

## MAPA ATUALIZADO DE CHUNKS (fonte: index_artigos.json)

Total de chunks complementares: **17**

| Arquivo | Artigos | Capítulo/Título |
|---|---|---|
| Chunk_001_DISPOSICOES_GERAIS.md | 1–3 | CAPÍTULO I — Disposições Gerais |
| Chunk_002_DA_POLITICA_NACIONAL_DE_RELACOES_DE_CONSUMO.md | 4–5 | CAPÍTULO II — Da Política Nacional de Relações de Consumo |
| Chunk_003_DOS_DIREITOS_BASICOS_DO_CONSUMIDOR.md | 6–7 | CAPÍTULO III — Dos Direitos Básicos do Consumidor |
| Chunk_004_DA_QUALIDADE_DE_PRODUTOS_E_SERVICOS_DA_PREVEN.md | 8–28 | CAPÍTULO IV — Da Qualidade de Produtos e Serviços, da Prevenção e da Reparação dos Danos |
| Chunk_005_DAS_PRATICAS_COMERCIAIS.md | 29–45 | CAPÍTULO V — Das Práticas Comerciais |
| Chunk_006_DA_PROTECAO_CONTRATUAL.md | 46–54 | CAPÍTULO VI — Da Proteção Contratual |
| Chunk_007_DA_PREVENCAO_E_DO_TRATAMENTO_DO_SUPERENDIVIDA.md | 54–54 | CAPÍTULO VI-A — DA PREVENÇÃO E DO TRATAMENTO DO SUPERENDIVIDAMENTO |
| Chunk_008_DAS_SANCOES_ADMINISTRATIVAS.md | 55–60 | CAPÍTULO VII — Das Sanções Administrativas |
| Chunk_009_DAS_INFRACOES_PENAIS.md | 61–80 | TÍTULO II — Das Infrações Penais |
| Chunk_010_DISPOSICOES_GERAIS.md | 81–90 | CAPÍTULO I — Disposições Gerais |
| Chunk_011_DAS_ACOES_COLETIVAS_PARA_A_DEFESA_DE_INTERESS.md | 91–100 | CAPÍTULO II — Das Ações Coletivas Para a Defesa de Interesses Individuais Homogêneos |
| Chunk_012_DAS_ACOES_DE_RESPONSABILIDADE_DO_FORNECEDOR_D.md | 101–102 | CAPÍTULO III — Das Ações de Responsabilidade do Fornecedor de Produtos e Serviços |
| Chunk_013_DA_COISA_JULGADA.md | 103–104 | CAPÍTULO IV — Da Coisa Julgada |
| Chunk_014_DA_CONCILIACAO_NO_SUPERENDIVIDAMENTO.md | 104–104 | CAPÍTULO V — DA CONCILIAÇÃO NO SUPERENDIVIDAMENTO |
| Chunk_015_DO_SISTEMA_NACIONAL_DE_DEFESA_DO_CONSUMIDOR.md | 105–106 | TÍTULO IV — Do Sistema Nacional de Defesa do Consumidor |
| Chunk_016_DA_CONVENCAO_COLETIVA_DE_CONSUMO.md | 107–108 | TÍTULO V — Da Convenção Coletiva de Consumo |
| Chunk_017_DISPOSICOES_FINAIS.md | 109–119 | TÍTULO VI — Disposições Finais |

<!-- MAPA_ATUALIZADO_FIM -->
