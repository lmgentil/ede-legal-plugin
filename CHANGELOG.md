# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e
este projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado
- **OAuth de aplicação no EDE MCP Server** (Gate 6.3-D2, ADR-0016). O EDE
  passa a ser Resource Server OAuth 2.0; Descope é o Authorization
  Server. Verificação RS256 com allowlist explícita de algoritmo,
  cabeçalhos JOSE `jku`/`jwk`/`x5u` rejeitados, validação exata de
  issuer e de audience (sem substring, prefixo, hostname ou curinga),
  `exp`/`nbf` com tolerância de 60s, cache de JWKS com TTL e refresh
  limitado, Protected Resource Metadata (RFC 9728) anunciando
  EXATAMENTE UM Resource, `WWW-Authenticate` com `resource_metadata`,
  exigência de escopo (`ede:health`, `ede:legal`) na camada HTTP e por
  ferramenta, `tools/list` filtrado por escopo, Host canônico fixado e
  política de Origin compatível com Claude e ChatGPT (ausente segue para
  o OAuth; presente e inesperada é recusada).
  Novos módulos: `mcp_server/auth_config.py`, `auth_logging.py`,
  `token_verifier.py`, `scope_policy.py`, `http_telemetry.py`.
- Telemetria de segurança somente-metadado, com allowlist FECHADA de
  campos — JWT, `Authorization`, segredos e qualquer conteúdo jurídico
  são estruturalmente incapazes de alcançar o log.
- `tests/test_mcp_oauth.py` e `tests/oauth_harness.py`: 106 testes
  determinísticos, sem rede e sem nenhum segredo real do Descope
  (chaves RSA sintéticas geradas no processo, JWKS em app ASGI de
  memória, issuer/Resource em domínios `.invalid`), incluindo prova de
  DISPATCH ZERO para todo caso negativo de autenticação/autorização.
- **Preparação de ativação de produção do MCP** (Gate 6.3-D3.1,
  ADR-0017). Guard de fail-closed específico do serviço de produção:
  quando `K_SERVICE` (variável injetada pela própria plataforma Cloud
  Run) for exatamente `ede-mcp`, o processo recusa subir sem a camada
  OAuth de aplicação explicitamente habilitada e validamente
  configurada — fecha a lacuna em que, com toda variável `EDE_MCP_*`
  ausente, a autenticação desligava por design (comportamento que
  continua válido para `ede-mcp-staging`, desenvolvimento local e a
  suíte de testes). Novo `mcp_server.auth_config.ProducaoSemAuthInvalida`
  e `servico_de_producao()`, cobertos por 9 novos testes determinísticos
  em `tests/test_mcp_oauth.py`.
  Documentação nova: `docs/adr/ADR-0017-ativacao-producao-mcp.md`
  (arquitetura de ativação de produção aprovada — serviço `ede-mcp`,
  rede pública só após prova de OAuth de aplicação, isolamento total de
  staging, e o desenho da Arquitetura A′ para o Modelo Oficial em
  produção — armazenamento privado, geração fixada, SHA-256 verificado,
  fail-closed, sem busca/reconstrução automática) e
  `docs/mcp-producao-contrato.md` (contrato de variáveis de ambiente
  não secretas do futuro serviço de produção — issuer/JWKS reais
  permanecem pendentes de provisionamento no Descope).
- Clarificação pontual de CLAUDE.md §13 (companheira de ADR-0017): a
  proibição de buscar, baixar ou reconstruir automaticamente o Modelo
  Oficial permanece integral e é explicitada como válida também em
  produção; o único mecanismo futuro permitido é carregar o modelo
  já provisionado pelo titular em armazenamento privado configurado
  explicitamente, com geração/hash fixados e verificados — nunca
  descoberto pelo runtime.
- **Readiness jurídica determinística no EDE MCP Server** (Gate 6.4-A,
  ADR-0015/ADR-0017). `checks.rag` e `checks.modelo_oficial` de
  `ede_health` deixam de ser stubs `NOT_CONFIGURED` fixos: novo módulo
  Core `scripts/legal_readiness.py` (`avaliar_corpus_rag`,
  `avaliar_modelo_oficial`), reutilizado por `mcp_server/server.py`
  (adapter fino, nenhuma lógica de validação duplicada).
  - Corpus RAG: novo `rag/corpus_manifest.json` (fingerprint SHA-256
    determinístico por diploma — CPC/CC/CDC/L8987/L9427/REN1000, 434
    chunks, biblioteca padrão apenas, sem pandas/numpy/pyarrow/
    scikit-learn/rank_bm25/sentence-transformers) — fica `READY` sem
    nenhum provisionamento adicional, porque o corpus já é asset
    público versionado no repositório (ADR-0017 §6). Jurisprudência
    (`C:\Dev\ede-private\rag\jurisprudencia`, dado de caso real) nunca
    entra no manifesto nem na imagem — INV-CONTESTACAO-SEM-PESQUISA-
    JURISPRUDENCIAL permanece intocada.
  - Modelo Oficial: reaproveita
    `instalar_modelo_oficial.validar_contrato_modelo`. Fica `READY`
    somente quando `EDE_MODELO_OFICIAL_PATH`/`EDE_MODELO_OFICIAL_SHA256`
    apontarem para um arquivo já provisionado, com SHA-256 pinado
    batendo e contrato institucional (placeholders/SDTs) conforme;
    ausência das duas variáveis é `NOT_CONFIGURED` (estado real de
    produção hoje — nenhum bucket/Arquitetura A′ foi criado nesta
    rodada). Nunca busca, baixa ou reconstrói o arquivo (CLAUDE.md §13).
  - `mcp_server/Dockerfile`/`.dockerignore`/`requirements.txt`
    atualizados (allowlist nominal) para embutir os cinco módulos Core
    necessários, o contrato institucional público
    (`templates/contestacao/schema.json`/`blocos.json`) e os chunks do
    corpus — nunca o Modelo Oficial `.docx` (privado, ADR-0009) nem
    `rag/embeddings/` (não necessário para a checagem de saúde). Única
    dependência nova: `lxml==6.1.3`.
  - Novos testes: `tests/test_legal_readiness.py` (17 casos — matriz
    completa de READY/NOT_READY/NOT_CONFIGURED/ERROR dos dois
    pré-requisitos). `tests/test_mcp_server.py`,
    `tests/test_mcp_oauth.py` e `tests/test_mcp_streamable_http.py`
    atualizados para o novo baseline real (corpus RAG já íntegro nesta
    checkout) — nenhuma assertion enfraquecida, só corrigida para
    refletir o comportamento correto e intencional desta etapa.
  - Sem mutação de infraestrutura: nenhum bucket GCS criado, nenhum
    upload de asset privado, nenhum deploy de nova revisão de produção.
    `contestacao_status` de produção permanece `NOT_READY` (Modelo
    Oficial ainda não provisionado em runtime remoto).
- **Provisionamento privado do Modelo Oficial via GCS + adapter Core**
  (Gate 6.4-B, Arquitetura A′, ADR-0017 §6). Autorizado pelo Gate 6.4-A
  (`PRIVATE ASSET UPLOAD READY FOR AUTHORIZATION`).
  - Bucket privado `gs://ede-legal-mcp-01-modelo-oficial-privado`
    (`southamerica-east1`, acesso uniforme, prevenção de acesso público
    forçada, sem `allUsers`/`allAuthenticatedUsers`, sem hospedagem de
    site, sem política de retenção/lifecycle). Objeto único
    `modelo-oficial/modelo-oficial.docx`, geração `1789696822240267`,
    SHA-256 idêntico ao relatado no Gate 6.4-A
    (`53adf880cb35a016986f482d6d9bc609118951b9684b77d413fae12a611104d8`)
    — confirmado por download real da geração pinada e validação
    completa (estrutura OOXML + Template Lock) no próprio gate.
  - IAM: `ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com`
    recebeu `roles/storage.objectViewer` escopado só a este bucket —
    nenhum papel de projeto, auditado após a concessão.
  - `scripts/legal_readiness.py`: `avaliar_modelo_oficial` passa a ter
    dois modos de aquisição — GCS (produção; ativa quando qualquer uma
    de `EDE_MODELO_OFICIAL_GCS_{BUCKET,OBJECT,GENERATION}` está
    definida, exigindo as três mais `EDE_MODELO_OFICIAL_SHA256` juntas)
    e local (`EDE_MODELO_OFICIAL_PATH`, Gate 6.4-A, só desenvolvimento/
    teste — nunca definida em produção). Novo adapter
    `_baixar_modelo_oficial_gcs`: baixa exatamente a geração pinada via
    REST/JSON do GCS (`httpx2`, já transitivo via `mcp`), autentica com
    `google.auth.default()` (metadata server em produção; ADC do
    titular fora dela — nenhuma chave de service account em arquivo),
    confere o cabeçalho `x-goog-generation` da resposta contra a geração
    pedida (defesa em profundidade) e nunca tenta outra geração/objeto.
    Validação (SHA-256 + estrutura + Template Lock) extraída para
    `_validar_conteudo_modelo_oficial`, compartilhada pelos dois modos —
    zero duplicação. Único dependente novo: `google-auth==2.58.0`
    (+ `pyasn1`/`pyasn1-modules`, transitivas puro-Python, ~527 KB no
    total) — deliberadamente NÃO `google-cloud-storage` (SDK completo,
    traria `google-api-core`/`google-cloud-core`/`google-resumable-
    media`/`requests`, uma segunda pilha HTTP).
  - Novos testes: 23 casos em `tests/test_legal_readiness.py` (matriz
    completa do adapter GCS — configuração parcial, geração/objeto
    ausentes, SHA divergente, bytes corrompidos, contrato inválido,
    nunca cai para o modo local, limpeza de arquivo efêmero em sucesso e
    falha, nenhum detalhe de baixo nível/conteúdo vaza em `detail`,
    tudo com fakes — nenhum teste da suíte normal acessa GCS real) +
    1 teste de ponta a ponta em `tests/test_mcp_server.py`
    (`ede_health` → GCS → contrato real → READY) + prova real controlada
    (fora da suíte, não commitada): download da geração pinada via
    `gcloud storage cp` autenticado pela sessão já autorizada do
    titular, sem materializar nenhuma credencial nova, confirmando bytes
    → SHA-256 → estrutura → Template Lock → READY.
  - `tests/test_docker_context.py` (novo, 11 testes): prova determinística
    (sem build Docker real) de que toda instrução `COPY` do Dockerfile
    tem liberação correspondente em `.dockerignore`, nenhum `.docx` é
    liberável, nenhum caminho sensível (Modelo Oficial, backups,
    jurisprudência, `ede-private`, credenciais) está na allowlist, e o
    corpus real em disco bate exatamente com os seis diplomas do
    manifesto.
  - CI: `.github/workflows/homologar-mcp-container.yml` ganhou o input
    opcional `publicar_candidato` (default `false`) — quando `true` e só
    depois de todos os testes do gate passarem, publica a imagem
    homologada no Artifact Registry (`ede-mcp/mcp-server`, tag
    `<sha>-candidato`) reaproveitando integralmente a identidade/
    infraestrutura já homologada em `deploy-mcp-staging.yml` (WIF,
    `ede-mcp-deployer`/`ede-mcp-builder`, mesmo `cloudbuild.yaml`) —
    nunca chama `gcloud run deploy`. Listas de dependência
    proibida/esperada e a checagem de assets sensíveis dentro da imagem
    real foram atualizadas para o novo baseline (RAG legítimo na
    imagem, `lxml`/`google-auth` legítimas).
  - Sem mutação de tráfego: nenhum deploy de produção, nenhuma alteração
    de OAuth/rede pública, revisão `ede-mcp` corrente intocada.
- **Correção de dependência do adapter GCS** (Gate 6.4-C1, achado real do
  Gate 6.4-C: primeira tentativa de ativação em produção, revertida em
  segundos por `checks.modelo_oficial=NOT_READY`). Causa raiz confirmada
  nos logs reais do Cloud Run ("Import of Compute Engine auth library
  failed.") e por leitura direta do código-fonte instalado:
  `google.auth.compute_engine._metadata` — o submódulo que
  `google.auth.default()` usa para detectar o ambiente Cloud Run/GCE via
  metadata server — tem `import requests` incondicional, não opcional.
  Sem `requests` instalado, a detecção de ambiente falhava silenciosamente
  (o `except Exception` de `_baixar_modelo_oficial_gcs` mascarava isso
  como `autenticacao_falhou`, comportamento fail-closed correto, mas
  escondendo a causa real do usuário por design de segurança). Adiciona
  `requests==2.34.2` a `mcp_server/requirements.txt` (faixa compatível
  `requests<3.0.0,>=2.30.0` conforme o próprio METADATA de
  `google-auth==2.58.0`) — entra só pela árvore de `google-auth`; nenhuma
  linha do EDE a importa diretamente, `httpx2` continua sendo o único
  cliente HTTP usado explicitamente pelo código do projeto. Novos testes
  (`tests/test_legal_readiness.py`) provam que o import que causou o
  rollback real resolve sem exceção; `tests/test_mcp_oauth.py` e o
  workflow de homologação atualizados para tratar `requests` como
  dependência legítima (nunca `google-cloud-*`/`grpcio`/`protobuf`, que
  continuam proibidos). Candidato anterior
  (`sha256:ae983d27013116d93ed863fc66908af9c21424fa569876fb8494341819ea3133`)
  descartado — nunca mais reutilizado. Sem mutação de produção nesta
  correção: `ede-mcp-00002-c2f` permanece servindo 100% do tráfego.
- **Primeira ferramenta jurídica real do EDE MCP: `ede_preparar_
  contestacao`** (Gate 6.5-A, escopo `ede:legal`, ADR-0015). Prepara um
  Pacote de Contexto determinístico da Contestação para o HOST
  (Claude/ChatGPT) raciocinar e redigir — esta ferramenta nunca redige,
  nunca decide teses/preliminares/Reconvenção, nunca pesquisa
  jurisprudência e nunca consulta DataJud automaticamente. Fronteira
  Host/Core preservada integralmente: todo raciocínio jurídico continua
  no host; o MCP só oferece regras institucionais, corpus legal
  autoritativo, recuperação determinística, contrato de template/schema
  e proveniência.
  - Novo Core `scripts/preparar_contestacao.py`: valida `fatos` (reaproveita
    o contrato de `fatos.json`/REQ-030 sem alteração), expõe o catálogo
    de blocos/zonas condicionais com o estado de gate fático (nunca
    decide inclusão/exclusão), extrai contexto institucional (título +
    texto fixo ao redor, truncado) só dos placeholders efetivamente
    redigíveis, e recupera fontes legais do corpus institucional com
    proveniência completa (`rag/legal_validation/models.py::
    fonte_juridica`, reaproveitado como módulo solto — nunca via
    `legal_validation/__init__.py`, que importaria `rag/search_hybrid.py`
    inteiro).
  - **Nota de produto explícita:** a recuperação de fontes legais desta
    v1 é uma camada de **retrieval lexical determinístico e limitado**
    (pontuação por sobreposição de palavras-chave sobre os chunks já
    embutidos na imagem) — **não é** equivalente ao pipeline híbrido
    BM25 + semântico completo de `rag/search_hybrid.py` (que exigiria
    pandas/numpy/scikit-learn/pyarrow/rank_bm25 na imagem do MCP,
    incompatível com RNF-CUSTO-001 e com o footprint mínimo mantido
    desde o Gate 6.4-A). Distinção mantida explícita no código
    (docstrings de `_buscar_fontes_para_questao`/`_montar_fontes_
    legais`) e nos testes — nunca descrita como "RAG completo".
  - Escopo `ede:legal` (já existente em `auth_config.py` desde o Gate
    6.3-D2, nunca antes usado): `mcp_server/scope_policy.py` mapeia
    `ede_preparar_contestacao -> ede:legal`; `ede_health` continua exigindo
    só `ede:health`; nenhum dos dois escopos implica o outro (verificado
    nas duas direções, contra o servidor real, não um stand-in
    sintético). Escopo de base do transporte permanece só `ede:health`.
  - Entrada estruturada e minimizada: `fatos` (obrigatório),
    `questoes_juridicas`/`estado_processual` (opcionais) — nenhum nome de
    parte, número de processo, CPF/RG/endereço/telefone/email é aceito
    ou necessário. Entrada é efêmera por requisição: nunca gravada em
    disco, nunca adicionada ao RAG, nunca cacheada, nunca logada
    (verificado por teste). Limites explícitos (máx. 30 fatos, 5 questões
    jurídicas, 10 fontes totais) — nunca um dump irrestrito do corpus.
  - Fail-closed: recusa com `PIPELINE_ABORTED` (nunca um pacote parcial
    apresentado como completo) se `contestacao_status` não estiver READY,
    entrada inválida/superdimensionada, ou schema/catálogo institucional
    do próprio plugin corrompido.
  - Refatoração mínima em `scripts/legal_readiness.py`: aquisição pura do
    Modelo Oficial (GCS ou local) extraída para
    `adquirir_bytes_modelo_oficial()`, reaproveitada tanto por
    `avaliar_modelo_oficial()` quanto pelo novo Core — nenhuma duplicação
    da lógica de despacho GCS-vs-local.
  - Novos testes: 23 em `tests/test_preparar_contestacao.py` (Core) + 6
    integrações OAuth reais em `tests/test_mcp_oauth.py` (contra o
    servidor de produção, não sintético) cobrindo a matriz completa do
    gate — entrada válida/inválida/superdimensionada, NOT_READY fail-
    closed, filtragem de escopo nas duas direções, chamada autorizada de
    ponta a ponta, proveniência, retrieval limitado, determinismo,
    ausência de vazamento de log/modelo/jurisprudência.
  - Dependência nova: **nenhuma** (`docx_context_engine.py` e
    `validate_fatos.py` só precisam de `lxml`/biblioteca padrão, já
    presentes). `mcp_server/Dockerfile`/`.dockerignore`/workflow de
    homologação atualizados para incluir os três novos arquivos Core +
    `rag/legal_validation/models.py` (nunca `__init__.py` do pacote).
  - **`ede:legal` implementado e homologado, mas NÃO autorizado a nenhum
    usuário humano em produção nesta rodada** — a política Descope de
    produção continua concedendo só `ede:health`; um gate de autorização
    separado, explícito, é necessário antes de qualquer advogado poder
    chamar esta ferramenta. Produção permanece na revisão do Legal Core
    do Gate 6.4-C Retry, sem nenhuma mutação.
  - `VERSION` passa a `0.13.0` (SemVer minor — nova ferramenta MCP,
    retrocompatível, escopo `ede:legal` nunca exigido de `ede_health`),
    **sem tag e sem GitHub Release** nesta etapa.
- **Robustez da recuperação lexical para questões jurídicas abstratas**
  (Gate 6.5-C1, `scripts/preparar_contestacao.py`). Achado do Gate 6.5-C
  em produção: o capítulo central "Dos Procedimentos Irregulares" (REN1000
  `TII_C07`) ficava fora do top-3 da questão de regularidade do
  procedimento e as questões finais recebiam poucas fontes ou nenhuma
  (CDC/CC ausentes). Causas medidas: (1) texto comparado só por `.lower()`,
  sem normalizar acento nem flexão (`procedimento`/`procedimentos`,
  `irregularidade`/`irregulares`), e stopwords escritas sem acento que
  nunca casavam com o texto acentuado; (2) vocabulário genérico do setor
  ("energia elétrica" no título de capítulos de pré-pagamento) valendo
  quase o mesmo que o assunto real; (3) o teto global de 10 fontes era
  esgotado pelas primeiras questões.
  - Normalização de acento/caixa e radical leve e conservador em PT-BR
    (plural, `-idade`, `-ção`, infinitivo, vogal final), IDF calculado
    sobre o próprio corpus (sem lista manual de palavras do setor),
    IDF² no bônus de título, saturação de frequência no corpo e
    comparação de bigramas sobre radicais.
  - Seleção entre questões **por rodadas** (melhor fonte de cada questão,
    depois a segunda, etc.): nenhuma questão fica sem fonte por causa do
    teto global. Alerta novo (só o índice, nunca o texto da questão) quando
    uma questão não recupera nenhuma fonte.
  - Tabela `CONCEITOS_JURIDICOS` explícita, com **um** conceito
    ("proteção do consumidor"), que só acrescenta termos de consulta com
    peso reduzido; nunca inclui diploma nem chunk. Dois outros conceitos
    avaliados foram descartados por ganho zero em ablation sobre 17
    paráfrases.
  - Contrato do pacote inalterado (`questoes_relacionadas`,
    `artigo_preciso`, `corpus_versao`, `validation_status`, `vigencia`,
    `truncado`, `alertas`). `score_lexical`/`score_final` passam de inteiro
    a decimal ponderado. Dependência nova: **nenhuma**; `VERSION`
    permanece `0.13.0`.
- **Precisão da recuperação jurídica e profundidade de dispositivos**
  (Gate 6.5-C3, `scripts/preparar_contestacao.py`). Achados do Gate 6.5-C2
  (produção, fixture exata SHA-256 `d9059ef3…292ef`): a questão de
  exigibilidade da cobrança de recuperação de consumo recuperava capítulos do
  CPC sobre *cumprimento de sentença* (a REN1000 não entrava no top-3); a de
  proteção do consumidor perdia vagas para capítulos genéricos do setor; e o
  excerto de 400 caracteres do capítulo central (arts. 589-598) cobria só o
  art. 589. Causas medidas: bônus de título com IDF² (27,2 para UMA palavra
  rara num título de ~10 termos); a própria referência normativa
  ("000", "2021", "aneel") pontuada como conteúdo; "à luz da" pontuada como
  assunto; e vocabulário de setor vencendo o conceito jurídico.
  - Título por **cobertura** (quanto do título a questão explica), no lugar
    de IDF²; expressões de enquadramento ("à luz da", "nos termos da") fora
    do conteúdo; **referência normativa explícita** (`Resolução Normativa
    ANEEL nº 1.000/2021`, `REN 1000`, `CDC`, `Lei nº 8.078/1990`...)
    reconhecida por tabela explícita e revisável: identificadores numéricos
    saem do texto de conteúdo e o diploma citado recebe um impulso
    multiplicativo **apenas sobre pontuação de conteúdo já existente** (uma
    questão que só cita o diploma não recupera nada). Termos que ativam um
    conceito jurídico ganham peso próprio (`PESO_TERMO_GATILHO`); o conceito
    de responsabilidade civil e dano foi reintroduzido com evidência (teste
    do 6.5-B3). Parâmetros calibrados sobre 31 checagens (fixture exata,
    paráfrases e contraexemplos reais de CPC) num platô, não numa ponta.
  - **`dispositivos_relevantes`** por fonte: parser determinístico de
    artigos (`Art. N` no início de linha, com `-A`, milhar e cabeçalhos
    estruturais aparados por posição), validado por contiguidade contra
    `art_inicio`/`art_fim` do chunk. Devolve até
    `MAX_DISPOSITIVOS_POR_FONTE` (3) artigos, escolhidos pela mesma
    intenção da questão, em ordem do diploma, com `score`, `truncado` e
    `questoes_relacionadas` (por que foi escolhido). Texto é sempre
    **prefixo literal** do corpus, verificado nos 3.926 artigos parseáveis.
    Chunks com estrutura não confiável (typo `At. 245.`, lacuna de
    numeração, artigos só com letra) caem em `modo_extrato: "trecho"` com
    `motivo_modo_trecho`; nada é corrigido ou reconstruído. `texto`,
    `artigo_preciso` e `truncado` continuam descrevendo o trecho inicial.
  - `validation_status` e `vigencia` inalterados: precisão do texto não
    eleva validação jurídica. Novo campo `score_componentes` (corpo, título,
    frase, diploma_explicito) para auditoria.
  - Pacote da fixture exata: 27,2 KB -> 50,9 KB. Dependência nova:
    **nenhuma**; `VERSION` permanece `0.13.0`. **Não implantado em
    produção neste gate.**
- **`docx_numeracao_engine`: `mc:Fallback` deixa de ser conteúdo visível**
  (Gate 6.6-A, auditoria obrigatória). O motor de numeração somava o texto
  dos ramos `mc:Choice` (moderno, exibido pelo Word) e `mc:Fallback` (VML
  legado, oculto) — mesma classe de defeito já corrigida em
  `docx_context_engine` no Gate 6.5-B3. Medido no Modelo Oficial real: **24
  dos 342 parágrafos** saíam com texto duplicado ("PRELIMINARESPRELIMINARES",
  "CONTESTAÇÃO COM RECONVENÇÃOCONTESTAÇÃO COM RECONVENÇÃO"…), e os 9 badges
  de nível 1 existem em dobro (9 em `mc:Choice`, 9 em `mc:Fallback`). A
  numeração só estava correta por um workaround que colapsava badges
  duplicados *adjacentes* pelo id — dependência estrutural implícita, que
  também escondia uma duplicata visível real.
  - Correção na causa: extração visível-only (`_ts_visiveis`), parágrafos
    do ramo Fallback ignorados, workaround removido; duplicata visível
    agora aborta (`numeracao_ordem_badges_invalida`). Helper reimplementado
    localmente (importar de `docx_context_engine` criaria ciclo).
  - Equivalência: saída renumerada **byte-idêntica em 41/41 cenários** de
    composição de blocos sobre o Modelo Oficial real, antes e depois.
  - Testes: sintéticos (Choice/Fallback não adjacentes, duplicata visível,
    resíduo só no Fallback) e `docx_real` (nenhum parágrafo duplicado,
    9 badges únicos e visíveis, propriedade metamórfica: renumerar o
    documento completo == renumerar sem o ramo Fallback).
  - Sem dependência nova; `VERSION` permanece `0.13.0`. Não implantado.
- **Fidelidade INDEPENDENTE do renderer, round-trip e modo produção-final**
  (Gate 6.6-A, continuação — decisões de bloco e valores de aceite
  fornecidos pelo usuário). O Template Lock existente
  (`docx_template_engine.verificar_template_lock`) recomputa o "esperado"
  chamando a MESMA cadeia de mutação do renderer e compara byte a byte —
  correto, mas não prova nada que um bug NA PRÓPRIA cadeia não repita
  identicamente dos dois lados. Dois módulos novos, nenhum deles chama
  `compor_xml`/`compor_zonas_xml`/`renumerar_titulos`/`substituir_
  placeholders`:
  - `scripts/docx_fidelidade_independente.py` — deriva do TEMPLATE (texto
    fixo + tokens ainda não substituídos) um padrão esperado por conta
    própria (regex construída por substring) e casa contra o DOCX gerado
    real; prova que nenhum wrapper `<w:sdt>` de bloco sobrevive à
    composição.
  - `scripts/docx_round_trip.py` — extrai do DOCX gerado real (nunca de
    `dados` cacheado) o valor efetivamente presente em cada placeholder,
    reconstruindo `**negrito**` a partir de `<w:b/>`, e compara com o
    valor original aceito.
  - **Dois defeitos reais encontrados e corrigidos pela auditoria
    independente** (nenhum dos dois era visível ao Template Lock
    self-referential, que recomputava o mesmo resultado incorreto dos
    dois lados):
    1. `docx_template_engine._substituir_um_no`: a divisão de um valor
       multiline usava `valor_bruto.split("\n")` cru, sem descartar linha
       em branco — diferente do critério que TODOS os validadores de
       densidade/380 caracteres já aplicam sobre o mesmo valor
       (`validate_paragrafos.paragrafos`). Um valor com `"\n\n"` entre
       parágrafos lógicos (uso comum, já validado como correto pelos
       validadores) produzia um `<w:p>` extra VAZIO no meio do documento.
       Corrigido: mesma regra de descarte de linha em branco, lista nunca
       fica vazia.
    2. Os dois módulos novos precisaram do MESMO tratamento de
       `mc:Fallback`/formas ancoradas já corrigido em
       `docx_numeracao_engine`/`docx_context_engine` — e, além disso, de
       um cuidado adicional descoberto aqui: um `<w:p>` "invólucro" que
       hospeda uma forma/textbox ancorada (ex.: o campo de identificação
       "PROCESSO Nº `{{NUMERO_PROCESSO}}`" do cabeçalho) não pode herdar,
       via `.iter()`, o texto do `<w:p>` aninhado dentro da forma — cada
       `<w:t>` só conta para o `<w:p>` mais próximo que realmente o
       contém.
  - `scripts/validate_placeholder_semantics.py`: modo PRODUÇÃO-FINAL
    (`validar_modo_producao_final`), formalizando a distinção entre
    artefato de ACEITE (marcadores `[PENDENTE:`/`SINTÉTICO DE ACEITE`
    explicitamente autorizados para teste) e peça pronta para protocolo
    (rejeita as duas sentinelas; exige os 11 placeholders sempre visíveis
    e os 8 placeholders block-local quando o bloco dono está INCLUIR —
    classificação obtida por auditoria direta do Modelo Oficial real via
    `docx_context_engine.extrair_contexto`, nunca suposta). Nunca chamado
    implicitamente pelo pipeline de geração existente — portão adicional
    e explícito.
  - Prova end-to-end (`docx_real`, contrato aceito de 19 placeholders,
    múltiplos blocos incluídos): fidelidade e round-trip com **zero**
    divergências contra o Modelo Oficial real, incluindo um teste
    negativo que corrompe texto institucional pós-render e confirma
    detecção. Regressão completa: 1091 passam (1 falha preexistente e
    não relacionada, `skills/docx` local).
  - **Achado, não corrigido — limitação documentada**: o run que carrega
    `{{IRREGULARIDADE_ENCONTRADA}}` no Modelo Oficial já nasce em negrito
    no próprio template (independente de qualquer `**marcação**` no
    valor); o round-trip de negrito PARCIAL dentro desse campo específico
    não é distinguível — consistente com o contrato (CLAUDE.md §14: nome
    do tipo inteiramente em negrito), sem ocorrência real nos 19
    placeholders para os quais isso importe.
  - **O DOCX de aceite do Gate 6.6-A não foi gerado nesta continuação**:
    a validação determinística pré-render (obrigatória antes de tocar o
    DOCX) reprova dois dos valores exatos fornecidos —
    `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` excede
    `LIMITES_DENSIDADE_BLOCO` (6 parágrafos/1373 caracteres; máximo 5/700)
    e `JUIZO` não começa com o prefixo institucional `"AO JUÍZO DA"`
    (`"AO JUÍZO DO JUIZADO ESPECIAL CÍVEL..."` não bate). Reportado à
    parte; nenhum dos dois validadores foi enfraquecido para fazer passar.
  - Sem dependência nova. `VERSION` permanece `0.13.0`. Não implantado em
    produção nesta continuação.
- **Gate 6.6-A fechado: artefato de aceite sintético gerado e aprovado**
  (continuação final — valores corrigidos de `JUIZO` e
  `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` fornecidos pelo usuário).
  Renderizado com as 9 decisões de bloco previamente autorizadas
  (`DEVER_LEGAL_FISCALIZACAO`/`CALCULOS_RECUPERACAO_CONSUMO`/
  `DESCABIMENTO_DANO_MORAL` INCLUIR; as demais, e todos os `state_linked`,
  EXCLUIR) e os 19 placeholders de aceite. `template_lock: OK`,
  fidelidade independente e round-trip **zero divergências** contra o
  Modelo Oficial real.
  - **Um defeito real a mais, encontrado só neste render completo**: os
    dois módulos independentes (`docx_fidelidade_independente.py`,
    `docx_round_trip.py`) ainda não sabiam reconhecer um bloco
    `decision_mode="linked"` (ex. `INLINE_COM_RECONVENCAO`, par MC_PAIR)
    — um `<w:sdt>` que embrulha só ALGUMAS runs no MEIO de um parágrafo
    de texto fixo, nunca o parágrafo inteiro, então a exclusão por
    ancestral de parágrafo (já usada para `BLOCO:`/`ZONA:`) nunca o
    alcança. Corrigido: o MESMO conjunto de tags já resolvidas como
    EXCLUIR (`fora`) agora filtra também a nível de RUN, reaproveitando o
    estado já resolvido pelo catálogo — nenhuma regra de resolução do
    "linked" duplicada.
  - **Normalização documentada #4** (round-trip): o run que carrega
    `{{IRREGULARIDADE_ENCONTRADA}}` no Modelo Oficial já nasce em negrito
    (achado do gate anterior) — `PLACEHOLDERS_COM_CARREGADOR_JA_NEGRITO`
    ignora marcadores `**` só para esse placeholder verificado, nunca uma
    regra geral (um negrito inesperado em qualquer outro campo continua
    reprovando; teste de regressão prova as duas coisas).
  - Produção-final (`validar_modo_producao_final`) confirmado rejeitando
    o próprio artefato de aceite (5 sentinelas: `AUTOR`,
    `TEMPESTIVIDADE_CASO`, `FOTOS_DA_IRREGULARIADE`, `NOME_TITULAR_DA_UC`,
    `TELAS_DA_TITULARIDADE`) — exatamente o comportamento exigido.
  - Artefato: `GATE-6.6-A-SYNTHETIC-ACCEPTANCE-ARTIFACT.docx`, gerado só
    no scratchpad efêmero da sessão — nunca commitado, nunca publicado.
  - Suíte completa: 1093 passam (1 falha preexistente e não relacionada,
    `skills/docx` local). Sem dependência nova. `VERSION` permanece
    `0.13.0`. Não implantado em produção.
- **Arquitetura do finalizador MCP remoto genérico** (Gate 6.6-B,
  auditoria — nenhuma tool pública, nenhum deploy). `docs/adr/ADR-0018-
  finalizador-mcp-remoto-e-entrega-de-artefato.md`: identificador de
  capacidade `<familia>.<modelo>` (registro server-side, nunca exposto
  por completo ao cliente), `ede_finalizar_peca` genérico em vez de uma
  tool por modelo institucional, nunca aceitar template/bucket/path do
  cliente (o cliente escolhe uma CAPACIDADE, nunca um arquivo), modo
  público sempre produção-final, entrega v1 como blob inline
  (`EmbeddedResource`/`BlobResourceContents`, `annotations.audience:
  ["user"]`) com v2 condicional (dois passos + `ResourceLink`) reservada
  para quando o documento crescer, escopo `ede:legal` reaproveitado
  (nunca um escopo por capacidade). Protótipo isolado mede overhead real
  de serialização do SDK `mcp==2.2.0` (~1,33x base64). `VERSION`
  permanece `0.13.0`; bump para `0.14.0` fica condicionado à aprovação
  explícita de implementação (concedida no Gate 6.6-C, abaixo).
- **`ede_finalizar_peca` — finalizador MCP remoto implementado** (Gate
  6.6-C, ADR-0018, candidato/homologação — sem ativação em produção).
  `scripts/capability_registry.py` (registro determinístico; hoje só
  `contestacao.irregularidade_consumo` está `READY`, INV-GATE-
  CONTESTACAO) e `scripts/finalizar_peca.py` (pipeline Core: validação
  estrutural -> composição de blocos/zonas -> modo PRODUÇÃO-FINAL
  (`validar_modo_producao_final`, sempre — nenhum parâmetro relaxa isso)
  -> aquisição/readiness do Modelo Oficial -> render -> fidelidade
  independente -> round-trip -> SHA-256/tamanho), reaproveitando
  integralmente o pipeline endurecido do Gate 6.6-A, nenhuma etapa pulada
  por ser agora um caminho MCP.
  - Vocabulário de erro FECHADO (`CAPABILITY_NOT_FOUND/_NOT_READY`,
    `INPUT_VALIDATION_FAILED`, `OFFICIAL_MODEL_NOT_READY`, `MISSING_
    REQUIRED_FIELD`, `MISSING_BLOCK_DECISION`, `SYNTHETIC_SENTINEL_
    REJECTED`, `TEMPLATE_LOCK_FAILED`, `ROUND_TRIP_FAILED`, `RENDER_
    FAILED`, `ARTIFACT_TOO_LARGE`, `ARTIFACT_DELIVERY_FAILED`) e estágio
    seguro por código — nunca stack trace, path privado ou identificador
    de armazenamento exposto ao cliente. Classificação de `stage` interno
    do motor de composição espelha DELIBERADAMENTE a já usada em
    `gerar_contestacao.py::_etapa_template` — nunca uma segunda taxonomia
    paralela.
  - `mcp_server/server.py`: `EdeFinalizarPecaEntrada` sem nenhum campo de
    template/bucket/path/hash/modo (ausência ESTRUTURAL, Decisão 3/4 da
    ADR-0018); resposta em dois content blocks MCP — `TextContent`
    (metadado JSON) sempre, `EmbeddedResource` (DOCX, blob base64,
    `annotations.audience: ["user"]`) só em sucesso. Escopo `ede:legal`
    (`mcp_server/scope_policy.py`), telemetria somente-metadado nova em
    `mcp_server/auth_logging.py` (`capability_id`, `resultado_
    finalizacao`, `estagio_finalizacao`, `codigo_erro_finalizacao`,
    `documento_tamanho_bytes` — vocabulário fechado espelhado do Core,
    nunca importado, com teste dedicado contra deriva).
  - Teto de entrega inline: **8 MiB exatos** (`8 * 1024 * 1024`, nunca
    8.000.000 decimal) — acima disso, `ARTIFACT_TOO_LARGE` sem nenhum
    byte do conteúdo codificado.
  - `mcp_server/Dockerfile`/`.dockerignore`: seis módulos Core liberados
    nominalmente (`capability_registry.py`, `finalizar_peca.py`,
    `validate_paragrafos.py`, `validate_placeholder_semantics.py`,
    `docx_fidelidade_independente.py`, `docx_round_trip.py`) — mesma
    disciplina allowlist fail-closed; `gerar_contestacao.py`/
    `datajud_client.py` continuam fora.
  - Testes novos: `tests/test_capability_registry.py`,
    `tests/test_finalizar_peca.py` (unidade + `docx_real` ponta a ponta
    contra o Modelo Oficial real, incluindo o caminho de sucesso completo
    e recusas de sentinela/campo obrigatório/decisão ausente/travessão/
    tamanho — Modelo Oficial configurado por `fixture` isolada via
    `monkeypatch`, nunca por variável de ambiente vazada entre testes),
    `tests/test_docker_context.py::test_modulos_core_do_gate_6_6_c_
    liberados`, `tests/test_marketplace.py::test_version_sincronizada_
    com_o_badge_do_readme` (achado: o badge do README nunca tinha trava
    própria), mais extensão de `tests/test_mcp_oauth.py` (escopo,
    dispatch, sucesso ponta a ponta pelo transporte MCP protegido).
    Suíte completa (`docx_real` incluído, um único run): **1144 passam**,
    1 falha preexistente e não relacionada (`skills/docx` local,
    INV-GATE-CONTESTACAO — diretório fora do controle de versão, alheio a
    este gate).
  - `VERSION`: `0.13.0` -> `0.14.0` (SemVer minor — nova ferramenta MCP,
    retrocompatível; aprovação explícita do usuário). **Candidato/
    homologação apenas** — sem ativação em produção, sem deploy, sem
    troca de tráfego do Cloud Run, sem rollout para advogados, sem tag e
    sem GitHub Release nesta etapa.

### Evidência viva — Gate 6.6-D, interoperabilidade do finalizador (2026-09-22) — ENCERRADO como PARTIAL PASS
- **Ativação controlada em produção (Gate 6.6-D).** Promoção
  explicitamente autorizada, exigida pelo teste de interoperabilidade
  viva: revisão `ede-mcp-00020-gum` (criada em 2026-09-22 15:01:49 UTC,
  tag `candidato-6-6-d`), VERSION `0.14.0`, digest imutável
  `sha256:63521b143622a3d1f134ff2bc4a008f136046e92a5edbedc3d116fd86e45c427`,
  100% do tráfego. O alvo de rollback anterior, `ede-mcp-00018-loc`
  (tag `candidato-6-5-c4`), continua disponível com 0%. Revisão, digest,
  tráfego e alvo de rollback conferidos por leitura
  (`gcloud run services/revisions describe`). **Não é rollout para
  advogados, release nem tag.** Corrige a menção "sem ativação em
  produção" da entrada do Gate 6.6-C acima, que valia só até este gate.
- **Chamada 1 (ChatGPT): recusada em `input_validation`; nenhum DOCX
  gerado.** Evidência válida de fail-closed, registrada separadamente da
  chamada 2. Primeira chamada
  real do cliente ChatGPT ao finalizador de produção (`ede_health` no
  momento do registro: `0.14.0`, `service_status`/`contestacao_status`/
  `rag`/`modelo_oficial` todos `READY`). Resposta: `status=REFUSED`,
  `stage=input_validation`; o código é `INPUT_VALIDATION_FAILED`, único
  que `_validar_rascunho_estruturado` emite (`scripts/finalizar_peca.py`).
  Recusa devolve só o `TextContent` de metadado; o `EmbeddedResource` do
  DOCX só é montado com `status=OK` (`mcp_server/server.py`), então não
  saiu artefato nenhum. Motivo: densidade de bloco
  (`validate_paragrafos.validar_densidade_blocos`):

  | Placeholder | Rascunho do cliente | Observado pelo servidor | Máximo |
  |---|---|---|---|
  | `SINOPSE_FATOS` | 2 parágrafos | 6 | 3 |
  | `REALIDADE_FATICA` | 2 parágrafos | 6 | 3 |
  | `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` | 4 parágrafos | 10 | 5 |

  A coluna "rascunho do cliente" é a estrutura da fixture do lado do
  cliente, segundo o relato do usuário; o servidor só conhece o valor
  recebido. A checagem de 380 caracteres roda antes da densidade e
  passou, o que bate com quebras inseridas dentro dos parágrafos, não
  com parágrafos longos demais.
- **Causa provável: transporte/cópia do lado do cliente inseriu quebras
  de linha nos valores string.** O contrato define parágrafo como linha
  não vazia separada por `\n` (`validate_paragrafos.paragrafos`), então o
  servidor não tem como distinguir uma quebra do autor de uma quebra do
  transporte, e não deve tentar. Reprodução local: quebrar dois
  parágrafos em 80 colunas produz exatamente 6 linhas e a mesma mensagem
  de recusa. Não foi possível confirmar o mecanismo exato no cliente.
- **Nenhum validador foi alterado.** A recusa é o comportamento correto
  de produção-final. Juntar linhas no servidor seria correção
  silenciosa (CLAUDE.md §17). A nova tentativa de interoperabilidade usa
  valores de parágrafo único nesses três campos, cada um abaixo de 380
  caracteres sem espaços. Risco aberto em `docs/PENDENCIAS.md` PEND-011:
  um sucesso com parágrafo único não prova que o transporte está limpo.
- **Chamada 2 (ChatGPT, nova tentativa com parágrafo único): `status=OK`.**
  Metadado do servidor: `document_size_bytes=1761975`,
  `document_sha256=edd2a513178f9eb7190cb105eb147ba8c9374d913d27b548fa0abe62eca872ab`.
  O ChatGPT não despejou o base64 na conversa. **PEND-011 continua
  ABERTA**: esta chamada não exercitou nenhum campo com mais de um
  parágrafo, então não prova que o transporte preserva multilinha.
  **Correção pela auditoria de log (abaixo):** o telemetria de produção
  mostra que o cliente `openai-mcp/1.0.0 (Codex)` não fez uma única
  chamada de sucesso, e sim **sete**, entre 15:45:39 e 15:56:09 UTC —
  todas `resultado_finalizacao=OK`, todas com
  `documento_tamanho_bytes=1761975`, todas depois da recusa às 15:35:52.
  Consistente com o cliente tentando repetidamente contornar a falha de
  entrega inline (cada tentativa refazendo a chamada de ferramenta). A
  narrativa "chamada 2" acima descreve o resultado obtido pelo usuário,
  não o número real de invocações no servidor; ambas as evidências
  concordam no que importa (`status=OK`, mesmo tamanho, mesmo SHA
  relatado) e nenhuma foi descartada.
- **Entrega inline do artefato no ChatGPT: FAIL.** A URI nativa do
  `EmbeddedResource` não foi utilizável pela UI; o próprio ChatGPT
  informou que "o link attachment:// não estava acessível na interface"
  e, como contorno do lado da aplicação, persistiu o arquivo por outro
  canal de arquivos. Isso não é entrega nativa: o critério do ChatGPT no
  Gate 6.6-D exige DOCX utilizável/baixável direto do resultado MCP, sem
  URL pública, sem reconstrução manual e sem regeneração secundária.
  Documentação consultada em 2026-09-22 (OpenAI Apps SDK Reference e
  "MCP server" em developers.openai.com): nenhum mecanismo nativo
  documentado para um resultado de ferramenta entregar arquivo baixável;
  as APIs de arquivo (`uploadFile`, `selectFiles`, `getFileDownloadUrl`)
  são de widget, e `openai/fileParams` é só para entrada de ferramenta.
  Sem evidência em contrário, o FAIL fica registrado. Aberto em
  `docs/PENDENCIAS.md` PEND-012.
- **Distinção obrigatória entre (A) e (B).** (A) entrega nativa via
  `EmbeddedResource`: FAIL, acima. (B) arquivo persistido pelo caminho
  secundário do ChatGPT: o arquivo baixado (`EDE-Contestacao-
  Irregularidade.docx`, pasta de downloads local, 13:25 -03:00) tem
  SHA-256 `edd2a513…a872ab` e 1761975 bytes, **idênticos byte a byte** ao
  metadado do servidor (verificado localmente, sem abrir o conteúdo). A
  inspeção visual do usuário encontrou o timbrado EDE íntegro: logo e
  cabeçalho na página 1, rodapé institucional, o mesmo padrão nas páginas
  seguintes e elementos gráficos/imagens institucionais preservados.
  **Não há defeito de renderer a registrar a partir deste arquivo.** A
  identidade de bytes de (B) não converte (A) em sucesso.
- **Item "SHA do arquivo baixado do ChatGPT x metadado do servidor":
  FECHADO.** Mesmo SHA-256
  (`edd2a513178f9eb7190cb105eb147ba8c9374d913d27b548fa0abe62eca872ab`) e
  mesmo tamanho (1761975 bytes). Conclusões: o caminho de persistência
  secundária do ChatGPT preservou exatamente os bytes do servidor; não
  houve corrupção pelo renderer; não houve perda de timbrado. A entrega
  nativa via `EmbeddedResource`/`attachment://` continua **FAIL** e a
  PEND-012 continua ABERTA; a Decisão 5 da ADR-0018 não foi alterada.
- **Nenhuma mudança de código ou infraestrutura por causa deste
  resultado.** Renderer, Template Lock e validação produção-final
  intocados; sem troca para base64 em `TextContent`; sem rollback (a
  política de rollback aprovada não o aciona por limitação da UI do
  ChatGPT com o servidor correto); sem redesenho automático, sem novo
  deploy, sem tag, sem release, sem ampliação de acesso de advogados.
- **Chamada do Claude, mesmo payload da chamada 2 do ChatGPT que deu
  certo: `status=OK`.** Metadado do servidor: `document_size_bytes=
  1761975`, `document_sha256=
  edd2a513178f9eb7190cb105eb147ba8c9374d913d27b548fa0abe62eca872ab` —
  **idêntico** ao devolvido nas chamadas do ChatGPT, com o mesmo
  payload de entrada. **Uma segunda chamada idêntica do Claude para
  determinismo não foi feita** — desnecessária: o determinismo do
  motor já está estabelecido pelas sete chamadas OK do ChatGPT (mesmo
  payload, mesmo tamanho a cada vez, evidência de log abaixo) mais esta
  chamada do Claude com o mesmo payload e o mesmo SHA; repetir só a
  entrega nativa do Claude, que o próprio cliente já recusou, não
  agregaria informação sobre determinismo — só repetiria um mecanismo de
  transporte que este cliente não suporta.
- **Entrega nativa do artefato no Claude: FAIL — recusa explícita do
  cliente, tipo de mídia identificado.** O claude.ai respondeu:
  "Resources of type
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  are not currently supported." Nenhum byte do DOCX chegou a ficar
  disponível para o usuário nesta chamada — diferença importante frente
  ao ChatGPT, que ao menos persistiu o arquivo por um canal próprio.
- **Confirmado no nível de transporte: os bytes SAÍRAM do servidor.** O
  log de requisições do Cloud Run (metadado apenas — método, tamanhos,
  status, latência; nunca corpo) mostra, para a chamada do Claude, uma
  resposta de **2.350.126 bytes**, quase exatamente a inflação base64 de
  um arquivo de 1.761.975 bytes (4/3 ≈ 2.349.300, mais a moldura JSON do
  `EmbeddedResource`/`TextContent`). Isto isola a falha: o
  `EmbeddedResource` com o blob completo foi transmitido pelo servidor;
  a rejeição é uma decisão do cliente Claude sobre o tipo de mídia, não
  uma falha de entrega do servidor nem do transporte HTTPS.
- **Resultado final de interoperabilidade viva, com as três camadas
  distintas exigidas:**
  1. **Correção do servidor** — `SERVER-SIDE FINALIZER = PASS`,
     `PRODUCTION-FINAL VALIDATION = PASS`, `OFFICIAL MODEL RENDER =
     PASS`. A recusa fail-closed da chamada 1 do ChatGPT e o sucesso
     determinístico de todas as chamadas seguintes (ambos os clientes)
     são o comportamento correto e esperado do pipeline endurecido do
     Gate 6.6-A/C.
  2. **Determinismo do documento** — `SERVER-SIDE DOCUMENT IDENTITY
     ACROSS CHATGPT AND CLAUDE = PASS`. As duas chamadas vivas com o
     mesmo payload de parágrafo único devolveram o mesmo SHA-256
     (`edd2a513…a872ab`) e o mesmo tamanho (1761975 bytes); a
     telemetria de produção mostra oito invocações OK no total (sete do
     ChatGPT, uma do Claude), todas com `documento_tamanho_bytes=
     1761975`.
  3. **Interoperabilidade de transporte do cliente** —
     `CHATGPT NATIVE EmbeddedResource DELIVERY = FAIL` (contorno do host
     preservou os bytes, mas não é entrega nativa) e
     `CLAUDE NATIVE EmbeddedResource DELIVERY = FAIL` (recusa explícita
     de tipo de mídia; nenhum contorno, nenhum byte chegou ao usuário).
     **Isto não é um defeito do renderer** — é uma lacuna do mecanismo de
     entrega v1 (Decisão 5 da ADR-0018, `EmbeddedResource`/
     `BlobResourceContents`) frente ao suporte real dos dois hosts MCP
     que importam para o produto.
- **Gate 6.6-D: ENCERRADO como `6.6-D FINALIZER LIVE INTEROPERABILITY —
  PARTIAL PASS`.** Nenhuma mudança de renderer, Template Lock ou
  validação produção-final; nenhuma troca para base64 em `TextContent`;
  nenhum workaround implementado neste gate; nenhum rollback de produção
  (a UI de nenhum dos dois clientes falhar em usar o artefato nativo,
  com o servidor correto, não aciona a política de rollback já
  aprovada); nenhuma tag Git; nenhum GitHub Release; nenhuma ampliação de
  acesso de advogados. Esta evidência é suficiente para concluir que a
  Decisão 5 da ADR-0018 (v1, `EmbeddedResource`/`BlobResourceContents`
  como mecanismo de entrega entre hosts) **não satisfaz o requisito real
  do produto** — nenhum cliente real testado consegue usá-la
  nativamente. A Decisão 5 não é revista nesta entrada: a avaliação de
  redesenho é preparada separadamente (ver ADR-0019, abaixo) e sua
  implementação aguarda autorização explícita, em gate próprio.

#### Auditoria final de logs/privacidade — chamada do Claude (Gate 6.6-D, item 6)
- **Método:** só leitura (`gcloud logging read`), mesma disciplina das
  auditorias anteriores deste gate. Nenhuma mutação.
- **Contagem completa de invocações no período, por telemetria da
  aplicação (`evento=finalizacao_peca`, allowlist fechada de
  `mcp_server/auth_logging.py`):** nove eventos entre 15:33 e 18:55 UTC
  de 2026-09-22 — uma `REFUSED` (`INPUT_VALIDATION_FAILED`, 15:35:52,
  cliente `openai-mcp/1.0.0 (Codex)`), sete `OK` do mesmo cliente entre
  15:45:39 e 15:56:09, e uma `OK` do cliente `Claude-User` às 18:55:14.
  As nove batem exatamente com as nove concessões de escopo
  `ede_finalizar_peca`/`ede:legal` registradas em `evento=
  autorizacao_ferramenta` no mesmo período (mais duas concessões de
  `ede_health`/`ede:health`, chamadas de diagnóstico feitas por esta
  sessão de auditoria, sem relação com o teste de interoperabilidade).
  Nenhum evento de `ede_preparar_contestacao` no período — nenhuma
  extração/preparação com dado de caso ocorreu durante o teste.
- **Nenhum conteúdo em log algum.** Os campos emitidos pela telemetria
  de aplicação continuam restritos à allowlist (`capability_id`,
  `resultado_finalizacao`, `estagio_finalizacao`,
  `codigo_erro_finalizacao`, `documento_tamanho_bytes`,
  `id_correlacao`) — nunca SHA-256, nunca base64, nunca texto de
  placeholder. O log de requisições do Cloud Run (infraestrutura, não
  aplicação) tem um schema fechado próprio (`latency`, `protocol`,
  `remoteIp`, `requestMethod`, `requestSize`, `requestUrl`,
  `responseSize`, `serverIp`, `status`, `userAgent`) que **nunca inclui
  corpo de requisição ou resposta** — confirmado por leitura direta dos
  registros da chamada do Claude: só os tamanhos aparecem (os mesmos
  2.350.126 bytes citados acima), nunca os bytes em si.
  `EDE_MODELO_OFICIAL_GCS_*`/segredos de OAuth nunca aparecem em nenhum
  dos dois logs, em nenhuma das nove chamadas.
- **Nenhuma URL assinada existe hoje para vazar.** O mecanismo de
  entrega v1 (`EmbeddedResource` inline) não envolve URL assinada nem
  armazenamento intermediário — o requisito "nenhuma URL assinada em log
  de longo prazo" não se aplica ao mecanismo atual; passa a valer a
  partir do redesenho avaliado em ADR-0019.
- **Conclusão:** auditoria final de log/privacidade para as chamadas do
  Claude **CONCLUÍDA**, sem achado. Fecha o item 6 do Gate 6.6-D
  integralmente (a parte de revisões antigas já havia sido aceita
  separadamente).

#### Auditoria somente-leitura das revisões antigas com tag (Gate 6.6-D, item 6) — CONCLUÍDA, aceita pelo usuário
- **Escopo e método.** Nenhuma mutação: só `gcloud run
  services/revisions describe`, `gcloud artifacts docker images list`,
  `gcloud logging read` e sondagens HTTP **sem token**, com User-Agent
  próprio (`ede-audit-gate-6.6-D-*`). Nenhuma tag removida, nenhum
  tráfego alterado, nenhum redeploy, nada tocado em IAM/OAuth/Descope/
  código. Nenhuma chamada a `ede_preparar_contestacao`, a
  `ede_finalizar_peca` ou com dado de caso.
- **Mapeamento (tag → revisão → digest → VERSION → tráfego).** VERSION vem
  do commit correspondente (tag da imagem no Artifact Registry é
  `<commit>-candidato`), sem precisar de chamada autenticada:

  | Tag | Revisão | Digest (prefixo) | Commit | VERSION | Tráfego | Classificação |
  |---|---|---|---|---|---|---|
  | `candidato` | `ede-mcp-0e74400-64c` | `sha256:1a0fa276ffa0` | `0e74400` | 0.12.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-5-b` | `ede-mcp-00010-gut` | `sha256:23294da8d211` | `ca9c0a74` | 0.13.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-5-b2` | `ede-mcp-00012-log` | `sha256:253f9889d1ab` | `895e995b` | 0.13.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-5-c` | `ede-mcp-00014-dox` | `sha256:5dfd43bace9a` | `0349c9ae` | 0.13.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-5-c2` | `ede-mcp-00016-yej` | `sha256:4096249730e1` | `2e013598` | 0.13.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-5-c4` | `ede-mcp-00018-loc` | `sha256:34d9b83381e3` | `981d9baa` | 0.13.0 | 0% | AUTH-BLOCKED |
  | `candidato-6-6-d` | `ede-mcp-00020-gum` | `sha256:63521b143622` | `fe2c92a2` | 0.14.0 | 100% | (revisão corrente — ver adiante) |

  Cada tag tem duas URLs públicas, a forma `…---ede-mcp-tzat7bdc6q-rj.a.run.app`
  e a determinística `…---ede-mcp-269134711029.southamerica-east1.run.app`;
  ambas verificadas. Todas as revisões estão `Ready`/`Active`, com
  `EDE_MCP_AUTH_ENABLED=true`, mesmo Resource canônico, mesmo
  `EDE_MCP_CANONICAL_HOST` e a mesma service account de runtime.
- **(A) Superfície sem autenticação, em todas as tags.** `GET /mcp` e
  `POST /mcp` (`tools/list`, sem token) → **401** com
  `WWW-Authenticate` apontando o PRM canônico; `GET /` → **404**;
  `GET /.well-known/oauth-protected-resource/mcp` → **200** com o PRM
  público (Resource canônico, issuer Descope, escopos anunciados —
  `ede:health` nas duas revisões mais antigas, `ede:health`+`ede:legal`
  nas demais). Nenhuma execução de ferramenta, nenhum dado jurídico.
- **(B) Nada sensível no corpo ou nos cabeçalhos.** Os únicos corpos são
  `{"error": "invalid_token", …}`, `Not Found` e o PRM. Varredura por
  stack trace, variável de ambiente, identificador de bucket/objeto do
  Modelo Oficial, caminho interno, segredo e conteúdo jurídico: nenhuma
  ocorrência.
- **(C) Log: zero dispatch de ferramenta.** Na janela das sondagens, as
  sete revisões registraram **apenas** `requisicao_http` e `startup` —
  **zero `autorizacao_ferramenta` e zero `finalizacao_peca`**, ou seja,
  nenhuma execução de ferramenta jurídica e nenhuma aquisição/renderização
  do Modelo Oficial (que só ocorrem dentro de uma chamada de ferramenta).
  Os campos emitidos continuam sendo só metadado da allowlist
  (`caminho`, `metodo_http`, `status_http`, `latencia_ms`,
  `resultado_auth`, `resultado_autz`, `id_correlacao`, `issuer`,
  `audiencias_aceitas`, `migracao_audiencia`) — nenhum corpo, token ou
  conteúdo de caso.
- **(D) Host canônico é inalcançável numa revisão com tag.** O Cloud Run
  roteia pelo Host: seis requisições enviadas às URLs de tag **com
  `Host:` do host canônico** foram servidas pela revisão corrente
  (`ede-mcp-00020-gum`), nunca pela revisão da tag (confirmado no log de
  requisições). Como toda revisão antiga roda o mesmo `mcp==2.2.0` e a
  mesma política `allowed_hosts=[canonical_host]` (casamento exato,
  verificado commit a commit), um token válido do titular numa URL de tag
  passaria pela autenticação e seria recusado com **421 Invalid Host**
  pelo transporte, antes de qualquer parsing JSON-RPC ou dispatch. Daí a
  classificação **AUTH-BLOCKED** para as seis tags históricas —
  **nenhuma LEGACY-MCP-REACHABLE**, nenhum achado de segurança.
- **Tag corrente `candidato-6-6-d` → `ede-mcp-00020-gum`, documentada à
  parte.** Comportamento idêntico ao das demais **pela URL de tag** (401
  sem token; Host da tag seria recusado com 421 mesmo autenticado). A
  diferença não é de proteção, e sim de papel: esta revisão é a que
  atende 100% do tráfego pelo host canônico, que é o caminho legítimo e
  o usado pelas chamadas vivas deste gate. Não é exposição histórica.
- **Limites desta auditoria, explicitados.** (1) Nenhuma sondagem
  autenticada foi feita: não há caminho já autorizado para usar a
  credencial OAuth do titular sem expor/copiar o token, então a recusa
  421 está provada por leitura de código e por roteamento, não por
  observação autenticada. (2) Só HTTP/1.1 foi exercitado (o `curl` do
  ambiente não tem HTTP/2), então `:authority` em HTTP/2 não foi testado
  diretamente. (3) Data Access log não está habilitado no projeto
  (`auditConfigs` vazio), então não existe log de leitura do bucket
  privado: a prova de "nenhuma aquisição do Modelo Oficial" é o zero
  dispatch de ferramenta em (C), não um log do GCS.
- **Conclusão aceita pelo usuário.** As seis tags históricas são
  AUTH-BLOCKED; nenhuma é LEGACY-MCP-REACHABLE; zero dispatch de
  ferramenta jurídica observado; zero evento de finalização observado;
  nenhum conteúdo sensível ou segredo de infraestrutura exposto; nenhuma
  condição de parada de segurança foi acionada. As três limitações desta
  auditoria — (1) nenhuma sondagem autenticada de URL com tag, (2)
  `:authority` de HTTP/2 não testado diretamente, (3) evidência de
  "nenhuma leitura do Modelo Oficial" derivada do zero dispatch de
  aplicação, não de log de acesso do GCS (Data Access log desligado no
  projeto) — permanecem registradas acima, não descartadas pela aceitação.
- **Remoção das tags: aprovada em princípio como *pre-pilot hardening*,
  execução ADIADA.** As seis tags históricas não são necessárias para
  rollback — a revisão alvo (`ede-mcp-00018-loc`) continua disponível por
  nome, com ou sem tag. Remover as tags antigas reduziria a superfície
  pública e impediria que código antigo suba por requisição externa a uma
  URL de tag. A execução fica explicitamente para depois de completo o
  restante da evidência de interoperabilidade viva do Gate 6.6-D (itens
  do Claude, acima) — decisão deliberada de não misturar esta mutação de
  infraestrutura com a evidência de interoperabilidade de cliente em
  andamento. Nenhuma tag foi removida nesta entrada.

### Gate 6.6-E — entrega v2 do artefato: objeto GCS efêmero + URL assinada (candidato/homologação, VERSION 0.15.0)
- **Autorização e objetivo.** Autorização explícita do usuário: Gate
  6.6-D fechou como `PARTIAL PASS` — correção do servidor, validação
  produção-final e determinismo do documento comprovados nos dois
  hosts reais; a falha era só a entrega nativa do `EmbeddedResource`
  inline v1 (ADR-0018, Decisão 5), rejeitada por evidência viva. Este
  gate implementa e homologa o v2: `ede_finalizar_peca` -> DOCX
  validado (pipeline inalterado) -> objeto GCS privado efêmero -> URL
  HTTPS assinada (V4) de curta duração -> `TextContent` pequeno com
  metadado + link, nunca base64. **Só implementação/homologação —
  nenhum deploy de produção, nenhuma tag Git, nenhum GitHub Release,
  nenhuma ampliação de acesso de advogados.**
- **Preservado sem alteração:** registro de capacidades, semântica
  produção-final, validação jurídica, Template Lock, renderer,
  fidelidade independente, round-trip, autoridade do Modelo Oficial,
  modelo de escopo OAuth (`ede:legal`, sem escopo novo), telemetria
  somente-metadado (allowlist fechada, dois campos novos conscientes:
  `artefato_id`, `artefato_limpeza_ok` — nunca URL).
- **VERSION:** `0.14.0` -> `0.15.0` (SemVer minor — mudança de contrato
  de saída de `ede_finalizar_peca`, retrocompatível na entrada).
  Sincronizado em `VERSION`, `.claude-plugin/plugin.json`, badge do
  README e `skills/atualizar-ede/SKILL.md` — os quatro literais que a
  suíte de testes (`test_marketplace.py`) trava contra deriva.
- **ADR-0018, Decisão 5: marcada HISTÓRICA, não apagada.** v1
  (`EmbeddedResource` inline) permanece registrada como implementada e
  corretamente testada, e agora REJEITADA como mecanismo de entrega
  entre hosts, com a evidência viva do Gate 6.6-D citada no próprio
  texto. Nova seção "Status histórico" documenta também que o v2
  implementado diverge do desenho original da própria Decisão 5 (que
  previa um `ResourceLink`/resource template do SDK como v2 primário, e
  URL assinada só como opção auditada à parte) — divergência
  por decisão explícita do usuário neste gate, registrada como tal, não
  uma reinterpretação silenciosa.
- **ADR-0019: de "proposta" para "candidato implementado".** Nova seção
  "Implementação (Gate 6.6-E)" com a arquitetura de bucket real, decisão
  final de limpeza, e o item de risco residual da verificação de
  assinatura (abaixo).
- **`scripts/artifact_storage.py` (Core novo).** Mesma disciplina de
  `legal_readiness.py` (Gate 6.4-B) — nenhum SDK de nuvem completo:
  `google-auth` (credencial) + `httpx2` (REST), ambos já dependências
  do projeto; nenhuma dependência nova. Upload multipart (bytes +
  metadado atômico), assinatura V4 construída à mão (conferida ponto a
  ponto contra `docs.cloud.google.com/storage/docs/access-control/
  signing-urls-manually`: escapamento de `canonical_uri` com
  `safe="/~"`, escapamento de query string equivalente a `safe=""`,
  token literal `"auto"` no `credential_scope`, linha em branco entre
  cabeçalhos canônicos e `signed_headers`), exclusão idempotente.
  Nenhuma chave de service account — assinatura via IAM Credentials
  `signBlob` (keyless), identidade de assinatura explícita
  (`EDE_ARTEFATOS_SIGNER_SA`, nunca auto-detectada de atributo de
  credencial). TTL de download (`TTL_DOWNLOAD_SEGUNDOS = 900`) é
  constante do módulo — `entregar_artefato_efemero` não tem parâmetro
  de TTL, e o schema Pydantic de `ede_finalizar_peca` nunca expôs nem
  expõe TTL/bucket/chave de objeto/modo de entrega ao cliente. Object
  key sempre opaco (`artifacts/<uuid4 hex>.docx`) — nunca deriva de
  SHA-256, nome de arquivo do cliente ou qualquer dado de caso; dois
  documentos idênticos em chamadas diferentes recebem objetos
  diferentes (identidade do documento e identidade de entrega
  deliberadamente separadas). Metadado do objeto restrito a
  `artifact_id`/`created_at`/`expires_at`/`sha256` — nunca dado de caso.
- **Integração em `scripts/finalizar_peca.py`.** Chamada logo após o
  SHA-256 do documento já aprovado por Template Lock/fidelidade/
  round-trip — nunca reabre/reconstrói os bytes. Dois códigos de erro
  novos no vocabulário fechado (`ARTIFACT_STORAGE_FAILED`,
  `ARTIFACT_SIGNING_FAILED`), mapeados ao estágio `artifact_delivery`
  já existente. Falha de upload: nenhuma limpeza necessária (upload
  multipart do GCS é atômico, nunca deixa objeto parcial). Falha de
  assinatura APÓS upload: tenta excluir o objeto órfão; o resultado
  (`limpeza_ok`) vai só para telemetria, nunca para o cliente MCP — a
  resposta é `REFUSED` de qualquer jeito, nunca uma URL inutilizável.
  Ponto único de injeção de transporte (`_obter_transporte_artefato`,
  monkeypatchável em teste) — nenhum parâmetro público relaxa ou
  escolhe o mecanismo de entrega.
- **`mcp_server/server.py`: resposta agora SEMPRE um único
  `TextContent`.** `EdeFinalizarPecaResposta` ganha `download_url`/
  `expires_at`; `EmbeddedResource`/`BlobResourceContents`/`Annotations`
  removidos dos imports (não usados mais em lugar nenhum). Nenhum
  base64, nenhum byte do documento, em nenhuma resposta MCP, sucesso ou
  recusa.
- **`mcp_server/auth_logging.py`:** dois códigos de erro novos no
  vocabulário fechado espelhado (testado contra deriva pelo teste já
  existente); dois campos novos na allowlist fechada de telemetria
  (`artefato_id` — opaco, sem barra, ≤64 chars; `artefato_limpeza_ok` —
  booleano) — `download_url`/`expires_at` NUNCA chegam a este módulo:
  `_registrar_finalizacao` não tem parâmetro nenhum para URL.
- **Bucket real de homologação:** `ede-legal-mcp-01-artefatos-efemeros`
  (`southamerica-east1`, `public_access_prevention: enforced`, acesso
  uniforme, sem versionamento). **Achado deste gate:** o padrão do
  projeto GCP retém objeto "excluído" por 7 dias (soft-delete) —
  desligado explicitamente neste bucket
  (`retentionDurationSeconds: 0`), porque guarda documento jurídico
  efêmero, não deveria sobreviver a uma exclusão real. Lifecycle
  `age: 1` (dia) como backstop de limpeza — reportado honestamente como
  granularidade de DIA, nunca chamado de "exclusão em 15 minutos"; a
  janela de 15 minutos é só a validade da URL assinada (Gate 6.6-E §9/
  §34: expiração de acesso e exclusão de armazenamento são garantias
  DIFERENTES, documentadas separadamente em `docs/mcp-producao-
  contrato.md`). Nenhuma IAM de runtime de PRODUÇÃO foi alterada (§41):
  as duas concessões que a implementação precisa (`storage.objectAdmin`
  escopado ao bucket; `iam.serviceAccountTokenCreator` de
  auto-impersonação) estão documentadas, não aplicadas.
- **Verificação real, parcial — risco residual explícito.** Upload
  multipart real contra o bucket funcionou (200); acesso não assinado
  ao objeto foi corretamente negado (401), antes e depois do upload;
  exclusão real do objeto de teste funcionou. **A chamada real a
  `iamcredentials.signBlob` não pôde ser completada nesta sessão:** o
  guard de segurança do próprio harness de execução ("Permission
  Grant") bloqueou toda tentativa de conceder a IAM necessária para
  testar — inclusive a criação de uma service account de homologação
  dedicada só para isso — e essa restrição foi respeitada, nunca
  contornada. Achado real, não suposição: `roles/owner` do operador
  **não inclui** `iam.serviceAccounts.signBlob` (testado ao vivo,
  403). Compensação: o algoritmo de `canonical_request`/`string-to-sign`
  foi conferido campo a campo contra a documentação oficial do Google
  (consultada nesta sessão) e contra a suíte de unidade determinística
  — a estrutura está correta; falta a prova de ponta a ponta com uma
  assinatura RSA real do GCS antes do gate de download ao vivo.
- **Testes.** `tests/test_artifact_storage.py` (19 casos novos, só fake,
  sem rede): caminho feliz, byte-identidade, object key opaco e único
  por chamada mesmo com SHA igual, metadado do objeto restrito aos
  quatro campos seguros, `Content-Disposition` com o nome neutro do
  cliente, TTL sempre a constante do módulo, matriz negativa completa
  (falha de upload nunca tenta assinar; falha de assinatura tenta
  limpar e propaga `artefato_id`/`limpeza_ok`; falha de assinatura E de
  limpeza reporta `limpeza_ok=False`, nunca silencioso; configuração
  ausente é erro tipado distinto de falha operacional), estrutura e
  determinismo do `string_to_sign`, preservação de barra interna do
  nome do objeto no `canonical_uri`, percent-encoding de `/` dentro do
  valor de `X-Goog-Credential` na query string. `tests/test_finalizar_
  peca.py`: fixture `transporte_artefato_fake` (fake em memória,
  reimplementado — não importado de `test_artifact_storage.py`, para
  não acoplar os dois arquivos), teste OK atualizado com asserções de
  `download_url`/`expires_at`/`artefato_id`/bytes armazenados idênticos
  aos renderizados, teste de residual de arquivo temporário atualizado,
  dois testes negativos novos (`ARTIFACT_STORAGE_FAILED` nunca tenta
  assinar; `ARTIFACT_SIGNING_FAILED` tenta limpar e reporta
  `limpeza_ok`), teste de tamanho máximo estendido para provar que
  NENHUM upload é tentado antes da checagem de 8 MiB.
  `tests/test_mcp_oauth.py::test_escopo_legal_finaliza_peca_com_sucesso_real`
  reescrito para o contrato v2: um único content block, `download_url`
  presente, nenhum `blob`/base64 em lugar nenhum da resposta serializada,
  bytes do fake batendo com o SHA-256 relatado ao cliente.
  `mcp_server/Dockerfile`, `.dockerignore` e `.github/workflows/
  homologar-mcp-container.yml` liberam `scripts/artifact_storage.py`
  pela MESMA allowlist tripla já usada pelos módulos do Gate 6.6-C
  (Dockerfile + `.dockerignore` + verificação independente dentro da
  imagem real via CI).
  Suíte completa: **1167 passam** (1103 unidade + 64 `docx_real`), 1
  falha preexistente e não relacionada (`skills/docx` local,
  INV-GATE-CONTESTACAO — mesma falha já registrada em gates anteriores,
  alheia a este).
- **PEND-012 ampliado (Gate 6.6-D) continua ABERTO** — a implementação
  do v2 não fecha PEND-012 sozinha (Gate 6.6-E §52): só uma prova viva
  de download real por Claude e ChatGPT fecha. **PEND-011 intocado**
  (Gate 6.6-E §51 — transporte de texto multilinha não faz parte deste
  gate). **PEND-013 (remoção de tags históricas) continua ADIADA**
  (Gate 6.6-E §50 — nenhuma tag removida nesta rodada). **PEND-014**
  passa de "em avaliação" para "candidato implementado", permanece
  ABERTA até a prova viva completa (assinatura real + download real) e
  autorização explícita de ativação em produção.

### Gate 6.6-E continuação — prova real de assinatura V4 + hard delete + retenção revisada para 24h (VERSION permanece 0.15.0)
- **IAM de homologação temporária, autorizada e usada só para isto.**
  Duas rodadas de prova real, cada uma com uma service account
  descartável (`ede-artefatos-homolog@ede-legal-mcp-01.iam.
  gserviceaccount.com`), criada, usada e **removida ao final de cada
  rodada** (bindings removidos, SA deletada, confirmado por leitura).
  IAM aplicada só à SA de homologação e ao bucket
  `ede-legal-mcp-01-artefatos-efemeros` (`storage.objectAdmin`
  escopado ao bucket) — a service account de runtime de produção
  (`ede-mcp-runtime@...`) nunca foi tocada.
- **Prova real completa de `signBlob`, fechando o risco residual do
  gate original.** Usando a implementação real
  (`artifact_storage.TransporteGcsReal`, não um script de assinatura à
  parte, com credenciais injetadas via token do próprio operador só
  porque este ambiente de desenvolvimento não tem ADC local),
  `finalizar_peca.finalizar_peca()` renderizou o Modelo Oficial real,
  enviou os bytes exatos ao bucket real, assinou uma URL V4 real e
  devolveu `status=OK`. SHA-256 idêntico em três pontas — renderer,
  objeto armazenado e bytes baixados pela URL assinada — confirmado por
  download HTTP comum e não autenticado. `Content-Type` e
  `Content-Disposition` corretos na resposta real do GCS.
- **Acesso não assinado negado (401), antes e depois do upload —
  real.** Enumeração anônima do bucket negada — real (confirmado em
  rodada anterior, reconfirmado nesta).
- **Expiração real.** `assinar_url()` chamada diretamente com TTL curto
  de teste (5s) — caminho interno, nunca exposto no schema Pydantic
  público; download dentro do TTL teve sucesso (200), depois de
  expirado falhou (400) — o contrato de produção (constante fixa,
  agora 24h) nunca foi alterado para viabilizar este teste.
- **Limpeza por falha de assinatura, prova real (não só fake).** Um
  seam de teste controlado força `assinar_url()` a falhar SEM mexer em
  IAM (upload e exclusão continuam sendo os métodos reais da classe) —
  `ErroAssinaturaArtefato` propagado com `limpeza_ok=True`, e o objeto
  órfão confirmado ausente por uma listagem real subsequente.
- **USER DECISION — SIGNED URL LIFETIME CHANGE, aplicada.** Janela de
  autorização de download revisada de 15 minutos para **24 horas**
  (`TTL_DOWNLOAD_SEGUNDOS = 86400`) — decisão explícita do usuário,
  não uma escolha técnica deste agente. A URL assinada continua
  documentada explicitamente como capacidade portadora (quem a possuir
  dentro da janela baixa o artefato, sem segunda verificação de
  identidade) — a janela maior é reconhecida como maior exposição, não
  minimizada.
- **USER RETENTION DECISION — HARD DELETE REQUIRED, aplicada e provada
  ao vivo.** Elegibilidade de limpeza revisada para EXATAMENTE
  `TTL_DOWNLOAD_SEGUNDOS` (24h, sem margem — substitui uma revisão
  intermediária de 26h que chegou a ser implementada e testada antes
  desta decisão final). Auditados e confirmados AO VIVO neste bucket,
  nesta ordem: soft-delete desligado (`retentionDurationSeconds: 0`),
  versionamento desligado, sem retention policy (Bucket Lock), sem
  default event-based hold. Lifecycle backstop revisado de `age: 1`
  para **`age: 2`** (dias) — aplicado ao vivo — porque a documentação
  oficial da Google (consultada nesta sessão) confirma que a condição
  `age` é avaliada no aniversário exato de criação do objeto e que a
  ação de exclusão é assíncrona **sem nenhuma garantia de prazo**; 2
  dias dá uma elegibilidade mínima de 48h, o dobro da janela de 24h,
  antes mesmo de considerar esse atraso assíncrono.
  **Prova real de HARD DELETE, os seis itens exigidos:** objeto criado
  com `created_at` retroagido além do limiar, URL assinada real emitida
  para ele, `limpar_artefatos_elegiveis` REAL executada (sem fake) —
  confirmado depois: (1) ausente da listagem autenticada real; (2) a
  URL assinada emitida ANTES da exclusão passa a devolver **404** (o
  objeto em si não existe mais, não é só "expirado"); (3) acesso não
  assinado continua negado (401); (4) `gcloud storage ls
  --soft-deleted` para o objeto devolve vazio — nenhuma geração
  recuperável; (5)/(6) sem geração não corrente possível, porque o
  bucket nunca teve versionamento ligado.
- **Limpeza deixa de depender só de tráfego — novo entrypoint
  standalone.** Achado do usuário, correto: limpeza oportunista
  (disparada só quando alguém finaliza uma peça) nunca garante, sozinha,
  retenção normal de ~24-25h num período sem tráfego algum. Novo
  `scripts/limpar_artefatos_agendado.py` — chama o mesmo núcleo
  (`artifact_storage.limpar_artefatos_elegiveis`) em laço, pronto para
  ser acionado por um mecanismo de agendamento externo (Cloud Scheduler
  -> Cloud Run Job/endpoint autenticado, cadência horária recomendada).
  **A infraestrutura de agendamento em si (Cloud Scheduler, o alvo que
  ele chama) NÃO foi provisionada nesta rodada** — deployar um novo
  serviço/job invocável ficou fora do escopo desta continuação
  (homologação, sem nova infraestrutura viva); é o item em aberto mais
  importante para a ADR-0019 antes do gate de download ao vivo. Sem
  esse agendamento ligado, a retenção normal comprovada hoje continua
  sendo só a via oportunista.
- **Código:** `scripts/artifact_storage.py` ganha `TransporteArtefato.
  listar()` (real e fake), `LIMPEZA_ELEGIVEL_SEGUNDOS`,
  `LIMPEZA_MAX_OBJETOS_POR_VARREDURA`, `limpar_artefatos_elegiveis()`
  (best-effort, nunca bloqueia a finalização que a disparou — uma
  finalização já bem-sucedida nunca deve ser degradada por um artefato
  órfão e não relacionado). `scripts/finalizar_peca.py` chama a
  limpeza oportunista logo após montar a resposta de sucesso, dentro de
  um `try/except Exception: pass` deliberado. Novo
  `scripts/limpar_artefatos_agendado.py`.
- **Testes:** `tests/test_artifact_storage.py` ganha 7 casos novos de
  limpeza (remove além do limiar, preserva o recente, ignora objeto sem
  metadado esperado, nunca inspeciona fora do prefixo `artifacts/`,
  respeita o teto por varredura, registra falha sem propagar exceção,
  limiar é exatamente o TTL). Novo `tests/test_limpar_artefatos_
  agendado.py` (4 casos, fake, sem rede: usa o transporte do ambiente,
  repete até esgotar backlog, respeita teto de rodadas por execução,
  configuração ausente sai com código 2). Valores de TTL/limiar
  reconciliados em todos os testes que os referenciavam (900s -> 86400s
  onde representava o contrato de produção; literais de teste
  arbitrários da função de assinatura de baixo nível, não ligados à
  constante de produção, mantidos como estavam). Suíte completa: 1178
  passam (1114 unidade + 64 `docx_real`), 1 falha preexistente e não
  relacionada (`skills/docx` local).
- **Nenhuma mudança de produção.** `ede-mcp-00020-gum`/`0.14.0`/100%
  intocados; nenhuma IAM de runtime de produção alterada; nenhum
  deploy; nenhuma tag Git; nenhum GitHub Release; nenhuma ampliação de
  acesso de advogados. Toda IAM temporária desta continuação foi
  removida antes do fim da sessão, confirmado por leitura.
- **Gate 6.6-E permanece `PARTIAL PASS`.** A prova de assinatura/hard
  delete que faltava está completa; falta ainda: provisionar o
  agendamento real de limpeza, aplicar a IAM de produção (passo
  controlado à parte), e o próprio gate de download ao vivo com Claude
  e ChatGPT (não iniciado — aguardando autorização explícita).

### Gate 6.6-E fechamento — limpeza agendada provisionada e provada em homologação (VERSION permanece 0.15.0)
- **Correção conceitual do usuário, aplicada:** o gate de download ao
  vivo com Claude/ChatGPT **não** é requisito para o PASS do Gate
  6.6-E — a sequência é `6.6-E PASS` -> candidato aceito -> só então,
  mediante autorização separada, o gate ao vivo. A única pendência que
  restava para o fechamento era a prova real do mecanismo AGENDADO de
  hard delete em períodos sem novas finalizações.
- **`scripts/limpar_artefatos_agendado.py` entra na imagem de
  runtime.** Liberado nas três allowlists independentes já usadas pelos
  módulos do Gate 6.6-C/6.6-E (linha `COPY` do Dockerfile,
  `.dockerignore`, e a verificação feita de DENTRO da imagem real pelo
  workflow de homologação), com novo teste
  `test_modulos_core_do_gate_6_6_e_liberados` travando as duas
  primeiras contra esquecimento. A limpeza roda a MESMA imagem do
  servidor MCP, trocando só o comando do container — nunca uma segunda
  implementação de exclusão fora da imagem de runtime.
- **Infraestrutura agendada, estritamente homologatória, provisionada
  com autorização explícita:** Cloud Scheduler
  `ede-artefatos-limpeza-homolog-horaria` (`0 * * * *` UTC, OAuth) ->
  Cloud Run Job `ede-artefatos-limpeza-homolog` (imagem fixada por
  DIGEST, nunca `:latest`; comando `python scripts/limpar_artefatos_
  agendado.py --json`) -> hard delete. Service account dedicada
  `ede-artefatos-limpeza-homolog` com **apenas**
  `roles/storage.objectAdmin` escopado ao bucket de artefatos e
  `roles/run.invoker` no próprio Job — **nenhuma autoridade de
  assinatura** (o caminho de limpeza jamais assina URL) e **nenhuma
  chave JSON** (identidade de workload do Cloud Run). API Cloud
  Scheduler habilitada no projeto como parte do provisionamento mínimo.
- **Prova real do caminho AGENDADO, sem nenhuma chamada a
  `finalizar_peca`:** três objetos reais no bucket de homologação e o
  Scheduler disparado de fato. Resultado — objeto de 25h (elegível):
  **excluído**; objeto recém-criado (<24h): **preservado**; objeto de
  99h fora do prefixo `artifacts/`: **intocado**. Log da execução com
  **só contadores agregados** (`status=OK; rodadas=1; inspecionados=2;
  excluidos=1; falhas=0`) — nenhum nome de objeto, nenhuma URL
  assinada, nenhum dado de caso.
- **Hard delete confirmado sobre o objeto excluído pelo caminho
  agendado:** GET autenticado -> **404**; URL assinada emitida ANTES da
  exclusão, ainda dentro da validade de 1h -> **404** (prova de que o
  OBJETO sumiu, não de que a URL expirou); acesso não assinado ->
  **401**; e a consulta de versões soft-deletadas é **recusada pelo
  próprio GCS** (`HTTPError 400: Soft delete policy is required to list
  soft-deleted versions`) — evidência mais forte que uma lista vazia:
  sem política de soft delete, geração recuperável não pode existir por
  construção. Versionamento permanece desligado.
- **Semântica de falha verificada ao vivo.** Uma execução foi
  propositalmente induzida a falhar (override de variável de ambiente
  SÓ na execução — a definição do Job foi conferida depois e continua
  íntegra): contêiner saiu com código 2, log com erro tipado
  (`status=ERRO_CONFIGURACAO`) e sem conteúdo algum, e os dois objetos
  NÃO elegíveis permaneceram **byte a byte intactos** (mesma
  `Generation`, mesmo `Content-Length` antes e depois). Execução
  agendada que falha não exclui, não altera e não corrompe nada; o
  backstop de lifecycle (`age: 2`, assíncrono) segue ativo
  independentemente.
- **Limpeza pós-prova:** objetos de teste removidos, service account
  temporária de assinatura (`ede-artefatos-signer-tmp`, usada só para
  emitir a URL que depois deveria dar 404) deletada junto do seu
  binding de bucket, bucket confirmado vazio. Permanecem, por serem a
  própria infraestrutura candidata homologada: bucket, Cloud Run Job,
  Cloud Scheduler e a SA de limpeza — todos rotulados
  `gate=6-6-e`/`status=homolog-candidate`.
- **Nenhuma mudança de produção.** `ede-mcp-00020-gum`/`0.14.0`/100%
  intocados; nenhuma variável `EDE_ARTEFATOS_*` na revisão de produção;
  IAM da service account de runtime de produção inalterado (confirmado
  por leitura ao final); sem deploy, sem tag Git, sem GitHub Release,
  sem rollout para advogados; gate de download ao vivo NÃO iniciado.
- **Suíte completa:** 1179 passam, 1 falha preexistente e não
  relacionada (`skills/docx` local, ausente no clone limpo da CI).

### Gate 6.6-E hardening final — fecha a corrida entre expiração real da URL e elegibilidade de limpeza
- **Achado real do usuário, corrigido na origem.** `assinar_url()`
  capturava seu próprio `datetime.now()` DEPOIS do upload já ter
  terminado — como assinar sempre ocorre depois de enviar (a própria
  latência de rede do upload), a expiração criptográfica real da URL
  (`X-Goog-Date + X-Goog-Expires`) ficava sempre um pouco DEPOIS do
  `expires_at` gravado no metadado. Uma varredura de limpeza rodando
  exatamente nessa janela — mesmo pequena — poderia excluir o objeto
  enquanto a URL emitida para ele ainda era tecnicamente válida.
- **Solução: instante único compartilhado, não um segundo campo de
  metadado.** Avaliada e descartada a alternativa de gravar um novo
  `download_expires_at` a partir do instante real de assinatura (exigiria
  uma segunda escrita de rede pós-assinatura, um modo de falha novo, e
  ainda deixaria uma janela menor, mas real). Em vez disso,
  `entregar_artefato_efemero` captura `agora` UMA vez e passa esse
  MESMO valor como `momento` explícito para `assinar_url()` — novo
  parâmetro opcional em `TransporteArtefato.assinar_url`/
  `TransporteGcsReal.assinar_url`/`_construir_url_assinada_v4`
  (`momento: datetime | None = None`; `None` preserva o relógio interno
  para assinaturas sem vínculo de metadado, como os testes de expiração
  já existentes). `X-Goog-Date` passa a ser EXATAMENTE o instante
  gravado em `created_at`/`expires_at` — a expiração real da URL e o
  `expires_at` do metadado tornam-se o MESMO valor, não uma aproximação.
- **`limpar_artefatos_elegiveis` decide por `expires_at`, nunca mais
  recalcula a partir de `created_at`** (essa reconstrução é exatamente
  o que reabriria a corrida). Metadado ausente ou malformado é
  fail-safe — objeto ignorado nesta varredura, nunca excluído por
  incerteza; o backstop de lifecycle continua sendo a rede de
  segurança para esse caso. `LIMPEZA_ELEGIVEL_SEGUNDOS` permanece como
  documentação de como `expires_at` é calculado no upload, não mais
  como base de uma segunda comparação independente.
- **Verificado AO VIVO, não só em teste de unidade:** pipeline completo
  real (render -> upload -> assinatura) contra o bucket de
  homologação, com uma service account temporária criada, usada e
  removida ao final. `expires_at` do metadado e `X-Goog-Date +
  X-Goog-Expires` extraídos da URL real bateram exatamente
  (`2026-09-24T00:50:37Z` nos dois lados); download real funcionou
  (200) logo em seguida; objeto de teste removido ao final.
- **Testes novos** em `tests/test_artifact_storage.py`: `expires_at`
  malformado é fail-safe (ignorado); regressão direta da corrida —
  objeto "velho" por `created_at` mas com `expires_at` ainda no futuro
  NUNCA é excluído; espelho — objeto "jovem" por `created_at` mas com
  `expires_at` já no passado É excluído; `assinar_url()` recebe
  exatamente o mesmo instante gravado no metadado;
  `_construir_url_assinada_v4` com `momento` explícito determina
  `X-Goog-Date`/`credential_scope` byte a byte. Helpers de teste de
  limpeza (`tests/test_artifact_storage.py`,
  `tests/test_limpar_artefatos_agendado.py`) passam a gravar `expires_at`
  coerente com `created_at + TTL_DOWNLOAD_SEGUNDOS`, refletindo o
  comportamento real pós-correção. Suíte completa: 1184 passam, 1 falha
  preexistente e não relacionada (`skills/docx` local).
- **Nenhuma mudança de produção.** `ede-mcp-00020-gum`/`0.14.0`/100%
  intocados; IAM de runtime de produção inalterado; toda IAM temporária
  desta prova foi removida e confirmada removida; sem deploy, sem tag
  Git, sem GitHub Release, sem rollout para advogados. Gate 6.6-E
  permanece `PASS`.

### Notas
- A camada é **opt-in** (`EDE_MCP_AUTH_ENABLED`) em todo serviço exceto
  o de produção (`K_SERVICE=ede-mcp`, ver acima). Desligada, o
  comportamento é exatamente o das Etapas 6.1/6.2 e o startup declara
  que não há autorização de aplicação. Configuração pela metade faz o
  servidor recusar subir — nunca degrada para acesso anônimo.
- Nenhum pacote novo no container: `pyjwt[crypto]` já era dependência
  direta de `mcp==2.2.0`; passou apenas a ser declarada e pinada.
- Sem mutação de infraestrutura nesta rodada: nenhum deploy, nenhum
  serviço `ede-mcp` criado, `ede-mcp-staging` intocado, nenhum Resource
  Descope criado, nenhum bucket ou upload do Modelo Oficial. `VERSION`
  passa a `0.12.0` (SemVer minor — Resource Server OAuth é uma
  funcionalidade nova e retrocompatível), **sem tag e sem GitHub
  Release** nesta etapa: a publicação formal fica para depois da prova
  de OAuth de produção (Gate 6.3-D3.7).
- **Nenhuma funcionalidade jurídica de produção é ativada por esta
  entrada.** `contestacao` continua não exposta como ferramenta remota;
  o Modelo Oficial em produção (Arquitetura A′) é desenho aprovado, não
  implementado; nenhuma conexão de produção com Claude ou ChatGPT foi
  estabelecida.

## [0.11.1] - 2026-09-10 — Fail-closed sem Modelo Oficial (hotfix)

### Corrigido
- Achado real pós-v0.11.0: em uso externo sem `templates/contestacao/
  modelo-oficial.docx` instalado, a execução produzia um documento Word
  autônomo em vez de abortar. Auditoria confirmou que o runtime Python
  já abortava corretamente (`gerar_contestacao.py` → `PIPELINE_ABORTED`,
  `stage=contexto_institucional`; `ede_doctor.py` → `NOT READY`) — a
  lacuna estava em `skills/contestacao/SKILL.md`, sem alteração de
  runtime, Template Lock, schema ou catálogo de blocos.
- `skills/contestacao/SKILL.md` — nova seção `§0A` exigindo pré-flight
  obrigatório via `ede_doctor.py` antes de qualquer elaboração em MODO
  PRODUÇÃO: sem `READY TO GENERATE`, bloqueio absoluto da geração,
  sem fallback documental.
- Proibição explícita de contornar o bloqueio gerando a Contestação por
  mecanismo alternativo (Skill genérica `docx`, `python-docx`, XML
  manual, outra Skill, ou qualquer outro caminho fora do pipeline
  oficial) — registrada em `§0A` e `§10`.
- Urgência processual, prazo vencendo ou pedido explícito do advogado
  nesse sentido não autorizam o bypass — o bloqueio é condicional ao
  estado do ambiente (`ede_doctor.py`), nunca à alegação de urgência.
- `§11` (`INV-CONTESTACAO-ENTREGA-DOCX`) passa a reconhecer
  explicitamente "modelo ausente/`ede_doctor` não READY" como
  interrupção legítima, distinta das demais; a regra de entrega
  contínua ("sempre entregar o DOCX") passa a ficar expressamente
  subordinada ao pré-flight aprovado.

### Adicionado
- `tests/test_contestacao_modelo_ausente_bloqueio.py` — guardas
  estruturais do contrato de pré-flight/bloqueio absoluto, mais
  confirmação funcional de que o runtime continua abortando sem o
  template e de que o ambiente regularizado não permanece bloqueado.

## [0.11.0] - 2026-09-10 — Runtime DOCX autônomo e distribuição reprodutível (Etapa 5.10)

### Adicionado (Etapa 5.10 — runtime DOCX autônomo e distribuição reprodutível, ADR-0014)
- Runtime OOXML/ZIP próprio do EDE (`scripts/docx_package.py`) substituindo
  a dependência de runtime do skill "docx" de terceiro (Anthropic) —
  não redistribuível pela licença dele e com contrato incompatível com a
  versão atualmente publicada (PEND-007, **resolvida**). Extração/
  reempacotamento OOXML próprios, XXE mitigado via `lxml` configurado
  (sem `defusedxml` — decisão registrada em `ADR-0014`), migrado para
  todos os consumidores (`docx_template_engine.py`, `docx_context_engine.py`,
  `docx_block_engine.py`, `validate_template.py`) sem regressão (57/57
  partes OOXML byte-idênticas na comparação runtime antigo × novo).
- `scripts/instalar_modelo_oficial.py` — bootstrap do Modelo Oficial:
  valida pacote OOXML e contrato institucional (placeholders/blocos/
  zonas) antes de instalar, instalação atômica, nunca substitui um
  modelo válido por um arquivo não validado; SHA-256 registrado só para
  auditoria, nunca como gate de compatibilidade.
- `scripts/ede_doctor.py` — diagnóstico de ambiente host-agnostic
  (`READY TO GENERATE`/`NOT READY`), verificação controlada de
  dependências Python (nunca importa o runtime antes de confirmar
  `lxml` presente), sem exigir `CLAUDE_PLUGIN_ROOT`.
- `scripts/homologar_distribuicao.py` — harness de homologação de
  distribuição: prova, sobre um clone Git limpo e temporário, que o
  pacote publicamente distribuível instala dependências, instala o
  Modelo Oficial, passa no doctor antes/depois, executa o pipeline
  completo até o DOCX final com Template Lock aprovado e zero resíduo
  de placeholder/zona/SDT, e aprova `validate_template.py` — sem
  depender de `skills/docx/`, DataJud real (isolado por stub
  determinístico só nesta homologação) ou caminho privado do
  desenvolvedor.
- `scripts/validate_template.py` reconstrói a peça de referência pelo
  mecanismo real de geração (`gerar_peca_com_blocos` — composição de
  blocos/zonas, renumeração, Template Lock interno), corrigindo um
  falso negativo sistemático contra Contestações reais com blocos
  excluídos (achado do Commit 7, corrigido no Microfix 7.1); propagação
  crua de erro de pacote OOXML inválido também corrigida (Microfix 7.1).
- `docs/DISTRIBUICAO.md` — guia de instalação/distribuição reprodutível,
  documentando exclusivamente o que foi homologado nos Commits 1–8.

### Corrigido
- Peso do fallback RAG TF-IDF+LSA: `svd.joblib` passou de 77,34 MiB para
  34,19 MiB (redução de 55,8%) com `components_` em `float32` e compactação
  Joblib zlib nível 3. O manifesto e o loader agora exigem esse contrato de
  armazenamento, sem nova dependência, download posterior ou perda do modo
  offline. O gold-set permaneceu em 18/24 top-1 e 21/24 top-3 (ADR-0013;
  PEND-003 resolvida).
- Compatibilidade do fallback RAG TF-IDF+LSA: dependências numéricas e de
  serialização fixadas, artefatos regenerados no runtime canônico e novo
  contrato fail-closed no `manifest.json`, com versões de Python/pacotes e
  SHA-256 dos arquivos carregados. O loader agora rejeita o manifesto legado,
  runtime incompatível, arquivo ausente ou alterado antes de abrir Parquet ou
  desserializar Joblib (ADR-0011). Qualidade preservada: 75% top-1 e 88% top-3.
- Localização dos recursos da Skill `contestacao`: substituído o uso de
  `$CLAUDE_PLUGIN_ROOT`/`os.environ` nos subprocessos pela expansão inline
  `${CLAUDE_PLUGIN_ROOT}` feita pelo host no conteúdo da Skill. Scripts,
  RAG, catálogo e template continuam independentes do `cwd`; arquivos do caso
  permanecem relativos ao workspace do advogado. Token não expandido ou root
  sem as sentinelas do plugin causa fail-closed (ADR-0012, SPEC-0001 §61).
- Reconciliação da documentação pós-auditoria: `PEND-006` passa a constar
  como resolvida também no índice e deixa de manter fechamento contraditório;
  `PEND-005` fica aberta somente para a futura migração a listas multinível
  nativas, reconhecendo que o motor atual já elimina lacunas; `PEND-003`
  distingue o tamanho ainda pendente da compatibilidade de runtime já
  corrigida pelo ADR-0011. Corrigidas também a contagem documental de 13
  placeholders, a condição 404 de `/atualizar-ede` sem afirmação temporal e
  a advertência de que o fluxo Cowork ainda não foi homologado de ponta a
  ponta e que `synced`/`updated` não comprova a versão efetivamente carregada.
- Suíte pytest segmentada por marcadores estritos e mutuamente exclusivos:
  grupo rápido unitário/estrutural, `docx_real`, `rag`, `pipeline_e2e` e
  `network` opt-in. A suíte completa permanece o gate final; o segmento E2E
  é explicitamente o pipeline Python local, sem simular homologação do host
  Claude Code ou do Cowork. Novo guarda coleta todos os segmentos e comprova
  que formam uma partição sem sobreposição.

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

> **Nota posterior:** o mecanismo desta etapa tratava o root como variável de
> ambiente do subprocesso. A correção registrada em **Não publicado** e no
> ADR-0012 preserva a intenção de portabilidade, mas usa a expansão inline
> `${CLAUDE_PLUGIN_ROOT}` do host; esta descrição permanece como histórico.

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
