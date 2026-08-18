---
name: atualizar-ede
description: >
  Orienta e valida a atualização do EDE Legal Plugin — a experiência
  equivalente a "/updateEde" (SPEC-0001 REQ-037). Use quando o usuário
  digitar "/updateEde", pedir para "atualizar o plugin EDE", "verificar se
  há versão nova do EDE Legal Plugin", ou perguntar "qual versão do EDE eu
  tenho". Não existe mecanismo do Claude Code para um plugin atualizar a
  si mesmo programaticamente — esta Skill nunca finge o contrário: ela
  identifica a versão atual, explica e conduz o advogado pelos comandos
  oficiais (`/plugin marketplace update`, `/plugin update`), e valida o
  resultado com `scripts/validar_instalacao.py` depois que a atualização
  oficial for aplicada.
allowed-tools:
  - Read
  - Bash
---

# Atualizar EDE Legal Plugin — fachada segura sobre o mecanismo oficial

## 1. O que esta Skill é e o que ela não é

Você **orienta e valida** a atualização — você não a executa por conta
própria. Não existe, hoje, API do Claude Code para um plugin instalado
disparar sua própria atualização de dentro de uma Skill (confirmado na
documentação oficial vigente, Fase 8). Fingir automação aqui seria pior
que não ter o comando: o advogado sairia achando que atualizou quando não
atualizou. Prefira sempre o comportamento correto — orientar — a uma
automação falsa (SPEC-0001 Fase 8 §29).

## 2. Passo 1 — identificar a versão atual

```bash
python scripts/validar_instalacao.py
```

Ou leia diretamente `VERSION` (ou `.claude-plugin/plugin.json`, campo
`version` — os dois devem estar sincronizados; se não estiverem, avise o
usuário disso já nesta etapa, é sinal de instalação inconsistente).

## 3. Passo 2 — explicar e conduzir a atualização oficial

O mecanismo oficial de atualização de plugins no Claude Code é:

```bash
/plugin marketplace update ede      # atualiza os METADADOS do marketplace
/plugin update ede-legal-plugin@ede # atualiza o PLUGIN instalado
```

**Achado confirmado em teste real (Fase 8):** `/plugin update` usa escopo
`user` por padrão. Se o plugin foi instalado com `--scope local` (ou
`project`), o update **falha silenciosamente com "not installed at scope
user"** a menos que o mesmo escopo seja passado explicitamente:
`/plugin update ede-legal-plugin@ede --scope local`. Se o usuário não
souber o escopo usado na instalação, rode `/plugin list` primeiro — o
escopo aparece ao lado da versão.

Diferença importante a explicar ao usuário, se perguntado: atualizar o
*marketplace* só atualiza o que o Claude Code sabe sobre versões
disponíveis; atualizar o *plugin* de fato baixa/aplica a nova versão. Os
dois passos são normalmente necessários, nessa ordem.

O Claude Code também verifica e atualiza plugins automaticamente em
segundo plano após o início da sessão (com atraso aleatório) — se isso já
tiver acontecido, o Claude Code avisa para rodar `/reload-plugins`. Se o
usuário perguntar por que a versão já mudou sem ele ter feito nada, essa é
a explicação provável.

**Depois de rodar os comandos acima, é necessário recarregar/reiniciar a
sessão do Claude Code para a nova versão ser efetivamente carregada** —
diga isso explicitamente; não deixe o usuário achar que terminou sem
reiniciar.

## 4. Passo 3 — validar após a atualização

Depois que o usuário confirmar que reiniciou/recarregou:

```bash
python scripts/validar_instalacao.py --json
```

Leia o campo `status`:

- **`"OK"`** — informe a nova versão (`versao`) e aponte a seção
  correspondente do `CHANGELOG.md` (procure o cabeçalho `## [<versao>]`).
- **`"UPDATE_FAILED"`** — **nunca afirme que a atualização terminou
  corretamente** (SPEC-0001 Fase 8 §35, Fail Closed). Liste os itens em
  `obrigatorias_falhando` para o usuário e sugira reinstalar
  (`/plugin uninstall ede-legal-plugin@ede` seguido de
  `/plugin install ede-legal-plugin@ede`) se o problema persistir.

## 5. Limitações a comunicar quando perguntado

- **Rollback:** não há comando oficial confirmado de "instalar versão
  anterior" de um plugin — se o usuário precisar reverter, a via é
  reinstalar apontando para uma tag/commit anterior do repositório fonte
  (`/plugin marketplace add <origem>@<tag-ou-commit>`, quando o
  marketplace for git), não algo automatizado por esta Skill.
- **Configurações locais:** a atualização do plugin não deve, pelo próprio
  mecanismo oficial, sobrescrever `.env`, workspace de documentos ou
  saídas locais do advogado — esses diretórios nunca fazem parte do
  pacote versionado (ver `.gitignore`, CLAUDE.md §19).
- **Template institucional:** `templates/contestacao/modelo-oficial.docx`
  é asset privado do escritório (ADR-0006), não distribuído pelo plugin
  público — uma atualização nunca o toca, e sua ausência não é falha de
  atualização (ver `scripts/validar_instalacao.py`, item opcional).
