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

**Endurecimento do Gate 6.6-F — `INV-CLOUD-RUN-AUTH-OBRIGATORIA`
(adendo à ADR-0017).** O parágrafo acima descreve o guard original. A
partir do commit `b20c2cf`, a obrigação de OAuth deixou de ser "só o
nome de produção" e passou a ser **fail-closed por padrão em todo
serviço Cloud Run**: qualquer processo com `K_SERVICE` não vazio recusa
subir sem a camada OAuth de aplicação (`CloudRunSemAuthInvalida`), salvo
a lista explícita e mínima `SERVICOS_CLOUD_RUN_ISENTOS_DE_AUTH` — hoje
somente `ede-mcp-staging` (privado por IAM, ADR-0016). Motivo: o
homolog permanente `ede-mcp-homolog` é internet-facing (`allUsers`) e
não pode depender da presença manual de `EDE_MCP_AUTH_ENABLED=true`.
Produção inalterada: `ede-mcp` continua levantando
`ProducaoSemAuthInvalida`, mesma mensagem (hoje subclasse de
`CloudRunSemAuthInvalida`). `K_SERVICE` ausente/vazio (local, suíte,
contêiner fora do Cloud Run) sem mudança. `ede-oauth-proof-disposable`
usa imagem própria (`ede-proof-disposable`), fora deste código.

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

## Modelo Oficial — Arquitetura A′ (Gate 6.4-B, ADR-0017 §6)

Diferente das variáveis OAuth acima (adiadas para o Gate 6.3-D3.2), o
bucket privado, o objeto e a geração pinada **já existem de fato** —
criados e verificados no Gate 6.4-B. Estes valores só passam a ser
**aplicados** ao serviço `ede-mcp` real no gate de deploy de produção
(ainda não autorizado); até lá, permanecem documentados aqui como
contrato congelado, não injetados em revisão alguma.

| Variável | Valor congelado | Status |
|---|---|---|
| `EDE_MODELO_OFICIAL_GCS_BUCKET` | `ede-legal-mcp-01-modelo-oficial-privado` | criado no Gate 6.4-B — privado, regional (`southamerica-east1`), acesso uniforme, prevenção de acesso público forçada (`public_access_prevention: enforced`), sem `allUsers`/`allAuthenticatedUsers` |
| `EDE_MODELO_OFICIAL_GCS_OBJECT` | `modelo-oficial/modelo-oficial.docx` | único objeto no bucket |
| `EDE_MODELO_OFICIAL_GCS_GENERATION` | `1789696822240267` | geração exata do upload do Gate 6.4-B — nunca "latest" |
| `EDE_MODELO_OFICIAL_SHA256` | `53adf880cb35a016986f482d6d9bc609118951b9684b77d413fae12a611104d8` | SHA-256 do `templates/contestacao/modelo-oficial.docx` canônico (idêntico ao relatado no Gate 6.4-A) — verificado por download real da geração pinada acima no próprio Gate 6.4-B |

IAM: `ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com` tem
`roles/storage.objectViewer` escopado **só** a este bucket (nenhum papel
de projeto, confirmado por auditoria `gcloud projects get-iam-policy`
sem resultado para esta SA). Única outra identidade com acesso a este
bucket: `ede-mcp-homolog-runtime` (`roles/storage.objectViewer`,
concedida no Gate 6.6-F para o homolog permanente — ver seção
"Homologação permanente" abaixo).

`EDE_MODELO_OFICIAL_PATH`/`EDE_MODELO_OFICIAL_SHA256` (modo local, Gate
6.4-A) **nunca** são definidas em produção — a presença de qualquer uma
das três variáveis `EDE_MODELO_OFICIAL_GCS_*` acima ativa exclusivamente
o modo GCS em `scripts/legal_readiness.py` (ver docstring do módulo).

## Artefatos efêmeros — entrega v2 (Gate 6.6-E, ADR-0019)

Mesma disciplina do bloco acima: o bucket **já existe de fato**
(candidato/homologação, criado no Gate 6.6-E), mas as duas variáveis
abaixo **não estão aplicadas a nenhuma revisão de produção** — a
revisão corrente (`ede-mcp-00020-gum`, 100% do tráfego) não tem nenhuma
delas definida, então `ede_finalizar_peca` em produção hoje recusa com
`ARTIFACT_STORAGE_FAILED` (`scripts/artifact_storage.ErroConfiguracaoArtefato`)
até a ativação ser explicitamente autorizada.

| Variável | Valor candidato | Status |
|---|---|---|
| `EDE_ARTEFATOS_GCS_BUCKET` | `ede-legal-mcp-01-artefatos-efemeros` | criado no Gate 6.6-E — privado, regional (`southamerica-east1`), acesso uniforme, `public_access_prevention: enforced`, sem `allUsers`/`allAuthenticatedUsers`, **sem versionamento** (confirmado ao vivo), **soft-delete desligado** (`retentionDurationSeconds: 0`, confirmado ao vivo — o padrão do projeto GCP retém objeto "excluído" por 7 dias; desligado aqui porque o bucket guarda documento jurídico efêmero e uma exclusão precisa ser real, nunca recuperável), **sem retention policy nem default event-based hold** (confirmado ao vivo), lifecycle `age: 2` (dias) como backstop **assíncrono, sem prazo garantido** — nunca a garantia normal de exclusão (ver ADR-0019, seção "Retenção") |
| `EDE_ARTEFATOS_SIGNER_SA` | *(pendente — ver nota de IAM abaixo)* | e-mail da service account a impersonar para `signBlob` (V4 keyless); em produção normal é o e-mail da PRÓPRIA `ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com` (auto-impersonation) |

**Retenção (decisão final, Gate 6.6-E continuação):** janela de
AUTORIZAÇÃO de download = 24 horas (`TTL_DOWNLOAD_SEGUNDOS`, revisado
de um valor original de 15 minutos — histórico no `CHANGELOG.md`);
elegibilidade de limpeza NORMAL = imediatamente ao expirar essa janela
(`LIMPEZA_ELEGIVEL_SEGUNDOS`, sem margem adicional); retenção normal
ALVO = ~24-25h, nunca prometida como exata, sustentada por **limpeza
agendada horária** (Cloud Scheduler -> Cloud Run Job executando
`scripts/limpar_artefatos_agendado.py` a partir da mesma imagem
imutável de runtime) somada à limpeza oportunista disparada por
finalizações reais. Provisionada e provada ao vivo **só em
homologação** — produção ainda não tem equivalente (ver tabela
abaixo). Exclusão é sempre
REAL (hard delete) — nunca soft-delete recuperável.

**Infraestrutura de limpeza agendada — hoje SÓ em homologação**
(provisionada e provada ao vivo na continuação do Gate 6.6-E; produção
ainda não tem equivalente):

| Recurso | Nome (homologação) | Observação |
|---|---|---|
| Cloud Run Job | `ede-artefatos-limpeza-homolog` | mesma imagem de runtime, fixada por DIGEST (nunca `:latest`); comando trocado para `python scripts/limpar_artefatos_agendado.py --json` |
| Cloud Scheduler | `ede-artefatos-limpeza-homolog-horaria` | `0 * * * *` (UTC), OAuth, aciona `jobs:run` |
| Service account | `ede-artefatos-limpeza-homolog` | **só** `roles/storage.objectAdmin` escopado ao bucket de artefatos + `roles/run.invoker` no próprio Job; **nenhuma autoridade de assinatura** (a limpeza nunca assina URL), nenhuma chave JSON |

IAM pendente, **não aplicada nesta rodada** (Gate 6.6-E §41 — nenhuma
alteração de IAM da service account de runtime corrente antes de um
passo controlado e explicitamente aprovado):

* `roles/storage.objectAdmin` escopado **só** ao bucket
  `ede-legal-mcp-01-artefatos-efemeros` (upload, leitura de metadado
  para assinatura, exclusão, listagem para limpeza) — nunca papel de
  projeto;
* `roles/iam.serviceAccountTokenCreator` de
  `ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com` NELA MESMA
  (auto-impersonation, necessário e suficiente para `signBlob` sem
  arquivo de chave);
* IAM própria do mecanismo de agendamento escolhido (Cloud Scheduler +
  alvo invocável), a definir junto do provisionamento desse mecanismo.

**Verificado AO VIVO, de ponta a ponta, na continuação do Gate 6.6-E**
com uma service account de homologação dedicada (`ede-artefatos-
homolog`) — criada, usada e **removida ao final** (nenhuma IAM
temporária permanece; nenhuma IAM de produção foi tocada): upload
multipart real, `signBlob` real, download por URL V4 assinada real com
`Content-Type`/`Content-Disposition` corretos, identidade de SHA-256
entre renderer/objeto/download, negação de acesso não assinado antes e
depois do upload, expiração real (TTL curto de teste, caminho interno
nunca exposto no schema público), limpeza oportunista real (objeto
antigo removido, objeto recente preservado), limpeza por falha de
assinatura real (upload real + exclusão real do órfão), e **hard
delete real completo**: objeto some da listagem autenticada, a URL
assinada emitida antes da exclusão passa a devolver 404, acesso não
assinado continua negado, `gcloud storage ls --soft-deleted` para o
objeto devolve vazio, e não há geração não corrente possível
(versionamento desligado). Nenhum item permanece só estrutural/
unitário.

## Homologação permanente — `ede-mcp-homolog` (Gate 6.6-F)

Superfície **permanente** de homologação, internet-facing, separada de
produção em serviço, identidade, Resource OAuth e IAM. Serve à prova
server-side (Fase 1, **PASS**) e aos testes reais com Claude/ChatGPT
(Fase 2, **pendente**). Não é produção: nenhum advogado usa este
endereço, e a ativação v2 em produção continua exigindo autorização
própria.

| Item | Valor |
|---|---|
| Serviço Cloud Run | `ede-mcp-homolog` (`southamerica-east1`), labels `gate=6-6-f`, `status=homolog-candidate` |
| URL canônica / Resource | `https://ede-mcp-homolog-269134711029.southamerica-east1.run.app/mcp` |
| Imagem (candidato canônico) | `southamerica-east1-docker.pkg.dev/ede-legal-mcp-01/ede-mcp/mcp-server@sha256:14f493a0704b4fdbe078158e087463f7c32d3a532ab3cd03a6ae9cfb7e0836a3` (commit `b20c2cf`, VERSION `0.15.0`) |
| Revisão | `ede-mcp-homolog-00005-8mp` |
| Service account | `ede-mcp-homolog-runtime@ede-legal-mcp-01.iam.gserviceaccount.com` — dedicada, **nunca** a SA de produção |
| Invoker | `allUsers` (`roles/run.invoker`) — só depois de provar OAuth obrigatório; a camada de aplicação recusa tudo sem Bearer válido |

**OAuth separado (Resource Descope próprio, mesmo projeto Descope):**

| Variável | Valor |
|---|---|
| `EDE_MCP_AUTH_ENABLED` | `true` (e, desde o hardening acima, obrigatório por código — o serviço não sobe sem ele) |
| `EDE_MCP_RESOURCE` | `https://ede-mcp-homolog-269134711029.southamerica-east1.run.app/mcp` |
| `EDE_MCP_ISSUER` | `https://api.descope.com/v1/apps/agentic/P3JJtIbHdYGjY2UYLFS04lMD23Ul/RS3Jhx0LU7dmcRV5GsKBNuZjj15nK` |
| `EDE_MCP_JWKS_URI` | `https://api.descope.com/P3JJtIbHdYGjY2UYLFS04lMD23Ul/.well-known/jwks.json` (do projeto, compartilhado) |
| `EDE_MCP_REQUIRED_SCOPES` | `ede:health` (`ede:legal` exigido por ferramenta, igual a produção) |
| `EDE_MCP_CANONICAL_HOST` | `ede-mcp-homolog-269134711029.southamerica-east1.run.app` |

Resource Descope de homologação: `RS3Jhx0LU7dmcRV5GsKBNuZjj15nK`, criado
manualmente pelo titular no console (nenhuma Management Key, client
secret ou access key). CIMD habilitado (approved domains `*`), DCR
habilitado, espelhando produção. O JWKS é do projeto, então a
separação entre ambientes está no `iss` (um Resource por ambiente) e no
`aud` — provado ao vivo: token de produção válido recusado pelo homolog
com `motivo=issuer_invalido`; token de homolog recusado por produção.

**Modelo Oficial e artefatos:** mesmas variáveis congeladas de
produção para o Modelo Oficial (bucket/objeto/geração
`1789696822240267`/SHA-256 acima); `EDE_ARTEFATOS_GCS_BUCKET=
ede-legal-mcp-01-artefatos-efemeros`, `EDE_ARTEFATOS_SIGNER_SA=
ede-mcp-homolog-runtime@…` (auto-impersonation).

**IAM da SA de homolog (mínima, nenhum papel de projeto):**
`roles/storage.objectViewer` só no bucket do Modelo Oficial;
`roles/storage.objectAdmin` só no bucket de artefatos;
`roles/iam.serviceAccountTokenCreator` sobre ela mesma (`signBlob`
keyless). A SA de runtime de produção **não** recebeu nada neste gate.

**Entrega e retenção:** a política da seção "Artefatos efêmeros" acima
vale integralmente — URL V4 de 24h, hard delete, limpeza oportunista +
agendada horária (`ede-artefatos-limpeza-homolog`), lifecycle de 2 dias
como backstop assíncrono. O homolog compartilha o bucket e a limpeza
agendada já provados no Gate 6.6-E.

## Confirmação do hostname determinístico

O valor de `EDE_MCP_RESOURCE`/`EDE_MCP_CANONICAL_HOST` acima é o
**esperado**, derivado do mesmo padrão já observado em produção real
neste projeto (`ede-mcp-staging-269134711029.southamerica-east1.run.app`
e o serviço de prova descartável, ambos determinísticos e confirmados).
A confirmação final de que `ede-mcp` (sem sufixo de revisão) resolve
para esse hostname exato é **critério de aceite do Gate 6.3-D3.5**
(criação do serviço candidato) — este documento não declara isso como
fato consumado antes da criação real do serviço.
