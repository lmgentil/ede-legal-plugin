# Distribuição e instalação reprodutível — EDE Legal Plugin

Documento técnico da Etapa 5.10 (Commits 1–8, ADR-0014). Descreve o
procedimento **real e homologado** de instalação/distribuição do EDE —
tudo aqui foi efetivamente comprovado por `scripts/homologar_distribuicao.py`
contra um clone Git limpo (não é procedimento hipotético). Complementa
`README.md` (visão geral, instalação do plugin em si) e não duplica as
decisões já registradas em `ADR-0009` (Modelo Oficial externo) e
`ADR-0014` (runtime DOCX autônomo).

## 1. Visão geral

```text
obter o plugin
   ↓
instalar dependências Python
   ↓
obter o Modelo Oficial (canal externo, fora do plugin)
   ↓
python scripts/instalar_modelo_oficial.py CAMINHO_DO_MODELO
   ↓
python scripts/ede_doctor.py
   ↓
READY TO GENERATE? → sim → gerar a Contestação
                   → não → corrigir o item indicado e repetir o doctor
```

Nenhuma etapa depende de `skills/docx/`, de rede além do DataJud (só em
produção, nunca na instalação), de OpenAI ou de MCP.

## 2. Instalar dependências Python

```bash
pip install -r scripts/requirements.txt
pip install -r rag/requirements.txt
```

`scripts/requirements.txt` cobre o runtime DOCX (`lxml`); `rag/requirements.txt`
cobre a busca híbrida (`joblib`, `numpy`, `pandas`, `pyarrow`, `scikit-learn`,
`scipy`, `rank_bm25`, `pyyaml`) — `sentence-transformers`/`huggingface_hub`
nesse arquivo são explicitamente opcionais (fallback TF-IDF+LSA local sem
elas). `python scripts/ede_doctor.py` confirma o que está de fato instalado.

## 3. Modelo Oficial — asset institucional externo

`templates/contestacao/modelo-oficial.docx` **não faz parte do Git** e
nunca fará (decisão encerrada — `ADR-0009`). Decorre disso:

- não deve ser baixado de nenhuma fonte pública não autorizada — só do
  canal institucional do próprio escritório;
- o plugin nunca busca, baixa ou reconstrói esse arquivo sozinho;
- a instalação local só é feita por `scripts/instalar_modelo_oficial.py`,
  nunca por cópia manual direta para `templates/contestacao/`.

### 3.1. Instalar

```bash
python scripts/instalar_modelo_oficial.py CAMINHO_DO_ARQUIVO.docx
python scripts/instalar_modelo_oficial.py CAMINHO_DO_ARQUIVO.docx --json
```

Opções adicionais (raramente necessárias — os padrões já apontam para os
caminhos corretos do próprio repositório): `--destino`, `--schema`,
`--catalogo`.

Fluxo interno, sempre nesta ordem, fail-closed em cada etapa:

1. confirma que a origem existe e tem extensão `.docx`;
2. abre como pacote OOXML (`docx_package.py` — nunca `skills/docx/`);
3. valida a estrutura mínima do pacote (`[Content_Types].xml`,
   `_rels/.rels`, `word/document.xml`, XML bem-formado);
4. valida o **contrato institucional**: os placeholders físicos do
   documento batem com `schema.json`, os SDTs de bloco/zona batem com
   `blocos.json` — reaproveita a mesma validação já usada na geração
   real, nenhuma checagem nova;
5. só então copia para `templates/contestacao/modelo-oficial.docx`, de
   forma **atômica** (arquivo temporário no mesmo diretório + rename) —
   um modelo válido já instalado nunca é substituído por um arquivo que
   ainda não passou pelas etapas 1–4.

### 3.2. `MODELO_INSTITUCIONAL_DESATUALIZADO`

Se o arquivo fornecido é um `.docx` válido, mas **não bate com o
contrato atual** (placeholder faltando/inesperado, SDT de bloco/zona
faltando, versão do template desatualizada em relação a `schema.json`/
`blocos.json`), a instalação é **rejeitada** — nada é copiado — e a
saída reporta `"status": "REJEITADO"`, `"motivo":
"MODELO_INSTITUCIONAL_DESATUALIZADO"`, com a lista exata de divergências
(placeholders/SDTs específicos). Não é um erro genérico: significa que o
arquivo fornecido é de uma versão do template incompatível com esta
instalação do plugin — peça a versão atualizada ao escritório, não tente
editar o `.docx` manualmente para "passar" na validação.

### 3.3. Hash — auditoria, não gate

Após uma instalação bem-sucedida, o SHA-256 do arquivo instalado é
calculado e devolvido (`auditoria.hash_sha256`), junto da versão do
plugin (`VERSION`) e das versões declaradas em `schema.json`/`blocos.json`.
Esse hash **nunca decide se um arquivo é aceito** — serve só para
diagnóstico/auditoria (comparar duas instalações, registrar qual arquivo
foi efetivamente instalado). O gate de aceitação é exclusivamente o
contrato institucional (item 3.1, etapa 4).

## 4. `ede_doctor.py` — diagnóstico do ambiente

```bash
python scripts/ede_doctor.py
python scripts/ede_doctor.py --json
python scripts/ede_doctor.py --saida CAMINHO   # testa se CAMINHO é gravável
```

Nunca gera peça, nunca instala nem edita nada — só verifica. Termina em
uma de duas linhas:

```text
READY TO GENERATE
```
ou
```text
NOT READY
```
seguida, no segundo caso, da lista de itens obrigatórios pendentes
(`obrigatorias_falhando`). Causas típicas de `NOT READY`:

| Item que falha | Causa típica |
|---|---|
| `template:modelo-oficial.docx` | Modelo Oficial ainda não instalado — ver §3.1 |
| `template:contrato` | modelo instalado, mas incompatível com `schema.json`/`blocos.json` atuais |
| `dependencia:<nome>` | dependência Python ausente (`pip install -r ...`, ver §2) |
| `template:schema.json` / `template:blocos.json` | arquivo de contrato do plugin ausente/corrompido (instalação incompleta do próprio plugin) |
| `runtime:docx_package` | runtime DOCX não importável — quase sempre reflexo de `dependencia:lxml` ausente |
| `saida:diretorio` | o diretório-alvo de `--saida` não existe nem pode ser criado, ou não é gravável |

`ambiente:CLAUDE_PLUGIN_ROOT` é sempre informativo (nunca obrigatório) —
o doctor nunca exige esse valor; resolve o repositório sozinho a partir
do próprio caminho do script.

Nunca contorne um item `NOT READY` editando manualmente arquivos internos
do plugin para "enganar" o doctor — corrija a causa real (instale a
dependência, instale o Modelo Oficial correto, corrija o diretório de
saída).

## 5. Runtime DOCX autônomo

O EDE **não depende mais** de `skills/docx/`, `unpack.py`, `pack.py` ou
de qualquer toolkit DOCX de terceiro — decisão e migração completa
registradas em `ADR-0014` (PEND-007, **resolvida** — ver
`docs/PENDENCIAS.md`). O runtime próprio é `scripts/docx_package.py`:
manipulação direta do pacote OOXML/ZIP (biblioteca padrão + `lxml`
configurado contra XXE), sem dependência de código de terceiro
licenciado à parte. Todos os consumidores (`docx_template_engine.py`,
`docx_context_engine.py`, `docx_block_engine.py`, `validate_template.py`)
já usam exclusivamente esse runtime.

## 6. Homologação de distribuição — `scripts/homologar_distribuicao.py`

Harness standalone (fora da suíte pytest padrão — depende do Modelo
Oficial real, fornecido por parâmetro) que prova, sobre um **clone Git
limpo e temporário** (nunca o working tree do desenvolvedor), que o
pacote publicamente distribuível do EDE funciona sozinho:

```bash
python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO_DO_MODELO.docx
python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO_DO_MODELO.docx --json
python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO_DO_MODELO.docx --manter-clone
```

Opções: `--modelo-oficial` (obrigatório), `--repo` (repositório local a
clonar; padrão: este repositório), `--manter-clone` (não apaga o clone
temporário ao final, para inspeção manual), `--saida-dir` (diretório dos
artefatos do teste; padrão: temporário autogerado), `--json`.

O que o harness prova, nesta ordem, sempre via subprocesso contra as
**cópias do clone** (nunca o working tree que o orquestra):

1. `skills/docx/` e o Modelo Oficial estão ausentes no clone recém-criado;
2. `ede_doctor.py` reporta `NOT READY` antes do bootstrap;
3. `pytest tests/` roda no clone antes do bootstrap;
4. `instalar_modelo_oficial.py` instala o Modelo Oficial fornecido;
5. `ede_doctor.py` reporta `READY TO GENERATE` depois do bootstrap;
6. `pytest -m docx_real` roda no clone depois do bootstrap;
7. o pipeline da Contestação (`gerar_contestacao.gerar`, com o DataJud
   isolado — ver §7) roda até o DOCX final;
8. o DOCX final é um pacote OOXML válido, com Template Lock aprovado,
   zero placeholder residual, zero token de zona residual, zero SDT de
   bloco/zona condicional residual e numeração válida;
9. `validate_template.py` (com os mesmos artefatos que geraram o DOCX —
   ver §8) aprova a mesma peça (`ok: true`);
10. nenhuma referência funcional a `skills/docx/` sobrevive no runtime do
    clone;
11. nenhum caminho absoluto do ambiente do desenvolvedor aparece embutido
    em qualquer saída (doctor, bootstrap, relatório do pipeline, DOCX
    final).

Saída: JSON com `head_testado` (commit exato testado), `fases` (cada
etapa acima, detalhada) e `pipeline_chegou_ao_docx_final` (bool —
`true` só quando o pipeline chegou ao DOCX **e** `validate_template.py`
aprovou).

## 7. DataJud — produção × homologação

Em **produção**, `{{JUIZO}}` continua resolvido pela API pública real do
DataJud/CNJ (`scripts/datajud_client.py`) — isso não muda e não foi
simplificado por nada desta etapa.

A **homologação de distribuição** (`homologar_distribuicao.py`) não pode
depender da disponibilidade momentânea de um serviço externo para provar
que o pacote do EDE está corretamente distribuído — por isso o harness
isola especificamente essa fronteira, injetando um stub determinístico
(`resolver_juizo_fn`, mesmo mecanismo de injeção já usado pela suíte de
testes automatizada) só para essa execução. Nenhum código de produção foi
alterado para viabilizar isso: `gerar_contestacao.gerar()` já aceitava
esse parâmetro antes desta etapa, com `datajud_client.resolver_juizo`
(API real) como padrão quando o parâmetro não é fornecido — exatamente o
que acontece em qualquer geração real.

## 8. `validate_template.py` — auditoria independente de Template Lock

CLI de auditoria — reconstrói uma peça de referência com os mesmos dados
e compara, parte por parte, contra um `.docx` já gerado. Desde o
Microfix 7.1, reconstrói a referência pelo **mesmo mecanismo real de
geração** (`gerar_peca_com_blocos` — composição de blocos/zonas,
renumeração, substituição de placeholders, Template Lock interno), não
mais pelo motor de placeholder isolado.

```bash
python scripts/validate_template.py --gerado saida/peca.docx \
    --dados dados.json --decisoes-blocos decisoes_blocos.json

python scripts/validate_template.py --gerado saida/peca.docx \
    --dados dados.json --decisoes-blocos decisoes_blocos.json \
    --fatos-processuais estado_processual.json \
    --conteudo-zonas zonas_resolvidas.json
```

| Argumento | Obrigatório | Conteúdo |
|---|---|---|
| `--gerado` | sim | `.docx` já gerado a auditar |
| `--dados` | sim | JSON com os placeholders usados na geração original |
| `--decisoes-blocos` | sim | JSON com as decisões de blocos condicionais — mesmo contrato de `decisoes_blocos.json` |
| `--catalogo` | não (default `templates/contestacao/blocos.json`) | catálogo de blocos/zonas |
| `--template` | não (default `templates/contestacao/modelo-oficial.docx`) | template institucional |
| `--schema` | não (default `templates/contestacao/schema.json`) | contrato de placeholders |
| `--fatos-processuais` | não (default `{}`) | mesmo contrato de `estado_processual.json` |
| `--conteudo-zonas` | não (default `{}`) | conteúdo **já resolvido** das zonas (`{zona_id: texto}`) — não é `zonas.json` cru |

Auditar uma Contestação real composta por blocos sempre exige fornecer o
estado estrutural correspondente (`--decisoes-blocos` no mínimo) — nunca
basta `--dados`/`--gerado` sozinhos, porque um bloco legitimamente
excluído altera a estrutura esperada da peça. Saída: `{"ok": bool,
"divergencias": [...]}`. Erro documental esperado (pacote OOXML
inválido/incompleto, referência impossível de gerar) nunca é traceback
cru; retorna `ok: false` com divergência explícita.

## 9. Solução de problemas (distribuição)

| Sintoma | O que fazer |
|---|---|
| A. `ede_doctor.py` reporta `NOT READY` só por `template:modelo-oficial.docx` | Esperado antes da instalação do Modelo Oficial — rode `instalar_modelo_oficial.py` (§3.1), não é erro. |
| B. Bootstrap rejeita com `MODELO_INSTITUCIONAL_DESATUALIZADO` | O arquivo fornecido é de uma versão do template incompatível com esta instalação do plugin — peça a versão atual ao escritório; ver §3.2. Nunca edite o `.docx` manualmente para forçar aceitação. |
| C. `ede_doctor.py` reporta `dependencia:<nome>` faltando | `pip install -r scripts/requirements.txt` e `pip install -r rag/requirements.txt` (§2). |
| D. Instalação/auditoria recebe um `.docx` corrompido/inválido | `instalar_modelo_oficial.py`/`validate_template.py` reportam `ok: false`/`REJEITADO` com o motivo — nunca traceback cru. Reobtenha o arquivo pela fonte original. |
| E. `validate_template.py` retorna `ok: false` contra uma peça aparentemente correta | Confirme que `--decisoes-blocos`/`--fatos-processuais`/`--conteudo-zonas` são exatamente os mesmos artefatos usados na geração daquela peça (§8) — divergência real de conteúdo institucional é Template Lock funcionando corretamente, não um bug do validador. |
| F. DataJud indisponível em produção | Falha esperada e fail-closed (`stage=juizo_datajud`) — não existe modo "produção sem DataJud"; aguarde a disponibilidade do serviço ou verifique `NUMERO_PROCESSO`. Não relacionado à homologação de distribuição (§7). |
| G. `skills/docx` local causa falha só em `pytest tests/` no ambiente do desenvolvedor | `test_gate_contestacao.py::test_nenhuma_skill_de_outra_peca_foi_criada` falha se existir uma pasta `skills/docx/` local antiga (gitignored, nunca commitada) — é um guarda de desenvolvimento, não um requisito do produto. `skills/docx/` **não é dependência do EDE** (§5) e não deve ser instalada por usuários finais; a falha desaparece num clone limpo (comprovado pelo harness — §6, item 10) ou apagando a pasta local antiga. |

## 10. Versionamento

`VERSION` (arquivo na raiz) é a **fonte canônica** da versão do plugin —
decisão já registrada em `ADR-0008` §Decisão item 3.
`.claude-plugin/plugin.json` é sincronizado manualmente a partir dela;
`tests/test_marketplace.py` e `scripts/validar_instalacao.py` conferem
essa sincronia. Este documento não altera `VERSION` nem `plugin.json` —
nenhum bump de versão é feito por este commit.

## 11. Arquitetura host-agnostic

Nenhum componente descrito neste documento depende de Claude Code para
funcionar:

- `docx_package.py` (runtime DOCX) — `Path`s explícitos, sem
  `CLAUDE_PLUGIN_ROOT`, sem `SKILL.md`, sem `~/.claude`/`~/.agents`;
- `instalar_modelo_oficial.py` — idem;
- `ede_doctor.py` — resolve o repositório sozinho
  (`Path(__file__).resolve()`); `CLAUDE_PLUGIN_ROOT`, quando definido, é
  reportado só como informação adicional, nunca exigido;
- `homologar_distribuicao.py` — roda via subprocesso puro Python/Git,
  sem SDK do Claude.

Isso preserva, para o futuro, a possibilidade de adapters equivalentes
para outros hosts (OpenAI, MCP) sem exigir reescrita do núcleo — **nenhum
desses adapters está implementado nem prometido por este documento.**

## 12. Fluxo operacional do advogado (uso normal)

Não é necessário entender OOXML, pytest, Git ou a arquitetura interna do
runtime para usar o plugin no dia a dia:

1. instalar o plugin (ver `README.md`, seção "Instalação");
2. preparar os documentos do caso normalmente;
3. instalar o Modelo Oficial **uma única vez** por instalação
   (`instalar_modelo_oficial.py`, §3.1) — repetir só se o escritório
   enviar uma versão atualizada do template;
4. rodar `python scripts/ede_doctor.py` quando houver dúvida sobre o
   ambiente (opcional no uso corriqueiro — só necessário logo após
   instalar, atualizar o plugin, ou diante de um erro inesperado);
5. só pedir a elaboração da Contestação quando o doctor confirmar
   `READY TO GENERATE` (ou, no uso corriqueiro, quando a geração
   anterior já tiver funcionado normalmente).

Este fluxo é distinto de diagnóstico/desenvolvimento (§4, §6, §8, §9) —
o advogado não precisa executar o harness de homologação nem
`validate_template.py`; essas ferramentas são de quem mantém/distribui o
plugin.

## 13. Pendências não bloqueantes

Registradas com detalhe em `docs/PENDENCIAS.md`:

- **Segundo asset de teste** (`modelo-oficial_topicos-2.3-a-2.6_contratados.docx`)
  — legado/redundante (partes OOXML byte-idênticas ao Modelo Oficial
  canônico); consolidação/remoção futura, não bloqueante.
- **`docx_numeracao_engine.py`** localiza títulos de nível 2/3 por
  âncoras de texto hardcoded do Modelo Oficial real — dívida
  arquitetural pré-existente (não introduzida pela Etapa 5.10), não
  bloqueante para runtime/distribuição.
- **Inspeção visual automatizada** do DOCX final ainda não foi
  executada — nenhum renderizador DOCX legítimo disponível no ambiente
  de homologação até este commit. Não bloqueia runtime/distribuição
  técnica, mas **permanece requisito antes de qualquer release público
  que pretenda declarar validação visual automatizada.**

## 14. O que este documento NÃO afirma

Para deixar explícito o limite do que foi homologado:

- **não** existe instalação automática do Modelo Oficial via
  marketplace — é sempre um passo manual, com arquivo fornecido
  externamente (§3);
- **não** existe atualização automática do Modelo Oficial — reinstalar
  é sempre uma ação explícita do usuário;
- **não** há suporte OpenAI/MCP implementado — só a arquitetura
  host-agnostic que os viabilizaria no futuro (§11);
- **não** há renderização visual automática do DOCX final pronta (§13);
- **não** se pode presumir que o DataJud estará sempre disponível em
  produção (§7, §9-F);
- **não** há zero dependência externa em produção — DataJud/CNJ
  continua sendo uma dependência de rede real da geração completa;
- **não** há auto-update do plugin — `/updateEde` só verifica e informa
  a versão publicada (ver `README.md`, seção "Atualização").
