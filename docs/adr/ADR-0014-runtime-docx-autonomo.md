# ADR-0014 — Runtime DOCX autônomo, sem dependência do skill "docx" de terceiro

* **Status:** Aceito
* **Data:** 2026-09-10
* **Relacionado:** ADR-0006, ADR-0009 (modelo institucional externo),
  ADR-0012 (resolução de recursos do plugin); SPEC-0001; PEND-007;
  auditorias Etapa 5.9 (distribuição reprodutível) e Etapa 5.10 (runtime
  DOCX autônomo)

## Contexto

A auditoria da Etapa 5.9 confirmou, por reprodução empírica (clone limpo
real e execução direta na máquina do desenvolvedor fora do runtime do
Claude Code), que `scripts/docx_template_engine.py`,
`scripts/docx_context_engine.py`, `scripts/docx_block_engine.py` e
`scripts/validate_template.py` dependem em runtime de `unpack.py`/`pack.py`
do skill "docx" de terceiro (Anthropic, PBC), localizado por
`_localizar_docx_toolkit()`/`_importar_toolkit()` em `docx_template_engine.py`.

Essa dependência é inviável por dois motivos independentes, não só um
problema de empacotamento:

1. **Licença.** A cópia vendorizada em `skills/docx/` (gitignored, nunca
   commitada) está sob licença própria (`skills/docx/LICENSE.txt`) que
   proíbe expressamente extração, cópia, redistribuição e obras
   derivadas fora dos Services da Anthropic. Distribuir o EDE Legal
   Plugin com esse toolkit embutido violaria essa licença.
2. **Obsolescência de contrato.** A versão do skill "docx" atualmente
   publicada (confirmada na própria máquina do desenvolvedor, em
   `~/.claude/skills/docx` e `~/.agents/skills/docx`) não expõe mais
   `unpack.py`/`pack.py` — foi reescrita para um fluxo `unzip → editar →
   zip`. Mesmo um usuário com o skill "docx" legitimamente instalado não
   satisfaz o contrato que o EDE hoje espera.

Resultado prático: fora do checkout específico do desenvolvedor (com a
cópia gitignored presente e `CLAUDE_PLUGIN_ROOT` setado manualmente), a
geração do DOCX falha sempre — inclusive para o próprio desenvolvedor, em
qualquer execução fora desse ambiente específico.

## Decisão

1. **O EDE Legal Plugin deixa de depender, em runtime, do skill "docx" da
   Anthropic — ou de qualquer outro toolkit de terceiro para manipulação
   do pacote OOXML.** A capacidade de extrair e reempacotar `.docx` passa
   a ser implementação própria do EDE.
2. **Módulo próprio:** `scripts/docx_package.py`, construído exclusivamente
   sobre biblioteca padrão Python (`zipfile`, `pathlib`, `shutil`, `os`,
   `stat`) e `lxml` (já dependência direta do projeto), configurada para
   processamento seguro. Fundamentado em conhecimento público do formato
   ZIP e do OOXML/OPC (ECMA-376 / ISO-IEC 29500), nunca em código de
   terceiro.
3. **`skills/docx/` permanece inteiramente fora dos limites.** Nunca foi
   e não deve ser consultado, lido, copiado, adaptado ou traduzido em
   nenhuma etapa da implementação deste runtime — nem para referência de
   design. A verificação disso é parte do critério de aceite de cada
   commit desta migração.
4. **API própria do EDE**, não um espelho da API do toolkit substituído
   — sem o parâmetro `original_file`, por exemplo, porque a garantia
   "nada fora de `word/document.xml` mudou" já é 100% responsabilidade
   de `verificar_template_lock()` (código próprio, inalterado), que roda
   antes do reempacotamento. Reproduzir a assinatura antiga só para
   parecer compatível teria sido mimetismo artificial, não reuso real.
5. **O Template Lock não é enfraquecido.** `verificar_template_lock()`
   continua sendo a fonte de verdade de que só o conteúdo autorizado foi
   alterado; o runtime novo não assume esse papel e não o duplica.
6. **`templates/contestacao/modelo-oficial.docx` permanece asset
   institucional externo**, nos termos já decididos e encerrados em
   ADR-0009 — esta ADR não reabre essa decisão.
7. **Runtime novo é host-agnostic.** `docx_package.py` não importa nem
   depende de nada específico do Claude Code (`CLAUDE_PLUGIN_ROOT`,
   `SKILL.md`, `~/.claude`, `~/.agents`) nem de OpenAI SDK, Apps SDK ou
   MCP. Toda entrada é recebida como `Path` explícito pelo chamador —
   resolver "onde estão os arquivos" continua sendo responsabilidade da
   camada que invoca o módulo, não dele. Claude continua sendo a
   plataforma atual do EDE Legal Plugin; a camada de Skills (`SKILL.md`,
   orquestração) pode continuar usando `CLAUDE_PLUGIN_ROOT` onde já é
   legitimamente necessário (ADR-0012) — só o núcleo novo não introduz
   acoplamento adicional a essa plataforma.
8. **Direção futura, não implementada por esta ADR:** uma eventual
   separação formal em `EDE CORE` / `Claude Adapter` / `OpenAI-MCP
   Adapter` só será realizada após a homologação da versão Claude atual.
   Esta ADR não cria essa estrutura de diretórios nem qualquer
   abstração de adaptador — só garante que o runtime DOCX, ao nascer
   agora, não precise ser reescrito quando essa separação vier a
   acontecer.
9. **Migração faseada.** Esta ADR registra a decisão e a existência do
   módulo novo. A migração dos consumidores existentes
   (`docx_template_engine.py`, `docx_context_engine.py`,
   `docx_block_engine.py`, `validate_template.py`) do toolkit antigo
   para `docx_package.py` é trabalho subsequente, sob autorização
   própria — não decidida nem executada por este ADR.

## Alternativas consideradas

* **Manter a cópia vendorizada em `skills/docx/` e formalizar isso.**
  Rejeitada: viola a licença do skill de terceiro de forma irremediável;
  não é uma opção de engenharia.
* **Exigir que o usuário instale separadamente o skill "docx" e apontar
  para ele.** Rejeitada: a versão atualmente publicada não tem o
  contrato (`unpack.py`/`pack.py`) que o EDE precisa; construir uma
  integração contra um contrato que já não existe na distribuição atual
  não resolveria o problema, só adiaria a mesma falha.
* **Adotar uma biblioteca de terceiro completa de manipulação de Word
  (ex.: um pacote de modelo de objeto Word em Python).** Rejeitada nesta
  decisão: o EDE não precisa de um modelo de objeto Word completo — só
  de extração/reempacotamento cirúrgico de um pacote ZIP/OPC, com o
  conteúdo de `word/document.xml` manipulado pelos motores XML próprios
  já existentes (`docx_template_engine.py`, `docx_numeracao_engine.py`,
  `docx_block_engine.py`). Adicionar uma dependência pesada para uma
  necessidade estreita seria desproporcional.

## Consequências

* O pipeline de geração da Contestação deixa de depender de qualquer
  arquivo fora do que é versionado no próprio repositório do EDE Legal
  Plugin (além do `modelo-oficial.docx`, cuja externalidade é decisão
  separada e já aceita).
* O runtime DOCX passa a ser testável isoladamente, com pacotes ZIP
  sintéticos, sem precisar do template institucional real nem de
  qualquer instalação de terceiro.
* Nenhuma dependência Python nova é introduzida (`lxml` já era direta;
  ver decisão específica lxml × `defusedxml` registrada na
  implementação desta etapa).
* Perda deliberada de capacidade frente ao toolkit antigo: validação XSD
  completa contra os schemas ECMA-376/ISO-IEC 29500 (usada pelo
  `pack.py --validate` do toolkit substituído) dá lugar, nesta etapa, a
  uma validação estrutural mais leve (partes OPC obrigatórias presentes
  + boa-formação XML). Validação XSD completa própria do EDE, caso volte
  a ser considerada necessária, é uma decisão separada e futura — as
  normas ECMA-376/ISO-IEC 29500 são públicas, mas a aquisição de uma
  cópia própria dos schemas (independente da cópia vendorizada da
  Anthropic) tem sua própria checagem de licença, não resolvida aqui.
* A migração dos consumidores (Commits 3 em diante da Etapa 5.10) passa
  a ser um trabalho de substituição isolado e reversível — o pipeline
  atual continua funcionando com o toolkit antigo até que cada
  consumidor seja migrado e validado individualmente contra o Template
  Lock.
