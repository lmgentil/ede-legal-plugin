# ADR-0019 — Redesenho da entrega de artefato entre hosts MCP

* **Status:** Candidato implementado e **verificado ao vivo** (Gate
  6.6-E, continuação) — Candidata A (objeto GCS efêmero + URL V4
  assinada) implementada em `scripts/artifact_storage.py`, VERSION
  `0.15.0`, com suíte de unidade completa (transporte fake, sem rede) e
  prova real COMPLETA contra GCP (upload, `signBlob`, download
  assinado, identidade de bytes/SHA-256 fim a fim, negação de acesso
  não assinado, expiração, limpeza oportunista, limpeza por falha de
  assinatura, e HARD DELETE — todas verificadas ao vivo contra o bucket
  real, com IAM de homologação temporária criada, usada e removida ao
  final; ver "Implementação (Gate 6.6-E)" e "Retenção" abaixo).
  Janela de autorização de download revisada de 15 minutos para
  **24 horas** por decisão explícita do usuário nesta continuação;
  retenção normal alvo de ~24-25h sustentada por um mecanismo de
  limpeza **agendado, provisionado em homologação e provado ao vivo**
  (Cloud Scheduler horário -> Cloud Run Job sobre a mesma imagem
  imutável -> hard delete), incluindo a prova de que uma execução
  agendada que falha não altera artefato não elegível. **Não ativado em
  produção**: a revisão corrente
  (`ede-mcp-00020-gum`) não tem `EDE_ARTEFATOS_GCS_BUCKET`/
  `EDE_ARTEFATOS_SIGNER_SA` configuradas, e a IAM de runtime necessária
  não foi concedida (Gate 6.6-E §41 — mutação de IAM de produção fica
  para um passo controlado e explicitamente aprovado à parte). Sem
  tag Git, sem release, sem rollout para advogados.
* **Data:** 2026-09-22 (proposta) — implementação candidata Gate 6.6-E,
  mesma data
* **Relacionado:** ADR-0018 (finalizador MCP remoto — Decisão 5 é o
  mecanismo de entrega v1 que este documento avalia substituir/
  complementar); ADR-0017 (Arquitetura A′ — precedente de bucket
  privado, generation pinning e verificação SHA-256 para o Modelo
  Oficial, reaproveitado aqui só como padrão de desenho, nunca o mesmo
  bucket); ADR-0009 (Modelo Oficial externo); `docs/PENDENCIAS.md`
  PEND-012 (entrega nativa falhou nos dois clientes) e PEND-014 (esta
  avaliação); Gate 6.6-D (evidência viva que motivou este documento).

> **Escopo desta ADR.** Ela avalia arquiteturas candidatas para
> substituir ou complementar a Decisão 5 da ADR-0018
> (`EmbeddedResource`/`BlobResourceContents` inline). Ela não decide
> qual candidata será adotada, não altera nenhuma decisão da ADR-0018,
> e não autoriza implementação. A implementação, se e quando aprovada,
> é um gate próprio (numeração a definir, ex. Gate 6.7), com sua própria
> prova viva contra os hosts reais — mesma disciplina do Gate 6.6-D.

## Contexto

O Gate 6.6-D (`CHANGELOG.md`, seção "Evidência viva — Gate 6.6-D")
testou `ede_finalizar_peca` ao vivo contra os dois hosts MCP que
importam para o produto e encontrou, em ambos, o mesmo padrão: o
servidor está correto (validação produção-final, render determinístico
do Modelo Oficial, mesmo SHA-256 do documento nas duas chamadas com o
mesmo payload) e a Decisão 5 (`EmbeddedResource` inline, base64,
`annotations.audience: ["user"]`) não chega ao usuário de forma nativa:

* **ChatGPT** — a UI não expõe a URI `attachment://` do
  `EmbeddedResource`; o host recorreu a um canal de arquivos próprio
  para persistir o documento (bytes idênticos ao do servidor, mas não é
  entrega nativa via MCP).
* **Claude** — o cliente recusa explicitamente o tipo de mídia
  (`application/vnd.openxmlformats-officedocument.wordprocessingml.
  document`); nenhum contorno, nenhum byte chega ao usuário. O log de
  requisições confirma que o servidor efetivamente transmitiu o recurso
  completo (tamanho da resposta ≈ inflação base64 esperada do
  documento) — a falha é do cliente, não do transporte.

Isto não é bug de nenhum dos dois clientes nem do renderer: é a v1
inline (desenhada e aceita na ADR-0018 §"Decisão 5" como aposta
deliberada, com v2 já prevista como "condicional (documento crescer com
evidência/imagens, ex. > ~8 MB)") batendo num limite de suporte real que
não tinha como ser conhecido sem prova viva contra hosts reais. A ADR-
0018 permanece correta sobre tudo que testou (Decisões 1-4, 6-8); só a
Decisão 5, especificamente sobre o mecanismo v1 de entrega, está
demonstrada insuficiente pelo Gate 6.6-D.

## Arquiteturas candidatas (nenhuma decidida)

### Candidata A (preferida para avaliação) — objeto GCS efêmero + URL assinada

```text
ede_finalizar_peca
  → DOCX validado e determinístico (pipeline atual, intocado)
  → objeto GCS efêmero, privado, chave opaca aleatória
  → URL HTTPS assinada, curta duração
  → TextContent (metadado) + link clicável para download
```

Requisitos de segurança levantados pelo usuário, mapeados a mecanismos
concretos (nenhum implementado ainda):

| Requisito | Mecanismo candidato |
|---|---|
| Bucket privado | Bucket dedicado, **distinto** do bucket do Modelo Oficial (ADR-0017 Arquitetura A′) — não reaproveitar: um é entrada institucional de longo prazo, o outro é saída efêmera por caso; misturá-los expande o raio de uma eventual falha de configuração no outro |
| Public Access Prevention | `public_access_prevention: enforced`, mesmo padrão já usado no bucket do Modelo Oficial |
| Sem `allUsers`/`allAuthenticatedUsers` | Nenhuma permissão de bucket a identidade pública; acesso só via URL assinada com expiração |
| Chave de objeto opaca | UUID/token aleatório gerado no momento da escrita, sem derivação de nenhum dado de entrada |
| Sem nome de parte, número de processo ou identificador de caso no caminho do objeto | Reforça o requisito acima — a chave opaca já impede isso por construção; nenhum campo de `placeholders`/`estado_processual` participa da composição do path |
| `Content-Type` correto do DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` fixado na escrita do objeto, nunca inferido do cliente |
| SHA-256 calculado pelo servidor | Reaproveita o `hashlib.sha256` já calculado em `scripts/finalizar_peca.py` — nenhum cálculo novo, só um destino adicional para o valor que já existe |
| URL assinada com janela de download definida | V4 signed URL (Cloud Storage), janela de **24 horas** (`TTL_DOWNLOAD_SEGUNDOS`) — valor revisado; ver "Retenção" abaixo para o histórico e o desenho atual |
| Exclusão real (hard delete) do objeto após a janela | Nunca soft-delete recuperável — mecanismo de limpeza dedicado, ver "Retenção" abaixo |
| Sem bytes/base64 do documento em log | Mesma allowlist fechada já vigente (`mcp_server/auth_logging.py`) — o documento nunca passa pelos campos de telemetria hoje ou depois |
| Sem URL assinada em log de longo prazo | A URL assinada (que embute a assinatura como capacidade de acesso — ver trade-off abaixo) nunca entra nos campos de telemetria de aplicação nem é reproduzida em log de requisição de forma legível; se algum log de infraestrutura capturar a query string por padrão da plataforma, isso precisa ser avaliado e, se necessário, suprimido antes da implementação — investigação pendente, não resolvida por este documento |
| Sem arquivo permanente | Sem cópia adicional, sem backup, sem réplica; o objeto GCS efêmero É o único local de armazenamento do artefato fora da memória do processo |
| IAM de runtime de menor privilégio | Nova permissão granular (ex. `roles/storage.objectCreator` + capacidade de assinar URL) só no objeto/prefixo dedicado desta função, nunca `roles/storage.admin` nem acesso ao bucket do Modelo Oficial |

### Candidata B — download autenticado mediado pelo servidor

```text
ede_finalizar_peca
  → DOCX validado e determinístico (pipeline atual, intocado)
  → identificador de download efêmero (nunca o documento em si)
  → TextContent (metadado) + endpoint HTTPS do próprio Resource Server
  → cliente refaz uma requisição autenticada (mesmo Bearer OAuth da
    chamada MCP) para obter os bytes
```

**Avaliação de usabilidade entre clientes, sem presumir que a
propagação de OAuth do navegador/cliente funcione.** Esta candidata
depende de o host (ChatGPT, Claude, ou o navegador do usuário atrás
dele) reapresentar o token Bearer emitido para a sessão MCP numa
requisição HTTP separada e comum — nenhum dos dois hosts documenta,
hoje, um mecanismo padrão para isso (a pesquisa da Etapa 6.6-D nas
páginas da OpenAI Apps SDK não encontrou tal mecanismo para resultados
de ferramenta; o comportamento equivalente do Claude não foi
pesquisado nesta ADR e fica como item aberto). Se o cliente não
propagar o token, o link cai para o mesmo problema que a Candidata A
resolve com uma URL pré-assinada — só que sem a assinatura, a
requisição simplesmente falharia por falta de autenticação, com uma
UX pior (um link que não funciona) em vez de melhor. A vantagem teórica
da Candidata B é não introduzir uma "capacidade portadora" (ver
trade-off abaixo); a desvantagem é depender de suporte de host não
comprovado. **Conclusão preliminar, sujeita a revisão:** a Candidata A
tem caminho de implementação mais previsível porque não depende do
comportamento do cliente para a parte de autenticação — o preço é o
trade-off de capacidade portadora, tratado explicitamente a seguir.
Antes de decidir, vale uma prova de conceito mínima e não autorizada
neste documento sobre se algum dos dois hosts de fato reapresenta o
Bearer da sessão MCP numa requisição de link separada.

## Trade-off explícito — URL assinada como capacidade portadora

Uma URL assinada V4 do Cloud Storage é uma **capacidade portadora**
(*bearer capability*): quem quer que a possua, dentro do prazo de
validade, pode baixar o objeto — não há segunda verificação de
identidade no momento do download. Isto é uma mudança de modelo de
ameaça frente ao mecanismo atual (Decisão 5 da ADR-0018), onde o
Bearer OAuth do titular é verificado a cada chamada MCP, inclusive a
que devolve o documento.

Consequências que uma eventual implementação precisa tratar
explicitamente, não justificar apenas com "TTL curto resolve":

* um link copiado para fora do canal original (encaminhado, colado em
  outro chat, capturado por uma extensão de navegador com acesso à
  página) concede acesso a quem quer que o receba, sem exigir
  credencial nenhuma, enquanto a validade durar;
* logs de rede intermediários (proxy corporativo, extensão de
  navegador, o próprio host MCP) podem capturar a URL completa mesmo
  que o EDE nunca a registre — a duração da janela de validade
  (**24 horas**, decisão explícita do usuário na continuação do Gate
  6.6-E, revisada de um alvo original de 15 minutos) muda o tamanho
  dessa janela, mas nunca a elimina; **24 horas é uma janela de
  exposição ordens de grandeza maior que 15 minutos** — esta ADR não
  suaviza essa diferença: quanto mais longa a validade, maior o tempo
  em que um link vazado (encaminhado, colado em outro chat, capturado
  por proxy/extensão) permanece útil para quem o obtiver;
* a mitigação real não é "não vai vazar", e sim conter o dano: janela
  de validade FIXA e não estendível pelo cliente, uso único quando
  tecnicamente viável (V4 signed URLs do GCS não suportam nativamente
  invalidação após o primeiro uso; simular isso exigiria um passo
  adicional de verificação no servidor, avaliação futura), e exclusão
  real (hard delete, nunca soft-delete recuperável) do objeto assim que
  a janela de download termina — ver "Retenção" abaixo;
* isto é uma aceitação de risco, não uma eliminação — qualquer
  implementação da Candidata A precisa declarar este trade-off ao
  usuário de novo no momento da aprovação de implementação, não só
  aqui.

## Implementação (Gate 6.6-E, 2026-09-22)

Autorização explícita do usuário: implementar a Candidata A, homologar,
**nunca ativar em produção nesta rodada**. Divergência anotada em
ADR-0018 §Decisão 5/"Status histórico": esta implementação vai direto à
URL assinada, sem passar pelo `ResourceLink`/resource template que a
Decisão 5 original cotava como v2 primário — decisão do usuário, não
uma reinterpretação silenciosa desta ADR.

**Código:** `scripts/artifact_storage.py` (Core puro, mesma disciplina
de `legal_readiness.py` — sem SDK de nuvem completo, `google-auth` +
`httpx2`, nenhuma dependência nova). Assinatura V4 construída à mão,
verificada ponto a ponto contra a documentação oficial do algoritmo
(`docs.cloud.google.com/storage/docs/access-control/signing-urls-manually`):
escapamento de `canonical_uri` com `safe="/~"`, escapamento de chave/
valor da query string equivalente a `safe=""`, token literal `"auto"`
no `credential_scope` (não a região real do bucket), linha em branco
entre `canonical_headers` e `signed_headers`. Integrado a
`scripts/finalizar_peca.py` logo após o SHA-256 do documento já
validado (Template Lock/fidelidade/round-trip) — nunca reabre/
reconstrói os bytes. `mcp_server/server.py` não emite mais
`EmbeddedResource`: resposta é sempre um único `TextContent`, com
`download_url`/`expires_at` em sucesso. Dois códigos de erro novos,
vocabulário fechado espelhado em `mcp_server/auth_logging.py` (testado
contra deriva pelo teste já existente): `ARTIFACT_STORAGE_FAILED`,
`ARTIFACT_SIGNING_FAILED`.

**Bucket real (candidato/homologação):** `ede-legal-mcp-01-artefatos-
efemeros`, `southamerica-east1`, `public_access_prevention: enforced`,
acesso uniforme. Nenhuma IAM de runtime de produção foi alterada (§41)
— as duas concessões que a Candidata A precisa (`roles/storage.
objectAdmin` escopado ao bucket; `roles/iam.serviceAccountTokenCreator`
da SA de runtime NELA MESMA) ficam documentadas, não aplicadas.

### Retenção — decisão final (Gate 6.6-E, continuação, "HARD DELETE REQUIRED")

Histórico, preservado deliberadamente (não uma correção silenciosa de
número): a primeira implementação deste gate usou TTL de 15 minutos e
limpeza oportunista com limiar de 30 minutos; uma revisão intermediária
mudou o TTL para 24 horas com limiar de limpeza de 26 horas. A decisão
final do usuário fixa os três conceitos separadamente, e exige exclusão
REAL (nunca soft-delete recuperável):

| Conceito | Valor final | Mecanismo |
|---|---|---|
| **Janela de AUTORIZAÇÃO de download** | 24 horas exatas | `TTL_DOWNLOAD_SEGUNDOS = 86400`, constante fixa, nunca parâmetro do cliente |
| **Elegibilidade para limpeza NORMAL** | Imediatamente ao expirar a janela acima (24h, sem margem) | `LIMPEZA_ELEGIVEL_SEGUNDOS = TTL_DOWNLOAD_SEGUNDOS` |
| **Retenção normal esperada (alvo)** | ~24–25h, nunca prometida como exata | Elegibilidade em 24h + cadência de varredura (ver abaixo) |
| **Exclusão** | SEMPRE real (hard delete) | Soft-delete DESLIGADO neste bucket (`retentionDurationSeconds: 0`, verificado ao vivo); sem versionamento (verificado ao vivo); sem retention policy nem default event-based hold (verificado ao vivo) |
| **Backstop independente** | ~2 dias, assíncrono, sem prazo garantido | Lifecycle `age: 2` (aplicado ao vivo neste bucket) |

**Mecanismo de varredura — por que oportunista sozinha não basta.** A
limpeza oportunista (`artifact_storage.limpar_artefatos_elegiveis`,
disparada por `finalizar_peca.py` a cada sucesso) cobre o caso comum,
mas **nunca garante, sozinha**, que um artefato seja limpo em ~24-25h
durante um período sem tráfego (a última finalização do dia ficaria
armazenada até a próxima, possivelmente no dia seguinte) — achado
explícito do usuário nesta continuação. Por isso o núcleo de limpeza
(`limpar_artefatos_elegiveis`) foi desenhado para ser chamado de duas
formas: oportunisticamente (já implementado) e por um mecanismo de
AGENDAMENTO independente de tráfego, com cadência horária. O segundo
caminho tem um entrypoint standalone,
`scripts/limpar_artefatos_agendado.py`.

**Agendamento provisionado e PROVADO em homologação (autorização
explícita do usuário).** Arquitetura escolhida, a mais simples que o
GCP já oferece para isto e que não exige nenhum serviço HTTP novo:

```text
Cloud Scheduler (0 * * * *, UTC)
  -> run.googleapis.com jobs:run (OAuth, SA dedicada)
  -> Cloud Run Job `ede-artefatos-limpeza-homolog`
  -> MESMA imagem de runtime, só trocando o comando do container:
     python scripts/limpar_artefatos_agendado.py --json
  -> artifact_storage.limpar_artefatos_elegiveis (hard delete)
```

Decisões relevantes: (1) o Job roda a **mesma imagem imutável** do
servidor MCP, fixada por digest — nunca uma segunda implementação de
exclusão fora da imagem de runtime, nunca `:latest`; (2) a identidade
do Job (`ede-artefatos-limpeza-homolog`) tem **apenas**
`roles/storage.objectAdmin` escopado ao bucket de artefatos e
`roles/run.invoker` no próprio Job — **nenhuma autoridade de
assinatura**, porque o caminho de limpeza só lista e exclui, jamais
assina URL; (3) nenhuma chave JSON de service account foi criada —
autenticação por identidade de workload do próprio Cloud Run; (4)
`EDE_ARTEFATOS_SIGNER_SA` é exigida pelo construtor do transporte mas
nunca exercitada por este caminho (pequena aresta de desenho, anotada
aqui em vez de escondida).

**Infraestrutura estritamente homologatória:** Job e Scheduler são
rotulados `gate=6-6-e`/`status=homolog-candidate`, apontam só para o
bucket de homologação, e não têm nenhuma relação com o serviço de
produção `ede-mcp` (que permanece na revisão `ede-mcp-00020-gum`,
VERSION `0.14.0`, 100% do tráfego, sem nenhuma variável
`EDE_ARTEFATOS_*` e com o IAM de runtime intocado).

**Prova real do caminho AGENDADO (sem nenhuma chamada a
`finalizar_peca`).** Três objetos reais foram colocados no bucket de
homologação e o **Cloud Scheduler** foi disparado (`gcloud scheduler
jobs run`), exercitando a cadeia inteira Scheduler -> Job -> limpeza:

| Objeto | Idade (`created_at`) | Esperado | Resultado real |
|---|---|---|---|
| `artifacts/<id>.docx` (stale) | 25h (> 24h) | excluído | **excluído** |
| `artifacts/<id>.docx` (fresh) | 0h | preservado | **preservado** |
| `outros/<id>.docx` (fora do prefixo) | 99h | intocado | **intocado** |

O log da execução agendada traz **só contadores agregados**
(`status=OK; rodadas=1; inspecionados=2; excluidos=1; falhas=0`) —
nenhum nome de objeto, nenhuma URL assinada, nenhum dado de caso.
Depois da execução, sobre o objeto excluído: GET autenticado -> **404**;
a URL assinada emitida ANTES da exclusão (validade de 1h, portanto
ainda dentro da janela) -> **404**, provando que o OBJETO sumiu e não
que a URL apenas expirou; acesso não assinado -> **401**; e a consulta
de versões soft-deletadas é **recusada pelo próprio GCS** com
`HTTPError 400: Soft delete policy is required to list soft-deleted
versions` — prova mais forte que uma lista vazia: sem política de soft
delete no bucket, geração recuperável não pode existir por construção.

**Semântica de falha da execução agendada (verificada ao vivo).** Uma
execução foi propositalmente induzida a falhar (override de variável de
ambiente só na execução, nunca na definição do Job — confirmado depois
que a definição continua íntegra). Resultado: contêiner saiu com código
2, log com erro tipado (`status=ERRO_CONFIGURACAO`) e sem conteúdo
algum; e os dois objetos NÃO elegíveis permaneceram **byte a byte
intactos** — mesma `Generation` e mesmo `Content-Length` antes e
depois. Uma execução agendada que falha não exclui, não altera e não
corrompe nada; o backstop de lifecycle continua ativo
independentemente.

**Backstop de lifecycle, semântica real verificada.** Documentação
oficial (consultada nesta sessão,
`docs.cloud.google.com/storage/docs/lifecycle`): a condição `age` é
avaliada no aniversário exato de criação (não à meia-noite UTC, salvo
`age: 0`), e a ação de exclusão é **assíncrona, sem qualquer garantia
de prazo** ("Your applications shouldn't rely on lifecycle actions
occurring within a certain amount of time after a lifecycle condition
is met"). `age: 2` (2 dias) dá uma elegibilidade mínima de 48h — o
dobro da janela de 24h, com folga de 24h antes mesmo de considerar o
atraso assíncrono — aplicado e confirmado ao vivo neste bucket. Nunca
descrito como "exclusão em 2 dias" — é um piso de elegibilidade, não um
prazo de execução.

**Hard delete: prova real completa contra o bucket ao vivo (não só
unitária).** Com IAM de homologação temporária (criada, usada, e
REMOVIDA ao final — nenhum vestígio permanente), um objeto real foi
criado com `created_at` retroagido para além do limiar de
elegibilidade, uma URL assinada real foi emitida para ele, e
`limpar_artefatos_elegiveis` real (upload/listagem/exclusão reais, sem
fake) foi executada. Confirmado ao vivo, nesta ordem: (1) o objeto
some da listagem autenticada real; (2) a URL assinada emitida
ANTES da exclusão passa a devolver 404 (não apenas "expirada" — o
objeto em si não existe mais); (3) acesso não assinado continua negado
(401, inalterado); (4) `gcloud storage ls --soft-deleted` para o
prefixo do objeto devolve vazio — nenhuma geração recuperável; (5)
sem geração não corrente possível, porque o versionamento do bucket
está desligado (confirmado ao vivo, campo `versioning` ausente do
recurso). Os seis itens que o usuário exigiu como prova de HARD DELETE
foram verificados — nenhum permanece só como garantia estrutural/
unitária.

**Verificação real, COMPLETA (continuação do Gate 6.6-E).** A lacuna
registrada na primeira rodada deste gate ("`signBlob` real não
verificado, bloqueado pelo guard de Permission Grant do harness") foi
fechada nesta continuação, com autorização explícita do usuário para
IAM de homologação temporária: service account dedicada e descartável
(`ede-artefatos-homolog`, nunca a SA de runtime de produção), criada,
usada e **removida ao final** (SA deletada, binding de bucket
removido, confirmado ao vivo). Com ela, `TransporteGcsReal` real (não
um script de assinatura à parte) executou, contra o bucket real:
upload multipart real (200); `signBlob` real via IAM Credentials
(sucesso); download via URL V4 assinada real (200, `Content-Type` e
`Content-Disposition` corretos); **identidade de bytes**
renderizador -> objeto GCS -> download assinado, SHA-256 idêntico nas
três pontas; acesso não assinado negado (401) antes e depois do
upload; prova de expiração real (`assinar_url` com TTL curto de teste,
caminho interno, nunca exposto no schema público — sucesso dentro do
TTL, falha real após expirar); limpeza oportunista real (objeto
propositalmente "envelhecido" via metadado removido, objeto recente
preservado); limpeza por falha de assinatura real (upload real,
assinatura forçada a falhar por um seam de teste controlado, exclusão
real do órfão confirmada); e a prova de HARD DELETE completa (seção
"Retenção" acima). Nenhum item desta lista permanece só estrutural/
unitário — todos têm prova viva.

**Itens em aberto para antes do gate de download ao vivo:**
1. replicar em PRODUÇÃO o agendamento já provado em homologação (Job +
   Scheduler equivalentes, apontando ao bucket de produção quando
   houver), com as concessões próprias — o mecanismo em si já está
   provado, o que falta é a instância de produção;
2. aplicar as duas concessões de IAM à SA de runtime de produção
   (assinatura), como um passo controlado e explicitamente aprovado à
   parte (§41);
3. confirmar se algum log de infraestrutura do Cloud Run/GCS captura a
   query string da URL assinada por padrão da plataforma — mais
   relevante agora, com janela de 24h em vez de 15 minutos;
4. decidir sobre uso único vs. reutilizável dentro da janela de 24h;
5. pesquisar o comportamento do Claude quanto a reapresentar Bearer
   OAuth em requisição separada (Candidata B) — não investigado;
6. medir performance/custo com o backend real em volume de produção
   (estimativas atuais no relatório do Gate 6.6-E combinam medição real
   pontual com preço público de lista, não uso medido em produção).

### Hardening pós-fechamento — corrida entre expiração real da URL e elegibilidade de limpeza

Achado do usuário depois do Gate 6.6-E fechar: `assinar_url()`
capturava seu próprio `datetime.now()` internamente, DEPOIS do upload
já ter terminado. Como assinatura sempre ocorre depois do upload (a
própria latência de rede do envio), a expiração criptográfica real da
URL (`X-Goog-Date + X-Goog-Expires`) ficava sempre um pouco DEPOIS do
`expires_at` gravado no metadado do objeto no momento do upload. Uma
varredura de limpeza (oportunista ou agendada) rodando exatamente
nessa janela — por menor que fosse — poderia excluir o objeto enquanto
a URL emitida para ele ainda era, tecnicamente, criptograficamente
válida: violação direta da invariante "artefato nunca fica elegível
para limpeza antes de sua autorização de download emitida ter
expirado".

**Solução escolhida — instante único compartilhado, não um segundo
campo de metadado.** A alternativa óbvia (gravar `download_expires_at`
a partir do instante REAL de assinatura, com uma escrita de metadado
adicional depois de assinar) foi considerada e descartada por ser mais
complexa sem necessidade: exigiria uma segunda chamada de rede (PATCH
de metadado pós-assinatura), um novo modo de falha (a escrita da
correção falhar depois da assinatura ter funcionado), e ainda deixaria
uma janela — menor, mas real — entre o upload original e essa
correção. A solução implementada é mais simples e fecha a corrida por
construção: `entregar_artefato_efemero` captura `agora` UMA vez e passa
esse MESMO valor como `momento` explícito para `assinar_url()`
(`TransporteArtefato.assinar_url(..., momento=None)`, novo parâmetro
opcional — `None` preserva o relógio interno para quem assina sem
vínculo de metadado, como os próprios testes de expiração deste
módulo). `X-Goog-Date` na URL passa a ser EXATAMENTE o mesmo instante
gravado em `created_at`/`expires_at` — a expiração real da URL e o
`expires_at` do metadado tornam-se o MESMO valor, não uma aproximação
com margem. **Verificado ao vivo** (não só em teste de unidade):
`expires_at` do metadado e `X-Goog-Date + X-Goog-Expires` extraídos da
URL real devolvida pelo pipeline completo bateram exatamente
(`2026-09-24T00:50:37Z` dos dois lados).

`limpar_artefatos_elegiveis` foi ajustada para decidir por `expires_at`
diretamente (nunca recalcular a partir de `created_at` — essa
reconstrução é exatamente o que reabriria a corrida). Metadado ausente
OU malformado é fail-safe: o objeto é ignorado nesta varredura, nunca
excluído por incerteza — o backstop de lifecycle continua sendo a rede
de segurança para esse caso. `LIMPEZA_ELEGIVEL_SEGUNDOS` permanece como
documentação da relação usada para CALCULAR `expires_at` no upload
(`created_at + TTL_DOWNLOAD_SEGUNDOS`), não mais como base de uma
segunda comparação independente na decisão de limpeza.

## Consequências desta ADR

* Código, testes e bucket de homologação existem (Gate 6.6-E); nenhuma
  mudança de produção, IAM de runtime, deploy ou tráfego.
  `ede_finalizar_peca`, o renderer, o Template Lock e a validação
  produção-final permanecem exatamente como o Gate 6.6-C/D os deixou.
* A Decisão 5 da ADR-0018 é HISTÓRICA (v1 rejeitada) a partir deste
  gate — não mais "mecanismo em produção", mas produção continua
  servindo v1 tecnicamente até uma ativação futura explicitamente
  autorizada do v2 (que hoje recusaria toda chamada, por falta de
  configuração — nunca "ativa sozinha").
* PEND-014 (`docs/PENDENCIAS.md`) passa de "em avaliação" para "candidato
  implementado, aguardando prova viva completa (assinatura real) e
  autorização de ativação" — não fecha só com este documento.
