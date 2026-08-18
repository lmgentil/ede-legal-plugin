# ADR-0006 — Assets institucionais e dados sensíveis no repositório público

## Status

Aceito (2026-08-18) — decisão conservadora e reversível apenas no sentido de
ampliar exposição, não de reduzi-la. Revisado na Fase 4 (RAG Jurídico,
2026-08-18) — ver "Atualização — Fase 4" ao final.

## Contexto

O `SPEC-0001` (§29, SEC-004, ADR-REQ-001) prevê repositório público no
GitHub, "ressalvados assets institucionais sensíveis", e determina que uma
decisão explícita seja registrada sobre o que é núcleo público versus asset
institucional — sem presumir automaticamente que o timbrado do escritório
deve integrar o público.

A auditoria da Fase 0 encontrou, além do timbrado (ainda inexistente), um
risco mais amplo: `rag/jurisprudencia/` contém:

1. **57 fichas em Markdown** (`*.md` + `INDEX.md`) — cada ficha traz um bloco
   "Contexto Estratégico" que identifica, para casos reais do escritório,
   o cliente (ex.: "COELBA"), a parte contrária por nome completo, o número
   do processo e a estratégia argumentativa usada na peça original.
2. **60 arquivos brutos** em `rag/jurisprudencia/.textos_varredura/`
   (~1,1 MB) — texto integral, extraído de `.docx`, de peças processuais
   reais do escritório (Agravos, Apelações), com nomes completos de partes
   e números de processo.

O item 2 é inequivocamente "documento processual real de cliente"
(`CLAUDE.md §18-19`, `SPEC-0001 SEC-002/SEC-003`) e não pode ser versionado
em hipótese alguma. O item 1 é mais matizado: a citação de jurisprudência
publicada (súmulas, temas repetitivos, acórdãos) é, em si, informação
pública; o que a torna sensível é o campo "Contexto Estratégico", que expõe
qual cliente do escritório usou aquele precedente e em que caso real — isto
é, revela relação cliente-escritório e estratégia de litígio, não apenas o
precedente em si.

Não havia, até esta ADR, `.gitignore` algum no repositório — ou seja, nada
impedia que todo esse conteúdo fosse commitado e publicado no primeiro
`git push`.

## Decisão

1. **`rag/jurisprudencia/.textos_varredura/`** fica permanentemente fora do
   controle de versão. É workspace local de elaboração de peças
   (`CLAUDE.md §19`), nunca núcleo do plugin.
2. **`rag/jurisprudencia/*.md` e `INDEX.md`**, embora contenham valor real
   como corpus de jurisprudência curada, ficam **fora do controle de versão
   por padrão nesta fase**, até que o conteúdo seja tratado (expurgo ou
   separação do bloco "Contexto Estratégico" em arquivo interno não
   versionado, mantendo apenas tese/ementa/fonte pública no arquivo
   versionável). Esse tratamento é trabalho de conteúdo, não de
   infraestrutura, e foi propositalmente deixado para a Fase 4 — RAG
   Jurídico, para não alterar dados de um corpus funcional sem análise
   própria (`CLAUDE.md §5`).
3. **O template institucional real** (`templates/**/modelo-oficial.docx`),
   quando fornecido pelo advogado, também fica fora do controle de versão
   por padrão, até decisão explícita em contrário (o timbrado pode revelar
   identidade do escritório, dados de contato, OAB etc.).
4. O **núcleo de legislação** (`rag/chunks_*`, `rag/embeddings/`,
   `rag/_originais_pre_split/`) permanece público: é derivado de texto
   normativo de domínio público, sem dado de cliente.
5. Efeito prático imediato: aplicado via `.gitignore` nesta mesma Fase 1.

## Alternativas consideradas

- **Publicar tudo, redigindo os campos sensíveis manualmente agora.**
  Rejeitada nesta fase: exigiria reescrever/curar 57 arquivos de conteúdo
  jurídico funcional dentro de uma fase que deveria se limitar a estrutura,
  versionamento e configuração (`CLAUDE.md §29`).
- **Manter tudo público, confiando que dados processuais no Brasil são
  majoritariamente públicos.** Rejeitada: a exposição problemática não é o
  precedente (público), é a associação nominal cliente↔caso↔estratégia, que
  não é dado de acesso público equivalente e fere o dever de sigilo
  profissional.
- **Repositório privado único (sem separação).** Rejeitada: contraria a
  premissa da SPEC de repositório público para o núcleo do plugin.
- **Repositório/submódulo institucional separado e privado**, com o núcleo
  público consumindo apenas metadados. Considerada a solução alvo de médio
  prazo, mas não implementada agora por ser infraestrutura especulativa
  além do escopo da Fase 1 (YAGN — construir quando a Fase 4 precisar).

## Consequências

- `rag/jurisprudencia/` some do histórico de commits do núcleo público
  enquanto esta ADR estiver vigente — a busca híbrida **não indexa
  jurisprudência** até a Fase 4 resolver o expurgo (isso já era um gap
  identificado na Fase 0, independente desta ADR).
- Qualquer clone público do repositório após esta fase não conterá o corpus
  de jurisprudência nem os textos brutos — quem precisar dele localmente
  continuará tendo acesso ao diretório de trabalho, apenas fora do git.
- Antes da Fase 4, é preciso decidir e documentar (nesta mesma ADR, por
  atualização, ou em uma nova) o mecanismo definitivo de distribuição do
  corpus de jurisprudência curado (submódulo privado, storage externo, ou
  expurgo campo a campo para reintegração ao núcleo público).
- `LICENSE` ainda usa um titular placeholder (`[TITULAR A DEFINIR]`);
  quando definido, deve ser revisado se o nome do escritório pode aparecer
  publicamente antes de o timbrado real ser tratado por esta mesma ADR.

## Atualização — Fase 4 (2026-08-18)

Conforme previsto no item 5 de "Consequências", a revisão exigida antes da
Fase 4 foi feita: apresentadas ao usuário três alternativas — expurgar o
bloco "Contexto Estratégico" e indexar a versão pública; indexar tudo como
está mantendo o diretório fora do git; ou adiar — a decisão foi **adiar**.
Fase 4 não indexa `rag/jurisprudencia/` na busca híbrida. Registrado como
`PEND-002` (`docs/PENDENCIAS.md`), sem fase bloqueante — retomar quando o
usuário decidir.

Nenhuma parte desta ADR muda: os itens 1-5 da "Decisão" continuam vigentes
sem alteração; `rag/jurisprudencia/*.md` segue fora do controle de versão e
fora da busca híbrida.
