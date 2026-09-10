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
