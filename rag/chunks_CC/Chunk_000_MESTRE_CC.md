---
chunk_id: "000"
tipo: chunk_mestre
lei: "Lei nº 10.406/2002 — Código Civil"
descricao: "Mapa sistemático completo do Código Civil para roteamento e contexto em RAG jurídico"
total_chunks: 192
artigos_cobertos: "1 – 2.046"
indice: A
---


> ⚠ **NOTA (atualização 2026-07):** chunks grandes foram divididos em partes (sufixo `_Pnn`). Tabelas antigas deste arquivo podem citar nomes que não existem mais. Para roteamento, use o **MAPA ATUALIZADO DE CHUNKS** ao final deste arquivo ou o `index_artigos.json`.
# CHUNK MESTRE — Código Civil (Lei nº 10.406/2002)

> **Propósito deste arquivo:** Fornecer contexto sistemático global para o sistema RAG. Use este chunk para identificar *em qual chunk buscar* a resposta a uma pergunta sobre o Código Civil, e para compreender a estrutura lógica da lei antes de recuperar artigos específicos. Este é o **Index A** da arquitetura dual-index; os chunks complementares (Chunk_001 a Chunk_192) formam o **Index B**.

---

## 1. VISÃO GERAL DA LEI

| Item | Dado |
|------|------|
| Lei | Lei nº 10.406, de 10 de janeiro de 2002 |
| Nome | Código Civil |
| Vigência | 11 de janeiro de 2003 (1 ano após publicação) |
| Total de artigos | 2.046 (numeração oficial; alguns artigos possuem desdobramentos com sufixo de letra, ex.: 1.358-B a 1.358-U, 1.783-A) |
| Total de chunks nesta base | 192 (Chunk_000 = mestre; Chunk_001 a Chunk_192 = complementares) |
| Estrutura | Parte Geral (Livros I–III) + Parte Especial (Livros I–V) + Livro Complementar |
| Hierarquia interna | Parte › Livro › Título › (Subtítulo, quando existente) › Capítulo › (Seção/Subseção, mantidas dentro do chunk do capítulo) |

**Observação sobre "Subtítulo":** alguns Títulos do Código Civil (Direito de Empresa — Da Sociedade; Direito de Família — Do Casamento, Das Relações de Parentesco, Do Direito Patrimonial) se subdividem em **Subtítulos** antes de chegar aos Capítulos. Quando um Subtítulo não possui Capítulos próprios (ex.: Do Usufruto e da Administração dos Bens de Filhos Menores; Dos Alimentos; Do Bem de Família), ele próprio constitui um chunk (campo `capitulo: null` no frontmatter, `subtitulo` preenchido).

---

## 2. MAPA HIERÁRQUICO COMPLETO

### PARTE GERAL


#### LIVRO I — DAS PESSOAS (Arts. 1–78)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [001] | T.I — DAS PESSOAS NATURAIS | Cap. I — DA PERSONALIDADE E DA CAPACIDADE | 1–10 |
| [002] | T.I — DAS PESSOAS NATURAIS | Cap. II — DOS DIREITOS DA PERSONALIDADE | 11–21 |
| [003] | T.I — DAS PESSOAS NATURAIS | Cap. III — DA AUSÊNCIA | 22–39 |
| [004] | T.II — DAS PESSOAS JURÍDICAS | Cap. I — DISPOSIÇÕES GERAIS | 40–52 |
| [005] | T.II — DAS PESSOAS JURÍDICAS | Cap. II — DAS ASSOCIAÇÕES | 53–61 |
| [006] | T.II — DAS PESSOAS JURÍDICAS | Cap. III — DAS FUNDAÇÕES | 62–69 |
| [007] | T.III — DO DOMICÍLIO | *(título integral)* | 70–78 |

#### LIVRO II — DOS BENS (Arts. 79–103)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [008] | T.UNICO — DAS DIFERENTES CLASSES DE BENS | Cap. I — DOS BENS CONSIDERADOS EM SI MESMOS | 79–91 |
| [009] | T.UNICO — DAS DIFERENTES CLASSES DE BENS | Cap. II — DOS BENS RECIPROCAMENTE CONSIDERADOS | 92–97 |
| [010] | T.UNICO — DAS DIFERENTES CLASSES DE BENS | Cap. III — DOS BENS PÚBLICOS | 98–103 |

#### LIVRO III — DOS FATOS JURÍDICOS (Arts. 104–232)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [011] | T.I — DO NEGÓCIO JURÍDICO | Cap. I — DISPOSIÇÕES GERAIS | 104–114 |
| [012] | T.I — DO NEGÓCIO JURÍDICO | Cap. II — DA REPRESENTAÇÃO | 115–120 |
| [013] | T.I — DO NEGÓCIO JURÍDICO | Cap. III — DA CONDIÇÃO, DO TERMO E DO ENCARGO | 121–137 |
| [014] | T.I — DO NEGÓCIO JURÍDICO | Cap. IV — DOS DEFEITOS DO NEGÓCIO JURÍDICO | 138–165 |
| [015] | T.I — DO NEGÓCIO JURÍDICO | Cap. V — DA INVALIDADE DO NEGÓCIO JURÍDICO | 166–184 |
| [016] | T.II — DOS ATOS JURÍDICOS LÍCITOS | *(título integral)* | 185 |
| [017] | T.III — DOS ATOS ILÍCITOS | *(título integral)* | 186–188 |
| [018] | T.IV — DA PRESCRIÇÃO E DA DECADÊNCIA | Cap. I — DA PRESCRIÇÃO | 189–206-A |
| [019] | T.IV — DA PRESCRIÇÃO E DA DECADÊNCIA | Cap. II — DA DECADÊNCIA | 207–211 |
| [020] | T.V — DA PROVA | *(título integral)* | 212–232 |

### PARTE ESPECIAL


#### LIVRO I — DO DIREITO DAS OBRIGAÇÕES (Arts. 233–965)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [021] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. I — DAS OBRIGAÇÕES DE DAR | 233–246 |
| [022] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. II — DAS OBRIGAÇÕES DE FAZER | 247–249 |
| [023] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. III — DAS OBRIGAÇÕES DE NÃO FAZER | 250–251 |
| [024] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. IV — DAS OBRIGAÇÕES ALTERNATIVAS | 252–256 |
| [025] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. V — DAS OBRIGAÇÕES DIVISÍVEIS E INDIVISÍVEIS | 257–263 |
| [026] | T.I — DAS MODALIDADES DAS OBRIGAÇÕES | Cap. VI — DAS OBRIGAÇÕES SOLIDÁRIAS | 264–285 |
| [027] | T.II — DA TRANSMISSÃO DAS OBRIGAÇÕES | Cap. I — DA CESSÃO DE CRÉDITO | 286–298 |
| [028] | T.II — DA TRANSMISSÃO DAS OBRIGAÇÕES | Cap. II — DA ASSUNÇÃO DE DÍVIDA | 299–303 |
| [029] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. I — DO PAGAMENTO | 304–333 |
| [030] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. II — DO PAGAMENTO EM CONSIGNAÇÃO | 334–345 |
| [031] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. III — DO PAGAMENTO COM SUB-ROGAÇÃO | 346–351 |
| [032] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. IV — DA IMPUTAÇÃO DO PAGAMENTO | 352–355 |
| [033] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. V — DA DAÇÃO EM PAGAMENTO | 356–359 |
| [034] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. VI — DA NOVAÇÃO | 360–367 |
| [035] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. VII — DA COMPENSAÇÃO | 368–380 |
| [036] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. VIII — DA CONFUSÃO | 381–384 |
| [037] | T.III — DO ADIMPLEMENTO E EXTINÇÃO DAS OBRIGAÇÕES | Cap. IX — DA REMISSÃO DAS DÍVIDAS | 385–388 |
| [038] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. I — DISPOSIÇÕES GERAIS | 389–393 |
| [039] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. II — DA MORA | 394–401 |
| [040] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. III — DAS PERDAS E DANOS | 402–405 |
| [041] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. IV — DOS JUROS LEGAIS | 406–407 |
| [042] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. V — DA CLÁUSULA PENAL | 408–416 |
| [043] | T.IV — DO INADIMPLEMENTO DAS OBRIGAÇÕES | Cap. VI — DAS ARRAS OU SINAL | 417–420 |
| [044] | T.V — DOS CONTRATOS EM GERAL | Cap. I — DISPOSIÇÕES GERAIS | 421–471 |
| [045] | T.V — DOS CONTRATOS EM GERAL | Cap. II — DA EXTINÇÃO DO CONTRATO | 472–480 |
| [046] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. I — DA COMPRA E VENDA | 481–532 |
| [047] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. II — DA TROCA OU PERMUTA | 533 |
| [048] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. III — DO CONTRATO ESTIMATÓRIO | 534–537 |
| [049] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. IV — DA DOAÇÃO | 538–564 |
| [050] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. V — DA LOCAÇÃO DE COISAS | 565–578 |
| [051] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. VI — DO EMPRÉSTIMO | 579–592 |
| [052] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. VII — DA PRESTAÇÃO DE SERVIÇO | 593–609 |
| [053] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. VIII — DA EMPREITADA | 610–626 |
| [054] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. IX — DO DEPÓSITO | 627–652 |
| [055] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. X — DO MANDATO | 653–692 |
| [056] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XI — DA COMISSÃO | 693–709 |
| [057] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XII — DA AGÊNCIA E DISTRIBUIÇÃO | 710–721 |
| [058] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XIII — DA CORRETAGEM | 722–729 |
| [059] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XIV — DO TRANSPORTE | 730–756 |
| [060] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XV — DO SEGURO | 757–802 |
| [061] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XVI — DA CONSTITUIÇÃO DE RENDA | 803–813 |
| [062] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XVII — DO JOGO E DA APOSTA | 814–817 |
| [063] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XVIII — DA FIANÇA | 818–839 |
| [064] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XIX — DA TRANSAÇÃO | 840–850 |
| [065] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XX — DO COMPROMISSO | 851–853 |
| [066] | T.VI — DAS VÁRIAS ESPÉCIES DE CONTRATO | Cap. XXI — DO CONTRATO DE ADMINISTRAÇÃO FIDUCIÁRIA DE GARANTIAS | 853-A |
| [067] | T.VII — DOS ATOS UNILATERAIS | Cap. I — DA PROMESSA DE RECOMPENSA | 854–860 |
| [068] | T.VII — DOS ATOS UNILATERAIS | Cap. II — DA GESTÃO DE NEGÓCIOS | 861–875 |
| [069] | T.VII — DOS ATOS UNILATERAIS | Cap. III — DO PAGAMENTO INDEVIDO | 876–883 |
| [070] | T.VII — DOS ATOS UNILATERAIS | Cap. IV — DO ENRIQUECIMENTO SEM CAUSA | 884–886 |
| [071] | T.VIII — DOS TÍTULOS DE CRÉDITO | Cap. I — DISPOSIÇÕES GERAIS | 887–903 |
| [072] | T.VIII — DOS TÍTULOS DE CRÉDITO | Cap. II — DO TÍTULO AO PORTADOR | 904–909 |
| [073] | T.VIII — DOS TÍTULOS DE CRÉDITO | Cap. III — DO TÍTULO À ORDEM | 910–920 |
| [074] | T.VIII — DOS TÍTULOS DE CRÉDITO | Cap. IV — DO TÍTULO NOMINATIVO | 921–926 |
| [075] | T.IX — DA RESPONSABILIDADE CIVIL | Cap. I — DA OBRIGAÇÃO DE INDENIZAR | 927–943 |
| [076] | T.IX — DA RESPONSABILIDADE CIVIL | Cap. II — DA INDENIZAÇÃO | 944–954 |
| [077] | T.X — DAS PREFERÊNCIAS E PRIVILÉGIOS CREDITÓRIOS | *(título integral)* | 955–965 |

#### LIVRO II — DO DIREITO DE EMPRESA (Arts. 966–1.195)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [078] | T.I — DO EMPRESÁRIO | Cap. I — DA CARACTERIZAÇÃO E DA INSCRIÇÃO | 966–971 |
| [079] | T.I — DO EMPRESÁRIO | Cap. II — DA CAPACIDADE | 972–980 |
| [080] | T.I-A — DA EMPRESA INDIVIDUAL DE RESPONSABILIDADE LIMITADA | *(título integral)* | 980-A |
| [081] | T.II — DA SOCIEDADE | Cap. UNICO — DISPOSIÇÕES GERAIS | 981–985 |
| [082] | T.II — DA SOCIEDADE / Sub.I — DA SOCIEDADE NÃO PERSONIFICADA | Cap. I — DA SOCIEDADE EM COMUM | 986–990 |
| [083] | T.II — DA SOCIEDADE / Sub.I — DA SOCIEDADE NÃO PERSONIFICADA | Cap. II — DA SOCIEDADE EM CONTA DE PARTICIPAÇÃO | 991–996 |
| [084] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. I — DA SOCIEDADE SIMPLES | 997–1.038 |
| [085] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. II — Da Sociedade em Nome Coletivo | 1.039–1.044 |
| [086] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. III — Da Sociedade em Comandita Simples | 1.045–1.051 |
| [087] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. IV — Da Sociedade Limitada | 1.052–1.087 |
| [088] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. V — DA SOCIEDADE ANÔNIMA | 1.088–1.089 |
| [089] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. VI — DA SOCIEDADE EM COMANDITA POR AÇÕES | 1.090–1.092 |
| [090] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. VII — DA SOCIEDADE COOPERATIVA | 1.093–1.096 |
| [091] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. VIII — DAS SOCIEDADES COLIGADAS | 1.097–1.101 |
| [092] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. IX — DA LIQUIDAÇÃO DA SOCIEDADE | 1.102–1.112 |
| [093] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. X — DA TRANSFORMAÇÃO, DA INCORPORAÇÃO, DA FUSÃO E DA CISÃO DAS SOCIEDADES | 1.113–1.122 |
| [094] | T.II — DA SOCIEDADE / Sub.II — DA SOCIEDADE PERSONIFICADA | Cap. XI — DA SOCIEDADE DEPENDENTE DE AUTORIZAÇÃO | 1.123–1.141 |
| [095] | T.III — DO ESTABELECIMENTO | Cap. UNICO — DISPOSIÇÕES GERAIS | 1.142–1.149 |
| [096] | T.IV — DOS INSTITUTOS COMPLEMENTARES | Cap. I — DO REGISTRO | 1.150–1.154 |
| [097] | T.IV — DOS INSTITUTOS COMPLEMENTARES | Cap. II — DO NOME EMPRESARIAL | 1.155–1.168 |
| [098] | T.IV — DOS INSTITUTOS COMPLEMENTARES | Cap. III — DOS PREPOSTOS | 1.169–1.178 |
| [099] | T.IV — DOS INSTITUTOS COMPLEMENTARES | Cap. IV — DA ESCRITURAÇÃO | 1.179–1.195 |

#### LIVRO III — DO DIREITO DAS COISAS (Arts. 1.196–1.510-E)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [100] | T.I — DA POSSE | Cap. I — DA POSSE E SUA CLASSIFICAÇÃO | 1.196–1.203 |
| [101] | T.I — DA POSSE | Cap. II — DA AQUISIÇÃO DA POSSE | 1.204–1.209 |
| [102] | T.I — DA POSSE | Cap. III — DOS EFEITOS DA POSSE | 1.210–1.222 |
| [103] | T.I — DA POSSE | Cap. IV — DA PERDA DA POSSE | 1.223–1.224 |
| [104] | T.II — DOS DIREITOS REAIS | Cap. UNICO — DISPOSIÇÕES GERAIS | 1.225–1.227 |
| [105] | T.III — DA PROPRIEDADE | Cap. I — DA PROPRIEDADE EM GERAL | 1.228–1.237 |
| [106] | T.III — DA PROPRIEDADE | Cap. II — DA AQUISIÇÃO DA PROPRIEDADE IMÓVEL | 1.238–1.259 |
| [107] | T.III — DA PROPRIEDADE | Cap. III — DA AQUISIÇÃO DA PROPRIEDADE MÓVEL | 1.260–1.274 |
| [108] | T.III — DA PROPRIEDADE | Cap. IV — DA PERDA DA PROPRIEDADE | 1.275–1.276 |
| [109] | T.III — DA PROPRIEDADE | Cap. V — DOS DIREITOS DE VIZINHANÇA | 1.277–1.313 |
| [110] | T.III — DA PROPRIEDADE | Cap. VI — DO CONDOMÍNIO GERAL | 1.314–1.330 |
| [111] | T.III — DA PROPRIEDADE | Cap. VII — DO CONDOMÍNIO EDILÍCIO | 1.331–1.358-A |
| [112] | T.III — DA PROPRIEDADE | Cap. VII-A — DO CONDOMÍNIO EM MULTIPROPRIEDADE | 1.358-B–1.358-U |
| [113] | T.III — DA PROPRIEDADE | Cap. VIII — DA PROPRIEDADE RESOLÚVEL | 1.359–1.360 |
| [114] | T.III — DA PROPRIEDADE | Cap. IX — DA PROPRIEDADE FIDUCIÁRIA | 1.361–1.368-B |
| [115] | T.III — DA PROPRIEDADE | Cap. X — DO FUNDO DE INVESTIMENTO | 1.368-C–1.368-F |
| [116] | T.IV — DA SUPERFÍCIE | *(título integral)* | 1.369–1.377 |
| [117] | T.V — DAS SERVIDÕES | Cap. I — DA CONSTITUIÇÃO DAS SERVIDÕES | 1.378–1.379 |
| [118] | T.V — DAS SERVIDÕES | Cap. II — DO EXERCÍCIO DAS SERVIDÕES | 1.380–1.386 |
| [119] | T.V — DAS SERVIDÕES | Cap. III — DA EXTINÇÃO DAS SERVIDÕES | 1.387–1.389 |
| [120] | T.VI — DO USUFRUTO | Cap. I — DISPOSIÇÕES GERAIS | 1.390–1.393 |
| [121] | T.VI — DO USUFRUTO | Cap. II — DOS DIREITOS DO USUFRUTUÁRIO | 1.394–1.399 |
| [122] | T.VI — DO USUFRUTO | Cap. III — DOS DEVERES DO USUFRUTUÁRIO | 1.400–1.409 |
| [123] | T.VI — DO USUFRUTO | Cap. IV — DA EXTINÇÃO DO USUFRUTO | 1.410–1.411 |
| [124] | T.VII — DO USO | *(título integral)* | 1.412–1.413 |
| [125] | T.VIII — DA HABITAÇÃO | *(título integral)* | 1.414–1.416 |
| [126] | T.IX — DO DIREITO DO PROMITENTE COMPRADOR | *(título integral)* | 1.417–1.418 |
| [127] | T.X — DO PENHOR, DA HIPOTECA E DA ANTICRESE | Cap. I — DISPOSIÇÕES GERAIS | 1.419–1.430 |
| [128] | T.X — DO PENHOR, DA HIPOTECA E DA ANTICRESE | Cap. II — DO PENHOR | 1.431–1.472 |
| [129] | T.X — DO PENHOR, DA HIPOTECA E DA ANTICRESE | Cap. III — DA HIPOTECA | 1.473–1.505 |
| [130] | T.X — DO PENHOR, DA HIPOTECA E DA ANTICRESE | Cap. IV — DA ANTICRESE | 1.506–1.510 |
| [131] | T.XI — DA LAJE | *(título integral)* | 1.510-A–1.510-E |

#### LIVRO IV — DO DIREITO DE FAMÍLIA (Arts. 1.511–1.783-A)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [132] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. I — DISPOSIÇÕES GERAIS | 1.511–1.516 |
| [133] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. II — DA CAPACIDADE PARA O CASAMENTO | 1.517–1.520 |
| [134] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. III — DOS IMPEDIMENTOS | 1.521–1.522 |
| [135] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. IV — DAS CAUSAS SUSPENSIVAS | 1.523–1.524 |
| [136] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. V — DO PROCESSO DE HABILITAÇÃO PARA O CASAMENTO | 1.525–1.532 |
| [137] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. VI — DA CELEBRAÇÃO DO CASAMENTO | 1.533–1.542 |
| [138] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. VII — DAS PROVAS DO CASAMENTO | 1.543–1.547 |
| [139] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. VIII — DA INVALIDADE DO CASAMENTO | 1.548–1.564 |
| [140] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. IX — DA EFICÁCIA DO CASAMENTO | 1.565–1.570 |
| [141] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. X — DA DISSOLUÇÃO DA SOCIEDADE E DO VÍNCULO CONJUGAL | 1.571–1.582 |
| [142] | T.I — DO DIREITO PESSOAL / Sub.I — DO CASAMENTO | Cap. XI — DA PROTEÇÃO DA PESSOA DOS FILHOS | 1.583–1.590 |
| [143] | T.I — DO DIREITO PESSOAL / Sub.II — DAS RELAÇÕES DE PARENTESCO | Cap. I — DISPOSIÇÕES GERAIS | 1.591–1.595 |
| [144] | T.I — DO DIREITO PESSOAL / Sub.II — DAS RELAÇÕES DE PARENTESCO | Cap. II — DA FILIAÇÃO | 1.596–1.606 |
| [145] | T.I — DO DIREITO PESSOAL / Sub.II — DAS RELAÇÕES DE PARENTESCO | Cap. III — DO RECONHECIMENTO DOS FILHOS | 1.607–1.617 |
| [146] | T.I — DO DIREITO PESSOAL / Sub.II — DAS RELAÇÕES DE PARENTESCO | Cap. IV — DA ADOÇÃO | 1.618–1629 |
| [147] | T.I — DO DIREITO PESSOAL / Sub.II — DAS RELAÇÕES DE PARENTESCO | Cap. V — DO PODER FAMILIAR | 1.630–1.638 |
| [148] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. I — DISPOSIÇÕES GERAIS | 1.639–1.652 |
| [149] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. II — DO PACTO ANTENUPCIAL | 1.653–1.657 |
| [150] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. III — DO REGIME DE COMUNHÃO PARCIAL | 1.658–1.666 |
| [151] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. IV — DO REGIME DE COMUNHÃO UNIVERSAL | 1.667–1.671 |
| [152] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. V — DO REGIME DE PARTICIPAÇÃO FINAL NOS AQÜESTOS | 1.672–1.686 |
| [153] | T.II — DO DIREITO PATRIMONIAL / Sub.I — DO REGIME DE BENS ENTRE OS CÔNJUGES | Cap. VI — DO REGIME DE SEPARAÇÃO DE BENS | 1.687–1.688 |
| [154] | T.II — DO DIREITO PATRIMONIAL / Sub.II — DO USUFRUTO E DA ADMINISTRAÇÃO DOS BENS DE FILHOS MENORES | *(subtítulo integral)* | 1.689–1.693 |
| [155] | T.II — DO DIREITO PATRIMONIAL / Sub.III — DOS ALIMENTOS | *(subtítulo integral)* | 1.694–1.710 |
| [156] | T.II — DO DIREITO PATRIMONIAL / Sub.IV — DO BEM DE FAMÍLIA | *(subtítulo integral)* | 1.711–1.722 |
| [157] | T.III — DA UNIÃO ESTÁVEL | *(título integral)* | 1.723–1.727 |
| [158] | T.IV — Da Tutela, da Curatela e da Tomada de Decisão Apoiada | Cap. I — DA TUTELA | 1.728–1.766 |
| [159] | T.IV — Da Tutela, da Curatela e da Tomada de Decisão Apoiada | Cap. II — DA CURATELA | 1.767–1.783 |
| [160] | T.IV — Da Tutela, da Curatela e da Tomada de Decisão Apoiada | Cap. III — Da Tomada de Decisão Apoiada | 1.783-A |

#### LIVRO V — DO DIREITO DAS SUCESSÕES (Arts. 1.784–2.027)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [161] | T.I — DA SUCESSÃO EM GERAL | Cap. I — DISPOSIÇÕES GERAIS | 1.784–1.790 |
| [162] | T.I — DA SUCESSÃO EM GERAL | Cap. II — DA HERANÇA E DE SUA ADMINISTRAÇÃO | 1.791–1.797 |
| [163] | T.I — DA SUCESSÃO EM GERAL | Cap. III — DA VOCAÇÃO HEREDITÁRIA | 1.798–1.803 |
| [164] | T.I — DA SUCESSÃO EM GERAL | Cap. IV — DA ACEITAÇÃO E RENÚNCIA DA HERANÇA | 1.804–1.813 |
| [165] | T.I — DA SUCESSÃO EM GERAL | Cap. V — DOS EXCLUÍDOS DA SUCESSÃO | 1.814–1.818 |
| [166] | T.I — DA SUCESSÃO EM GERAL | Cap. VI — DA HERANÇA JACENTE | 1.819–1.823 |
| [167] | T.I — DA SUCESSÃO EM GERAL | Cap. VII — DA PETIÇÃO DE HERANÇA | 1.824–1.828 |
| [168] | T.II — DA SUCESSÃO LEGÍTIMA | Cap. I — DA ORDEM DA VOCAÇÃO HEREDITÁRIA | 1.829–1.844 |
| [169] | T.II — DA SUCESSÃO LEGÍTIMA | Cap. II — DOS HERDEIROS NECESSÁRIOS | 1.845–1.850 |
| [170] | T.II — DA SUCESSÃO LEGÍTIMA | Cap. III — DO DIREITO DE REPRESENTAÇÃO | 1.851–1.856 |
| [171] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. I — DO TESTAMENTO EM GERAL | 1.857–1.859 |
| [172] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. II — DA CAPACIDADE DE TESTAR | 1.860–1.861 |
| [173] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. III — DAS FORMAS ORDINÁRIAS DO TESTAMENTO | 1.862–1.880 |
| [174] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. IV — DOS CODICILOS | 1.881–1.885 |
| [175] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. V — DOS TESTAMENTOS ESPECIAIS | 1.886–1.896 |
| [176] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. VI — DAS DISPOSIÇÕES TESTAMENTÁRIAS | 1.897–1.911 |
| [177] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. VII — DOS LEGADOS | 1.912–1.940 |
| [178] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. VIII — DO DIREITO DE ACRESCER ENTRE HERDEIROS E LEGATÁRIOS | 1.941–1.946 |
| [179] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. IX — DAS SUBSTITUIÇÕES | 1.947–1.960 |
| [180] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. X — DA DESERDAÇÃO | 1.961–1.965 |
| [181] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. XI — DA REDUÇÃO DAS DISPOSIÇÕES TESTAMENTÁRIAS | 1.966–1.968 |
| [182] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. XII — DA REVOGAÇÃO DO TESTAMENTO | 1.969–1.972 |
| [183] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. XIII — DO ROMPIMENTO DO TESTAMENTO | 1.973–1.975 |
| [184] | T.III — DA SUCESSÃO TESTAMENTÁRIA | Cap. XIV — DO TESTAMENTEIRO | 1.976–1.990 |
| [185] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. I — DO INVENTÁRIO | 1.991 |
| [186] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. II — Dos Sonegados | 1.992–1.996 |
| [187] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. III — DO PAGAMENTO DAS DÍVIDAS | 1.997–2.001 |
| [188] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. IV — DA COLAÇÃO | 2.002–2.012 |
| [189] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. V — DA PARTILHA | 2.013–2.022 |
| [190] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. VI — DA GARANTIA DOS QUINHÕES HEREDITÁRIOS | 2.023–2.026 |
| [191] | T.IV — DO INVENTÁRIO E DA PARTILHA | Cap. VII — DA ANULAÇÃO DA PARTILHA | 2.027 |

### LIVRO COMPLEMENTAR (fora das Partes)


#### LIVRO COMPLEMENTAR — DAS DISPOSIÇÕES FINAIS E TRANSITÓRIAS (Arts. 2.028–2.046)

| Chunk | Título / Subtítulo | Capítulo | Artigos |
|-------|---------------------|----------|---------|
| [192] | — | *(livro integral)* | 2.028–2.046 |

---

## 3. ÍNDICE TEMÁTICO RÁPIDO

Use este índice para identificar o(s) chunk(s) correto(s) pela temática da pergunta:

| Tema | Chunk(s) |
|------|----------|
| Personalidade e capacidade civil | 001 |
| Direitos da personalidade | 002 |
| Ausência / morte presumida | 003 |
| Pessoa jurídica (disposições gerais) | 004 |
| Associações | 005 |
| Fundações | 006 |
| Domicílio | 007 |
| Bens (classificação) | 008 |
| Negócio jurídico — disposições gerais | 011 |
| Defeitos do negócio jurídico (erro, dolo, coação, lesão, fraude) | 014 |
| Invalidade do negócio jurídico / nulidades | 015 |
| Prescrição | 018, 019 |
| Decadência | 018, 019 |
| Prova | 020 |
| Obrigações — modalidades (dar, fazer, não fazer, alternativas, solidárias) | 021, 022, 023, 024, 025, 026 |
| Adimplemento e extinção das obrigações / pagamento | 029, 030, 031, 032, 033, 034, 035, 036, 037 |
| Inadimplemento, mora, perdas e danos, cláusula penal | 038, 039, 040, 041, 042, 043 |
| Contratos — disposições gerais, formação, vícios redibitórios, evicção | 044, 045 |
| Compra e venda | 046 |
| Troca, doação, locação | 049 |
| Locação de coisas | 050 |
| Comodato / mútuo | 051 |
| Prestação de serviço / empreitada | 053 |
| Mandato | 055 |
| Seguro | 060 |
| Fiança | 063 |
| Transação / compromisso (arbitragem) | 064 |
| Títulos de crédito | 071 |
| Responsabilidade civil / obrigação de indenizar | 075 |
| Empresário / capacidade para empresa | 078 |
| Sociedade simples | 084 |
| Sociedade limitada | 087 |
| Sociedade anônima / cooperativa | 088 |
| Estabelecimento empresarial | 095 |
| Posse | 100 |
| Propriedade em geral / usucapião | 105 |
| Aquisição da propriedade imóvel (usucapião) | 106 |
| Direitos de vizinhança | 109 |
| Condomínio geral / edilício | 111 |
| Multipropriedade | 112 |
| Propriedade resolúvel / fiduciária | 114 |
| Superfície | 116 |
| Servidões | 117 |
| Usufruto | 121 |
| Penhor, hipoteca e anticrese — disposições gerais | 127, 128, 129, 130 |
| Hipoteca | 127 |
| Casamento — capacidade, impedimentos, celebração | 132 |
| Invalidade do casamento | 139 |
| Divórcio / dissolução do vínculo conjugal | 141 |
| Filiação / reconhecimento de filhos | 144 |
| Adoção | 146 |
| Poder familiar | 147 |
| Regime de bens entre cônjuges (geral) | 148 |
| Pacto antenupcial | 149 |
| Regimes de bens (comunhão parcial/universal/participação/separação) | 150, 151, 152, 153 |
| Alimentos | 155 |
| Bem de família | 156 |
| União estável | 157 |
| Tutela | 158 |
| Curatela | 159 |
| Tomada de decisão apoiada | 158, 159, 160 |
| Sucessão em geral / herança jacente | 166 |
| Ordem da vocação hereditária / herdeiros necessários | 168 |
| Direito de representação (sucessões) | 170 |
| Testamento — formas, capacidade, codicilos | 173 |
| Legados | 177 |
| Deserdação | 180 |
| Revogação / rompimento do testamento | 182 |
| Inventário e partilha | 185, 186, 187, 188, 189, 190, 191 |
| Colação | 188 |
| Anulação da partilha | 191 |
| Disposições finais e transitórias / direito intertemporal | 192 |
| Tomada de decisão apoiada | 160 |

---

## 4. REGRAS DE ROTEAMENTO PARA O SISTEMA RAG

```
SE a pergunta menciona:
  - artigo específico (ex: "art. 927", "art. 1.641") → localizar no Mapa Hierárquico (Seção 2) o chunk cujo range de artigos inclui o número
  - "personalidade", "capacidade civil", "incapaz" → Chunk 001
  - "pessoa jurídica", "associação", "fundação" → Chunks 004–006
  - "negócio jurídico", "defeito", "erro", "dolo", "coação", "simulação" → Chunks 011–015
  - "prescrição" → Chunk 018 | "decadência" → Chunk 019
  - "obrigações" (modalidades, solidárias, transmissão) → Chunks 021–030
  - "inadimplemento", "mora", "perdas e danos", "cláusula penal", "juros" → Chunks 034–038
  - "contrato" (disposições gerais, formação, vícios redibitórios, evicção) → Chunks 039–045
  - "compra e venda" → Chunk 046 | "doação" → Chunk 049 | "locação" → Chunk 050
  - "comodato", "mútuo", "empréstimo" → Chunk 051
  - "mandato" → Chunk 055 | "seguro" → Chunk 060 | "fiança" → Chunk 063
  - "transação", "arbitragem", "compromisso" → Chunk 064
  - "títulos de crédito" → Chunks 071–074
  - "responsabilidade civil", "indenização", "dano" → Chunks 075–076
  - "empresário", "sociedade limitada", "sociedade anônima" → Chunks 078–099
  - "posse" → Chunks 100–103
  - "propriedade", "usucapião" → Chunks 105–108
  - "direitos de vizinhança" → Chunk 109
  - "condomínio edilício" → Chunk 111 | "multipropriedade" → Chunk 112
  - "propriedade fiduciária" → Chunk 117
  - "servidão" → Chunks 118–119 | "usufruto" → Chunks 120–123
  - "penhor" → Chunk 128 | "hipoteca" → Chunk 129 | "anticrese" → Chunk 130
  - "casamento" (capacidade, celebração, invalidade) → Chunks 133–139
  - "divórcio", "dissolução do vínculo conjugal" → Chunk 141
  - "filiação", "reconhecimento de filhos" → Chunks 144–145
  - "adoção" → Chunk 146 | "poder familiar" → Chunk 147
  - "regime de bens", "pacto antenupcial" → Chunks 148–153
  - "alimentos" → Chunk 155 | "bem de família" → Chunk 156
  - "união estável" → Chunk 157
  - "tutela" → Chunk 158 | "curatela" → Chunk 159 | "tomada de decisão apoiada" → Chunk 160
  - "herança", "vocação hereditária", "herdeiros necessários" → Chunks 161–169
  - "testamento" (formas, capacidade, codicilo) → Chunks 171–176
  - "legado" → Chunk 177 | "deserdação" → Chunk 180
  - "inventário", "partilha", "colação" → Chunks 185–191
  - "disposições finais e transitórias", "direito intertemporal" → Chunk 192
```

---

## 5. INSTRUÇÕES DE USO DO DUAL-INDEX

**Index A (este chunk — Chunk_000_MESTRE_CC.md):**
- Usar para responder perguntas sobre: *qual a estrutura do Código Civil / em que livro-título-capítulo está tal matéria / quais chunks preciso combinar*.
- Contém o mapa hierárquico completo (Seção 2) e o índice temático (Seção 3).
- Sempre carregar em conjunto com o(s) chunk(s) do Index B relevante(s) ao tema da pergunta.

**Index B (Chunk_001.md … Chunk_192.md):**
- Usar para recuperar o texto integral dos artigos sobre um tema específico.
- Cada chunk corresponde a um Capítulo (ou, na ausência de Capítulo, ao Subtítulo ou Título integral, ou ao Livro Complementar).
- Frontmatter de cada chunk contém: `parte`, `livro`, `titulo`, `subtitulo`, `capitulo`, `arts_range`, `art_inicio`, `art_fim`, `linha_inicio`, `linha_fim`.
- Selecionar pelo `chunk_id` indicado nas Seções 2–4 deste chunk mestre.
- Combinar sempre com o chunk mestre para contextualização sistemática (ex.: saber que um artigo sobre "regime de bens" está dentro do Subtítulo I do Título II do Livro IV, Direito de Família).

---

*Gerado automaticamente a partir de OpenL-2607011429.md (texto compilado da Lei nº 10.406/2002, Presidência da República/Casa Civil, consultado em 01/07/2026) — Base: 192 chunks complementares, Arts. 1–2.046.*

<!-- MAPA_ATUALIZADO_INICIO -->

## MAPA ATUALIZADO DE CHUNKS (fonte: index_artigos.json)

Total de chunks complementares: **197**

| Arquivo | Artigos | Capítulo/Título |
|---|---|---|
| Chunk_001_DA_PERSONALIDADE_E_DA_CAPACIDADE.md | 1–10 | CAPÍTULO I — DA PERSONALIDADE E DA CAPACIDADE |
| Chunk_002_DOS_DIREITOS_DA_PERSONALIDADE.md | 11–21 | CAPÍTULO II — DOS DIREITOS DA PERSONALIDADE |
| Chunk_003_DA_AUSENCIA.md | 22–39 | CAPÍTULO III — DA AUSÊNCIA |
| Chunk_004_DISPOSICOES_GERAIS.md | 40–52 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_005_DAS_ASSOCIACOES.md | 53–61 | CAPÍTULO II — DAS ASSOCIAÇÕES |
| Chunk_006_DAS_FUNDACOES.md | 62–69 | CAPÍTULO III — DAS FUNDAÇÕES |
| Chunk_007_DO_DOMICILIO.md | 70–78 | TÍTULO III — DO DOMICÍLIO |
| Chunk_008_DOS_BENS_CONSIDERADOS_EM_SI_MESMOS.md | 79–91 | CAPÍTULO I — DOS BENS CONSIDERADOS EM SI MESMOS |
| Chunk_009_DOS_BENS_RECIPROCAMENTE_CONSIDERADOS.md | 92–97 | CAPÍTULO II — DOS BENS RECIPROCAMENTE CONSIDERADOS |
| Chunk_010_DOS_BENS_PUBLICOS.md | 98–103 | CAPÍTULO III — DOS BENS PÚBLICOS |
| Chunk_011_DISPOSICOES_GERAIS.md | 104–114 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_012_DA_REPRESENTACAO.md | 115–120 | CAPÍTULO II — DA REPRESENTAÇÃO |
| Chunk_013_DA_CONDICAO_DO_TERMO_E_DO_ENCARGO.md | 121–137 | CAPÍTULO III — DA CONDIÇÃO, DO TERMO E DO ENCARGO |
| Chunk_014_DOS_DEFEITOS_DO_NEGOCIO_JURIDICO.md | 138–165 | CAPÍTULO IV — DOS DEFEITOS DO NEGÓCIO JURÍDICO |
| Chunk_015_DA_INVALIDADE_DO_NEGOCIO_JURIDICO.md | 166–184 | CAPÍTULO V — DA INVALIDADE DO NEGÓCIO JURÍDICO |
| Chunk_016_DOS_ATOS_JURIDICOS_LICITOS.md | 185–185 | TÍTULO II — DOS ATOS JURÍDICOS LÍCITOS |
| Chunk_017_DOS_ATOS_ILICITOS.md | 186–188 | TÍTULO III — DOS ATOS ILÍCITOS |
| Chunk_018_DA_PRESCRICAO.md | 189–206 | CAPÍTULO I — DA PRESCRIÇÃO |
| Chunk_019_DA_DECADENCIA.md | 207–211 | CAPÍTULO II — DA DECADÊNCIA |
| Chunk_020_DA_PROVA.md | 212–232 | TÍTULO V — DA PROVA |
| Chunk_021_DAS_OBRIGACOES_DE_DAR.md | 233–246 | CAPÍTULO I — DAS OBRIGAÇÕES DE DAR |
| Chunk_022_DAS_OBRIGACOES_DE_FAZER.md | 247–249 | CAPÍTULO II — DAS OBRIGAÇÕES DE FAZER |
| Chunk_023_DAS_OBRIGACOES_DE_NAO_FAZER.md | 250–251 | CAPÍTULO III — DAS OBRIGAÇÕES DE NÃO FAZER |
| Chunk_024_DAS_OBRIGACOES_ALTERNATIVAS.md | 252–256 | CAPÍTULO IV — DAS OBRIGAÇÕES ALTERNATIVAS |
| Chunk_025_DAS_OBRIGACOES_DIVISIVEIS_E_INDIVISIVEIS.md | 257–263 | CAPÍTULO V — DAS OBRIGAÇÕES DIVISÍVEIS E INDIVISÍVEIS |
| Chunk_026_DAS_OBRIGACOES_SOLIDARIAS.md | 264–285 | CAPÍTULO VI — DAS OBRIGAÇÕES SOLIDÁRIAS |
| Chunk_027_DA_CESSAO_DE_CREDITO.md | 286–298 | CAPÍTULO I — DA CESSÃO DE CRÉDITO |
| Chunk_028_DA_ASSUNCAO_DE_DIVIDA.md | 299–303 | CAPÍTULO II — DA ASSUNÇÃO DE DÍVIDA |
| Chunk_029_DO_PAGAMENTO.md | 304–333 | CAPÍTULO I — DO PAGAMENTO |
| Chunk_030_DO_PAGAMENTO_EM_CONSIGNACAO.md | 334–345 | CAPÍTULO II — DO PAGAMENTO EM CONSIGNAÇÃO |
| Chunk_031_DO_PAGAMENTO_COM_SUB_ROGACAO.md | 346–351 | CAPÍTULO III — DO PAGAMENTO COM SUB-ROGAÇÃO |
| Chunk_032_DA_IMPUTACAO_DO_PAGAMENTO.md | 352–355 | CAPÍTULO IV — DA IMPUTAÇÃO DO PAGAMENTO |
| Chunk_033_DA_DACAO_EM_PAGAMENTO.md | 356–359 | CAPÍTULO V — DA DAÇÃO EM PAGAMENTO |
| Chunk_034_DA_NOVACAO.md | 360–367 | CAPÍTULO VI — DA NOVAÇÃO |
| Chunk_035_DA_COMPENSACAO.md | 368–380 | CAPÍTULO VII — DA COMPENSAÇÃO |
| Chunk_036_DA_CONFUSAO.md | 381–384 | CAPÍTULO VIII — DA CONFUSÃO |
| Chunk_037_DA_REMISSAO_DAS_DIVIDAS.md | 385–388 | CAPÍTULO IX — DA REMISSÃO DAS DÍVIDAS |
| Chunk_038_DISPOSICOES_GERAIS.md | 389–393 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_039_DA_MORA.md | 394–401 | CAPÍTULO II — DA MORA |
| Chunk_040_DAS_PERDAS_E_DANOS.md | 402–405 | CAPÍTULO III — DAS PERDAS E DANOS |
| Chunk_041_DOS_JUROS_LEGAIS.md | 406–407 | CAPÍTULO IV — DOS JUROS LEGAIS |
| Chunk_042_DA_CLAUSULA_PENAL.md | 408–416 | CAPÍTULO V — DA CLÁUSULA PENAL |
| Chunk_043_DAS_ARRAS_OU_SINAL.md | 417–420 | CAPÍTULO VI — DAS ARRAS OU SINAL |
| Chunk_044_DISPOSICOES_GERAIS.md | 421–471 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_045_DA_EXTINCAO_DO_CONTRATO.md | 472–480 | CAPÍTULO II — DA EXTINÇÃO DO CONTRATO |
| Chunk_046_DA_COMPRA_E_VENDA.md | 481–532 | CAPÍTULO I — DA COMPRA E VENDA |
| Chunk_047_DA_TROCA_OU_PERMUTA.md | 533–533 | CAPÍTULO II — DA TROCA OU PERMUTA |
| Chunk_048_DO_CONTRATO_ESTIMATORIO.md | 534–537 | CAPÍTULO III — DO CONTRATO ESTIMATÓRIO |
| Chunk_049_DA_DOACAO.md | 538–564 | CAPÍTULO IV — DA DOAÇÃO |
| Chunk_050_DA_LOCACAO_DE_COISAS.md | 565–578 | CAPÍTULO V — DA LOCAÇÃO DE COISAS |
| Chunk_051_DO_EMPRESTIMO.md | 579–592 | CAPÍTULO VI — DO EMPRÉSTIMO |
| Chunk_052_DA_PRESTACAO_DE_SERVICO.md | 593–609 | CAPÍTULO VII — DA PRESTAÇÃO DE SERVIÇO |
| Chunk_053_DA_EMPREITADA.md | 610–626 | CAPÍTULO VIII — DA EMPREITADA |
| Chunk_054_DO_DEPOSITO.md | 627–652 | CAPÍTULO IX — DO DEPÓSITO |
| Chunk_055_DO_MANDATO.md | 653–692 | CAPÍTULO X — DO MANDATO |
| Chunk_056_DA_COMISSAO.md | 693–709 | CAPÍTULO XI — DA COMISSÃO |
| Chunk_057_DA_AGENCIA_E_DISTRIBUICAO.md | 710–721 | CAPÍTULO XII — DA AGÊNCIA E DISTRIBUIÇÃO |
| Chunk_058_DA_CORRETAGEM.md | 722–729 | CAPÍTULO XIII — DA CORRETAGEM |
| Chunk_059_DO_TRANSPORTE.md | 730–756 | CAPÍTULO XIV — DO TRANSPORTE |
| Chunk_060_DO_SEGURO.md | 757–802 | CAPÍTULO XV — DO SEGURO |
| Chunk_061_DA_CONSTITUICAO_DE_RENDA.md | 803–813 | CAPÍTULO XVI — DA CONSTITUIÇÃO DE RENDA |
| Chunk_062_DO_JOGO_E_DA_APOSTA.md | 814–817 | CAPÍTULO XVII — DO JOGO E DA APOSTA |
| Chunk_063_DA_FIANCA.md | 818–839 | CAPÍTULO XVIII — DA FIANÇA |
| Chunk_064_DA_TRANSACAO.md | 840–850 | CAPÍTULO XIX — DA TRANSAÇÃO |
| Chunk_065_DO_COMPROMISSO.md | 851–853 | CAPÍTULO XX — DO COMPROMISSO |
| Chunk_066_DO_CONTRATO_DE_ADMINISTRACAO_FIDUCIARIA_DE_GA.md | 853–853 | CAPÍTULO XXI — DO CONTRATO DE ADMINISTRAÇÃO FIDUCIÁRIA DE GARANTIAS |
| Chunk_067_DA_PROMESSA_DE_RECOMPENSA.md | 854–860 | CAPÍTULO I — DA PROMESSA DE RECOMPENSA |
| Chunk_068_DA_GESTAO_DE_NEGOCIOS.md | 861–875 | CAPÍTULO II — DA GESTÃO DE NEGÓCIOS |
| Chunk_069_DO_PAGAMENTO_INDEVIDO.md | 876–883 | CAPÍTULO III — DO PAGAMENTO INDEVIDO |
| Chunk_070_DO_ENRIQUECIMENTO_SEM_CAUSA.md | 884–886 | CAPÍTULO IV — DO ENRIQUECIMENTO SEM CAUSA |
| Chunk_071_DISPOSICOES_GERAIS.md | 887–903 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_072_DO_TITULO_AO_PORTADOR.md | 904–909 | CAPÍTULO II — DO TÍTULO AO PORTADOR |
| Chunk_073_DO_TITULO_A_ORDEM.md | 910–920 | CAPÍTULO III — DO TÍTULO À ORDEM |
| Chunk_074_DO_TITULO_NOMINATIVO.md | 921–926 | CAPÍTULO IV — DO TÍTULO NOMINATIVO |
| Chunk_075_DA_OBRIGACAO_DE_INDENIZAR.md | 927–943 | CAPÍTULO I — DA OBRIGAÇÃO DE INDENIZAR |
| Chunk_076_DA_INDENIZACAO.md | 944–954 | CAPÍTULO II — DA INDENIZAÇÃO |
| Chunk_077_DAS_PREFERENCIAS_E_PRIVILEGIOS_CREDITORIOS.md | 955–965 | TÍTULO X — DAS PREFERÊNCIAS E PRIVILÉGIOS CREDITÓRIOS |
| Chunk_078_DA_CARACTERIZACAO_E_DA_INSCRICAO.md | 966–971 | CAPÍTULO I — DA CARACTERIZAÇÃO E DA INSCRIÇÃO |
| Chunk_079_DA_CAPACIDADE.md | 972–980 | CAPÍTULO II — DA CAPACIDADE |
| Chunk_080_DA_EMPRESA_INDIVIDUAL_DE_RESPONSABILIDADE_LIM.md | 980–980 | TÍTULO I-A — DA EMPRESA INDIVIDUAL DE RESPONSABILIDADE LIMITADA |
| Chunk_081_DISPOSICOES_GERAIS.md | 981–985 | CAPÍTULO UNICO — DISPOSIÇÕES GERAIS |
| Chunk_082_DA_SOCIEDADE_EM_COMUM.md | 986–990 | CAPÍTULO I — DA SOCIEDADE EM COMUM |
| Chunk_083_DA_SOCIEDADE_EM_CONTA_DE_PARTICIPACAO.md | 991–996 | CAPÍTULO II — DA SOCIEDADE EM CONTA DE PARTICIPAÇÃO |
| Chunk_084_DA_SOCIEDADE_SIMPLES_P01.md | 997–1019 | CAPÍTULO I — DA SOCIEDADE SIMPLES |
| Chunk_084_DA_SOCIEDADE_SIMPLES_P02.md | 1020–1038 | CAPÍTULO I — DA SOCIEDADE SIMPLES |
| Chunk_085_DA_SOCIEDADE_EM_NOME_COLETIVO.md | 1039–1044 | CAPÍTULO II — Da Sociedade em Nome Coletivo |
| Chunk_086_DA_SOCIEDADE_EM_COMANDITA_SIMPLES.md | 1045–1051 | CAPÍTULO III — Da Sociedade em Comandita Simples |
| Chunk_087_DA_SOCIEDADE_LIMITADA_P01.md | 1052–1071 | CAPÍTULO IV — Da Sociedade Limitada |
| Chunk_087_DA_SOCIEDADE_LIMITADA_P02.md | 1072–1087 | CAPÍTULO IV — Da Sociedade Limitada |
| Chunk_088_DA_SOCIEDADE_ANONIMA.md | 1088–1089 | CAPÍTULO V — DA SOCIEDADE ANÔNIMA |
| Chunk_089_DA_SOCIEDADE_EM_COMANDITA_POR_ACOES.md | 1090–1092 | CAPÍTULO VI — DA SOCIEDADE EM COMANDITA POR AÇÕES |
| Chunk_090_DA_SOCIEDADE_COOPERATIVA.md | 1093–1096 | CAPÍTULO VII — DA SOCIEDADE COOPERATIVA |
| Chunk_091_DAS_SOCIEDADES_COLIGADAS.md | 1097–1101 | CAPÍTULO VIII — DAS SOCIEDADES COLIGADAS |
| Chunk_092_DA_LIQUIDACAO_DA_SOCIEDADE.md | 1102–1112 | CAPÍTULO IX — DA LIQUIDAÇÃO DA SOCIEDADE |
| Chunk_093_DA_TRANSFORMACAO_DA_INCORPORACAO_DA_FUSAO_E_D.md | 1113–1122 | CAPÍTULO X — DA TRANSFORMAÇÃO, DA INCORPORAÇÃO, DA FUSÃO E DA CISÃO DAS SOCIEDADES |
| Chunk_094_DA_SOCIEDADE_DEPENDENTE_DE_AUTORIZACAO.md | 1123–1141 | CAPÍTULO XI — DA SOCIEDADE DEPENDENTE DE AUTORIZAÇÃO |
| Chunk_095_DISPOSICOES_GERAIS.md | 1142–1149 | CAPÍTULO UNICO — DISPOSIÇÕES GERAIS |
| Chunk_096_DO_REGISTRO.md | 1150–1154 | CAPÍTULO I — DO REGISTRO |
| Chunk_097_DO_NOME_EMPRESARIAL.md | 1155–1168 | CAPÍTULO II — DO NOME EMPRESARIAL |
| Chunk_098_DOS_PREPOSTOS.md | 1169–1178 | CAPÍTULO III — DOS PREPOSTOS |
| Chunk_099_DA_ESCRITURACAO.md | 1179–1195 | CAPÍTULO IV — DA ESCRITURAÇÃO |
| Chunk_100_DA_POSSE_E_SUA_CLASSIFICACAO.md | 1196–1203 | CAPÍTULO I — DA POSSE E SUA CLASSIFICAÇÃO |
| Chunk_101_DA_AQUISICAO_DA_POSSE.md | 1204–1209 | CAPÍTULO II — DA AQUISIÇÃO DA POSSE |
| Chunk_102_DOS_EFEITOS_DA_POSSE.md | 1210–1222 | CAPÍTULO III — DOS EFEITOS DA POSSE |
| Chunk_103_DA_PERDA_DA_POSSE.md | 1223–1224 | CAPÍTULO IV — DA PERDA DA POSSE |
| Chunk_104_DISPOSICOES_GERAIS.md | 1225–1227 | CAPÍTULO UNICO — DISPOSIÇÕES GERAIS |
| Chunk_105_DA_PROPRIEDADE_EM_GERAL.md | 1228–1237 | CAPÍTULO I — DA PROPRIEDADE EM GERAL |
| Chunk_106_DA_AQUISICAO_DA_PROPRIEDADE_IMOVEL.md | 1238–1259 | CAPÍTULO II — DA AQUISIÇÃO DA PROPRIEDADE IMÓVEL |
| Chunk_107_DA_AQUISICAO_DA_PROPRIEDADE_MOVEL.md | 1260–1274 | CAPÍTULO III — DA AQUISIÇÃO DA PROPRIEDADE MÓVEL |
| Chunk_108_DA_PERDA_DA_PROPRIEDADE.md | 1275–1276 | CAPÍTULO IV — DA PERDA DA PROPRIEDADE |
| Chunk_109_DOS_DIREITOS_DE_VIZINHANCA.md | 1277–1313 | CAPÍTULO V — DOS DIREITOS DE VIZINHANÇA |
| Chunk_110_DO_CONDOMINIO_GERAL.md | 1314–1330 | CAPÍTULO VI — DO CONDOMÍNIO GERAL |
| Chunk_111_DO_CONDOMINIO_EDILICIO_P01.md | 1331–1347 | CAPÍTULO VII — DO CONDOMÍNIO EDILÍCIO |
| Chunk_111_DO_CONDOMINIO_EDILICIO_P02.md | 1348–1358 | CAPÍTULO VII — DO CONDOMÍNIO EDILÍCIO |
| Chunk_112_DO_CONDOMINIO_EM_MULTIPROPRIEDADE_P01.md | 1358–1358 | CAPÍTULO VII-A — DO CONDOMÍNIO EM MULTIPROPRIEDADE |
| Chunk_112_DO_CONDOMINIO_EM_MULTIPROPRIEDADE_P02.md | 1358–1358 | CAPÍTULO VII-A — DO CONDOMÍNIO EM MULTIPROPRIEDADE |
| Chunk_112_DO_CONDOMINIO_EM_MULTIPROPRIEDADE_P03.md | 1358–1358 | CAPÍTULO VII-A — DO CONDOMÍNIO EM MULTIPROPRIEDADE |
| Chunk_113_DA_PROPRIEDADE_RESOLUVEL.md | 1359–1360 | CAPÍTULO VIII — DA PROPRIEDADE RESOLÚVEL |
| Chunk_114_DA_PROPRIEDADE_FIDUCIARIA.md | 1361–1368 | CAPÍTULO IX — DA PROPRIEDADE FIDUCIÁRIA |
| Chunk_115_DO_FUNDO_DE_INVESTIMENTO.md | 1368–1368 | CAPÍTULO X — DO FUNDO DE INVESTIMENTO |
| Chunk_116_DA_SUPERFICIE.md | 1369–1377 | TÍTULO IV — DA SUPERFÍCIE |
| Chunk_117_DA_CONSTITUICAO_DAS_SERVIDOES.md | 1378–1379 | CAPÍTULO I — DA CONSTITUIÇÃO DAS SERVIDÕES |
| Chunk_118_DO_EXERCICIO_DAS_SERVIDOES.md | 1380–1386 | CAPÍTULO II — DO EXERCÍCIO DAS SERVIDÕES |
| Chunk_119_DA_EXTINCAO_DAS_SERVIDOES.md | 1387–1389 | CAPÍTULO III — DA EXTINÇÃO DAS SERVIDÕES |
| Chunk_120_DISPOSICOES_GERAIS.md | 1390–1393 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_121_DOS_DIREITOS_DO_USUFRUTUARIO.md | 1394–1399 | CAPÍTULO II — DOS DIREITOS DO USUFRUTUÁRIO |
| Chunk_122_DOS_DEVERES_DO_USUFRUTUARIO.md | 1400–1409 | CAPÍTULO III — DOS DEVERES DO USUFRUTUÁRIO |
| Chunk_123_DA_EXTINCAO_DO_USUFRUTO.md | 1410–1411 | CAPÍTULO IV — DA EXTINÇÃO DO USUFRUTO |
| Chunk_124_DO_USO.md | 1412–1413 | TÍTULO VII — DO USO |
| Chunk_125_DA_HABITACAO.md | 1414–1416 | TÍTULO VIII — DA HABITAÇÃO |
| Chunk_126_DO_DIREITO_DO_PROMITENTE_COMPRADOR.md | 1417–1418 | TÍTULO IX — DO DIREITO DO PROMITENTE COMPRADOR |
| Chunk_127_DISPOSICOES_GERAIS.md | 1419–1430 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_128_DO_PENHOR.md | 1431–1472 | CAPÍTULO II — DO PENHOR |
| Chunk_129_DA_HIPOTECA.md | 1473–1505 | CAPÍTULO III — DA HIPOTECA |
| Chunk_130_DA_ANTICRESE.md | 1506–1510 | CAPÍTULO IV — DA ANTICRESE |
| Chunk_131_DA_LAJE.md | 1510–1510 | TÍTULO XI — DA LAJE |
| Chunk_132_DISPOSICOES_GERAIS.md | 1511–1516 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_133_DA_CAPACIDADE_PARA_O_CASAMENTO.md | 1517–1520 | CAPÍTULO II — DA CAPACIDADE PARA O CASAMENTO |
| Chunk_134_DOS_IMPEDIMENTOS.md | 1521–1522 | CAPÍTULO III — DOS IMPEDIMENTOS |
| Chunk_135_DAS_CAUSAS_SUSPENSIVAS.md | 1523–1524 | CAPÍTULO IV — DAS CAUSAS SUSPENSIVAS |
| Chunk_136_DO_PROCESSO_DE_HABILITACAO_PARA_O_CASAMENTO.md | 1525–1532 | CAPÍTULO V — DO PROCESSO DE HABILITAÇÃO PARA O CASAMENTO |
| Chunk_137_DA_CELEBRACAO_DO_CASAMENTO.md | 1533–1542 | CAPÍTULO VI — DA CELEBRAÇÃO DO CASAMENTO |
| Chunk_138_DAS_PROVAS_DO_CASAMENTO.md | 1543–1547 | CAPÍTULO VII — DAS PROVAS DO CASAMENTO |
| Chunk_139_DA_INVALIDADE_DO_CASAMENTO.md | 1548–1564 | CAPÍTULO VIII — DA INVALIDADE DO CASAMENTO |
| Chunk_140_DA_EFICACIA_DO_CASAMENTO.md | 1565–1570 | CAPÍTULO IX — DA EFICÁCIA DO CASAMENTO |
| Chunk_141_DA_DISSOLUCAO_DA_SOCIEDADE_E_DO_VINCULO_CONJU.md | 1571–1582 | CAPÍTULO X — DA DISSOLUÇÃO DA SOCIEDADE E DO VÍNCULO CONJUGAL |
| Chunk_142_DA_PROTECAO_DA_PESSOA_DOS_FILHOS.md | 1583–1590 | CAPÍTULO XI — DA PROTEÇÃO DA PESSOA DOS FILHOS |
| Chunk_143_DISPOSICOES_GERAIS.md | 1591–1595 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_144_DA_FILIACAO.md | 1596–1606 | CAPÍTULO II — DA FILIAÇÃO |
| Chunk_145_DO_RECONHECIMENTO_DOS_FILHOS.md | 1607–1617 | CAPÍTULO III — DO RECONHECIMENTO DOS FILHOS |
| Chunk_146_DA_ADOCAO.md | 1618–1629 | CAPÍTULO IV — DA ADOÇÃO |
| Chunk_147_DO_PODER_FAMILIAR.md | 1630–1638 | CAPÍTULO V — DO PODER FAMILIAR |
| Chunk_148_DISPOSICOES_GERAIS.md | 1639–1652 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_149_DO_PACTO_ANTENUPCIAL.md | 1653–1657 | CAPÍTULO II — DO PACTO ANTENUPCIAL |
| Chunk_150_DO_REGIME_DE_COMUNHAO_PARCIAL.md | 1658–1666 | CAPÍTULO III — DO REGIME DE COMUNHÃO PARCIAL |
| Chunk_151_DO_REGIME_DE_COMUNHAO_UNIVERSAL.md | 1667–1671 | CAPÍTULO IV — DO REGIME DE COMUNHÃO UNIVERSAL |
| Chunk_152_DO_REGIME_DE_PARTICIPACAO_FINAL_NOS_AQUESTOS.md | 1672–1686 | CAPÍTULO V — DO REGIME DE PARTICIPAÇÃO FINAL NOS AQÜESTOS |
| Chunk_153_DO_REGIME_DE_SEPARACAO_DE_BENS.md | 1687–1688 | CAPÍTULO VI — DO REGIME DE SEPARAÇÃO DE BENS |
| Chunk_154_DO_USUFRUTO_E_DA_ADMINISTRACAO_DOS_BENS_DE_FI.md | 1689–1693 | TÍTULO II — DO DIREITO PATRIMONIAL |
| Chunk_155_DOS_ALIMENTOS.md | 1694–1710 | TÍTULO II — DO DIREITO PATRIMONIAL |
| Chunk_156_DO_BEM_DE_FAMILIA.md | 1711–1722 | TÍTULO II — DO DIREITO PATRIMONIAL |
| Chunk_157_DA_UNIAO_ESTAVEL.md | 1723–1727 | TÍTULO III — DA UNIÃO ESTÁVEL |
| Chunk_158_DA_TUTELA.md | 1728–1766 | CAPÍTULO I — DA TUTELA |
| Chunk_159_DA_CURATELA.md | 1767–1783 | CAPÍTULO II — DA CURATELA |
| Chunk_160_DA_TOMADA_DE_DECISAO_APOIADA.md | 1783–1783 | CAPÍTULO III — Da Tomada de Decisão Apoiada |
| Chunk_161_DISPOSICOES_GERAIS.md | 1784–1790 | CAPÍTULO I — DISPOSIÇÕES GERAIS |
| Chunk_162_DA_HERANCA_E_DE_SUA_ADMINISTRACAO.md | 1791–1797 | CAPÍTULO II — DA HERANÇA E DE SUA ADMINISTRAÇÃO |
| Chunk_163_DA_VOCACAO_HEREDITARIA.md | 1798–1803 | CAPÍTULO III — DA VOCAÇÃO HEREDITÁRIA |
| Chunk_164_DA_ACEITACAO_E_RENUNCIA_DA_HERANCA.md | 1804–1813 | CAPÍTULO IV — DA ACEITAÇÃO E RENÚNCIA DA HERANÇA |
| Chunk_165_DOS_EXCLUIDOS_DA_SUCESSAO.md | 1814–1818 | CAPÍTULO V — DOS EXCLUÍDOS DA SUCESSÃO |
| Chunk_166_DA_HERANCA_JACENTE.md | 1819–1823 | CAPÍTULO VI — DA HERANÇA JACENTE |
| Chunk_167_DA_PETICAO_DE_HERANCA.md | 1824–1828 | CAPÍTULO VII — DA PETIÇÃO DE HERANÇA |
| Chunk_168_DA_ORDEM_DA_VOCACAO_HEREDITARIA.md | 1829–1844 | CAPÍTULO I — DA ORDEM DA VOCAÇÃO HEREDITÁRIA |
| Chunk_169_DOS_HERDEIROS_NECESSARIOS.md | 1845–1850 | CAPÍTULO II — DOS HERDEIROS NECESSÁRIOS |
| Chunk_170_DO_DIREITO_DE_REPRESENTACAO.md | 1851–1856 | CAPÍTULO III — DO DIREITO DE REPRESENTAÇÃO |
| Chunk_171_DO_TESTAMENTO_EM_GERAL.md | 1857–1859 | CAPÍTULO I — DO TESTAMENTO EM GERAL |
| Chunk_172_DA_CAPACIDADE_DE_TESTAR.md | 1860–1861 | CAPÍTULO II — DA CAPACIDADE DE TESTAR |
| Chunk_173_DAS_FORMAS_ORDINARIAS_DO_TESTAMENTO.md | 1862–1880 | CAPÍTULO III — DAS FORMAS ORDINÁRIAS DO TESTAMENTO |
| Chunk_174_DOS_CODICILOS.md | 1881–1885 | CAPÍTULO IV — DOS CODICILOS |
| Chunk_175_DOS_TESTAMENTOS_ESPECIAIS.md | 1886–1896 | CAPÍTULO V — DOS TESTAMENTOS ESPECIAIS |
| Chunk_176_DAS_DISPOSICOES_TESTAMENTARIAS.md | 1897–1911 | CAPÍTULO VI — DAS DISPOSIÇÕES TESTAMENTÁRIAS |
| Chunk_177_DOS_LEGADOS.md | 1912–1940 | CAPÍTULO VII — DOS LEGADOS |
| Chunk_178_DO_DIREITO_DE_ACRESCER_ENTRE_HERDEIROS_E_LEGA.md | 1941–1946 | CAPÍTULO VIII — DO DIREITO DE ACRESCER ENTRE HERDEIROS E LEGATÁRIOS |
| Chunk_179_DAS_SUBSTITUICOES.md | 1947–1960 | CAPÍTULO IX — DAS SUBSTITUIÇÕES |
| Chunk_180_DA_DESERDACAO.md | 1961–1965 | CAPÍTULO X — DA DESERDAÇÃO |
| Chunk_181_DA_REDUCAO_DAS_DISPOSICOES_TESTAMENTARIAS.md | 1966–1968 | CAPÍTULO XI — DA REDUÇÃO DAS DISPOSIÇÕES TESTAMENTÁRIAS |
| Chunk_182_DA_REVOGACAO_DO_TESTAMENTO.md | 1969–1972 | CAPÍTULO XII — DA REVOGAÇÃO DO TESTAMENTO |
| Chunk_183_DO_ROMPIMENTO_DO_TESTAMENTO.md | 1973–1975 | CAPÍTULO XIII — DO ROMPIMENTO DO TESTAMENTO |
| Chunk_184_DO_TESTAMENTEIRO.md | 1976–1990 | CAPÍTULO XIV — DO TESTAMENTEIRO |
| Chunk_185_DO_INVENTARIO.md | 1991–1991 | CAPÍTULO I — DO INVENTÁRIO |
| Chunk_186_DOS_SONEGADOS.md | 1992–1996 | CAPÍTULO II — Dos Sonegados |
| Chunk_187_DO_PAGAMENTO_DAS_DIVIDAS.md | 1997–2001 | CAPÍTULO III — DO PAGAMENTO DAS DÍVIDAS |
| Chunk_188_DA_COLACAO.md | 2002–2012 | CAPÍTULO IV — DA COLAÇÃO |
| Chunk_189_DA_PARTILHA.md | 2013–2022 | CAPÍTULO V — DA PARTILHA |
| Chunk_190_DA_GARANTIA_DOS_QUINHOES_HEREDITARIOS.md | 2023–2026 | CAPÍTULO VI — DA GARANTIA DOS QUINHÕES HEREDITÁRIOS |
| Chunk_191_DA_ANULACAO_DA_PARTILHA.md | 2027–2027 | CAPÍTULO VII — DA ANULAÇÃO DA PARTILHA |
| Chunk_192_DAS_DISPOSICOES_FINAIS_E_TRANSITORIAS.md | 2028–2046 |  |

<!-- MAPA_ATUALIZADO_FIM -->
