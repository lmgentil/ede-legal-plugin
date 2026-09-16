# ADR-0017 — Ativação de produção do EDE MCP Server (fase OAuth/runtime remoto)

* **Status:** Aceito
* **Data:** 2026-09-17
* **Relacionado:** ADR-0006 (assets institucionais), ADR-0008
  (distribuição/versão), ADR-0009 (Modelo Oficial externo), ADR-0014
  (runtime DOCX autônomo), ADR-0015 (fronteira Core/Adapter/MCP),
  ADR-0016 (OAuth de produção — arquitetura e implementação de
  repositório); CLAUDE.md §13 (clarificação companheira desta ADR);
  Gates 6.3-D2.x (implementação, auditoria, relocalização de
  repositório) e 6.3-D3.0 (plano de ativação de produção, aprovado pelo
  usuário: H1/H2/H3).

> **Escopo desta ADR.** Ela registra a arquitetura de ativação de
> produção **aprovada** para a fase OAuth/runtime remoto (D3.1–D3.7) e
> formaliza o desenho da Arquitetura A′ para a fase jurídica futura
> (D3.8+, **ainda não implementada**). Ela **não** autoriza nenhuma
> mutação de infraestrutura — nenhum serviço `ede-mcp` de produção,
> nenhum bucket, nenhum Resource Descope de produção e nenhuma
> credencial foram criados por este documento ou pelo Gate 6.3-D3.1.
> **Contestação continua não pronta para produção remota** — esta ADR
> não muda esse fato; ver seção "Fronteira jurídica" abaixo.

## Contexto

O Gate 6.3-D2 implementou o EDE MCP Server como Resource Server OAuth
2.0 (ADR-0016), com verificação de token, PRM, escopos e telemetria
totalmente testados de forma sintética. O Gate 6.3-D2.1 a D2.8 auditou
essa implementação, relocalizou o repositório de desenvolvimento para
fora de sincronização em nuvem (`C:\Dev\ede-legal-plugin`) e confirmou,
por evidência direta (leitura de `gcloud`, do workflow e do repositório):

* nenhum Resource Descope de produção existe;
* nenhuma chave privada de service account persiste em lugar algum do
  escopo EDE;
* a autenticação `GitHub Actions → GCP` já usa Workload Identity
  Federation, sem segredo persistido;
* o staging (`ede-mcp-staging`) permanece protegido só por IAM do Cloud
  Run — nunca por OAuth de aplicação;
* existe um serviço de prova descartável (`ede-oauth-proof-disposable`),
  já público e protegido por OAuth de aplicação, que prova
  empiricamente a viabilidade da arquitetura de rede-pública +
  OAuth-de-aplicação antes de aplicá-la ao serviço de produção.

O Gate 6.3-D3.0 produziu o plano de ativação de produção e identificou
decisões que precisavam de aprovação explícita do usuário antes de
qualquer mutação de repositório: a arquitetura A′ do Modelo Oficial (que
tensiona com a redação literal de CLAUDE.md §13), o momento do bump de
`VERSION` e a necessidade de um guard de fail-closed específico para o
nome de serviço de produção. As três foram aprovadas (H1, H2, H3) antes
deste documento.

## Decisão

### 1. Identidade do serviço de produção

* **Nome do serviço:** `ede-mcp` — nunca `ede-mcp-staging` renomeado, e
  nunca reaproveitando a revisão/configuração de staging.
* **Projeto GCP:** `ede-legal-mcp-01` (mesmo projeto do staging e da
  prova descartável — sem criar projeto novo nesta fase).
* **Região:** `southamerica-east1` (mesma do staging; latência e
  jurisdição para o público-alvo brasileiro).
* **Endpoint canônico inicial:** hostname determinístico nativo do
  Cloud Run (`https://ede-mcp-<PROJECT_NUMBER>.southamerica-east1.run.app/mcp`),
  já comprovado pelo padrão do staging e da prova descartável. Domínio
  customizado **não é criado nesta fase** — mecanismo de migração de
  audience já existe em `mcp_server/auth_config.py`
  (`EDE_MCP_ACCEPTED_AUDIENCES`) para viabilizá-lo depois, sem
  reescrever o verificador.

### 2. Modelo de rede e IAM — transição obrigatória

O Cloud Run do serviço de produção **só se torna publicamente invocável
depois que o OAuth de aplicação estiver provado sobre ele, com IAM
ainda privado**. Nunca na ordem inversa. A primeira revisão de um
serviço novo recebe 100% do tráfego automaticamente — por isso a
proteção da janela inicial é IAM privado, não "tráfego zero". Esta ADR
formaliza a exigência; a coreografia exata (login com identidade Google
via `X-Serverless-Authorization` enquanto o `Authorization` continua
livre para o Bearer do Descope, matriz de aceite antes/depois de abrir
`allUsers`) é executada e verificada nos Gates 6.3-D3.5/D3.6 — não
reproduzida aqui.

### 3. Autenticação de aplicação — Descope, EDE como Resource Server

Preservado de ADR-0016, sem alteração de contrato:

* **EDE é Resource Server; Descope é o Authorization Server.** O EDE
  nunca emite token, nunca implementa `/authorize`/`/token`, nunca
  guarda client secret de terceiro.
* **Advogados nunca usam IAM do GCP.** A rede pode ser pública; o
  controle de acesso da aplicação é inteiramente OAuth/Descope.
* **Identidade de infraestrutura do Google Cloud nunca é autorização de
  aplicação EDE** — princípio já registrado em ADR-0016, reafirmado
  aqui porque é exatamente o que a transição da seção 2 precisa manter
  verdadeiro durante toda a janela de ativação.
* O Resource de produção, os escopos (`ede:health` hoje; `ede:legal`
  reservado) e o mecanismo de verificação (RS256, JWKS pinada, audience
  exata, Host/Origin) são os já implementados e testados no Gate 6.3-D2
  — esta ADR não os reabre. O contrato de variáveis de ambiente de
  produção correspondente vive em `docs/mcp-producao-contrato.md`
  (documento companheiro, atualizável sem reabrir esta ADR).

### 4. Produção deve falhar fechado quando o OAuth estiver ausente

Achado do Gate 6.3-D3.0: com todas as variáveis `EDE_MCP_*` ausentes, a
camada OAuth desliga por design (compatibilidade com staging/local —
ADR-0016). Isso é aceitável para staging, mas **nunca** para o serviço
`ede-mcp` de produção: um deploy mal configurado seguido de `allUsers`
exporia o servidor sem autenticação alguma. Esta ADR formaliza a
exigência de um guard amarrado ao nome do serviço de produção
(`K_SERVICE`, injetado pela própria plataforma Cloud Run — nunca
esquecível por omissão de configuração externa); o mecanismo
determinístico está implementado em `mcp_server/auth_config.py` e
coberto por teste (Gate 6.3-D3.1, `tests/test_mcp_oauth.py`).

### 5. Isolamento staging/produção

Staging e produção nunca compartilham: nome de serviço, service account
de runtime/deploy/smoke, Resource/audience Descope, variáveis de
ambiente, ou referência de asset (Modelo Oficial). O workflow de deploy
de produção é um arquivo próprio, distinto de
`.github/workflows/deploy-mcp-staging.yml`, também `workflow_dispatch`
apenas — nunca disparado automaticamente por push. Detalhe operacional
completo (nomes de service account propostos, binding WIF, Environment
do GitHub) é matéria de implementação dos Gates 6.3-D3.4 em diante, não
desta ADR.

### 6. Arquitetura A′ — Modelo Oficial em produção (fase jurídica futura, não implementada)

Formalizada aqui como desenho aprovado; **nenhuma implementação, bucket
ou upload ocorre nesta ADR nem no Gate 6.3-D3.1**.

```text
Cloud Run (ede-mcp)
  + armazenamento privado regional do Modelo Oficial (GCS)
  + corpus jurídico público/versionado embutido na imagem, onde aplicável
```

Contrato obrigatório da aquisição em runtime, quando implementada:

* bucket **privado**, sem acesso público, sem URL assinada, sem ACL de
  objeto;
* **generation pinning** — o runtime lê exatamente a geração do objeto
  configurada, nunca "a mais recente" por convenção implícita;
* verificação de **SHA-256** do objeto lido contra o valor configurado;
* validação de contrato determinística (`validar_contrato_modelo`, já
  existente) antes de qualquer uso;
* **fail-closed** em qualquer falha: sem geração/hash configurados, sem
  acesso ao bucket, hash divergente, ou contrato inválido → `checks.
  modelo_oficial` fica `ERROR`/`NOT_READY`, `contestacao_status` fica
  `NOT_READY`, e nenhuma ferramenta jurídica despacha — a ferramenta
  `ede_health` continua respondendo normalmente;
* **nunca** busca automática, reconstrução, template genérico de
  fallback, ou tratamento da ausência como instalação inválida — ver
  clarificação de CLAUDE.md §13, publicada junto desta ADR;
* IAM de leitura (`roles/storage.objectViewer`) escopado **só a este
  bucket**, concedido só à service account de runtime de produção —
  nunca à de staging.

O corpus jurídico público/versionado (`rag/`, legislação e artefatos
LSA já rastreados no repositório) pode ser embutido na imagem, sob a
mesma disciplina de contrato/SHA-256 já vigente (ADR-0011); a
jurisprudência privada local (`C:\Dev\ede-private\rag\jurisprudencia`,
dados reais de caso) **nunca** é enviada como parte desta ativação —
ver seção "Fronteira jurídica".

### 7. Fronteira jurídica — o que esta ADR não muda

* O raciocínio jurídico (`estrategista-contestacao-ede`,
  `redator-peca-processual-elite`, `humanizer-pt-br`) continua no host
  Claude, exatamente como ADR-0015 decidiu (Opção A). Esta ADR não move
  raciocínio para o MCP.
* O Core determinístico (`scripts/gerar_contestacao.py` e módulos
  correlatos) continua exclusivamente server-side, chamado como
  biblioteca — nunca reimplementado no cliente.
* Documentos brutos do cliente não precisam alcançar o Cloud Run quando
  entradas estruturadas bastam (artefatos já produzidos pelas Skills no
  host) — princípio de fronteira de dados preservado sem alteração.
* Logging de aplicação permanece **somente metadado** (ADR-0016,
  `mcp_server/auth_logging.py`) — esta ADR não abre exceção para
  conteúdo jurídico em log.
* O runtime permanece stateless onde possível (transporte Streamable
  HTTP stateless do SDK MCP 2.2.0).
* **Nenhuma ferramenta jurídica de Contestação é exposta por esta ADR.**
  A progressão de exposição de ferramentas (de `ede_health` até
  `contestacao` determinística sob escopo `ede:legal`) é matéria dos
  Gates 6.3-D3.8 em diante — fora do escopo desta decisão.

### 8. Rollback — princípio de segurança

Em qualquer incerteza sobre a integridade do OAuth de aplicação em
produção: **fechar o acesso público de rede primeiro** (remover
`allUsers`), confirmar que o Cloud Run volta a responder 403 por conta
própria, só então decidir sobre tráfego/revisão. Nunca a ordem inversa.
Este princípio governa o runbook de rollback detalhado nos Gates
6.3-D3.5/D3.6, não reproduzido aqui.

### 9. Requisitos não funcionais preservados

* **RNF-PLUG-AND-PLAY-001** — o advogado autentica pelo fluxo OAuth
  normal do cliente (Claude/ChatGPT); nunca instala Python, nunca
  clona o repositório, nunca configura GCP, nunca maneja credencial de
  infraestrutura.
* **RNF-CUSTO-001** — o dimensionamento inicial do serviço de produção
  (min/max instances, CPU, memória, timeout) é decidido nos Gates de
  implementação (6.3-D3.4 em diante) sob o orçamento de custo já
  estabelecido para a escala-alvo do projeto, não fixado por esta ADR.

## Alternativas consideradas

* **Renomear `ede-mcp-staging` para `ede-mcp`.** Rejeitada: destruiria o
  ambiente de homologação e misturaria configuração/identidade de
  staging com produção — viola o isolamento exigido pela seção 5.
* **Abrir `allUsers` antes de provar o OAuth de aplicação.** Rejeitada:
  inverteria a ordem de segurança da seção 2; é exatamente o cenário que
  o rollback da seção 8 existe para nunca precisar corrigir em
  produção real.
* **Reconstruir/buscar o Modelo Oficial automaticamente quando ausente
  em produção.** Rejeitada — mantém a decisão definitiva de ADR-0009;
  ver clarificação de CLAUDE.md §13.
* **Domínio customizado já nesta fase.** Adiada, não rejeitada em
  definitivo: sem ganho imediato que justifique o custo de DNS/
  certificado/load balancer agora; o mecanismo de migração de audience
  já existe para viabilizá-la depois sem reescrever o verificador.

## Consequências

* Fica registrado, de forma vinculante para os Gates seguintes, que
  produção nunca reutiliza identidade de staging, nunca abre rede
  pública antes de provar OAuth, e nunca trata o Modelo Oficial ausente
  como algo a contornar automaticamente.
* A implementação da Arquitetura A′ (bucket, upload, IAM de leitura,
  aquisição em runtime) fica pendente para o Gate 6.3-D3.8 — esta ADR
  formaliza o contrato, não a implementação.
* `docs/mcp-producao-contrato.md` passa a ser a referência viva do
  contrato de variáveis de ambiente de produção, atualizável
  independentemente desta ADR conforme os Gates de implementação
  avançam (D3.2 preenche os valores reais de issuer/JWKS ainda hoje
  documentados como pendentes).
