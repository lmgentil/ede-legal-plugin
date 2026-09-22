# mcp_server/Dockerfile — imagem mínima do EDE MCP Server (Etapa 6.2-A).
#
# Escopo desta etapa: ARTEFATO ESTÁTICO apenas. Este arquivo nunca foi
# construído nem executado nesta máquina — não há runtime de container
# disponível neste ambiente (nem Docker, nem Podman, nem WSL com
# distribuição instalada), e a decisão do usuário nesta rodada foi
# deliberada: não instalar nenhum deles apenas para satisfazer o gate
# local. O objetivo arquitetural do EDE é execução remota em nuvem, não
# dependência de container runtime na máquina do advogado/desenvolvedor.
# Build real, testes reais (positivos e negativos) e inventário real de
# dependências instaladas ficam para a Etapa 6.2-B (build remoto, gate
# próprio, ainda não autorizado — GATE CLOUD RUN STAGING).
#
# Decisões já aprovadas nos gates anteriores (Etapa 6.0/6.1/6.2):
#   - ADR-0015: este servidor é um adapter remoto fino sobre o EDE Core;
#     nunca chama a API Claude/LLM, nunca reimplementa
#     estrategista-contestacao-ede/redator-peca-processual-elite/
#     humanizer-pt-br (essas Skills continuam rodando no host Claude).
#   - HOST/PORT são sempre lidos do ambiente por mcp_server/server.py
#     (main()) — este Dockerfile NUNCA fixa PORT (nem em ENV, nem em
#     CMD, nem em nenhuma outra instrução). A plataforma (Cloud Run)
#     injeta PORT em runtime; o servidor só cai no default LOCAL 8765
#     quando a variável está mesmo ausente (não é o caso em
#     container/Cloud Run, onde HOST é fixado abaixo e PORT vem de
#     fora).
#   - HOST=0.0.0.0 é decisão do AMBIENTE CONTAINERIZADO (ver ENV
#     abaixo) — distinta do default local 127.0.0.1 usado fora de
#     container (server.DEFAULT_HOST_LOCAL).
#   - Sem EXPOSE: é só documentação para humanos/alguns orquestradores
#     locais — Cloud Run ignora a instrução e descobre a porta
#     exclusivamente via variável de ambiente PORT. Declarar um valor
#     fixo aqui sugeriria, incorretamente, que a porta é estática.
#
# Imagem-base: python:3.12-slim.
#
# Digest resolvido de forma REAL nesta rodada (não inventado) via Docker
# Hub Registry API v2:
#   GET https://registry.hub.docker.com/v2/repositories/library/python/tags/3.12-slim
#   consultado em 2026-09-10. Campos relevantes da resposta real:
#     name:                 3.12-slim
#     digest (manifest-list, multi-arch):
#       sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
#     last_updated:         2026-09-02T05:07:35.501893Z
#     amd64 image digest:   sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79
#     amd64 size:           46175163 bytes (~44 MiB, camada base comprimida, reportada pela API — NÃO o tamanho final da imagem construída)
#   O valor fixado em FROM é o digest da MANIFEST LIST (multi-arch) — o
#   mesmo que `docker pull python:3.12-slim` resolve hoje, e o que
#   `docker buildx imagetools inspect python:3.12-slim` reportaria.
#   "3.12-slim" é tag ROLANTE: a mantenedora da imagem oficial pode
#   publicar nova revisão (patch de segurança do Debian bookworm/CPython
#   3.12.x) a qualquer momento, o que muda este digest. ESTE VALOR DEVE
#   SER RE-VERIFICADO NO MOMENTO DO BUILD REMOTO (Etapa 6.2-B) — não
#   reutilizar cegamente se muito tempo tiver passado desde 2026-09-10.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

# Reprodutibilidade/higiene do runtime Python em container — não afeta
# nenhuma decisão arquitetural discutida nos gates: só evita bytecode
# .pyc órfão numa imagem que deveria ser imutável, e garante que
# stdout/stderr do processo MCP cheguem sem buffer aos logs do
# orquestrador (Cloud Run/`docker logs`).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Usuário dedicado não-root, UID/GID estáveis (10001), conforme decisão
# do gate. --no-create-home: /app já é o WORKDIR, não precisa de home.
# --shell /usr/sbin/nologin: sem shell interativo — este container só
# existe para rodar mcp_server/server.py, nunca para login. Sem sudo,
# sem ferramenta administrativa adicionada além do necessário para criar
# o próprio usuário.
#
# groupadd/useradd assumidos disponíveis por virtude da imagem-base ser
# Debian (bookworm-slim) — pacote `passwd`, parte do conjunto essencial
# de qualquer imagem Debian, inclusive a variante "slim" (que remove
# documentação/pacotes não-essenciais, não utilitários essenciais do
# sistema base). NÃO CONFIRMADO POR EXECUÇÃO REAL nesta rodada — é a
# primeira coisa a validar no build remoto da Etapa 6.2-B.
RUN groupadd --gid 10001 ede \
    && useradd --uid 10001 --gid ede --no-create-home --shell /usr/sbin/nologin ede

# Copiar SOMENTE requirements.txt primeiro (cache de layer: mudanças em
# server.py não invalidam o `pip install`, que é o passo mais caro desta
# imagem). Ver mcp_server/../.dockerignore (allowlist) para a prova
# estática de que nenhum outro arquivo do repositório entra no contexto
# de build.
COPY mcp_server/requirements.txt mcp_server/requirements.txt

# Só as dependências diretas declaradas em mcp_server/requirements.txt
# são instaladas aqui — nunca scripts/requirements.txt, rag/
# requirements.txt ou um requirements geral do projeto (nenhum dos quais
# é sequer copiado para o contexto, ver .dockerignore). Desde o Gate
# 6.4-A isso inclui `lxml` (contrato do Modelo Oficial) e, desde o Gate
# 6.4-B, `google-auth` (aquisição do Modelo Oficial via GCS, Arquitetura
# A′ — só `google.auth.default()`; NUNCA `google-cloud-storage`, ver
# comentário em mcp_server/requirements.txt). Desde o Gate 6.4-C1,
# `requests` também: achado real de um rollback de produção
# (`google.auth.compute_engine._metadata` — a detecção de ambiente
# Cloud Run/GCE usada por `google.auth.default()` — tem `import
# requests` incondicional; sem ela a detecção falha e o Modelo Oficial
# nunca fica READY). A leitura do objeto GCS em si continua usando só
# `httpx2` (já transitivo via `mcp`) — `requests` entra somente pela
# árvore de `google-auth`, nenhuma linha do EDE a importa diretamente.
# Deliberadamente ausentes: pyarrow, rank_bm25, sentence-transformers,
# pandas, numpy, joblib, scikit-learn, scipy,
# google-cloud-storage/google-api-core — a checagem de saúde do corpus
# RAG usa só biblioteca padrão. Se alguma dependência não declarada
# entrar TRANSITIVAMENTE, isso só pode ser confirmado num build real
# (ainda não executado nesta máquina — sem runtime de container
# disponível) —
# nenhuma alegação de inventário de
# dependências instaladas é feita aqui.
RUN pip install --no-cache-dir -r mcp_server/requirements.txt

# Demais arquivos autorizados — mesmo espirito do .dockerignore em
# allowlist: nada de `COPY mcp_server/ mcp_server/` nem `COPY scripts/
# scripts/` nem `COPY rag/ rag/`, que trariam para a imagem qualquer
# arquivo futuro do diretorio sem revisao. --chown evita uma camada RUN
# chown separada; os pacotes instalados acima continuam legiveis pelo
# usuario nao-root pelas permissoes default do pip (site-packages
# world-readable em python:slim).
# Gate 6.3-D2: server.py deixou de ser o unico modulo -- a camada OAuth
# de aplicacao vive em modulos irmaos, importados por caminho plano
# (`from auth_config import ...`), que funciona porque `python
# mcp_server/server.py` coloca mcp_server/ como sys.path[0]. Os cinco sao
# copiados explicitamente.
COPY --chown=10001:10001 mcp_server/server.py mcp_server/server.py
COPY --chown=10001:10001 mcp_server/auth_config.py mcp_server/auth_config.py
COPY --chown=10001:10001 mcp_server/auth_logging.py mcp_server/auth_logging.py
COPY --chown=10001:10001 mcp_server/http_telemetry.py mcp_server/http_telemetry.py
COPY --chown=10001:10001 mcp_server/scope_policy.py mcp_server/scope_policy.py
COPY --chown=10001:10001 mcp_server/prm_override.py mcp_server/prm_override.py
COPY --chown=10001:10001 mcp_server/token_verifier.py mcp_server/token_verifier.py
COPY --chown=10001:10001 VERSION VERSION

# Gate 6.4-A (ADR-0015/ADR-0017): EDE Core mínimo necessário para
# `scripts/legal_readiness.py` (chamado por server.py em `ede_health`) —
# só os módulos de manipulação/validação OOXML que ele importa
# transitivamente, nunca o pipeline inteiro de geração da Contestação
# (gerar_contestacao.py, datajud_client.py etc. continuam FORA — nenhuma
# ferramenta de GERAÇÃO DE DOCX era exposta por este gate, só readiness e
# preparação de contexto).
#
# Gate 6.5-A acrescenta `docx_context_engine.py` (contexto institucional
# ao redor dos placeholders — mesma disciplina lxml-only das demais) e
# `validate_fatos.py` (validação estrutural de fatos.json, biblioteca
# padrão, sem lxml sequer) para `scripts/preparar_contestacao.py`
# (`ede_preparar_contestacao`, escopo `ede:legal`).
COPY --chown=10001:10001 scripts/legal_readiness.py scripts/legal_readiness.py
COPY --chown=10001:10001 scripts/preparar_contestacao.py scripts/preparar_contestacao.py
COPY --chown=10001:10001 scripts/docx_package.py scripts/docx_package.py
COPY --chown=10001:10001 scripts/docx_template_engine.py scripts/docx_template_engine.py
COPY --chown=10001:10001 scripts/docx_block_engine.py scripts/docx_block_engine.py
COPY --chown=10001:10001 scripts/docx_numeracao_engine.py scripts/docx_numeracao_engine.py
COPY --chown=10001:10001 scripts/docx_context_engine.py scripts/docx_context_engine.py
COPY --chown=10001:10001 scripts/instalar_modelo_oficial.py scripts/instalar_modelo_oficial.py
COPY --chown=10001:10001 scripts/validate_fatos.py scripts/validate_fatos.py

# Gate 6.6-C (ADR-0018): `ede_finalizar_peca` roda dentro do container o
# MESMO pipeline endurecido do Gate 6.6-A, nunca uma versão reduzida —
# `validate_paragrafos.py`/`validate_placeholder_semantics.py` (validação
# estrutural/semântica 380/densidade/travessão/produção-final, biblioteca
# padrão, sem lxml) deixam de ficar "FORA" (comentário acima, agora
# desatualizado por esta razão) porque o finalizador as chama antes de
# renderizar; `docx_fidelidade_independente.py`/`docx_round_trip.py` são
# a verificação PÓS-render que deliberadamente nunca chama as funções de
# composição/substituição do próprio renderer (Gate 6.6-A); `capability_
# registry.py` é o registro determinístico de capacidades (só
# `contestacao.irregularidade_consumo` está `READY` — INV-GATE-
# CONTESTACAO); `finalizar_peca.py` é o próprio pipeline Core do
# finalizador. `gerar_contestacao.py`/`datajud_client.py` continuam FORA
# — o finalizador nunca resolve `JUIZO`/tempestividade, só compõe e
# renderiza a partir de um rascunho já estruturado.
COPY --chown=10001:10001 scripts/validate_paragrafos.py scripts/validate_paragrafos.py
COPY --chown=10001:10001 scripts/validate_placeholder_semantics.py scripts/validate_placeholder_semantics.py
COPY --chown=10001:10001 scripts/docx_fidelidade_independente.py scripts/docx_fidelidade_independente.py
COPY --chown=10001:10001 scripts/docx_round_trip.py scripts/docx_round_trip.py
COPY --chown=10001:10001 scripts/capability_registry.py scripts/capability_registry.py
COPY --chown=10001:10001 scripts/finalizar_peca.py scripts/finalizar_peca.py

# Gate 6.6-E (ADR-0019): entrega v2 do artefato -- objeto GCS efêmero +
# URL HTTPS assinada, substitui o EmbeddedResource inline v1 (Decisão 5
# da ADR-0018, provada insuficiente no Gate 6.6-D). Nenhum SDK de nuvem
# novo na imagem (google-auth e httpx2 já eram dependências, ver
# mcp_server/requirements.txt) -- só este módulo Core.
COPY --chown=10001:10001 scripts/artifact_storage.py scripts/artifact_storage.py

# Contrato institucional (público, git-tracked — nunca o Modelo Oficial
# .docx em si, que é asset privado externo, ADR-0009, e nunca entra
# nesta imagem nem em nenhuma outra).
COPY --chown=10001:10001 templates/contestacao/schema.json templates/contestacao/schema.json
COPY --chown=10001:10001 templates/contestacao/blocos.json templates/contestacao/blocos.json

# Gate 6.5-A: só `models.py` de rag/legal_validation/ (o construtor
# `fonte_juridica()`, puro dict, sem import algum) — nunca o pacote
# `legal_validation` inteiro, cujo `__init__.py` importa `citation_
# parser.py` -> `rag/search_hybrid.py` -> pandas/numpy/scikit-learn/
# pyarrow/rank_bm25 (RNF-CUSTO-001; ver comentário em
# scripts/preparar_contestacao.py para o detalhe completo).
COPY --chown=10001:10001 rag/legal_validation/models.py rag/legal_validation/models.py

# Corpus RAG institucional — legislação já pública/versionada no
# repositório (CPC/CC/CDC/L8987/L9427/REN1000; nunca jurisprudência —
# INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL, CLAUDE.md §10 — que
# também nunca seria elegível: vive fora do repositório, em
# C:\Dev\ede-private\rag\jurisprudencia, dado de caso real, nunca
# versionado nem embutido em imagem alguma). Só os chunks de texto e o
# manifesto entram — deliberadamente SEM rag/embeddings/ (~43 MiB,
# exigiria pandas/numpy/pyarrow/scikit-learn só para a checagem de
# saúde, que verifica presença/integridade estrutural, nunca constrói
# índice de busca).
COPY --chown=10001:10001 rag/corpus_manifest.json rag/corpus_manifest.json
COPY --chown=10001:10001 rag/chunks_CPC rag/chunks_CPC
COPY --chown=10001:10001 rag/chunks_CC rag/chunks_CC
COPY --chown=10001:10001 rag/chunks_CDC rag/chunks_CDC
COPY --chown=10001:10001 rag/chunks_L8987 rag/chunks_L8987
COPY --chown=10001:10001 rag/chunks_L9427 rag/chunks_L9427
COPY --chown=10001:10001 rag/chunks_REN1000 rag/chunks_REN1000

# HOST=0.0.0.0 é decisão do AMBIENTE CONTAINERIZADO (main() em
# mcp_server/server.py lê HOST do ambiente; sem esta variável, cairia no
# default local 127.0.0.1, errado dentro de um container — o processo
# não aceitaria conexão vinda de fora do próprio container). PORT
# deliberadamente NUNCA aparece aqui — vem da plataforma (Cloud Run) ou,
# em teste manual do container, de `docker run -e PORT=...`.
ENV HOST=0.0.0.0

USER ede

# Sem EXPOSE (ver nota acima). server.py resolve HOST/PORT em main() —
# nenhuma lógica de transporte/porta é decidida neste Dockerfile.
CMD ["python", "mcp_server/server.py"]
