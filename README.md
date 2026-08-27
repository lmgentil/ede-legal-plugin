# EDE Legal Plugin

Plugin jurídico para [Claude](https://claude.com) voltado à elaboração
assistida de peças processuais, combinando Skills jurídicas
especializadas, recuperação de conhecimento jurídico (RAG), validação de
citações e geração estruturada de documentos.

> Atualmente, o módulo processual disponível é a Contestação.

**Versão:** 0.10.1 · **Licença:** source-available · **Repositório:**
[`lmgentil/ede-legal-plugin`](https://github.com/lmgentil/ede-legal-plugin)

## Principais recursos

- Elaboração assistida de Contestação.
- Análise estratégica obrigatória antes da redação.
- Recuperação de legislação e regulamentação por RAG (busca lexical + vetorial).
- Validação de citações jurídicas.
- Separação entre fatos documentados, alegações e inferências.
- Análise de tempestividade quando aplicável.
- Redação jurídica estruturada.
- Humanização textual.
- Geração de DOCX a partir de template institucional.
- Mecanismo fail-closed: impede geração silenciosa quando falta elemento essencial.

## Contestação

```text
Documentos do processo
        ↓
Extração e organização dos fatos
        ↓
Análise de tempestividade
        ↓
Estratégia defensiva
        ↓
Pesquisa jurídica
        ↓
Validação das citações
        ↓
Redação
        ↓
Revisão/humanização
        ↓
Documento final
```

## RAG jurídico

O plugin possui mecanismo próprio de recuperação de conhecimento
jurídico, combinando busca lexical e vetorial sobre legislação e
regulamentação. O objetivo é fornecer contexto jurídico rastreável para
a elaboração das peças e reduzir o risco de citações inexistentes ou
desconectadas da fonte.

Diplomas cobertos atualmente: Código de Processo Civil, Código Civil,
Código de Defesa do Consumidor, Lei 8.987/1995, Lei 9.427/1996 e a
Resolução Normativa ANEEL 1.000/2021.

> A jurisprudência do escritório ainda não integra a busca híbrida nesta versão.

## Instalação

### Opção 1 — Claude Cowork

Instalação pela interface, sem terminal. Este fluxo ainda **não foi
homologado de ponta a ponta**: marketplaces pessoais do Cowork podem
manter conteúdo anterior mesmo quando a interface exibe `synced` ou
`updated`. Esses estados não comprovam que a versão atual do plugin foi
carregada.

1. **Adicionar o marketplace:** Customize → Plugins → Personal plugins
   → **+** → Add marketplace → Add from a repository → informe
   `lmgentil/ede-legal-plugin`.
2. **Instalar o plugin:** Browse plugins → **EDE Legal Plugin** → Install.
3. **Usar as Skills:** digite `/` no chat ou use o botão **+** — a Skill
   certa é acionada conforme o pedido.

### Opção 2 — Claude Code

```text
/plugin marketplace add lmgentil/ede-legal-plugin
/plugin install ede-legal-plugin@ede
```

O plugin fica disponível na sessão atual do Claude Code.

### Opção 3 — Clone pelo terminal

```bash
git clone https://github.com/lmgentil/ede-legal-plugin.git
```

Indicado para estudo do código, desenvolvimento ou adaptação nos limites
da licença.

## Desenvolvimento e testes

A suíte pytest é segmentada por dependência operacional. Os segmentos
pesados são mutuamente exclusivos; testes sem marcador pesado compõem o
grupo rápido.

```text
# Unitários e estruturais rápidos
python -m pytest -m "not rag and not docx_real and not pipeline_e2e and not network"

# Integração com o modelo institucional privado disponível localmente
python -m pytest -m docx_real

# RAG, artefatos persistidos e gold set
python -m pytest -m rag

# Pipeline Python completo da Contestação
python -m pytest -m pipeline_e2e

# Smoke tests externos — opt-in; retorna código 5 enquanto o segmento estiver vazio
python -m pytest -m network

# Gate final: todos os segmentos
python -m pytest
```

`pipeline_e2e` comprova o pipeline Python local, não uma execução real do
Claude Code. Homologação do host Claude Code e do Cowork continua sendo
uma atividade separada; o Cowork permanece não homologado de ponta a
ponta. Os marcadores são registrados com `--strict-markers` em
`pytest.ini`, de modo que erros de digitação ou categorias não declaradas
interrompam a coleta.

## Como usar

Depois de instalado, não é necessário conhecer o nome de cada Skill —
basta pedir em linguagem natural, por exemplo:

- "Analise os documentos desta pasta e elabore uma contestação."
- "Elabore uma contestação utilizando o EDE Legal Plugin."
- "Analise estrategicamente este processo antes de elaborar a defesa."

## Skills incluídas

| Skill | Função |
|---|---|
| `contestacao` | Orquestra a elaboração da Contestação |
| `estrategista-contestacao-ede` | Define a estratégia defensiva antes da redação |
| `redator-peca-processual-elite` | Realiza a redação jurídica estruturada |
| `humanizer-pt-br` | Refina a naturalidade e fluidez do texto |
| `calendario-forense-tjba-2026` | Auxilia na análise de tempestividade |
| `atualizar-ede` | Verifica se há versão mais nova do plugin publicada |

## Template institucional

O template DOCX institucional não é distribuído neste repositório.
Usuários autorizados podem receber o arquivo separadamente e utilizá-lo
com o mecanismo de geração documental do plugin.

A ausência do template não impede a instalação nem o uso das Skills e
dos recursos jurídicos; ela apenas impede a geração do DOCX
institucional correspondente.

## Atualização

No Claude Code:

```text
/plugin marketplace update ede
/plugin update ede-legal-plugin@ede
```

`/updateEde` (Skill `atualizar-ede`) não executa os comandos acima — ela
só verifica se a versão instalada está desatualizada em relação à última
Release oficial publicada no GitHub e indica a Release correspondente.

No Claude Cowork, use `/updateEde` apenas para verificar a versão
carregada. Até a homologação completa desse fluxo, `synced` ou `updated`
não comprova atualização efetiva. Se houver divergência, reinstale por
um pacote/versionamento explicitamente identificado conforme o canal de
distribuição autorizado; não presuma que a sincronização visual resolveu
o cache.

## Desinstalação

```text
/plugin uninstall ede-legal-plugin@ede
```

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| Marketplace não encontrado | Confirme que adicionou `lmgentil/ede-legal-plugin` como marketplace antes de instalar o plugin. |
| Plugin não encontrado | O identificador técnico é `ede-legal-plugin`, dentro do marketplace `ede`. |
| Template institucional ausente | Esperado antes do fornecimento do arquivo pelo escritório — não é erro de instalação. |
| Versão antiga carregada | No Claude Code, rode os comandos de atualização acima e reinicie/recarregue a sessão. No Cowork, confira com `/updateEde`; se persistir, reinstale por um pacote/versionamento explicitamente identificado, pois `synced` não comprova a versão carregada. |

## Segurança

> Não versione nem publique documentos processuais, credenciais,
> informações sigilosas ou outros dados de clientes junto ao repositório.

## Licença

O projeto utiliza licença própria **source-available** — não é open
source. Ver [`LICENSE`](./LICENSE) para o texto integral.

**Permitido:** visualizar, baixar/clonar, instalar, utilizar conforme os
termos da licença, estudar o código, uso profissional nos limites
definidos.

**Condicionado:** criar modificações e derivados, redistribuir
derivados — conforme os requisitos da licença.

**Proibido sem autorização prévia:** redistribuir o projeto original
como produto próprio, sublicenciar, vender ou oferecer comercialmente
cópia/derivado, remover avisos de autoria, apresentar o projeto como de
autoria própria, usar indevidamente marcas ou timbrados institucionais.

## Aviso

O EDE Legal Plugin é uma ferramenta de apoio à atividade jurídica e não
substitui a análise profissional do advogado responsável. O usuário deve
revisar fatos, fundamentos jurídicos, citações, tempestividade e
conteúdo final antes de qualquer protocolo ou utilização profissional.

## Documentação técnica

Para desenvolvedores e interessados na arquitetura:
[`CLAUDE.md`](./CLAUDE.md), [`docs/`](./docs/), [`CHANGELOG.md`](./CHANGELOG.md).
