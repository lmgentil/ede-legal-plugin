---
name: atualizar-ede
description: >
  Verificador de versão do EDE Legal Plugin — a experiência equivalente a
  "/updateEde" (SPEC-0001 REQ-037/REQ-039, revisado na Etapa 5.9-I e nos
  dois Gates seguintes). Use quando o usuário digitar "/updateEde", pedir
  para "verificar se há versão nova do EDE Legal Plugin", "checar
  atualização do EDE", ou perguntar "qual versão do EDE eu tenho". Esta
  Skill NÃO atualiza, instala, sincroniza, reinstala nem modifica arquivo
  algum do plugin, e não baixa nem verifica pacote algum — ela só
  identifica a versão instalada, consulta a última versão OFICIALMENTE
  PUBLICADA (a última GitHub Release não-draft/não-prerelease, nunca o
  estado de desenvolvimento em `main`), compara as duas e informa o
  resultado, apontando a Release correspondente quando houver versão
  mais nova.
allowed-tools:
  - WebFetch
---

# Verificador de versão do EDE Legal Plugin

## 1. Escopo único — VERIFICADOR, não atualizador

Decisão definitiva da Etapa 5.9-I (substitui o comportamento anterior desta
Skill, que orientava e validava a atualização): esta Skill **só verifica
versão**. Fluxo fixo, sempre nesta ordem:

```text
VERSÃO INSTALADA → VERSÃO OFICIAL PUBLICADA → COMPARAR → INFORMAR STATUS
```

Esta Skill nunca:

- atualiza, instala ou reinstala o EDE;
- sincroniza o marketplace;
- executa ou menciona `/plugin update`, `/plugin marketplace update`,
  `/plugin install` ou qualquer outro comando `/plugin`;
- faz `git pull` ou qualquer operação Git;
- modifica, baixa ou reconstrói arquivo algum do plugin;
- identifica ou pergunta escopo (`user`/`project`/`local`) de instalação;
- usa `$CLAUDE_PLUGIN_ROOT`, `os.environ`, Bash ou Python em tempo de
  execução (o `allowed-tools` acima é só `WebFetch`, de propósito);
- apaga cache;
- consulta o marketplace local como fonte de verdade;
- confia no status `loaded`/`updated`/`synced` do Cowork para concluir que
  o plugin está atualizado (achado real: o Cowork pode carregar uma versão
  antiga sem alertar o usuário — ver §9);
- tenta se autoatualizar;
- baixa arquivo algum, instala pacote algum, nem verifica a existência de
  asset `.zip` ou de qualquer outro artefato de instalação — **essa
  exigência foi avaliada e revogada** (Gate Final da Etapa 5.9-I): uma
  Release oficialmente publicada, com tag SemVer válida, já representa
  versão disponível por si só; o mecanismo/pacote de instalação não é
  responsabilidade desta Skill;
- decide ou prescreve o mecanismo de instalação (não diz qual arquivo
  baixar, nem como instalar) — só aponta a Release correspondente; só
  entra em mecanismo de instalação se o próprio advogado perguntar,
  fora do fluxo de verificação;
- diferencia o fluxo de verificação entre Claude Code e Cowork (§8);
- tenta corrigir uma instalação;
- compara a versão instalada contra `main` do repositório (branch de
  desenvolvimento — ver §3, distinção obrigatória entre versão de
  desenvolvimento e versão oficialmente publicada).

## 2. Versão instalada

**Versão instalada neste pacote: `0.10.1`**

Este valor é a versão instalada — não é lido de `VERSION`, de
`.claude-plugin/plugin.json`, nem de variável de ambiente em tempo de
execução. Mecanismo deliberado (auditoria da plataforma, Etapa 5.9-I): o
próprio conteúdo desta Skill só chega ao advogado dentro do pacote
instalado — se este arquivo foi carregado, o valor acima **é** a versão
instalada, sem precisar de `$CLAUDE_PLUGIN_ROOT`, `os.environ`, Bash, nem
resolução de caminho nenhuma. Isso funciona identicamente em Claude Code e
em Cowork, porque não depende de nenhuma camada de execução — só do
próprio pacote ter sido carregado.

Contrapartida: este valor precisa ser mantido em sincronia com `VERSION` e
`.claude-plugin/plugin.json` a cada release — **obrigação de processo de
release, não opcional** — `tests/test_atualizar_ede_skill.py` verifica
essa sincronia automaticamente (fail se os três divergirem), para que o
esquecimento vire teste vermelho, nunca versão errada relatada em
silêncio.

Se este trecho estiver ausente, ilegível, ou o valor não parecer um SemVer
válido (`MAJOR.MINOR.PATCH`), responda apenas:

> Não foi possível identificar com segurança a versão instalada do EDE.

e **PARE** — não invente, não estime, não assuma a partir de outro dado.

## 3. Versão oficialmente publicada — nunca `main`, sempre a última Release válida

**Distinção obrigatória (mantida desde a Etapa 5.9-I):**

- **VERSÃO DE DESENVOLVIMENTO** = estado atual de `main`/`VERSION` no
  repositório. Pode estar à frente de qualquer versão realmente publicada
  — nunca é o que esta Skill anuncia ao advogado, nem entra em
  comparação alguma.
- **VERSÃO OFICIALMENTE PUBLICADA** = a versão (`tag_name`) da última
  GitHub Release válida (§3.1) — é a única fonte de verdade desta Skill.

**Revogado no Gate Final:** a versão anterior desta seção também exigia
um asset `.zip` anexado à Release para considerá-la "distribuível". Essa
exigência foi avaliada e **revogada** — ZIP oficial não faz parte da
arquitetura desta Skill. Uma Release publicada com tag SemVer válida já
é, por si só, versão oficial suficiente para a comparação; esta Skill não
verifica, exige nem menciona asset de instalação algum.

Consulte, via `WebFetch`, exclusivamente a API de Releases do GitHub —
**nunca** `raw.githubusercontent.com/.../main/VERSION` nem qualquer
conteúdo de branch:

```text
https://api.github.com/repos/lmgentil/ede-legal-plugin/releases/latest
```

### 3.1. O que conta como Release válida

Da resposta JSON, use:

- `tag_name` — remova um `v` inicial se houver (ex.: `v0.10.1` → `0.10.1`)
  e valide como SemVer (`MAJOR.MINOR.PATCH`). Esta é a **versão
  oficialmente publicada**.
- `html_url` — é o link a informar ao advogado quando houver atualização
  (§7). Vem da **mesma resposta JSON** usada para ler `tag_name`, então
  aponta sempre para a mesma Release comparada — nunca reconstrua ou
  monte essa URL manualmente (ex.: nunca `.../releases/latest` como link
  final: esse endereço é um redirecionamento que pode mudar entre a
  consulta e o clique do advogado; use o `html_url` literal já resolvido
  na resposta).

`GET .../releases/latest` já é, pelo próprio contrato da API do GitHub, a
última release **não-draft e não-prerelease** — usar exatamente este
endpoint (nunca listar `/releases` e pegar o primeiro item manualmente)
já resolve a exclusão de rascunho/pré-lançamento na origem. Mesmo assim,
como checagem defensiva (a resposta é dado externo, nunca confiar
cegamente): se o objeto retornado trouxer `draft: true` ou
`prerelease: true`, trate como se não houvesse Release válida — mesma
resposta do §3.2, nunca anuncie essa versão.

Nenhuma lógica desta Skill verifica, exige ou menciona `assets`, pacote
`.zip`, "Source code (zip)" ou qualquer artefato de instalação — a tag
SemVer válida da Release é suficiente.

### 3.2. Nenhuma Release oficial publicada

Se `GET /repos/lmgentil/ede-legal-plugin/releases/latest` responder 404,
isso significa que não há Release oficial válida disponível para
comparação naquele momento. Trate a resposta como estado esperado, não
como falha de rede, e use exatamente esta mensagem — nunca a de "erro"
genérica do §3.3, que é para falha de consulta, não para ausência de
Release:

> Não há versão oficial publicada disponível para comparação neste
> momento.

e **PARE**. Nunca compare contra `main/VERSION` como substituto, nunca
diga que o EDE está desatualizado, nunca invente versão publicada.

### 3.3. GitHub indisponível ou resposta inválida

Se a API não responder, responder com erro diferente de 404, ou o corpo
não for o JSON esperado (sem `tag_name`, `tag_name` que não valida como
SemVer após remover o `v`):

> Não foi possível verificar a versão do EDE neste momento. Tente
> novamente mais tarde.

e **PARE**. Nunca presuma que a versão instalada é a mais recente só
porque a consulta falhou — fail-closed.

## 4. Comparação — SemVer numérico, nunca string

Compare `VERSÃO_INSTALADA` × `VERSÃO_PUBLICADA` componente a componente
(major, minor, patch) como números inteiros — **nunca** como comparação
lexicográfica de string. Exemplo do motivo: como string, `"0.10.10"` vem
antes de `"0.10.9"`; como versão, `0.10.10` é MAIOR que `0.10.9`.
`scripts/comparar_versao.py` (`comparar_semver`) implementa essa lógica e
é coberto por `tests/test_comparar_versao.py` — é um **utilitário
testado, não é dependência operacional desta Skill nem é invocado em
tempo de execução por ela** (o `allowed-tools` acima é só `WebFetch`, sem
Bash/Python): sua função é dar ao algoritmo descrito aqui (comparação de
três inteiros, major primeiro) uma guarda de regressão automatizada, já
que a prosa por si só não pode provar que a lógica está correta no caso
`0.10.10` × `0.10.9`. Ao executar esta Skill, aplique a mesma regra
diretamente por raciocínio (nunca comparação de string).

## 5. Resultado — atualizado

Se `VERSÃO_INSTALADA == VERSÃO_PUBLICADA`:

> EDE Legal Plugin está atualizado.
>
> Versão instalada: X
> Versão mais recente: X
>
> Nenhuma ação necessária.

## 6. Resultado — atualização disponível

Se `VERSÃO_PUBLICADA` for maior (SemVer, §4) que `VERSÃO_INSTALADA`:

> Há uma nova versão do EDE Legal Plugin disponível.
>
> Versão instalada: X
> Versão mais recente: Y
>
> Consulte a versão mais recente:
> <html_url da mesma resposta usada para ler a versão — nunca link fixo>

e **PARE**. Não mencione ZIP, asset, pacote de instalação ou qualquer
mecanismo de instalação nesta resposta — só entre nesse assunto se o
próprio advogado perguntar depois, fora deste fluxo. Não execute nenhuma
atualização automaticamente — só informe e aponte a Release. A versão
anunciada (Y) e o link informado são sempre a mesma Release, por
construção (mesma resposta JSON, §3) — nunca versões diferentes.

## 7. Resultado — versão instalada maior que a publicada

Se `VERSÃO_INSTALADA` for maior (SemVer, §4) que `VERSÃO_PUBLICADA`,
**nunca trate isso como downgrade a sugerir nem como "atualizado"**: é
uma inconsistência a reportar, sem inventar causa.

> A versão instalada do EDE é superior à última versão oficial publicada.
>
> Instalada: X
> Última versão publicada: Y.
>
> Nenhuma atualização é recomendada.

## 8. Claude Code e Cowork — mesmo contrato

A lógica e a resposta são idênticas nos dois ambientes: versão instalada
→ versão oficialmente publicada → comparar → informar status — nunca
duplique o fluxo de verificação por ambiente, e não diferencie a
resposta final entre Claude Code e Cowork (nenhuma das duas menciona
mecanismo de instalação, por §6/§1).

## 9. Marketplace nunca é fonte de verdade

O status do marketplace (`loaded`, `updated`, `synced` no Cowork, ou
equivalente no Claude Code) nunca é usado para decidir se o EDE está
atualizado — só a última Release oficialmente publicada no GitHub (§3).
Não consulte, não mencione, não infira a partir de comandos de
marketplace.

## 10. O que nunca expor

Fora de modo diagnóstico explicitamente solicitado pelo advogado, a
resposta não expõe: cache, scope de instalação, `CLAUDE_PLUGIN_ROOT`,
commit SHA, detalhes de marketplace, asset/pacote de instalação, ou
qualquer comando técnico (`/plugin ...`, `git ...`).
