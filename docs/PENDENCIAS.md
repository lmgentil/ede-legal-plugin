# Pendências — EDE Legal Plugin

Registro formal de pendências técnicas/funcionais abertas durante a
implementação, com ID rastreável, fase de origem, fase de bloqueio (quando
houver) e critério objetivo de resolução. Complementa — não substitui —
os `REQ-`/`INV-`/`TEST-` de `docs/specs/SPEC-0001.md` e os ADRs de
`docs/adr/`: uma pendência aqui é um item de trabalho conhecido e ainda não
resolvido; um REQ/INV é um requisito permanente da arquitetura; um ADR é
uma decisão já tomada.

Nenhuma pendência com fase de bloqueio deve ser resolvida silenciosamente
nem adiada além da fase indicada sem nova decisão explícita do usuário
(`CLAUDE.md §6/§17`).

| ID | Status | Aberta na | Bloqueia | Descrição |
|---|---|---|---|---|
| PEND-001 | DEFERRED | Fase 3 | Nenhuma (deferida por decisão do usuário — correção v0.6.1) | Suporte multimídia ao placeholder `FOTOS_DA_IRREGULARIADE` |
| PEND-002 | ABERTA | Fase 4 | Nenhuma (adiada por decisão do usuário) | Indexação de jurisprudência (REQ-018) na busca híbrida |
| PEND-003 | RESOLVIDA (ADR-0013) | Fase 8 | — | `svd.joblib` reduzido de 77,34 MiB para 34,19 MiB com `float32` + zlib, preservando fallback offline e gold-set |
| PEND-004 | RESOLVIDA (gate PEND-004) | Fase 8 | — | Definir licença proprietária/source-available compatível com repositório público e distribuição do plugin |
| PEND-005 | ABERTA | Etapa 5 | Nenhuma (dívida estrutural; a renumeração dinâmica atual elimina lacunas) | Subtítulos ainda não migrados para lista multinível nativa do Word |
| PEND-006 | RESOLVIDA (causa eliminada) | Etapa 5 | — | Ambiguidade da fronteira de `EVOLUCAO_CONSUMO` eliminada com a retirada do placeholder duplicado |
| PEND-007 | RESOLVIDA (Commits 3-7.2 da Etapa 5.10) | Etapa 5.9 | — | Dependência runtime do skill "docx" de terceiro (Anthropic) — não redistribuível por licença e com contrato obsoleto frente à versão atualmente publicada |
| PEND-008 | ABERTA | Etapa 5.10, Microfix 7.1 | Nenhuma (não bloqueante — partes OOXML byte-idênticas ao canônico) | Segundo asset de teste `modelo-oficial_topicos-2.3-a-2.6_contratados.docx` é legado/redundante |
| PEND-009 | ABERTA | Etapa 5.10, Microfix 7.1 | Nenhuma (dívida arquitetural pré-existente, não introduzida pela Etapa 5.10) | `docx_numeracao_engine.py` localiza títulos de nível 2/3 por âncoras de texto hardcoded do Modelo Oficial real, não derivadas de `blocos.json` |
| PEND-010 | ABERTA | Etapa 5.10, Commit 7 | Declaração de validação visual automatizada em release público (não bloqueia runtime/distribuição técnica) | Inspeção visual automatizada do DOCX final ainda não executada — nenhum renderizador DOCX legítimo disponível no ambiente de homologação |
| PEND-011 | ABERTA | Primeira chamada viva do ChatGPT a `ede_finalizar_peca` (2026-09-22) | Declaração de interoperabilidade do finalizador com o ChatGPT (não bloqueia o runtime; o servidor já recusa quando a inflação estoura o limite) | Transporte do cliente ChatGPT inseriu quebras de linha nos valores de placeholder; abaixo do limite de densidade isso passaria sem detecção |
| PEND-012 | ABERTA (escopo ampliado) | Gate 6.6-D, chamadas do ChatGPT e do Claude (2026-09-22) | Critério de entrega nativa do Gate 6.6-D, ENCERRADO como PARTIAL PASS com esta pendência aberta; não bloqueia o runtime nem motiva rollback | Nem ChatGPT nem Claude entregam o DOCX nativamente via `EmbeddedResource` — ChatGPT não expõe a URI `attachment://` (contorno do host preserva os bytes); Claude recusa explicitamente o tipo de mídia do DOCX (nenhum byte chega ao usuário) |
| PEND-013 | APROVADA, execução ADIADA | Auditoria somente-leitura das revisões antigas com tag, Gate 6.6-D item 6 (2026-09-22) | Nenhuma (não bloqueia; execução deliberadamente adiada para depois da evidência de interoperabilidade viva do Claude) | Remoção das seis tags históricas do Cloud Run (`candidato`, `candidato-6-5-b`, `candidato-6-5-b2`, `candidato-6-5-c`, `candidato-6-5-c2`, `candidato-6-5-c4`) — aprovada em princípio como *pre-pilot hardening*, nenhuma removida ainda |
| PEND-014 | CANDIDATO IMPLEMENTADO E PROVADO AO VIVO (Gate 6.6-E, incl. limpeza agendada); download ao vivo Claude/ChatGPT e ativação em produção NÃO autorizados | Fechamento do Gate 6.6-D como PARTIAL PASS (2026-09-22); implementação Gate 6.6-E mesma data | Gate de download ao vivo (Claude/ChatGPT); não bloqueia o runtime — produção continua em v1 até ativação explícita | Redesenho do mecanismo de entrega de artefato entre hosts — v2 (`scripts/artifact_storage.py`, GCS efêmero + URL V4 assinada de 24h) implementado, testado e verificado ao vivo: assinatura real, identidade de bytes, hard delete, e limpeza agendada horária (Cloud Scheduler -> Cloud Run Job) provisionada em homologação |

---

## PEND-001 — Suporte multimídia ao placeholder `FOTOS_DA_IRREGULARIADE`

**Status:** DEFERRED (decisão superveniente em 2026-08-18 — correção
arquitetural v0.6.1; ver seção "Decisão superveniente" abaixo)
**Aberta em:** Fase 3 (auditoria de `templates/contestacao/modelo-oficial.docx`)
**Bloqueava:** Fase 7 — End-to-End, até a decisão superveniente abaixo.
**Bloqueia agora:** nenhuma fase.

### Contexto

A auditoria da Fase 3 encontrou `{{FOTOS_DA_IRREGULARIADE}}` (nome com erro
de digitação no próprio DOCX — falta o "D" de "IRREGULARIDADE"; mantido
literal em `schema.json` porque a engine precisa casar com o token real)
sozinho em seu próprio parágrafo/run, com a mesma formatação de destaque
(vermelho, `color="EE0000"`) usada pelos demais placeholders textuais do
template. A auditoria não determinou se o campo deve receber:

* **(a)** texto/legenda descrevendo a irregularidade encontrada; ou
* **(b)** imagem(ns) real(is) da irregularidade embutida(s) no corpo do
  documento (fotos do TOI, do medidor, do local, etc.).

`scripts/docx_template_engine.py` (Fase 3) trata este placeholder como
texto simples — substituição cirúrgica em nó `<w:t>`, igual aos demais 12
placeholders do schema. **Não há, hoje, suporte a inserção de imagem**
(elemento `<w:drawing>`/`r:embed`, parte de relacionamento em
`word/_rels/document.xml.rels`, arquivo novo em `word/media/`) na engine.

### Risco se não resolvido

Se o uso pretendido for (b), a Contestação final sairá sem a prova visual
da irregularidade. Neste fact-pattern (defesa por irregularidade/fraude em
medição de energia, com Termo de Ocorrência e Inspeção), fotos do TOI/do
medidor podem ser elemento probatório relevante para a tese. Gerar a peça
com esse campo preenchido só como texto, quando o padrão real do escritório
exige a imagem, seria uma lacuna silenciosa — incompatível com o princípio
de Fail Closed (`CLAUDE.md §17`, `SPEC-0001 INV-006`).

### Critério de resolução

1. Confirmar com o usuário (fonte da peça original / prática do
   escritório) qual o uso real do campo: texto ou imagem embutida.
2. **Se imagem:** estender `docx_template_engine.py` para aceitar dados de
   imagem (formato de entrada a definir — ex.: lista de caminhos de
   arquivo), implementando inserção controlada de `<w:drawing>` + relação
   + cópia para `word/media/`. `verificar_template_lock()` precisará
   reconhecer mídia nova em posição de placeholder autorizado como
   substituição legítima, não como violação (hoje qualquer arquivo novo em
   `word/media/` reprova o Template Lock por design).
3. **Se texto:** nenhuma mudança de código necessária — só documentar a
   decisão aqui e fechar esta pendência.
4. Atualizar `templates/contestacao/schema.json` (e este registro) com o
   resultado.
5. Adicionar teste de regressão cobrindo o caminho escolhido em
   `tests/test_template_engine.py`.

### Decisão superveniente (2026-08-18 — correção arquitetural v0.6.1)

Resolve o item 1 do "Critério de resolução" acima: confirmado com o
usuário que, **na V1**, o campo `FOTOS_DA_IRREGULARIADE` **não** recebe
inserção automática de imagem. Fotografias da irregularidade serão
inseridas **manualmente pelo advogado**, no DOCX já gerado, depois que a
Contestação sair do plugin.

Isso corresponde à alternativa **(a) texto**, não (b) imagem — mas com uma
nuance sobre o próprio conteúdo do texto: o valor gerado para este
placeholder não deve ser uma legenda/descrição da irregularidade (isso já
é o conteúdo de `IRREGULARIDADE_ENCONTRADA`), e sim um **marcador
operacional explícito de pós-edição manual**, por exemplo:

```text
[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]
```

Consequências, aplicando literalmente o item 3 do "Critério de resolução"
("Se texto: nenhuma mudança de código necessária"):

* **Nenhuma mudança de código no Template Engine.** `docx_template_engine.py`
  já trata este campo como texto simples desde a Fase 3 — o comportamento
  atual já satisfaz a decisão. Nenhuma implementação de `<w:drawing>`,
  relacionamento de mídia, upload ou seleção automática de fotografia foi
  feita, nem está planejada para a V1.
* `templates/contestacao/schema.json` ganhou um bloco aditivo
  `placeholder_semantics.FOTOS_DA_IRREGULARIADE` (não altera
  `editable_placeholders`, que é o único campo lido pelo Template Engine —
  confirmado sem regressão em `tests/test_template_engine.py`, 10/10)
  documentando o `tratamento_v1: "manual_post_edit"` e a semântica do
  marcador esperado.
* `skills/contestacao/SKILL.md` (§9, mapeamento de placeholders) atualizado
  para refletir o marcador manual em vez de "texto/legenda... PEND-001
  aberta".
* Suporte multimídia automático **pode** ser reconsiderado em versão
  futura, mas nenhuma implementação foi antecipada nesta correção.
* Esta pendência **deixa de bloquear a Fase 7** — o gate de entrada da
  Fase 7 em `docs/specs/SPEC-0001.md` §21 foi atualizado de acordo.

### Fechamento

**DEFERRED em 2026-08-18** (correção v0.6.1) — decisão tomada e
documentada acima; nenhuma implementação de código foi necessária
(caminho "texto" do critério de resolução original). Diferente de
"RESOLVIDA": não houve entrega de funcionalidade multimídia, e sim a
decisão explícita de que a V1 não a terá — automação continua em aberto
para avaliação futura, sem prazo.

---

## PEND-002 — Indexação de jurisprudência (REQ-018) na busca híbrida

**Status:** ABERTA
**Aberta em:** Fase 4 (RAG Jurídico)
**Bloqueia:** nenhuma fase — adiada por decisão explícita do usuário em
2026-08-18, sem prazo definido.

### Contexto

`docs/adr/ADR-0006-assets-institucionais.md` já registrava, desde a Fase 1,
que uma decisão explícita seria necessária antes da Fase 4 sobre
`rag/jurisprudencia/`: 57 fichas em Markdown, cada uma com bloco "Contexto
Estratégico" e tabela "Histórico de Utilização" que expõem, para casos reais
do escritório, o nome do cliente (ex.: "COELBA"), a parte contrária por nome
completo e o número do processo — além de 60 textos brutos extraídos de
`.docx` em `.textos_varredura/` (esses já tratados como workspace local,
nunca versionáveis, por decisão anterior).

Apresentadas três opções ao usuário na Fase 4 — (a) expurgar o bloco
sensível e indexar a versão pública; (b) indexar tudo como está, mantendo
`rag/jurisprudencia/` inteiro fora do git; (c) adiar a indexação de
jurisprudência e tratar só legislação/regulamentos nesta fase — a escolha
foi **(c)**.

### Efeito desta fase

* `search_hybrid.py` continua indexando somente os 434 chunks de
  legislação/regulamentos (CPC, CC, CDC, L8987, L9427, REN1000) — REQ-018
  ("jurisprudência" como tipo de conteúdo do corpus) permanece `[PARCIAL]`.
* Nenhum arquivo de `rag/jurisprudencia/` foi lido, alterado, movido ou
  incluído na fusão/reranking desta fase.
* `INV-006` (Fail Closed): como o corpus de jurisprudência não está
  indexado, uma consulta que dependa dele deve retornar confiança "baixa"
  ou nenhum resultado — nunca inventar uma citação jurisprudencial a partir
  da memória do modelo. Isso já é o comportamento de `search_hybrid.py`
  para qualquer termo fora dos 6 corpora indexados.

### Critério de resolução

Quando o usuário decidir retomar: escolher entre as opções (a)/(b) acima (ou
uma nova), executar a decisão, adicionar o corpus de jurisprudência à
ingestão/chunking/embeddings/indexação de `search_hybrid.py` e atualizar
`rag/config.yaml` (`corpus.diplomas`), `CONTEXTO_RAG.md`, este registro e
`ADR-0006`.

### Nota — INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL (achado do Teste Real 01-B)

Auditada após o achado do Teste Real 01-B ("Calling Jurisprudências.ai
5 times", `docs/specs/SPEC-0001.md` §46): esta pendência é sobre a
INFRAESTRUTURA do RAG (se/como indexar `rag/jurisprudencia/` na busca
híbrida geral do projeto) — não é, em si, "adicionar jurisprudência à
Contestação". Por isso permanece `ABERTA`, sem alteração de escopo ou
critério de resolução. O que muda: independentemente de quando/se esta
pendência for resolvida, a Skill `contestacao` **não consumirá**
jurisprudência para citação — decisão arquitetural distinta e permanente
da peça (`INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL`). As duas
decisões são independentes; resolver esta pendência não reabilita
pesquisa/uso de jurisprudência pela Contestação.

### Fechamento

Em aberto, sem prazo. Ao resolver, mover a linha da tabela para "RESOLVIDA
(Fase N)", preencher a decisão tomada e referenciar o commit/PR.

---

## PEND-003 — Tamanho de `rag/embeddings/svd.joblib` no pacote distribuído

**Status:** RESOLVIDA (ADR-0013)
**Aberta em:** Fase 8 (auditoria de distribuição)
**Resolvida em:** prioridade 8 da auditoria arquitetural, 2026-08-27.

### Contexto

`rag/embeddings/svd.joblib` (o modelo TF-IDF+LSA de fallback offline,
Fase 4) tinha 81.097.447 bytes (77,34 MiB). A matriz
`TruncatedSVD.components_`, em `float64`, respondia por praticamente todo o
arquivo.

### Risco se não resolvido

O risco era exclusivamente distributivo: instalação mais lenta e repositório
mais pesado para clonar via `/plugin marketplace add`. A incompatibilidade de
serialização/runtime permanece tratada separadamente por
`docs/adr/ADR-0011-compatibilidade-artefatos-rag.md`.

### Critério de resolução

Adotado `float32` para `components_` com compactação Joblib zlib nível 3.
O manifesto declara e o loader valida o formato antes da desserialização.
Não houve retirada do artefato, dependência nova, download posterior,
alteração de corpus, dimensão, ranking ou reconstrução na primeira execução.

### Fechamento

**Resolvida em 2026-08-27.** O artefato oficial passou a 35.848.840 bytes
(34,19 MiB), redução de 55,8%. O gold-set permaneceu em 18/24 top-1 e
21/24 top-3. Decisão e alternativas medidas: `ADR-0013`.

---

## PEND-005 — Numeração manual das subseções da Contestação não migrada para lista multinível nativa

**Status:** ABERTA
**Aberta em:** Etapa 5 (Motor Composicional de Blocos Condicionais)
**Bloqueia:** nenhuma fase — o motor atual renumera os títulos
sobreviventes e elimina lacunas; permanece apenas a dívida de migrar os
subtítulos literais para uma lista multinível nativa do Word.

### Contexto

A Etapa 4-A avaliou migrar essas subseções para lista multinível nativa
do Word e decidiu explicitamente **não improvisar**: só migrar se
comprovadamente sem regressão visual, com `numbering.xml` preservado e
teste visual+estrutural, Word abrindo sem reparo.

A implementação posterior de `scripts/docx_numeracao_engine.py` aplica
`INV-NUMERACAO-DINAMICA-CONTESTACAO`: depois da composição dos blocos,
recalcula deterministicamente os prefixos literais dos níveis 2 e 3. O
nível 1 continua sob a lista nativa já existente (`numId=17`). Saltos,
duplicidades e inconsistências hierárquicas causam fail-closed.

### Risco se não resolvido

Não há risco conhecido de lacunas na numeração final, coberta pelo motor
e por seus testes. O risco remanescente é de manutenção: os níveis 2 e 3
continuam acoplados a prefixos textuais do template e dependem do motor
determinístico, em vez de aproveitar integralmente a estrutura nativa de
listas multinível do Word.

### Critério de resolução

Quando priorizado: migrar para `w:numPr`/`numId` nativo do Word,
validado com o mesmo padrão de 3 camadas usado na Etapa 5 (lxml
estrutural + XSD do toolkit `docx` + renderização Word/PDF real) antes
de aplicar ao template real.

### Fechamento

Em aberto, sem prazo.

---

## PEND-006 — Fronteira do bloco `EVOLUCAO_CONSUMO` definida por julgamento humano, não por marcador estrutural único

**Status:** RESOLVIDA (por eliminação da causa)
**Aberta em:** Etapa 5 (Motor Composicional de Blocos Condicionais)
**Resolvida em:** correção pontual de remoção definitiva de
`ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` — ver `docs/specs/SPEC-0001.md`
§49.
**Bloqueia:** —

### Contexto

Historicamente, `{{ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA}}` tinha duas
ocorrências dentro da região candidata do template real. Isso impedia
usar sua ocorrência como marcador estrutural inequívoco e exigiu leitura
humana para definir a fronteira `[87, 93]`.

A correção eliminou o placeholder de toda a arquitetura e tornou a
argumentação de evolução de consumo integralmente fixa no modelo. A
causa da ambiguidade deixou de existir. A composição resultante foi
validada em três camadas (lxml, XSD do toolkit e Word/PDF real), além do
teste de ponta a ponta `LOCAL_ONLY`.

### Risco se não resolvido

Nenhum risco pendente associado à causa registrada. Uma edição futura do
modelo institucional continua sujeita ao Template Lock e à validação
estrutural aplicável; eventual nova ambiguidade deverá gerar uma nova
pendência, baseada no novo estado do template.

### Critério de resolução

Atendido: o marcador ambíguo foi removido e a região final foi validada.

### Fechamento

Resolvida por eliminação da causa. Nenhuma ação remanescente nesta
pendência.

---

## PEND-004 — Definir licença proprietária/source-available compatível com repositório público e distribuição do plugin

**Status:** RESOLVIDA (gate PEND-004, 2026-08-18)
**Aberta em:** Fase 8 (auditoria de distribuição)
**Bloqueava:** publicação externa (push a um remote público, listagem em
marketplace acessível a terceiros) — nunca bloqueou o trabalho técnico
local (marketplace testável localmente, sem remote). Ver "Fechamento"
abaixo — a redação da `LICENSE` está feita; publicação externa segue sem
outro bloqueio jurídico conhecido (ausência de remote é decisão
operacional separada, não pendência).

### Contexto

A `LICENSE` do repositório reserva todos os direitos: "Nenhuma permissão
é concedida para copiar, modificar, distribuir, sublicenciar... sem
autorização prévia e expressa por escrito do titular." O objetivo da
Fase 8 (SPEC-0001, CLAUDE.md §25) é tornar o plugin instalável por
outros advogados — o que, tecnicamente, envolve copiar arquivos do
repositório para a máquina de quem instala.

### Risco se não resolvido

Ambiguidade jurídica sobre se a própria disponibilização pública no
marketplace já constitui a "autorização prévia e expressa por escrito"
que a `LICENSE` exige, ou se é necessário um passo adicional (atualizar a
`LICENSE`, ou adotar marketplace privado/restrito). Não é uma questão
técnica — é uma decisão do titular dos direitos.

### Critério de resolução

O titular decide entre, por exemplo: (a) atualizar a `LICENSE` para
permitir explicitamente instalação/uso via marketplace, preservando
restrições de modificação/redistribuição comercial; (b) manter a
`LICENSE` como está e tratar a listagem no marketplace como a autorização
por escrito (documentando essa interpretação); (c) manter o marketplace
privado/restrito a instalação autorizada individualmente. Não decidido
nesta fase — ver `ADR-0008`.

### Decisão superveniente (consolidação pós-Fase 8)

**Superadas** as três alternativas (a)/(b)/(c) acima — a pergunta não é
mais "publicar ou não publicar", isso já foi decidido: repositório e
plugin **serão públicos** no GitHub (visibilidade pública, clone,
download, instalação via marketplace, sem exigir que o usuário seja
colaborador autorizado). Acesso técnico ao repositório ≠ autorização
jurídica irrestrita sobre o software — quem disciplina isso é a
`LICENSE`, e é exatamente essa redação que falta.

**Modelo jurídico já definido** para orientar a redação futura (ainda
**não** redigida — ver "Fechamento" abaixo): licença proprietária/
source-available, não MIT/Apache-2.0/GPL/AGPL nem equivalente,
preservando controle sobre redistribuição e exploração comercial.
Parâmetros decididos para orientar essa redação futura:

* **Permitido:** código publicamente acessível; download e clone; instalação
  via marketplace; estudo do código; modificação local; uso profissional;
  uso interno por organizações (inclusive escritórios de advocacia
  diferentes do titular).
* **Restrito** (sujeito a condição/aviso, não proibição total):
  publicação de modificações; criação/distribuição de derivados.
* **Proibido sem autorização expressa do titular:** redistribuição;
  sublicenciamento; comercialização do plugin ou de derivados;
  apropriação de autoria; remoção de avisos/notices; uso de
  marcas/timbrados do titular ou de terceiros.

### Fechamento

**RESOLVIDA em 2026-08-18** (gate PEND-004, autorizado explicitamente
pelo usuário após a consolidação pós-Fase 8). `LICENSE` reescrita
implementando literalmente a matriz de parâmetros acima — Seção 1
("Permitido, sem necessidade de autorização adicional") cobre
integralmente o bloco "Permitido"; Seção 2 ("Permitido, sujeito às
condições abaixo") cobre o bloco "Restrito"; Seção 3 ("Proibido sem
autorização prévia e expressa por escrito do titular") cobre item a item
o bloco "Proibido". Seções de conteúdo de terceiros e ausência de
garantia, já existentes no texto anterior, preservadas. Não é MIT/
Apache-2.0/GPL/AGPL nem adota licença de terceiro — texto próprio,
redigido para este projeto. `README.md` (seção "Licença") e
`ADR-0009` atualizados de acordo.

Continuam válidas, sem alteração por esta resolução: `PEND-001`
(`DEFERRED`), `PEND-002` (`ADIADA`), `PEND-003` (`ABERTA`, tamanho de
`svd.joblib`). Nenhum remote foi criado, nenhum push ou publicação
externa foi realizado ao resolver esta pendência — isso permanece uma
decisão operacional separada e futura.

---

## PEND-007 — Dependência runtime do skill "docx" de terceiro (Anthropic) — não redistribuível e com contrato obsoleto

**Status:** RESOLVIDA (Commits 3–7.2 da Etapa 5.10; ver "Fechamento" abaixo)
**Aberta em:** Etapa 5.9 (auditoria de distribuição reprodutível)
**Bloqueia:** Nenhuma — o pipeline atual continua funcional para quem já
possui a cópia vendorizada local (`skills/docx/`, gitignored) e
`CLAUDE_PLUGIN_ROOT` apontando para ela; bloqueia, sim, a reprodutibilidade
da instalação para qualquer usuário fora desse ambiente específico, que é
exatamente o problema que motivou a auditoria.

### Contexto

`scripts/docx_template_engine.py`, `docx_context_engine.py`,
`docx_block_engine.py` e `validate_template.py` dependem em runtime de
`unpack.py`/`pack.py` do skill "docx" da Anthropic, localizados via
`_localizar_docx_toolkit()`. Essa dependência nunca foi vendorizável de
forma distribuível: (1) a licença do skill (`skills/docx/LICENSE.txt`)
proíbe extração, cópia e redistribuição fora dos Services da Anthropic;
(2) a versão atualmente publicada do skill não expõe mais
`unpack.py`/`pack.py` — reescrita para um fluxo `unzip/editar/zip`,
contrato incompatível com o que o EDE espera, confirmado inclusive na
própria máquina do desenvolvedor fora do checkout deste repositório.

### Risco se não resolvido

Nenhum advogado externo consegue gerar a Contestação a partir de uma
instalação padrão do plugin (marketplace ou clone), mesmo fornecendo o
`modelo-oficial.docx` pelo canal externo já previsto em `ADR-0009` — a
geração falha sempre no estágio de desempacotamento do DOCX, com
`RuntimeError` não tratado (achado da auditoria da Etapa 5.9, Fase 6).

### Critério de resolução

Runtime DOCX próprio do EDE (`scripts/docx_package.py`, `ADR-0014`),
sem dependência de `skills/docx/` nem de qualquer outro toolkit de
terceiro, migrado para todos os consumidores atuais e validado contra o
Template Lock (`verificar_template_lock`) sem regressão. Critério
objetivo: busca por `skills/docx`, `unpack.py`, `pack.py` no runtime do
pipeline de Contestação retorna zero ocorrências funcionais (só
referências históricas em ADRs/CHANGELOG).

### Fechamento

**Resolvida.** Runtime próprio (`scripts/docx_package.py`, `ADR-0014`)
implementado no Commit 2 e migrado para todos os consumidores nos
Commits 3 (`docx_template_engine.py`, `docx_context_engine.py`,
`docx_block_engine.py`, `validate_template.py`) e 4 (padronização
fail-closed). Comparação byte a byte OOXML (57/57 partes idênticas,
runtime antigo × novo) confirmou zero regressão no Commit 3. O critério
objetivo de resolução (zero ocorrência funcional de `skills/docx`,
`unpack.py`, `pack.py` no runtime do pipeline) foi confirmado
repetidamente: Commits 5, 6, 7 e Microfixes 7.1/7.2, e comprovado de
forma definitiva pelo harness `scripts/homologar_distribuicao.py`
(Commit 7) contra um clone Git limpo sem `skills/docx/` — o pipeline
completo, incluindo `validate_template.py` (corrigido nos Microfixes
7.1/7.2), chega ao DOCX final com Template Lock aprovado. Reprodutível
por qualquer instalação pública, sem a cópia vendorizada local. Ver
`docs/DISTRIBUICAO.md` §5 para o resumo operacional.


## PEND-008 — Segundo asset de teste `modelo-oficial_topicos-2.3-a-2.6_contratados.docx` legado/redundante

**Status:** ABERTA
**Aberta em:** Etapa 5.10, Microfix 7.1 (auditoria dos 3 skips
dependentes desse asset, requisitada na autorização do Microfix 7.1)
**Bloqueia:** Nenhuma — asset local do ambiente de desenvolvimento,
gitignored, não distribuído; os 3 testes que dependem dele (`R/S/W/X`
em `tests/test_topicos_2_3_a_2_6.py`) já usam `pytest.skip()` explícito
quando ausente.

### Contexto

`templates/contestacao/modelo-oficial_topicos-2.3-a-2.6_contratados.docx`
é um snapshot de trabalho salvo durante o desenvolvimento da Etapa
5.8-G (adição dos tópicos 2.3–2.6), com histórico próprio de correções
manuais registradas em `templates/contestacao/backup/` (`...-BACKUP-
pre-fix-merito-sdt-...`, `...-pre-fix-token-economico-...`). Auditoria
do Microfix 7.1 comparou esse arquivo contra o `modelo-oficial.docx`
canônico, parte a parte (desempacotamento completo dos dois): **as
partes OOXML são byte-idênticas** (`word/document.xml` e todas as
demais partes) — a única diferença está no hash do arquivo `.docx`
inteiro, decorrente de metadado de contêiner ZIP (timestamp/ordem/
compressão), não de conteúdo. Confirmado também que o canônico já
contém todos os SDTs/zonas dos tópicos 2.3–2.6 que os 3 testes
dependentes exercitam.

### Critério de resolução

Migrar `TEMPLATE_2_3_A_2_6` (`tests/test_topicos_2_3_a_2_6.py`) para
apontar para `modelo-oficial.docx`, eliminando a necessidade do segundo
arquivo; ou remover o arquivo duplicado do ambiente de desenvolvimento
após confirmar que nenhum teste depende mais dele.

### Fechamento

Em aberto — classificado como legado/redundante, não bloqueante.
Correção explicitamente não autorizada nas rodadas da Etapa 5.10
(Microfix 7.1/7.2, Commit 8) — fica para rodada própria.


## PEND-009 — `docx_numeracao_engine.py` depende de âncoras textuais hardcoded do Modelo Oficial

**Status:** ABERTA
**Aberta em:** Etapa 5.10, Microfix 7.1 (achado de auditoria, Fase 1,
antes de desenhar os testes de `validate_template.py`)
**Bloqueia:** Nenhuma — dívida arquitetural pré-existente (não
introduzida pela Etapa 5.10); o motor funciona corretamente contra o
Modelo Oficial real, exatamente como sempre funcionou.

### Contexto

`scripts/docx_numeracao_engine.py` (`NOS_NIVEL_1`/`NOS_LITERAIS`)
localiza os títulos de nível 2/3 da Contestação por um catálogo
INTERNO, próprio, de âncoras de texto literal (ex.: `"LEGALIDADE DOS
PROCEDIMENTOS"` para o nó `LEGALIDADE_PROCEDIMENTOS`) — não deriva nada
de `templates/contestacao/blocos.json`. Consequência prática, achada ao
tentar testar `gerar_peca_com_blocos()` (Microfix 7.1) contra um
catálogo sintético mínimo: a renumeração automática (etapa obrigatória
de toda geração via blocos) só é executável contra um documento que
contenha essas âncoras reais — nenhuma composição sintética arbitrária
chega ao fim do pipeline. Por esse motivo, todo teste que precisa de
`gerar_peca_com_blocos()` completo (renumeração incluída) já é, e
continuará sendo, `docx_real` — convenção já estabelecida antes desta
etapa (`test_pipeline_completo_com_blocos_contra_template_real`, em
`tests/test_docx_block_engine.py`), não uma limitação nova.

### Risco se não resolvido

Nenhum — é uma característica estrutural conhecida, não um defeito
ativo. O risco é só de manutenção: qualquer alteração futura de título
no Modelo Oficial exige atualizar `NOS_LITERAIS` manualmente, em
sincronia com o `.docx` real.

### Critério de resolução (futuro, não solicitado nesta etapa)

Derivar as âncoras de numeração de `blocos.json` (ou de um catálogo
próprio declarado nele), eliminando o acoplamento a texto hardcoded —
refatoração de escopo próprio, fora do que qualquer rodada da Etapa
5.10 autorizou.

### Fechamento

Em aberto — dívida arquitetural não bloqueante, registrada para etapa
futura. Não refatorado nesta etapa.


## PEND-010 — Inspeção visual automatizada do DOCX final ainda não executada

**Status:** ABERTA
**Aberta em:** Etapa 5.10, Commit 7 (homologação de distribuição)
**Bloqueia:** Declaração de validação visual automatizada em release
público — não bloqueia runtime, distribuição técnica nem os gates já
homologados (Template Lock estrutural, zero resíduo, OOXML válido
continuam sendo verificados programaticamente).

### Contexto

Todos os gates de homologação desta etapa (Commits 1–8) são estruturais/
programáticos — Template Lock, ausência de placeholder/zona/SDT
residual, numeração, validade OOXML. Nenhum deles renderiza o DOCX
final visualmente para comparação humana ou automatizada contra a peça
homologada. O ambiente de homologação usado nesta etapa não possui
nenhum renderizador DOCX legítimo disponível (e a instalação de um
toolkit proprietário para viabilizar isso foi explicitamente vedada em
todas as rodadas desta etapa).

### Critério de resolução

Executar inspeção visual (manual ou por renderizador legítimo,
licenciado) do DOCX final gerado pelo pipeline, comparando contra a
peça de referência já homologada manualmente pelo usuário, antes de
qualquer release público que declare validação visual automatizada.

### Fechamento

Em aberto. Registrada como requisito explícito para esse cenário
futuro (release público com tal declaração) — não é pré-requisito para
o uso interno já validado tecnicamente por esta etapa.

---

## PEND-011 — Quebras de linha inseridas pelo transporte do cliente ChatGPT nos valores de placeholder

**Status:** ABERTA
**Aberta em:** primeira chamada viva do ChatGPT a `ede_finalizar_peca`
(2026-09-22)
**Bloqueia:** Declaração de interoperabilidade do finalizador com o
ChatGPT. Não bloqueia o runtime: o servidor já recusa em
`input_validation` quando a inflação estoura um limite de densidade.

### Contexto

A primeira chamada viva foi recusada, sem DOCX, porque os três campos
narrativos chegaram ao servidor com cerca de 2,5 a 3 vezes mais linhas do
que o rascunho do cliente (2→6, 2→6, 4→10; evidência no `CHANGELOG.md`,
seção "Evidência viva"). O contrato conta parágrafo por `\n`
(`validate_paragrafos.paragrafos`), então o servidor não distingue a
quebra do autor da quebra do transporte.

O risco é o caso que **não** falha: inflação que fica abaixo do limite
(por exemplo, um parágrafo único de uns 450 caracteres brutos quebrado em
3 linhas em `SINOPSE_FATOS`, cujo máximo é 3) passa na checagem de 380, na
densidade e no round-trip, e cada linha vira um `<w:p>` próprio no DOCX,
com o parágrafo partido no meio da frase. Reproduzido localmente contra
`validate_paragrafos` na mesma data.

A segunda chamada, com parágrafo único nos três campos, terminou `OK`.
Isso **não** resolve esta pendência: nenhum campo com mais de um
parágrafo foi exercitado, então a preservação de multilinha pelo
transporte continua sem prova.

### Critério de resolução

Uma chamada viva do ChatGPT em que o DOCX devolvido tenha, em cada campo
multiline, exatamente o número de parágrafos do rascunho do cliente,
incluindo pelo menos um campo com 2 ou mais parágrafos. Um sucesso só com
valores de parágrafo único não fecha esta pendência, porque não exercita o
separador. Alternativa aceitável: identificar e corrigir a causa no
cliente.

Esta pendência nunca se resolve relaxando validador, juntando linhas no
servidor nem inferindo a intenção do cliente (CLAUDE.md §17/§21).

### Fechamento

Em aberto.

---

## PEND-012 — Nenhum host MCP testado (ChatGPT, Claude) entrega o DOCX nativamente via `EmbeddedResource`

**Status:** ABERTA (escopo ampliado em 2026-09-22 — passou a cobrir os
dois clientes; aberta originalmente só para o ChatGPT)
**Aberta em:** Gate 6.6-D, chamada 2 do ChatGPT a `ede_finalizar_peca`
(2026-09-22); ampliada no mesmo gate com a chamada viva do Claude
**Bloqueia:** Critério de entrega nativa do Gate 6.6-D. O gate foi
**ENCERRADO como `6.6-D FINALIZER LIVE INTEROPERABILITY — PARTIAL
PASS`** com esta pendência aberta — correção do servidor e determinismo
do documento comprovados; entrega nativa é o item que falhou nos dois
clientes. Não bloqueia o runtime e, pela política de rollback aprovada,
não motiva rollback.

### Contexto

**ChatGPT.** A chamada terminou `OK` (1761975 bytes, SHA-256
`edd2a513178f9eb7190cb105eb147ba8c9374d913d27b548fa0abe62eca872ab`), e o
base64 não apareceu na conversa. Mas a UI do ChatGPT não conseguiu usar a
URI `attachment://` do `EmbeddedResource` e o próprio host persistiu o
arquivo por outro canal de arquivos. O arquivo obtido assim é idêntico
byte a byte ao do servidor e mantém o timbrado. O problema é de entrega
nativa no host, não do renderer.

**Claude.** Chamada com o mesmo payload de parágrafo único, terminou
`OK` com o **mesmo SHA-256** do ChatGPT. O claude.ai recusou
explicitamente o tipo de mídia: "Resources of type
'application/vnd.openxmlformats-officedocument.wordprocessingml.
document' are not currently supported." Nenhum contorno; nenhum byte do
DOCX chegou a ficar disponível para o usuário. O log de requisições
confirma que o servidor transmitiu o `EmbeddedResource` completo
(tamanho de resposta ≈ inflação base64 esperada) — a falha é do cliente,
não do transporte nem do servidor.

Evidência completa das duas chamadas no `CHANGELOG.md`, seção
"Evidência viva — Gate 6.6-D".

Documentação da OpenAI consultada em 2026-09-22 (Apps SDK Reference e
"MCP server" em developers.openai.com): nenhum mecanismo nativo documentado
para um resultado de ferramenta entregar arquivo baixável. As APIs de
arquivo documentadas são de widget (`uploadFile`, `selectFiles`,
`getFileDownloadUrl`), e `openai/fileParams` é só para entrada de
ferramenta.

### Critério de resolução

Uma das duas:

1. evidência de um mecanismo nativo de QUALQUER um dos hosts que exponha
   este `EmbeddedResource` como artefato utilizável/baixável direto do
   resultado MCP, sem URL pública, sem reconstrução manual e sem
   regeneração secundária, comprovada em chamada viva; ou
2. decisão explícita do usuário por outro mecanismo de entrega, registrada
   como revisão da Decisão 5 da ADR-0018 (avaliação preparatória, sem
   implementação, em ADR-0019 / PEND-014).

Esta pendência nunca se resolve trocando a entrega para base64 em
`TextContent`, publicando URL pública sem o desenho de segurança de
PEND-014, mexendo no renderer ou no Template Lock, ou afrouxando a
validação produção-final. Também não se resolve tratando o contorno do
ChatGPT como entrega nativa, mesmo com os bytes idênticos.

### Fechamento

Em aberto. O Gate 6.6-D fechou com esta pendência aberta — a decisão do
usuário foi encerrar o gate como PARTIAL PASS em vez de bloquear no
critério de entrega nativa.

---

## PEND-013 — Remoção das tags históricas do Cloud Run (pre-pilot hardening, execução adiada)

**Status:** APROVADA em princípio pelo usuário; execução ADIADA
**Aberta em:** Auditoria somente-leitura das revisões antigas com tag,
Gate 6.6-D item 6 (2026-09-22)
**Bloqueia:** Nenhuma fase. Não bloqueia o runtime, o Gate 6.6-D nem
qualquer entrega — as seis tags são AUTH-BLOCKED (auditoria acima) e não
são necessárias para rollback.

### Contexto

A auditoria somente-leitura do Gate 6.6-D item 6 concluiu que as seis
tags históricas do Cloud Run (`candidato`, `candidato-6-5-b`,
`candidato-6-5-b2`, `candidato-6-5-c`, `candidato-6-5-c2`,
`candidato-6-5-c4`) apontam para revisões `AUTH-BLOCKED`: alcançáveis sem
autenticação só até a política de Host/OAuth, nunca até um dispatch de
ferramenta (evidência completa no `CHANGELOG.md`, seção "Auditoria
somente-leitura das revisões antigas com tag"). Nenhuma é
`LEGACY-MCP-REACHABLE`.

O usuário aceitou a conclusão da auditoria e aprovou EM PRINCÍPIO a
remoção dessas tags como *pre-pilot hardening* (reduzir superfície
pública antes de qualquer expansão de acesso a advogados), mas pediu
explicitamente que a execução fique para depois de completa a evidência
de interoperabilidade viva do Claude no Gate 6.6-D — para não misturar
uma mutação de infraestrutura com evidência de interoperabilidade de
cliente em andamento.

### Critério de resolução

Depois que o Gate 6.6-D fechar (ou, no mínimo, depois que a evidência de
interoperabilidade viva do Claude estiver completa), remover as seis
tags listadas (`gcloud run services update-traffic ede-mcp
--remove-tags=...`) e verificar que a revisão alvo de rollback
(`ede-mcp-00018-loc`) continua endereçável por nome de revisão sem a
tag. Registrar a execução aqui e no `CHANGELOG.md`, com data e comando
efetivamente usado.

Esta pendência nunca se resolve por remoção automática/silenciosa das
tags — exige autorização explícita do usuário no momento da execução
(CLAUDE.md §6/§24), mesmo já tendo aprovação de princípio agora.

### Fechamento

Em aberto (execução deliberadamente adiada).

---

## PEND-014 — Redesenho do mecanismo de entrega de artefato entre hosts (candidato implementado, Gate 6.6-E)

**Status:** CANDIDATO IMPLEMENTADO E VERIFICADO AO VIVO (continuação do
Gate 6.6-E). `scripts/artifact_storage.py` (objeto GCS efêmero + URL V4
assinada) implementado, testado (fake, sem rede) e verificado
COMPLETAMENTE contra GCP real: upload, `signBlob`, download assinado,
identidade de bytes/SHA-256, negação de acesso não assinado, expiração,
limpeza oportunista e HARD DELETE — todos com IAM de homologação
temporária, criada/usada/removida (ver ADR-0019 "Implementação" e
"Retenção"). Janela de download revisada para 24h (decisão do usuário);
retenção normal (~24-25h) sustentada por limpeza AGENDADA horária
(Cloud Scheduler -> Cloud Run Job sobre a mesma imagem imutável),
**provisionada em homologação e provada ao vivo** — inclusive a
semântica de falha (execução agendada que falha não altera artefato
não elegível). **Prova viva de download por Claude/ChatGPT e ativação
em produção continuam NÃO autorizadas.**
**Aberta em:** Fechamento do Gate 6.6-D como `PARTIAL PASS` (2026-09-22);
implementação candidata no Gate 6.6-E, mesma data.
**Bloqueia:** O gate de download ao vivo (verificação com Claude/ChatGPT
reais). Não bloqueia o runtime: produção continua servindo v1
tecnicamente (a revisão corrente não tem `EDE_ARTEFATOS_GCS_*`
configuradas, então v2 nem é alcançável em produção hoje).

### Contexto

O Gate 6.6-D provou que o mecanismo de entrega v1 da ADR-0018 (Decisão
5 — `EmbeddedResource`/`BlobResourceContents` inline) não é usável
nativamente por nenhum dos dois hosts MCP reais testados: o ChatGPT não
expõe a URI `attachment://` na UI (PEND-012), e o Claude recusa
explicitamente o tipo de mídia do DOCX. Em ambos os casos o servidor
está correto — o documento é gerado deterministicamente e os bytes
efetivamente saem pelo transporte HTTPS (confirmado por tamanho de
resposta no log de requisições do Claude). A lacuna é estrutural do
mecanismo de entrega, não do renderer.

`docs/adr/ADR-0019-entrega-de-artefato-multi-cliente.md` registra a
avaliação e, desde o Gate 6.6-E, a implementação candidata: bucket real
`ede-legal-mcp-01-artefatos-efemeros` (homologação, privado, PAP
enforced, soft-delete desligado, lifecycle de 2 dias como backstop),
`scripts/artifact_storage.py` (V4 signing manual, sem SDK de nuvem
novo), integração em `finalizar_peca.py`/`server.py` (v2 substitui o
`EmbeddedResource`, nunca em paralelo). **Nenhuma IAM de runtime de
produção foi alterada** (Gate 6.6-E §41) — as duas concessões
necessárias (bucket-scoped `storage.objectAdmin`;
`iam.serviceAccountTokenCreator` de auto-impersonation) ficam
documentadas, não aplicadas.

### Critério de resolução

Esta pendência se resolve com uma das duas:

1. verificação real completa da assinatura V4 (com IAM de homologação
   explicitamente concedida por decisão separada do usuário — o guard
   de segurança do harness bloqueou isso nesta sessão, propositalmente
   não contornado), seguida de aplicação controlada da IAM de produção
   e prova viva de download real com Claude e ChatGPT; ou
2. decisão explícita do usuário de manter a Decisão 5 (v1) como está,
   aceitando que a entrega nativa continue indisponível e que o
   artefato só chegue ao usuário por contorno do cliente (caso do
   ChatGPT) ou não chegue (caso do Claude).

Esta pendência nunca se resolve por ativação silenciosa — nenhuma
mudança de IAM de runtime de produção nem configuração das variáveis
`EDE_ARTEFATOS_GCS_*` na revisão de produção sem autorização explícita
do usuário para esse passo específico (CLAUDE.md §6/§17/§24).

### Fechamento

Em aberto (avaliação em andamento).
