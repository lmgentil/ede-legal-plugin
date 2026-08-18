---
chunk_id: "000"
tipo: mestre
lei: "Lei nº 13.105/2015 — Código de Processo Civil"
descricao: "Mapa sistemático completo do CPC para roteamento e contexto em RAG jurídico"
total_chunks: 106
artigos_cobertos: "1 – 1.072"
---


> ⚠ **NOTA (atualização 2026-07):** chunks grandes foram divididos em partes (sufixo `_Pnn`). Tabelas antigas deste arquivo podem citar nomes que não existem mais. Para roteamento, use o **MAPA ATUALIZADO DE CHUNKS** ao final deste arquivo ou o `index_artigos.json`.
# CHUNK MESTRE — Código de Processo Civil (Lei 13.105/2015)

> **Propósito deste arquivo:** Fornecer contexto sistemático global para o sistema RAG. Use este chunk para identificar *em qual chunk buscar* a resposta a uma pergunta sobre o CPC, e para compreender a estrutura lógica da lei antes de recuperar artigos específicos.

---

## 1. VISÃO GERAL DA LEI

| Item | Dado |
|------|------|
| Lei | Lei nº 13.105, de 16 de março de 2015 |
| Nome | Código de Processo Civil (CPC 2015) |
| Vigência | 18 de março de 2016 (1 ano após publicação) |
| Total de artigos | 1.072 |
| Total de chunks nesta base | 106 (Chunk_001 a Chunk_106) |
| Estrutura | 2 Partes + Livro Complementar |

---

## 2. MAPA HIERÁRQUICO COMPLETO

### PARTE GERAL (Arts. 1 – 317)

#### LIVRO I — Das Normas Processuais Civis (Arts. 1–15)

| Chunk | Capítulo | Artigos | Conteúdo |
|-------|----------|---------|----------|
| [001] | Cap. I | 1 – 12 | **Normas Fundamentais do Processo Civil** — princípios constitucionais, boa-fé, cooperação, contraditório, publicidade, fundamentação, ordem cronológica |
| [002] | Cap. II | 13 – 15 | **Aplicação das Normas Processuais** — irretroatividade, aplicação imediata, subsidiariedade a processos trabalhistas/eleitorais/administrativos |

#### LIVRO II — Da Função Jurisdicional (Arts. 16–69)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [003] | Título I | 16 – 20 | **Jurisdição e Ação** — jurisdição civil, legitimidade, interesse, ação declaratória |
| [004] | Cap. I | 21 – 25 | **Limites da Jurisdição Nacional** — competência internacional brasileira, réu domiciliado no Brasil, obrigação cumprida no Brasil |
| [005] | Cap. II | 26 – 41 | **Cooperação Internacional** — cartas rogatórias, auxílio direto, central de cooperação jurídica |
| [006] | Cap. I | 42 – 66 | **Competência Interna** — competência absoluta, relativa, modificações, perpetuatio jurisdictionis, conexão, continência |
| [007] | Cap. II | 67 – 69 | **Cooperação Nacional** — cartas precatórias e de ordem entre juízos brasileiros |

#### LIVRO III — Dos Sujeitos do Processo (Arts. 70–187)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [008] | Cap. I | 70 – 76 | **Capacidade Processual** — capacidade para ser parte, capacidade processual, curador especial, incapazes |
| [009] | Cap. II | 77 – 102 | **Deveres das Partes e Procuradores** — litigância de má-fé, boa-fé processual, multas, responsabilidade por dano processual |
| [010] | Cap. III | 103 – 107 | **Procuradores** — mandato judicial, substabelecimento, procuração |
| [011] | Cap. IV | 108 – 112 | **Sucessão das Partes e Procuradores** — alienação da coisa litigiosa, morte da parte, sucessão processual |
| [012] | Título II | 113 – 118 | **Litisconsórcio** — litisconsórcio facultativo/necessário, unitário/simples, recusa de formação, poderes individuais |
| [013] | Cap. I | 119 – 124 | **Assistência** — assistência simples e litisconsorcial, intervenção de terceiros |
| [014] | Cap. II | 125 – 129 | **Denunciação da Lide** — hipóteses, procedimento, contestação do denunciado |
| [015] | Cap. III | 130 – 132 | **Chamamento ao Processo** — fiador, devedor solidário |
| [016] | Cap. IV | 133 – 137 | **Desconsideração da Personalidade Jurídica** — incidente, pedido, contraditório, responsabilidade do sócio |
| [017] | Cap. V | 138 | **Amicus Curiae** — admissão, poderes, participação |
| [018] | Cap. I | 139 – 143 | **Poderes, Deveres e Responsabilidade do Juiz** — poderes de direção, dever de urbanidade, responsabilidade civil |
| [019] | Cap. II | 144 – 148 | **Impedimentos e Suspeição** — hipóteses de impedimento e suspeição do juiz |
| [020] | Cap. III | 149 – 175 | **Auxiliares da Justiça** — escrivão, oficial de justiça, perito, depositário, intérprete, administrador |
| [021] | Título V | 176 – 181 | **Ministério Público** — funções, fiscalização, prazo em dobro, recusabilidade |
| [022] | Título VI | 182 – 184 | **Advocacia Pública** — União, Estados, Municípios, prazo em dobro |
| [023] | Título VII | 185 – 187 | **Defensoria Pública** — atuação, prazo em dobro |

#### LIVRO IV — Dos Atos Processuais (Arts. 188–293)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [024] | Cap. I | 188 – 211 | **Forma dos Atos Processuais** — processo eletrônico, petições, atas, publicidade, atos em língua estrangeira |
| [025] | Cap. II | 212 – 217 | **Tempo e Lugar dos Atos Processuais** — dias e horas hábeis, férias, feriados |
| [026] | Cap. III | 218 – 235 | **Prazos** — contagem, dilatação, peremptório vs. dilatório, prazo em dobro para Fazenda e MP |
| [027] | Cap. I | 236 – 237 | **Comunicação dos Atos — Disposições Gerais** — citação e intimação em geral |
| [028] | Cap. II | 238 – 259 | **Citação** — modalidades (postal, oficial de justiça, edital, eletrônica), efeitos, vícios |
| [029] | Cap. III | 260 – 268 | **Cartas** — carta precatória, rogatória, de ordem, arbitral |
| [030] | Cap. IV | 269 – 275 | **Intimações** — modalidades, intimação pessoal, intimação pelo Diário Oficial |
| [031] | Título III | 276 – 283 | **Nulidades** — princípios, nulidade absoluta/relativa, aproveitamento dos atos, convalidação |
| [032] | Título IV | 284 – 290 | **Distribuição e Registro** — distribuição por dependência, livre distribuição, registro |
| [033] | Título V | 291 – 293 | **Valor da Causa** — fixação, impugnação ao valor |

#### LIVRO V — Da Tutela Provisória (Arts. 294–311)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [034] | Título I | 294 – 299 | **Tutela Provisória — Disposições Gerais** — espécies (urgência/evidência), fungibilidade, estabilização |
| [035] | Cap. I | 300 – 302 | **Tutela de Urgência — Disposições Gerais** — pressupostos (fumus + periculum), caução, reversibilidade |
| [036] | Cap. II | 303 – 304 | **Tutela Antecipada Antecedente** — procedimento, adiantamento de tese, estabilização |
| [037] | Cap. III | 305 – 310 | **Tutela Cautelar Antecedente** — procedimento, efetivação, conversão |
| [038] | Título III | 311 | **Tutela da Evidência** — hipóteses (abuso do direito de defesa, tese repetitiva, prova documental suficiente, pedido incontroverso) |

#### LIVRO VI — Formação, Suspensão e Extinção do Processo (Arts. 312–317)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [039] | Título I | 312 | **Formação do Processo** — propositura da ação, litispendência |
| [040] | Título II | 313 – 315 | **Suspensão do Processo** — hipóteses, prazo máximo, impedimento do juiz |
| [041] | Título III | 316 – 317 | **Extinção do Processo** — sem/com resolução do mérito (remissão aos arts. 485 e 487) |

---

### PARTE ESPECIAL — LIVRO I — Do Processo de Conhecimento e do Cumprimento de Sentença (Arts. 318–770)

#### Título I — Do Procedimento Comum (Arts. 318–512)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [042] | Cap. I | 318 | **Disposições Gerais** — procedimento comum como regra supletiva |
| [043] | Cap. II | 319 – 331 | **Petição Inicial** — requisitos, emenda, indeferimento, distribuição, aditamento |
| [044] | Cap. III | 332 | **Improcedência Liminar do Pedido** — hipóteses (súmula, repetitivo, decadência, prescrição) |
| [045] | Cap. IV | 333 | **Conversão de Ação Individual em Coletiva** — requisitos, vedação |
| [046] | Cap. V | 334 | **Audiência de Conciliação ou Mediação** — designação, dispensa, mediadores, ausência injustificada |
| [047] | Cap. VI | 335 – 342 | **Contestação** — prazo, forma, princípio da impugnação especificada, preliminares, mérito |
| [048] | Cap. VII | 343 | **Reconvenção** — cabimento, prazo, autonomia, pedido contraposto |
| [049] | Cap. VIII | 344 – 346 | **Revelia** — efeitos, exceções (matéria de ordem pública, litisconsórcio, direito indisponível) |
| [050] | Cap. IX | 347 – 353 | **Providências Preliminares e Saneamento** — réplica, saneamento, organização do processo |
| [051] | Cap. X | 354 – 357 | **Julgamento conforme o Estado do Processo** — extinção, improcedência liminar, julgamento antecipado do mérito, julgamento antecipado parcial |
| [052] | Cap. XI | 358 – 368 | **Audiência de Instrução e Julgamento** — designação, ordem, colheita de provas, debates orais, sentença |
| [053] | Cap. XII | 369 – 484 | **Das Provas** — ônus, provas em espécie: depoimento pessoal, confissão, exibição, documental, testemunhal, pericial, inspeção judicial |
| [054] | Cap. XIII | 485 – 508 | **Sentença e Coisa Julgada** — extinção sem mérito (art. 485), com mérito (art. 487), requisitos, efeitos, coisa julgada material e formal, relativização |
| [055] | Cap. XIV | 509 – 512 | **Liquidação de Sentença** — por arbitramento, pelo procedimento comum, liquidação provisória |

#### Título II — Do Cumprimento de Sentença (Arts. 513–538)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [056] | Cap. I | 513 – 519 | **Disposições Gerais** — título judicial, requerimento, multa do art. 523, responsabilidade patrimonial |
| [057] | Cap. II | 520 – 522 | **Cumprimento Provisório** — atos de constrição, multa, carta fiança, responsabilidade |
| [058] | Cap. III | 523 – 527 | **Cumprimento Definitivo — Obrigação de Pagar Quantia (particular)** — multa de 10%, honorários, protesto, negativação |
| [059] | Cap. IV | 528 – 533 | **Cumprimento de Sentença — Alimentos** — prisão civil, desconto em folha, penhora |
| [060] | Cap. V | 534 – 535 | **Cumprimento de Sentença — Fazenda Pública** — precatório, RPV, impugnação |
| [061] | Cap. VI | 536 – 538 | **Cumprimento de Sentença — Obrigação de Fazer/Não Fazer/Entrega de Coisa** — astreintes, medidas de apoio |

#### Título III — Dos Procedimentos Especiais (Arts. 539–770)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [062] | Cap. I | 539 – 549 | **Ação de Consignação em Pagamento** — consignação judicial e extrajudicial, contestação, levantamento |
| [063] | Cap. II | 550 – 553 | **Ação de Exigir Contas** — prestação de contas, duas fases, saldo credor/devedor |
| [064] | Cap. III | 554 – 568 | **Ações Possessórias** — reintegração, manutenção, interdito, fungibilidade, liminar, turbação coletiva |
| [065] | Cap. IV | 569 – 598 | **Ação de Divisão e Demarcação de Terras** — demarcação, divisão, duas fases, sentença |
| [066] | Cap. V | 599 – 609 | **Ação de Dissolução Parcial de Sociedade** — exclusão de sócio, apuração de haveres, dissolução |
| [067] | Cap. VI | 610 – 673 | **Inventário e Partilha** — inventário judicial e extrajudicial, arrolamento, colação, sobrepartilha |
| [068] | Cap. VII | 674 – 681 | **Embargos de Terceiro** — cabimento, prazo, liminar, oposição à penhora |
| [069] | Cap. VIII | 682 – 686 | **Oposição** — cabimento, prazo, conexão com ação principal |
| [070] | Cap. IX | 687 – 692 | **Habilitação** — habilitação de herdeiros, sucessão processual por morte |
| [071] | Cap. X | 693 – 699 | **Ações de Família** — mediação obrigatória, alimentos provisionais, guarda |
| [072] | Cap. XI | 700 – 702 | **Ação Monitória** — requisitos, mandado monitório, embargos, conversão em executivo |
| [073] | Cap. XII | 703 – 706 | **Homologação do Penhor Legal** |
| [074] | Cap. XIII | 707 – 711 | **Regulação de Avaria Grossa** — direito marítimo |
| [075] | Cap. XIV | 712 – 718 | **Restauração de Autos** — perda/destruição dos autos, reconstituição |
| [076] | Cap. XV | 719 – 770 | **Jurisdição Voluntária** — disposições gerais, interdição, testamentos, herança jacente, organização e fiscalização de fundações |

---

### PARTE ESPECIAL — LIVRO II — Do Processo de Execução (Arts. 771–925)

#### Título I — Da Execução em Geral (Arts. 771–796)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [077] | Cap. I | 771 – 777 | **Disposições Gerais da Execução** — aplicação subsidiária do processo de conhecimento, título extrajudicial |
| [078] | Cap. II | 778 – 780 | **Partes na Execução** — exequente, executado, legitimidade |
| [079] | Cap. III | 781 – 782 | **Competência na Execução** — foro do domicílio do executado, opção do exequente |
| [080] | Cap. IV | 783 – 788 | **Requisitos da Execução** — título certo, líquido e exigível, inadimplemento, títulos extrajudiciais (art. 784) |
| [081] | Cap. V | 789 – 796 | **Responsabilidade Patrimonial** — bens presentes e futuros, bem de família, fraude à execução, desconsideração |

#### Título II — Das Diversas Espécies de Execução (Arts. 797–913)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [082] | Cap. I | 797 – 805 | **Disposições Gerais** — execução provisória x definitiva, arresto, averbação premonitória |
| [083] | Cap. II | 806 – 813 | **Execução para Entrega de Coisa** — coisa certa e coisa incerta, busca e apreensão |
| [084] | Cap. III | 814 – 823 | **Execução de Obrigações de Fazer ou Não Fazer** — astreintes, terceiro executor, desfazimento |
| [085] | Cap. IV | 824 – 909 | **Execução por Quantia Certa** — penhora, avaliação, expropriação, adjudicação, alienação, usufruto executivo, defesa do executado |
| [086] | Cap. V | 910 | **Execução contra a Fazenda Pública** — precatório, RPV, sequestro |
| [087] | Cap. VI | 911 – 913 | **Execução de Alimentos** — prisão civil, desconto em folha, execução especial |

#### Títulos III e IV — Embargos à Execução e Extinção (Arts. 914–925)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [088] | Título III | 914 – 920 | **Embargos à Execução** — prazo, efeito suspensivo, matérias arguíveis, rejeição liminar |
| [089] | Cap. I | 921 – 923 | **Suspensão do Processo de Execução** — hipóteses, prazo de prescrição intercorrente |
| [090] | Cap. II | 924 – 925 | **Extinção do Processo de Execução** — hipóteses, sentenças com/sem mérito |

---

### PARTE ESPECIAL — LIVRO III — Processos nos Tribunais e Meios de Impugnação (Arts. 926–1.044)

#### Título I — Ordem dos Processos e Competência Originária dos Tribunais (Arts. 926–993)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [091] | Cap. I | 926 – 928 | **Disposições Gerais — Tribunais** — uniformização de jurisprudência, precedentes, IRDR, súmulas vinculantes |
| [092] | Cap. II | 929 – 946 | **Ordem dos Processos no Tribunal** — distribuição, sessão de julgamento, sustentação oral, acórdão, embargos infringentes |
| [093] | Cap. III | 947 | **Incidente de Assunção de Competência (IAC)** — requisitos, efeito vinculante |
| [094] | Cap. IV | 948 – 950 | **Incidente de Arguição de Inconstitucionalidade** — cláusula de reserva de plenário, maioria absoluta |
| [095] | Cap. V | 951 – 959 | **Conflito de Competência** — positivo/negativo, suscitação, competência para julgar |
| [096] | Cap. VI | 960 – 965 | **Homologação de Decisão Estrangeira e Exequatur** — STJ, requisitos, carta rogatória |
| [097] | Cap. VII | 966 – 975 | **Ação Rescisória** — hipóteses (art. 966), prazo decadencial de 2 anos, depósito, competência |
| [098] | Cap. VIII | 976 – 987 | **IRDR — Incidente de Resolução de Demandas Repetitivas** — requisitos, suspensão, tese, revisão |
| [099] | Cap. IX | 988 – 993 | **Reclamação** — cabimento (preservar competência, garantir autoridade de decisão), STF/STJ/Tribunais |

#### Título II — Dos Recursos (Arts. 994–1.044)

| Chunk | Seção | Artigos | Conteúdo |
|-------|-------|---------|----------|
| [100] | Cap. I | 994 – 1.008 | **Recursos — Disposições Gerais** — espécies, pressupostos, preparo, deserção, tempestividade, fungibilidade, efeito devolutivo/suspensivo/translativo |
| [101] | Cap. II | 1.009 – 1.014 | **Apelação** — cabimento, prazo (15 dias), efeito suspensivo, juízo de retratação, questões de fato |
| [102] | Cap. III | 1.015 – 1.020 | **Agravo de Instrumento** — hipóteses taxativas (art. 1.015), prazo (15 dias), processamento, efeito suspensivo |
| [103] | Cap. IV | 1.021 | **Agravo Interno** — cabimento, prazo (15 dias), multa por interposição infundada |
| [104] | Cap. V | 1.022 – 1.026 | **Embargos de Declaração** — omissão, contradição, obscuridade, erro material, efeitos infringentes, prequestionamento |
| [105] | Cap. VI | 1.027 – 1.044 | **Recursos para o STF e STJ** — RE, REsp, admissibilidade, repercussão geral, recursos repetitivos, agravo em REsp/RE |

---

### LIVRO COMPLEMENTAR — Disposições Finais e Transitórias (Arts. 1.045–1.072)

| Chunk | Artigos | Conteúdo |
|-------|---------|----------|
| [106] | 1.045 – 1.072 | Vigência (1 ano), aplicação imediata, revogação do CPC/1973, disposições transitórias sobre atos praticados, recursos pendentes, execuções em curso, unificação de prazos |

---

## 3. ÍNDICE TEMÁTICO RÁPIDO

Use este índice para identificar o chunk correto pela temática da pergunta:

| Tema | Chunk(s) |
|------|----------|
| Princípios processuais, boa-fé, contraditório | 001 |
| Prazo em dobro (MP, Fazenda, Defensoria) | 021, 022, 023, 026 |
| Competência (absoluta, relativa, conexão) | 006 |
| Cooperação internacional / carta rogatória | 005, 029 |
| Tutela antecipada / tutela de urgência | 034, 035, 036 |
| Tutela cautelar | 035, 037 |
| Tutela da evidência | 038 |
| Estabilização da tutela antecipada | 036 |
| Litisconsórcio | 012 |
| Intervenção de terceiros | 013, 014, 015, 016, 017 |
| Desconsideração da personalidade jurídica | 016 |
| Impedimento e suspeição do juiz | 019 |
| Prazos processuais | 026 |
| Citação | 028 |
| Intimações | 030 |
| Nulidades processuais | 031 |
| Petição inicial | 043 |
| Improcedência liminar | 044 |
| Audiência de conciliação / mediação | 046 |
| Contestação / preliminares | 047 |
| Reconvenção | 048 |
| Revelia | 049 |
| Saneamento do processo | 050 |
| Julgamento antecipado do mérito | 051 |
| Provas (ônus, perícia, testemunho, documental) | 053 |
| Sentença / extinção do processo | 054 |
| Coisa julgada | 054 |
| Liquidação de sentença | 055 |
| Cumprimento de sentença — quantia (particular) | 058 |
| Cumprimento de sentença — alimentos | 059 |
| Cumprimento de sentença — Fazenda Pública | 060 |
| Cumprimento provisório | 057 |
| Ação possessória | 064 |
| Inventário e partilha | 067 |
| Embargos de terceiro | 068 |
| Ações de família | 071 |
| Ação monitória | 072 |
| Jurisdição voluntária | 076 |
| Títulos extrajudiciais / execução | 080 |
| Penhora / arresto / avaliação | 082, 085 |
| Embargos à execução | 088 |
| Prescrição intercorrente na execução | 089 |
| Uniformização de jurisprudência / precedentes | 091 |
| IRDR | 098 |
| Ação rescisória | 097 |
| Reclamação | 099 |
| Apelação | 101 |
| Agravo de instrumento (hipóteses) | 102 |
| Embargos de declaração | 104 |
| Recurso Especial (REsp) e Recurso Extraordinário (RE) | 105 |
| Recursos repetitivos / julgamento de casos repetitivos | 098, 105 |
| Disposições transitórias / direito intertemporal | 106 |

---

## 4. REGRAS DE ROTEAMENTO PARA O SISTEMA RAG

```
SE a pergunta menciona:
 - artigo específico (ex: "art. 489") → consultar chunk cujo range inclui esse artigo
 - "prova", "perícia", "depoimento", "confissão" → Chunk 053
 - "sentença", "coisa julgada", "art. 485", "art. 487" → Chunk 054
 - "tutela antecipada", "liminar", "urgência" → Chunks 034–037
 - "apelação", "recurso de apelação" → Chunk 101
 - "agravo de instrumento" → Chunk 102
 - "embargos de declaração" → Chunk 104
 - "REsp", "recurso especial", "STJ" → Chunk 105
 - "IRDR", "demandas repetitivas" → Chunk 098
 - "ação rescisória" → Chunk 097
 - "execução de alimentos" → Chunks 059, 087
 - "Fazenda Pública" (execução) → Chunks 060, 086
 - "embargos à execução" → Chunk 088
 - "competência" (geral) → Chunk 006
 - "competência" (execução) → Chunk 079
 - "nulidade" → Chunk 031
 - "prazo" → Chunk 026
 - "citação" → Chunk 028
 - "litisconsórcio" → Chunk 012
 - "prescrição intercorrente" → Chunk 089
 - "amicus curiae" → Chunk 017
 - "desconsideração da personalidade jurídica" → Chunk 016
 - "inventário", "partilha", "espólio" → Chunk 067
 - "monitória", "ação monitória" → Chunk 072
```

---

*Gerado automaticamente a partir de L13105.pdf (170 páginas) em 2026-06-30. Base: 106 chunks, Arts. 1–1.072.*

<!-- MAPA_ATUALIZADO_INICIO -->

## MAPA ATUALIZADO DE CHUNKS (fonte: index_artigos.json)

Total de chunks complementares: **128**

| Arquivo | Artigos | Capítulo/Título |
|---|---|---|
| Chunk_001_DAS_NORMAS_FUNDAMENTAIS_DO_PROCESSO_CIVIL.md | 1–12 | CAPÍTULO I — DAS NORMAS FUNDAMENTAIS DO PROCESSO CIVIL |
| Chunk_002_DA_APLICACAO_DAS_NORMAS_PROCESSUAIS.md | 13–15 | CAPÍTULO II — DA APLICAÇÃO DAS NORMAS PROCESSUAIS |
| Chunk_003_DA_JURISDICAO_E_DA_ACAO.md | 16–20 | TÍTULO I — DA JURISDIÇÃO E DA AÇÃO |
| Chunk_004_DOS_LIMITES_DA_JURISDICAO_NACIONAL.md | 21–25 | CAPÍTULO I — DOS LIMITES DA JURISDIÇÃO NACIONAL |
| Chunk_005_DA_COOPERACAO_INTERNACIONAL.md | 26–41 | CAPÍTULO II — DA COOPERAÇÃO INTERNACIONAL |
| Chunk_006_DA_COMPETENCIA.md | 42–66 | CAPÍTULO I — DA COMPETÊNCIA |
| Chunk_007_DA_COOPERACAO_NACIONAL.md | 67–69 | CAPÍTULO II — DA COOPERAÇÃO NACIONAL |
| Chunk_008_DA_CAPACIDADE_PROCESSUAL.md | 70–76 | CAPÍTULO I — DA CAPACIDADE PROCESSUAL |
| Chunk_009_DOS_DEVERES_DAS_PARTES_E_DE_SEUS_PROCURADORES_P01.md | 77–84 | CAPÍTULO II — DOS DEVERES DAS PARTES E DE SEUS PROCURADORES |
| Chunk_009_DOS_DEVERES_DAS_PARTES_E_DE_SEUS_PROCURADORES_P02.md | 85–93 | CAPÍTULO II — DOS DEVERES DAS PARTES E DE SEUS PROCURADORES |
| Chunk_009_DOS_DEVERES_DAS_PARTES_E_DE_SEUS_PROCURADORES_P03.md | 94–102 | CAPÍTULO II — DOS DEVERES DAS PARTES E DE SEUS PROCURADORES |
| Chunk_010_DOS_PROCURADORES.md | 103–107 | CAPÍTULO III — DOS PROCURADORES |
| Chunk_011_DA_SUCESSAO_DAS_PARTES_E_DOS_PROCURADORES.md | 108–112 | CAPÍTULO IV — DA SUCESSÃO DAS PARTES E DOS PROCURADORES |
| Chunk_012_DO_LITISCONSORCIO.md | 113–118 | TÍTULO II — DO LITISCONSÓRCIO |
| Chunk_013_DA_ASSISTENCIA.md | 119–124 | CAPÍTULO I — DA ASSISTÊNCIA |
| Chunk_014_DA_DENUNCIACAO_DA_LIDE.md | 125–129 | CAPÍTULO II — DA DENUNCIAÇÃO DA LIDE |
| Chunk_015_DO_CHAMAMENTO_AO_PROCESSO.md | 130–132 | CAPÍTULO III — DO CHAMAMENTO AO PROCESSO |
| Chunk_016_DO_INCIDENTE_DE_DESCONSIDERACAO_DA_PERSONALIDADE_J.md | 133–137 | CAPÍTULO IV — DO INCIDENTE DE DESCONSIDERAÇÃO DA PERSONALIDADE JURÍDICA |
| Chunk_017_DO_AMICUS_CURIAE.md | 138–138 | CAPÍTULO V — DO AMICUS CURIAE |
| Chunk_018_DOS_PODERES_DOS_DEVERES_E_DA_RESPONSABILIDADE_DO_J.md | 139–143 | CAPÍTULO I — DOS PODERES, DOS DEVERES E DA RESPONSABILIDADE DO JUIZ |
| Chunk_019_DOS_IMPEDIMENTOS_E_DA_SUSPEICAO.md | 144–148 | CAPÍTULO II — DOS IMPEDIMENTOS E DA SUSPEIÇÃO |
| Chunk_020_DOS_AUXILIARES_DA_JUSTICA_P01.md | 149–164 | CAPÍTULO III — DOS AUXILIARES DA JUSTIÇA |
| Chunk_020_DOS_AUXILIARES_DA_JUSTICA_P02.md | 165–175 | CAPÍTULO III — DOS AUXILIARES DA JUSTIÇA |
| Chunk_021_DO_MINISTERIO_PUBLICO.md | 176–181 | TÍTULO V — DO MINISTÉRIO PÚBLICO |
| Chunk_022_DA_ADVOCACIA_PUBLICA.md | 182–184 | TÍTULO VI — DA ADVOCACIA PÚBLICA |
| Chunk_023_DA_DEFENSORIA_PUBLICA.md | 185–187 | TÍTULO VII — DA DEFENSORIA PÚBLICA |
| Chunk_024_DA_FORMA_DOS_ATOS_PROCESSUAIS.md | 188–211 | CAPÍTULO I — DA FORMA DOS ATOS PROCESSUAIS |
| Chunk_025_DO_TEMPO_E_DO_LUGAR_DOS_ATOS_PROCESSUAIS.md | 212–217 | CAPÍTULO II — DO TEMPO E DO LUGAR DOS ATOS PROCESSUAIS |
| Chunk_026_DOS_PRAZOS.md | 218–235 | CAPÍTULO III — DOS PRAZOS |
| Chunk_027_DISPOSICOES_GERAIS.md | 236–237 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_028_DA_CITACAO.md | 238–259 | CAPÍTULO II — DA CITAÇÃO |
| Chunk_029_DAS_CARTAS.md | 260–268 | CAPÍTULO III — DAS CARTAS |
| Chunk_030_DAS_INTIMACOES.md | 269–275 | CAPÍTULO IV — DAS INTIMAÇÕES |
| Chunk_031_DAS_NULIDADES.md | 276–283 | TÍTULO III — DAS NULIDADES |
| Chunk_032_DA_DISTRIBUICAO_E_DO_REGISTRO.md | 284–290 | TÍTULO IV — DA DISTRIBUIÇÃO E DO REGISTRO |
| Chunk_033_DO_VALOR_DA_CAUSA.md | 291–293 | TÍTULO V — DO VALOR DA CAUSA |
| Chunk_034_DISPOSICOES_GERAIS.md | 294–299 | TÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_035_DISPOSICOES_GERAIS.md | 300–302 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_036_DO_PROCEDIMENTO_DA_TUTELA_ANTECIPADA_REQUERIDA_EM_.md | 303–304 | CAPÍTULO II — DO PROCEDIMENTO DA TUTELA ANTECIPADA REQUERIDA EM CARÁTER ANTECEDENTE |
| Chunk_037_DO_PROCEDIMENTO_DA_TUTELA_CAUTELAR_REQUERIDA_EM_CA.md | 305–310 | CAPÍTULO III — DO PROCEDIMENTO DA TUTELA CAUTELAR REQUERIDA EM CARÁTER ANTECEDENTE |
| Chunk_038_DA_TUTELA_DA_EVIDENCIA.md | 311–311 | TÍTULO III — DA TUTELA DA EVIDÊNCIA |
| Chunk_039_DA_FORMACAO_DO_PROCESSO.md | 312–312 | TÍTULO I — DA FORMAÇÃO DO PROCESSO |
| Chunk_040_DA_SUSPENSAO_DO_PROCESSO.md | 313–315 | TÍTULO II — DA SUSPENSÃO DO PROCESSO |
| Chunk_041_DA_EXTINCAO_DO_PROCESSO.md | 316–317 | TÍTULO III — DA EXTINÇÃO DO PROCESSO |
| Chunk_042_DISPOSICOES_GERAIS.md | 318–318 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_043_DA_PETICAO_INICIAL.md | 319–331 | CAPÍTULO II — DA PETIÇÃO INICIAL |
| Chunk_044_DA_IMPROCEDENCIA_LIMINAR_DO_PEDIDO.md | 332–332 | CAPÍTULO III — DA IMPROCEDÊNCIA LIMINAR DO PEDIDO |
| Chunk_045_DA_CONVERSAO_DA_ACAO_INDIVIDUAL_EM_ACAO_COLETIVA.md | 333–333 | CAPÍTULO IV — DA CONVERSÃO DA AÇÃO INDIVIDUAL EM AÇÃO COLETIVA |
| Chunk_046_DA_AUDIENCIA_DE_CONCILIACAO_OU_DE_MEDIACAO.md | 334–334 | CAPÍTULO V — DA AUDIÊNCIA DE CONCILIAÇÃO OU DE MEDIAÇÃO |
| Chunk_047_DA_CONTESTACAO.md | 335–342 | CAPÍTULO VI — DA CONTESTAÇÃO |
| Chunk_048_DA_RECONVENCAO.md | 343–343 | CAPÍTULO VII — DA RECONVENÇÃO |
| Chunk_049_DA_REVELIA.md | 344–346 | CAPÍTULO VIII — DA REVELIA |
| Chunk_050_DAS_PROVIDENCIAS_PRELIMINARES_E_DO_SANEAMENTO.md | 347–353 | CAPÍTULO IX — DAS PROVIDÊNCIAS PRELIMINARES E DO SANEAMENTO |
| Chunk_051_DO_JULGAMENTO_CONFORME_O_ESTADO_DO_PROCESSO.md | 354–357 | CAPÍTULO X — DO JULGAMENTO CONFORME O ESTADO DO PROCESSO |
| Chunk_052_DA_AUDIENCIA_DE_INSTRUCAO_E_JULGAMENTO.md | 358–368 | CAPÍTULO XI — DA AUDIÊNCIA DE INSTRUÇÃO E JULGAMENTO |
| Chunk_053_DAS_PROVAS_P01.md | 369–390 | CAPÍTULO XII — DAS PROVAS |
| Chunk_053_DAS_PROVAS_P02.md | 391–415 | CAPÍTULO XII — DAS PROVAS |
| Chunk_053_DAS_PROVAS_P03.md | 416–438 | CAPÍTULO XII — DAS PROVAS |
| Chunk_053_DAS_PROVAS_P04.md | 439–456 | CAPÍTULO XII — DAS PROVAS |
| Chunk_053_DAS_PROVAS_P05.md | 457–472 | CAPÍTULO XII — DAS PROVAS |
| Chunk_053_DAS_PROVAS_P06.md | 473–484 | CAPÍTULO XII — DAS PROVAS |
| Chunk_054_DA_SENTENCA_E_DA_COISA_JULGADA.md | 485–508 | CAPÍTULO XIII — DA SENTENÇA E DA COISA JULGADA |
| Chunk_055_DA_LIQUIDACAO_DE_SENTENCA.md | 509–512 | CAPÍTULO XIV — DA LIQUIDAÇÃO DE SENTENÇA |
| Chunk_056_DISPOSICOES_GERAIS.md | 513–519 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_057_DO_CUMPRIMENTO_PROVISORIO_DA_SENTENCA_QUE_RECONHEC.md | 520–522 | CAPÍTULO II — DO CUMPRIMENTO PROVISÓRIO DA SENTENÇA QUE RECONHECE A EXIGIBILIDADE DE OBRIG |
| Chunk_058_DO_CUMPRIMENTO_DEFINITIVO_DA_SENTENCA_QUE_RECONHEC.md | 523–527 | CAPÍTULO III — DO CUMPRIMENTO DEFINITIVO DA SENTENÇA QUE RECONHECE A EXIGIBILIDADE DE OBRI |
| Chunk_059_DO_CUMPRIMENTO_DE_SENTENCA_QUE_RECONHECA_A_EXIGIBI.md | 528–533 | CAPÍTULO IV — DO CUMPRIMENTO DE SENTENÇA QUE RECONHEÇA A EXIGIBILIDADE DE OBRIGAÇÃO DE PRE |
| Chunk_060_DO_CUMPRIMENTO_DE_SENTENCA_QUE_RECONHECA_A_EXIGIBI.md | 534–535 | CAPÍTULO V — DO CUMPRIMENTO DE SENTENÇA QUE RECONHEÇA A EXIGIBILIDADE DE OBRIGAÇÃO DE PAGA |
| Chunk_061_DO_CUMPRIMENTO_DE_SENTENCA_QUE_RECONHECA_A_EXIGIBI.md | 536–538 | CAPÍTULO VI — DO CUMPRIMENTO DE SENTENÇA QUE RECONHEÇA A EXIGIBILIDADE DE OBRIGAÇÃO DE FAZ |
| Chunk_062_DA_ACAO_DE_CONSIGNACAO_EM_PAGAMENTO.md | 539–549 | CAPÍTULO I — DA AÇÃO DE CONSIGNAÇÃO EM PAGAMENTO |
| Chunk_063_DA_ACAO_DE_EXIGIR_CONTAS.md | 550–553 | CAPÍTULO II — DA AÇÃO DE EXIGIR CONTAS |
| Chunk_064_DAS_ACOES_POSSESSORIAS.md | 554–568 | CAPÍTULO III — DAS AÇÕES POSSESSÓRIAS |
| Chunk_065_DA_ACAO_DE_DIVISAO_E_DA_DEMARCACAO_DE_TERRAS_PARTI.md | 569–598 | CAPÍTULO IV — DA AÇÃO DE DIVISÃO E DA DEMARCAÇÃO DE TERRAS PARTICULARES |
| Chunk_066_DA_ACAO_DE_DISSOLUCAO_PARCIAL_DE_SOCIEDADE.md | 599–609 | CAPÍTULO V — DA AÇÃO DE DISSOLUÇÃO PARCIAL DE SOCIEDADE |
| Chunk_067_DO_INVENTARIO_E_DA_PARTILHA_P01.md | 610–625 | CAPÍTULO VI — DO INVENTÁRIO E DA PARTILHA |
| Chunk_067_DO_INVENTARIO_E_DA_PARTILHA_P02.md | 626–646 | CAPÍTULO VI — DO INVENTÁRIO E DA PARTILHA |
| Chunk_067_DO_INVENTARIO_E_DA_PARTILHA_P03.md | 647–673 | CAPÍTULO VI — DO INVENTÁRIO E DA PARTILHA |
| Chunk_068_DOS_EMBARGOS_DE_TERCEIRO.md | 674–681 | CAPÍTULO VII — DOS EMBARGOS DE TERCEIRO |
| Chunk_069_DA_OPOSICAO.md | 682–686 | CAPÍTULO VIII — DA OPOSIÇÃO |
| Chunk_070_DA_HABILITACAO.md | 687–692 | CAPÍTULO IX — DA HABILITAÇÃO |
| Chunk_071_DAS_ACOES_DE_FAMILIA.md | 693–699 | CAPÍTULO X — DAS AÇÕES DE FAMÍLIA |
| Chunk_072_DA_ACAO_MONITORIA.md | 700–702 | CAPÍTULO XI — DA AÇÃO MONITÓRIA |
| Chunk_073_DA_HOMOLOGACAO_DO_PENHOR_LEGAL.md | 703–706 | CAPÍTULO XII — DA HOMOLOGAÇÃO DO PENHOR LEGAL |
| Chunk_074_DA_REGULACAO_DE_AVARIA_GROSSA.md | 707–711 | CAPÍTULO XIII — DA REGULAÇÃO DE AVARIA GROSSA |
| Chunk_075_DA_RESTAURACAO_DE_AUTOS.md | 712–718 | CAPÍTULO XIV — DA RESTAURAÇÃO DE AUTOS |
| Chunk_076_DOS_PROCEDIMENTOS_DE_JURISDICAO_VOLUNTARIA_P01.md | 719–739 | CAPÍTULO XV — DOS PROCEDIMENTOS DE JURISDIÇÃO VOLUNTÁRIA |
| Chunk_076_DOS_PROCEDIMENTOS_DE_JURISDICAO_VOLUNTARIA_P02.md | 740–754 | CAPÍTULO XV — DOS PROCEDIMENTOS DE JURISDIÇÃO VOLUNTÁRIA |
| Chunk_076_DOS_PROCEDIMENTOS_DE_JURISDICAO_VOLUNTARIA_P03.md | 755–770 | CAPÍTULO XV — DOS PROCEDIMENTOS DE JURISDIÇÃO VOLUNTÁRIA |
| Chunk_077_DISPOSICOES_GERAIS.md | 771–777 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_078_DAS_PARTES.md | 778–780 | CAPÍTULO II — DAS PARTES |
| Chunk_079_DA_COMPETENCIA.md | 781–782 | CAPÍTULO III — DA COMPETÊNCIA |
| Chunk_080_DOS_REQUISITOS_NECESSARIOS_PARA_REALIZAR_QUALQUER_.md | 783–788 | CAPÍTULO IV — DOS REQUISITOS NECESSÁRIOS PARA REALIZAR QUALQUER EXECUÇÃO |
| Chunk_081_DA_RESPONSABILIDADE_PATRIMONIAL.md | 789–796 | CAPÍTULO V — DA RESPONSABILIDADE PATRIMONIAL |
| Chunk_082_DISPOSICOES_GERAIS.md | 797–805 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_083_DA_EXECUCAO_PARA_A_ENTREGA_DE_COISA.md | 806–813 | CAPÍTULO II — DA EXECUÇÃO PARA A ENTREGA DE COISA |
| Chunk_084_DA_EXECUCAO_DAS_OBRIGACOES_DE_FAZER_OU_DE_NAO_FAZE.md | 814–823 | CAPÍTULO III — DA EXECUÇÃO DAS OBRIGAÇÕES DE FAZER OU DE NÃO FAZER |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P01.md | 824–838 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P02.md | 839–853 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P03.md | 854–863 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P04.md | 864–876 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P05.md | 877–889 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P06.md | 890–902 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_085_DA_EXECUCAO_POR_QUANTIA_CERTA_P07.md | 903–909 | CAPÍTULO IV — DA EXECUÇÃO POR QUANTIA CERTA |
| Chunk_086_DA_EXECUCAO_CONTRA_A_FAZENDA_PUBLICA.md | 910–910 | CAPÍTULO V — DA EXECUÇÃO CONTRA A FAZENDA PÚBLICA |
| Chunk_087_DA_EXECUCAO_DE_ALIMENTOS.md | 911–913 | CAPÍTULO VI — DA EXECUÇÃO DE ALIMENTOS |
| Chunk_088_DOS_EMBARGOS_A_EXECUCAO.md | 914–920 | TÍTULO III — DOS EMBARGOS À EXECUÇÃO |
| Chunk_089_DA_SUSPENSAO_DO_PROCESSO_DE_EXECUCAO.md | 921–923 | CAPÍTULO I — DA SUSPENSÃO DO PROCESSO DE EXECUÇÃO |
| Chunk_090_DA_EXTINCAO_DO_PROCESSO_DE_EXECUCAO.md | 924–925 | CAPÍTULO II — DA EXTINÇÃO DO PROCESSO DE EXECUÇÃO |
| Chunk_091_DISPOSICOES_GERAIS.md | 926–928 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_092_DA_ORDEM_DOS_PROCESSOS_NO_TRIBUNAL.md | 929–946 | CAPÍTULO II — DA ORDEM DOS PROCESSOS NO TRIBUNAL |
| Chunk_093_DO_INCIDENTE_DE_ASSUNCAO_DE_COMPETENCIA.md | 947–947 | CAPÍTULO III — DO INCIDENTE DE ASSUNÇÃO DE COMPETÊNCIA |
| Chunk_094_DO_INCIDENTE_DE_ARGUICAO_DE_INCONSTITUCIONALIDADE.md | 948–950 | CAPÍTULO IV — DO INCIDENTE DE ARGUIÇÃO DE INCONSTITUCIONALIDADE |
| Chunk_095_DO_CONFLITO_DE_COMPETENCIA.md | 951–959 | CAPÍTULO V — DO CONFLITO DE COMPETÊNCIA |
| Chunk_096_DA_HOMOLOGACAO_DE_DECISAO_ESTRANGEIRA_E_DA_CONCESS.md | 960–965 | CAPÍTULO VI — DA HOMOLOGAÇÃO DE DECISÃO ESTRANGEIRA E DA CONCESSÃO DO EXEQUATUR À CARTA RO |
| Chunk_097_DA_ACAO_RESCISORIA.md | 966–975 | CAPÍTULO VII — DA AÇÃO RESCISÓRIA |
| Chunk_098_DO_INCIDENTE_DE_RESOLUCAO_DE_DEMANDAS_REPETITIVAS.md | 976–987 | CAPÍTULO VIII — DO INCIDENTE DE RESOLUÇÃO DE DEMANDAS REPETITIVAS |
| Chunk_099_DA_RECLAMACAO.md | 988–993 | CAPÍTULO IX — DA RECLAMAÇÃO |
| Chunk_100_DISPOSICOES_GERAIS.md | 994–1008 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_101_DA_APELACAO.md | 1009–1014 | CAPÍTULO II — DA APELAÇÃO |
| Chunk_102_DO_AGRAVO_DE_INSTRUMENTO.md | 1015–1020 | CAPÍTULO III — DO AGRAVO DE INSTRUMENTO |
| Chunk_103_DO_AGRAVO_INTERNO.md | 1021–1021 | CAPÍTULO IV — DO AGRAVO INTERNO |
| Chunk_104_DOS_EMBARGOS_DE_DECLARACAO.md | 1022–1026 | CAPÍTULO V — DOS EMBARGOS DE DECLARAÇÃO |
| Chunk_105_DOS_RECURSOS_PARA_O_SUPREMO_TRIBUNAL_FEDERAL_E_PAR_P01.md | 1027–1031 | CAPÍTULO VI — DOS RECURSOS PARA O SUPREMO TRIBUNAL FEDERAL E PARA O SUPERIOR TRIBUNAL DE J |
| Chunk_105_DOS_RECURSOS_PARA_O_SUPREMO_TRIBUNAL_FEDERAL_E_PAR_P02.md | 1032–1036 | CAPÍTULO VI — DOS RECURSOS PARA O SUPREMO TRIBUNAL FEDERAL E PARA O SUPERIOR TRIBUNAL DE J |
| Chunk_105_DOS_RECURSOS_PARA_O_SUPREMO_TRIBUNAL_FEDERAL_E_PAR_P03.md | 1037–1042 | CAPÍTULO VI — DOS RECURSOS PARA O SUPREMO TRIBUNAL FEDERAL E PARA O SUPERIOR TRIBUNAL DE J |
| Chunk_105_DOS_RECURSOS_PARA_O_SUPREMO_TRIBUNAL_FEDERAL_E_PAR_P04.md | 1042–1044 | CAPÍTULO VI — DOS RECURSOS PARA O SUPREMO TRIBUNAL FEDERAL E PARA O SUPERIOR TRIBUNAL DE J |
| Chunk_106_DISPOSICOES_FINAIS_E_TRANSITORIAS_P01.md | 1045–1066 | LIVRO COMPLEMENTAR — DISPOSIÇÕES FINAIS E TRANSITÓRIAS |
| Chunk_106_DISPOSICOES_FINAIS_E_TRANSITORIAS_P02.md | 1067–1072 | LIVRO COMPLEMENTAR — DISPOSIÇÕES FINAIS E TRANSITÓRIAS |

<!-- MAPA_ATUALIZADO_FIM -->
