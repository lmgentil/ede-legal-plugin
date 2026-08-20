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
5. RAG jurídico -> validação jurídica de cada citação (§7)
  ↓
6. redator-peca-processual-elite -> humanizer-pt-br (§8)
  ↓
7. geração dos 13 valores de placeholder (§9)
  ↓
8. (Fase 7) Template Engine (scripts/render_docx.py) -> Template Lock -> Contestação
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
de impugnação, riscos, documentos, jurisprudência sugerida — sempre
marcando o que não estiver confirmado como `NÃO INFORMADO NOS ELEMENTOS
DISPONIBILIZADOS` ou `PESQUISA JURISPRUDENCIAL NECESSÁRIA`) — é o insumo
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
2. **Nunca cite um resultado de recuperação diretamente.** Antes de
   qualquer citação entrar na peça, valide-a:
   ```python
   from legal_validation import validar_citacao
   r = validar_citacao("art. 129 da REN ANEEL 1.000/2021")
   ```
   Só use `r["status"] == "VALIDADA"` (ou `PARCIALMENTE_VALIDADA`, com a
   ressalva explícita) como fundamento confirmado. `NAO_VALIDADA`,
   `AMBIGUA` ou `FONTE_INSUFICIENTE` significam: não cite — pesquise de
   novo, refaça a citação, ou marque a dependência no texto (ver
   `estrategista-contestacao-ede` §2: `"TESE CONDICIONADA À CONFIRMAÇÃO
   DOCUMENTAL."`/`"PESQUISA JURISPRUDENCIAL NECESSÁRIA."`).
3. Jurisprudência real (`rag/jurisprudencia/`) **não está indexada** nesta
   fase (`PEND-002`) — não a use como fonte automatizada. Uma citação
   jurisprudencial só pode vir de confirmação manual do advogado ou de
   pesquisa externa explícita, nunca do RAG atual.

Esta etapa mantém a separação fato × direito do §5: o que sai daqui é
conhecimento jurídico verificável, nunca fato do processo.

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

## 9. Geração dos 13 placeholders

Monte um único JSON `{PLACEHOLDER: valor}` (ver
`templates/contestacao/schema.json`) para consumo por
`scripts/render_docx.py` na Fase 7. Mapeamento de origem de cada campo:

| Placeholder | Vem de |
|---|---|
| `JUIZO` | Extração factual (§5) — documento processual |
| `NUMERO_PROCESSO` | Extração factual (§5) |
| `AUTOR` | Extração factual (§5) |
| `TEMPESTIVIDADE_CASO` | Tempestividade (§6) — memória de cálculo com marco temporal resolvido (INV-TEMPESTIVIDADE-MARCO); nunca `PENDENTE DE VALIDAÇÃO` |
| `SINOPSE_FATOS` | Extração factual (§5) + redator/humanizer |
| `REALIDADE_FATICA` | Extração factual (§5) + análise estratégica (§4) + redator/humanizer |
| `IRREGULARIDADE_ENCONTRADA` | Extração factual (TOI/laudo) + análise estratégica (§4) + RAG/validação (§7) + redator/humanizer |
| `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` | Análise estratégica (§4, análise artigo-por-artigo REN 1.000/2021) + RAG/validação (§7) + redator/humanizer |
| `FOTOS_DA_IRREGULARIADE` | Marcador textual de pós-edição manual (ex.: `"[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"`) — decisão V1, `PEND-001` `DEFERRED`; nunca uma legenda da irregularidade (isso é `IRREGULARIDADE_ENCONTRADA`), nem imagem embutida automatizada |
| `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` | Extração factual (histórico de consumo) + análise estratégica (§4) + redator/humanizer |
| `VALOR_FRA` | Extração factual — **nunca calculado ou estimado por inferência**; se ausente dos documentos, sinalizar, não inventar |
| `PEDIDOS_FINAIS` | Análise estratégica (§4, impugnação dos pedidos + teses subsidiárias) + redator/humanizer |
| `LOCAL_DATA` | Local padrão do escritório + data de assinatura (dado operacional, não jurídico) |

Nenhum destes campos pode ser gerado sem que a etapa estratégica (§4) já
tenha sido executada e concluída — sete dos treze dependem diretamente da
saída de `estrategista-contestacao-ede`.

Cada valor final passa pelo mesmo Fail Closed do restante do projeto: se
um placeholder depende de dado ausente, o valor deve dizer isso
explicitamente (`"NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."`,
`"PESQUISA JURISPRUDENCIAL NECESSÁRIA."`, etc.) — nunca ficar vazio
silenciosamente nem ser preenchido por suposição. Exceção:
`TEMPESTIVIDADE_CASO` não admite sentinela de ausência — sem marco
resolvido (§6, INV-TEMPESTIVIDADE-MARCO), o pipeline aborta antes de
chegar aqui. A validação estrutural final (placeholder desconhecido,
placeholder residual) é feita por `scripts/validate_placeholders.py`, já
pronto desde a Fase 3.

## 10. O que esta skill nunca faz

Não inventa fato, data, número de processo, valor, dispositivo legal,
súmula, precedente ou conteúdo de decisão (CLAUDE.md §9/§12). Não usa
jurisprudência real do RAG (`PEND-002`, ausente). Não insere imagem no
placeholder de foto — decisão V1 (`PEND-001`, `DEFERRED`): o campo recebe
só o marcador textual de pós-edição manual (§9). Não executa o fluxo fim-a-fim
contra um DOCX real nesta fase (Fase 7). **Não avança para o RAG ou para a
redação sem a etapa estratégica de `estrategista-contestacao-ede` ter sido
executada e concluída** — não existe caso "simples" que a dispense; essa
decisão foi revogada (ver CHANGELOG, correção da Fase 6). Não duplica
internamente as funções de `estrategista-contestacao-ede`,
`redator-peca-processual-elite` ou `humanizer-pt-br` — só orquestra e
consome a saída de cada uma.
