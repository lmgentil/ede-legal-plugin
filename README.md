# EDE Legal Plugin

Plugin jurídico para [Claude Code](https://claude.com/claude-code) destinado
à elaboração assistida de peças processuais, combinando Skills jurídicas
especializadas, um modelo DOCX institucional protegido (Template Lock) e um
RAG jurídico próprio (busca híbrida lexical + vetorial sobre legislação e
jurisprudência).

O primeiro módulo processual suportado é a **Contestação**. A arquitetura é
projetada para permanecer extensível a outros tipos de peça — ver
[`CLAUDE.md`](./CLAUDE.md) e [`docs/specs/SPEC-0001.md`](./docs/specs/SPEC-0001.md).

## Status atual (v0.8.0 — Fase 8 de 9 aprovada)

🚧 **Em desenvolvimento. Distribuição via marketplace pronta e testada
localmente (Fase 8). Decisão de arquitetura definitiva: repositório e
plugin serão públicos, o modelo institucional (`.docx`) é asset externo
que nunca integra o repositório — ver "Template institucional" abaixo.
Publicação externa (GitHub público, release) ainda não aconteceu; único
bloqueio conhecido é `PEND-004` (definição da licença). Hardening final
(Fase 9) segue pendente.**

| Camada | Status |
|---|---|
| Estrutura do plugin, versionamento, segurança básica | ✅ Fase 1 |
| Skills transversais (redator, humanizer, calendário) | ✅ Fase 2 |
| Template Engine + Template Lock | ✅ Fase 3 — ver pendência PEND-001 abaixo |
| RAG jurídico | ✅ Fase 4 (legislação/regulamentos); jurisprudência adiada — `PEND-002` |
| Validação jurídica (citações, vigência, rastreabilidade) | ✅ Fase 5 |
| Skill Contestação + estrategista-contestacao-ede (orquestração obrigatória) | ✅ Fase 6 |
| Integração end-to-end (`scripts/gerar_contestacao.py`) | ✅ Fase 7 — caso sintético, ver `docs/E2E_FASE7.md` |
| Distribuição via marketplace + `/updateEde` | ✅ Fase 8 — publicação externa pendente, ver "Instalação" |
| Hardening final | ⏳ Fase 9 |

O progresso por fase é controlado por gates explícitos — ver `CLAUDE.md §4`.
Nenhuma fase é iniciada sem autorização.

> **PEND-001** (`docs/PENDENCIAS.md`, status `DEFERRED` desde a correção
> v0.6.1): suporte a imagem embutida no placeholder
> `FOTOS_DA_IRREGULARIADE` não será automatizado na V1 — decisão explícita
> do usuário. O campo recebe um marcador textual de inserção manual pelo
> advogado. Não bloqueia a Fase 8.

## RAG jurídico (já funcional)

O componente de recuperação de conhecimento jurídico (`rag/`) foi migrado de
um projeto anterior e já está operacional, independente do restante do
plugin:

- 434 chunks cobrindo 6 diplomas (CPC, Código Civil, CDC, Lei 8.987/1995,
  Lei 9.427/1996, REN ANEEL 1.000/2021), com cobertura de artigos de 100%.
- Busca híbrida (BM25 + embeddings) com lookup direto por número de artigo.
- Camada de confiança calibrada (alta/média/baixa) e avaliação de regressão
  contra um gold-set de consultas.

```bash
pip install -r rag/requirements.txt
python rag/search_hybrid.py "prazo para contestação no procedimento comum"
python rag/search_hybrid.py "art. 373 CPC"
```

Detalhes em [`rag/CONTEXTO_RAG.md`](./rag/CONTEXTO_RAG.md).

> A jurisprudência curada do escritório (`rag/jurisprudencia/`) existe
> localmente mas **não é distribuída com o repositório público** e ainda não
> está integrada à busca híbrida — ver
> [`docs/adr/ADR-0006-assets-institucionais.md`](./docs/adr/ADR-0006-assets-institucionais.md).

## Template institucional

O EDE Legal Plugin é o **motor** de elaboração da Contestação — RAG,
validação jurídica, orquestração de Skills, Template Engine, Template
Lock. O modelo institucional propriamente dito,

```text
templates/contestacao/modelo-oficial.docx
```

é um **asset externo ao plugin**, decisão definitiva (não uma questão em
aberto — ver `docs/adr/ADR-0009-distribuicao-publica-template-externo.md`):

1. **não integra o repositório** (nunca foi commitado, confirmado no
   histórico git completo, não só no índice atual);
2. **não é distribuído com o plugin público** — instalar o plugin via
   marketplace nunca inclui esse arquivo;
3. é **fornecido separadamente**, fora deste repositório, aos usuários
   autorizados a recebê-lo (o timbrado revela identidade do escritório,
   dados de contato e OAB);
4. o caminho esperado, quando fornecido, é exatamente
   `templates/contestacao/modelo-oficial.docx`;
5. **sem esse arquivo, o resto do plugin continua disponível** — Skills,
   RAG, validação jurídica e análise estratégica funcionam normalmente;
6. **só a geração do DOCX institucional final exige o template** — nesse
   ponto específico, a ausência interrompe só essa etapa
   (`scripts/gerar_contestacao.py` reporta `PIPELINE_ABORTED` no estágio
   `template_engine`, nunca inventa, baixa ou reconstrói um template).

`python scripts/validar_instalacao.py` trata este item como **opcional**
— sua ausência não significa instalação incorreta.

## Instalação

> ⚠️ **Este repositório ainda não tem origem git remota configurada**
> (`git remote -v` vazio) — os comandos abaixo funcionam hoje com um
> **caminho local** (`/plugin marketplace add <caminho-para-este-repositório>`).
> Quando houver uma origem git (GitHub ou equivalente) publicada, o mesmo
> fluxo funciona apontando para ela em vez do caminho local — nenhum outro
> passo muda.

Pré-requisitos: Claude Code com suporte a Plugin Marketplace (versão
atual da CLI) e Python 3.10+ no PATH (testado em 3.12) para os scripts do
RAG e do Template Engine — ver "Dependências Python" abaixo.

1. **Adicionar o marketplace:**
   ```text
   /plugin marketplace add <caminho-ou-origem-deste-repositório>
   ```
2. **Instalar o plugin:**
   ```text
   /plugin install ede-legal-plugin@ede
   ```
3. **Instalar dependências Python** (fora do Claude Code, uma vez):
   ```bash
   pip install -r rag/requirements.txt
   pip install -r scripts/requirements.txt
   ```
   O toolkit `docx` (usado pelo Template Engine) não é distribuído com
   este plugin — precisa estar disponível em `~/.claude/skills/docx` ou
   `~/.agents/skills/docx`. Sem ele, `render_docx.py`/`validate_template.py`
   falham explicitamente (fail closed), não silenciosamente.
4. **Fornecer o template institucional** — asset externo, ver "Template
   institucional" acima. Copie o `.docx` real do seu escritório para
   `templates/contestacao/modelo-oficial.docx` antes de gerar uma
   Contestação.
5. **Validar a instalação:**
   ```bash
   python scripts/validar_instalacao.py
   ```
   `STATUS: OK` confirma que as 5 Skills, o schema do template e a
   configuração do RAG estão presentes (o `.docx` institucional real é
   opcional nesta checagem — ver passo 4).

## Atualização

Digite **`/updateEde`** — aciona a Skill `atualizar-ede`, que identifica
sua versão atual, explica e conduz os dois comandos oficiais do Claude
Code:
```text
/plugin marketplace update ede
/plugin update ede-legal-plugin@ede
```
e valida o resultado com `scripts/validar_instalacao.py` depois que você
reiniciar/recarregar a sessão (necessário para a nova versão carregar).

**Não existe atualização automática disparada pelo próprio plugin** — o
Claude Code verifica e aplica atualizações em segundo plano
periodicamente, mas o gatilho é sempre do usuário ou desse mecanismo
nativo, nunca do plugin instalado. `/updateEde` nunca afirma que uma
atualização terminou sem essa validação (Fail Closed).

Para ver o que mudou entre versões, consulte [`CHANGELOG.md`](./CHANGELOG.md)
— procure o cabeçalho `## [<sua-versão-nova>]`.

## Desinstalação

```text
/plugin uninstall ede-legal-plugin@ede
```
Comando oficial confirmado na documentação vigente do Claude Code — não
há passo adicional específico deste plugin.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| Marketplace não encontrado | Confirme o caminho/origem exato passado a `/plugin marketplace add`; rode `/plugin marketplace list` para ver o que já foi adicionado. |
| Plugin não encontrado | Confirme que o marketplace `ede` foi adicionado antes de `/plugin install ede-legal-plugin@ede`; o nome do plugin é `ede-legal-plugin`, não "EDE Legal Plugin" (esse é só o `displayName`). |
| Versão antiga ainda carregada | Rode `/plugin update ede-legal-plugin@ede` e **reinicie/recarregue a sessão** — a nova versão só é aplicada após reload. |
| Dependência Python ausente | `pip install -r rag/requirements.txt -r scripts/requirements.txt`. Scripts falham explicitamente (fail closed), nunca silenciosamente, quando uma dependência falta. |
| RAG indisponível | Confirme `rag/config.yaml` e `rag/index_artigos.json` presentes (`python scripts/validar_instalacao.py`); sem `sentence-transformers` instalado, a busca cai automaticamente para o fallback TF-IDF+LSA — não é erro. |
| Template ausente | Esperado logo após instalar — `modelo-oficial.docx` é asset privado do escritório, não vem com o plugin público. Copie o seu para `templates/contestacao/modelo-oficial.docx`. |
| `claude plugin validate .` falha | Rode `claude plugin validate .claude-plugin/plugin.json` para isolar erros do plugin dos do marketplace (`marketplace.json`), validados separadamente quando ambos existem no mesmo diretório. |

## Segurança

- Documentos processuais reais (petições, TOIs, laudos, faturas) **nunca
  devem ser commitados** — mantenha-os fora da árvore do repositório ou
  em diretórios cobertos pelo `.gitignore` (CLAUDE.md §18-19).
- `.env` nunca deve ser versionado — use `.env.example` como referência
  de nomes de variável, nunca com valores reais.
- Fotografias da irregularidade são inseridas **manualmente pelo
  advogado** na V1 — o placeholder `FOTOS_DA_IRREGULARIADE` só recebe um
  marcador textual (`PEND-001`, `DEFERRED`), nunca imagem automática.
- Jurisprudência real do escritório (`rag/jurisprudencia/`) **não integra
  a distribuição atual** — `PEND-002`, adiada. Nada desse diretório é
  lido pela busca híbrida nem publicado.
- O template institucional real é asset privado — ver "Instalação" acima
  e `docs/adr/ADR-0006-assets-institucionais.md`.

## Documentação

- [`CLAUDE.md`](./CLAUDE.md) — regras operacionais permanentes do agente.
- [`docs/specs/SPEC-0001.md`](./docs/specs/SPEC-0001.md) — especificação da Arquitetura v1.
- [`docs/adr/`](./docs/adr/) — decisões arquiteturais registradas.
- [`docs/PENDENCIAS.md`](./docs/PENDENCIAS.md) — pendências abertas com ID rastreável e fase de bloqueio.
- [`docs/E2E_FASE7.md`](./docs/E2E_FASE7.md) — execução end-to-end registrada sobre caso sintético.
- [`CHANGELOG.md`](./CHANGELOG.md) — histórico de mudanças.

## Licença

O código-fonte é disponibilizado publicamente sob uma licença
proprietária de código-fonte disponível ("source-available") — ver
[`LICENSE`](./LICENSE). Isso não o torna *open source* nem *free
software*. Resumo (não substitui a leitura do texto integral):

* **Permitido sem pedir autorização:** visualizar, baixar, clonar,
  instalar e executar o plugin (inclusive via marketplace), estudar o
  código, modificar cópias locais, usar profissionalmente — inclusive
  internamente por escritórios de advocacia diferentes do titular.
* **Permitido com condições:** criar e distribuir versões modificadas,
  desde que mantidos os avisos de copyright/licença, identificado
  claramente como versão modificada, e sem se apresentar como o EDE
  Legal Plugin original.
* **Proibido sem autorização prévia e expressa por escrito do
  titular:** redistribuir o software original por canal próprio,
  sublicenciar, comercializar o plugin ou derivados, apropriar-se da
  autoria, remover avisos, ou usar o nome/marcas do projeto ou de
  terceiros de forma a sugerir endosso inexistente.
