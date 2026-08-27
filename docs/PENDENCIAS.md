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
| PEND-003 | ABERTA | Fase 8 | Nenhuma (não impede uso; afeta tamanho de clone/instalação) | `rag/embeddings/svd.joblib` (~81 MB) domina o tamanho do repositório distribuído; compatibilidade de runtime já resolvida separadamente |
| PEND-004 | RESOLVIDA (gate PEND-004) | Fase 8 | — | Definir licença proprietária/source-available compatível com repositório público e distribuição do plugin |
| PEND-005 | ABERTA | Etapa 5 | Nenhuma (dívida estrutural; a renumeração dinâmica atual elimina lacunas) | Subtítulos ainda não migrados para lista multinível nativa do Word |
| PEND-006 | RESOLVIDA (causa eliminada) | Etapa 5 | — | Ambiguidade da fronteira de `EVOLUCAO_CONSUMO` eliminada com a retirada do placeholder duplicado |

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

**Status:** ABERTA
**Aberta em:** Fase 8 (auditoria de distribuição)
**Bloqueia:** nenhuma fase — não impede instalação nem uso; só torna o
clone/instalação mais pesado do que precisaria.

### Contexto

`rag/embeddings/svd.joblib` (o modelo TF-IDF+LSA de fallback offline,
Fase 4) tem ~81 MB — sozinho, ~91% dos ~89 MB rastreados pelo git neste
repositório. É o único item que se aproxima de tamanhos problemáticos
para distribuição via marketplace (clone completo do repositório a cada
instalação/atualização).

### Risco se não resolvido

O risco que permanece nesta pendência é exclusivamente distributivo:
instalação mais lenta e repositório mais pesado para clonar via
`/plugin marketplace add`. A incompatibilidade de serialização/runtime
identificada posteriormente foi resolvida separadamente pelo contrato
fail-closed do manifesto, dependências fixadas e artefatos regenerados
no runtime canônico, conforme `docs/adr/ADR-0011-contrato-artefatos-rag.md`.
Essa correção não reduz os ~81 MB e, portanto, não encerra a PEND-003.

### Critério de resolução

Quando priorizado: avaliar Git LFS, ou reconstrução local sob demanda
(`rag/embeddings/build_embeddings.py` já existe e é determinístico a
partir do corpus versionado — reconstruir é possível, só não está
automatizado como parte da instalação), ou aceitar o tamanho atual como
suficiente. Não decidido nesta fase (SPEC-0001 Fase 8 §53: não
redesenhar o RAG sem necessidade).

### Fechamento

Em aberto, sem prazo.

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
