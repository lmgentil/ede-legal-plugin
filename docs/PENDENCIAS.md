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
| PEND-001 | ABERTA | Fase 3 | Fase 7 | Suporte multimídia ao placeholder `FOTOS_DA_IRREGULARIADE` |
| PEND-002 | ABERTA | Fase 4 | Nenhuma (adiada por decisão do usuário) | Indexação de jurisprudência (REQ-018) na busca híbrida |

---

## PEND-001 — Suporte multimídia ao placeholder `FOTOS_DA_IRREGULARIADE`

**Status:** ABERTA
**Aberta em:** Fase 3 (auditoria de `templates/contestacao/modelo-oficial.docx`)
**Bloqueia:** Fase 7 — End-to-End (resolução obrigatória antes de iniciar)

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

### Fechamento

Em aberto. Ao resolver, mover a linha da tabela acima para
"RESOLVIDA (Fase N)", preencher a decisão tomada nesta seção, e referenciar
o commit/PR correspondente.

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

### Fechamento

Em aberto, sem prazo. Ao resolver, mover a linha da tabela para "RESOLVIDA
(Fase N)", preencher a decisão tomada e referenciar o commit/PR.
