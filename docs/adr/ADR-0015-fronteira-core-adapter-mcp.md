# ADR-0015 — Fronteira EDE Core / Claude Adapter / MCP Server

* **Status:** Aceito
* **Data:** 2026-09-10
* **Relacionado:** ADR-0006 (assets institucionais), ADR-0009 (Modelo
  Oficial externo), ADR-0012 (resolução de recursos do plugin), ADR-0014
  (runtime DOCX autônomo — item 8 já previa esta separação como "direção
  futura, não implementada por esta ADR"); SPEC-0001; Etapa 6.0
  (arquitetura e plano de extração MCP, aprovada pelo usuário) e Etapa 6.1
  (servidor MCP mínimo, `ede_health`).

## Contexto

A Etapa 6.0 auditou o EDE Core e constatou que parte relevante do trabalho
de portabilidade já existia: o ADR-0014 removeu a dependência do runtime
DOCX em relação ao skill "docx" de terceiro e deixou `scripts/docx_*.py`
host-agnósticos (nenhuma dependência de `CLAUDE_PLUGIN_ROOT`, `SKILL.md`,
`~/.claude`/`~/.agents`, OpenAI SDK, Apps SDK ou MCP). O mesmo vale para
`scripts/validate_*.py`, `scripts/datajud_client.py`,
`skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py`
e `rag/search_hybrid.py`/`rag/legal_validation/*.py` — todos recebem
`Path`/dados explícitos do chamador, sem resolver localização de host por
conta própria.

O único acoplamento de host ativo hoje está nos arquivos `SKILL.md`
(`skills/contestacao/`, `skills/estrategista-contestacao-ede/`,
`skills/redator-peca-processual-elite/`, `skills/humanizer-pt-br/`), que
orquestram esses scripts via Bash usando `${CLAUDE_PLUGIN_ROOT}` — uso já
legítimo segundo o próprio ADR-0014 (item 7).

`scripts/gerar_contestacao.py` documenta, no próprio módulo, uma
limitação estrutural ("LIMITAÇÃO CONHECIDA", SPEC-0001 Fase 7 §33): Skills
do Claude Code são arquivos de instrução para um agente LLM, não há API
Python para "executá-las" de dentro de um script. Isso força uma escolha
explícita antes de desenhar qualquer tool MCP que toque a Contestação:
onde roda o raciocínio jurídico (`estrategista-contestacao-ede`,
`redator-peca-processual-elite`, `humanizer-pt-br`)?

A especificação MCP vigente (2026-07-28) foi consultada nesta rodada, não
assumida por memória: tornou o núcleo do protocolo stateless (elimina
`initialize`/`initialized` e `Mcp-Session-Id`; cada request carrega
versão/identidade/capacidades em `_meta`), exige headers `Mcp-Method`/
`Mcp-Name` no transporte Streamable HTTP (SEP-2243) e mantém uma janela
de depreciação mínima de 12 meses para o transporte HTTP+SSE legado — não
construir sobre ele.

## Decisão

1. **Três camadas, fronteira explícita:**

   ```text
   EDE CORE (host-agnostic, execução determinística)
     scripts/docx_*.py, scripts/validate_*.py, scripts/datajud_client.py,
     skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py,
     rag/search_hybrid.py, rag/legal_validation/*.py,
     scripts/gerar_contestacao.py (gerar(), como biblioteca)

   CLAUDE ADAPTER (existente, host Claude)
     skills/*/SKILL.md — orquestração e raciocínio LLM;
     produz artefatos estruturados (estrategia.md, fatos.json,
     placeholders.json, decisoes_blocos.json, citacoes.json)

   MCP SERVER (novo, mcp_server/)
     adapter remoto fino; chama o EDE Core como biblioteca Python;
     nunca reimplementa raciocínio jurídico
   ```

2. **Opção A aprovada.** `estrategista-contestacao-ede`,
   `redator-peca-processual-elite`, `humanizer-pt-br` e a própria
   orquestração de `skills/contestacao/SKILL.md` continuam executando
   **no host Claude**, exatamente como hoje. O MCP Server **nunca** chama
   a API Claude ou qualquer LLM, e **nunca** reimplementa esse raciocínio
   — ele recebe do host os artefatos já produzidos pelas Skills e executa
   só a parte 100% determinística que `scripts/gerar_contestacao.py` já
   executa localmente hoje (validação de fatos/proveniência, cálculo de
   tempestividade, RAG/validação de citação, composição de blocos/zonas,
   renumeração, Template Lock, montagem do DOCX).

3. **Opção B rejeitada nesta fase.** Mover a execução das Skills para
   dentro do servidor (o servidor chamando a API Claude por conta
   própria) criaria uma segunda cópia de comportamento equivalente a
   `SKILL.md` fora do host, com risco de deriva entre as duas cópias, e
   violaria a vedação expressa de não alterar `skills/contestacao/
   SKILL.md` nesta etapa. Não autorizada.

4. **Runtime local v0.11.1 permanece baseline oficial** durante toda a
   prototipação (Fase A do plano de migração da Etapa 6.0). Nenhuma
   dependência local é removida, nenhum `SKILL.md` é alterado, nenhum
   script de `scripts/`/`rag/` é movido ou reorganizado por esta decisão.

5. **Diretório novo e isolado, `mcp_server/`.** Nome escolhido após
   auditar as convenções já existentes: diretórios de nível raiz do
   projeto (`scripts/`, `rag/`, `skills/`, `templates/`, `tests/`, `docs/`)
   são palavras únicas; onde há mais de uma palavra dentro de um pacote
   Python, o padrão é `snake_case` (`docx_block_engine.py`,
   `docx_template_engine.py`, todos os arquivos de `scripts/`), nunca
   `kebab-case` — reservado a diretórios de Skill orientados a produto/
   humano (`estrategista-contestacao-ede`, `redator-peca-processual-elite`).
   Como `mcp_server/` é, tal como `scripts/`/`rag/`, um diretório de
   módulos Python (não uma Skill), `snake_case` é a escolha coerente.
   Contém somente o necessário ao servidor MCP; nada do Core é movido
   para dentro dele — ele importa o Core como biblioteca, com o mesmo
   padrão de `sys.path.insert()` já usado por `scripts/gerar_
   contestacao.py`.

6. **SDK Python oficial `mcp`, versão pinada `2.2.0`** (release estável,
   publicada em 2026-09-07, linha major v2 — compatível com a
   especificação MCP 2026-07-28, confirmada nesta rodada via
   `https://pypi.org/pypi/mcp/json` e o changelog de releases do
   repositório oficial, não por memória). `mcp_server/requirements.txt`
   pina só a dependência direta (`mcp==2.2.0`), no mesmo padrão de
   `scripts/requirements.txt`/`rag/requirements.txt` — as transitivas
   (`pydantic`, `anyio`, `starlette`, `uvicorn`, `mcp_types` etc.) ficam a
   cargo da resolução do próprio pacote `mcp`, sem lockfile completo
   nesta etapa.

7. **Transporte: Streamable HTTP**, via `mcp.server.MCPServer` — classe
   que substitui `FastMCP` na major 2.x do SDK (`FastMCP` foi renomeada;
   importar `mcp.server.fastmcp` na 2.x levanta erro explícito apontando
   para o guia de migração). `mcp.run(transport="streamable-http", ...)`
   é o único ponto que decide transporte/porta — nenhuma lógica de
   protocolo (parsing de request, headers `Mcp-Method`/`Mcp-Name`,
   framing JSON-RPC) é escrita à mão neste projeto; toda ela vem do SDK.

8. **Etapa 6.1 entrega somente `ede_health`.** Nenhuma geração de
   Contestação, nenhum índice RAG carregado (`pyarrow`, `rank_bm25`,
   `sentence-transformers`, parquet, joblib ficam fora desta etapa),
   nenhum Modelo Oficial acessado, copiado, enviado a bucket ou embutido
   em imagem/fixture. `ede_health` distingue explicitamente
   `service_status` (o processo respondeu?) de `contestacao_status` (o
   pipeline determinístico da Contestação teria como rodar?) — nesta
   etapa `contestacao_status` é sempre `NOT_READY`, porque RAG e Modelo
   Oficial estão deliberadamente fora de escopo.

## Alternativas consideradas

* **Opção B** (execução das Skills dentro do servidor) — ver item 3
  acima. Rejeitada nesta fase; pode voltar a ser avaliada no futuro, mas
  como decisão própria e explícita, não como efeito colateral de uma
  etapa de infraestrutura.
* **Implementar o transporte HTTP manualmente** (parsing próprio de
  JSON-RPC/SSE) — rejeitada: o pedido da Etapa 6.1 veda expressamente
  criar abstração MCP própria ou reimplementar o protocolo, e o SDK
  oficial já resolve exatamente esse problema, com conformidade
  verificada contra a especificação vigente.
* **Adiar a definição de fronteira até a tool `ede_gerar_contestacao`
  existir** — rejeitada: a ambiguidade documentada em `gerar_
  contestacao.py` ("LIMITAÇÃO CONHECIDA") só cresce se não for resolvida
  antes de qualquer tool tocar a Contestação; melhor travar a decisão
  agora, com baixo custo de reversão, do que descobrir a inconsistência
  depois de várias tools já implementadas sobre uma premissa errada.

## Consequências

* O MCP Server pode evoluir tool a tool sem jamais precisar decidir
  estratégia jurídica — cada tool nova é avaliada contra a mesma
  pergunta: "isto é execução determinística (Core) ou raciocínio
  (Adapter/host)?".
* Gerar uma Contestação de ponta a ponta continuará exigindo os dois
  lados por desenho: o host Claude (Skills) para a etapa estratégica/
  redacional, e o MCP Server remoto (quando `ede_gerar_contestacao`
  existir) para a etapa determinística. Nenhum dos dois sozinho basta —
  isso não é uma limitação temporária desta etapa, é a arquitetura-alvo.
* Uma eventual peça processual futura (vedada por ora pela
  `INV-GATE-CONTESTACAO`, CLAUDE.md §27) precisaria repetir a mesma
  fronteira — Core determinístico no servidor, raciocínio no host — mas
  isso é decisão de expansão futura, não antecipada nem preparada por
  este ADR.
* Nenhuma dependência de RAG (`pyarrow`, `rank_bm25`, `sentence-
  transformers`) entra na imagem do servidor nesta etapa — mantém a
  primeira imagem pequena, conforme o objetivo explícito da Etapa 6.1.
