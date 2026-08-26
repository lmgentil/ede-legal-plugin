---
name: contestacao
description: >
  Orquestra a elaboração da Contestação institucional (Contestação com
  Reconvenção por irregularidade/fraude em medição de energia elétrica,
  sobre templates/contestacao/modelo-oficial.docx — SPEC-0001). Use ao
  pedir para "gerar a contestação", "preencher o modelo oficial de
  contestação", "montar a contestação da COELBA/EDE neste caso", ou
  equivalente. Esta skill não redige texto nem produz a análise
  estratégica: ela COORDENA — aciona `estrategista-contestacao-ede`,
  `redator-peca-processual-elite` e `humanizer-pt-br` (as três
  OBRIGATÓRIAS, INV-CONTESTACAO-ESTRATEGIA), `calendario-forense-tjba-2026`
  para tempestividade TJBA/2026, o RAG (`rag/search_hybrid.py`) e a
  validação jurídica (`rag/legal_validation/`) para fundamentação
  verificável, e por fim gera o JSON de dados para
  `scripts/render_docx.py`. Diferente de `estrategista-contestacao-ede`
  (só pensa e estrutura) e de `redator-peca-processual-elite` (só redige
  forma) — esta é a única que fecha o ciclo até os 13 placeholders do
  template oficial.
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# Contestação — Skill orquestradora (SPEC-0001 REQ-002)

## 0. Dependências obrigatórias (não substituíveis, não silenciáveis)

- `estrategista-contestacao-ede` — **obrigatória**, executada antes da
  etapa de redação (INV-CONTESTACAO-ESTRATEGIA, SPEC-0001 §5)
- `redator-peca-processual-elite` — **obrigatória** (CLAUDE.md §7)
- `humanizer-pt-br` — **obrigatória** (CLAUDE.md §7)
- `calendario-forense-tjba-2026` — **obrigatória** quando houver
  tempestividade TJBA/2026 (CLAUDE.md §8)

Nenhuma destas quatro é opcional, recomendada ou dispensável a critério do
advogado ou do agente. Ausência ou falha de qualquer uma delas **impede o
pipeline de avançar** para a etapa seguinte — não existe fallback
silencioso que a ignore e siga em frente.

## 1. O que esta skill é e o que ela não é

Você **coordena** o fluxo completo de elaboração da Contestação — não
redige texto, não inventa fundamentação, não decide sozinha a estratégia,
e não duplica internamente o que `estrategista-contestacao-ede`,
`redator-peca-processual-elite` ou `humanizer-pt-br` já fazem. Cada etapa
do pipeline (§3) tem um dono específico; sua função é acioná-lo na ordem
certa, passar o insumo certo, consumir a saída dele, e recusar-se a
avançar quando um insumo obrigatório estiver faltando (Fail Closed —
CLAUDE.md §17).

**Escopo (Fase 7, SPEC-0001, gate de entrada sem pendência — `PEND-001`
reclassificada `DEFERRED` na v0.6.1):** esta skill define, integra E
EXECUTA o pipeline abaixo — extração factual, proveniência,
tempestividade, análise estratégica, RAG, validação jurídica, redator,
humanizer e geração dos 13 valores de placeholder — **até o DOCX final,
contra o caso real**, numa única execução contínua
(INV-CONTESTACAO-ENTREGA-DOCX, §11). Os "Testes Reais" documentados nas
Etapas 5.2 a 5.5 deste arquivo e em `docs/specs/SPEC-0001.md` §§46-53 já
são execuções ponta a ponta desta fase — não é mais um estado futuro.

## 2. Componentes acionados (quem faz o quê)

| Etapa | Componente | Obrigatório? |
|---|---|---|
| Análise estratégica (teses, riscos, matriz de impugnação) | Skill `estrategista-contestacao-ede` | **Obrigatório** — INV-CONTESTACAO-ESTRATEGIA, §4 |
| Decisão de blocos condicionais (INCLUIR/EXCLUIR/INDETERMINADO) | Você, a partir da análise estratégica — `templates/contestacao/blocos.json` | **Obrigatório** — INV-COMPOSICAO-BLOCOS, §4A |
| Composição estrutural dos blocos no DOCX | `scripts/docx_block_engine.py` (mecânica, nunca decide) | Só na Fase 7 |
| Tempestividade TJBA/2026 | Skill `calendario-forense-tjba-2026` | Obrigatório quando aplicável (CLAUDE.md §8) |
| Pesquisa/recuperação jurídica | `rag/search_hybrid.py` (`HybridSearcher`) | Obrigatório para toda fundamentação normativa |
| Validação de citação | `rag/legal_validation/` (`validar_citacao`) | Obrigatório antes de qualquer citação entrar na peça |
| Redação | Skill `redator-peca-processual-elite` | **Obrigatório** (CLAUDE.md §7, SPEC-0001 REQ-003) |
| Humanização | Skill `humanizer-pt-br` | **Obrigatório** (CLAUDE.md §7, SPEC-0001 REQ-004) |
| Proveniência factual | `scripts/validate_fatos.py` | Obrigatório antes de usar um fato na peça |
| Renderização final | `scripts/render_docx.py` (Fase 3, já pronto) | Só na Fase 7 |

## 3. Pipeline (SPEC-0001 REQ-031 + INV-CONTESTACAO-ESTRATEGIA)

```text
documentos do processo
  ↓
1. identificação de documentos relevantes
  ↓
2. extração factual COM PROVENIÊNCIA (§5)
  ↓
3. identificação de pedidos e datas relevantes; tempestividade (§6)
  ↓
4. estrategista-contestacao-ede — OBRIGATÓRIA, sem ela o pipeline PARA (§4)
  ↓
   estrutura defensiva / matriz de impugnação / teses / riscos
  ↓
4A. decisões de blocos condicionais (INCLUIR/EXCLUIR/INDETERMINADO) — §4A
    + estado_processual.json (GRATUIDADE_CONCEDIDA vincula
    PRELIMINAR_REVOGACAO_GRATUIDADE deterministicamente; CORTE_EFETIVO
    condiciona LICITUDE_CORTE_SUSPENSAO — gate fático, decisão continua
    sendo do advogado via AskUserQuestion) + reconvenção via
    AskUserQuestion (SIM/NÃO) — §4A
  ↓
5. RAG jurídico -> validação jurídica de cada citação (§7)
  ↓
6. redator-peca-processual-elite -> humanizer-pt-br (§8)
  ↓
7. geração dos 11 valores de placeholder que a redação produz (§9) —
   NUNCA inclui JUIZO (INV-JUIZO-DATAJUD, abaixo) — Sinopse estritamente
   autoral (INV-SINOPSE-ESTRITAMENTE-AUTORAL), parágrafos ≤380 caracteres
   sem espaços (INV-PARAGRAFO-380)
  ↓
7A. resolução determinística de JUIZO — scripts/datajud_client.py, a
    partir de NUMERO_PROCESSO: DataJud/CNJ (órgão julgador) + IBGE
    (comarca) -> "AO JUÍZO DA ... DA COMARCA DE ...". Fail-closed
    (stage=juizo_datajud) se indisponível/ambíguo/não encontrado, ou se
    a redação tiver fornecido um JUIZO próprio (INV-JUIZO-DATAJUD)
  ↓
8. validação de INV-PARAGRAFO-380 (scripts/validate_paragrafos.py) —
   parágrafo >380 aborta antes do motor documental (stage=paragrafo_380)
  ↓
9. (Fase 7) motor documental (scripts/gerar_contestacao.py: block_composition
   via scripts/docx_block_engine.py, com os gates fáticos de 4A -> renumeração
   dinâmica dos títulos, scripts/docx_numeracao_engine.py, INV-NUMERACAO-
   DINAMICA-CONTESTACAO -> Template Engine, scripts/docx_template_engine.py)
   -> Template Lock composicional -> Contestação
  ↓
10. entrega ao advogado — DOCX final, resposta mínima (§11,
    INV-CONTESTACAO-ENTREGA-DOCX)
```

Não pule etapas para "adiantar" a peça — um pedido da inicial sem resposta,
uma tempestividade sem memória de cálculo, ou uma citação sem validação são
exatamente os buracos que o `estrategista-contestacao-ede` (checklist de
dialeticidade) e o Fail Closed deste projeto existem para prevenir. Em modo
produção (§11), também não pare entre as etapas 4-9 para relatar progresso
ou pedir autorização — elas são internas; a execução só interrompe diante
de decisão humana obrigatória pendente ou fail-closed real (§11).

## 4. Análise estratégica — `estrategista-contestacao-ede` (OBRIGATÓRIA)

**INV-CONTESTACAO-ESTRATEGIA** (SPEC-0001 §5): toda elaboração de
Contestação deverá obrigatoriamente executar a Skill
`estrategista-contestacao-ede` antes da etapa de redação. A Skill
`contestacao` atua como orquestradora e não poderá suprimir, substituir
silenciosamente ou tratar como opcional a etapa estratégica.

Acione `estrategista-contestacao-ede` com os documentos do caso
imediatamente após a extração factual (§5) e a identificação de
pedidos/datas (§6) — **antes** de consultar o RAG e **antes** de acionar o
redator. Ela entrega uma "ANÁLISE ESTRATÉGICA" estruturada (teses, matriz
de impugnação, riscos, documentos — sempre marcando o que não estiver
confirmado como `NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS`; a
Contestação não trabalha com jurisprudência sugerida —
INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL, §7) — é o insumo
principal para as seções V-XIV dessa análise, que por sua vez alimentam os
placeholders de §9.

**Isto não é uma etapa recomendada — é obrigatória, no mesmo grau de
`redator-peca-processual-elite` e `humanizer-pt-br`.** Se a Skill
`estrategista-contestacao-ede` não estiver disponível, falhar, ou for
invocada e não retornar a estrutura esperada (seção 7 do `SKILL.md` dela:
Diagnóstico Executivo até Estrutura da Contestação), **o pipeline não pode
prosseguir para o RAG nem para a redação** — a etapa estratégica não foi
concluída, e isso deve ser reportado explicitamente ao advogado, nunca
contornado silenciosamente com uma análise resumida feita ad-hoc por esta
skill orquestradora ou pelo redator.

**A ANÁLISE ESTRATÉGICA não é a resposta ao advogado** (quando esta Skill
`contestacao` foi acionada para produzir a peça, §11) — é insumo interno,
consumido por você para as etapas seguintes. Não a repasse como se fosse
a entrega solicitada, e não pare a execução aqui.

## 4A. Decisões de blocos condicionais (INV-COMPOSICAO-BLOCOS)

O template institucional tem teses condicionais marcadas estruturalmente
(`<w:sdt>`, catálogo em `templates/contestacao/blocos.json`) — preliminares
(inaplicabilidade do CDC, revogação da gratuidade), dever legal de
fiscalização, desnecessidade de aviso prévio, cálculos de recuperação de
consumo, evolução de consumo, licitude do corte/suspensão, nexo causal
indemonstrado, descabimento de dano moral, e a Reconvenção (que também
governa o título da peça, "CONTESTAÇÃO" vs. "CONTESTAÇÃO COM
RECONVENÇÃO"). **A decisão de incluir ou excluir cada uma dessas teses é
exclusivamente sua, como estrategista** — nunca do motor documental
(`scripts/docx_block_engine.py`), que só executa deterministicamente o que
for decidido aqui e nunca decide por conta própria (nenhuma heurística
jurídica em Python).

Depois de `estrategista-contestacao-ede` (§4) concluída, para cada bloco
folha do catálogo (`decision_mode: "estrategista"` **ou** `"humano"` — ver
RECONVENCAO abaixo), registre um estado —
**apenas um destes três, sem sinônimo, sem booleano, sem número**:

- `INCLUIR` — a tese se aplica ao caso, com fundamento.
- `EXCLUIR` — a tese não se aplica.
- `INDETERMINADO` — falta informação para decidir.

Grave em `decisoes_blocos.json` (mesmo diretório do caso), um objeto por
bloco, com proveniência:

```json
{
  "PRELIMINAR_CDC_INAPLICAVEL": {"decisao": "INCLUIR", "fundamento": "parte autora é pessoa jurídica que usa a energia como insumo produtivo — sem relação de consumo"},
  "RECONVENCAO": {"decisao": "INCLUIR", "fundamento": "advogado respondeu SIM à pergunta obrigatória — há débito de recuperação de consumo (FRA) comprovado e não adimplido"}
}
```

Blocos `CONTAINER_DERIVED` (ex.: `PRELIMINARES`), o inline vinculado
(`INLINE:COM_RECONVENCAO`) e o vinculado a estado processual
(`PRELIMINAR_REVOGACAO_GRATUIDADE`, ver INV-GRATUIDADE-LINKED abaixo)
**nunca recebem decisão manual** — seus estados são derivados
automaticamente pelo motor a partir dos filhos/bloco vinculado/estado
processual (`docx_block_engine.validar_e_resolver_decisoes`); incluí-los
em `decisoes_blocos.json` é erro (`stage=decisao_invalida`).

### INV-RECONVENCAO-AUTORIZACAO-EXPRESSA (Etapa 5.2)

`RECONVENCAO` é `decision_mode: "humano"` no catálogo — não `"estrategista"`
(mudança da Etapa 5.2; o Teste Real 01 mostrou reconvenção inserida sem
autorização expressa do advogado). `estrategista-contestacao-ede` pode
identificar a **possibilidade material** de reconvenção (débito de FRA
comprovado), mas **você, Skill `contestacao`, decide se pergunta e registra
a decisão** — nunca o estrategista sozinho, nunca por inferência da
existência de `VALOR_FRA`/irregularidade/tese favorável. Fluxo obrigatório:

1. Se a análise estratégica indicar possibilidade material de reconvenção,
   pergunte — `AskUserQuestion` — ao advogado: **"Deseja apresentar
   reconvenção neste processo?"** (SIM/NÃO).
2. Resposta **NÃO** → registre `{"decisao": "EXCLUIR", "fundamento":
   "advogado respondeu NÃO à pergunta obrigatória"}`. `INLINE_COM_RECONVENCAO`
   segue automaticamente (linked) — nenhum resíduo "COM RECONVENÇÃO" no
   título.
3. Resposta **SIM** → registre `{"decisao": "INCLUIR", ...}` **somente se**
   as dependências já existentes estiverem satisfeitas (`VALOR_FRA` com
   valor real, não sentinela — `scripts/validate_placeholder_semantics.py`).
4. **Sem resposta** (advogado não respondeu, ou a pergunta não foi feita) →
   não registre decisão nenhuma para `RECONVENCAO` (ou registre
   `INDETERMINADO` se precisar deixar rastro) — o fail-closed já existente
   (`decisao_ausente`/`decisao_indeterminada`) aborta o pipeline
   (`PIPELINE_ABORTED`, `stage=block_composition`). Nunca presuma SIM.

### INV-GRATUIDADE-LINKED (Etapa 5.2, corrigida) — vínculo determinístico, não decisão

**`PRELIMINAR_REVOGACAO_GRATUIDADE` não é decisão sua nem do estrategista
— nunca registre uma entrada para ela em `decisoes_blocos.json`.** No
catálogo, `decision_mode: "state_linked"` com `linked_fact:
"GRATUIDADE_CONCEDIDA"`: o estado do bloco **é** o estado processual,
resolvido inteiramente por `docx_block_engine.py` a partir de
`estado_processual.json` (mesmo diretório do caso; ausente conta como
`{}`):

```json
{
  "GRATUIDADE_CONCEDIDA": {"valor": true, "fonte_documento": "decisao-fls-20.pdf", "pagina": 2}
}
```

Contrato determinístico, sem etapa intermediária de "elegibilidade +
decisão estratégica":

- `GRATUIDADE_CONCEDIDA: true` → `PRELIMINAR_REVOGACAO_GRATUIDADE = INCLUIR`,
  automaticamente.
- `GRATUIDADE_CONCEDIDA` ausente, `false`, ou não confirmada (**mero
  pedido de gratuidade, declaração de hipossuficiência sem decisão, ou
  pedido pendente**) → `EXCLUIR`, automaticamente. Só decisão/ato
  processual inequívoco de concessão conta como `true` — ausência simples
  de informação NUNCA vira ambiguidade, resolve para `false`/`EXCLUIR`.
- `GRATUIDADE_CONCEDIDA: "INDETERMINADO"` (documentos genuinamente
  contraditórios ou insuficientes para determinar se houve concessão) →
  o motor aborta (`PIPELINE_ABORTED`, `stage=block_composition`,
  `decisao_indeterminada`) — pergunte ao advogado antes de prosseguir,
  nunca decida silenciosamente.
- Se, por engano, `decisoes_blocos.json` incluir uma entrada para
  `PRELIMINAR_REVOGACAO_GRATUIDADE`, o motor **rejeita explicitamente**
  (`stage=block_composition`, `decisao_invalida`) — nunca ignora a
  decisão indevida em silêncio, mesmo que ela coincida com o estado real.

Resolva `GRATUIDADE_CONCEDIDA` a partir dos documentos do caso (mesma
disciplina de proveniência de §5) — **nunca por ocorrência lexical**
("requer gratuidade" não vira `GRATUIDADE_CONCEDIDA: true`). Você (e o
estrategista) podem desenvolver o conteúdo/argumentação do bloco quando
ele já estiver presente — mas não decidem se ele existe.

### INV-CORTE-GATE-HUMANO — gate fático + decisão humana (Etapa 5.5, 3ª correção arquitetural)

**`LICITUDE_CORTE_SUSPENSAO` é `decision_mode: "humano"` com
`requires_fact: {"key": "CORTE_EFETIVO"}` no catálogo** — não mais
`state_linked` (a versão anterior, corrigida por este achado do Teste
Real). O corte efetivo comprovado é **condição necessária, mas nunca
suficiente**, para incluir o bloco: mesmo com `CORTE_EFETIVO: true`
confirmado, a inclusão da tese continua sendo **decisão reservada ao
advogado**, nunca automática. Mesma filosofia de controle humano de
`INV-RECONVENCAO-AUTORIZACAO-EXPRESSA` (§ acima), com um gate fático por
cima.

Resolva `CORTE_EFETIVO` a partir dos documentos do caso (mesma
disciplina de proveniência de §5) e registre em
`estado_processual.json`:

```json
{
  "CORTE_EFETIVO": {"valor": true, "fonte_documento": "registro-operacional-concessionaria.pdf"}
}
```

Fluxo obrigatório:

1. `CORTE_EFETIVO` ausente ou `false` → **não pergunte nada** — registre
   `EXCLUIR` (ou simplesmente não registre decisão nenhuma; o motor
   resolve `EXCLUIR` automaticamente pela ausência do gate). Nada a
   decidir sobre uma tese sem suporte fático; não desperdice interação
   humana com uma pergunta cuja resposta já está determinada pelos
   fatos.
2. `CORTE_EFETIVO: "INDETERMINADO"` → o motor aborta
   (`decisao_indeterminada`), com ou sem decisão registrada — pergunte
   ao advogado sobre o **fato** (houve corte efetivo ou não?) antes de
   prosseguir, nunca sobre a inclusão do bloco ainda.
3. `CORTE_EFETIVO: true` **sem** decisão registrada em
   `decisoes_blocos.json` → o motor aborta (`decisao_ausente`) — isso é
   o sinal para você perguntar — `AskUserQuestion` — ao advogado:
   **"Deseja incluir o tópico relativo à licitude do corte/suspensão?"**
   (SIM/NÃO). Nunca gere o DOCX final calado nesse estado.
4. Resposta **SIM** → registre `{"decisao": "INCLUIR", "fundamento": ...}`.
5. Resposta **NÃO** (ou nenhuma resposta obtida) → registre `{"decisao":
   "EXCLUIR", ...}` (ou simplesmente não registre — mesmo efeito: o gate
   já não seria satisfeito para uma decisão ausente, mas registrar
   `EXCLUIR` explicitamente deixa rastro da pergunta feita). Nunca
   presuma SIM.
6. Tentar `INCLUIR` com `CORTE_EFETIVO: false`/ausente → rejeitado
   explicitamente (`gate_fatico_nao_satisfeito`) — o gate protege mesmo
   uma decisão humana mal informada.

**Alegação da autora não é prova de corte efetivo — exceção expressa a
INV-BLOCO-SUPORTE-FATICO (abaixo).** Mera ameaça de corte, aviso de
possível suspensão, pedido preventivo, pedido de restabelecimento
isolado, inadimplência ou débito **NÃO configuram** `CORTE_EFETIVO:
true` — nem isoladamente, nem combinados entre si. `CORTE_EFETIVO: true`
exige evidência que a Ré não contradiga (registro operacional da
concessionária, documento do caso que confirme a suspensão) ou
confirmação expressa do advogado (`AskUserQuestion`, mesmo padrão de
`INV-TEMPESTIVIDADE-MARCO`/`INV-RECONVENCAO-AUTORIZACAO-EXPRESSA`)
quando os documentos não bastarem para confirmar de forma independente
da narrativa da própria autora. Nunca por ocorrência lexical: "não
houve corte" no texto de um documento não vira `CORTE_EFETIVO: true`.
Resolva a partir dos documentos do caso (mesma disciplina de
proveniência de §5). Você (e o estrategista) podem desenvolver o
conteúdo/argumentação do bloco quando ele já estiver presente — mas a
decisão final de incluí-lo, mesmo com o fato comprovado, é sempre do
advogado.

**Histórico da modelagem (2 correções anteriores, ambas superadas):**
(1) `estrategista` + gate `requires_fact` permitia `INCLUIR` sempre que
`CORTE_EFETIVO: true` estivesse confirmado, sem checagem adicional — um
teste real mostrou o bloco entrar com base numa alegação isolada da
própria autora, tratada incorretamente como suporte suficiente. (2)
Corrigido para `state_linked` (vínculo puramente determinístico, sem
decisão alguma) — um teste real seguinte mostrou que isso incluía o
bloco automaticamente sempre que o corte fosse comprovado, sem o
advogado ter manifestado vontade de desenvolver a tese. A modelagem
atual (`humano` + `requires_fact`) combina os dois requisitos: suporte
fático **e** decisão humana, nenhum dos dois dispensa o outro.

### INV-BLOCO-SUPORTE-FATICO (Etapa 5.2) — princípio geral

Nenhum bloco condicional entra na peça só porque existe no catálogo, é
juridicamente possível, é comum nesse tipo de processo, ou o RAG recuperou
legislação relacionada. Para todo bloco decidido por você/estrategista
(não `PRELIMINAR_REVOGACAO_GRATUIDADE`, o único `state_linked` puro
acima — `LICITUDE_CORTE_SUSPENSAO` É decidido por você, com o gate
fático por cima), exija de si mesma um fato/alegação/estado processual
concreto, com proveniência, antes de considerar a tese elegível — só
depois disso a decide como estratégica/humana.
**Exceção expressa: `CORTE_EFETIVO` (que condiciona `LICITUDE_CORTE_
SUSPENSAO` acima) exige padrão mais rigoroso que "alegação basta" —
alegação isolada e não corroborada da autora nunca satisfaz esse estado
específico** (INV-CORTE-GATE-HUMANO acima detalha o porquê: foi
exatamente essa confusão que causou o achado real que motivou a
correção). Para `DESCABIMENTO_DANO_MORAL`, especificamente: só é
elegível se a autora formulou pretensão de dano moral (extraída
estruturalmente dos pedidos, §6 — nunca por busca lexical na petição).
Diferente do vínculo `state_linked` de `PRELIMINAR_REVOGACAO_GRATUIDADE`,
esta é uma invariante **comportamental** (não há validação Python
determinística para "há suporte fático" em geral — seria heurística
jurídica em código, vedada por CLAUDE.md §3/§6) — a disciplina é sua, como
orquestradora, e do estrategista. Quando este bloco é `INCLUIR`, o
placeholder `VALOR_DANO_MORAL_PRETENDIDO` (§5) é obrigatório — extraia o
valor exato pedido na inicial, nunca invente; se a inicial não
quantificar, use uma frase natural de ausência de quantificação ("a ser
arbitrado pelo Juízo"), nunca a sentinela literal; se houver valores
contraditórios ou incerteza sobre qual corresponde ao dano moral,
pergunte ao advogado em vez de escolher automaticamente
(INV-VALOR-DANO-MORAL-DOCUMENTAL, `docs/specs/SPEC-0001.md` §53).

**`INDETERMINADO` nunca chega ao DOCX.** Se, depois de examinar os
documentos e a análise estratégica, um bloco permanecer `INDETERMINADO`
por falta de informação factual **que o advogado pode fornecer**,
pergunte — `AskUserQuestion` — antes de prosseguir. Se a resposta resolver
a dúvida, registre `INCLUIR`/`EXCLUIR` com a justificativa dada pelo
advogado. Se não houver como resolver (nem nos documentos, nem com o
advogado), **não gere a peça**: relate a pendência claramente e pare —
igual ao tratamento de tempestividade sem marco (§6). Nunca infira
silenciosamente um estado a partir de blocos irmãos já decididos, e nunca
normalize `INDETERMINADO` para `EXCLUIR` "para não travar a geração" —
isso seria uma decisão jurídica tomada por omissão, exatamente o que
`INV-COMPOSICAO-BLOCOS` (SPEC-0001 §5) proíbe.

`scripts/gerar_contestacao.py` (etapa `block_composition`,
`scripts/docx_block_engine.py`) valida estruturalmente cada decisão
recebida e aborta (`PIPELINE_ABORTED`) se qualquer bloco estiver ausente,
com estado inválido, ou `INDETERMINADO` — nunca produz DOCX parcial.

## 5. Extração factual com proveniência (REQ-030)

A extração de fatos dos documentos do processo é tarefa sua, como agente —
não existe (nem deveria existir: é compreensão de texto, não determinismo)
um extrator de código para isso. Ao extrair um fato, produza-o neste
formato, sempre com proveniência:

```json
{
  "fact": "A linha foi cancelada em 12/11/2025.",
  "source_document": "documento-x.pdf",
  "page": 4,
  "confidence": 0.99
}
```

`source_document` é obrigatório — nunca declare um fato sem apontar de
qual documento ele veio. Antes de usar a lista de fatos extraídos (e antes
de acionar o estrategista, §4), valide-a estruturalmente:

```bash
python scripts/validate_fatos.py --dados fatos.json
```

Um fato que falhar nessa validação (sem `source_document`, ou com
`confidence`/`page` mal formados) não é utilizável até ser corrigido.
Fatos não comprovados documentalmente (alegação do próprio autor, sem
contraprova) devem ser marcados como tal na Sinopse dos Fatos — nunca
apresentados como fato incontroverso.

**Fato ≠ conhecimento jurídico (CLAUDE.md §11):** fatos vêm exclusivamente
dos documentos do processo ou de informação expressa do advogado. O RAG
nunca é fonte de fato processual — só de fundamento jurídico (§7).

## 6. Pedidos, datas e tempestividade — INV-TEMPESTIVIDADE-MARCO

Identifique todos os pedidos do autor (sem omitir nenhum — a análise do
estrategista, §4, vai exigir isso na matriz de impugnação) e as datas
relevantes extraídas com proveniência (§5).

**INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM (Etapa 5.5 — decisão de produto
fixa e permanente).** Esta Contestação SEMPRE calcula tempestividade
pelo procedimento comum do CPC — prazo de 15 dias, contagem em dias
úteis, art. 335 do CPC. Nunca a lógica do Juizado Especial (Lei
9.099/95), mesmo quando o caso concreto tramitar por rito que admitiria
aplicação subsidiária dessa lei — não pergunte ao advogado qual rito
aplicar, não deixe o estrategista escolher, não escreva
`"fundamento_normativo"` mencionando "9.099"/"Juizado Especial" em
`tempestividade.json` (o pipeline rejeita explicitamente,
`stage=tempestividade`). Se você omitir `prazo_legal_dias`/`tipo_prazo`/
`fundamento_normativo`, o pipeline aplica esse padrão fixo
automaticamente.

**INV-TEMPESTIVIDADE-MARCO** (SPEC-0001 §5, CLAUDE.md §8): nenhuma
Contestação pode alcançar a etapa de redação final/geração do template
sem marco temporal (data da citação, intimação ou publicação) concreto —
documentalmente identificado com proveniência, ou expressamente
informado pelo advogado. `PENDENTE DE VALIDAÇÃO` deixou de ser um estado
terminal aceitável para `TEMPESTIVIDADE_CASO`: é fail-closed rígido, sem
opção de "prosseguir mesmo assim sob responsabilidade do advogado" — o
pipeline (`scripts/gerar_contestacao.py`) impõe isso estruturalmente
(`PIPELINE_ABORTED`, stage `tempestividade`) exatamente como faz para a
etapa estratégica (§4).

Fluxo obrigatório, nesta ordem:

1. **Procure o marco nos documentos do caso primeiro.** Se a data da
   citação, intimação ou publicação estiver inequivocamente documentada
   — sem ambiguidade, sem conflito entre fontes, com prova documental
   suficiente — extraia-a com proveniência (mesmo contrato de §5:
   documento-fonte identificado) e registre em `tempestividade.json`:
   ```json
   {
     "aplicavel": true,
     "data_ciencia": "2026-01-05",
     "marco_origem": "documental",
     "marco_source_document": "certidao-citacao.pdf",
     "marco_page": 1,
     "prazo_legal_dias": 15,
     "tipo_prazo": "uteis",
     "fundamento_normativo": "art. 335, caput, CPC",
     "data_pratica_ato": "..."
   }
   ```
   Com `marco_origem: "documental"` e proveniência registrada, **não
   pergunte novamente ao advogado** — acione
   `calendario-forense-tjba-2026` diretamente com esses dados.

2. **Se o marco estiver ausente, ambíguo, conflitante ou
   insuficientemente comprovado nos documentos**, pergunte
   obrigatoriamente ao advogado — use `AskUserQuestion` (já declarada em
   `allowed-tools` deste `SKILL.md`) com a pergunta:

   > "Qual foi a data da citação, intimação ou publicação relevante para
   > a contagem do prazo?"

   Nunca presuma, nunca invente, nunca deixe o campo vazio "para revisar
   depois" — a pergunta acontece agora, antes de acionar o redator.

3. **Se o advogado responder com uma data concreta**, registre a origem
   e a resposta literal em `tempestividade.json`:
   ```json
   {
     "aplicavel": true,
     "data_ciencia": "2026-01-05",
     "marco_origem": "informado_pelo_advogado",
     "marco_resposta_advogado": "Resposta literal do advogado aqui.",
     "prazo_legal_dias": 15,
     "tipo_prazo": "uteis",
     "fundamento_normativo": "art. 335, caput, CPC",
     "data_pratica_ato": "..."
   }
   ```
   e acione `calendario-forense-tjba-2026` normalmente com essa data.

4. **Se, mesmo após a pergunta, não houver data concreta** (advogado não
   sabe, ainda não localizou a certidão, etc.), **não gere a peça**. Não
   existe opção de prosseguir "sob responsabilidade do advogado" — relate
   isso claramente e aguarde a informação antes de continuar. O pipeline
   abortará (`PIPELINE_ABORTED`, stage `tempestividade`) se
   `tempestividade.json` for gravado sem marco resolvido.

5. **Qualquer outro dado essencial ao cálculo** (prazo legal em dias,
   fundamento normativo, calendário forense verificado) que falte também
   impede a conclusão — o mesmo `PENDENTE DE VALIDAÇÃO` que hoje só
   sinalizava passa a bloquear o pipeline, não só o marco temporal
   especificamente.

Em todos os casos, esta Skill **orquestra** o acionamento do calendário —
não recalcula dias úteis/feriados/suspensões por conta própria
(CLAUDE.md §8); `calendario-forense-tjba-2026` continua sendo o único
mecanismo de cálculo.

**Cálculo e redação são coisas diferentes (Etapa 5.5 §2-§3, achado
real).** O cálculo interno (marco, termo inicial/final, dias úteis,
suspensões, feriados, memória de cálculo) fica em `stages[...]
['memoria_calculo']` — nunca despejado no DOCX. Quando você não fornecer
`TEMPESTIVIDADE_CASO` em `placeholders.json`, `scripts/
gerar_contestacao.py` já gera automaticamente uma redação natural a
partir do resultado do cálculo (ex.: `"A presente Contestação é
tempestiva. Considerado o marco processual ocorrido em [data
DD/MM/AAAA] e a contagem do prazo de 15 (quinze) dias úteis, nos termos
do art. 335 do Código de Processo Civil, o prazo defensivo encerra-se em
[data], razão pela qual a defesa é apresentada tempestivamente."`) —
prefira deixar o campo vazio e usar esse texto automático. Se você
mesma escrever `TEMPESTIVIDADE_CASO`, siga a mesma disciplina: prosa
jurídica curta e institucional, nunca formato de relatório
(`"TEMPESTIVO: termo inicial ..., termo final ..."`), nunca data em
formato ISO (`AAAA-MM-DD` — sempre `DD/MM/AAAA` ou por extenso), nunca
menção a "aplicado subsidiariamente ao rito da Lei 9.099/1995" ou
equivalente, nunca menção a algoritmo/cálculo interno/input/advogado/
sistema/JSON/calendário como ferramenta (mesma proibição de
meta-proveniência de §9). Backstop determinístico em
`scripts/validate_placeholder_semantics.py`
(`_validar_tempestividade_caso`) rejeita qualquer um desses padrões
antes da geração final, independentemente da fonte do valor.

## 7. Questões jurídicas — RAG + validação de citações

Depois que `estrategista-contestacao-ede` (§4) tiver identificado as teses
e teses subsidiárias, para cada fundamento normativo que a análise ou a
redação precisarem citar:

1. Recupere candidatos com `rag/search_hybrid.py`:
   ```python
   from search_hybrid import HybridSearcher
   s = HybridSearcher()
   resultados = s.query("recuperação de consumo por irregularidade no medidor", k=5)
   ```
   O corpus indexado é exclusivamente legislação/regulamentação (CPC, CC,
   CDC, L8987, L9427, REN 1000/2021) — nunca jurisprudência (ver
   INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL abaixo).
2. **Nunca cite um resultado de recuperação diretamente.** Antes de
   qualquer citação entrar na peça, valide-a:
   ```python
   from legal_validation import validar_citacao
   r = validar_citacao("art. 129 da REN ANEEL 1.000/2021")
   ```
   Só use `r["status"] == "VALIDADA"` (ou `PARCIALMENTE_VALIDADA`, com a
   ressalva explícita) como fundamento confirmado. `NAO_VALIDADA`,
   `AMBIGUA` ou `FONTE_INSUFICIENTE` significam: não cite — refaça a
   consulta a `rag/search_hybrid.py` com termos diferentes (o RAG local de
   legislação/regulamentação, nunca ferramenta externa alguma), refaça a
   citação, ou marque a dependência no texto (`estrategista-contestacao-ede`
   §2: `"TESE CONDICIONADA À CONFIRMAÇÃO DOCUMENTAL."`).
3. Jurisprudência (súmula, precedente, entendimento de tribunal) **não
   integra a camada variável desta peça** — decisão arquitetural
   permanente, não uma lacuna temporária de `PEND-002`. A Contestação não
   pesquisa, não solicita ao advogado que pesquise, e não deixa de gerar a
   peça por ausência de jurisprudência. Ver
   INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL abaixo.

### INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL

A Contestação é **autossuficiente e estrita ao modelo institucional**: sua
elaboração não realiza pesquisa jurisprudencial de espécie alguma. Isto
não decorre de `PEND-002` estar aberta — é uma decisão arquitetural da
peça, que **não muda** se/quando `PEND-002` for resolvida (indexar
jurisprudência no RAG é uma decisão sobre a infraestrutura do RAG, não
uma autorização para a Contestação consumi-la). A execução de
`/contestacao`:

- **não** pesquisa jurisprudência (RAG local, web, ou qualquer outro meio);
- **não** aciona Jurisprudências.ai ou nome equivalente;
- **não** aciona MCP de jurisprudência (o plugin não declara nenhum —
  `.claude-plugin/plugin.json`);
- **não** aciona agente ou subagente de jurisprudência;
- **não** usa busca web para jurisprudência;
- **não** usa API jurisprudencial de qualquer espécie;
- **não** consulta tribunal;
- **não** pesquisa precedentes por nenhum caminho, externo ou não;
- **não** solicita automaticamente ao advogado que pesquise jurisprudência;
- **não** interrompe ou bloqueia a geração da peça por ausência de
  jurisprudência.

Isso vale **mesmo que** tal ferramenta esteja disponível no
ambiente/sessão do Claude Code por integração alheia ao plugin (MCP
pessoal do usuário, busca web habilitada, etc.) — disponibilidade não é
autorização de uso. A Contestação parte do conteúdo-base institucional já
existente no modelo oficial, complementado apenas pelos fatos do caso e
pela fundamentação normativa/regulatória validada localmente — nunca por
precedente novo. Súmula/precedente/entendimento jurisprudencial só
aparece na peça onde já estiver preservado no conteúdo-base fixo do
modelo — nunca acrescentado, atualizado, substituído ou expandido durante
a elaboração de um caso.

Ausência de jurisprudência **nunca é lacuna a ser preenchida** — não gere
o marcador `"PESQUISA JURISPRUDENCIAL NECESSÁRIA."` (obsoleto para esta
peça); simplesmente não trabalhe com jurisprudência. Se uma tese só puder
ser sustentada mediante precedente, isso é sinal de deficiência estrutural
do modelo institucional — registre como achado para revisão humana futura
do modelo, nunca como motivo para pesquisar.

Esta etapa mantém a separação fato × direito do §5: o que sai daqui é
conhecimento jurídico verificável (legislação/regulamentação), nunca fato
do processo, e nunca jurisprudência.

## 8. Redação e humanização (obrigatórias)

Com fatos validados (§5), tempestividade resolvida — nunca meramente
sinalizada como pendente, INV-TEMPESTIVIDADE-MARCO (§6) —, a análise
estratégica concluída (§4) e citações validadas (§7) em mãos,
acione `redator-peca-processual-elite` para redigir cada seção com esse
conteúdo — nunca deixe o redator inventar tese, fato ou fundamento; ele
recebe conteúdo definido (pela análise do estrategista e pelos fatos
validados) e produz forma. Em seguida, acione `humanizer-pt-br` sobre o
texto produzido — ela pode ajustar ritmo, conectivos e fluidez, mas não
pode alterar fundamentos, fatos, pedidos, valores, citações, estratégia ou
conclusão jurídica (SPEC-0001 REQ-010).

### INV-CONTESTACAO-SEM-TRAVESSAO — correção pontual pós-teste real

Nenhum conteúdo textual gerado, reescrito, humanizado ou complementado
pela IA para os placeholders da Contestação pode conter o travessão
("—", U+2014) — nem redator, nem humanizer. Use pontuação convencional
(vírgula, ponto, ponto e vírgula, dois-pontos, parênteses); a escolha
depende da estrutura da frase, não é substituição mecânica. A regra é
independente do comportamento das Skills: `scripts/
validate_placeholder_semantics.py` roda um backstop determinístico sobre
todo placeholder fornecido (`_checar_travessao`) antes da geração do
DOCX — qualquer travessão residual aborta o pipeline
(`PIPELINE_ABORTED`, stage `placeholders`), sem substituição automática
por vírgula/hífen (a pontuação correta é decisão do Redator/Humanizer,
não deste validador). Escopo: só o conteúdo variável; o texto fixo
institucional do modelo nunca é tocado por esta regra.

## 9. Geração dos 12 placeholders

### Contexto institucional do modelo — INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA (Etapa 5.7-B)

**Antes** de acionar `redator-peca-processual-elite`, extraia o contexto
institucional real do template para cada placeholder gerativo:

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from docx_context_engine import extrair_contexto_do_template
import json
contexto = extrair_contexto_do_template(
    'templates/contestacao/modelo-oficial.docx',
    'templates/contestacao/blocos.json',
)
print(json.dumps(contexto, ensure_ascii=False, indent=2))
"
```

`scripts/docx_context_engine.py` lê o `modelo-oficial.docx` real (nunca o
altera — extração é SOMENTE LEITURA, mesma disciplina INV-012 do Template
Engine) e devolve, para cada ocorrência física de cada placeholder,
`{"titulo": ..., "antes": ..., "depois": ..., "bloco": ...}` — o
título/subtítulo mais próximo, o texto fixo imediatamente ao redor, e o
bloco condicional ancestral (quando existir). Repasse esse contexto ao
`redator-peca-processual-elite` junto com fatos, estratégia e limites de
redação já existentes — **modelo institucional é a fonte primária da
redação**: PRESERVAR (texto fixo nunca muda) > COMPLEMENTAR (o
placeholder acrescenta o que falta) > CRIAR (só dentro do placeholder).

Isto substitui, como mecanismo PRINCIPAL, a transcrição manual pontual do
texto fixo que hoje só existe para 2-3 placeholders (ex.:
`IRREGULARIDADE_ENCONTRADA`, abaixo) — as citações literais que
permanecem nesta seção continuam válidas como referência histórica/
exemplo, mas o contexto real e completo (13 placeholders) vem da
extração, nunca de memorizar este `SKILL.md`.

Com o contexto em mãos, o Redator segue este raciocínio antes de redigir
cada placeholder:

- **(A)** O texto institucional ao redor já contém esta afirmação? →
  **não repetir**.
- **(B)** O placeholder precisa apenas inserir o dado específico do
  caso? → **inserir somente o dado**.
- **(C)** É necessária contraposição/complementação factual? → **redigir
  somente o conteúdo novo necessário**.
- **(D)** O argumento jurídico já está desenvolvido no texto fixo? →
  **não reescrever a fundamentação** (subsunção, não reexposição —
  reforça `INV-NAO-REDUNDANCIA-NORMATIVA` abaixo).
- **(E)** O conteúdo pretendido pertence semanticamente a outro
  placeholder? → **não inserir** (reforça `INV-NAO-REPETICAO-FATICA`
  abaixo).

`SEM PLACEHOLDER OU ZONA EXPRESSAMENTE AUTORIZADA → SEM ESCRITA
GERATIVA` — os 13 placeholders continuam as únicas zonas de intervenção
textual (nenhuma nova foi criada por esta correção); a única exceção
permanece a renumeração determinística de títulos
(`INV-NUMERACAO-DINAMICA-CONTESTACAO`, §3), que não é escrita gerativa.
`humanizer-pt-br` **nunca** recebe o contexto institucional como conteúdo
a reescrever — só o texto já produzido pelo redator para os placeholders,
exatamente como hoje (§8 acima). Detalhe completo, mecanismo e
diagnóstico em `docs/specs/SPEC-0001.md` §56 (CLAUDE.md §7).

**Etapa 5.7-C — backstop automático (SPEC-0001 §57):** além de você
extrair e repassar o contexto manualmente antes de acionar o redator
(acima), `scripts/gerar_contestacao.py` (Fase 7, §9 mais abaixo) chama
`extrair_contexto_do_template()` automaticamente como PRIMEIRA etapa,
incondicional, de toda geração — nenhum DOCX sai sem essa etapa ter
sucedido primeiro, na mesma execução, contra o template vigente. Isso não
dispensa você de repassar o contexto ao redator durante a conversa (a
etapa automática é um backstop code-level, não substitui o raciocínio
A-E) — mas garante que, mesmo que essa instrução seja esquecida, o
pipeline não produz a peça final sem o contexto ter sido extraído.

Monte um único JSON `{PLACEHOLDER: valor}` (ver
`templates/contestacao/schema.json`) para consumo por
`scripts/render_docx.py` na Fase 7. O template tem 13
placeholders, mas você (redator) só produz 12 — `JUIZO` é resolvido à
parte pela orquestração, nunca por você (INV-JUIZO-DATAJUD, ver linha
abaixo e detalhe mais adiante). Mapeamento de origem de cada campo:

| Placeholder | Vem de |
|---|---|
| `JUIZO` | **Não é conteúdo gerativo** (INV-JUIZO-DATAJUD) — resolvido automaticamente por `scripts/datajud_client.py` a partir de `NUMERO_PROCESSO` (DataJud/CNJ + IBGE); nunca fornecido pelo redator, ver detalhe abaixo |
| `NUMERO_PROCESSO` | Extração factual (§5) |
| `AUTOR` | Extração factual (§5) — **apenas o nome da parte autora, em CAIXA ALTA** (Etapa 5.3 §3). O texto fixo do template já formula a cláusula de qualificação ("já qualificado(a) nos autos") e o CPF, quando aplicável, imediatamente depois do placeholder. Nunca produza `"Fulano de Tal, já qualificado nos autos, portador do CPF nº..."` — a duplicação dessa cláusula já causou quebra de página real, confirmada por diagnóstico forense (isolamento causal: encurtar só o AUTOR eliminou a quebra). Contrato completo em `templates/contestacao/schema.json` (`placeholder_contracts.AUTOR`), verificado automaticamente por `scripts/validate_placeholder_semantics.py` antes da geração final |
| `TEMPESTIVIDADE_CASO` | Tempestividade (§6) — memória de cálculo com marco temporal resolvido (INV-TEMPESTIVIDADE-MARCO); nunca `PENDENTE DE VALIDAÇÃO`. Redija como texto jurídico natural (Etapa 5.3 §5), nunca revelando a mecânica de obtenção do dado — ver "Proibição de meta-informação" abaixo |
| `SINOPSE_FATOS` | Extração factual (§5) + redator/humanizer — **estritamente autoral, INV-SINOPSE-ESTRITAMENTE-AUTORAL (Etapa 5.2)**, compacta e em tempo verbal uniforme (Etapa 5.3 §7-§8), ver detalhe abaixo |
| `REALIDADE_FATICA` | Extração factual (§5) + análise estratégica (§4) + redator/humanizer — contraposição fática GLOBAL e objetiva, sem antecipar o detalhe técnico que pertence a `IRREGULARIDADE_ENCONTRADA`/`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` (INV-NAO-REPETICAO-FATICA, Etapa 5.5), ver detalhe abaixo |
| `IRREGULARIDADE_ENCONTRADA` | Extração factual (TOI/laudo) + análise estratégica (§4) + RAG/validação (§7) + redator/humanizer — contrato ATÔMICO (Etapa 5.3-B §15): EXCLUSIVAMENTE o nome/tipo, em **negrito**, minúsculas/natural (nunca caixa alta forçada), nunca repete o texto fixo do template ao redor do placeholder, nunca menciona assinatura do TOI (§11), ver detalhe abaixo |
| `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` | Análise estratégica (§4) + RAG/validação (§7) + redator/humanizer — foco em SUBSUNÇÃO ao caso concreto, não em reexplicar artigo por artigo o que o modelo já traz (Etapa 5.3 §12-§13); acrescenta o mecanismo técnico concreto, nunca só reafirma o rótulo de `IRREGULARIDADE_ENCONTRADA` com outras palavras (INV-NAO-REPETICAO-FATICA, Etapa 5.5), ver detalhe abaixo |
| `FOTOS_DA_IRREGULARIADE` | Marcador textual de pós-edição manual (ex.: `"[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"`) — decisão V1, `PEND-001` `DEFERRED`; nunca uma legenda da irregularidade (isso é `IRREGULARIDADE_ENCONTRADA`), nem imagem embutida automatizada |
| `VALOR_FRA` | Extração factual — **nunca calculado ou estimado por inferência**; se ausente dos documentos, sinalizar, não inventar |
| `VALOR_DANO_MORAL_PRETENDIDO` | Extração factual da petição inicial — **nunca inventado, estimado, arredondado, ou confundido com valor da causa/dano material/outro pedido econômico** (INV-VALOR-DANO-MORAL-DOCUMENTAL). Só é produzido quando `DESCABIMENTO_DANO_MORAL` está `INCLUIR` (§4 acima). Inicial sem quantificação ("a ser arbitrado pelo Juízo") → frase natural nesse sentido, nunca a sentinela "NÃO ESPECIFICADO"/"NÃO INFORMADO" impressa literalmente. Valores divergentes na inicial (contraditórios, ou incerteza sobre qual corresponde ao dano moral) → não escolha automaticamente maior/menor/último; sinalize a pendência e, se não resolvida pelos documentos, pergunte ao advogado antes de prosseguir. Formato monetário brasileiro (`R$ 10.000,00`) quando há quantia |
| `PEDIDOS_FINAIS` | Análise estratégica (§4) + redator/humanizer — **curto, institucional e conclusivo** (Etapa 5.3 §16-§20), refletindo exatamente os blocos incluídos/excluídos, ver detalhe abaixo |
| `LOCAL_DATA` | **Sempre "Salvador"** + data de elaboração da peça (Etapa 5.3 §21-§22) — nunca a comarca do processo; dado operacional, não jurídico |

Nenhum destes campos pode ser gerado sem que a etapa estratégica (§4) já
tenha sido executada e concluída — a maioria depende diretamente da
saída de `estrategista-contestacao-ede`. Lista com 13 placeholders (foi
12 por um tempo, e antes disso 13 por outro motivo — histórico completo
em `docs/specs/SPEC-0001.md` §49/§53, não repetido aqui):
`ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` foi removido definitivamente
(o modelo oficial já traz a argumentação de evolução de consumo
inteiramente fixa, sem marcador; a IA nunca a gera/parafraseia — bloco
`EVOLUCAO_CONSUMO` continua existindo, sem placeholder próprio); depois
disso, `VALOR_DANO_MORAL_PRETENDIDO` foi acrescentado (inserido
manualmente pelo advogado no template, dentro de `DESCABIMENTO_DANO_
MORAL` — INV-VALOR-DANO-MORAL-DOCUMENTAL, ver §4 e a tabela acima).

Cada placeholder tem um contrato semântico formal (tipo, restrições) em
`templates/contestacao/schema.json` (`placeholder_contracts`) —
`scripts/validate_placeholder_semantics.py` verifica automaticamente
`AUTOR`, `NUMERO_PROCESSO`, `VALOR_FRA`, `VALOR_DANO_MORAL_PRETENDIDO`,
`LOCAL_DATA` e (Etapa 5.2) `SINOPSE_FATOS` antes da geração final;
conteúdo semanticamente
incompatível aborta o pipeline (`PIPELINE_ABORTED`, stage `placeholders`),
nunca chega ao template. O Template Engine, automaticamente e sem ação
desta Skill, marca em vermelho (`FF0000`) todo texto inserido nos
placeholders — regra transversal ao motor documental (não exclusiva da
Contestação); o texto fixo institucional nunca muda de cor.

### INV-SINOPSE-ESTRITAMENTE-AUTORAL (Etapa 5.2)

`SINOPSE_FATOS` tem função **exclusivamente narrativa** — responde só "o
que a parte autora afirma que aconteceu e o que pretende obter
judicialmente?", com fonte primária na petição inicial. Pode conter:
relação jurídica narrada, fatos alegados, evento que originou a demanda,
condutas atribuídas à ré, consequências alegadas, pedidos formulados,
valores pedidos, causa de pedir em síntese. **É proibido** nela: versão
da ré, análise comercial, argumentação defensiva, impugnação, valoração
de prova, ou qualquer formulação do tipo "não comprovou", "não merece
prosperar", "ao contrário do alegado", "os documentos demonstram", "não
há prova", "a cobrança é legítima", "regularidade da atuação" — essas
pertencem a `REALIDADE_FATICA` e aos tópicos de defesa, nunca à Sinopse.
`scripts/validate_placeholder_semantics.py` roda um backstop lexical
sobre um conjunto fechado desses marcadores (rejeita se encontrar — mas a
ausência deles não prova que a Sinopse está correta: texto defensivo bem
escrito passa incólume por esse backstop). **O controle real é seu, como
orquestradora**: ao montar `SINOPSE_FATOS`, releia e confirme que não há
nenhuma palavra de valoração/impugnação, só narrativa + pedidos. Se não
for possível identificar a petição inicial com segurança, não fabrique a
Sinopse — trate como qualquer outra lacuna fática (fail closed/interação).

### INV-NAO-REPETICAO-FATICA (Etapa 5.5, achado do Teste Real)

O mesmo fato técnico (ex. "desvio de energia antes do medidor")
reapareceu quase palavra por palavra em `REALIDADE_FATICA`, na
identificação da irregularidade e no desenvolvimento técnico —
produzindo sensação de texto gerado por IA sem edição. **Um fato não
deve ser reapresentado em vários parágrafos apenas com palavras
diferentes.** Cada placeholder narrativo tem função própria e exclusiva
(ver tabela acima) — nenhum é uma "nova versão" do anterior:
`SINOPSE_FATOS` só a narrativa autoral (acima); `REALIDADE_FATICA`
contraposição global/objetiva, sem antecipar detalhe técnico (exemplo
corrigido: `"A inspeção identificou irregularidade no sistema de
medição, dando origem ao procedimento de recuperação de consumo
documentado nos autos."`); `IRREGULARIDADE_ENCONTRADA` só o rótulo
atômico; `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` acrescenta o mecanismo
técnico concreto (não copia o rótulo); `EVOLUCAO_CONSUMO` só dado
concreto; `PEDIDOS_FINAIS` conclusão processual, sem reencenar fatos.
Dado técnico concreto (código de irregularidade, número do TOI, data da
inspeção, critério de cálculo, período, ciclos, kWh, valor), quando
documentado, distribua racionalmente — um dado, uma função
argumentativa, um local primário, não repetido em múltiplos blocos.

**Presença da titular na inspeção**: mencionar a presença física da
titular (quando documentalmente relevante) não vira automaticamente a
conclusão jurídica de que o contraditório foi "assegurado" — presença
física ≠ conclusão jurídica de contraditório garantido. Preserva-se a
regra já existente: a assinatura do TOI nunca é usada como argumento
defensivo (§11).

Antes de finalizar um parágrafo narrativo, verifique se ele: (A)
apresenta fato novo; (B) desenvolve consequência nova; (C) realiza
subsunção necessária; ou (D) apenas parafraseia informação já dita
noutro placeholder — só (D) exige remoção/reescrita. O problema é
SEMÂNTICO (paráfrase), não mera igualdade textual — não existe (nem
deveria existir) um bloqueador destrutivo de similaridade textual
genérica no código (geraria falsos positivos). **Classificação:
majoritariamente COMPORTAMENTAL, sua e do redator/humanizer, com um
backstop determinístico NARROW**: `scripts/validate_placeholder_
semantics.py` (`_validar_nao_repeticao_realidade_fatica`, não exaustivo)
rejeita quando o rótulo atômico de `IRREGULARIDADE_ENCONTRADA` aparece
verbatim dentro de `REALIDADE_FATICA` — só o sintoma mais grave e
inequívoco; paráfrase com palavras diferentes fica fora do escopo do
código, é controle seu.

### INV-PARAGRAFO-380 / INV-NAO-REDUNDANCIA / INV-NAO-REDUNDANCIA-NORMATIVA (Etapa 5.2)

Ao consumir o texto produzido por `redator-peca-processual-elite` +
`humanizer-pt-br` para os campos multiline (`SINOPSE_FATOS`,
`REALIDADE_FATICA`, `IRREGULARIDADE_ENCONTRADA`,
`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`, `PEDIDOS_FINAIS`,
`TEMPESTIVIDADE_CASO` — `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` removido
definitivamente do projeto, ver §9 acima), confira que cada parágrafo
(separado por `\n` dentro do valor — cada linha lógica vira um `<w:p>`
real no DOCX final, clonando o parágrafo-placeholder — Etapa 5.3-B) tem
no máximo **380 caracteres sem espaços** (contam-se os caracteres efetivos: letras, números e pontuação; espaço, tabulação e quebra interna ficam de fora — ajuste da Etapa 5.8-C.1). `scripts/validate_paragrafos.py`
valida isso estruturalmente antes do motor documental
(`stage=paragrafo_380`, `PIPELINE_ABORTED` se violado) — mas não corta
texto automaticamente: se um parágrafo estourar o limite, devolva ao
redator para decompor o raciocínio em mais parágrafos, nunca resuma o
conteúdo. Cada novo parágrafo deve acrescentar um elemento argumentativo
útil (fato, prova, subsunção, conclusão) — não multiplique parágrafos só
para meter o texto no limite (INV-NAO-REDUNDANCIA, comportamental, sem
validação Python). Igualmente comportamental: não deixe a redação
variável repetir dispositivo normativo já presente no tópico-base fixo do
modelo institucional (INV-NAO-REDUNDANCIA-NORMATIVA) — o RAG (§7) valida/
complementa a fundamentação já existente, não gera lista de artigos para
despejar no texto.

Cada valor final passa pelo mesmo Fail Closed do restante do projeto: se
um placeholder depende de dado ausente, o valor deve dizer isso
explicitamente (`"NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."`, etc.)
— nunca ficar vazio silenciosamente nem ser preenchido por suposição
(jurisprudência não gera sentinela — simplesmente não aparece na peça,
INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL, §7). Exceção:
`TEMPESTIVIDADE_CASO` não admite sentinela de ausência — sem marco
resolvido (§6, INV-TEMPESTIVIDADE-MARCO), o pipeline aborta antes de
chegar aqui. A validação estrutural final (placeholder desconhecido,
placeholder residual) é feita por `scripts/validate_placeholders.py`, já
pronto desde a Fase 3.

### Etapa 5.3 — calibração final (achados do Teste Real 01-B)

Sete achados reais concretos, cada um com correção específica. Todos têm
backstop lexical/estrutural em `scripts/validate_placeholder_semantics.py`
e/ou `scripts/validate_paragrafos.py` (`stage=placeholders`/
`stage=densidade_bloco`, `PIPELINE_ABORTED` se violado) — mas, como
qualquer backstop deste projeto, a ausência de erro reportado NÃO prova
que o conteúdo está correto; o controle real é seu.

**Endereçamento (`JUIZO`) — INV-JUIZO-DATAJUD, correção pontual que
substitui a orientação anterior.** `JUIZO` **deixou de ser conteúdo
gerativo** — você (redator/humanizer) nunca produz esse valor; não o
inclua na saída de placeholders. É resolvido deterministicamente por
`scripts/datajud_client.py`, acionado pela orquestração
(`gerar_contestacao.py`, `stage=juizo_datajud`) a partir de
`NUMERO_PROCESSO`: consulta a API Pública DataJud/CNJ para o órgão
julgador real do processo, resolve a comarca via IBGE
(`codigoMunicipioIBGE`) e monta o padrão institucional `AO JUÍZO DA
[unidade judiciária real] DA COMARCA DE [comarca real]`, tudo em CAIXA
ALTA — nunca um exemplo ilustrativo, sempre o dado retornado pelo
Judiciário. Se `placeholders.json` trouxer um `JUIZO` próprio (por
engano, ou por implementação antiga desta Skill), o pipeline **rejeita a
geração inteira** (`PIPELINE_ABORTED`, `stage=juizo_datajud`) — nunca
usa o valor fornecido, nunca tenta reconciliar. Indisponibilidade do
DataJud, processo não encontrado, múltiplos resultados incompatíveis ou
resposta sem órgão julgador também abortam (fail-closed) — nesse
cenário, informe o advogado de que o juízo precisa ser confirmado
manualmente; você não tenta preencher o valor "para destravar". O nome
do órgão julgador retornado pelo DataJud é fonte de verdade — não
expanda, corrija, reinterprete ou substitua abreviações/nomenclatura
oficial, mesmo que pareça incompleta ou estranha.

**Proibição de meta-informação na peça (achado grave, §4).** O documento
final **jamais** revela sua própria mecânica de obtenção/validação de
dado. Nunca escreva `"conforme informação fornecida pelo advogado"`,
`"conforme informado pelo advogado"`, `"conforme dados fornecidos"`,
`"segundo os documentos enviados"`, `"conforme arquivo analisado"`,
`"de acordo com a análise realizada"`, `"conforme o RAG"`, `"segundo o
sistema"`, ou qualquer referência a prompt/IA/Skill/pipeline/JSON/
extração. A proveniência (`marco_origem`, `source_document` etc.) existe
só para auditoria interna (`fatos.json`, `tempestividade.json`) — nunca é
verbalizada no texto da peça. `TEMPESTIVIDADE_CASO` é o campo onde esse
achado ocorreu de fato: escreva como peça processual normal — "A Ré foi
citada em [data]. Considerando o prazo legal aplicável e a contagem em
dias úteis, a presente defesa é tempestiva." (ou redação institucional
equivalente do modelo) — nunca "a citação foi realizada em [data],
conforme informação processual fornecida pelo advogado".

**Densidade por bloco — 380 é teto, não meta (§6-§8, §30-§31).** Parágrafo
individual ≤380 caracteres não basta: um bloco pode respeitar o teto em
cada parágrafo e ainda ser prolixo por acumulação. `scripts/
validate_paragrafos.py` (`LIMITES_DENSIDADE_BLOCO`) valida também o
total do bloco — `SINOPSE_FATOS`/`REALIDADE_FATICA` ≤3 parágrafos/≤600
caracteres, `IRREGULARIDADE_ENCONTRADA` ≤2/≤600 (na prática, o contrato
atômico da Etapa 5.3-B — ver abaixo — já mantém o campo bem abaixo desse
teto: só o nome do tipo, tipicamente uma linha),
`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` ≤5/≤700, `PEDIDOS_FINAIS` ≤2/≤400
(números calibrados por medição em fixture sintética, não uma amostra
real do Teste Real 01-B — primeira hipótese, a recalibrar com dados do
próximo teste real). Nunca tente preencher 380 caracteres — prefira
parágrafos curtos e funcionais, uma ideia por parágrafo. Evite introdução
retórica, conclusão repetitiva, paráfrase do parágrafo anterior, ou
"enchimento" argumentativo. `SINOPSE_FATOS` especificamente deve ser um
RESUMO de verdade (§8): núcleo da relação jurídica, fato gerador,
principais alegações, consequências afirmadas, pedidos relevantes — nunca
reprodução quase cronológica da inicial. Uniformize o tempo verbal em
presente do indicativo ("alega", "afirma", "sustenta", "requer") ou
pretérito perfeito para fato concluído ("solicitou", "recebeu") — evite
alternância desnecessária (§7).

**Tipo de irregularidade em destaque — contrato ATÔMICO
(`IRREGULARIDADE_ENCONTRADA`, Etapa 5.3-B §14-§18; substitui a orientação
"negrito + caixa alta" da Etapa 5.3 §9, revertida por achado real do
Teste 5.3).** O template oficial já contém, como texto FIXO ao redor do
placeholder, a frase completa: `"Na ocasião, foi constatada
irregularidade do tipo, {{IRREGULARIDADE_ENCONTRADA}}, circunstância que
impedia o registro integral da energia efetivamente consumida na
unidade."` — `IRREGULARIDADE_ENCONTRADA` deve conter **exclusivamente o
nome/tipo da irregularidade**, marcado com `**negrito**` (convenção
markdown do Template Engine — vira `<w:b/>` real, mantendo FF0000), em
minúsculas/redação natural (ressalvados nomes próprios/siglas — nunca
caixa alta forçada no tipo inteiro). Exemplo correto:
`"**desvio de energia antes do sistema de medição**"`. NUNCA repita
"Na ocasião", "foi constatada", "irregularidade do tipo", "circunstância
que" ou "impedia o registro" dentro do valor — isso duplica o texto fixo
do template (bug real confirmado no Teste 5.3, corrigido por backstop
lexical em `scripts/validate_placeholder_semantics.py`
`_validar_irregularidade_encontrada`). A explicação técnica do tipo
(objetiva, específica, sem inventar característica não comprovada) **não
entra neste campo** — vai em `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`,
que o template já renderiza como parágrafo(s) subsequente(s). Não
confunda o TIPO identificado (classificação) com a DESCRIÇÃO FÁTICA
documentada do caso (proveniência factual, §5).

**Assinatura do TOI nunca mencionada (§11).** Nunca escreva "a autora
assinou o TOI", "o TOI foi assinado", "mediante assinatura", "recibo
assinado" ou equivalentes — mesmo que a informação exista nos documentos
do caso (pode permanecer na camada de extração/proveniência interna,
nunca na redação defensiva).

**Modelo fornece o direito — subsunção é seu trabalho (§12-§13).** O
modelo institucional já contém a fundamentação normativa necessária nos
tópicos-base fixos. Nunca reescreva a legislação já estampada no modelo
nem produza sequência tipo "art. 589... art. 590... art. 591..." — isso é
INV-NAO-REDUNDANCIA-NORMATIVA (acima) levada a sério. Em
`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` especialmente, escreva
prioritariamente: o que aconteceu, qual documento comprova, como o
procedimento ocorreu, como o cálculo foi realizado, por que os fatos se
enquadram na tese institucional — não repita o texto do dispositivo.
Prefira `"No caso concreto, a inspeção resultou na emissão do TOI nº
[...], acompanhado dos registros técnicos pertinentes"` a `"O art. 590 da
REN ANEEL 1.000/2021 estabelece..."`.

**RAG normativo — validação, não geração (§14-§15).** `rag/
search_hybrid.py` permanece ativo e obrigatório onde já era — mas
RECUPERAÇÃO ≠ INSERÇÃO, VALIDAÇÃO ≠ REDAÇÃO. Não insira automaticamente
na peça todo artigo que o RAG recuperar; use-o para validar/conferir
coerência normativa e complementar só quando houver lacuna normativa
REAL necessária à tese (mesmo princípio de INV-NAO-REDUNDANCIA-NORMATIVA,
§7 acima). Se o tópico-base já cobre o fundamento, o conteúdo variável
faz subsunção, não nova exposição normativa.

**`PEDIDOS_FINAIS` curto e composicional (§16-§20).** Não é uma segunda
contestação — não rebata de novo, individualmente, cada pedido da inicial
(restabelecimento, cobrança, negativação, multa, dano moral, inversão,
exibição, repetição...); isso pertence à fundamentação, já desenvolvida
nos tópicos correspondentes. O núcleo do mérito é essencialmente "julgar
improcedentes os pedidos da inicial" — sem listá-los de novo. **A seção
deve refletir exatamente os blocos efetivamente incluídos**: nunca
mencione revogação de gratuidade, inaplicabilidade do CDC, ou
reconvenção quando o bloco correspondente estiver `EXCLUIR` —
`scripts/docx_block_engine.py` (`validar_pedidos_composicionais`) valida
isso deterministicamente (`stage=pedidos_composicionais`,
`PIPELINE_ABORTED` se incoerente) antes da composição do DOCX. Não crie
cascata de pedidos subsidiários ("subsidiariamente... subsidiariamente...
subsidiariamente...") por mera cautela retórica — só insira pedido
subsidiário com suporte real no caso.

**Local sempre Salvador (`LOCAL_DATA`, §21-§22).** Independentemente da
comarca do processo — nunca a comarca do processo, sempre "Salvador".
Data é a de elaboração/geração da peça, formato institucional em
português (ex.: `"Salvador/BA, 20 de agosto de 2026."`), sem metadado
técnico.

## 9A. Zonas de Complementação (INV-ZONA-COMPLEMENTACAO, Etapa 5.8-B)

Além dos 13 placeholders, o modelo tem **uma** Zona de Complementação
catalogada — `ZONA_METODOLOGIA_APURACAO`, dentro do bloco
`CALCULOS_RECUPERACAO_CONSUMO` (tópico 3.4). A zona é **normalmente
vazia**: o estado normal da peça é não ter conteúdo nela.

Ela existe porque o tópico 3.4 transcreve os cinco incisos do art. 595 e
afirma aderência a eles "no caso concreto", sem nunca dizer qual inciso
foi aplicado nem qual período foi apurado. A zona conecta essa
fundamentação fixa ao dado documental do processo — nada além disso.

**Zona não é bloco:** você nunca pergunta ao advogado se deve incluí-la
(diferente de Reconvenção e de licitude de corte/suspensão), e ela nunca
entra em `decisoes_blocos.json`. **Zona não é placeholder:** nunca entra
em `placeholders.json` nem em `editable_placeholders`.

### Passo 1 — resolver o estado processual

Acrescente a `estado_processual.json`:

```json
{ "METODOLOGIA_APURACAO_DOCUMENTADA": true }
```

* `true` — os autos contêm memória de cálculo ou memorial de faturamento
  que identifica o critério e o período da apuração;
* `false` ou chave ausente — não contêm. A zona é excluída
  automaticamente, **sem perguntar nada**;
* `"INDETERMINADO"` — documentos contraditórios. O pipeline aborta
  (`stage=zonas`, `zona_indeterminada`) para você resolver com o
  advogado. Nunca presuma.

Resolva isso **a partir dos documentos, com proveniência em
`fatos.json`** — nunca por busca textual, nunca por plausibilidade.

### Passo 2 — teste de necessidade (antes de redigir qualquer coisa)

Na ordem. Qualquer resposta que mande para "zona vazia" encerra o teste:

1. **Algum dos 13 placeholders é o endereço semântico correto disto?**
   Se sim → zona vazia. A zona nunca é atalho para escapar dos limites de
   `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` ou de qualquer outro campo.
2. O texto institucional anterior ou posterior já diz isto
   suficientemente? Se sim → zona vazia.
3. A informação é concreta e documentalmente comprovada? Se não → zona
   vazia.
4. É juridicamente relevante para demonstrar a metodologia do cálculo
   **naquele** processo? Se não → zona vazia.
5. Acrescenta informação efetivamente nova? Se não → zona vazia.

Só com todas autorizando é que o Redator escreve.

### Passo 2A — regra de densidade documental (Etapa 5.8-C)

Autorizado o passo 2, **levante todos os elementos comprovados antes de
redigir**. O primeiro teste real produziu texto pobre porque os dados do
memorial de cálculo existiam nos documentos mas não tinham sido
extraídos para `fatos.json` — o Redator nunca os viu.

Antes de acionar o Redator, confira se `fatos.json` já expõe, como fatos
próprios e com proveniência, o que os documentos trazem:

| Elemento | Onde costuma estar |
|---|---|
| critério/inciso do art. 595 aplicado | memória de cálculo |
| período de apuração e ciclos | memória de cálculo, art. 596 |
| consumo médio apurado | memória de cálculo |
| consumo faturado no período | memória de cálculo |
| diferença por ciclo e total (kWh) | memória de cálculo |
| tarifa aplicada | memória de cálculo |
| valor total apurado | memória de cálculo, fatura |
| histórico de consumo levantado | TOI, histórico |

Um único fato dizendo "foi aplicado o art. 595, III, e apurou-se R$ X"
**não basta** — ele colapsa sete elementos em um e apaga os números que
dão concretude à defesa. Extraia cada elemento separadamente.

A extensão da zona é proporcional ao que está comprovado: **mais
informação comprovada, mais texto; nenhuma informação, zona vazia.**
Nunca o contrário — jamais alongue o texto para parecer robusto.

### Passo 3 — gravar `zonas.json` com proveniência

No diretório do caso, quando e só quando o teste autorizar. Desde a
Etapa 5.8-C a forma estruturada é **obrigatória**:

```json
{
  "ZONA_METODOLOGIA_APURACAO": {
    "conteudo": "primeiro parágrafo\nsegundo parágrafo\nterceiro",
    "fatos": [
      {"tipo": "consumo_medio_apurado", "valor": "612", "unidade": "kWh/ciclo",
       "fonte": "memorial_calculo.pdf", "natureza": "documental"},
      {"tipo": "consumo_faturado", "valor": "210", "unidade": "kWh/ciclo",
       "fonte": "memorial_calculo.pdf", "natureza": "documental"},
      {"tipo": "diferenca_por_ciclo", "valor": "402", "unidade": "kWh/ciclo",
       "fonte": "memorial_calculo.pdf", "natureza": "documental",
       "operacao": {"op": "subtracao",
                    "operandos": ["consumo_medio_apurado", "consumo_faturado"]}},
      {"tipo": "valor_total_apurado", "valor": "4.328,17", "unidade": "R$",
       "fonte": "memorial_calculo.pdf", "natureza": "documental"}
    ]
  }
}
```

Cada dado declara (Etapa 5.8-C.1):

| Campo | O que é |
|---|---|
| `tipo` | identifica o dado; serve de referência de operando |
| `valor` | literal como está no documento ("2.412", "1,7947", "R$ 4.328,17") |
| `unidade` | quando houver: `kWh`, `kWh/ciclo`, `R$`, `R$/kWh`, `ciclo` |
| `fonte` | documento da base do caso (mesma base de `fatos.json`) |
| `natureza` | `documental` (consta do documento) ou `derivado` (resultado de conta) |
| `operacao` | opcional; `{"op": "soma"\|"subtracao"\|"multiplicacao"\|"media", "operandos": [tipo, ...]}` |
| `metodologia` | opcional; `{"descricao", "fonte"}` — ver abaixo |

**Todo número, data e dispositivo que aparecer em `conteudo` precisa
estar em algum `valor`**, e toda `fonte` precisa ser um documento que já
sustenta a peça. Mais: o dado `documental` precisa estar **naquele**
documento — atribuir a tarifa ao TOI quando ela consta da memória de
cálculo aborta o pipeline. O pipeline verifica tudo isso
deterministicamente — é assim que número inventado, ou atribuído à fonte
errada, nunca chega ao DOCX.

### A aritmética é controle de coerência, nunca recálculo da cobrança

A cobrança **já foi constituída** no procedimento administrativo. O
**Memorial de Cálculo** e o **Memorial de Faturamento** são a fonte de
verdade de consumo recuperado, período, ciclos, critério aplicado,
tarifa, diferenças e valor final. A zona existe para **defender a
cobrança efetivamente constituída**, não para reconstruí-la.

**Estimativa regulamentar não é arbitrariedade.** A recuperação de
consumo pode ser apurada por estimativa, desde que segundo os critérios
da regulamentação aplicável. Nunca tente demonstrar que a cobrança
corresponde a uma multiplicação simples reconstruída por você.

Quando o texto reproduz uma relação entre dados, o pipeline confere a
conta em `Decimal` (nunca float para dinheiro) e a unidade por
cancelamento (kWh/ciclo × ciclo = kWh). Três regras:

1. mesmo dado com valores divergentes em documentos oficiais diferentes
   (Memorial de Cálculo × Memorial de Faturamento) → **aborta**: é
   contradição interna real, e a defesa não escolhe um deles;
2. valor apresentado como `derivado` que não fecha → **aborta**: a peça
   estaria afirmando uma conta falsa;
3. valor `documental` que não fecha com a operação reproduzida → o valor
   é **preservado**. Vá ao Memorial de Cálculo/Faturamento e verifique se
   há metodologia, proporcionalização, bandeira, tributo ou arredondamento
   que explique a diferença; se houver, declare
   `"metodologia": {"descricao": ..., "fonte": ...}` no dado e siga. Sem
   essa declaração o pipeline aborta — **nunca troque o valor documental
   por um cálculo seu**.

**Se o documento não apresenta a operação como fórmula, não declare
`operacao`.** É o caminho mais simples e o mais comum: `valor_total_apurado`
no exemplo acima não tem `operacao` porque o memorial registra consumo,
tarifa e valor total em linhas separadas, sem "=" entre eles — a peça não
afirma que a multiplicação produz aquele total, então não há fórmula para
"não fechar". Só declare `operacao` quando o documento realmente escreve
a conta (como faz com "402 kWh/ciclo x 6 ciclos = 2.412 kWh").

### Lógica de redação da zona

```text
DOCUMENTAÇÃO ADMINISTRATIVA
  → CRITÉRIO REGULAMENTAR
  → METODOLOGIA EFETIVAMENTE APLICADA
  → RESULTADO DOCUMENTADO
```

Nunca `DADOS EXTRAÍDOS → RECÁLCULO AUTÔNOMO DA IA → NOVO VALOR`. Atribua
cada número ao documento que o registra ("a memória de cálculo registra /
consigna / aplicou"), jamais como resultado de conta feita pela peça. A
sequência para em RESULTADO DOCUMENTADO — a legitimidade da cobrança é
conclusão do texto institucional adjacente, nunca da zona (Etapa 5.8-E,
"A zona demonstra; o texto institucional conclui" em CLAUDE.md).

Arquivo ausente, chave ausente ou string vazia = zona vazia, e o SDT é
removido sem deixar parágrafo em branco. Texto simples (string não
vazia) é **rejeitado**: conteúdo sem proveniência não entra. E **nunca**
grave sentinela ("NÃO APLICÁVEL", "SEM DADOS", "VAZIO").

Limites do catálogo: **3 parágrafos, 380 caracteres por parágrafo
(sem espaços), 1000 no total (com espaços).** Duas contagens distintas,
deliberadamente: o teto por parágrafo mede texto efetivo; o teto agregado
mede o tamanho bruto da zona.

Conteúdo admissível: critério/inciso do art. 595 aplicado, período de
irregularidade, ciclos, consumos considerados, média apurada, diferença,
tarifa, valor recuperado, base documental da apuração. O objetivo é
**demonstrar como a recuperação foi apurada naquele processo**, não
anunciar que um critério foi usado.

Vedado: repetir a lista dos incisos, reproduzir os arts. 595/596, criar
tese jurídica nova, reencenar a irregularidade (isso é
`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`), repetir `REALIDADE_FATICA`,
inserir jurisprudência, criar título ou subtítulo, começar parágrafo com
numeração ("3.5", "3.4.1"), usar travessão.

**Frases vazias proibidas** — "o procedimento foi regular", "a
concessionária observou a legislação", "a cobrança é legítima", "os
valores estão corretos", "não houve arbitrariedade", "conforme
documentos anexos", "os valores constam do memorial". O texto
institucional já afirma tudo isso. Só podem aparecer acompanhadas do
dado concreto que as justifica; parágrafo que seja só a frase genérica,
sem nenhum número, é rejeitado pelo pipeline.

### Incoerências que abortam

* conteúdo de zona com `CALCULOS_RECUPERACAO_CONSUMO` excluído →
  `zona_incoerente`;
* conteúdo de zona sem `METODOLOGIA_APURACAO_DOCUMENTADA: true` →
  `zona_incoerente`;
* modelo do advogado sem o SDT da zona →
  `modelo_institucional_desatualizado`. Oriente-o a substituir o
  `modelo-oficial.docx` pela versão compatível, fornecida separadamente.
  **Nunca** baixe, reconstrua ou edite o modelo por conta própria.

## 10. O que esta skill nunca faz

Não inventa fato, data, número de processo, valor, dispositivo legal,
súmula, precedente ou conteúdo de decisão (CLAUDE.md §9/§12). **Não
trabalha com jurisprudência de espécie alguma na camada variável** — nem
pesquisa (RAG, web, tribunal, ou qualquer outro meio), nem aciona
ferramenta, agente, subagente ou MCP de jurisprudência (Jurisprudências.ai
ou equivalente), nem solicita ao advogado que pesquise, mesmo disponível
na sessão, mesmo diante de lacuna jurisprudencial, mesmo que `PEND-002`
seja resolvida no futuro (INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL,
§7 — decisão arquitetural permanente, não vinculada a `PEND-002`). Não
insere imagem no
placeholder de foto — decisão V1 (`PEND-001`, `DEFERRED`): o campo recebe
só o marcador textual de pós-edição manual (§9). Não executa o fluxo fim-a-fim
contra um DOCX real nesta fase (Fase 7). **Não avança para o RAG ou para a
redação sem a etapa estratégica de `estrategista-contestacao-ede` ter sido
executada e concluída** — não existe caso "simples" que a dispense; essa
decisão foi revogada (ver CHANGELOG, correção da Fase 6). Não duplica
internamente as funções de `estrategista-contestacao-ede`,
`redator-peca-processual-elite` ou `humanizer-pt-br` — só orquestra e
consome a saída de cada uma. **Não decide sozinha, nem deixa o motor
documental decidir, se uma tese condicional entra ou sai da peça** (§4A) —
essa decisão é sempre da etapa estratégica, nunca de heurística em código
Python. **Não gera o DOCX final enquanto qualquer bloco condicional
permanecer `INDETERMINADO`** — pergunta ao advogado quando resolvível,
relata a pendência e para quando não for. **Não decide reconvenção por
conta própria nem deixa o estrategista decidir sozinho** — sempre
pergunta SIM/NÃO ao advogado (INV-RECONVENCAO-AUTORIZACAO-EXPRESSA, §4A).
**Nem decide, registra ou tenta influenciar a existência de
`PRELIMINAR_REVOGACAO_GRATUIDADE`** — vinculado deterministicamente a
`GRATUIDADE_CONCEDIDA` em `estado_processual.json`, nunca a uma decisão
em `decisoes_blocos.json` (INV-GRATUIDADE-LINKED, §4A). **Já
`LICITUDE_CORTE_SUSPENSAO` é diferente**: `CORTE_EFETIVO` (também em
`estado_processual.json`) só condiciona a *elegibilidade* do bloco —
mesmo com `CORTE_EFETIVO: true` comprovado, a inclusão continua exigindo
pergunta expressa ao advogado (`AskUserQuestion`, INV-CORTE-GATE-HUMANO,
§4A); nunca inclui automaticamente, e nunca gera o DOCX final com
`CORTE_EFETIVO: true` sem essa decisão registrada. Em nenhum dos dois
casos por busca lexical, e a alegação isolada da autora nunca basta para
`CORTE_EFETIVO: true` (INV-CORTE-GATE-HUMANO, §4A).
**Nem produz, aceita ou reconcilia um `JUIZO` fornecido pelo
redator/humanizer** — é resolvido automaticamente via DataJud/CNJ
(`scripts/datajud_client.py`, INV-JUIZO-DATAJUD, §9); qualquer `JUIZO`
presente em `placeholders.json` aborta o pipeline inteiro
(`stage=juizo_datajud`), não é silenciosamente ignorado nem sobrescrito.
**Não deixa parágrafo de
conteúdo variável ultrapassar 380 caracteres sem espaços**
(INV-PARAGRAFO-380, §9)
nem permite que `SINOPSE_FATOS` contenha valoração/impugnação defensiva
(INV-SINOPSE-ESTRITAMENTE-AUTORAL, §9). **Não verbaliza na peça a
mecânica interna de obtenção/validação de um dado** (meta-proveniência —
"conforme informado pelo advogado", "conforme o RAG" etc. — Etapa 5.3
§9). **Não menciona se o TOI foi ou não assinado** (Etapa 5.3 §9). **Não
deixa `PEDIDOS_FINAIS` reintroduzir tese/bloco excluído pelo motor
composicional** nem produz endereçamento fora do padrão institucional ou
`LOCAL_DATA` fora de Salvador (Etapa 5.3 §9).

## 11. Modo de operação e entrega final da resposta — INV-CONTESTACAO-ENTREGA-DOCX (Etapa 5.6)

Achado real (Teste Real, Etapa 5.6): a execução concluiu corretamente a
análise estratégica (§4) e encerrou a resposta entregando-a ao advogado,
informando que os próximos passos seriam RAG, Redator e Humanizer. Isso é
incorreto — o objetivo operacional do plugin é produção da peça, não
condução manual das etapas internas pelo advogado. Causa raiz: a Skill
`estrategista-contestacao-ede` (`SKILL.md` §9, antes da correção) instruía
entregar a análise como artefato final e sugerir o próximo passo sempre
que concluída, sem distinguir se havia sido acionada por esta orquestradora
ou diretamente pelo usuário — corrigido lá (mesma Etapa 5.6): agora ela só
entrega a análise como resposta final quando acionada diretamente. Esta
seção formaliza o lado da orquestração.

### Modos de operação — não confunda

Antes de iniciar o pipeline, identifique a intenção do pedido:

| Pedido do advogado (exemplos) | Modo | Saída obrigatória |
|---|---|---|
| "elabore/gere/faça/produza a contestação", "preencha o modelo oficial", "monte a contestação deste caso" | **PRODUÇÃO** | DOCX final (este §11) |
| "analise este processo", "faça só a estratégia", "não gere a contestação ainda" | **ANÁLISE** | análise estratégica é a entrega final (`estrategista-contestacao-ede` acionada diretamente, fora desta orquestração) |
| "quais teses cabem nesse caso?", "recuperação de consumo é sustentável aqui?" | **CONSULTIVO** | resposta pontual, sem acionar o pipeline completo |
| instrução explícita de teste do pipeline | **TESTE** | conforme a instrução específica do teste |

Esta seção (§11) rege apenas o **MODO PRODUÇÃO**. Nos modos ANÁLISE e
CONSULTIVO, a entrega intermediária É a resposta correta — não force o
pipeline completo nem gere DOCX quando o advogado não pediu a peça.

### Em modo produção: execução contínua, sem checkpoint por etapa interna

Análise estratégica (§4), decisões de blocos (§4A), RAG (§7), redator e
humanizer (§8), validações e composição (§9) são **etapas internas do
mesmo fluxo** — nenhuma delas é resposta final ao advogado, e nenhuma
delas encerra a execução. Ao concluir cada etapa interna, continue
automaticamente para a próxima, sem perguntar se deve prosseguir e sem
frases do tipo "próximo passo recomendado...", "agora devemos seguir
para...", "posso gerar a Contestação...", "se quiser, prossigo para o
DOCX...". O pedido inicial do advogado ("elabore a Contestação") já é a
autorização para o pipeline inteiro — pedir essa autorização de novo, a
cada etapa, é o próprio defeito que esta seção corrige.

Isso vale igualmente para o RAG (§7): acionar `rag/search_hybrid.py` e a
validação de citações é automático quando previsto, nunca um checkpoint
("deseja que eu prossiga para o RAG?") nem uma entrega intermediária
("resultado do RAG: ..."). Preserva-se integralmente
INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL (§7) — execução contínua não
é licença para pesquisar jurisprudência.

### Única hipótese normal de interrupção: decisão humana obrigatória pendente

O pipeline só pode parar antes do DOCX quando existir uma decisão humana
que este `SKILL.md` já exige (§4A) e que ainda não foi respondida:

- Reconvenção elegível, sem resposta ainda — pergunte SOMENTE
  Reconvenção (`AskUserQuestion`, INV-RECONVENCAO-AUTORIZACAO-EXPRESSA).
- `CORTE_EFETIVO: true` sem decisão registrada — pergunte SOMENTE sobre
  incluir o tópico de corte/suspensão (INV-CORTE-GATE-HUMANO).

Se o advogado já respondeu a uma dessas perguntas no pedido inicial (ex.:
"elabore a contestação, sem reconvenção"), registre a decisão a partir
dessa resposta e **não pergunte de novo**. Pergunte apenas a(s) decisão(ões)
efetivamente pendente(s) — nunca as duas por hábito quando só uma está em
aberto.

Interrupção também é legítima diante de fail-closed técnico/fático real já
previsto em outras seções deste documento — fato essencial `INDETERMINADO`
(§4A), tempestividade sem marco (§6, INV-TEMPESTIVIDADE-MARCO), DataJud
incapaz de resolver `JUIZO` (§9), valor contraditório não resolvível
documentalmente (§9), ou documento indispensável ilegível. Nesses casos,
pergunte somente o dado necessário para destravar o pipeline; recebida a
resposta, **retome automaticamente e siga até o DOCX** — não volte a
entregar a análise estratégica nem qualquer outro artefato interno como se
fosse a resposta final.

Fora dessas hipóteses (decisão humana obrigatória pendente, ou fail-closed
técnico/fático real), nenhuma etapa interna concluída — estratégia, RAG,
decisões automáticas de blocos, redator, humanizer, validações — encerra a
execução nem gera pergunta ao advogado.

### Resposta final ao advogado (sucesso)

Em modo produção, a resposta final é mínima: o DOCX gerado, mais,
opcionalmente, uma nota breve (blocos que exigiram decisão humana e a
decisão registrada; alerta relevante, se houver). Não despeje análise
estratégica, saída do RAG, rascunho do redator, relatório de validação ou
memória de cálculo de tempestividade junto com a peça — esses artefatos
existem para auditoria interna do pipeline (§5, §6, §9), não para compor a
resposta ao advogado.

### Escopo desta correção

Esta seção corrige exclusivamente orquestração e entrega — não recalibra
redação, template, placeholders, blocos, RAG, tempestividade, DataJud,
limite de 380 caracteres, dano moral, corte ou Reconvenção (essas regras
permanecem como já definidas nas seções anteriores deste documento).
