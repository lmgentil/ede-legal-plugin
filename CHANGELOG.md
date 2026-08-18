# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e
este projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Bloqueado
- Fase 3 (Template Engine) aguarda o `.docx` institucional real
  (`templates/contestacao/modelo-oficial.docx`), ainda não fornecido.

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
