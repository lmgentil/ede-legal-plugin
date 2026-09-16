# ADR-0016 — OAuth de produção do EDE MCP Server (Descope, Resource `run.app`)

* **Status:** Aceito
* **Data:** 2026-09-16
* **Relacionado:** ADR-0015 (fronteira Core/Adapter/MCP), ADR-0009
  (Modelo Oficial externo), ADR-0008 (distribuição/versão); SPEC-0001;
  Gates 6.3-D0c Fase 2B (interoperabilidade viva com Claude e ChatGPT),
  6.3-D1 (desenho da migração OAuth de produção), 6.3-D1.1 (decisão da
  URL canônica) e 6.3-D2 (esta implementação de repositório).

> **Escopo desta ADR.** Ela registra decisões de ARQUITETURA e a
> implementação de repositório feita no Gate 6.3-D2. Ela **não** autoriza
> e **não** descreve como concluída nenhuma mutação de nuvem: o serviço
> `ede-mcp` de produção não existe, nenhum Resource Descope de produção
> foi criado, `ede-mcp-staging` não foi tocado. Ver "Dívida de migração".

---

## Contexto

### RNF-PLUG-AND-PLAY-001

O EDE é distribuído a advogados, não a operadores de infraestrutura
(CLAUDE.md §25: "o advogado usuário do plugin não deverá precisar
conhecer Git"). O mesmo princípio vale para o MCP remoto: conectar o EDE
a um host MCP não pode exigir que o advogado gere chave, cole token,
configure `gcloud`, edite JSON de credencial ou entenda IAM. O requisito
é *plug and play*: informar a URL do servidor e autenticar-se pelo fluxo
normal do host.

Isso elimina, por si só, qualquer desenho baseado em segredo
pré-compartilhado distribuído junto do plugin, e é a razão de fundo pela
qual o EDE precisa de OAuth de verdade em vez de uma chave de API.

### A distinção que motivou tudo: alcançável por rede != anônimo na aplicação

`ede-mcp-staging` hoje é protegido por **IAM do Cloud Run**: sem um ID
token do Google aceito pelo IAM, a conexão não se estabelece. Isso
protege o endpoint, mas é autorização de **INFRAESTRUTURA** — responde
"quem pode abrir conexão com este serviço", nunca "quem pode executar o
quê dentro do EDE".

Consequência que precisa ficar registrada de forma inequívoca:

> **Identidade de infraestrutura do Google Cloud NUNCA é autorização de
> aplicação EDE.**

Um principal que satisfaça o IAM do Cloud Run é, do ponto de vista da
aplicação, **anônimo**. Sem OAuth de aplicação, o EDE não tem como
distinguir advogado de robô de CI, nem como negar a um deles uma
operação jurídica. Por isso a camada OAuth desta ADR não substitui o
IAM nem é substituída por ele: são camadas independentes e
complementares.

### Prova viva — Claude e ChatGPT (Gate 6.3-D0c Fase 2B)

A escolha de arquitetura não foi feita no papel. O Gate 6.3-D0c executou
interoperabilidade **ao vivo** contra os dois hosts MCP que importam para
o produto, e os dois se conectaram e operaram o servidor com sucesso:

* **Claude** — conexão viva comprovada;
* **ChatGPT** — conexão viva comprovada.

Dois achados dessa prova governam decisões de código nesta ADR:

1. **Nenhum dos dois clientes envia `Origin` de navegador.** Uma política
   que exigisse `Origin` quebraria os dois hosts reais do produto. Daí a
   política de Origin adotada adiante (ausente => segue para o OAuth).
2. **O hostname precisa ser determinístico.** O cliente fixa a URL do
   Resource; um endpoint cujo hostname mude quebra a configuração já
   salva pelo usuário e invalida a audience dos tokens em circulação.

O registro detalhado dessas execuções vive nos transcritos dos gates
6.3-D0c/D1/D1.1, fora deste repositório. Esta ADR registra as
CONCLUSÕES que passaram a governar o código; ela não reproduz evidência
que não esteja aqui.

---

## Decisão

### 1. EDE é Resource Server; Descope é o Authorization Server

O EDE **não** implementa Authorization Server. Não emite token, não
expõe `/authorize` nem `/token`, não guarda client secret, não faz
registro dinâmico de cliente. Ele verifica tokens emitidos por terceiro e
expõe Protected Resource Metadata (RFC 9728) apontando para esse
terceiro.

**Descope selecionado** como Authorization Server.

**WorkOS rejeitado.** Motivo registrado no Gate 6.3-D1: o modelo comercial
e de empacotamento do WorkOS não se ajusta ao perfil de custo e de
escala do EDE — um plugin jurídico de base pequena de usuários, sob
`RNF-CUSTO-001` (ver adiante). A rejeição foi de ADEQUAÇÃO AO PRODUTO,
não de qualidade técnica do WorkOS.

### 2. Fluxos de autorização

* **Humano (advogado): `authorization_code` + PKCE.** É o fluxo que
  Claude e ChatGPT conduzem sozinhos, e é o que satisfaz
  `RNF-PLUG-AND-PLAY-001` — o advogado faz login, não configura
  credencial.
* **Máquina (CI):** autorização de máquina própria, com identidade e
  escopos próprios, nunca reaproveitando credencial de humano.

Uma consequência de segurança está codificada em
`mcp_server/auth_logging.py`: **o EDE não classifica um principal como
"humano" ou "M2M" sem uma claim assinada que estabeleça isso.** O
contrato de token desta etapa não estabelece grant type, então nenhum
campo de telemetria existe para ele e nenhuma classificação é inferida a
partir de `sub`, `azp` ou formato de `client_id`.

### 3. URL canônica: `run.app` nativo e determinístico (Gate 6.3-D1.1)

O Resource canônico inicial de produção é o hostname **nativo do Cloud
Run**, determinístico, do futuro serviço `ede-mcp`, na forma conceitual:

```text
https://ede-mcp-<PROJECT_NUMBER>.southamerica-east1.run.app/mcp
```

**Domínio customizado fica explicitamente adiado** — não rejeitado,
adiado — até que seja pedido. O ganho de um domínio próprio (independência
de fornecedor na identidade OAuth) não compensa, neste momento, o custo
de DNS, certificado e load balancer sob `RNF-CUSTO-001`.

**`ede-mcp-staging` permanece staging e NUNCA se torna a identidade OAuth
permanente.** Produção será um serviço Cloud Run separado.

Como o serviço de produção ainda não existe, **o URI final não é
hardcoded no código**: `mcp_server/auth_config.py` o recebe em runtime
(`EDE_MCP_RESOURCE`) e valida. Fixar agora um URI de um serviço
inexistente seria inventar identidade.

### 4. Exatamente um Resource anunciado; audience exata

* O PRM anuncia **um** Resource, sempre — nunca uma lista, nunca o
  hostname alternativo que o Cloud Run também roteia.
* A validação de audience exige **pertinência exata de conjunto**. São
  rejeitados: audience ausente, malformada, não relacionada,
  correspondência por substring, por prefixo, só por hostname, e
  curinga. Não existe audience coringa em nenhum ponto da configuração.
* O Host aceito é **somente** o host canônico derivado do Resource.
  Roteamento não é identidade: o Cloud Run pode entregar requisições de
  um hostname alternativo, e elas são recusadas (421).

### 5. Mecanismo de migração de audience (dívida controlada)

Trocar `run.app` por domínio customizado no futuro significa trocar a
identidade do Resource — e tokens já emitidos carregam a audience
antiga. Para que essa troca não exija rearquitetar o verificador, ele
aceita uma **lista** de audiences autorizadas.

Travas que impedem esse mecanismo de virar afrouxamento:

* a operação normal tem **exatamente uma** audience, derivada do
  Resource canônico;
* mais de uma audience só existe se declarada **explicitamente**;
* cada entrada passa pela mesma validação do Resource canônico;
* o Resource canônico precisa estar contido na lista;
* **o PRM continua anunciando um único Resource**, mesmo durante a
  migração;
* a condição fica **visível na telemetria de startup**
  (`migracao_audiencia`);
* nenhum alargamento acontece por omissão, e curinga é recusado.

### 6. Escopos: autenticação e autorização são camadas distintas

* `ede:health` — funcionalidade operacional/sintética/health. **Não
  autoriza** operação jurídica do Core.
* `ede:legal` — reservado à funcionalidade jurídica protegida. **Nenhuma
  tool `ede:legal` é implementada neste gate.**

Nenhum principal recebe `ede:legal` por ter autenticado com sucesso.

A exigência acontece em duas camadas: a base do transporte
(`AuthSettings.required_scopes`, hoje `ede:health`, exata porque toda a
superfície exposta é operacional) e a exigência **por ferramenta**
(`mcp_server/scope_policy.py`), que é o que carregará `ede:legal`.
`tools/list` é filtrado deterministicamente pelo mesmo mapa que protege o
dispatch — usando `ServerMiddleware`, mecanismo de primeira classe do SDK
MCP 2.2.0, sem modificação invasiva de framework e sem inventar
comportamento que o SDK não ofereça.

### 7. Política de Origin e Host

* **`Origin` ausente => segue para a validação OAuth.** Exigir `Origin`
  quebraria Claude e ChatGPT, conforme a prova viva do Gate 6.3-D0c.
  Quem decide nesse caso é o OAuth, não o transporte.
* **`Origin` presente e inesperada => recusada** (403). A proteção contra
  DNS rebinding continua valendo para chamador de navegador.
* **Nunca `*`.** Curinga de Origin é recusado na validação da
  configuração.
* **Host** aceito é somente o canônico (421 caso contrário).

### 8. Fronteira de log

Telemetria de segurança é **somente metadado**, garantida por allowlist
FECHADA de campos (`mcp_server/auth_logging.py`): emitir um campo fora
dela levanta exceção e o evento não sai. Nunca são registrados JWT bruto,
header `Authorization`, refresh token, authorization code, client secret,
cookie, CPF, CNPJ, nome de cliente, número de processo, identificador de
contrato, sinopse, corpo de peça, corpo de documento, prompt ou texto
jurídico gerado. O motivo de falha é vocabulário fechado — nunca texto
livre, que seria o caminho por onde conteúdo do token chegaria ao log.

### 9. Separação preservada: Modelo Oficial e RAG continuam fora

Esta ADR não altera ADR-0009 nem ADR-0015. O MCP permanece adapter fino:
nenhum provisionamento de Modelo Oficial, nenhum RAG jurídico, nenhuma
geração de DOCX, nenhum dado real de cliente. `ede_health` continua
reportando `rag` e `modelo_oficial` como `NOT_CONFIGURED`, e
`contestacao_status` como `NOT_READY`. **A proteção OAuth envolve o
acesso; ela não redefine a prontidão jurídica.**

### 10. RNF-CUSTO-001

O EDE opera sob restrição de custo explícita: base pequena de usuários,
sem receita de escala para sustentar infraestrutura permanente cara. Daí
decorrem, nesta ADR: `run.app` nativo em vez de load balancer + domínio
(adiado); Descope em vez de WorkOS; nenhuma dependência nova no
container (ver adiante); e Cloud Run escalando a zero em vez de
infraestrutura sempre ligada.

### 11. Dependências

**Nenhum pacote novo entra na imagem.** `pyjwt[crypto]` **já era**
dependência direta do próprio `mcp==2.2.0`
(`Requires-Dist: pyjwt[crypto]>=2.10.1`), e `httpx2` também. O que mudou
foi a DECLARAÇÃO: `mcp_server/token_verifier.py` importa `jwt`
diretamente, então a dependência deixou de ser transitiva e passou a ser
pinada em `mcp_server/requirements.txt`. Depender implicitamente da
árvore de outro pacote para um módulo de SEGURANÇA seria frágil.

Deliberadamente ausentes: framework web próprio, pacote de Authorization
Server, SDK de nuvem, RAG, DOCX.

### 12. Requisito de rollback

A ativação do OAuth em produção precisa ser reversível sem reconstrução
de imagem: a camada é ligada por configuração
(`EDE_MCP_AUTH_ENABLED` + variáveis do Resource/issuer/JWKS), e o Cloud
Run permite reverter para a revisão anterior por digest. O que **não** é
reversível por acidente: configuração pela metade — variável de auth
presente com a camada desligada faz o servidor **recusar subir**, em vez
de degradar para acesso anônimo.

---

## Alternativas consideradas

* **Chave de API pré-compartilhada distribuída com o plugin.** Rejeitada:
  viola `RNF-PLUG-AND-PLAY-001` (o advogado teria de configurar
  credencial) e versionaria segredo (CLAUDE.md §18).
* **Tratar o IAM do Cloud Run como a camada de autorização do EDE.**
  Rejeitada: é autorização de infraestrutura. Não distingue principais
  da aplicação nem suporta escopos; ver "alcançável por rede != anônimo
  na aplicação".
* **WorkOS como Authorization Server.** Rejeitada por adequação ao
  produto sob `RNF-CUSTO-001`, não por qualidade técnica.
* **Domínio customizado já nesta rodada.** Adiada (Gate 6.3-D1.1): custo
  de DNS/certificado/load balancer sem ganho imediato. O mecanismo de
  lista de audiences existe exatamente para tornar essa migração
  possível depois, sem rearquitetura.
* **Reaproveitar `ede-mcp-staging` como identidade de produção.**
  Rejeitada: staging e produção precisam de identidades OAuth distintas;
  um token de staging jamais deve valer em produção.
* **`PyJWKClient` da própria PyJWT para o cache de JWKS.** Rejeitada: é
  síncrono (urllib) dentro de um servidor async, e não expõe controle
  sobre a política de cache exigida (TTL, limite de chaves, refresh
  limitado por `kid` desconhecido, sem fail-open além do TTL).

---

## Consequências

* Sem token OAuth de aplicação válido **não há dispatch protegido** — e
  isso é provado, não afirmado: a suíte compara um contador de dispatch
  antes e depois de cada caso negativo (`tests/test_mcp_oauth.py`).
* O contrato de health permanece o baseline de produção/staging
  (`service_status=READY`, `contestacao_status=NOT_READY`, `rag` e
  `modelo_oficial` `NOT_CONFIGURED`, `version` = arquivo `VERSION`).
* A camada é **opt-in** neste gate. Com ela desligada, o comportamento é
  exatamente o das Etapas 6.1/6.2 e o startup **declara** que não há
  autorização de aplicação — estado conhecido, nunca disfarçado.
* O teste local é sintético e **não substitui** o gate posterior com
  Resource Descope real: ele prova semântica de implementação, não
  interoperabilidade com o emissor de verdade.

### Dívida de migração (nada disto foi feito)

1. Criar o serviço Cloud Run `ede-mcp` de produção (separado de
   `ede-mcp-staging`) e capturar o `run.app` determinístico real.
2. Criar o Resource Descope de produção, com os escopos `ede:health` e
   `ede:legal`, e obter issuer e JWKS URI reais.
3. Injetar `EDE_MCP_AUTH_ENABLED` e as variáveis do Resource/issuer/JWKS
   na revisão de produção.
4. Validar ponta a ponta com Claude e ChatGPT reais contra o Resource
   Descope real (o harness sintético não cobre isso).
5. Decidir a política de exposição pública do serviço de produção
   (hoje o staging depende de IAM do Cloud Run).
6. Quando houver domínio customizado: usar a lista explícita de
   audiences, migrar, e voltar a **uma** audience ao fim da janela.
