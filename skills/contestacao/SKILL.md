---
name: contestacao
description: >
  Orquestra a elaboração da Contestação institucional (Contestação com
  Reconvenção por irregularidade/fraude em medição de energia elétrica,
  sobre templates/contestacao/modelo-oficial.docx — SPEC-0001). Use ao
  pedir para "gerar a contestação", "preencher o modelo oficial de
  contestação", "montar a contestação da COELBA/EDE neste caso", ou
  equivalente. Esta skill não redige texto nem produz a análise
  estratégica: ela COORDENA — aciona `estrategista-contestacao-ede` para a
  análise, `redator-peca-processual-elite` e `humanizer-pt-br`
  (obrigatórias) para o texto, `calendario-forense-tjba-2026` para
  tempestividade TJBA/2026, o RAG (`rag/search_hybrid.py`) e a validação
  jurídica (`rag/legal_validation/`) para fundamentação verificável, e por
  fim gera o JSON de dados para `scripts/render_docx.py`. Diferente de
  `estrategista-contestacao-ede` (só pensa e estrutura) e de
  `redator-peca-processual-elite` (só redige forma) — esta é a única que
  fecha o ciclo até os 13 placeholders do template oficial.
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# Contestação — Skill orquestradora (SPEC-0001 REQ-002)

## 1. O que esta skill é e o que ela não é

Você **coordena** o fluxo completo de elaboração da Contestação — não
redige texto, não inventa fundamentação, não decide sozinha a estratégia.
Cada etapa abaixo tem um dono específico; sua função é acioná-lo na ordem
certa, passar o insumo certo, e recusar-se a avançar quando um insumo
obrigatório estiver faltando (Fail Closed — CLAUDE.md §17).

**Escopo desta fase (Fase 6, SPEC-0001):** esta skill define e integra
todo o pipeline abaixo — extração factual, proveniência, tempestividade,
RAG, validação jurídica, redator, humanizer e geração dos 13 valores de
placeholder. **Ela não executa aqui, contra um caso real, o fluxo fim-a-fim
até o DOCX final** — isso é objeto da Fase 7 (End-to-End), que também
depende da resolução prévia de `PEND-001` (suporte a imagem no placeholder
`FOTOS_DA_IRREGULARIADE` — ver `docs/PENDENCIAS.md`). Quando a Fase 7 for
autorizada, esta skill já está pronta para ser exercida ponta a ponta.

## 2. Componentes acionados (quem faz o quê)

| Etapa | Componente | Obrigatório? |
|---|---|---|
| Análise estratégica (teses, riscos, matriz de impugnação) | Skill `estrategista-contestacao-ede` | Recomendado — ver §4 |
| Tempestividade TJBA/2026 | Skill `calendario-forense-tjba-2026` | Obrigatório quando aplicável (CLAUDE.md §8) |
| Pesquisa/recuperação jurídica | `rag/search_hybrid.py` (`HybridSearcher`) | Obrigatório para toda fundamentação normativa |
| Validação de citação | `rag/legal_validation/` (`validar_citacao`) | Obrigatório antes de qualquer citação entrar na peça |
| Redação | Skill `redator-peca-processual-elite` | Obrigatório (CLAUDE.md §7, SPEC-0001 REQ-003) |
| Humanização | Skill `humanizer-pt-br` | Obrigatório (CLAUDE.md §7, SPEC-0001 REQ-004) |
| Proveniência factual | `scripts/validate_fatos.py` | Obrigatório antes de usar um fato na peça |
| Renderização final | `scripts/render_docx.py` (Fase 3, já pronto) | Só na Fase 7 |

## 3. Pipeline (SPEC-0001 REQ-031)

```text
documentos do advogado
  ↓
1. identificação de documentos relevantes
  ↓
2. extração factual COM PROVENIÊNCIA (§5)
  ↓
3. identificação de pedidos (do autor) e datas relevantes
  ↓
4. tempestividade (§6)
  ↓
5. identificação de questões jurídicas -> RAG -> validação de citações (§7)
  ↓
6. análise estratégica (estrategista-contestacao-ede) (§4)
  ↓
7. redator-peca-processual-elite -> humanizer-pt-br (§8)
  ↓
8. geração dos 13 valores de placeholder (§9)
  ↓
9. (Fase 7) scripts/render_docx.py -> Template Lock -> DOCX final
```

Não pule etapas para "adiantar" a peça — um pedido da inicial sem resposta,
uma tempestividade sem memória de cálculo, ou uma citação sem validação são
exatamente os buracos que o `estrategista-contestacao-ede` (checklist de
dialeticidade) e o Fail Closed deste projeto existem para prevenir.

## 4. Análise estratégica — `estrategista-contestacao-ede`

Para o fact-pattern deste template (irregularidade/fraude em medição de
energia, com Reconvenção), acione **primeiro** a skill
`estrategista-contestacao-ede` com os documentos do caso. Ela entrega uma
"ANÁLISE ESTRATÉGICA" estruturada (teses, matriz de impugnação, riscos,
documentos, jurisprudência sugerida — sempre marcando o que não estiver
confirmado como `NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS` ou
`PESQUISA JURISPRUDENCIAL NECESSÁRIA`) — é o principal insumo para as
seções V-XIV dessa análise, que alimentam os placeholders de §9.

Essa etapa é **recomendada, não uma dependência obrigatória no sentido do
CLAUDE.md §7** (que exige apenas redator + humanizer): um caso simples,
sem irregularidade regulatória disputada, pode dispensá-la a critério do
advogado. Quando dispensada, registre explicitamente essa decisão — não
silenciosamente pule a etapa.

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
qual documento ele veio. Antes de usar a lista de fatos extraídos na etapa
de redação, valide-a estruturalmente:

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

## 6. Tempestividade

Se houver prazo a contar e o processo tramitar no TJBA em 2026, acione
`calendario-forense-tjba-2026` (`skills/calendario-forense-tjba-2026/
scripts/calcular_tempestividade.py`) com data de publicação/ciência
extraída dos documentos (nunca presumida). Se faltar dado essencial
(REQ-012), o valor do placeholder `TEMPESTIVIDADE_CASO` deve registrar
`PENDENTE DE VALIDAÇÃO` e a memória de cálculo parcial — nunca uma data
inventada ou uma conclusão de tempestividade sem lastro.

## 7. Questões jurídicas — RAG + validação de citações

Para cada fundamento normativo que a análise estratégica ou a redação
precisarem citar:

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

Com fatos validados (§5), tempestividade resolvida ou sinalizada (§6),
citações validadas (§7) e a análise estratégica (§4) em mãos, acione
`redator-peca-processual-elite` para redigir cada seção com esse
conteúdo — nunca deixe o redator inventar tese, fato ou fundamento; ele
recebe conteúdo definido e produz forma. Em seguida, acione
`humanizer-pt-br` sobre o texto produzido — ela pode ajustar ritmo,
conectivos e fluidez, mas não pode alterar fundamentos, fatos, pedidos,
valores, citações ou conclusão jurídica (SPEC-0001 REQ-010).

## 9. Geração dos 13 placeholders

Monte um único JSON `{PLACEHOLDER: valor}` (ver
`templates/contestacao/schema.json`) para consumo por
`scripts/render_docx.py` na Fase 7. Mapeamento de origem de cada campo:

| Placeholder | Vem de |
|---|---|
| `JUIZO` | Extração factual (§5) — documento processual |
| `NUMERO_PROCESSO` | Extração factual (§5) |
| `AUTOR` | Extração factual (§5) |
| `TEMPESTIVIDADE_CASO` | Tempestividade (§6) — memória de cálculo ou `PENDENTE DE VALIDAÇÃO` |
| `SINOPSE_FATOS` | Extração factual (§5) + redator/humanizer |
| `REALIDADE_FATICA` | Extração factual (§5) + análise estratégica (§4) + redator/humanizer |
| `IRREGULARIDADE_ENCONTRADA` | Extração factual (TOI/laudo) + análise estratégica + RAG/validação (§7) + redator/humanizer |
| `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` | Análise estratégica (análise artigo-por-artigo REN 1.000/2021) + RAG/validação (§7) + redator/humanizer |
| `FOTOS_DA_IRREGULARIADE` | Texto/legenda (decisão da Fase 3 — `PEND-001` aberta para imagem embutida; não bloqueia esta fase) |
| `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` | Extração factual (histórico de consumo) + análise estratégica + redator/humanizer |
| `VALOR_FRA` | Extração factual — **nunca calculado ou estimado por inferência**; se ausente dos documentos, sinalizar, não inventar |
| `PEDIDOS_FINAIS` | Análise estratégica (impugnação dos pedidos + teses subsidiárias) + redator/humanizer |
| `LOCAL_DATA` | Local padrão do escritório + data de assinatura (dado operacional, não jurídico) |

Cada valor final passa pelo mesmo Fail Closed do restante do projeto: se
um placeholder depende de dado ausente, o valor deve dizer isso
explicitamente (`"NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."`,
`PENDENTE DE VALIDAÇÃO`, etc.) — nunca ficar vazio silenciosamente nem ser
preenchido por suposição. A validação estrutural final (placeholder
desconhecido, placeholder residual) é feita por
`scripts/validate_placeholders.py`, já pronto desde a Fase 3.

## 10. O que esta skill nunca faz

Não inventa fato, data, número de processo, valor, dispositivo legal,
súmula, precedente ou conteúdo de decisão (CLAUDE.md §9/§12). Não usa
jurisprudência real do RAG (`PEND-002`, ausente). Não insere imagem no
placeholder de foto (`PEND-001`, aberta). Não executa o fluxo fim-a-fim
contra um DOCX real nesta fase (Fase 7). Não decide sozinha estratégia de
defesa sem passar pela análise de `estrategista-contestacao-ede` quando
essa análise for pertinente ao caso.
