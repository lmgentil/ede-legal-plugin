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
  `requires_fact` (abaixo) — este é vínculo, não gate.
- **INV-CORTE-EFETIVO** — `LICITUDE_CORTE_SUSPENSAO` só é elegível a
  `INCLUIR` se o fornecimento tiver sido efetivamente cortado/suspenso
  (não mera ameaça ou pedido preventivo) — GATE `requires_fact:
  CORTE_EFETIVO` no catálogo (`decision_mode` continua `"estrategista"`,
  a decisão INCLUIR/EXCLUIR quando o fato é verdadeiro continua sendo da
  etapa estratégica), validado por `scripts/docx_block_engine.py` a
  partir de `estado_processual.json`. Nem este gate nem o vínculo de
  gratuidade aceitam ocorrência lexical ("não houve corte" no texto de um
  documento nunca vira `CORTE_EFETIVO: true`) como prova — o estado é
  resolvido pela Skill `contestacao` a partir dos documentos, com
  proveniência, nunca por busca textual.
- **INV-NAO-REDUNDANCIA-NORMATIVA** — a redação variável não repete
  dispositivo normativo já presente no tópico-base institucional fixo do
  modelo; o RAG valida/complementa fundamentação, não é gerador de lista
  de artigos.

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

### INV-JURISPRUDENCIA-EXTERNA-DESABILITADA (achado do Teste Real 01-B)

Enquanto `PEND-002` (indexação de jurisprudência real na busca híbrida)
permanecer não implementada, nenhuma Skill do EDE Legal Plugin aciona,
direta ou indiretamente: Jurisprudências.ai ou equivalente; agente/
subagente externo de jurisprudência/precedentes; MCP de jurisprudência
(o plugin não declara nenhum — `.claude-plugin/plugin.json`); ou qualquer
API/ferramenta externa de pesquisa jurisprudencial — mesmo que disponível
na sessão por integração alheia ao plugin. A ausência de jurisprudência
indexada nunca autoriza buscá-la por outro caminho; a Contestação
prossegue sem citação jurisprudencial, usando o conteúdo-base do modelo,
o corpus local (legislação/regulamentos já indexados) e a validação
jurídica existente. `"PESQUISA JURISPRUDENCIAL NECESSÁRIA."` é marcador
textual de lacuna, nunca instrução de busca. Detalhe operacional em
`skills/contestacao/SKILL.md` §7.

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
{{ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA}}
{{VALOR_FRA}}
{{PEDIDOS_FINAIS}}
{{LOCAL_DATA}}
```

Não crie novos placeholders silenciosamente.

Alteração do contrato de placeholders exige atualização do schema e, quando aplicável, da SPEC.

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
