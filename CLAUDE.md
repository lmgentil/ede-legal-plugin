# CLAUDE.md — EDE Legal Plugin

## 1. Projeto

Este repositório contém o **EDE Legal Plugin**, plugin jurídico para Claude Code destinado à elaboração assistida de peças processuais.

A primeira peça suportada é a **Contestação**, mas a arquitetura deve permanecer extensível para outros tipos de peças.

A especificação arquitetural vigente está em:

`docs/specs/SPEC-0001.md`

Antes de realizar alterações estruturais, leia a SPEC e os ADRs aplicáveis.

---

## 2. Hierarquia documental

Para decisões de implementação, observe:

1. `CLAUDE.md` — regras operacionais permanentes;
2. SPEC vigente — requisitos do sistema;
3. ADRs aceitos — decisões arquiteturais;
4. `SKILL.md` — comportamento especializado;
5. código e testes existentes.

Se houver conflito relevante entre esses documentos, não escolha silenciosamente uma interpretação.

Identifique e reporte a divergência.

---

## 3. Regra fundamental

Não transforme o projeto em um gerador monolítico de Contestação.

A arquitetura deve permanecer:

```text
Core
├── Skills processuais
├── Skills transversais
├── Templates
├── RAG jurídico
├── Validação
├── Renderização
└── Atualização
```

Contestação é apenas o primeiro módulo processual.

---

## 4. Desenvolvimento por fases

A implementação da `SPEC-0001` é controlada por gates.

Não avance automaticamente entre fases.

Quando autorizado a executar determinada fase:

1. implemente somente aquela fase;
2. execute os testes aplicáveis;
3. valide os critérios de aceite;
4. documente alterações relevantes;
5. informe pendências;
6. pare ao concluir.

Não inicie a fase seguinte sem autorização explícita.

---

## 5. Antes de modificar código

Antes de qualquer alteração relevante:

1. inspecione os arquivos relacionados;
2. identifique implementação existente;
3. verifique testes existentes;
4. consulte SPEC e ADRs relacionados;
5. preserve comportamento funcional não relacionado.

Não sobrescreva implementação funcional sem compreender sua finalidade.

---

## 6. Alterações arquiteturais

Não introduza silenciosamente decisões arquiteturais novas.

Quando uma alteração representar decisão arquitetural relevante:

* identifique a necessidade;
* verifique ADR existente;
* proponha atualização ou novo ADR;
* registre consequências.

Código não deve se tornar arquitetura por acidente.

---

## 7. Skills obrigatórias

### 7.1. Dependências transversais (toda peça processual)

Toda elaboração de peça processual deverá utilizar:

`redator-peca-processual-elite`

e:

`humanizer-pt-br`

Essas duas são dependências transversais obrigatórias de redação —
aplicam-se a qualquer peça, não só à Contestação. Nenhuma Skill
processual específica (`contestacao` e as que vierem depois) deverá
duplicar integralmente as responsabilidades delas; a Skill processual
orquestra, não redige nem humaniza por conta própria.

### 7.2. Dependências específicas por tipo de peça

Além das transversais, cada tipo de peça pode ter dependências próprias,
específicas daquele tipo — não generalizadas para as demais. Hoje:

```text
Contestação
→ estrategista-contestacao-ede
```

Isso deverá permitir, no futuro, estruturas equivalentes para outras
peças (ex.: um eventual `estrategista-recurso-inominado-ede` para Recurso
Inominado, uma Skill estratégica própria para Embargos de Declaração),
**sem** tornar `estrategista-contestacao-ede` dependência de peças
diferentes de Contestação.

Para Contestação, especificamente, toda elaboração deverá utilizar
obrigatoriamente as três:

`estrategista-contestacao-ede`
`redator-peca-processual-elite`
`humanizer-pt-br`

`estrategista-contestacao-ede` é dependência obrigatória — não deve ser
descrita nem tratada como opcional, recomendada, facultativa ou
complementar. Ver `INV-CONTESTACAO-ESTRATEGIA` (SPEC-0001 §5).

A Skill `contestacao` é a orquestradora do fluxo — responsável por
acioná-las na ordem certa e consumir a saída de cada uma, sem absorver
integralmente as responsabilidades de nenhuma delas:

* `estrategista-contestacao-ede` — análise estratégica da demanda:
  decomposição da narrativa autoral, identificação das controvérsias,
  matriz de impugnação, teses defensivas, riscos, lacunas documentais,
  direcionamento estratégico da defesa.
* `redator-peca-processual-elite` — construção e redação técnico-jurídica
  da peça a partir dos fatos, da estratégia e dos fundamentos
  juridicamente admitidos pelo pipeline.
* `humanizer-pt-br` — tratamento linguístico final, preservando fatos,
  estratégia, fundamentos, citações, valores, dados processuais e sentido
  jurídico; não cria fatos nem modifica substancialmente a estratégia
  definida.

### Invariante — Estratégia obrigatória da Contestação

Toda elaboração de Contestação deverá executar obrigatoriamente a Skill
`estrategista-contestacao-ede` antes da etapa de redação.

A Skill `contestacao` deverá atuar como orquestradora desse fluxo e não
poderá:

* suprimir a etapa estratégica;
* substituir silenciosamente o estrategista;
* tratar sua execução como opcional;
* iniciar a redação definitiva sem que a etapa estratégica tenha sido
  concluída.

Falha ou indisponibilidade da Skill estratégica deverá ser explicitamente
reportada. Não implementar fallback silencioso que produza a Contestação
como se a etapa estratégica tivesse ocorrido.

Formalizada na SPEC como `INV-CONTESTACAO-ESTRATEGIA` (SPEC-0001 §5).

### Fluxo conceitual da Contestação

```text
Documentos do processo
        ↓
extração factual + proveniência
        ↓
estrategista-contestacao-ede
        ↓
estratégia defensiva
        ↓
RAG jurídico
        ↓
validação jurídica
        ↓
redator-peca-processual-elite
        ↓
humanizer-pt-br
        ↓
conteúdo autorizado dos placeholders
        ↓
Template Engine
        ↓
Contestação
```

Representação conceitual — não é uma prescrição literal de código; o que
importa é a ordem e a separação de responsabilidades, já refletidas em
`skills/contestacao/SKILL.md`.

### Composição de blocos condicionais (Etapa 5)

O template marca estruturalmente (`<w:sdt>`) as teses condicionais da
Contestação (preliminares, dever legal de fiscalização, evolução de
consumo, Reconvenção etc.), catalogadas em
`templates/contestacao/blocos.json`. A decisão de incluir/excluir cada
tese é sempre da etapa estratégica — nunca do motor documental
(`scripts/docx_block_engine.py`), que só valida o catálogo e executa
deterministicamente (nenhuma heurística jurídica em Python). Estado só
pode ser `INCLUIR`/`EXCLUIR`/`INDETERMINADO`; `INDETERMINADO` nunca
alcança o DOCX final — aborta o pipeline, mesmo com blocos irmãos
decididos. Formalizada na SPEC como `INV-COMPOSICAO-BLOCOS`
(SPEC-0001 §5, REQ-002-B) — detalhes de catálogo/cardinalidade/Template
Lock composicional ficam lá, não duplicados aqui.

### Invariantes de calibração redacional e composição (Etapa 5.2)

Decorrentes dos problemas confirmados no primeiro teste prático real da
Contestação (parágrafos excessivamente extensos, Sinopse contaminada por
argumentação defensiva, Reconvenção incluída sem autorização do advogado,
LICITUDE_CORTE_SUSPENSAO incluído sem notícia concreta de corte). Não
substituem nenhuma invariante anterior. Definição completa em
`docs/specs/SPEC-0001.md` (seção "Invariantes de calibração redacional,
Etapa 5.2") — resumo operacional aqui:

- **INV-PARAGRAFO-380** — todo parágrafo de conteúdo variável (novo,
  gerado pela IA para os placeholders multiline) tem no máximo 380
  caracteres com espaços; validado estruturalmente por
  `scripts/validate_paragrafos.py` antes do DOCX final
  (`stage=paragrafo_380`). Não se aplica ao texto-base institucional
  fixo do template.
- **INV-NAO-REDUNDANCIA** — o limite de 380 caracteres não pode ser
  contornado multiplicando parágrafos artificialmente; cada parágrafo
  novo deve acrescentar um elemento argumentativo útil. Comportamental
  (sem validação Python — detectar redundância semântica de forma
  confiável seria heurística jurídica embutida em código, vedada).
- **INV-SINOPSE-ESTRITAMENTE-AUTORAL** — `SINOPSE_FATOS` é exclusivamente
  a narrativa da petição inicial (fatos alegados + pedidos), nunca a
  versão ou impugnação da Ré. Backstop lexical em
  `scripts/validate_placeholder_semantics.py` (não exaustivo); controle
  real é comportamental, da Skill `contestacao`/`redator-peca-processual-
  elite`.
- **INV-NAO-REPETICAO-FATICA (Etapa 5.5)** — achado do Teste Real: o
  mesmo fato técnico (ex. "desvio de energia antes do medidor")
  reaparecia quase palavra por palavra em `REALIDADE_FATICA`,
  `IRREGULARIDADE_ENCONTRADA` e `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`.
  Um fato não deve ser reapresentado em vários parágrafos apenas com
  palavras diferentes; cada placeholder narrativo tem função própria e
  exclusiva — nenhum é uma "nova versão" do anterior:
  `SINOPSE_FATOS` só a narrativa autoral (acima); `REALIDADE_FATICA` é
  contraposição global/objetiva, sem antecipar o detalhe técnico que
  pertence aos subtópicos; `IRREGULARIDADE_ENCONTRADA` só o nome/tipo
  atômico (contrato já existente, Etapa 5.3-B); `DESENVOLVIMENTO_TECNICO_
  IRREGULARIDADE` acrescenta explicação técnica nova, nunca só restate o
  rótulo; `EVOLUCAO_CONSUMO` só dado concreto de evolução;
  `PEDIDOS_FINAIS` conclusão processual, sem reencenar fatos. Antes de
  finalizar um parágrafo narrativo, Redator/Humanizer verificam se ele
  apresenta fato novo, desenvolve consequência nova, faz subsunção
  necessária, ou apenas parafraseia o que já foi dito noutro
  placeholder — só o último caso exige reescrita/remoção. O problema é
  semântico (paráfrase), não mera igualdade textual — não crie
  bloqueador destrutivo baseado em igualdade/similaridade textual
  genérica (geraria falsos positivos); backstop determinístico em
  `scripts/validate_placeholder_semantics.py` cobre só o sintoma mais
  grave e inequívoco (rótulo atômico de `IRREGULARIDADE_ENCONTRADA`
  reaparecendo verbatim dentro de `REALIDADE_FATICA`), não exaustivo —
  controle real é comportamental, das Skills `contestacao`/
  `redator-peca-processual-elite`/`humanizer-pt-br`.
- **INV-RECONVENCAO-AUTORIZACAO-EXPRESSA** — Reconvenção é decisão
  reservada ao advogado, nunca do estrategista sozinho:
  `RECONVENCAO` é `decision_mode: "humano"` no catálogo
  (`templates/contestacao/blocos.json`) — a Skill `contestacao` deve
  perguntar SIM/NÃO (`AskUserQuestion`) antes de registrar a decisão; sem
  resposta, o bloco permanece ausente/`INDETERMINADO` e o fail-closed já
  existente aborta o pipeline.
- **INV-BLOCO-SUPORTE-FATICO** — nenhum bloco condicional entra só porque
  existe no catálogo, é juridicamente possível, ou o RAG recuperou
  legislação relacionada; exige suporte fático/processual concreto, com
  proveniência. Princípio geral, majoritariamente comportamental — dois
  blocos específicos (abaixo) têm mecanismo determinístico.
- **INV-GRATUIDADE-LINKED** — `PRELIMINAR_REVOGACAO_GRATUIDADE` **não é
  decisão do estrategista** (nem livre, nem sob gate): é vinculada
  deterministicamente ao estado processual `GRATUIDADE_CONCEDIDA`
  (`decision_mode: "state_linked"`, `linked_fact` no catálogo) — o estado
  do bloco *é* o estado processual (`true`→`INCLUIR`, `false`/
  ausente→`EXCLUIR`, `"INDETERMINADO"`→aborta). Decisão manual para este
  bloco em `decisoes_blocos.json` é rejeitada explicitamente. Distinto de
  `requires_fact` (mecanismo de gate fático que só restringe `INCLUIR`,
  sem dispensar decisão manual — usado por `LICITUDE_CORTE_SUSPENSAO`
  abaixo) — este é vínculo, não gate.
- **INV-CORTE-GATE-HUMANO** (Etapa 5.5, 3ª correção arquitetural) —
  `LICITUDE_CORTE_SUSPENSAO` é `decision_mode: "humano"` com
  `requires_fact: {"key": "CORTE_EFETIVO"}` no catálogo: suporte fático
  **e** decisão humana, nenhum dos dois dispensa o outro. `CORTE_EFETIVO:
  false`/ausente→`EXCLUIR` automático, sem perguntar ao advogado (nada a
  decidir sobre tese sem suporte fático). `CORTE_EFETIVO:
  "INDETERMINADO"`→aborta (`decisao_indeterminada`), com ou sem decisão
  registrada. `CORTE_EFETIVO: true` **sem** decisão em
  `decisoes_blocos.json`→aborta (`decisao_ausente`) — sinal para a Skill
  `contestacao` perguntar (`AskUserQuestion`) "Deseja incluir o tópico
  relativo à licitude do corte/suspensão?"; só resposta afirmativa vira
  `INCLUIR`. `CORTE_EFETIVO: true` com decisão humana registrada→
  `INCLUIR`/`EXCLUIR` conforme a resposta. Tentar `INCLUIR` com
  `CORTE_EFETIVO: false`→rejeitado (`gate_fatico_nao_satisfeito`), mesmo
  com decisão humana registrada. Duas correções anteriores, ambas
  superadas: (1) gate + decisão estratégica sem checagem adicional
  permitiu, em teste real, inclusão baseada em mera alegação da autora;
  (2) `state_linked` puro (mesma arquitetura de `INV-GRATUIDADE-LINKED`)
  incluía automaticamente sempre que o corte fosse comprovado, sem o
  advogado manifestar vontade de desenvolver a tese — um teste real
  seguinte mostrou que isso também é incorreto. **Alegação da autora não
  é prova de corte efetivo**: mera ameaça, aviso de possível suspensão,
  pedido preventivo, pedido de restabelecimento isolado,
  inadimplência/débito não configuram `CORTE_EFETIVO: true` — exige
  evidência que a Ré não contradiga (ex.: registro operacional da
  concessionária) ou confirmação expressa do advogado (`AskUserQuestion`)
  quando os documentos não bastarem para confirmar de forma independente
  da narrativa da própria autora; esta é exceção expressa ao princípio
  geral de `INV-BLOCO-SUPORTE-FATICO` (abaixo), que aceita alegação da
  autora como suporte suficiente para a maioria dos blocos. Nem
  `CORTE_EFETIVO` nem `GRATUIDADE_CONCEDIDA` aceitam ocorrência lexical
  ("não houve corte" no texto de um documento nunca vira `CORTE_EFETIVO:
  true`) como prova — o estado é resolvido pela Skill `contestacao` a
  partir dos documentos, com proveniência, nunca por busca textual.
- **INV-NAO-REDUNDANCIA-NORMATIVA** — a redação variável não repete
  dispositivo normativo já presente no tópico-base institucional fixo do
  modelo; o RAG valida/complementa fundamentação, não é gerador de lista
  de artigos.

### Invariante de orquestração e entrega (Etapa 5.6)

Achado do Teste Real (Etapa 5.6): a análise estratégica concluiu
corretamente e a execução encerrou entregando-a ao advogado como resposta
final, anunciando RAG/Redator/Humanizer como "próximos passos". Incorreto
— o plugin existe para produzir a peça, não para o advogado conduzir
manualmente as etapas internas do pipeline.

- **INV-CONTESTACAO-ENTREGA-DOCX** — quando a intenção do pedido for
  elaborar, gerar, preparar ou produzir a Contestação (`MODO PRODUÇÃO`),
  a resposta esperada é a **Contestação final em DOCX**, não um artefato
  intermediário. Análise estratégica, extração factual, RAG, decisões
  automáticas de blocos, redator, humanizer, validações e composição são
  etapas internas do mesmo fluxo — nenhuma delas é resposta final, e a
  conclusão de qualquer uma delas não encerra a execução nem gera pedido
  de autorização para prosseguir ("próximo passo recomendado...", "posso
  gerar a Contestação...", "se quiser, prossigo para o DOCX..."). A
  execução só pode interromper antes do DOCX por: (a) decisão humana
  obrigatória ainda não respondida — Reconvenção
  (INV-RECONVENCAO-AUTORIZACAO-EXPRESSA) ou licitude de corte/suspensão
  com `CORTE_EFETIVO: true` (INV-CORTE-GATE-HUMANO), perguntando SOMENTE
  a decisão pendente, nunca as duas por hábito, e nunca de novo se o
  advogado já respondeu no pedido inicial; ou (b) fail-closed
  técnico/fático real já previsto neste documento (bloco `INDETERMINADO`,
  tempestividade sem marco, `JUIZO` não resolvível via DataJud, valor
  contraditório não resolvível documentalmente, documento indispensável
  ilegível) — respondida a pergunta, o fluxo retoma automaticamente até
  o DOCX, sem voltar a entregar análise estratégica ou qualquer artefato
  interno como se fosse a entrega final. Pedidos que não solicitam a peça
  ("analise este processo", "quais teses cabem?") permanecem em `MODO
  ANÁLISE`/`MODO CONSULTIVO` — nesses, a análise/resposta pontual é a
  entrega correta, e esta invariante não se aplica. Detalhe operacional
  em `skills/contestacao/SKILL.md` §11 e `skills/estrategista-
  contestacao-ede/SKILL.md` §9 (que passa a distinguir se foi acionada
  pela orquestração — não entrega a análise ao usuário — ou diretamente
  pelo advogado — aí sim entrega e sugere próximo passo); auditoria e
  origem do achado em `docs/specs/SPEC-0001.md` §54.

---

## 8. Tempestividade

Toda análise de tempestividade relativa ao TJBA em 2026 deverá utilizar:

`calendario-forense-tjba-2026`

Quando a questão estiver abrangida pelo escopo dessa Skill, sua utilização
é obrigatória. Nenhuma Skill processual (`contestacao` incluída) deverá
calcular autonomamente calendário forense — dias úteis, feriados,
suspensões — quando `calendario-forense-tjba-2026` cobrir o caso; ela
orquestra o acionamento, não reimplementa o cálculo.

Não declare tempestividade sem dados suficientes.

Não invente:

* data de publicação;
* data de ciência;
* feriado;
* suspensão;
* termo inicial;
* termo final.

Quando os dados forem insuficientes, sinalize a pendência.

Sinalizar a pendência não basta para permitir a conclusão da peça: a
Contestação não pode alcançar a etapa de redação final/template com
tempestividade pendente. Quando o marco temporal (citação, intimação ou
publicação) não estiver documentalmente identificado com proveniência, a
Skill `contestacao` deve perguntar obrigatoriamente ao advogado antes de
prosseguir — nunca presumir, nunca deixar `PENDENTE DE VALIDAÇÃO`
alcançar o documento final. Formalizada na SPEC como
`INV-TEMPESTIVIDADE-MARCO` (SPEC-0001 §5).

**INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM (Etapa 5.5)** — decisão de
produto fixa e permanente: esta Contestação sempre calcula tempestividade
pelo procedimento comum do CPC (15 dias, dias úteis, art. 335 do CPC).
Nunca a lógica do Juizado Especial (Lei 9.099/95), mesmo quando o caso
concreto tramitar por um rito que admitiria aplicação subsidiária dela —
`scripts/gerar_contestacao.py` aplica esse padrão fixo quando
`tempestividade.json` não especifica prazo/tipo/fundamento, e aborta se
algo incompatível for especificado (nunca escolhe silenciosamente outro
rito). Cálculo e redação são coisas diferentes: a memória de cálculo
completa (marco, termo inicial, dias úteis, termo final) fica só na
auditoria interna do pipeline — o placeholder `TEMPESTIVIDADE_CASO`
recebe prosa jurídica natural e curta, nunca dump robótico
("TEMPESTIVO: termo inicial ..., termo final ..."), nunca data em
formato ISO, nunca menção à Lei 9.099/95/Juizado Especial. Backstop
lexical em `scripts/validate_placeholder_semantics.py` (não exaustivo).

---

## 9. Integridade jurídica

Nunca invente:

* dispositivo legal;
* artigo;
* resolução;
* súmula;
* enunciado;
* precedente;
* número processual;
* ementa;
* tese jurisprudencial;
* conteúdo de decisão.

Sempre que houver fonte disponível no RAG, prefira o conteúdo recuperado e verificável à memória do modelo.

---

## 10. RAG jurídico

O RAG é a camada de conhecimento jurídico do projeto.

As Skills não devem conter cópias extensas da legislação.

Fluxo esperado:

```text
Skill
  ↓
consulta jurídica
  ↓
RAG
  ↓
busca lexical + vetorial
  ↓
reranking
  ↓
fontes recuperadas
  ↓
validação
  ↓
redação
```

Mantenha o RAG desacoplado das Skills.

### INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL (achado do Teste Real 01-B)

A Contestação é autossuficiente e estrita ao modelo institucional: sua
elaboração não realiza pesquisa jurisprudencial de espécie alguma. Isto é
**decisão arquitetural permanente da peça** — não uma restrição temporária
decorrente de `PEND-002` estar aberta, e não muda se/quando `PEND-002` for
resolvida (indexar jurisprudência no RAG é decisão sobre a infraestrutura
do RAG, não autorização para a Contestação consumi-la). A execução de
`/contestacao` nunca: pesquisa jurisprudência (RAG, web, ou qualquer outro
meio); aciona Jurisprudências.ai ou equivalente; aciona MCP de
jurisprudência (o plugin não declara nenhum — `.claude-plugin/
plugin.json`); aciona agente/subagente de jurisprudência; usa busca web ou
API jurisprudencial; consulta tribunal; solicita automaticamente ao
advogado que pesquise; ou interrompe a geração por ausência de
jurisprudência — mesmo que tal recurso esteja disponível na sessão por
integração alheia ao plugin (disponibilidade não é autorização de uso).
A Contestação prossegue sempre com o conteúdo-base institucional do
modelo, o corpus local (legislação/regulamentos já indexados) e a
validação jurídica existente; súmula/precedente só aparece onde já
preservado no conteúdo-base fixo do modelo, nunca acrescentado durante a
elaboração de um caso. Detalhe operacional em `skills/contestacao/
SKILL.md` §7; auditoria e origem do achado em `docs/specs/SPEC-0001.md`
§46.

---

## 11. Separação fato × direito

Nunca misture:

`FATOS DO PROCESSO`

com:

`CONHECIMENTO JURÍDICO`

Fatos devem derivar dos documentos ou de informação expressamente fornecida pelo advogado.

Conhecimento jurídico deve derivar das fontes jurídicas disponíveis.

O RAG não é fonte de fatos processuais.

---

## 12. Regra anti-hallucination

Uma afirmação jurídica específica que dependa de fonte deve ser verificável.

Para citações:

```text
citação proposta
      ↓
fonte encontrada?
      ↓
SIM → validar
NÃO → pesquisar novamente
      ↓
continua sem fonte?
      ↓
não utilizar como citação confirmada
```

Nunca complete uma referência jurídica por plausibilidade.

---

## 13. Template oficial

O template institucional da Contestação é protegido.

Arquivo esperado:

`templates/contestacao/modelo-oficial.docx`

Todo conteúdo que não seja placeholder autorizado ou seção condicional mapeada deve permanecer intocado.

**Decisão definitiva (ADR-0009):** este arquivo é asset externo ao
plugin — nunca commitado, nunca distribuído com o pacote público,
fornecido separadamente aos usuários autorizados. Não voltar a
apresentar alternativas sobre publicá-lo junto do plugin; a decisão está
encerrada.

Implementações futuras não deverão:

* commitar `modelo-oficial.docx` real no repositório;
* baixar, buscar ou reconstruir automaticamente o timbrado (internet,
  IA, template genérico) quando ausente;
* tratar a ausência do template como instalação inválida do plugin — é
  o comportamento esperado antes do fornecimento externo;
* misturar esse arquivo com jurisprudência real (`rag/jurisprudencia/`,
  ver §10) na distribuição pública — ambos são excluídos pelo mesmo
  princípio de proteção de asset sensível, mas por motivos distintos.

Quando a geração do DOCX final for solicitada sem o template presente,
interrompa somente essa etapa (Fail Closed — §17), nunca o restante do
pipeline que não depende dele.

---

## 14. Placeholders autorizados

Lista real, auditada diretamente em `templates/contestacao/modelo-oficial.docx`
(Fase 3) — substitui a lista hipotética original desta seção; ver
`docs/specs/SPEC-0001.md REQ-014` para a justificativa da divergência:

```text
{{JUIZO}}
{{NUMERO_PROCESSO}}
{{AUTOR}}
{{TEMPESTIVIDADE_CASO}}
{{SINOPSE_FATOS}}
{{REALIDADE_FATICA}}
{{IRREGULARIDADE_ENCONTRADA}}
{{DESENVOLVIMENTO_TECNICO_IRREGULARIDADE}}
{{FOTOS_DA_IRREGULARIADE}}
{{VALOR_FRA}}
{{VALOR_DANO_MORAL_PRETENDIDO}}
{{PEDIDOS_FINAIS}}
{{LOCAL_DATA}}
```

Não crie novos placeholders silenciosamente.

Alteração do contrato de placeholders exige atualização do schema e, quando aplicável, da SPEC.

### Remoção definitiva de `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA`

Decisão definitiva, não uma pausa temporária: o placeholder
`{{ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA}}` foi removido de toda a
arquitetura da Contestação (schema, catálogo de blocos, validadores,
fixtures, testes, documentação) — não renomeado, não substituído por
equivalente. O texto institucional sobre evolução de consumo pertence
exclusivamente ao modelo oficial (bloco `EVOLUCAO_CONSUMO`, hoje
`CONDICIONAL_PADRAO` — inteiramente fixo, sem placeholder próprio); a
IA nunca mais gera nem parafraseia essa argumentação. Quando o bloco
está `INCLUIR`, só o texto fixo aparece; se faltar dado concreto do
caso para eventual complementação casuística em outro campo já
existente, nenhuma argumentação genérica é criada para preencher
espaço — o texto fixo do modelo basta. Não crie um novo placeholder
equivalente sob outro nome sem autorização expressa.

### INV-CONTESTACAO-SEM-TRAVESSAO — correção pontual pós-teste real

Achado real: `redator-peca-processual-elite` e `humanizer-pt-br`
estavam inserindo o travessão ("—", U+2014) no texto da Contestação.
Proibido: nenhum conteúdo textual gerado, reescrito, humanizado ou
complementado pela IA para os placeholders da Contestação pode conter
esse caractere — use pontuação convencional (vírgula, ponto, ponto e
vírgula, dois-pontos, parênteses), nunca como recurso estilístico. A
regra é independente do comportamento probabilístico das Skills:
`scripts/validate_placeholder_semantics.py` (`_checar_travessao`) roda
um backstop determinístico sobre todo placeholder fornecido, antes do
Template Engine — travessão encontrado aborta o pipeline
(`PIPELINE_ABORTED`, stage `placeholders`), nunca é substituído
automaticamente por vírgula/hífen (a pontuação correta depende da
estrutura sintática da frase, decisão do Redator/Humanizer, não deste
validador). Escopo: só o conteúdo variável produzido pela IA — texto
institucional fixo do modelo oficial nunca é alterado por esta regra,
mesmo que eventualmente contenha travessão.

### INV-JUIZO-DATAJUD — {{JUIZO}} deixa de ser conteúdo gerativo

`{{JUIZO}}` não é mais redigido/inferido pela IA. É resolvido
deterministicamente por `scripts/datajud_client.py`, a partir de
`NUMERO_PROCESSO`: identifica o tribunal pelo número CNJ, consulta a API
Pública DataJud/CNJ para o órgão julgador real do processo, resolve a
comarca via API do IBGE (`codigoMunicipioIBGE`) e monta o padrão
institucional `AO JUÍZO DA [unidade judiciária real] DA COMARCA DE
[comarca real]`, em caixa alta — nunca um exemplo ilustrativo. Escopo
suportado (segmento do número CNJ): 8 (Justiça Estadual, 27 UFs), 4
(Justiça Federal, TRF1-TRF6), 3 (STJ) — demais segmentos falham
explicitamente (fail closed), nunca "chutam" um alias. Fail-closed
(`PIPELINE_ABORTED`, `stage=juizo_datajud`) se: DataJud indisponível,
processo não encontrado, múltiplos resultados incompatíveis, órgão
julgador ausente na resposta, alias não determinável, ou
`placeholders.json` trouxer um `JUIZO` próprio (rejeitado, nunca
usado/reconciliado). **API key (Etapa 5.5 — decisão expressa do
projeto, substitui a orientação anterior)**: a chave PÚBLICA do DataJud
é versionada no repositório, num único ponto canônico
(`DATAJUD_API_KEY_PADRAO` em `scripts/datajud_client.py`) — plugin
autossuficiente, sem configuração manual pelo advogado. Não reproduzir
essa chave em nenhum outro arquivo; demais módulos consomem
`resolver_juizo`/`resolver_orgao_julgador`. `DATAJUD_API_KEY` (variável
de ambiente) continua aceita como override, útil se o CNJ rotacionar a
chave antes do código ser atualizado. Erro de autenticação (credencial
inválida/expirada) é marcado (`TAG_ERRO_AUTENTICACAO`) e nunca degrada
para JUIZO gerativo nem busca/inventa nova chave automaticamente — exige
atualização manual de `DATAJUD_API_KEY_PADRAO`. O secret scan do projeto
trata esta chave especificamente como exceção expressa (não é mais
"possível segredo vazado"); demais credenciais continuam proibidas de
versionamento (CLAUDE.md §18). Cache local (`.cache/datajud/`,
gitignored) evita nova consulta para o mesmo processo em elaboração em
massa.

O campo `orgaoJulgador.nome` retornado pelo DataJud constitui a fonte de
verdade da denominação da unidade judiciária. O plugin não deve expandir,
corrigir, reinterpretar ou substituir automaticamente abreviações ou a
nomenclatura oficial retornada pela fonte.

### Calibração final de conteúdo (Etapa 5.3, achados do Teste Real 01-B)

Sete achados reais e suas correções — detalhe completo em
`docs/specs/SPEC-0001.md` §47 e `skills/contestacao/SKILL.md` §9:

- **Endereçamento** (`JUIZO`): caixa alta, padrão institucional `AO
  JUÍZO DA VARA [...] DA COMARCA DE [...]`, nunca construção improvisada.
- **Meta-informação proibida**: o documento final nunca revela sua
  própria mecânica de obtenção/validação de dado ("conforme informado
  pelo advogado", "conforme o RAG", etc.) — proveniência é interna.
- **Densidade por bloco**: 380 caracteres é teto por parágrafo, não meta;
  cada campo multiline tem também um limite de bloco (soma dos
  parágrafos) contra acumulação — `scripts/validate_paragrafos.py`.
- **Irregularidade em destaque**: nome do tipo em `**negrito**` (revisado
  na Etapa 5.3-B — ver abaixo, substitui "caixa alta" por contrato
  atômico + minúsculas/natural); TOI nunca menciona assinatura.
- **Modelo fornece o direito**: a redação variável faz subsunção ao caso
  concreto, não reexplica artigo por artigo o que o modelo já traz
  (reforça INV-NAO-REDUNDANCIA-NORMATIVA, §7); RAG valida/complementa,
  nunca gera exposição normativa nova.
- **`PEDIDOS_FINAIS` curto e composicional**: núcleo é "julgar
  improcedentes os pedidos da inicial"; nunca menciona tese/bloco
  excluído pelo motor composicional (`validar_pedidos_composicionais`,
  determinístico).
- **`LOCAL_DATA` sempre Salvador**, independentemente da comarca do
  processo.

### Normalização visual de parágrafos e contrato atômico da irregularidade (Etapa 5.3-B)

Correção decorrente de achado real do Teste 5.3: parágrafos gerados pela
IA para placeholders multiline (`SINOPSE_FATOS`, `REALIDADE_FATICA`
etc.) apareciam visualmente diferentes dos parágrafos nativos do modelo
— causa raiz confirmada (não heurística): cada linha lógica virava
`<w:br/>` dentro de um único `<w:p>`, então `w:spacing`/`w:before`/
`w:after`/`contextualSpacing` do parágrafo (aplicados por unidade `<w:p>`
no OOXML) só se aplicavam UMA vez ao bloco inteiro, não entre as linhas.

- **INV-PARAGRAFO-HERDA-TEMPLATE**: todo `<w:p>` novo criado a partir de
  conteúdo multiline de um placeholder deve herdar estruturalmente
  (clonagem/deep copy do `w:pPr`, nunca reconstrução propriedade a
  propriedade) as propriedades do parágrafo-placeholder que lhe deu
  origem — nunca um estilo visual próprio do pipeline. TEMPLATE define
  aparência; PIPELINE só fornece conteúdo. Implementado em
  `scripts/docx_template_engine.py`
  (`_explodir_paragrafos_multilinha`): cada linha lógica de um valor
  multiline vira um `<w:p>` irmão real, não uma quebra de linha. A
  detecção de qual `<w:br/>`/`<w:t>` pertence à expansão é feita por
  marcador explícito em namespace próprio (nunca por inferência
  vermelho+quebra, frágil) — removido do XML antes de alcançar o schema
  OOXML; quebras legítimas pré-existentes do template nunca são tocadas.
  Idempotente por construção (só consome marcadores, nunca cria novos).
- **Contrato atômico de `IRREGULARIDADE_ENCONTRADA`**: o campo contém
  EXCLUSIVAMENTE o nome/tipo da irregularidade, em `**negrito**`,
  minúsculas/redação natural (ressalvados nomes próprios/siglas) — nunca
  repete o texto fixo do template que já envolve o placeholder ("Na
  ocasião, foi constatada irregularidade do tipo, " / ", circunstância
  que impedia o registro integral..."). A explicação técnica do tipo vai
  em `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE`, nunca dentro deste campo.
  Backstop lexical específico (não genérico) em
  `scripts/validate_placeholder_semantics.py`
  (`_validar_irregularidade_encontrada`).

### INV-VALOR-DANO-MORAL-DOCUMENTAL — correção pontual (13º placeholder)

`{{VALOR_DANO_MORAL_PRETENDIDO}}` foi inserido manualmente pelo advogado
no modelo oficial, dentro do bloco condicional `DESCABIMENTO_DANO_MORAL`
("...ao pagamento de indenização por danos morais no valor de
`{{VALOR_DANO_MORAL_PRETENDIDO}}`, contudo, a mera formulação de
pretensão indenizatória não se revela suficiente..."). Representa
exclusivamente o valor da indenização por danos morais efetivamente
pretendido pela parte **autora** na petição inicial — dado factual
documental, nunca gerado/estimado/arredondado pelo Redator, Humanizer ou
Estrategista, e nunca confundido com valor da causa, dano material,
multa, astreintes ou qualquer outro pedido econômico distinto.

Só é exigido quando `DESCABIMENTO_DANO_MORAL` está `INCLUIR` (autora
formulou pedido de dano moral) — ausência de pedido mantém o bloco
`EXCLUIR` e o placeholder some junto com ele, automaticamente (o SDT
inteiro é removido antes da substituição; nenhuma regra adicional em
`blocos.json` é necessária, diferente de `VALOR_FRA`/`RECONVENCAO`).
Pedido de dano moral sem quantificação na inicial ("a ser arbitrado pelo
Juízo") é conteúdo legítimo, nunca vira fail-closed obrigatório como a
sentinela de ausência de `VALOR_FRA` — mas nunca pode ser impresso como a
sentinela literal ("NÃO ESPECIFICADO"/"NÃO INFORMADO"). Valores
monetários divergentes no mesmo campo (inicial contraditória ou
extração incerta) são fail-closed: nunca escolher automaticamente
maior/menor/último, sempre confirmar com o advogado. Formato monetário
brasileiro obrigatório quando há quantia (`R$ 10.000,00`, nunca
`10000`/`R$10000`/`10.000`/formato americano). Backstop determinístico
em `scripts/validate_placeholder_semantics.py`
(`_validar_valor_dano_moral_pretendido`). Detalhe completo em
`docs/specs/SPEC-0001.md` §53. 12→13 placeholders — não reabre a
discussão do `VALOR_DANO_MORAL` original (removido na auditoria de Fase
3, REQ-014): este é homônimo, mas semanticamente distinto (valor citado
defensivamente no tópico de descabimento, não um pedido de dano moral
que este modelo de Contestação nunca formula).

---

## 15. Template Lock

Nunca contorne o Template Lock para fazer uma geração "funcionar".

Se a validação estrutural falhar:

**a geração deve falhar.**

Não liberar DOCX final como válido quando houver alteração não autorizada.

---

## 16. Manipulação de DOCX

Não reconstruir o documento inteiro quando o objetivo for preencher o template.

Preserve, sempre que tecnicamente aplicável:

* estilos;
* runs;
* fontes;
* cabeçalhos;
* rodapés;
* tabelas;
* imagens;
* hyperlinks;
* margens;
* espaçamento;
* elementos institucionais.

Sempre trabalhar sobre cópia.

Nunca sobrescrever o template mestre durante a geração de uma peça.

---

## 17. Fail Closed

Em matéria jurídica ou documental, prefira falhar explicitamente a gerar resultado silenciosamente incorreto.

Exemplos:

```text
fonte jurídica não validada
→ não inventar

tempestividade inconclusiva
→ sinalizar

placeholder ausente
→ falhar

template alterado indevidamente
→ falhar

documento processual ilegível
→ sinalizar
```

---

## 18. Segurança

Este projeto poderá possuir repositório público.

Nunca versionar:

* `.env`;
* API keys;
* tokens;
* senhas;
* credenciais;
* documentos reais de clientes;
* processos sigilosos;
* dados pessoais desnecessários;
* secrets;
* arquivos locais de trabalho.

Use `.env.example` apenas com nomes de variáveis e valores fictícios.

---

## 19. Workspace

Documentos processuais utilizados durante elaboração de peças devem permanecer fora do versionamento.

Diretórios locais de trabalho devem constar no `.gitignore`.

---

## 20. Dependências

Não adicione biblioteca sem necessidade concreta.

Antes de adicionar dependência, considere:

* necessidade;
* manutenção;
* licença;
* segurança;
* estabilidade;
* peso;
* alternativa já disponível.

---

## 21. Testes

Não considere uma implementação concluída apenas porque o código foi escrito.

Execute os testes aplicáveis.

Nunca:

* esconda teste falhando;
* remova teste apenas para obter verde;
* enfraqueça assertion sem justificativa;
* altere fixture para mascarar regressão.

Corrija a causa da falha.

---

## 22. Regressões

Antes de concluir uma fase:

1. execute os testes novos;
2. execute testes relacionados;
3. execute a suíte completa quando razoável;
4. informe qualquer falha preexistente separadamente.

---

## 23. Commits

Prefira commits pequenos e semanticamente coerentes.

Um commit deve representar uma unidade lógica de mudança.

Evite misturar:

* feature;
* refatoração não relacionada;
* documentação não relacionada;
* correções oportunistas.

---

## 24. Git

Não execute operações destrutivas sem autorização explícita.

Evite especialmente:

```text
git reset --hard
git clean -fd
git push --force
```

Não descarte alterações locais desconhecidas.

Antes de operações relevantes, consulte `git status`.

---

## 25. Atualização

O mecanismo de atualização deverá preservar configurações locais.

A experiência desejada é equivalente a:

`/updateEde`

O advogado usuário do plugin não deverá precisar conhecer Git para atualizar a instalação.

---

## 26. Compatibilidade com Claude Code

Não invente:

* comandos;
* hooks;
* propriedades de manifest;
* APIs;
* mecanismos de plugin;
* comportamento de marketplace;
* sintaxe MCP.

Quando a implementação depender do comportamento atual do Claude Code, consulte a documentação oficial vigente.

---

## 27. Expansão futura

### Invariante — Trava de validação humana da Contestação (INV-GATE-CONTESTACAO)

> A Contestação é a única peça processual autorizada para desenvolvimento,
> estabilização, correção e testes no estágio atual do EDE Legal Plugin.
> É vedado iniciar, projetar, implementar, antecipar, criar scaffolding,
> criar templates, criar Skills, criar estrategistas, criar catálogos de
> blocos ou realizar refatorações destinadas especificamente à inclusão
> de Recurso Inominado, Embargos, manifestações ou qualquer outra nova
> peça processual enquanto a Contestação não tiver sido validada
> integralmente pelo usuário em utilização real. Testes automatizados,
> cobertura E2E, validação estrutural, aprovação técnica ou declaração de
> estabilidade pelo agente não substituem a validação humana do usuário.
> A liberação para expansão do projeto dependerá de manifestação expressa
> do usuário após sua validação prática da Contestação.

Consequência prática: **141/141 testes verdes ≠ Contestação validada.**
Testes automatizados demonstram validação técnica — nunca validação
profissional, jurídica final, visual final, operacional, em casos reais,
ou aprovação da Contestação pelo usuário. Enquanto esta invariante
estiver ativa, nunca declare a Contestação "validada", "concluída
definitivamente", "pronta para produção" ou "100% aprovada" — a
formulação correta é "tecnicamente apta para testes reais, não validada
pelo usuário". A validação final é sempre uma manifestação expressa do
usuário ("CONTESTAÇÃO VALIDADA" ou equivalente inequívoco), nunca inferida
de suíte verde, CI ou relatório do agente.

Enquanto ativa, permanece autorizado testar, corrigir, melhorar,
documentar e criar regressão para a Contestação existente; permanece
vedado iniciar qualquer nova peça processual (Skill, template, catálogo
de blocos, schema, fixture, pipeline) ou generalizar prematuramente a
arquitetura para acomodar peças futuras ainda não autorizadas (nada de
`piece_registry`/`piece_factory`/`base_piece` ou equivalente só porque
"poderá ser útil depois") — a abstração multipeça só se justifica quando
necessária para corrigir a própria Contestação, ou após o usuário liberar
expressamente a expansão. Novos tipos de peça deverão reutilizar os
componentes transversais.

Exemplo esperado:

```text
skills/
├── contestacao/
├── recurso-inominado/
├── embargos-de-declaracao/
└── ...
```

e:

```text
templates/
├── contestacao/
├── recurso-inominado/
├── embargos-de-declaracao/
└── ...
```

Não duplique o Core para implementar nova peça.

---

## 28. Critério de conclusão de tarefa

Antes de declarar uma tarefa concluída, informe:

1. o que foi implementado;
2. arquivos criados;
3. arquivos modificados;
4. testes executados;
5. resultado dos testes;
6. requisitos da SPEC atendidos;
7. pendências conhecidas;
8. riscos remanescentes.

Não declare "concluído" quando houver erro conhecido relevante.

---

## 29. Regra de escopo

Quando receber:

`Implemente a Fase N`

isso significa:

**implementar somente a Fase N.**

Não utilizar a autorização como permissão genérica para implementar fases subsequentes.

---

## 30. Fonte normativa do projeto

A SPEC vigente define os requisitos.

Os ADRs registram decisões arquiteturais.

As Skills definem comportamentos especializados.

O `CLAUDE.md` estabelece as regras permanentes de trabalho do agente.

Preserve essa separação durante toda a evolução do projeto.
