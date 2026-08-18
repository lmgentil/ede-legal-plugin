# Fixtures E2E — Contestação (Fase 7)

Cenários **inteiramente sintéticos** usados por `tests/test_e2e_contestacao.py`
via `scripts/gerar_contestacao.py`. Nenhum dado real de cliente, processo ou
documento — nomes, número de processo, unidade consumidora e valores são
fictícios. Nenhum conteúdo de `rag/jurisprudencia/` foi usado (PEND-002).

## `happy_path/`

Caso completo — todas as etapas obrigatórias presentes e válidas. Ver
`docs/E2E_FASE7.md` para como `estrategia.md` e `placeholders*.json`
foram efetivamente produzidos (execução manual assistida das Skills
`estrategista-contestacao-ede`, `redator-peca-processual-elite` e
`humanizer-pt-br`, não simulada por código).

## `fail_closed_valor_ausente/`

Mesmo caso, mas `placeholders.json` sinaliza `VALOR_FRA` como não
informado (memorial de cálculo ausente) — o pipeline deve interromper
(`PIPELINE_ABORTED`), nunca inventar o valor.

## Saída dos testes

DOCX gerados pelos testes vão para diretórios temporários
(`tempfile.TemporaryDirectory`) — nunca para este diretório nem para o
repositório.
