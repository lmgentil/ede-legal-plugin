---
name: calendario-forense-tjba-2026
description: Calcula tempestividade de atos processuais perante o TJBA no ano de 2026 (termo inicial, prazo, dias úteis, feriados forenses, suspensões, termo final), produzindo memória de cálculo auditável. Use sempre que precisar declarar ou avaliar tempestividade relativa ao TJBA em 2026 — nunca declare tempestividade sem passar por esta Skill, e nunca presuma data de publicação, ciência, feriado, suspensão ou termo final.
tools: [Read, Bash]
---

# calendario-forense-tjba-2026

Skill transversal obrigatória (`CLAUDE.md §8`, `SPEC-0001 REQ-005`) para toda
análise de tempestividade relativa ao TJBA em 2026.

## Regra de ouro (não negociável)

`CLAUDE.md §8` / `SPEC-0001 REQ-012`: **nunca declarar tempestividade sem
dados suficientes**, e nunca inventar data de publicação, data de ciência,
feriado, suspensão, termo inicial ou termo final. Quando os dados forem
insuficientes, o resultado correto é `PENDENTE DE VALIDAÇÃO` — isso **não é
uma falha da Skill, é o comportamento correto**.

## Como calcular

Não faça a conta de cabeça. Data de dias úteis com feriados/suspensões é
aritmética sujeita a erro sistemático de "off-by-one" mesmo para humanos —
use sempre o script determinístico:

```bash
python skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py --demo
```

Uso programático (dentro de um fluxo maior, ex. a futura Skill
`contestacao`):

```python
from calcular_tempestividade import calcular_tempestividade

resultado = calcular_tempestividade(
    data_pratica_ato="2026-03-10",       # quando o ato foi/será praticado
    data_publicacao="2026-02-02",         # ou data_ciencia, se houver
    prazo_legal_dias=15,
    tipo_prazo="uteis",                   # ou "corridos"
    fundamento_normativo="art. 335 CPC",
)
print(resultado.memoria_calculo())
```

## Estado atual do calendário forense TJBA 2026 — PENDÊNCIA CRÍTICA

`feriados_forenses_tjba_2026.json` está com `"verificado": false` e listas
vazias. **Isso é proposital**: não existe, nesta execução, uma fonte oficial
verificada (provimento/portaria da Corregedoria Geral de Justiça do TJBA)
para os feriados forenses e suspensões de prazo de 2026. Enquanto esse
arquivo não for preenchido a partir de fonte oficial:

- `calcular_tempestividade()` **sempre** retorna `status = "PENDENTE DE
  VALIDAÇÃO"` com o motivo explícito de que o calendário não está
  verificado — mesmo que todas as demais datas estejam completas;
- **nunca** presuma "não há feriado nesse intervalo" para contornar isso.

### Para destravar esta pendência

1. Obter o calendário forense oficial do TJBA para 2026 em fonte oficial
   (site do TJBA / DJEN / provimento da Corregedoria).
2. Preencher `feriados_forenses_tjba_2026.json`: `feriados_forenses` (lista
   de datas `YYYY-MM-DD`), `suspensoes` (lista de `{"inicio", "fim"}`),
   `fonte_oficial` (URL/identificação do ato normativo) e
   `data_verificacao`.
3. Só então marcar `"verificado": true`.

Isso está fora do escopo desta Fase 2 (é ingestão de dado factual externo
verificado, não redação/estrutura de Skill) — fica registrado como
pendência para antes de a Skill `contestacao` (Fase 6) depender dela para
uma conclusão definitiva de tempestividade.

## O que esta Skill produz (memória de cálculo — REQ-011)

Todo cálculo retorna, no mínimo: data de publicação, data de ciência
(quando houver), termo inicial, prazo legal em dias, tipo de prazo (dias
úteis/corridos), fundamento normativo, feriados considerados, suspensões
consideradas, termo final e status (`TEMPESTIVO` / `INTEMPESTIVO` /
`PENDENTE DE VALIDAÇÃO`, com motivo). Isso é o que vai para o relatório
operacional da peça (Fase 6, REQ-035).

## O que esta Skill nunca faz

- Nunca conclui `TEMPESTIVO`/`INTEMPESTIVO` sem calendário forense
  verificado.
- Nunca conclui sem data de publicação/ciência, prazo legal e fundamento
  normativo explícitos.
- Nunca aproxima "provavelmente não há feriado" como substituto de dado
  verificado.
