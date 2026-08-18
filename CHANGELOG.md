# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e
este projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Bloqueado
- **PEND-001** (ver `docs/PENDENCIAS.md`) bloqueia o início da Fase 7 —
  resolução obrigatória antes disso, não depois. Nada bloqueia a Fase 7 além
  disso (Fase 6 encerrada abaixo).

## [0.6.0] - 2026-08-18 — Fase 6 (Contestação)

### Auditoria prévia — conflito identificado

`Contestacao - Skill.skill` (arquivo solto na raiz do repositório, .zip,
não versionado) continha uma skill do usuário já pronta:
`estrategista-contestacao-ede`. Ela **não é** a "Skill Contestação" que a
SPEC-0001 REQ-002 define (`skills/contestacao/SKILL.md`, responsável por
orquestrar identificação de documentos → extração → fatos → pedidos →
datas → tempestividade → RAG → Skills transversais → placeholders →
renderização → validação). É uma skill de **análise estratégica**
upstream: decompõe a inicial, define teses/preliminares/riscos e entrega
uma "ANÁLISE ESTRATÉGICA" em Markdown — o próprio `SKILL.md` dela declara
explicitamente que não redige a peça e que espera ser sucedida por
`redator-peca-processual-elite` **ou** por "a skill `contestacao` do
plugin `contestacao-ede`" (preenchimento do Modelo Oficial).

Ou seja: o próprio pacote do usuário já pressupõe a existência do
orquestrador REQ-002 como uma peça separada, ainda não escrita. Não havia
conflito de conteúdo (a skill é tecnicamente sólida, alinhada com
CLAUDE.md §9/§12 — nunca inventa jurisprudência/número de processo, usa
`"NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."` e `"PESQUISA
JURISPRUDENCIAL NECESSÁRIA."` como os próprios marcadores de Fail Closed
deste projeto), só uma peça faltante na arquitetura. Resolução: instalada
verbatim como `skills/estrategista-contestacao-ede/` (mesmo tratamento das
skills reais do usuário na Fase 2 — não regenerada) e
`skills/contestacao/SKILL.md` escrito como o orquestrador REQ-002 que a
invoca como etapa recomendada (não uma das duas obrigatórias do CLAUDE.md
§7). Divergência menor, não corrigida por ser conteúdo do usuário: o
`SKILL.md` da `estrategista` cita "o plugin `contestacao-ede`" — nome
antigo/informal do que este repositório chama de "EDE Legal Plugin";
cosmético, não afeta funcionamento. Nenhum dado de cliente real encontrado
nos 7 arquivos do pacote (checado antes de instalar).

### Adicionado — Fase 6 (Contestação)
- `skills/contestacao/SKILL.md` (novo) — orquestrador REQ-002: pipeline
  completo (REQ-031) mapeado para os componentes reais do repositório —
  extração factual com proveniência (REQ-030), tempestividade
  (`calendario-forense-tjba-2026`), RAG (`search_hybrid.py`) + validação de
  citações (`legal_validation.validar_citacao`, Fase 5), análise
  estratégica (`estrategista-contestacao-ede`, recomendada), redator +
  humanizer (obrigatórias, CLAUDE.md §7), e tabela de mapeamento dos 13
  placeholders → origem do valor. **Não executa o fluxo fim-a-fim nesta
  fase** — isso é Fase 7, que segue com gate em `PEND-001`.
- `skills/estrategista-contestacao-ede/` (novo) — skill do usuário, 7
  arquivos, instalada verbatim (SKILL.md + 6 references/).
- `scripts/validate_fatos.py` (novo, REQ-030) — valida estruturalmente uma
  lista de fatos extraídos: `source_document` obrigatório e não vazio,
  `confidence` (se presente) em `[0, 1]`, `page` (se presente) inteiro.
  Fail closed: fato sem proveniência não passa. A extração em si continua
  sendo tarefa do agente (compreensão de texto), não deterministicamente
  automatizável — este script só audita o formato do que foi extraído.
- `tests/test_validate_fatos.py` (novo) — 12 testes.

### Corrigido
- `.claude-plugin/plugin.json`: campo `version` estava parado em `0.3.0`
  desde a Fase 3 — não foi atualizado nas Fases 4/5 (esquecimento,
  registrado aqui em vez de corrigido silenciosamente). Sincronizado com
  `VERSION` (`0.6.0`).

### Testado
- `python tests/test_validate_fatos.py` — 12/12.
- `python tests/test_legal_validation.py` — 24/24 (sem regressão).
- `python tests/test_rag_search.py` — 8/8 (sem regressão).
- `python rag/avaliar_recuperacao.py` — top-1 75% (18/24), top-3 88%
  (21/24) — idêntico ao baseline.
- `python tests/test_template_engine.py` — 10/10 (sem regressão).
- `claude plugin validate .` — sem novos warnings.

### Status dos requisitos da Fase 6
- **REQ-002** (Skill Contestação) — `[PRONTO]` como orquestração
  documentada; **não exercida** contra um caso real nesta fase.
- **REQ-003/REQ-004** (redator/humanizer obrigatórios) — `[PRONTO]`,
  reafirmado no pipeline (§8 do SKILL.md).
- **REQ-005** (tempestividade aciona o calendário) — `[PRONTO]` no
  pipeline (§6); depende de dados reais do caso para ser exercido.
- **REQ-030** (proveniência factual) — `[PRONTO]` como contrato +
  validador (`validate_fatos.py`); a extração real depende de documentos
  de um caso concreto (Fase 7).
- **REQ-031** (pipeline mínimo) — `[PRONTO]` como definição; execução
  fim-a-fim é Fase 7.

### Pendências conhecidas
- `PEND-001` e `PEND-002` inalteradas — nenhuma das duas foi resolvida
  nesta fase, por instrução explícita.
- `skills/estrategista-contestacao-ede/` não foi adicionada à lista de
  Skills transversais obrigatórias do CLAUDE.md §7/SPEC-0001 REQ-003/004
  — é recomendada, não obrigatória; se o usuário decidir torná-la
  obrigatória para este tipo de caso, isso é uma decisão de CLAUDE.md/SPEC
  a registrar explicitamente, não presumida aqui.
- Nenhum teste desta fase exercita `skills/contestacao/SKILL.md` contra um
  caso real (arquivo de instruções para o agente, não código) — a
  validação aplicável é `claude plugin validate .`, igual às demais Skills
  do projeto.

## [0.5.0] - 2026-08-18 — Fase 5 (Validação Jurídica)

Adiciona a camada que transforma o que o RAG recupera em conhecimento
juridicamente verificável e rastreável (SPEC-0001 §5-30): `rag/legal_validation/`,
desacoplada de `rag/search_hybrid.py` (ver `ADR-0007`). Regra central:
recuperar um trecho relevante não significa que ele esteja automaticamente
autorizado para citação — RECUPERADO ≠ VALIDADO.

### Adicionado — Fase 5 (Validação Jurídica)
- `rag/legal_validation/models.py` — modelo canônico de fonte jurídica
  (`fonte_juridica()`, SPEC-0001 §9) e os três eixos independentes:
  `VALIDATION_STATUS` (existência/correspondência textual da citação),
  `VIGENCIA_STATUS` (estado temporal da norma) e `AUTHORITY_LEVELS`
  (autoridade da fonte) — nunca colapsados num único booleano.
- `rag/legal_validation/citation_parser.py` — `parse_citacao()`: extrai
  artigo/parágrafo/inciso/alínea/diploma de uma citação em texto livre,
  reaproveitando `detect_articles()`/`CORPUS_HINTS` de `search_hybrid.py`
  (não duplicado).
- `rag/legal_validation/citation_validator.py` — `validar_citacao()`
  (REQ-027/028): resolve a citação contra `index_artigos.json` (lido
  direto, sem instanciar `HybridSearcher`), extrai o bloco de texto real
  do artigo/parágrafo/inciso e confere correspondência exata — nunca por
  proximidade semântica. `enriquecer_resultados()` (REQ-024/025/026):
  envolve a saída de `HybridSearcher.query()`/`search()` no modelo
  canônico, com `validation_status` derivado do tipo de correspondência
  (`indice_artigos` = correspondência exata; `hibrida` = relevância, não
  validação).
- `rag/legal_validation/source_authority.py` — `classificar_autoridade()`
  (REQ-025): determinística, configurável via `rag/config.yaml`
  (`validacao_juridica.autoridade_por_corpus`); corpus fora do mapa cai em
  `NAO_VERIFICADA` (fail closed).
- `rag/legal_validation/temporal_status.py` — `vigencia_de()` (REQ-026):
  sempre `NAO_VERIFICADA` hoje — decisão deliberada e documentada, não uma
  lacuna esquecida (nenhuma fonte real de verificação temporal existe na
  infraestrutura atual).
- `rag/legal_validation/provenance.py` — `proveniencia()` (REQ-029):
  corpus + arquivo + caminho relativo + diploma + dispositivo, para toda
  fonte validada/enriquecida.
- `docs/adr/ADR-0007-camada-validacao-juridica.md` — decisão da separação
  Retrieval ≠ Legal Validation.
- `tests/test_legal_validation.py` — 24 testes (mesmo padrão sem
  framework): metadados completos/parciais/enum inválido, autoridade
  oficial/desconhecida, vigência sempre não verificada, citação existente/
  inexistente/inciso correto/incorreto/parágrafo correto/inexistente/
  diploma correto/incompatível/abreviada/ambígua, anti-hallucination
  (`art. 9999`), incompatibilidade de inciso por proximidade, separação
  score-alto ≠ validado. Usa exclusivamente o corpus legislativo público —
  nenhuma fixture toca `rag/jurisprudencia/` (PEND-002/ADR-0006).
- `rag/config.yaml`: nova seção `validacao_juridica.autoridade_por_corpus`
  (REQ-044).

### Testado
- `python tests/test_legal_validation.py` — 24/24.
- `python tests/test_rag_search.py` — 8/8 (sem regressão).
- `python rag/avaliar_recuperacao.py` — top-1 75% (18/24), top-3 88%
  (21/24) — idêntico ao baseline, `legal_validation` não altera
  `search_hybrid.py`.
- `python tests/test_template_engine.py` — 10/10 (subsistema não tocado).
- `claude plugin validate .` — sem novos warnings.

### Status dos requisitos da Fase 5
- **REQ-024** (metadados) — `[PARCIAL]`: a *estrutura* suporta todos os
  campos (`fonte_juridica()`); os corpora legislativos *preenchem*
  id/diploma/norma/artigo/parágrafo/inciso/alínea/texto/fonte. `url` e
  `data_verificacao` ficam `None` — nenhum dos dois é derivável com
  segurança do corpus atual (nenhum compilado traz URL por artigo; nenhuma
  verificação foi de fato executada) — `None` explícito, não inventado.
- **REQ-025** (autoridade de fontes) — `[PRONTO]` para os 6 corpora
  legislativos (todos `OFICIAL`, configurável); `[AUSENTE]` para
  jurisprudência (PEND-002, corpus não indexado).
- **REQ-026** (vigência) — `[PRONTO]` como *mecanismo* (estado explícito,
  fail closed); todo o corpus está, por design, em `NAO_VERIFICADA` — não
  há, hoje, nenhuma fonte real de verificação temporal integrada.
- **REQ-027** (verificação obrigatória de citação) — `[PRONTO]`:
  `validar_citacao()` só devolve `VALIDADA` com correspondência exata de
  texto.
- **REQ-028** (citação não encontrada) — `[PRONTO]`: `NAO_VALIDADA` +
  sugestão opcional (nunca promovida) via busca híbrida direcionada.
- **REQ-029** (proveniência jurídica) — `[PRONTO]` para os 6 corpora
  legislativos.
- **REQ-030** (proveniência factual) — `[PARCIAL]`, por design: proveniência
  factual pertence ao pipeline processual (extração de fatos de
  documentos do processo), que é escopo da Fase 6 — Contestação, não
  desta fase. Nenhuma extração de fatos foi implementada aqui.

### Pendências conhecidas
- `PEND-001` e `PEND-002` inalteradas (ver `docs/PENDENCIAS.md`).
- REQ-024 (`url`, `data_verificacao`) e REQ-026 (vigência real) só evoluem
  se/quando uma fonte externa de verificação for integrada — fora do
  escopo desta fase (nenhum serviço externo foi consultado).
- Camada de sugestão de candidato (§16) importa `HybridSearcher` sob
  demanda; se os módulos de embeddings não estiverem instalados,
  degrada para `sugestao: None` silenciosamente — mesmo estilo de
  degradação já usado em `search_hybrid.py`, mas vale registrar que
  `validar_citacao(..., sugerir_candidato=True)` nunca falha por isso.

## [0.4.0] - 2026-08-18 — Fase 4 (RAG Jurídico)

A auditoria da Fase 4 encontrou um RAG jurídico já funcional, migrado de um
projeto anterior do usuário ("RAG JURÍDICO"): 434 chunks (CPC, CC, CDC,
L8987, L9427, REN1000), embeddings TF-IDF+LSA e semânticos, busca híbrida
BM25+denso com lookup direto por artigo, calibração de confiança e avaliação
contra gold-set (`rag/avaliar_recuperacao.py`, baseline top-1 75%/top-3 88%).
Ingestão, normalização, chunking, embeddings, indexação, busca lexical,
busca vetorial e fusão já estavam `[PRONTO]` para os 6 corpora legislativos
antes desta fase — não foram reconstruídos.

O trabalho real desta fase foi religar o que já estava sinalizado como
pendente para ela (REQ-044, ver nota em `rag/config.yaml` desde a Fase 1) e
resolver a decisão que `ADR-0006` reservava explicitamente para este ponto
(indexação de jurisprudência).

### Adicionado — Fase 4 (RAG Jurídico)
- `rag/search_hybrid.py`: novo estágio explícito de **reranking**
  (SPEC-0001 §15: fusão → reranking → contexto) — reordena os top-3k
  candidatos da fusão BM25+denso por um pequeno reforço de cobertura de
  termos (`peso_rerank_cobertura`, padrão 0.05) antes do corte final em k.
  Extraído como `HybridSearcher._rerank()` (staticmethod), testável
  isoladamente sem carregar o índice completo.
- `tests/test_rag_search.py` — 8 testes (padrão assert + `__main__`, sem
  framework, igual a `tests/test_template_engine.py`): religação de config,
  fallback de config ausente, tokenização, detecção de artigos, reranking
  isolado, smoke da busca híbrida, e guarda de regressão do gold-set via
  `rag/avaliar_recuperacao.py`.

### Corrigido
- **REQ-044** — `rag/search_hybrid.py` e `rag/avaliar_recuperacao.py` agora
  leem `alpha` e os limiares de confiança (`CONF_LSA`, `CONF_SEM`) de
  `rag/config.yaml` em vez de constantes hardcoded. Fallback automático
  (com aviso) para os mesmos valores hardcoded se `pyyaml` não estiver
  instalado ou o arquivo não puder ser lido — sem mudança de comportamento
  nesse caso.
- `rag/requirements.txt`: `pyyaml` movido do bloco "Opcional" para o
  "Núcleo" — agora é lido diretamente por `search_hybrid.py`, não só por
  `build_embeddings_semantic.py`.

### Testado
- `python rag/avaliar_recuperacao.py` — top-1: 75% (18/24), top-3: 88%
  (21/24) — **idêntico ao baseline pré-Fase-4**, confirmando que a
  religação de config e o novo estágio de reranking não regrediram a
  qualidade de recuperação.
- `python tests/test_rag_search.py` — 8/8.

### Pendências conhecidas
- **PEND-002** (nova, registrada em `docs/PENDENCIAS.md`): indexação de
  jurisprudência (REQ-018) **adiada por decisão explícita do usuário** —
  `rag/jurisprudencia/` (57 fichas com dados de cliente real no bloco
  "Contexto Estratégico", conforme `ADR-0006`) permanece fora da busca
  híbrida. Sem fase bloqueante; retomar quando o usuário decidir entre
  expurgar-e-indexar ou indexar-tudo-local-only (alternativas já registradas
  em `ADR-0006`).
- `rag/index_artigos.json` tem mojibake (`CAP�TULO`) no campo `capitulo` de
  pelo menos alguns registros do corpus CPC — cosmético (não afeta o lookup
  por artigo, que usa `art_inicio`/`art_fim` numéricos, só o texto exibido);
  não corrigido nesta fase por ser assunto de conteúdo pré-existente, não de
  religação de configuração ou reranking.
- REQ-024 (metadados mínimos) está `[PARCIAL]` para os corpora legislativos:
  id/diploma/artigo/texto presentes via frontmatter YAML dos chunks; URL,
  data de publicação/verificação e vigência (REQ-025/026, "Autoridade de
  Fontes" e "Vigência") pertencem à Fase 5 — Validação Jurídica, não a esta.
- `rag/scripts/` da estrutura da SPEC (REQ-001) não existe — os scripts do
  RAG ficam direto em `rag/*.py`, divergência pré-existente da migração
  (Fase 0/1), não alterada nesta fase por não ter sido apontada como
  bloqueio e por risco de quebrar caminhos relativos já em produção sem
  necessidade concreta.

## [0.3.0] - 2026-08-18 — Fase 3 aprovada

Resolve a "Atenção — divergência de arquitetura" que ficava pendente na
versão anterior: o usuário escolheu a arquitetura híbrida (placeholder +
edição direta de OOXML) e confirmou que o `.docx` oficial já existia,
totalmente estruturado. **Fase 3 — Template Engine: encerrada e aprovada
pelo usuário em 2026-08-18.**

### Adicionado — Fase 3 (Template Engine)
- `templates/contestacao/modelo-oficial.docx` — movido de
  `Templates/Contestação/` (caminho não canônico) para o caminho da SPEC,
  conteúdo intocado. Segue fora do git (ADR-0006).
- `templates/contestacao/schema.json` — 13 placeholders **auditados
  diretamente no DOCX real**, não a lista hipotética original da SPEC.
- `scripts/docx_template_engine.py` — motor de substituição por manipulação
  cirúrgica de nós `<w:t>` (nunca reconstrói o documento; nunca toca em
  `<w:pPr>`/estilos/imagens), com Template Lock por comparação estrutural
  (`word/document.xml` deve ser exatamente template + substituição
  controlada; todo outro arquivo deve ficar byte-idêntico).
- `scripts/render_docx.py`, `scripts/validate_placeholders.py`,
  `scripts/validate_template.py` — CLIs finas sobre o motor (REQ-032,
  REQ-034, REQ-016).
- `scripts/requirements.txt` — dependências transitivas do toolkit externo
  `docx` (defusedxml, lxml); o toolkit em si não é vendorizado, é localizado
  em tempo de execução (`~/.claude/skills/docx` ou `~/.agents/skills/docx`).
- `tests/test_template_engine.py` — 10 testes: 9 sobre XML sintético
  (sempre rodam) + 1 pipeline completo contra o DOCX real (roda só se ele
  existir localmente; SKIP explícito em CI/clone limpo).

### Corrigido
- `docs/specs/SPEC-0001.md` (REQ-014/REQ-015) e `CLAUDE.md` (§14): lista de
  placeholders atualizada para os 13 reais do DOCX. Removidos `TIPO_ACAO`,
  `TITULO_TESE_FATICA`, `VALOR_DANO_MORAL` (não existem no template real —
  ele é uma Contestação com Reconvenção por fraude/irregularidade em
  medição de energia, não uma Contestação genérica com pedido de dano
  moral). `FOTOS_DA_IRREGULARIADE` mantido com a grafia exata do DOCX
  (erro de digitação real no arquivo, sem o "D" de "IRREGULARIDADE") — a
  SPEC já tinha sido editada com uma lista mesclada (16 itens, grafia
  corrigida) que não batia com o arquivo real; corrigido para os 13 exatos.

### Testado
- `tests/test_template_engine.py` — 10/10, incluindo geração completa
  contra o DOCX real com Template Lock aprovado e detecção positiva de
  adulteração (troquei "COELBA" por texto arbitrário no XML gerado e
  confirmei que o Template Lock reprova).
- `python rag/avaliar_recuperacao.py` — sem regressão (mesmo baseline:
  top-1 75%, top-3 88%).
- `claude plugin validate .` — sem novos warnings.

### Notas técnicas
- Placeholders ficam fragmentados entre `<w:r>` no DOCX bruto mesmo com
  formatação idêntica — confirmado empiricamente em 2 dos 13. O motor
  depende do merge de runs do `unpack.py` do skill `docx` para consolidá-los
  antes de substituir; não reimplementamos esse merge.
- `garantir_utf8()`: no Windows, encoding padrão cp1252 quebrava o
  validador do toolkit `docx` em texto com acentuação; os CLIs se
  relançam automaticamente em modo UTF-8 (via subprocess — `os.execvpe`
  causou segmentation fault neste ambiente Git Bash/MSYS).
- `validate_template.py` regenera uma peça de referência com os mesmos
  dados em vez de comparar contra um único unpack do template: o
  pretty-print/condense do toolkit OOXML não é perfeitamente idempotente
  entre gerações, e uma comparação ingênua acusava divergência de espaço
  em branco entre tags (fora de qualquer `<w:t>`) que não era mudança de
  conteúdo real.

### Pendências conhecidas
- **PEND-001** (registrada formalmente em `docs/PENDENCIAS.md`, bloqueia a
  Fase 7): `FOTOS_DA_IRREGULARIADE` tratado como texto/legenda; inserção
  real de imagem embutida (drawing/blip) não implementada nesta fase — não
  ficou claro pela auditoria se o campo espera foto de fato.
- Nó `<w:t>` com mais de um placeholder não é suportado (nenhum caso assim
  existe no DOCX real; falha explícita se acontecer).
- Nenhuma seção condicional (`INV-008`) foi encontrada no DOCX — Template
  Lock cobre só substituição simples de placeholder por ora.

## [0.2.0] - 2026-08-18

### Adicionado
- **Fase 2 — Skills transversais**, usando as skills que o usuário já tinha
  prontas (não geradas do zero — correção de um primeiro rascunho autoral
  que foi descartado):
  - `skills/redator-peca-processual-elite/` — `SKILL.md` +
    `references/edicao-docx-timbrado.md`.
  - `skills/humanizer-pt-br/` — `SKILL.md` + `README.md` + `LICENSE`
    (projeto de terceiro sob MIT, github.com/mackswendhell/humanizer-pt-br;
    atribuição preservada conforme exigido pela licença).
  - `skills/calendario-forense-tjba-2026/` — `SKILL.md` com o calendário
    forense TJBA 2026 já verificado pelo usuário (Decreto Judiciário TJBA
    nº 1050/2025, DJE 05/12/2025).
  - `skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py`
    — utilitário adicional (não faz parte do pacote original do usuário):
    calculadora determinística de dias úteis/feriados/suspensões, com
    guarda fail-closed (REQ-012) para quando o calendário não estiver
    verificado. `feriados_forenses_tjba_2026.json` populado com os mesmos
    dados citados no `SKILL.md`.

### Testado
- `claude plugin validate .` — passa sem novos warnings.
- `calcular_tempestividade.py --demo` — 4/4 checagens, incluindo o
  "Exemplo verificado" do próprio `SKILL.md` (termo final 09/06/2026 e
  07/07/2026), batendo exatamente com o cálculo automatizado — valida a
  transcrição do calendário e a aritmética de dias úteis.

### Segurança
- `.gitignore` ampliado (`/*.docx`, `~$*.docx`): durante a fase, um `.docx`
  de timbrado real apareceu solto na raiz do repositório. Foi retirado do
  stage antes de qualquer commit; a regra passa a cobrir estruturalmente
  esse caso, não só por checagem manual.

### Pendências conhecidas
- Ver "Atenção — divergência de arquitetura" acima ([Não lançado]).
- Campo `tools`/`allowed-tools` no frontmatter de `SKILL.md`: um linter do
  editor aponta ambos como não suportados por "VS Code agents"; o
  `claude plugin validate` (autoridade para este plugin) aceita os arquivos
  sem erro. Mantido como está — sinalizado, não corrigido às cegas.

## [0.1.0] - 2026-08-18

### Adicionado
- **Fase 0 — Auditoria**: mapeamento completo do repositório, Gap Analysis
  contra a SPEC-0001, riscos e plano de implementação. Nenhuma alteração de
  código nesta fase.
- **Fase 1 — Fundação**:
  - `.claude-plugin/plugin.json` — manifesto do plugin.
  - `VERSION`, `LICENSE`, `.env.example`, `.gitignore`.
  - `rag/requirements.txt` — dependências Python do RAG, antes implícitas.
  - `rag/config.yaml` — parâmetros do RAG centralizados para religação
    futura (Fase 4); comportamento do `search_hybrid.py` não foi alterado.
  - `docs/adr/ADR-0006-assets-institucionais.md`.
  - Normalização de caminhos: `CLAUDE.MD` → `CLAUDE.md`,
    `Docs/Specs/SPEC-0001.md` → `docs/specs/SPEC-0001.md`.
  - Inicialização do controle de versão (`git init`) com commit inicial.
  - `author` em `.claude-plugin/plugin.json`, resolvendo o warning do
    `claude plugin validate`.

### Testado
- `claude plugin validate .` — passa sem warnings.
- `python rag/avaliar_recuperacao.py` — top-1: 75% (18/24), top-3: 88%
  (21/24), idêntico ao baseline pré-existente: confirma que a normalização
  de caminhos e os novos arquivos não regrediram a busca híbrida.

### Segurança
- `rag/jurisprudencia/` (fichas de jurisprudência e textos brutos de peças
  reais do escritório) passa a ser ignorado pelo git por padrão — ver
  `docs/adr/ADR-0006-assets-institucionais.md`. Antes desta versão, o
  repositório não tinha `.gitignore` e nada impedia que esse conteúdo fosse
  versionado.

### Pendências conhecidas
- REQ-018 (jurisprudência no corpus RAG) segue `[PARCIAL]`: ainda não
  indexada na busca híbrida.
- `templates/`, `skills/`, `commands/`, `scripts/`, `tests/` ainda não
  existem — previstos para as Fases 2, 3 e 6.
- REQ-036/037/038 (`/contestacao`, `/updateEde`, `/atualizar-rag`) serão
  implementados como Skills invocáveis (`skills/<nome>/SKILL.md`), não como
  `commands/*.md` — a documentação oficial do Claude Code trata `commands/`
  como formato legado.
- `claude plugin validate` aponta que `CLAUDE.md` na raiz não é carregado
  como contexto de projeto para quem instala o plugin — esperado, pois este
  arquivo governa o desenvolvimento do repositório, não o comportamento
  entregue ao usuário final (isso cabe às Skills). Registrado para eventual
  esclarecimento na SPEC.
