# Contrato de ambiente de produção — EDE MCP Server (`ede-mcp`)

* **Status:** referência viva, companheira de ADR-0017.
* **Escopo:** somente as variáveis de ambiente **não secretas** que o
  serviço Cloud Run `ede-mcp` de produção precisa receber para que
  `mcp_server/auth_config.py` monte uma `EdeAuthConfig` válida e o guard
  de produção (`INV-PRODUCAO-AUTH-OBRIGATORIA`, Gate 6.3-D3.1) aceite a
  subida do processo.
* **Este documento não cria, não provisiona e não injeta nada.** Ele só
  registra o contrato para os Gates de implementação (6.3-D3.2 em
  diante) preencherem os valores reais.
* Nenhum valor abaixo é secreto — todos são identificadores públicos por
  natureza (URL, issuer, nome de host). Segredo algum pertence a este
  arquivo, a este repositório, ou a variável de ambiente do Cloud Run —
  ver Gate 6.3-D3.0 §8 (análise de necessidade de client secret) e
  ADR-0017 §3/§6.

## Variáveis obrigatórias

| Variável | Valor de produção | Status | Fonte |
|---|---|---|---|
| `EDE_MCP_AUTH_ENABLED` | `true` | **fixo, obrigatório** | esta ADR — nunca omitido em produção (ver guard, seção abaixo) |
| `EDE_MCP_RESOURCE` | `https://ede-mcp-269134711029.southamerica-east1.run.app/mcp` | **valor esperado, verificação final é critério de aceite do Gate 6.3-D3.5** (a criação real do serviço confirma o hostname determinístico) | derivado do nome do serviço (`ede-mcp`), número do projeto (`269134711029`, já confirmado em uso pelo staging) e região |
| `EDE_MCP_ISSUER` | *pendente* | **preenchido no Gate 6.3-D3.2** | descoberta OIDC do Resource Descope de produção |
| `EDE_MCP_JWKS_URI` | *pendente* | **preenchido no Gate 6.3-D3.2** | descoberta OIDC do Resource Descope de produção |
| `EDE_MCP_REQUIRED_SCOPES` | `ede:health` | **fixo nesta fase** | nenhuma ferramenta `ede:legal` existe ainda (Gate 6.3-D3.8+ reabre este valor) |
| `EDE_MCP_CANONICAL_HOST` | `ede-mcp-269134711029.southamerica-east1.run.app` | **valor esperado**, mesma ressalva de `EDE_MCP_RESOURCE` | derivado do host do Resource |

## Variáveis que permanecem deliberadamente ausentes

| Variável | Por que fica ausente |
|---|---|
| `EDE_MCP_ACCEPTED_AUDIENCES` | ausente → `auth_config.py` deriva automaticamente `(EDE_MCP_RESOURCE,)`, exatamente uma audience. Só passa a ser declarada explicitamente numa futura janela de migração de hostname (domínio customizado) — nunca por omissão. |
| `EDE_MCP_ALLOWED_ORIGINS` | ausente → nenhuma Origin de navegador é pré-autorizada. Claude e ChatGPT não enviam Origin de navegador (prova viva do Gate 6.3-D0c) — Origin ausente segue normalmente para a validação OAuth. Só passa a ser preenchida se um cliente comprovadamente precisar de Origin explícita. |

## Guard de produção — `INV-PRODUCAO-AUTH-OBRIGATORIA`

Implementado no Gate 6.3-D3.1 em `mcp_server/auth_config.py`. Regra:

> Quando a variável de ambiente `K_SERVICE` (injetada pela própria
> plataforma Cloud Run — nunca configurável por omissão externa) for
> exatamente `ede-mcp`, a camada OAuth de aplicação é **obrigatória**.
> `EDE_MCP_AUTH_ENABLED` ausente, falso, ou qualquer configuração OAuth
> inválida faz o processo recusar subir. Não existe caminho em que o
> serviço de produção alcance o dispatcher MCP com autenticação
> desligada.

O guard é amarrado especificamente a `K_SERVICE == "ede-mcp"` — nunca
generalizado para qualquer nome de serviço. `ede-mcp-staging`, o
serviço de prova descartável, desenvolvimento local e a suíte de testes
continuam podendo rodar com a camada OAuth desligada, exatamente como
antes (ADR-0016).

## Pendências explícitas para o Gate 6.3-D3.2

1. Criar o Resource Descope de produção e capturar `issuer`/`jwks_uri`
   reais (nenhum dos dois existe hoje — Gate 6.3-D2.6, achado
   confirmado por ADR-0017 §3).
2. **Validar o formato exato de claim de um token real do Descope**
   contra o verificador implementado (`mcp_server/token_verifier.py`):
   tipo de `scope` (string espaço-separada, não lista), forma de `aud`,
   presença de `azp`/`client_id`/`sub`, e se o `issuer` retornado pela
   descoberta OIDC do Descope termina ou não em `/` (a validação de
   configuração de `auth_config.py` rejeita URI com barra final). Os
   106 testes do Gate 6.3-D2 são inteiramente sintéticos — nenhum deles
   provou o formato real de um token Descope. Este é pré-requisito de
   aceite explícito do Gate 6.3-D3.2, não do 6.3-D3.1.
3. Só depois de (1) e (2), preencher `EDE_MCP_ISSUER`/`EDE_MCP_JWKS_URI`
   nesta tabela com os valores reais.

## Confirmação do hostname determinístico

O valor de `EDE_MCP_RESOURCE`/`EDE_MCP_CANONICAL_HOST` acima é o
**esperado**, derivado do mesmo padrão já observado em produção real
neste projeto (`ede-mcp-staging-269134711029.southamerica-east1.run.app`
e o serviço de prova descartável, ambos determinísticos e confirmados).
A confirmação final de que `ede-mcp` (sem sufixo de revisão) resolve
para esse hostname exato é **critério de aceite do Gate 6.3-D3.5**
(criação do serviço candidato) — este documento não declara isso como
fato consumado antes da criação real do serviço.
