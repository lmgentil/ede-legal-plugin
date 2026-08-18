# Fase 7 — End-to-End da Contestação: procedimento e execução real

## Por que este documento existe

`estrategista-contestacao-ede`, `redator-peca-processual-elite` e
`humanizer-pt-br` são Skills do Claude Code — arquivos de instrução para
um agente LLM, não funções Python. Não existe, hoje, uma API para
"executar uma Skill" de dentro de um script (SPEC-0001 Fase 7 §33/§34).

`scripts/gerar_contestacao.py` e `tests/test_e2e_contestacao.py`
automatizam tudo que é automatizável — extração/validação de fatos,
tempestividade, RAG, validação jurídica, Template Engine, Template Lock —
e verificam, estruturalmente, que a saída esperada das três Skills existe
e tem a forma exigida pelos respectivos contratos. Mas a *produção* dessa
saída para o cenário sintético é um procedimento manual assistido: rodado
por este agente, dentro desta mesma sessão do Claude Code, registrado
abaixo com entrada e saída — não fabricado nem simulado por código.

## Procedimento

1. **Automatizar o automatizável** — feito em `scripts/gerar_contestacao.py`
   (fatos, tempestividade, RAG, validação jurídica, Template Engine/Lock).
2. **Criar procedimento manual reproduzível** — para cada Skill obrigatória,
   ler `skills/<nome>/SKILL.md` e aplicar seu contrato de saída ao caso
   sintético em `tests/fixtures/contestacao/happy_path/documentos/`.
3. **Executar no Claude Code** — feito nesta sessão (registro abaixo).
4. **Registrar entrada** — os 5 documentos sintéticos em `documentos/`.
5. **Registrar saída** — os artefatos gerados, listados abaixo.
6. **Validar critérios** — contrato de cada Skill conferido linha a linha
   antes de aceitar o artefato como válido.

## Execução registrada — cenário `happy_path`

### 1. `estrategista-contestacao-ede`

**Entrada:** os 5 documentos sintéticos de
`tests/fixtures/contestacao/happy_path/documentos/` (petição inicial,
TOI, laudo técnico, memorial de cálculo, certidão de citação).

**Procedimento aplicado:** metodologia de `skills/estrategista-contestacao-ede/SKILL.md`
§3-§7 — raio-x da inicial (fatos alegados/comprovados/não comprovados),
identificação de tese-mãe, análise artigo-por-artigo da REN ANEEL
1.000/2021 (§590, 591, 595, 596), classificação de risco por tese,
checklist de dialeticidade (nenhum pedido da inicial ficou sem resposta).

**Saída:** `tests/fixtures/contestacao/happy_path/estrategia.md` — 15
seções (I a XV), conforme o contrato de entrega de
`skills/estrategista-contestacao-ede/SKILL.md` §7.

**Critério validado:** `scripts/gerar_contestacao.py` confere
estruturalmente as 15 seções antes de aceitar o arquivo (estágio
`strategy`) — não apenas que ele existe.

### 2. `redator-peca-processual-elite`

**Entrada:** `estrategia.md` (acima) + fatos validados
(`tests/fixtures/contestacao/happy_path/fatos.json`) + citações validadas
(`rag/legal_validation.validar_citacao`, 7 das 8 citações candidatas).

**Procedimento aplicado:** redação técnico-jurídica de cada placeholder
narrativo (SINOPSE_FATOS, REALIDADE_FATICA, IRREGULARIDADE_ENCONTRADA,
DESENVOLVIMENTO_TECNICO_IRREGULARIDADE, ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA,
VALOR_FRA, PEDIDOS_FINAIS) a partir exclusivamente do conteúdo definido
pela estratégia e pelos fatos — nenhum fato ou fundamento novo introduzido.

**Saída:** `tests/fixtures/contestacao/happy_path/placeholders_redator.json`
(rascunho, pré-humanização).

### 3. `humanizer-pt-br`

**Entrada:** `placeholders_redator.json` (acima).

**Procedimento aplicado:** `skills/humanizer-pt-br/SKILL.md` — varia o
ritmo das frases, remove fórmulas repetitivas ("com fundamento no art.
X... com fundamento no art. Y..."), quebra estruturas mecânicas — sem
alterar nenhum fato, valor, nome, número de processo, citação ou
conclusão jurídica (SPEC-0001 REQ-010, conferido campo a campo entre as
duas versões abaixo).

**Saída:** `tests/fixtures/contestacao/happy_path/placeholders.json`
(versão final, consumida por `scripts/gerar_contestacao.py`).

**Conferência de que nada substancial mudou** (REQ-010): mesmos números
(`R$ 4.328,17`, `445566-7`, `8000001-11.2026.8.05.0080`), mesmas citações
(arts. 590/591/595/596 da REN 1.000, 373 do CPC), mesmos pedidos (a/b/c/d
da impugnação) e mesma conclusão (improcedência) em ambos os arquivos —
só a redação mudou.

## Resultado da execução automatizada sobre essa saída

```text
python scripts/gerar_contestacao.py --caso tests/fixtures/contestacao/happy_path \
    --output <tmp>/contestacao_sintetica.docx
```

```json
{
  "status": "OK",
  "fatos_com_proveniencia": 11,
  "citacoes_validadas": 7,
  "citacoes_nao_validadas": 1,
  "tempestividade": "TEMPESTIVO — termo inicial 2026-01-05, prazo de 15 dias uteis (art. 335, caput, CPC), termo final 2026-02-10.",
  "template_lock": "OK",
  "fotos": "INSERÇÃO MANUAL"
}
```

Reproduzido automaticamente por
`tests/test_e2e_contestacao.py::test_happy_path_pipeline_completo`.
