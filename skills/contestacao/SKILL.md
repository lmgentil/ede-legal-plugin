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

**Escopo desta fase (Fase 6, SPEC-0001):** esta skill define e integra
todo o pipeline abaixo — extração factual, proveniência, tempestividade,
análise estratégica, RAG, validação jurídica, redator, humanizer e geração
dos 13 valores de placeholder. **Ela não executa aqui, contra um caso
real, o fluxo fim-a-fim até o DOCX final** — isso é objeto da Fase 7
(End-to-End). `PEND-001` (suporte a imagem no placeholder
`FOTOS_DA_IRREGULARIADE` — ver `docs/PENDENCIAS.md`) foi reclassificada
como `DEFERRED` (correção v0.6.1): a V1 não automatiza inserção de
imagem, então não bloqueia mais o início da Fase 7. Quando a Fase 7 for
autorizada, esta skill já está pronta para ser exercida ponta a ponta.

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
    vincula LICITUDE_CORTE_SUSPENSAO deterministicamente — mesmo
    mecanismo) + reconvenção via AskUserQuestion (SIM/NÃO) — §4A
  ↓
5. RAG jurídico -> validação jurídica de cada citação (§7)
  ↓
6. redator-peca-processual-elite -> humanizer-pt-br (§8)
  ↓
7. geração dos 11 valores de placeholder que a redação produz (§9) —
   NUNCA inclui JUIZO (INV-JUIZO-DATAJUD, abaixo) — Sinopse estritamente
   autoral (INV-SINOPSE-ESTRITAMENTE-AUTORAL), parágrafos ≤380 caracteres
   (INV-PARAGRAFO-380)
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
   via scripts/docx_block_engine.py, com os gates fáticos de 4A -> Template
   Engine, scripts/docx_template_engine.py) -> Template Lock composicional
   -> Contestação
```

Não pule etapas para "adiantar" a peça — um pedido da inicial sem resposta,
uma tempestividade sem memória de cálculo, ou uma citação sem validação são
exatamente os buracos que o `estrategista-contestacao-ede` (checklist de
dialeticidade) e o Fail Closed deste projeto existem para prevenir.

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

### INV-CORTE-LINKED — vínculo determinístico, não decisão (correção arquitetural)

**`LICITUDE_CORTE_SUSPENSAO` não é decisão sua nem do estrategista —
nunca registre uma entrada para ela em `decisoes_blocos.json`.** Mesma
arquitetura de `PRELIMINAR_REVOGACAO_GRATUIDADE` logo acima:
`decision_mode: "state_linked"` com `linked_fact: "CORTE_EFETIVO"` no
catálogo — o estado do bloco **é** o estado processual, resolvido
inteiramente por `docx_block_engine.py` a partir de
`estado_processual.json`:

```json
{
  "CORTE_EFETIVO": {"valor": true, "fonte_documento": "registro-operacional-concessionaria.pdf"}
}
```

- `CORTE_EFETIVO: true` → `LICITUDE_CORTE_SUSPENSAO = INCLUIR`,
  automaticamente.
- `CORTE_EFETIVO` ausente ou `false` → `EXCLUIR`, automaticamente.
- `CORTE_EFETIVO: "INDETERMINADO"` → o motor aborta
  (`decisao_indeterminada`) — pergunte ao advogado antes de prosseguir.
- Entrada indevida em `decisoes_blocos.json` para este bloco → rejeitada
  explicitamente (`decisao_invalida`), mesmo coincidindo com o fato real.

**Correção arquitetural (achado real):** a modelagem anterior (gate
`requires_fact` + decisão estratégica) permitia registrar `INCLUIR`
sempre que `CORTE_EFETIVO: true` estivesse confirmado — e, num teste
real, o bloco entrou com base numa **alegação da própria autora na
petição inicial**, tratada incorretamente como suporte suficiente.
Corrigido para `state_linked`: não há mais "elegibilidade + decisão", só
vínculo direto.

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
conteúdo/argumentação do bloco quando ele já estiver presente — mas não
decidem se ele existe.

### INV-BLOCO-SUPORTE-FATICO (Etapa 5.2) — princípio geral

Nenhum bloco condicional entra na peça só porque existe no catálogo, é
juridicamente possível, é comum nesse tipo de processo, ou o RAG recuperou
legislação relacionada. Para todo bloco decidido por você/estrategista
(não os dois `state_linked` acima), exija de si mesma um
fato/alegação/estado processual concreto, com proveniência, antes de
considerar a tese elegível — só depois disso a decide como estratégica.
**Exceção expressa: `CORTE_EFETIVO` (que alimenta `LICITUDE_CORTE_
SUSPENSAO` acima) exige padrão mais rigoroso que "alegação basta" —
alegação isolada e não corroborada da autora nunca satisfaz esse estado
específico** (INV-CORTE-LINKED acima detalha o porquê: foi exatamente
essa confusão que causou o achado real que motivou a correção). Para
`DESCABIMENTO_DANO_MORAL`, especificamente: só é elegível se a autora
formulou pretensão de dano moral (extraída estruturalmente dos pedidos,
§6 — nunca por busca lexical na petição). Diferente dos dois vínculos
`state_linked` acima, esta é uma invariante **comportamental** (não há
validação Python determinística para "há suporte fático" em geral —
seria heurística jurídica em código, vedada por CLAUDE.md §3/§6) — a
disciplina é sua, como
orquestradora, e do estrategista.

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

Monte um único JSON `{PLACEHOLDER: valor}` (ver
`templates/contestacao/schema.json`) para consumo por
`scripts/render_docx.py` na Fase 7. O template ainda tem 12
placeholders, mas você (redator) só produz 11 — `JUIZO` é resolvido à
parte pela orquestração, nunca por você (INV-JUIZO-DATAJUD, ver linha
abaixo e detalhe mais adiante). Mapeamento de origem de cada campo:

| Placeholder | Vem de |
|---|---|
| `JUIZO` | **Não é conteúdo gerativo** (INV-JUIZO-DATAJUD) — resolvido automaticamente por `scripts/datajud_client.py` a partir de `NUMERO_PROCESSO` (DataJud/CNJ + IBGE); nunca fornecido pelo redator, ver detalhe abaixo |
| `NUMERO_PROCESSO` | Extração factual (§5) |
| `AUTOR` | Extração factual (§5) — **apenas o nome da parte autora, em CAIXA ALTA** (Etapa 5.3 §3). O texto fixo do template já formula a cláusula de qualificação ("já qualificado(a) nos autos") e o CPF, quando aplicável, imediatamente depois do placeholder. Nunca produza `"Fulano de Tal, já qualificado nos autos, portador do CPF nº..."` — a duplicação dessa cláusula já causou quebra de página real, confirmada por diagnóstico forense (isolamento causal: encurtar só o AUTOR eliminou a quebra). Contrato completo em `templates/contestacao/schema.json` (`placeholder_contracts.AUTOR`), verificado automaticamente por `scripts/validate_placeholder_semantics.py` antes da geração final |
| `TEMPESTIVIDADE_CASO` | Tempestividade (§6) — memória de cálculo com marco temporal resolvido (INV-TEMPESTIVIDADE-MARCO); nunca `PENDENTE DE VALIDAÇÃO`. Redija como texto jurídico natural (Etapa 5.3 §5), nunca revelando a mecânica de obtenção do dado — ver "Proibição de meta-informação" abaixo |
| `SINOPSE_FATOS` | Extração factual (§5) + redator/humanizer — **estritamente autoral, INV-SINOPSE-ESTRITAMENTE-AUTORAL (Etapa 5.2)**, compacta e em tempo verbal uniforme (Etapa 5.3 §7-§8), ver detalhe abaixo |
| `REALIDADE_FATICA` | Extração factual (§5) + análise estratégica (§4) + redator/humanizer |
| `IRREGULARIDADE_ENCONTRADA` | Extração factual (TOI/laudo) + análise estratégica (§4) + RAG/validação (§7) + redator/humanizer — contrato ATÔMICO (Etapa 5.3-B §15): EXCLUSIVAMENTE o nome/tipo, em **negrito**, minúsculas/natural (nunca caixa alta forçada), nunca repete o texto fixo do template ao redor do placeholder, nunca menciona assinatura do TOI (§11), ver detalhe abaixo |
| `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` | Análise estratégica (§4) + RAG/validação (§7) + redator/humanizer — foco em SUBSUNÇÃO ao caso concreto, não em reexplicar artigo por artigo o que o modelo já traz (Etapa 5.3 §12-§13), ver detalhe abaixo |
| `FOTOS_DA_IRREGULARIADE` | Marcador textual de pós-edição manual (ex.: `"[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"`) — decisão V1, `PEND-001` `DEFERRED`; nunca uma legenda da irregularidade (isso é `IRREGULARIDADE_ENCONTRADA`), nem imagem embutida automatizada |
| `VALOR_FRA` | Extração factual — **nunca calculado ou estimado por inferência**; se ausente dos documentos, sinalizar, não inventar |
| `PEDIDOS_FINAIS` | Análise estratégica (§4) + redator/humanizer — **curto, institucional e conclusivo** (Etapa 5.3 §16-§20), refletindo exatamente os blocos incluídos/excluídos, ver detalhe abaixo |
| `LOCAL_DATA` | **Sempre "Salvador"** + data de elaboração da peça (Etapa 5.3 §21-§22) — nunca a comarca do processo; dado operacional, não jurídico |

Nenhum destes campos pode ser gerado sem que a etapa estratégica (§4) já
tenha sido executada e concluída — a maioria depende diretamente da
saída de `estrategista-contestacao-ede`. Lista com 12 placeholders (era
13 — `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` removido definitivamente:
o modelo oficial já traz a argumentação de evolução de consumo
inteiramente fixa, sem marcador; a IA nunca a gera/parafraseia. Bloco
`EVOLUCAO_CONSUMO` (catálogo de composição) continua existindo, agora
sem placeholder próprio — só decisão INCLUIR/EXCLUIR da etapa
estratégica, sem preenchimento algum. Ver `docs/specs/SPEC-0001.md` §49).

Cada placeholder tem um contrato semântico formal (tipo, restrições) em
`templates/contestacao/schema.json` (`placeholder_contracts`) —
`scripts/validate_placeholder_semantics.py` verifica automaticamente
`AUTOR`, `NUMERO_PROCESSO`, `VALOR_FRA`, `LOCAL_DATA` e (Etapa 5.2)
`SINOPSE_FATOS` antes da geração final; conteúdo semanticamente
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

### INV-PARAGRAFO-380 / INV-NAO-REDUNDANCIA / INV-NAO-REDUNDANCIA-NORMATIVA (Etapa 5.2)

Ao consumir o texto produzido por `redator-peca-processual-elite` +
`humanizer-pt-br` para os campos multiline (`SINOPSE_FATOS`,
`REALIDADE_FATICA`, `IRREGULARIDADE_ENCONTRADA`,
`DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`, `PEDIDOS_FINAIS`,
`TEMPESTIVIDADE_CASO` — `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` removido
definitivamente do projeto, ver §9 acima), confira que cada parágrafo
(separado por `\n` dentro do valor — cada linha lógica vira um `<w:p>`
real no DOCX final, clonando o parágrafo-placeholder — Etapa 5.3-B) tem
no máximo **380 caracteres com espaços**. `scripts/validate_paragrafos.py`
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
`LICITUDE_CORTE_SUSPENSAO` nem de `PRELIMINAR_REVOGACAO_GRATUIDADE`** —
ambos os blocos são vinculados deterministicamente a `CORTE_EFETIVO`/
`GRATUIDADE_CONCEDIDA` em `estado_processual.json`, nunca a uma decisão
em `decisoes_blocos.json` (INV-CORTE-LINKED/INV-GRATUIDADE-LINKED, §4A)
— em nenhum dos dois casos por busca lexical, e a alegação isolada da
autora nunca basta para `CORTE_EFETIVO: true` (INV-CORTE-LINKED, §4A).
**Nem produz, aceita ou reconcilia um `JUIZO` fornecido pelo
redator/humanizer** — é resolvido automaticamente via DataJud/CNJ
(`scripts/datajud_client.py`, INV-JUIZO-DATAJUD, §9); qualquer `JUIZO`
presente em `placeholders.json` aborta o pipeline inteiro
(`stage=juizo_datajud`), não é silenciosamente ignorado nem sobrescrito.
**Não deixa parágrafo de
conteúdo variável ultrapassar 380 caracteres** (INV-PARAGRAFO-380, §9)
nem permite que `SINOPSE_FATOS` contenha valoração/impugnação defensiva
(INV-SINOPSE-ESTRITAMENTE-AUTORAL, §9). **Não verbaliza na peça a
mecânica interna de obtenção/validação de um dado** (meta-proveniência —
"conforme informado pelo advogado", "conforme o RAG" etc. — Etapa 5.3
§9). **Não menciona se o TOI foi ou não assinado** (Etapa 5.3 §9). **Não
deixa `PEDIDOS_FINAIS` reintroduzir tese/bloco excluído pelo motor
composicional** nem produz endereçamento fora do padrão institucional ou
`LOCAL_DATA` fora de Salvador (Etapa 5.3 §9).
