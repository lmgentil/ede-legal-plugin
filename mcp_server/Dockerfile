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

# Só a dependência direta declarada em mcp_server/requirements.txt
# (mcp==2.2.0) é instalada aqui — nunca scripts/requirements.txt,
# rag/requirements.txt ou um requirements geral do projeto (nenhum dos
# quais é sequer copiado para o contexto, ver .dockerignore).
# Deliberadamente ausentes (mesma disciplina do requirements.txt):
# pyarrow, rank_bm25, sentence-transformers, pandas, numpy, joblib,
# lxml. Se alguma delas entrar TRANSITIVAMENTE via `mcp`, isso só pode
# ser confirmado num build real (Etapa 6.2-B) — nenhuma alegação de
# inventário de dependências instaladas é feita aqui.
RUN pip install --no-cache-dir -r mcp_server/requirements.txt

# Demais arquivos autorizados — nada além destes três (mcp_server/
# requirements.txt já copiado acima, mcp_server/server.py e VERSION).
# --chown evita uma camada RUN chown separada; os pacotes instalados
# acima continuam legíveis pelo usuário não-root pelas permissões
# default do pip (site-packages world-readable em python:slim).
COPY --chown=10001:10001 mcp_server/server.py mcp_server/server.py
COPY --chown=10001:10001 VERSION VERSION

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
