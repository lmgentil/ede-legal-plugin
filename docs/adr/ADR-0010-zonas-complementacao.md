# ADR-0010 — Zonas de Complementação no modelo institucional da Contestação

* **Status:** Aceito
* **Data:** 2026-08-25
* **Etapas:** 5.8-A (auditoria somente-leitura), 5.8-B (implementação piloto)
* **Invariante criada:** `INV-ZONA-COMPLEMENTACAO`
* **Relacionados:** ADR-0009 (template como asset externo),
  `INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA` (SPEC-0001 §56),
  `INV-COMPOSICAO-BLOCOS` (SPEC-0001 §5),
  `INV-NUMERACAO-DINAMICA-CONTESTACAO` (SPEC-0001 §55)

---

## Contexto

A auditoria somente-leitura da Etapa 5.8-A mediu, contra o
`modelo-oficial.docx` real, uma lacuna estrutural concreta:

* das 16 ocorrências físicas dos 13 placeholders, **12 ficam fora de
  qualquer bloco condicional**;
* o catálogo tem 12 entradas em `blocks[]`; descontado
  `INLINE_COM_RECONVENCAO` (fragmento do título da peça, não uma seção),
  são 11 seções, e **9 delas são integralmente texto fixo** — os
  únicos placeholders dentro de bloco são `VALOR_FRA` (×2) e
  `IRREGULARIDADE_ENCONTRADA` em `RECONVENCAO`, e
  `VALOR_DANO_MORAL_PRETENDIDO` em `DESCABIMENTO_DANO_MORAL`, todos
  valores ou rótulo atômico, nenhum argumentativo;
* consequência medida: `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` é o único
  ponto gerativo técnico do documento inteiro (teto de 5 parágrafos /
  700 caracteres, no tópico 3.1.2) e acaba absorvendo o que pertenceria
  ao tópico 3.4 e ao bloco de evolução de consumo, porque esses não têm
  endereço nenhum.

O ponto mais nítido é o tópico 3.4: o modelo transcreve integralmente os
cinco incisos do art. 595 e o prazo de 36 ciclos do art. 596, §5º, e
depois afirma que *"a concessionária observou rigorosamente essa lógica
normativa, adotando metodologia compatível com os elementos técnicos
disponíveis, em total aderência à disciplina do art. 595"* — **sem nunca
dizer qual inciso foi aplicado neste caso, nem qual período foi
apurado**. É asserção de conformidade sem o dado que a torna verificável,
e o dado é documental (consta da memória de cálculo).

O problema não é falta de espaço. É **ausência de endereço**: o conteúdo
migra para o campo errado porque não existe campo certo.

## Decisão

Criar uma terceira categoria de zona de intervenção textual, a **Zona de
Complementação**, distinta das duas existentes:

| | Bloco | Placeholder | **Zona** |
|---|---|---|---|
| decidido por | estrategista/advogado | — | **ninguém: nunca é decidida** |
| `decision_mode` | sim | — | **proibido no catálogo** |
| entra em `derived_rule` | sim | — | **nunca** |
| pode incluir o bloco-pai | — | — | **nunca** |
| listado em `editable_placeholders` | não | sim (13) | **nunca** |
| estado normal | conforme estratégia | preenchido | **vazia** |
| exige suporte fático | conforme o bloco | conforme o campo | **sempre, obrigatório** |

A regra permanente do projeto passa de:

> SEM PLACEHOLDER → SEM ESCRITA GERATIVA

para:

> **SEM PLACEHOLDER OU ZONA DE COMPLEMENTAÇÃO EXPRESSAMENTE CATALOGADA
> → SEM ESCRITA GERATIVA**

A ordem de princípio de `INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA`
permanece intacta: **PRESERVAR > COMPLEMENTAR > CRIAR**. A zona não
autoriza reescrita de texto institucional em hipótese alguma; ela existe
para conectar a fundamentação institucional fixa aos dados concretos e
documentais do processo.

Esta etapa autoriza **uma única zona**:

```
ZONA_METODOLOGIA_APURACAO  →  bloco CALCULOS_RECUPERACAO_CONSUMO
```

## Representação OOXML

Alternativas comparadas na Etapa 5.8-A:

| | Localização | Remoção quando vazia | Herda `w:pPr` | Veredito |
|---|---|---|---|---|
| A. `w:sdt` próprio | determinística, mecânica existente | caminho `EXCLUIR` já implementado | precisa de parágrafo âncora | forte, incompleta sozinha |
| B. bookmark | frágil (Word renomeia/duplica ao editar) | sem semântica de container | não | **rejeitada** |
| C. token puro `{{ZONA_X}}` | regex existente | exige código novo de remoção de `<w:p>` | sim | mistura contratos no schema |
| **D. híbrido A+C** | tag do SDT | remove o SDT inteiro | sim | **adotada** |

**D**: um `w:sdt` com `w:tag = "ZONA:<ID>"` contendo **exatamente um**
`<w:p>` cujo texto é o token `{{ZONA_<ID>}}`, sozinho no parágrafo.

D não é mais complexa que C: ela **reaproveita** a complexidade já
existente e já auditada. Nenhum mecanismo paralelo foi criado —
localização, remoção, cor, parágrafo e limites vêm todos de código que já
estava em produção:

| Requisito | Resolvido por (pré-existente) |
|---|---|
| localização determinística | `_sdts_por_tag()` |
| remoção integral quando vazia | caminho `EXCLUIR` de `_compor_sdts_do_corpo()` |
| inserção só naquele ponto | substituição token → valor num único `w:t` |
| FF0000 | `_rpr_com_cor_forcada()` / `COR_CONTEUDO_GERADO` |
| `<w:p>` reais herdando `w:pPr` | `_explodir_paragrafos_multilinha()` |
| 380 caracteres por parágrafo (sem espaços desde a 5.8-C.1) | `INV-PARAGRAFO-380` |
| travessão proibido | `_checar_travessao()` |
| Template Lock | recomputação byte a byte, inalterada |

## Cadeia determinística

`compor_zonas` entra **depois** da composição de blocos — para que o
estado do bloco-pai já esteja resolvido — e **antes** da renumeração e da
validação de placeholders, para que zona vazia jamais alcance
`validar_placeholders()`:

```
template_xml
  → compor_blocos      (ignora SDT ZONA:*)
  → compor_zonas       (NOVO)
  → renumerar_titulos
  → validar_numeracao_final
  → validar_placeholders
  → substituir_placeholders
  → Template Lock (recomputa a MESMA cadeia e compara byte a byte)
```

Quando o bloco-pai é `EXCLUIR`, o SDT da zona desaparece junto com ele,
por ser seu descendente — a regra "bloco-pai `EXCLUIR` ⇒ zona `EXCLUIR`"
se cumpre estruturalmente, não por regra duplicada.

## Regra de ativação (cascata)

1. bloco-pai `EXCLUIR` → `EXCLUIR`
2. algum `requires_facts` `"INDETERMINADO"` → **aborta** (`zona_indeterminada`)
3. algum `requires_facts` falso/ausente → `EXCLUIR`, **sem perguntar**
4. fatos presentes, conteúdo não vazio → `INCLUIR`
5. fatos presentes, conteúdo vazio → `EXCLUIR`

A ordem 2 antes de 3 é deliberada: ambiguidade documental nunca pode ser
silenciosamente resolvida como "sem suporte fático" — mesmo princípio de
`INV-CORTE-GATE-HUMANO`.

Conteúdo fornecido para zona que a cascata resolve como `EXCLUIR` (por
bloco-pai excluído ou falta de suporte fático) é **incoerência de
pipeline**, não sobra inofensiva: aborta (`zona_incoerente`) em vez de
descartar em silêncio (CLAUDE.md §17).

**Nenhum ramo pergunta ao advogado.** Zona não tem decisão humana —
diferente de `RECONVENCAO` (`INV-RECONVENCAO-AUTORIZACAO-EXPRESSA`) e de
`LICITUDE_CORTE_SUSPENSAO` (`INV-CORTE-GATE-HUMANO`), que abortam
pedindo manifestação. Gastar interação humana com complemento seria
ruído.

## Gate fático: por que uma chave nova, e só uma

O pipeline produz dois contratos factuais distintos:

* `fatos.json` — lista de fatos em prosa com proveniência
  (`validate_fatos.py`). **Sem chaves consultáveis.**
* `estado_processual.json` — o **único** contrato de fato com chave,
  resolvido por `_estado_fato_processual` em `TRUE`/`FALSE`/
  `INDETERMINADO`, hoje com duas chaves (`GRATUIDADE_CONCEDIDA`,
  `CORTE_EFETIVO`).

Como a regra de ativação exige a tri-estabilidade, o gate reutiliza
integralmente o segundo mecanismo — nenhum contrato novo, nenhum
validador novo, nenhum arquivo novo de fato. Nenhuma das duas chaves
existentes trata de metodologia de apuração, então **uma** chave nova foi
introduzida:

```
METODOLOGIA_APURACAO_DOCUMENTADA
```

`true` quando os autos contêm memória de cálculo ou memorial de
faturamento que identifica o critério e o período da apuração; `false`/
ausente quando não contêm; `"INDETERMINADO"` quando os documentos são
contraditórios. Resolvida pela Skill `contestacao` a partir dos
documentos, com proveniência — **nunca por busca lexical**.

## Modelo desatualizado

O `modelo-oficial.docx` é asset externo, fornecido separadamente
(ADR-0009). Criar uma zona significa uma nova versão do modelo em poder
de cada usuário. Quem estiver com o modelo anterior recebe erro
operacional próprio, `MODELO_INSTITUCIONAL_DESATUALIZADO`, que diz o que
precisa ser feito — nunca um `tag_ausente` cru. O plugin **não** busca,
baixa, reconstrói nem edita o modelo automaticamente, e nenhuma peça é
gerada até que o modelo seja atualizado.

## Consequências

**Positivas**

* O tópico 3.4 passa a poder afirmar aderência ao art. 595 **e** dizer
  qual inciso e qual período — sem que o Redator precise contrabandear
  esse conteúdo para `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`.
* O Template Lock ganha alcance: passa a rejeitar, de graça, qualquer SDT
  `ZONA:*` que apareça no template sem estar catalogado.
* A auditabilidade não se degrada: a zona é declarada, versionada,
  limitada e verificada nos dois sentidos contra o template real.

**Negativas / riscos assumidos**

* Existem agora **duas** listas de zonas de escrita, não uma. Toda
  auditoria futura precisa consultar `schema.json` **e** `blocos.json`.
* Risco central: a zona virar válvula de escape para o conteúdo que não
  coube no placeholder correto. Mitigações: tetos de zona
  deliberadamente menores que os dos placeholders (2 parágrafos / 400
  caracteres, contra 3-5 / 600-700), e o teste de necessidade abrindo
  com a pergunta "algum dos 13 placeholders é o endereço correto disto?".
* Distribuição: um modelo por usuário passa a ter versão funcional
  acoplada ao catálogo.

**Contenção permanente**

Toda zona futura exige **autorização expressa do usuário**, com
auditoria própria como a da Etapa 5.8-A. Não existe, e não deve passar a
existir, `ZONA_COMPLEMENTACAO_GENERICA` ou equivalente sem bloco-pai
único.

## Alternativas rejeitadas

* **Criar um 14º placeholder.** Placeholder é obrigatório e tem
  finalidade semântica fixa; esta área é opcional e normalmente vazia.
  Misturar os contratos destruiria a asserção "os 13 são 13".
* **Flexibilizar o Template Lock com whitelist de regiões editáveis.**
  Desnecessário: o Lock é recomputação, não diff — bastou acrescentar um
  estágio determinístico à cadeia. Uma whitelist teria enfraquecido a
  única prova forte que o projeto tem.
* **Zonas nos blocos com premissa hardcoded** (`RECONVENCAO`,
  `DEVER_LEGAL_FISCALIZACAO`, `PRELIMINAR_CDC_INAPLICAVEL`). Ali o
  problema é texto-base incompatível, matéria composicional; zona seria
  remendo, vedado pelo princípio PRESERVAR > COMPLEMENTAR.
* **`ZONA_EVOLUCAO_NUMERICA`.** Juridicamente forte, mas colide com a
  remoção definitiva de `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA`
  (CLAUDE.md §14), que exige autorização expressa para qualquer
  equivalente. Registrada, não implementada.

## Adendo — Etapa 5.8-C.1 (coerência semântica e aritmética)

A proveniência introduzida na 5.8-C provava **ancoragem lexical**: todo
número do texto existia em algum dado declarado com fonte. Não provava
que o dado estava na fonte certa, que a unidade fazia sentido, nem que as
contas fechavam. O teste real da 5.8-C produziu uma redação de teste
afirmando `2.412 kWh × R$ 1,7947/kWh = R$ 4.328,17` como se fosse a
fórmula do memorial (o produto real é R$ 4.328,82), aprovada por todas as
validações.

**Correção de curso, gate de fechamento:** a primeira resposta a este
achado tratou a divergência como erro da fixture e alterou o valor
documental para R$ 4.328,82. Auditado o memorial diretamente, ele **não**
apresenta a multiplicação como fórmula do total (consumo, tarifa e valor
final são três linhas separadas, sem "="). R$ 4.328,17 foi **preservado**
como valor documental; corrigida foi a redação de teste, removendo a
afirmação de fórmula que o documento não sustenta.

Consequências para esta decisão arquitetural:

- o contrato de proveniência da zona passa de `{"dado", "fonte"}` para
  `{"tipo", "valor", "unidade"?, "fonte", "natureza", "operacao"?,
  "metodologia"?}` — dado legível por máquina, não prosa;
- `natureza` distingue **documental** (consta expressamente do documento
  oficial) de **derivado** (resultado matemático de dados documentais);
- a validação aritmética é **controle de coerência, nunca recálculo da
  cobrança**: a fonte de verdade dos valores é o Memorial de Cálculo /
  Memorial de Faturamento do procedimento administrativo, e a zona existe
  para defender a cobrança constituída, não para reconstruí-la;
- **estimativa regulamentar não é arbitrariedade** — apuração estimada
  segundo os critérios da regulamentação é procedimento regular; a
  diferença aparente entre uma conta simples e o valor documental pede
  consulta à metodologia do próprio documento (declarada em
  `metodologia`) antes de qualquer fail-closed;
- só há fail-closed quando (1) documentos oficiais se contradizem sobre o
  mesmo dado, (2) a peça afirma como `derivado` um resultado que não
  fecha, ou (3) a peça reproduz uma operação que o documento não sustenta
  e nenhuma metodologia documental foi apontada;
- nenhum validador de linguagem natural: só relações estruturadas desta
  primeira zona, com `Decimal` para dinheiro e álgebra de unidades por
  cancelamento.

Nada disso altera a natureza da zona (não é bloco, não é placeholder, é
normalmente vazia), a cadeia determinística, o Template Lock, nem a
quantidade de zonas autorizadas — que continua **uma**.

Detalhamento completo em `docs/specs/SPEC-0001.md` §59.
