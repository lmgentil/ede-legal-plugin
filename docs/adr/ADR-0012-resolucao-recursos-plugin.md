# ADR-0012 — Resolução dos recursos pertencentes ao plugin

* **Status:** Aceito
* **Data:** 2026-08-27
* **Relacionado:** SPEC-0001 §61; Etapa 5.9-B

## Contexto

A Skill `contestacao` precisa acessar scripts, RAG, catálogos e o template
instalado sem depender do diretório de trabalho do advogado. A primeira
correção usou `$CLAUDE_PLUGIN_ROOT` no shell e `os.environ` no Python. Essa
solução supunha que o host exportaria a variável para todo subprocesso, o que
não foi confirmado na execução real. Os testes protegiam a forma textual da
solução, mas não o comportamento do subprocesso fora do checkout.

O contrato de plugins do Claude Code define `${CLAUDE_PLUGIN_ROOT}` como token
substituído inline no conteúdo das Skills. A exportação como variável de
ambiente é contrato separado para hooks e servidores MCP/LSP.

## Decisão

Usar `${CLAUDE_PLUGIN_ROOT}` exclusivamente como expansão inline do host:

- comandos recebem caminhos absolutos já expandidos e entre aspas;
- snippets Python recebem o valor expandido diretamente e o convertem em
  `pathlib.Path`, sem consultar o ambiente;
- o root é validado por sentinelas do pacote antes do primeiro uso;
- não existe fallback por `cwd`, diretório pai, cache ou caminho de máquina;
- arquivos do caso permanecem relativos ao workspace do advogado.

## Alternativas consideradas

- **Manter a variável de ambiente do subprocesso:** rejeitada porque foi a
  causa da falha observada e não corresponde ao contrato aplicável à Skill.
- **Procurar o plugin em caches conhecidos:** rejeitada por acoplar a Skill à
  implementação e ao layout de instalação de cada host.
- **Adicionar wrappers em `bin/`:** possível, mas rejeitada nesta correção por
  ampliar empacotamento e superfície multiplataforma sem necessidade.
- **Voltar a caminhos relativos ao `cwd`:** rejeitada porque mistura recursos
  do plugin com arquivos do caso e só funciona dentro do checkout.

## Consequências

- A Contestação pode ser executada com o workspace do caso como `cwd`.
- Caminhos de instalação com espaços permanecem válidos.
- Falha de expansão do host aparece antes do pipeline documental.
- A correção depende do contrato de expansão de Skills do host, não do
  ambiente herdado por Bash/Python.
- Compatibilidade plena com Cowork continua sujeita a homologação E2E; esta
  decisão não a declara por inferência.
