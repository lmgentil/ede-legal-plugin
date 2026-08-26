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
documentação oficial vigente, Fase 8, ADR-0008). Fingir automação aqui
seria pior que não ter o comando: o advogado sairia achando que atualizou
quando não atualizou. Prefira sempre o comportamento correto — orientar —
a uma automação falsa (SPEC-0001 Fase 8 §29). Esta decisão está encerrada
(ADR-0008) — não reabra a discussão nem tente disparar `/plugin
marketplace update`/`/plugin update` programaticamente (não são binários
de shell, são comandos nativos do Claude Code; nenhuma ferramenta desta
Skill os invoca por conta própria).

Todo caminho de arquivo usado por esta Skill é resolvido a partir de
`$CLAUDE_PLUGIN_ROOT` — a variável de ambiente que o Claude Code expõe
para um plugin localizar a própria instalação (mesmo padrão já usado em
`scripts/docx_template_engine.py`). Nunca use caminho relativo
(`scripts/validar_instalacao.py`, `VERSION`) nem o `cwd` corrente: o
diretório de trabalho do advogado é a pasta do caso, não a instalação do
plugin — um caminho relativo resolve contra o `cwd` e falha
("arquivo não encontrado") fora do checkout do próprio plugin.

## 2. Passo 0 — gate de ambiente (obrigatório, antes de qualquer outra ação)

Antes de identificar versão, comparar, ou orientar qualquer comando,
verifique se `CLAUDE_PLUGIN_ROOT` está disponível, por exemplo:

```bash
echo "$CLAUDE_PLUGIN_ROOT"
```

- **Ausente ou vazia** (Claude.ai, web, ou qualquer ambiente sem esta
  instalação local do plugin) → responda **somente**:

  > A atualização do EDE deve ser executada no Claude Code onde o plugin
  > está instalado.

  E **PARE**. Não tente localizar `VERSION`, `plugin.json` ou
  `validar_instalacao.py` por caminho alternativo, não use o `cwd`
  corrente como substituto, não tente rodar em sandbox/web como fallback
  — nenhum destes é equivalente válido (fail-closed, CLAUDE.md §17).
- **Presente** → prossiga para o Passo 1, sempre com `$CLAUDE_PLUGIN_ROOT`
  como raiz de qualquer caminho usado por esta Skill a partir daqui.

## 3. Passo 1 — identificar a versão atual

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/validar_instalacao.py"
```

Ou leia diretamente `$CLAUDE_PLUGIN_ROOT/VERSION` e
`$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json` (campo `version`) — os
dois devem estar sincronizados. **Guarde este valor** (versão anterior):
ele é necessário no Passo 4 para informar se algo mudou.

**Se `VERSION` e `plugin.json` divergirem** → FAIL-CLOSED: informe ao
advogado que a instalação está inconsistente (cite os dois valores lidos)
e **não** avance para orientar nenhuma atualização até isso ser resolvido
— sinal de instalação corrompida, não algo que a atualização normal
corrige.

## 4. Passo 2 — escopo (a partir de `/plugin list`, nunca "user" por hábito)

`/plugin list` não pode ser executado programaticamente por esta Skill —
é um comando nativo do Claude Code, não um binário de shell. Peça ao
advogado para rodá-lo e colar a saída aqui.

A partir do texto colado, identifique **você mesmo**, sem pedir ao
advogado para interpretar a coluna:

- a linha correspondente a `ede-legal-plugin`;
- a versão instalada reportada ali (cheque contra o Passo 1);
- o marketplace associado — espera-se `@ede` (ADR-0008); se vier
  diferente, sinalize e não prossiga, é sinal de instalação fora do
  padrão desta Skill;
- o escopo (`user`, `project` ou `local`) reportado na mesma linha.

**Nunca assuma `scope=user` por padrão.** Se a saída colada não deixar o
escopo inequívoco, pergunte objetivamente ao advogado qual escopo foi
usado na instalação — nunca escolha um sozinho, e nunca prossiga sem essa
confirmação.

## 5. Passo 3 — explicar e conduzir a atualização oficial

O mecanismo oficial de atualização de plugins no Claude Code é:

```bash
/plugin marketplace update ede
/plugin update ede-legal-plugin@ede --scope <SCOPE_DETECTADO>
```

Substitua `<SCOPE_DETECTADO>` pelo escopo identificado no Passo 2 — nunca
"user" por padrão, nunca um escopo diferente do detectado. **Achado
confirmado em teste real (Fase 8):** `/plugin update` usa escopo `user`
por padrão quando `--scope` é omitido; se o plugin foi instalado com
`--scope local` ou `--scope project`, omitir `--scope` faz o update
**falhar silenciosamente com "not installed at scope user"**.

Se o escopo detectado não puder ser confirmado, não crie uma segunda
instalação "para simplificar" nem sugira desinstalar/reinstalar como
atalho — pare e peça a confirmação do Passo 2.

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

## 6. Passo 4 — validar após a atualização

Depois que o usuário confirmar que reiniciou/recarregou:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/validar_instalacao.py" --json
```

Compare o campo `versao` deste resultado com a versão guardada no Passo 1
e responda exatamente num dos três formatos abaixo:

- **`status == "OK"` e a versão mudou:**

  > EDE Legal Plugin atualizado com sucesso.
  > Versão anterior: X
  > Versão atual: Y
  > Instalação: OK

  Aponte também a seção correspondente do `CHANGELOG.md` (cabeçalho
  `## [<versao>]`).

- **`status == "OK"` e a versão é a mesma do Passo 1:**

  > EDE Legal Plugin já estava atualizado.
  > Versão atual: X
  > Instalação: OK

- **`status == "UPDATE_FAILED"`** — **nunca afirme que a atualização
  terminou corretamente** (SPEC-0001 Fase 8 §35, Fail Closed):

  > Atualização não concluída.
  > Motivo: <causa objetiva, a partir de `obrigatorias_falhando`>

  Sugira reinstalar (`/plugin uninstall ede-legal-plugin@ede` seguido de
  `/plugin install ede-legal-plugin@ede`) se o problema persistir.

## 7. Limitações a comunicar quando perguntado

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
