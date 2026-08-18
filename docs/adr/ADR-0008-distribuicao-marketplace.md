# ADR-0008 — Distribuição via Claude Code Plugin Marketplace

## Status

Aceito (2026-08-18) — Fase 8. Publicação externa (push para GitHub,
visibilidade pública, release) **não autorizada por esta ADR** — só a
arquitetura técnica de distribuição.

## Contexto

SPEC-0001 REQ-036/037/038 preveem um comando/mecanismo equivalente a
`/contestacao`, `/updateEde` e `/atualizar-rag`. A Fase 1 já havia
decidido (CHANGELOG `[0.1.0]`) que esses fluxos seriam implementados como
Skills invocáveis, não como `commands/*.md` — decisão preservada aqui, não
revista.

A Fase 8 precisa, além disso, definir *como o plugin chega até o
computador de outro advogado* — REQ-039 (identificar versão local/
disponível, comparar, atualizar só se necessário, preservar configuração
local, validar pós-atualização) e os objetivos gerais de distribuição do
CLAUDE.md §25.

Consultada a documentação oficial vigente do Claude Code (não memória
antiga nem exemplos de terceiros — Fase 8 §61), confirmado que:

* o mecanismo de distribuição oficial é o **Plugin Marketplace**
  (`.claude-plugin/marketplace.json`);
* quando marketplace e plugin vivem no mesmo repositório, o `source` de
  um plugin pode apontar para a raiz (`"./"`) sem duplicar a árvore em
  `plugins/<nome>/`;
* instalação: `/plugin marketplace add <origem>` seguido de
  `/plugin install <plugin>@<marketplace>`;
* atualização: `/plugin marketplace update <marketplace>` +
  `/plugin update <plugin>@<marketplace>` — **sempre disparada pelo
  usuário ou pelo processo de atualização automática em segundo plano do
  próprio Claude Code; não existe API para um plugin atualizar a si
  mesmo programaticamente**;
* `claude plugin validate .` valida o manifesto do marketplace quando
  `marketplace.json` está presente no diretório apontado; para validar
  só o plugin, aponte para `.claude-plugin/plugin.json` diretamente;
* `claude plugin tag . --dry-run` é o mecanismo oficial que confere se
  `plugin.json` e a entrada correspondente no marketplace concordam —
  usado aqui como checagem de sincronização de versão, complementar ao
  teste automatizado do repositório (`tests/test_marketplace.py`).

## Decisão

1. **Marketplace e plugin no mesmo repositório**, sem duplicação física:
   `.claude-plugin/marketplace.json` na raiz, com um único plugin
   (`ede-legal-plugin`) cujo `source` é `"./"`.
2. **Nome do marketplace:** `ede`. **Nome do plugin:** `ede-legal-plugin`
   — identidade já consolidada em `plugin.json` desde a Fase 1, não
   renomeada.
3. **Versão — fonte única:** `VERSION` (arquivo canônico, humano) →
   sincronizado manualmente em `.claude-plugin/plugin.json`. A entrada do
   plugin em `marketplace.json` **não declara `version` própria**
   (achado desta fase: se declarasse, o valor de `plugin.json` venceria
   silenciosamente, sem aviso — risco de configuração enganosa evitado
   por simplesmente não duplicar o campo). `tests/test_marketplace.py`
   e `claude plugin tag . --dry-run` são as duas checagens de
   sincronização — uma no repositório, outra no CLI oficial.
4. **`/updateEde` = Skill `atualizar-ede`**, fachada sobre o mecanismo
   oficial: identifica versão, explica e conduz os comandos oficiais,
   valida o resultado com `scripts/validar_instalacao.py`. **Não
   implementa self-update** — não existe mecanismo oficial para isso, e
   fingir um seria pior que não ter o comando (Fail Closed, CLAUDE.md
   §17).
5. **`/atualizar-rag` (REQ-038)** permanece fora do escopo desta fase —
   não foi solicitado nem implementado aqui; o RAG atual não tem fonte de
   atualização automática de corpus (é migrado, versionado estaticamente).
   Registrado como trabalho futuro, não uma decisão tomada.

## Alternativas consideradas

- **Instalação via `git clone` manual.** Rejeitada: contraria
  explicitamente CLAUDE.md §25 ("o advogado usuário do plugin não deverá
  precisar conhecer Git") e o objetivo da Fase 8 de não exigir
  `git clone`/`git pull` do usuário final.
- **`plugins/ede-legal-plugin/` como subdiretório dedicado**, duplicando
  a árvore do projeto dentro de si mesma. Rejeitada: layout mais invasivo
  sem necessidade — o schema oficial já suporta `source: "./"` para
  marketplace e plugin coincidentes.
- **`/updateEde` reimplementando um `git pull` próprio sobre o cache
  interno do plugin.** Rejeitada explicitamente (Fase 8 §27): conflitaria
  com o mecanismo oficial e arrisca corromper o estado que o Claude Code
  gerencia.

## Consequências

- Instalar/atualizar o EDE Legal Plugin passa a ser possível sem Git, via
  `/plugin marketplace add` + `/plugin install`/`/plugin update` — mas
  **isso só funciona de fato depois que o repositório tiver uma origem
  git acessível** (hoje não há remote configurado; ver `git remote -v`,
  vazio). Testável localmente (`/plugin marketplace add <caminho-local>`)
  desde já.
- `/updateEde` orienta e valida — nunca afirma sucesso de atualização sem
  checagem real (`scripts/validar_instalacao.py`).
- **Tensão não resolvida por esta ADR:** o objetivo de distribuição
  pública (instalável por outros advogados) pressupõe que o repositório
  seja publicamente clonável/instalável, mas a `LICENSE` atual do
  repositório reserva todos os direitos e não concede permissão de
  "copiar, modificar, distribuir... sem autorização prévia e expressa por
  escrito do titular". Instalar via marketplace implica copiar arquivos
  para a máquina do advogado — isso só é legítimo se a própria
  disponibilização no marketplace for entendida como essa autorização, o
  que **não foi decidido aqui**. Ver `docs/PENDENCIAS.md` (`PEND-004`).
- `templates/contestacao/modelo-oficial.docx` continua fora do pacote
  distribuído (gitignored) — a decisão de fundo sobre torná-lo público,
  privado-separado, ou baixado de origem autenticada **permanece em
  aberto** (ADR-0006, seção "Atualização — Fase 8" abaixo/nela mesma;
  não decidida por esta ADR).
