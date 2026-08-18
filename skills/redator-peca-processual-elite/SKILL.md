---
name: redator-peca-processual-elite
description: Redige e revisa o conteúdo jurídico (teses, fundamentação, pedidos) de peças processuais, com padrão técnico elevado, separação rígida entre fato e direito, e proibição absoluta de inventar fatos ou fundamentos jurídicos. Use sempre que estiver escrevendo ou revisando o mérito de uma peça processual — nunca redija fundamentação jurídica de peça sem passar por esta Skill.
tools: [Read, Grep, Glob, Bash]
---

# redator-peca-processual-elite

Skill transversal obrigatória (`CLAUDE.md §7`, `SPEC-0001 REQ-003`) para toda
elaboração de peça processual. Responsabilidade: transformar fatos já
extraídos + fontes jurídicas já recuperadas em texto jurídico redigido —
nunca produzir fato ou fundamento por conta própria.

## Quando usar

Sempre que for necessário escrever ou revisar:
- síntese fática de uma peça (ex.: `{{SINOPSE_FATOS}}`, `{{REALIDADE_FATICA}}`);
- tese jurídica (ex.: `{{TITULO_TESE_FATICA}}`);
- fundamentação de mérito;
- pedidos (`{{PEDIDOS_FINAIS}}`).

Não usar para decidir tempestividade (isso é `calendario-forense-tjba-2026`)
nem para o polimento final de fluidez (isso é `humanizer-pt-br`, que roda
**depois** desta Skill, nunca antes).

## Entradas exigidas

Esta Skill **não extrai fatos nem pesquisa jurisprudência por conta própria
a partir do zero** — ela consome o que já foi levantado:

1. **Fatos do processo**, com proveniência (documento de origem), já
   extraídos por quem chamou esta Skill. Se um fato relevante não vier
   acompanhado de fonte, não presumir: sinalizar a lacuna em vez de redigir
   em torno dela (`SPEC-0001 REQ-030`, `CLAUDE.md §17`).
2. **Questões jurídicas** a enfrentar (identificadas previamente).
3. Acesso ao RAG jurídico (`rag/search_hybrid.py`) para fundamentar cada
   afirmação de direito.

## Regra fundamental: fato × direito nunca se misturam

`CLAUDE.md §11` / `SPEC-0001 INV-005`: **FATOS DO PROCESSO** vêm exclusivamente
dos documentos do processo ou de informação expressamente fornecida pelo
advogado. **CONHECIMENTO JURÍDICO** vem exclusivamente do RAG ou de fontes
verificáveis. O RAG nunca é fonte de fato processual, e um documento do
processo nunca é fonte de tese jurídica. Ao redigir, mantenha essa origem
rastreável — não fundir os dois na hora da escrita a ponto de perder a
proveniência.

## Proibição de invenção (REQ-007, REQ-008 — não negociável)

- **Nunca** criar um fato que não esteja nos documentos do processo ou em
  informação expressamente fornecida pelo advogado.
- **Nunca** criar fundamento jurídico inexistente: artigo, súmula, resolução,
  precedente, ementa ou tese jurisprudencial que não tenha sido efetivamente
  recuperado e verificado.
- Uma citação jurídica só entra no texto depois de confirmada
  (`CLAUDE.md §12`):

  ```text
  citação proposta → fonte encontrada?
    SIM → validar → usar
    NÃO → nova consulta ao RAG → ainda sem fonte → NÃO usar como citação confirmada
  ```

- Se a busca no RAG não retornar informação suficiente, a resposta correta é
  declarar a insuficiência (conforme `rag/CONTEXTO_RAG.md`: *"Não há
  informação suficiente nos documentos para responder com segurança"*) — não
  completar por plausibilidade.

## Consulta ao RAG jurídico

Toda tese jurídica deve ser fundamentada via `rag/search_hybrid.py`, nunca
por memória do modelo quando o RAG estiver disponível (`CLAUDE.md §9/§10`):

```bash
python rag/search_hybrid.py "responsabilidade da distribuidora por interrupção indevida" -k 5
python rag/search_hybrid.py "art. 373 CPC"
```

Cada resultado traz um nível de confiança (alta/média/baixa — ver
`rag/CONTEXTO_RAG.md`). Resultado "baixa" é sinal de que provavelmente não há
base suficiente ali; não usar como fundamento sem nova consulta ou sem
sinalizar a fragilidade.

Toda citação usada na peça deve poder ser rastreada até a fonte recuperada
(corpus + chunk + artigo, ex.: `(Fonte: REN 1000, TII_C04_P02.md, art. 356)`),
para permitir a validação de citações prevista para a Fase 5.

## Padrão redacional (REQ-006)

- linguagem profissional e objetiva;
- coerência argumentativa, com encadeamento explícito fato → norma → conclusão;
- ausência de redundância desnecessária;
- precisão terminológica (não trocar termos técnicos por sinônimos genéricos);
- pedidos formulados com precisão processual (claros, específicos, sem
  ambiguidade quanto ao que se pede).

## O que esta Skill não faz

- Não decide tempestividade — aciona `calendario-forense-tjba-2026`.
- Não faz o polimento final de fluidez/ritmo — isso é `humanizer-pt-br`,
  executado depois, sobre o texto que esta Skill produziu.
- Não decide qual template/placeholder usar — isso é do motor de
  renderização (Fase 3) e da Skill orquestradora da peça (Fase 6).
- Não inventa número de processo, ementa ou teor de decisão.

## Limitações conhecidas nesta fase (Fase 2)

- Ainda não existe Skill orquestradora (`skills/contestacao/`, Fase 6) que
  chame esta Skill automaticamnte dentro de um pipeline — hoje ela é
  invocável isoladamente.
- O corpus de jurisprudência (`rag/jurisprudencia/`) ainda não está indexado
  em `rag/search_hybrid.py` (gap registrado na auditoria da Fase 0, REQ-018
  `[PARCIAL]`) — até lá, qualquer citação de jurisprudência precisa ser
  verificada manualmente contra as fichas em `rag/jurisprudencia/*.md`
  (fora do controle de versão, ver `docs/adr/ADR-0006-assets-institucionais.md`),
  nunca por memória do modelo.
- O template e o schema de placeholders ainda não existem (Fase 3) — o texto
  produzido por esta Skill hoje é conteúdo solto, não preenchimento de
  `{{PLACEHOLDER}}`.
