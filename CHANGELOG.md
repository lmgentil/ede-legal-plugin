# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e
este projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.10.1] - 2026-08-27 — `/atualizar-ede` transformado em verificador puro de versão (Etapa 5.9-I)

### Modificado
- `skills/atualizar-ede/SKILL.md` reescrita por inteiro: deixou de
  "orientar e validar" a atualização (gate de `$CLAUDE_PLUGIN_ROOT`,
  detecção de escopo via `/plugin list`, condução passo a passo de
  `/plugin marketplace update`/`/plugin update`) e passou a ser
  exclusivamente um **VERIFICADOR DE VERSÃO**: identifica a versão
  instalada, consulta a última versão oficialmente publicada, compara e
  informa status — nada além disso. `allowed-tools` reduzido a só
  `WebFetch` (sem Bash/Python, sem `CLAUDE_PLUGIN_ROOT`/`os.environ` em
  tempo de execução, sem comandos `/plugin`, sem detecção de escopo, sem
  self-update).
- Versão instalada passa a ser um valor literal embutido no próprio
  `SKILL.md` (não lida de arquivo/variável de ambiente em runtime) —
  guarda de sincronismo obrigatória (`VERSION == plugin.json == versão
  embutida na Skill`) em `tests/test_atualizar_ede_skill.py`, para que
  divergência vire teste vermelho, nunca versão errada relatada em
  silêncio.
- Versão oficial mais recente passa a ser consultada via GitHub Releases
  API (`GET /repos/lmgentil/ede-legal-plugin/releases/latest`) — nunca
  `main`/`VERSION` do repositório (branch de desenvolvimento, pode estar
  à frente de qualquer versão realmente publicada). Comparação sempre
  por SemVer numérico componente a componente, nunca lexicográfica de
  string (`scripts/comparar_versao.py`, novo, utilitário testado — não é
  dependência operacional da Skill).
- Comportamento fail-closed explícito para os três casos de falha:
  nenhuma Release publicada ainda (404), GitHub indisponível/resposta
  inválida, e versão instalada não identificável — nenhum deles é
  tratado como "atualizado".
- `README.md`, `docs/adr/ADR-0008-distribuicao-marketplace.md` e
  `docs/specs/SPEC-0001.md` (REQ-039) atualizados para refletir o
  contrato definitivo; histórico das duas decisões descartadas ao longo
  da própria Etapa 5.9-I (condução manual do `/plugin update`; exigência
  de asset `.zip` para considerar uma Release válida) preservado só como
  registro, explicitamente marcado como superado.

## [0.10.0] - 2026-08-26 — Renumeração dinâmica, Modelo Institucional como Fonte Primária, Zona de Complementação Documental e portabilidade via CLAUDE_PLUGIN_ROOT

### Corrigido (Etapa 5.6 — orquestração e entrega da Contestação)
- `INV-CONTESTACAO-ENTREGA-DOCX` (`docs/specs/SPEC-0001.md` §54,
  `CLAUDE.md` §7): achado do Teste Real em que a execução encerrava a
  solicitação de elaboração da Contestação entregando só a análise
  estratégica, anunciando RAG/Redator/Humanizer como "próximos passos".
  Causa raiz em `skills/estrategista-contestacao-ede/SKILL.md` §9, que
  instruía entregar a análise como artefato final e sugerir o próximo
  passo mesmo quando acionada internamente pela orquestração de
  `contestacao` — agora distingue acionamento pela orquestração (análise
  é insumo interno, sem "próximo passo") de acionamento direto pelo
  usuário (comportamento anterior preservado). `skills/contestacao/
  SKILL.md` ganha nova §11 com os modos de operação
  (PRODUÇÃO/ANÁLISE/CONSULTIVO/TESTE), execução contínua sem checkpoint
  por etapa interna em modo produção, e as duas únicas hipóteses normais
  de interrupção (decisão humana obrigatória pendente; fail-closed
  técnico/fático real). Novo teste de governança
  `tests/test_orquestracao_entrega_contestacao.py`. Correção exclusiva de
  orquestração/entrega — redação, template, placeholders, blocos, RAG,
  tempestividade, DataJud e demais regras de conteúdo não foram alteradas.

### Adicionado (INV-NUMERACAO-DINAMICA-CONTESTACAO)
- Novo `scripts/docx_numeracao_engine.py`: recalcula deterministicamente
  os prefixos numéricos dos subtítulos (nível 2/3) após a composição de
  blocos — nível 1 (títulos-badge) continua na lista numerada nativa do
  Word (`numId=17`), já dinâmica por construção. Exclusão de bloco
  provoca renumeração automática dos sobreviventes, sem lacuna; título
  numerado residual, duplicidade, salto ou inconsistência hierárquica
  causam fail-closed, nunca correção silenciosa. `scripts/
  docx_block_engine.py` aciona a renumeração entre a composição e a
  substituição de placeholders; Template Lock passa a cobrir também a
  renumeração (`docs/specs/SPEC-0001.md` §55). 16 novos testes
  (`tests/test_docx_numeracao_engine.py`).

### Adicionado (INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA — Etapa 5.7)
- Novo `scripts/docx_context_engine.py`: extrai, somente leitura, o
  contexto institucional real ao redor de cada placeholder gerativo
  (título/subtítulo mais próximo, texto fixo imediatamente anterior/
  posterior, bloco condicional ancestral) diretamente do
  `modelo-oficial.docx` — nunca de transcrição manual. `scripts/
  gerar_contestacao.py` passa a chamar essa extração como primeira
  etapa, incondicional, do pipeline; falha nela aborta antes de
  qualquer leitura de documento do caso. Regra PRESERVAR >
  COMPLEMENTAR > CRIAR: o texto institucional fixo nunca é reescrito/
  parafraseado pela IA; Redator e Humanizer passam a receber esse
  contexto como referência não editável (`docs/specs/SPEC-0001.md`
  §§56-57).

### Corrigido (infraestrutura de testes)
- `sys.exit` disparado durante a fase de *collection* do pytest (fora
  de qualquer teste) podia interromper a suíte antes mesmo de rodar —
  corrigido em `scripts/docx_template_engine.py`/`scripts/
  gerar_contestacao.py`; novo `conftest.py` e `tests/
  test_infra_garantir_utf8_import_safe.py` cobrem a regressão. Sem
  efeito sobre o comportamento em produção do plugin.

### Adicionado (INV-ZONA-COMPLEMENTACAO — Etapa 5.8-B/5.8-C/5.8-C.1, ADR-0010)
- Terceira categoria de zona de intervenção textual, ao lado de bloco e
  placeholder: `ZONA_METODOLOGIA_APURACAO` (bloco-pai
  `CALCULOS_RECUPERACAO_CONSUMO`) conecta a fundamentação normativa
  fixa do tópico 3.4 aos dados concretos de apuração do processo —
  normalmente vazia, só existe com suporte fático documentado e
  conteúdo efetivamente produzido pelo Redator; nunca é perguntada ao
  advogado, nunca vira placeholder (os 13 continuam 13), nunca provoca
  inclusão de bloco.
- Proveniência estruturada: cada dado da zona declara tipo/valor/
  unidade/fonte/natureza (documental/derivado), com operação matemática
  opcional quando mantém relação com outros dados, verificada em
  `Decimal` (nunca float para dinheiro), com álgebra de unidades por
  cancelamento — controle de coerência, nunca recálculo autônomo da
  cobrança; os valores dos Memoriais de Cálculo/Faturamento são
  preservados como fonte de verdade, nunca recalculados pela IA.
- `INV-PARAGRAFO-380` passa a contar apenas caracteres efetivos (sem
  espaços) por parágrafo; o teto agregado por bloco continua bruto —
  duas contenções deliberadamente distintas, não uniformizadas.
- `INV-CONTINUIDADE-ZONA` (Etapa 5.8-E/5.8-D.1, `docs/specs/
  SPEC-0001.md` §60): a zona demonstra, o texto institucional conclui —
  novo comparador genérico (`paragrafos_compartilham_abertura`, sem
  blacklist de frases) vira gate fail-closed em `gerar_contestacao.py`,
  rejeitando parágrafo de zona que repita a abertura do texto
  institucional imediatamente anterior/posterior.
- 82 novos testes (`tests/test_zonas_complementacao.py`).

### Corrigido (Etapa 5.9-A/5.9-B — portabilidade via CLAUDE_PLUGIN_ROOT)
- `atualizar-ede` e `contestacao` resolviam recursos internos do plugin
  (`scripts/*.py`, `templates/contestacao/modelo-oficial.docx`,
  `templates/contestacao/blocos.json`, módulos de `rag/`) por caminho
  relativo ao diretório de trabalho corrente — funcionava só por
  coincidência quando o `cwd` era o próprio checkout do plugin, nunca
  no uso real do advogado (pasta do caso). Ambas as Skills passam a
  resolver esses recursos exclusivamente via `$CLAUDE_PLUGIN_ROOT`, com
  fail-closed explícito (sem fallback para `./scripts`, `../scripts`,
  cwd ou diretório alternativo) quando a variável não está disponível.
  Recursos do próprio caso (`fatos.json` etc.) continuam relativos ao
  workspace do advogado. Melhorias de portabilidade para execução fora
  do checkout do plugin — não resolvem, e não têm relação com, o
  problema documentado de sincronização de marketplaces pessoais no
  Claude Cowork.

## [0.9.1] - 2026-08-21 — Etapa 5.3–5.5, DataJud, vedação de pesquisa jurisprudencial e dano moral documental

### Adicionado (INV-VALOR-DANO-MORAL-DOCUMENTAL — 13º placeholder)
- `{{VALOR_DANO_MORAL_PRETENDIDO}}` (`docs/specs/SPEC-0001.md` §53):
  inserido manualmente pelo advogado no `modelo-oficial.docx`, dentro do
  bloco `DESCABIMENTO_DANO_MORAL` já catalogado — representa
  exclusivamente o valor de indenização por danos morais pretendido pela
  parte autora na petição inicial, dado documental (nunca gerado/
  estimado/arredondado). Só é exigido quando o bloco está `INCLUIR`,
  automaticamente (sem gate novo em `blocos.json` — o mecanismo já
  existente de `docx_template_engine.validar_placeholders` sobre a XML
  composta cobre os dois casos). Aceita frase de "sem quantificação"
  ("a ser arbitrado pelo Juízo"); rejeita valores monetários divergentes
  no mesmo campo (fail-closed) e formato fora do padrão BR. Novo
  `_validar_valor_dano_moral_pretendido` em
  `scripts/validate_placeholder_semantics.py`. 12→13 placeholders.

### Adicionado (Etapa 5.5 — tempestividade natural e não-repetição fática)
- `INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM` (`docs/specs/SPEC-0001.md`
  §52): esta Contestação sempre calcula tempestividade pelo
  procedimento comum do CPC (15 dias úteis, art. 335), nunca a Lei
  9.099/95, mesmo quando o rito concreto admitiria aplicação
  subsidiária; `scripts/gerar_contestacao.py` aplica o padrão fixo e
  aborta diante de qualquer especificação incompatível.
  `TEMPESTIVIDADE_CASO` passa a receber prosa jurídica natural e curta
  (nunca dump robótico do tipo "TEMPESTIVO: termo inicial...", nunca
  data ISO, nunca menção ao Juizado Especial) — a memória de cálculo
  completa permanece só na auditoria interna do pipeline.
- `INV-NAO-REPETICAO-FATICA`: o mesmo fato técnico não pode reaparecer
  quase palavra por palavra em `REALIDADE_FATICA`,
  `IRREGULARIDADE_ENCONTRADA` e `DESENVOLVIMENTO_TECNICO_
  IRREGULARIDADE` — cada placeholder narrativo passa a ter função
  própria e exclusiva. Backstop determinístico narrow (não exaustivo)
  em `scripts/validate_placeholder_semantics.py`
  (`_validar_nao_repeticao_realidade_fatica`).

### Adicionado (INV-JUIZO-DATAJUD)
- `{{JUIZO}}` deixa de ser conteúdo gerativo (`docs/specs/SPEC-0001.md`
  §51): resolvido deterministicamente por `scripts/datajud_client.py` a
  partir de `NUMERO_PROCESSO` — identifica o tribunal pelo número CNJ,
  consulta a API Pública DataJud/CNJ para o órgão julgador real, resolve
  a comarca via API do IBGE, monta `AO JUÍZO DA [...] DA COMARCA DE
  [...]` em caixa alta. Fail-closed em qualquer indisponibilidade/
  ambiguidade/processo não encontrado — nunca presume a vara. Chave
  pública do DataJud versionada em `DATAJUD_API_KEY_PADRAO` (exceção
  expressa do secret scan, ver `CLAUDE.md` §18).

### Corrigido (INV-CONTESTACAO-SEM-TRAVESSAO)
- `redator-peca-processual-elite` e `humanizer-pt-br` inseriam o
  travessão ("—", U+2014) no texto da Contestação (`docs/specs/
  SPEC-0001.md` §50). Backstop determinístico em `scripts/
  validate_placeholder_semantics.py` (`_checar_travessao`) roda sobre
  todo placeholder fornecido — travessão encontrado aborta o pipeline,
  nunca é substituído automaticamente.

### Removido (correção pontual)
- `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA` removido definitivamente
  (`docs/specs/SPEC-0001.md` §49) — o modelo oficial já traz a
  argumentação de evolução de consumo inteiramente fixa, sem marcador;
  a IA nunca mais a gera/parafraseia. Bloco `EVOLUCAO_CONSUMO` continua
  existindo, agora sem placeholder próprio.

### Adicionado (Etapa 5.3 e 5.3-B — Calibração final do Teste Real 01-B)
- Sete achados reais corrigidos (`docs/specs/SPEC-0001.md` §47):
  endereçamento institucional (`JUIZO` sempre em caixa alta, padrão "AO
  JUÍZO DA VARA [...] DA COMARCA DE [...]"), proibição de meta-
  informação no documento final, densidade por bloco além do teto de
  380 caracteres por parágrafo, `PEDIDOS_FINAIS` curto e composicional,
  `LOCAL_DATA` sempre Salvador independentemente da comarca do
  processo.
- Contrato atômico de `IRREGULARIDADE_ENCONTRADA` e normalização visual
  dos parágrafos multiline (`docs/specs/SPEC-0001.md` §48,
  `INV-PARAGRAFO-HERDA-TEMPLATE`): cada linha lógica de um placeholder
  multiline vira um `<w:p>` irmão real herdando o `w:pPr` do parágrafo-
  placeholder, em vez de `<w:br/>` dentro de um único parágrafo — corrige
  bug real de espaçamento visual divergente do texto nativo do modelo.

### Vedado (INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL)
- Achado do Teste Real 01-B (`docs/specs/SPEC-0001.md` §46):
  comportamento "Calling Jurisprudências.ai 5 times" durante a
  elaboração da Contestação, nunca autorizado pela arquitetura. Decisão
  arquitetural permanente: a Contestação nunca pesquisa jurisprudência
  (RAG, web, MCP, agente) — disponibilidade de uma ferramenta no
  ambiente não é autorização de uso. `skills/contestacao/SKILL.md`
  corrigida; teste audita o texto das Skills, sobrevivendo à existência
  futura de qualquer ferramenta de pesquisa.

### Adicionado (Etapa 5.2 — Calibração redacional, pertinência fática e controle de decisões)
- Sete novas invariantes decorrentes do Teste Real 01 (`docs/specs/SPEC-0001.md`
  §45, `CLAUDE.md` §7): `INV-PARAGRAFO-380` (parágrafo de conteúdo variável
  ≤380 caracteres, `scripts/validate_paragrafos.py`, novo `stage=paragrafo_380`
  em `scripts/gerar_contestacao.py`), `INV-NAO-REDUNDANCIA` e
  `INV-NAO-REDUNDANCIA-NORMATIVA` (comportamentais), `INV-SINOPSE-ESTRITAMENTE-
  AUTORAL` (`SINOPSE_FATOS` exclusivamente narrativa — backstop lexical em
  `scripts/validate_placeholder_semantics.py`), `INV-RECONVENCAO-AUTORIZACAO-
  EXPRESSA` (`RECONVENCAO` muda de `decision_mode: "estrategista"` para
  `"humano"` em `templates/contestacao/blocos.json` — autorização expressa do
  advogado via `AskUserQuestion`, não mais decisão do estrategista sozinho),
  `INV-BLOCO-SUPORTE-FATICO` (princípio geral), `INV-GRATUIDADE-LINKED` e
  `INV-CORTE-EFETIVO`. `estado_processual.json` (novo, opcional no diretório
  do caso) carrega ambos os estados; nenhum dos dois aceita ocorrência
  lexical como prova.
- **Correção pontual pré-commit (auditoria do usuário)**:
  `PRELIMINAR_REVOGACAO_GRATUIDADE` havia sido implementada como
  `decision_mode: "estrategista"` + gate `requires_fact` — gate + decisão
  estratégica, não o vínculo determinístico exigido ("a preliminar de
  gratuidade deve ser linked"). Corrigido para novo `decision_mode:
  "state_linked"` (`templates/contestacao/blocos.json`, campo
  `linked_fact: "GRATUIDADE_CONCEDIDA"`) — o estado do bloco *é* o estado
  processual (`true`→`INCLUIR`, ausente/`false`→`EXCLUIR`,
  `"INDETERMINADO"`→aborta), nunca uma decisão da etapa estratégica;
  decisão manual em `decisoes_blocos.json` para este bloco é rejeitada
  explicitamente (`scripts/docx_block_engine.py`,
  `_estado_fato_processual`, nova resolução `state_linked` antes dos
  containers `derived`). `LICITUDE_CORTE_SUSPENSAO`/`INV-CORTE-EFETIVO`
  preserva o mecanismo de gate original — a correção é específica da
  gratuidade.
- Corrigido bug real de composição: `compor_blocos`
  (`scripts/docx_block_engine.py`) só descia por `w:sdtContent`, então um SDT
  aninhado fora dessa cadeia (`INLINE:COM_RECONVENCAO`, dentro de
  `wps:txbx/w:txbxContent` — a caixa de texto do título) nunca era alcançado
  e ficava intocado independentemente da decisão de `RECONVENCAO`. Recursão
  generalizada para descer por qualquer elemento, não só `w:sdtContent`.
- `skills/contestacao/SKILL.md`, `skills/estrategista-contestacao-ede/SKILL.md`,
  `skills/redator-peca-processual-elite/SKILL.md` atualizadas para explicar
  como cumprir as sete invariantes acima. `estrategista-contestacao-ede`
  continua obrigatória (`INV-CONTESTACAO-ESTRATEGIA` inalterada).
- Fixture `tests/fixtures/contestacao/happy_path/placeholders.json`
  reescrita (parágrafos ≤380 caracteres, `SINOPSE_FATOS` sem linguagem
  defensiva) — mesmos fatos/valores sintéticos, sem alteração de conteúdo
  substantivo. Novos testes em `tests/test_blocos_contestacao.py`,
  `tests/test_docx_block_engine.py`, `tests/test_e2e_contestacao.py`,
  `tests/test_validate_placeholder_semantics.py`, e novos arquivos
  `scripts/validate_paragrafos.py`/`tests/test_validate_paragrafos.py`.

### Adicionado (Gate 5.1 — Trava de validação humana da Contestação)
- `INV-GATE-CONTESTACAO` (`docs/specs/SPEC-0001.md` §32, `CLAUDE.md` §27,
  `tests/test_gate_contestacao.py`): enquanto a Contestação não for
  validada pelo usuário em uso real, nenhuma nova peça processual
  (Recurso Inominado, Embargos, ou qualquer outra) pode ser iniciada, e
  nenhuma generalização multipeça prematura da arquitetura é permitida.
  Suíte técnica verde (141/141 testes) não equivale a validação — só
  manifestação expressa do usuário libera a trava.

### Adicionado (Etapa 5 — Motor Composicional de Blocos Condicionais)
- `templates/contestacao/blocos.json` — catálogo estrutural formal dos 11
  blocos condicionais/container/inline do template real (auditado
  diretamente no DOCX, Etapas 4-A a 4-D): `PRELIMINARES`
  (`CONTAINER_DERIVED`, `derived_rule: ANY_CHILD_INCLUDED`) com filhos
  `PRELIMINAR_CDC_INAPLICAVEL`/`PRELIMINAR_REVOGACAO_GRATUIDADE`;
  `DEVER_LEGAL_FISCALIZACAO`, `DESNECESSIDADE_AVISO_PREVIO`,
  `CALCULOS_RECUPERACAO_CONSUMO`, `LICITUDE_CORTE_SUSPENSAO`,
  `NEXO_CAUSAL_INDEMONSTRADO`, `DESCABIMENTO_DANO_MORAL`
  (`CONDICIONAL_PADRAO`); `EVOLUCAO_CONSUMO`, `RECONVENCAO`
  (`CONDICIONAL_HIBRIDO`, placeholder interno); `INLINE:COM_RECONVENCAO`
  (`decision_mode: linked`, espelha `RECONVENCAO`).
- `scripts/docx_block_engine.py` — motor de composição: validação
  estrutural do catálogo, validação/resolução de decisões
  (`INCLUIR`/`EXCLUIR`/`INDETERMINADO`, containers `DERIVED`, inline
  `linked`), cruzamento dos `<w:sdt>` reais do template contra o
  catálogo, composição determinística via `lxml.etree` (unwrap/remove,
  pós-ordem, preservando parágrafos/runs/drawings/bookmarks/
  `mc:AlternateContent` originais), e orquestração completa
  (`gerar_peca_com_blocos`) reaproveitando `docx_template_engine.py`
  (substituição de placeholders/FF0000/pack) sem duplicar nada disso.
- `scripts/docx_template_engine.py` — `verificar_template_lock()` ganha
  parâmetro opcional `transformar_xml` (Template Lock composicional: o
  "esperado" passa a ser template → composição de blocos → substituição
  de placeholders; lógica de diff arquivo-a-arquivo reaproveitada, não
  duplicada).
- `scripts/gerar_contestacao.py` — nova etapa `block_composition`
  (`_etapa_blocos`, entre `strategy` e `rag_legal_validation`): lê
  `decisoes_blocos.json` do caso, valida catálogo, aborta
  (`PIPELINE_ABORTED`) em qualquer `INDETERMINADO`/decisão ausente/
  catálogo inconsistente; `_etapa_template` passa a chamar
  `gerar_peca_com_blocos`; relatório final ganha `blocos_incluidos`/
  `blocos_excluidos`/`containers_derivados`/`blocos_indeterminados`.
- `skills/contestacao/SKILL.md` — nova seção §4A (decisões de blocos
  condicionais): a etapa estratégica decide, a Skill pergunta ao
  advogado via `AskUserQuestion` quando `INDETERMINADO` for
  factualmente resolvível, nunca inventa, nunca gera DOCX com
  `INDETERMINADO` pendente.
- `docs/specs/SPEC-0001.md` — `REQ-002-B`/`INV-COMPOSICAO-BLOCOS` (§5):
  formaliza a separação decisão (estratégica) × mecânica (motor
  documental), os 4 tipos de bloco, e a extensão do Template Lock.
- `CLAUDE.md` — nota breve sobre `INV-COMPOSICAO-BLOCOS`, remetendo à
  SPEC para os detalhes (sem duplicar).
- `tests/test_blocos_contestacao.py` (17 testes) e
  `tests/test_docx_block_engine.py` (14 testes, incluindo
  `LOCAL_ONLY` ponta a ponta contra o template real) — 15 fixtures
  negativas (parent/child inexistente, ciclo, tipo incompatível, leaf
  com children, ids/tags duplicados, dependency malformada, SDT sem
  tag/sdtContent, tag desconhecida/ausente, cardinalidade inválida,
  estado `INDETERMINADO`/inválido/ausente).
- `templates/contestacao/modelo-oficial.docx` (asset local, fora do
  git — ADR-0006) migrado para embutir os 11 `<w:sdt>` de bloco/
  container/inline, validado em 3 camadas (lxml estrutural + XSD do
  toolkit `docx` + renderização Word/PDF real) antes da aplicação;
  dois defeitos de fronteira de bloco encontrados e corrigidos durante
  a validação (não presentes na versão final): um `<w:bookmarkEnd>`
  solto (`_Hlk225341328`) atribuído ao bloco vizinho errado, e uma
  ordem de processamento ascendente que deslocava os índices do bloco
  seguinte (`PRELIMINAR_REVOGACAO_GRATUIDADE` capturava o intervalo
  errado) — ambos detectados por checagem de integridade de bookmark
  antes de qualquer geração real, corrigidos, revalidados.

### Bloqueado
- Nenhuma pendência bloqueia a Fase 9 nem a publicação externa
  tecnicamente/juridicamente. Publicação real (remote, push, release)
  segue sendo uma decisão e ação operacional futura, não uma pendência.

## [0.9.0] - 2026-08-18 — Gate PEND-004: licença proprietária source-available

Fecha `PEND-004`. `LICENSE` reescrita como licença proprietária de
código-fonte disponível ("source-available"), implementando literalmente
a matriz de direitos aprovada em `docs/PENDENCIAS.md`. Primeira definição
real de direitos de uso desde a criação do projeto — antes, o texto
reservava todos os direitos sem conceder nenhum uso explícito além de
"transparência e consulta"; passa a autorizar expressamente execução,
modificação local e uso profissional sem pedido de autorização.

### Alterado
- `LICENSE` — reescrita em 5 seções: (1) permitido sem autorização
  (visualizar/baixar/clonar, instalar e executar — inclusive via
  marketplace —, estudar, modificar cópias locais, uso profissional
  inclusive por escritórios de advocacia diferentes do titular); (2)
  permitido com condições (criar/distribuir Derivados, mantendo avisos
  de copyright/licença e identificação clara como versão modificada,
  sem se apresentar como o projeto original); (3) proibido sem
  autorização prévia e expressa por escrito (redistribuir o original por
  canal próprio, sublicenciar, comercializar o plugin ou derivados,
  apropriar-se da autoria, remover avisos, usar nome/marcas de forma a
  sugerir endosso inexistente); (4) conteúdo de terceiros (preservada,
  sem alteração de mérito); (5) ausência de garantia (preservada, sem
  alteração de mérito). Não adota MIT/Apache-2.0/GPL/AGPL nem licença de
  terceiro — texto próprio, redigido especificamente para este projeto.
- `README.md` (seção "Licença") — resumo dos três blocos de direitos,
  sem afirmar *open source*/*free software* (nenhum dos dois é o caso).
- `docs/PENDENCIAS.md` — `PEND-004`: `ABERTA` → **`RESOLVIDA`**. Seções
  históricas (Contexto/Risco/Critério de resolução/Decisão superveniente)
  preservadas sem reescrita; `Fechamento` documenta o mapeamento
  seção-a-seção entre a matriz aprovada e o texto final da `LICENSE`.
- `docs/adr/ADR-0009-distribuicao-publica-template-externo.md` — seção
  "Atualização — Gate PEND-004 resolvido": remove o único bloqueio
  jurídico que a ADR apontava para publicação externa.

### Testado
- `python tests/test_marketplace.py` — 7/7 (sem regressão; VERSION/
  plugin.json ressincronizados em 0.9.0).
- `python tests/test_pacote_distribuicao.py` — 5/5.
- `python tests/test_validar_instalacao.py` — 3/3.
- `python tests/test_e2e_contestacao.py` — 6/6.
- `python tests/test_contestacao_skill_dependencies.py` — 8/8.
- `python tests/test_validate_fatos.py` — 16/16.
- `python tests/test_legal_validation.py` — 24/24.
- `python tests/test_rag_search.py` — 8/8.
- `python rag/avaliar_recuperacao.py` — top-1 75%/top-3 88% (sem regressão).
- `python tests/test_template_engine.py` — 10/10.
- `claude plugin validate .` (marketplace) e
  `claude plugin validate .claude-plugin/plugin.json` (plugin) — sem
  novos warnings.

### Pendências
- `PEND-001` (`DEFERRED`), `PEND-002` (`ADIADA`), `PEND-003` (`ABERTA`)
  — inalteradas.
- `PEND-004` — **RESOLVIDA** nesta versão.
- Nenhum remote criado, nenhum push, nenhuma publicação externa
  realizada — por instrução explícita.

## [0.8.1] - 2026-08-18 — Consolidação pós-Fase 8: distribuição pública + template externo

Não é uma nova fase funcional — consolida formalmente, na governança do
projeto, decisões arquiteturais já tomadas: **repositório e plugin serão
públicos**; **o template institucional é definitivamente um asset
externo**, nunca distribuído com o plugin (decisão encerrada — as
alternativas A/B/C de `ADR-0006` não voltam a ser apresentadas).

### Adicionado
- `docs/adr/ADR-0009-distribuicao-publica-template-externo.md` (novo) —
  registra as duas decisões: repositório/plugin públicos; template
  institucional externo (opção B de `ADR-0006`, confirmada). Acesso
  técnico ao repositório ≠ autorização jurídica irrestrita — quem
  disciplina isso é a `LICENSE` (`PEND-004`, gate próprio).
- `docs/specs/SPEC-0001.md` §29 — **REQ-046** (repositório/plugin
  públicos, template externo), **REQ-047** + **INV-015** (ausência do
  template não invalida instalação; fail closed restrito à etapa que
  depende dele, preservando as etapas anteriores como concluídas).
- `CLAUDE.md` §13 — regras explícitas: nunca commitar o `.docx` real,
  nunca baixar/reconstruir automaticamente o timbrado, nunca tratar sua
  ausência como instalação inválida.
- `tests/test_pacote_distribuicao.py`: +2 testes —
  `test_modelo_oficial_nao_esta_no_historico_git` (varre `git log --all`,
  não só o índice atual — `.gitignore` não apaga histórico já existente;
  confirmado: **nunca esteve no histórico**) e
  `test_modelo_oficial_e_asset_externo_nao_de_instalacao_base` (não
  tracked, não referenciado em `marketplace.json`, opcional em
  `validar_instalacao.py`, e `gerar_peca()` falha explicitamente —
  `status: "FALHOU", etapa: "template"` — quando ausente, sem criar
  arquivo de saída).
- `tests/test_e2e_contestacao.py`: +1 teste —
  `test_fail_closed_template_institucional_ausente`: roda o pipeline
  completo com template inexistente e confirma que fatos, tempestividade,
  estratégia, RAG/validação e redação+humanização completam normalmente
  (`status: "ok"`) e só `template_engine` aborta — demonstra a
  separação `PLUGIN_INSTALLED` × `INSTITUTIONAL_TEMPLATE_INSTALLED` na
  prática, não só em documentação.
- `README.md`: nova seção "Template institucional", explicando a decisão
  e suas 6 consequências práticas para quem instala.
- `docs/PENDENCIAS.md`: `PEND-004` reescrita — não é mais "conflito a
  resolver entre publicar ou não publicar" (isso já foi decidido); passa
  a "definir a redação da licença proprietária/source-available",
  incluindo os parâmetros já aprovados (permitido/restrito/proibido) como
  critério para essa redação futura — **a `LICENSE` em si não foi
  reescrita nesta consolidação**, por decisão explícita de tratá-la como
  gate específico subsequente.
- `docs/adr/ADR-0006-assets-institucionais.md`: seção "Atualização —
  Consolidação pós-Fase 8" — fecha a escolha entre as alternativas A/B/C,
  remete a `ADR-0009` para o detalhe; os demais itens da ADR permanecem
  vigentes sem alteração.
- `tests/test_template_engine.py`: `test_pipeline_completo_contra_template_real`
  rotulado explicitamente como `LOCAL_ONLY` na documentação do arquivo —
  mesmo comportamento de sempre (SKIP sem o `.docx` real), só a
  classificação ficou explícita.

### Testado
- `python tests/test_pacote_distribuicao.py` — 5/5 (era 3/5, +2 novos).
- `python tests/test_e2e_contestacao.py` — 6/6 (era 5/6, +1 novo).
- `python tests/test_marketplace.py` — 7/7.
- `python tests/test_validar_instalacao.py` — 3/3.
- `python tests/test_contestacao_skill_dependencies.py` — 8/8.
- `python tests/test_validate_fatos.py` — 16/16.
- `python tests/test_legal_validation.py` — 24/24.
- `python tests/test_rag_search.py` — 8/8.
- `python rag/avaliar_recuperacao.py` — top-1 75%/top-3 88% (sem regressão).
- `python tests/test_template_engine.py` — 10/10.
- `claude plugin validate .` (marketplace) e
  `claude plugin validate .claude-plugin/plugin.json` (plugin) — ambos
  sem novos warnings.

### Auditoria de segurança pré-publicação
`git log --all` para `modelo-oficial.docx`: **nunca esteve no
histórico** (não só fora do índice atual). Varredura de CPF, CNPJ real,
e-mail pessoal além do titular já conhecido, tokens/segredos, e caminhos
locais pessoais em todo o conteúdo rastreado: **nada encontrado**. Um
achado cosmético, não sensível: o corpus público da REN ANEEL 1.000/2021
(`rag/chunks_REN1000/`, `rag/_originais_pre_split/`) carrega marcas
"Uso Interno CPFL" residuais da extração original do PDF fonte — texto
normativo público, sem dado de cliente; registrado aqui, não removido
nesta consolidação (fora do escopo desta tarefa).

### Pendências
- `PEND-001` (`DEFERRED`) e `PEND-002` (`ADIADA`) — inalteradas.
- `PEND-003` — inalterada, tamanho de `svd.joblib`, sem ação nesta tarefa
  (Git LFS/reconstrução sob demanda continuam não implementados, por
  instrução explícita).
- `PEND-004` — reescrita (ver acima); **continua ABERTA e bloqueando
  publicação externa** — a `LICENSE` definitiva não foi redigida nesta
  tarefa.

## [0.8.0] - 2026-08-18 — Fase 8 (Distribuição, Instalação e Atualização)

Torna o EDE Legal Plugin instalável/atualizável via Claude Code Plugin
Marketplace, sem exigir Git do usuário final. Testado de ponta a ponta
**de verdade** nesta máquina (não simulado): marketplace adicionado,
plugin instalado, componentes conferidos, atualização 0.7.0→0.8.0
aplicada e confirmada.

### Auditoria prévia
Sem remote git configurado (`git remote -v` vazio) — repositório
local-only até aqui; nada publicado. Documentação oficial do Claude Code
consultada (não memória/exemplo de terceiros — SPEC-0001 Fase 8 §61) via
agente `claude-code-guide` e confirmada empiricamente rodando os
comandos reais (`claude plugin marketplace add`, `claude plugin install`,
`claude plugin update`, `claude plugin details`, `claude plugin tag
--dry-run`).

### Adicionado — Fase 8
- `.claude-plugin/marketplace.json` (novo): marketplace `ede`, um único
  plugin (`ede-legal-plugin`) com `source: "./"` — sem duplicar a árvore
  do projeto em `plugins/<nome>/` (SPEC-0001 Fase 8 §42). Entrada do
  plugin **não declara `version` própria** — achado desta fase: se
  declarasse, o valor de `plugin.json` venceria silenciosamente, sem
  aviso.
- `skills/atualizar-ede/SKILL.md` (novo) — `/updateEde` (REQ-037): não
  existe self-update programático no Claude Code (confirmado na
  documentação oficial); a Skill identifica a versão atual, conduz os
  comandos oficiais (`/plugin marketplace update` +
  `/plugin update ... --scope <mesmo da instalação>` — nuance de escopo
  descoberta testando de verdade, documentada) e valida o resultado com
  `scripts/validar_instalacao.py`. Nunca afirma sucesso sem essa
  validação (Fail Closed).
- `scripts/validar_instalacao.py` (novo) — checagem pós-instalação/
  pós-atualização: 5 Skills essenciais, `schema.json`, `rag/config.yaml`,
  `rag/index_artigos.json`, sincronização `VERSION`==`plugin.json`. O
  `.docx` institucional real é conferido mas **não obrigatório** (asset
  privado, ADR-0006) — sua ausência não reprova a instalação.
  `--json` para consumo programático; saída `UPDATE_FAILED` (não um
  falso "sucesso") quando algo obrigatório falta.
- `docs/adr/ADR-0008-distribuicao-marketplace.md` (novo) — decisão da
  arquitetura de distribuição (marketplace no mesmo repositório, fonte
  única de versão, `/updateEde` como fachada sem self-update).
- `docs/adr/ADR-0006-assets-institucionais.md`: seção "Atualização —
  Fase 8" — reabre, sem decidir, o destino do template institucional
  (público/privado-separado/download autenticado); resolve (sem precisar
  de nova decisão) o placeholder de titular da `LICENSE`, que já estava
  preenchido; registra a tensão nova entre `LICENSE` (todos os direitos
  reservados) e distribuição via marketplace público (`PEND-004`).
- `README.md`: seções "Instalação", "Atualização", "Desinstalação",
  "Solução de problemas" e "Segurança" — comandos oficiais reais, não
  inventados; nota explícita de que ainda não há remote git configurado.
- `tests/test_marketplace.py` (novo, 7 testes): `marketplace.json`
  parseável, campos obrigatórios, identidade preservada (não renomeado
  silenciosamente), `source` do plugin resolve para um `plugin.json`
  real, entrada do marketplace não declara `version` própria,
  `VERSION`==`plugin.json` (equivalente automatizado ao
  `claude plugin tag . --dry-run` oficial).
- `tests/test_pacote_distribuicao.py` (novo, 3 testes): varre
  `git ls-files` (o que realmente viaja com o plugin) contra padrões
  proibidos (`.env`, `.key`/`.pem`, `workspace/`, `processos_reais/`,
  `rag/jurisprudencia/`, o zip legado, `.textos_varredura/`,
  `modelo-oficial.docx`); confirma que `.gitignore` cobre os ativos
  sensíveis conhecidos; confirma nenhum `.docx` solto na raiz rastreado.
- `tests/test_validar_instalacao.py` (novo, 3 testes): instalação atual
  do repositório passa; instalação faltando as 5 Skills reporta
  `UPDATE_FAILED`; ausência do `.docx` institucional não reprova.
- `docs/PENDENCIAS.md`: `PEND-003` (novo) — `rag/embeddings/svd.joblib`
  (~81 MB, ~91% do repositório rastreado) infla o tamanho do
  clone/instalação; não bloqueia uso, registrado para avaliação futura
  (Git LFS ou reconstrução sob demanda). `PEND-004` (novo) — tensão
  `LICENSE` × distribuição via marketplace público; bloqueia só
  publicação externa.

### Testado — real, não simulado
- `claude plugin marketplace add "./"` → `ede` adicionado.
- `claude plugin install ede-legal-plugin@ede --scope local -y` → sucesso.
- `claude plugin details ede-legal-plugin@ede` → **6 Skills detectadas**
  (`atualizar-ede`, `calendario-forense-tjba-2026`, `contestacao`,
  `estrategista-contestacao-ede`, `humanizer-pt-br`,
  `redator-peca-processual-elite`), 0 agents, 0 hooks, **0 MCP servers**
  (confirma SPEC-0001 Fase 8 §54), 0 LSP servers.
- `claude plugin marketplace update ede` → sucesso.
- `claude plugin update ede-legal-plugin@ede --scope local` → **"updated
  from 0.7.0 to 0.8.0"**, confirmado em `claude plugin list` após.
- `claude plugin validate .` (marketplace) e
  `claude plugin validate .claude-plugin/plugin.json` (plugin) — ambos
  passam; nenhum warning novo além do pré-existente sobre `CLAUDE.md`.
- `claude plugin tag . --dry-run` — confirma que `plugin.json` e a
  entrada do marketplace concordam (exit não-zero só por working tree
  sujo antes do commit, comportamento esperado).
- `python tests/test_marketplace.py` — 7/7.
- `python tests/test_pacote_distribuicao.py` — 3/3.
- `python tests/test_validar_instalacao.py` — 3/3.
- `python tests/test_e2e_contestacao.py` — 5/5 (sem regressão).
- `python tests/test_contestacao_skill_dependencies.py` — 8/8.
- `python tests/test_validate_fatos.py` — 16/16.
- `python tests/test_legal_validation.py` — 24/24.
- `python tests/test_rag_search.py` — 8/8.
- `python rag/avaliar_recuperacao.py` — top-1 75% (18/24), top-3 88%
  (21/24) — idêntico ao baseline.
- `python tests/test_template_engine.py` — 10/10.

### Pendências
- `PEND-001` (`DEFERRED`) e `PEND-002` (`ADIADA`) — inalteradas.
- `PEND-003` (nova) e `PEND-004` (nova) — ver acima.
- Publicação externa (GitHub, visibilidade, release) **não realizada**
  nesta fase — sem remote configurado, por instrução explícita de não
  criar um arbitrariamente. Instalação testada só localmente.
- `/atualizar-rag` (REQ-038) fora do escopo desta fase — não implementado.

## [0.7.0] - 2026-08-18 — Fase 7 (Integração End-to-End da Contestação)

Prova, com um caso sintético completo, que os componentes das Fases 1-6
funcionam integrados: extração factual → tempestividade → estratégia →
RAG → validação jurídica → redação → humanização → placeholders →
Template Engine → Template Lock → DOCX final.

### Auditoria prévia
Interfaces das Fases 3-6 já eram estáveis e não precisaram de
reformulação: `docx_template_engine.gerar_peca(template, schema, dados,
output) -> dict`, `legal_validation.validar_citacao(texto) -> dict`,
`validate_fatos.validar_fatos(fatos) -> (ok, erros)`,
`calcular_tempestividade.calcular_tempestividade(...) -> ResultadoTempestividade`.
Nenhum subsistema foi reconstruído — só integrado.

**Limitação estrutural confirmada (não uma lacuna de implementação):**
`estrategista-contestacao-ede`, `redator-peca-processual-elite` e
`humanizer-pt-br` são Skills do Claude Code (arquivos de instrução para
um agente LLM), não há API Python para executá-las de dentro de um
script. O orquestrador consome a SAÍDA delas e confere estruturalmente
que ela existe e tem a forma esperada; a produção dessa saída para o
cenário de teste foi um procedimento manual assistido, executado por este
agente e registrado em `docs/E2E_FASE7.md` (SPEC-0001 Fase 7 §33/§34) —
não simulada por código.

### Adicionado — Fase 7
- `scripts/gerar_contestacao.py` (novo) — orquestrador executável: coordena
  fatos (REQ-030) → tempestividade → verificação estrutural da saída do
  estrategista (INV-CONTESTACAO-ESTRATEGIA) → RAG + validação jurídica →
  placeholders (saída de redator+humanizer) → Template Engine/Lock.
  Fail closed em cada estágio: `PIPELINE_ABORTED` com `stage`/`reason`
  sempre que uma etapa obrigatória faltar, for inválida, ou um
  placeholder crítico (`VALOR_FRA`) ficar como sentinela de ausência —
  nunca gera DOCX como se a etapa tivesse ocorrido. Marcador de fotos
  (`PEND-001`/DEFERRED) injetado automaticamente, não lido do caso.
- `tests/fixtures/contestacao/happy_path/` (novo) — caso sintético
  completo (5 documentos fictícios, `fatos.json` com o novo campo `tipo`
  — ver abaixo —, `estrategia.md` real de 15 seções, `citacoes.json` com
  8 candidatas, `placeholders_redator.json` + `placeholders.json`
  mostrando o antes/depois da humanização). Produção documentada em
  `docs/E2E_FASE7.md`.
- `tests/fixtures/contestacao/fail_closed_valor_ausente/` (novo) — mesmo
  caso, `VALOR_FRA` sinalizado como não informado (memorial de cálculo
  ausente).
- `tests/test_e2e_contestacao.py` (novo, 5 testes): happy path completo
  (todas as 6 etapas `ok`, 7/8 citações validadas, Template Lock OK, DOCX
  íntegro — ZIP válido, XML bem formado, header/footer preservados,
  conteúdo sintético esperado presente, nenhum placeholder residual);
  fail-closed por dado essencial ausente (`PIPELINE_ABORTED`, nenhum DOCX
  no disco); fail-closed por Skill estratégica indisponível (arquivo
  ausente) e por saída estruturalmente inválida (seções faltando).
  Cenário de Template Lock reprovando adulteração já tinha cobertura
  equivalente em `tests/test_template_engine.py` — não duplicado
  (SPEC-0001 Fase 7 §28).
- `docs/E2E_FASE7.md` (novo) — procedimento manual assistido e registro
  da execução real das três Skills sobre o cenário sintético.
- `scripts/validate_fatos.py`: novo campo opcional `tipo` no contrato de
  fato (REQ-030) — `FATO_DOCUMENTADO` (default) / `ALEGACAO_AUTORAL` /
  `INFERENCIA` / `DADO_NAO_INFORMADO` (SPEC-0001 Fase 7 §9): o pipeline
  agora pode distinguir fato comprovado de alegação da parte autora sem
  contraprova, evitando que uma vire a outra silenciosamente. Retrocompatível
  — fato sem `tipo` continua válido, tratado como `FATO_DOCUMENTADO`.
  `tests/test_validate_fatos.py` ganhou 4 testes (16/16).

### Corrigido — bugs localizados encontrados pelo E2E (SPEC-0001 Fase 7 §3/§45)
- `rag/search_hybrid.py` (`CORPUS_HINTS`): "REN ANEEL 1.000/2021" (grafia
  usada em citações reais, com "ANEEL" entre "REN" e o número) não batia
  com nenhuma dica de corpus — só "REN 1.000" sem "ANEEL" funcionava.
  Adicionadas as variantes "ren aneel 1000"/"ren aneel 1.000". Sem
  regressão (`avaliar_recuperacao.py`: top-1 75%/top-3 88%, idêntico).
- `rag/legal_validation/citation_validator.py` (`_marcador_artigo_re`):
  o regex de localização de artigo exigia pontuação (`.`/`)`) logo após o
  número — bate com o estilo do CPC/REN1000 ("Art. 335.") mas não com o
  do CDC ("Art. 6º São direitos..."), fazendo toda citação de artigo do
  CDC falhar com "marcador não localizado" mesmo com o artigo existindo.
  Trocado por negative lookahead (não seguido de dígito) — funciona nos
  dois estilos de pontuação, sem abrir brecha para casar "Art. 6" dentro
  de "Art. 60". Sem regressão (`test_legal_validation.py`: 24/24).

### Testado
- `python tests/test_e2e_contestacao.py` — 5/5 (novo).
- `python tests/test_contestacao_skill_dependencies.py` — 8/8.
- `python tests/test_validate_fatos.py` — 16/16 (12 + 4 novos de `tipo`).
- `python tests/test_legal_validation.py` — 24/24.
- `python tests/test_rag_search.py` — 8/8.
- `python rag/avaliar_recuperacao.py` — top-1 75% (18/24), top-3 88%
  (21/24) — idêntico ao baseline.
- `python tests/test_template_engine.py` — 10/10.
- `claude plugin validate .` — sem novos warnings.

### SPEC GAP
Nenhum encontrado. As duas correções acima foram bugs localizados em
componentes já aprovados (regex/dicionário de sinônimos), não decisões
arquiteturais — resolvidas sem alterar nenhum REQ/INV da SPEC-0001
(SPEC-0001 Fase 7 §44/§45).

### Pendências
- `PEND-001` (`DEFERRED`) e `PEND-002` (`ADIADA`) — inalteradas, sem
  bloqueio.
- MCP, `/updateEde`, marketplace, updater, distribuição, jurisprudência
  real e inserção automática de fotografia: **não implementados nesta
  fase**, por instrução explícita — pertencem à Fase 8 ou a versões
  futuras.
- O E2E cobre um único fact-pattern (irregularidade de medição com
  reconvenção). Novos fact-patterns dentro do mesmo template devem
  reaproveitar o mesmo orquestrador — não exigem novo pipeline.

## [0.6.1] - 2026-08-18 — Correção arquitetural: estrategista-contestacao-ede passa a obrigatória + fechamento (PEND-001 DEFERRED)

**Revoga** a decisão registrada em `[0.6.0]` abaixo, que tratava
`estrategista-contestacao-ede` como etapa "recomendada, não uma
dependência obrigatória". Por decisão explícita do usuário, ela passa a
dependência **obrigatória** da elaboração de Contestação, no mesmo grau de
`redator-peca-processual-elite` e `humanizer-pt-br`. O texto do registro
`[0.6.0]` abaixo **não foi reescrito** — descreve fielmente a decisão
vigente naquele momento; esta entrada é quem a substitui.

### Alterado
- `CLAUDE.md` §7 — reestruturado em "Dependências transversais" (redator +
  humanizer, toda peça) vs. "Dependências específicas por tipo de peça"
  (Contestação → `estrategista-contestacao-ede`, sem generalizar para
  outras peças ainda inexistentes). Adicionado o bloco nomeado "Invariante
  — Estratégia obrigatória da Contestação" e o fluxo conceitual
  documentos → extração factual → estrategista → RAG → validação jurídica
  → redator → humanizer → placeholders → Template Engine → Contestação.
  §8 (Tempestividade) ganhou a ressalva de que nenhuma Skill processual
  recalcula calendário forense por conta própria quando
  `calendario-forense-tjba-2026` cobre o caso.
- `docs/specs/SPEC-0001.md` §5 — REQ-002 (fluxo da Skill Contestação)
  atualizado para incluir a etapa estratégica na ordem correta (após
  extração factual e datas, antes do RAG); novo **REQ-002-A** (dependência
  obrigatória do estrategista) com o bloco formal
  **`INV-CONTESTACAO-ESTRATEGIA`**; TEST-005 e o checklist de critérios de
  aceite da v1 (§37) atualizados para incluir `estrategista-contestacao-ede`
  como obrigatória.
- `skills/contestacao/SKILL.md` — reescrito: nova seção "0. Dependências
  obrigatórias" no topo (lista parseável, usada pelo teste estrutural
  abaixo); pipeline (§3) reordenado para extração factual → tempestividade
  → **estrategista (obrigatório, pipeline para sem ele)** → RAG →
  validação → redator → humanizer → placeholders — igual ao fluxo
  formalizado no CLAUDE.md; §4 reescrita para deixar explícito que a etapa
  NÃO pode ser dispensada por "caso simples" (linguagem antiga removida) e
  que falha/ausência do estrategista deve ser reportada, nunca contornada
  com uma análise resumida ad-hoc.

### Adicionado
- `tests/test_contestacao_skill_dependencies.py` (novo, 8 testes) — guarda
  estrutural: lê o conteúdo real de `skills/contestacao/SKILL.md` (não só
  confere que o diretório existe) e falha se `estrategista-contestacao-ede`
  deixar de estar declarada como obrigatória, se `redator-peca-processual-elite`/
  `humanizer-pt-br` deixarem de estar, se qualquer linha que mencione o
  estrategista usar linguagem de "opcional/recomendada/facultativa/
  dispensável", se a etapa estratégica deixar de preceder a redação no
  arquivo, ou se a declaração de Fail Closed (sem fallback silencioso)
  desaparecer. Verificado manualmente que o teste detecta a regressão:
  reintroduzir "recomendada" na linha do estrategista faz
  `test_estrategista_declarado_como_obrigatorio` falhar.

### Auditoria de consistência
Buscadas ocorrências de "opcional"/"recomendada"/"recomendado"/
"facultativa"/"facultativo" associadas a `estrategista-contestacao-ede`
em todo o repositório. Resultado: só existiam em `CLAUDE.md`,
`skills/contestacao/SKILL.md` e `docs/specs/SPEC-0001.md` — todas
corrigidas nesta entrada. As três ocorrências remanescentes estão no
registro histórico `[0.6.0]` abaixo (mantido intacto, é fato histórico) e
em `skills/estrategista-contestacao-ede/SKILL.md:201` ("Preliminares
recomendadas" — cabeçalho de seção do template de saída da própria skill,
sobre teses jurídicas recomendadas ao advogado; não descreve a skill em
si, conteúdo do usuário, não alterado). Nenhum ADR versionado menciona a
skill — nenhum ADR precisou de correção.

### PEND-001 — reclassificação (fechamento desta correção)

Decisão superveniente do usuário: **na V1, fotografias da irregularidade
não são inseridas automaticamente** — inserção manual pelo advogado após a
geração do DOCX. Detalhe completo em `docs/PENDENCIAS.md`
("Decisão superveniente", seção `PEND-001`).

- `docs/PENDENCIAS.md` — `PEND-001`: `ABERTA` → **`DEFERRED`**; deixa de
  bloquear a Fase 7. Nova seção "Decisão superveniente" documenta a
  escolha (texto/marcador manual, não imagem embutida) sem reescrever o
  registro histórico da Fase 3 (Contexto/Risco/Critério de resolução
  originais preservados intactos).
- `templates/contestacao/schema.json` — bloco aditivo
  `placeholder_semantics.FOTOS_DA_IRREGULARIADE` (`tratamento_v1:
  "manual_post_edit"`). **Não altera** `editable_placeholders` — o único
  campo que `docx_template_engine.py`/`validate_placeholders.py` de fato
  leem (confirmado lendo o código antes de editar); nenhuma mudança
  funcional do Template Engine, nenhuma implementação de `<w:drawing>`,
  relação de mídia, upload ou seleção automática de fotografia.
- `docs/specs/SPEC-0001.md` §21 (gate de entrada da Fase 7) e `README.md`
  atualizados: `PEND-001` não bloqueia mais.
- `skills/contestacao/SKILL.md` (§1, §9, §10) — placeholder
  `FOTOS_DA_IRREGULARIADE` documentado como marcador textual de pós-edição
  manual (ex.: `"[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"`),
  não legenda da irregularidade nem imagem embutida.
- **Preservado, sem reescrita:** o registro `[0.6.0]` abaixo, e a entrada
  `[0.3.0]` que originou `PEND-001` — ambos verdadeiros no contexto da
  versão em que foram escritos.

### Testado
- `python tests/test_contestacao_skill_dependencies.py` — 8/8.
- `python tests/test_validate_fatos.py` — 12/12 (sem regressão).
- `python tests/test_legal_validation.py` — 24/24 (sem regressão).
- `python tests/test_rag_search.py` — 8/8 (sem regressão).
- `python rag/avaliar_recuperacao.py` — top-1 75%/top-3 88% (sem regressão,
  RAG não foi tocado por esta correção).
- `python tests/test_template_engine.py` — 10/10 (sem regressão — inclui o
  teste de ponta a ponta contra o DOCX real, confirmando que o campo
  aditivo em `schema.json` não afeta Template Lock/renderização).
- `claude plugin validate .` — sem novos warnings.

### Não feito nesta correção (por instrução explícita)
- Fase 7 não iniciada.
- RAG não alterado; MCP não implementado.
- Nenhuma implementação multimídia (upload, seleção, `<w:drawing>`,
  relação de mídia) — `PEND-001` fechada pelo caminho "texto", não "imagem".
- `PEND-002` não retomada; `rag/jurisprudencia/` não lido em massa,
  indexado, movido, sanitizado, copiado ou usado como fixture.
- Template Engine e DOCX oficial não alterados funcionalmente.
- Nenhum código não relacionado foi refatorado.

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
