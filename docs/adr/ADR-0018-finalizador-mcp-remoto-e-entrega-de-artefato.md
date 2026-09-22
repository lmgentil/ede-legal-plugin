# ADR-0018 — Finalizador MCP remoto: contrato multi-peça e entrega de DOCX

* **Status:** Implementado (Gate 6.6-C — `ede_finalizar_peca` real,
  escopo `ede:legal`, VERSION `0.14.0`) e **ativado em produção de forma
  controlada no Gate 6.6-D**, por promoção explicitamente autorizada:
  revisão `ede-mcp-00020-gum`, VERSION `0.14.0`, digest imutável
  `sha256:63521b143622a3d1f134ff2bc4a008f136046e92a5edbedc3d116fd86e45c427`,
  100% do tráfego; alvo de rollback anterior preservado
  (`ede-mcp-00018-loc`). A ativação existiu só para o teste de
  interoperabilidade viva do Gate 6.6-D: **não foi rollout para
  advogados, release nem tag**. **Gate 6.6-D ENCERRADO como `PARTIAL
  PASS`** (correção do servidor e determinismo do documento comprovados
  nos dois clientes; entrega nativa do artefato falhou nos dois — ver
  "Prova viva" abaixo). Desenho original (Gate 6.6-B) permanece íntegro;
  nenhuma decisão desta ADR foi revista, a Decisão 5 inclusive — sua
  insuficiência frente ao requisito real está registrada, mas a revisão
  em si fica para um gate próprio (ver "Prova viva", PEND-012 e
  PEND-014; avaliação preparatória em ADR-0019, sem implementação).
* **Data:** 2026-09-22 (Gate 6.6-B) — implementação Gate 6.6-C e ativação
  controlada Gate 6.6-D (revisão criada às 15:01:49 UTC), mesma data
* **Relacionado:** ADR-0015 (fronteira Core/Adapter/MCP), ADR-0016/0017
  (OAuth e ativação de produção), ADR-0009 (Modelo Oficial externo);
  Gate 6.5-A/B3/C1-C4 (`ede_preparar_contestacao`, escopo `ede:legal`);
  Gate 6.6-A (renderer do Modelo Oficial, Template Lock, fidelidade
  independente, round-trip, modo produção-final); Gate 6.6-C
  (implementação: `scripts/capability_registry.py`,
  `scripts/finalizar_peca.py`, `mcp_server/server.py::ede_finalizar_peca`)

## Contexto

O EDE MCP hoje expõe duas tools públicas: `ede_health` (escopo
`ede:health`) e `ede_preparar_contestacao` (escopo `ede:legal`), que
prepara o Pacote de Contexto consumido pelo host (Claude/ChatGPT) para
redigir. O Gate 6.6-A endureceu e aceitou o renderer determinístico do
Modelo Oficial (`docx_block_engine.gerar_peca_com_blocos`) — composição de
blocos/zonas, renumeração, Template Lock, verificação independente de
fidelidade (`docx_fidelidade_independente.py`) e round-trip
(`docx_round_trip.py`) — mas o renderer só roda localmente; nenhuma tool
MCP o expõe.

O objetivo de produto é:

```
advogado no Claude/ChatGPT
  → rascunho estruturado aprovado (host)
  → finalização determinística do EDE
  → Modelo Oficial exato
  → DOCX baixável
```

sem Python local, template, chaves ou infraestrutura do lado do advogado.

Esta ADR registra as decisões de arquitetura para esse finalizador —
**auditoria e desenho, sem ativação pública** (Gate 6.6-B). Nenhuma tool
nova foi registrada; nenhum bucket, escopo ou revisão de produção foi
criado ou alterado.

## Decisão 1 — Modelo de capacidade multi-peça (não hardcoded em Contestação)

O EDE deve crescer para Recurso Inominado, Contrarrazões, Embargos de
Declaração, execução/cumprimento, e múltiplos modelos institucionais
dentro de cada família de peça (ex.: `contestacao.irregularidade_consumo`,
`contestacao.corte_indevido`). O contrato público não pode ser desenhado
em torno de um único modelo.

Adota-se um identificador de capacidade estável, no formato
`<familia>.<modelo>` (snake_case, minúsculo, sem acento — mesma convenção
já usada em `estado_processual`/`decisoes_blocos`):

```
contestacao.irregularidade_consumo   (única capacidade hoje pronta)
contestacao.ligacao
contestacao.corte_indevido
contestacao.negativacao_indevida
recurso.recurso_inominado
recurso.contrarrazoes_recurso_inominado
recurso.embargos_de_declaracao
```

Um **registro de capacidades** (server-side, nunca exposto por completo ao
cliente) declara, por capacidade:

| Campo | Finalidade |
|---|---|
| `capability_id` | identificador estável (`familia.modelo`) |
| `piece_family` | agrupamento de produto (`contestacao`, `recurso`, …) |
| `institutional_model_id` | referência interna ao Modelo Oficial/catálogo/schema daquele modelo (nunca o path/SHA/bucket — isso é autoridade de infraestrutura, Decisão 3) |
| `status` | `READY` \| `NOT_READY` \| `DEPRECATED` |
| `schema_version` | versão do contrato de placeholders/blocos daquele modelo |
| `official_model_authority` | referência interna (não pública) ao mecanismo de aquisição do ADR-0009/ADR-0017 |
| `renderer_available` | booleano — o renderer determinístico existe e passou pela auditoria do Gate 6.6-A para este modelo |
| `required_decisions` | lista dos blocos `decision_mode` humano/estrategista daquele catálogo |
| `production_final_ready` | booleano — `validar_modo_producao_final` (ou equivalente) existe e está calibrado para este modelo |

A **Etapa 5 (INV-GATE-CONTESTACAO)** permanece em vigor: só
`contestacao.irregularidade_consumo` é implementada; o registro existe
como *contrato*, não como convite a generalizar prematuramente
(`piece_registry`/`piece_factory` genéricos continuam vedados até
liberação expressa do usuário — CLAUDE.md §27).

## Decisão 2 — Um finalizador genérico, não um por peça

```
ede_finalizar_peca
```

em vez de `ede_finalizar_contestacao_irregularidade`. Um tool novo por
modelo institucional obrigaria reautorização OAuth e uma nova entrada no
PRM a cada capacidade nova — inviável para ~40 advogados x N modelos.

### Contrato de requisição (conceitual)

```
{
  "capability_id": "contestacao.irregularidade_consumo",
  "placeholders": { "<NOME>": "<valor>", ... },
  "block_decisions": { "<BLOCO_ID>": "INCLUIR" | "EXCLUIR", ... },
  "estado_processual": { "<FATO>": true | false | "INDETERMINADO", ... },
  "mode": "production_final"
}
```

Nunca aceito do cliente: bucket, objeto GCS, geração, hash do template,
path local, URL pública de template. O cliente escolhe uma **capacidade
jurídica**, nunca um arquivo (Decisão 3). `mode` existe só para tornar o
contrato explícito e auditável — o finalizador **público** só aceita
`"production_final"` (Decisão 4); `"acceptance"` é uso interno/teste, nunca
alcançável pelo transporte público.

### Contrato de resposta (conceitual)

```
{
  "status": "OK" | "REFUSED",
  "capability_id": "...",
  "document_sha256": "...",
  "document_size": 1794330,
  "filename": "contestacao-<opaco>.docx",
  "artifact": { ... mecanismo de entrega, Decisão 5 ... },
  "warnings": [ ... ]
}
```

Nunca exposto: nome do bucket, geração GCS, path privado do Modelo
Oficial, qualquer credencial.

### Contrato de erro (código fechado, nunca stack trace/infra)

```
OFFICIAL_MODEL_NOT_READY
MISSING_REQUIRED_FIELD
MISSING_BLOCK_DECISION
SYNTHETIC_SENTINEL_REJECTED
INPUT_VALIDATION_FAILED
TEMPLATE_LOCK_FAILED
ROUND_TRIP_FAILED
RENDER_FAILED
ARTIFACT_DELIVERY_FAILED
```

## Decisão 3 — Nunca aceitar template arbitrário do cliente

O cliente escolhe `capability_id`; o servidor resolve, internamente, qual
Modelo Oficial/catálogo/schema usar (mesmo mecanismo do ADR-0009/ADR-0017
— geração GCS pinada, SHA-256 verificado, fail-closed). Qualquer tentativa
de especificar template/bucket/objeto/hash/path/URL é rejeitada
estruturalmente (o schema Pydantic da requisição nem declara esses campos
— não é uma checagem em runtime que pode ser esquecida, é ausência de
campo).

## Decisão 4 — O finalizador público só fala modo produção-final

`validar_modo_producao_final` (Gate 6.6-A) — ou o equivalente por
capacidade — roda sempre. Recusa (fail-closed, nunca "melhor esforço") se:
Modelo Oficial não READY; placeholder sempre-visível ausente; placeholder
block-local ausente com o bloco dono INCLUIR; decisão humana/estrategista
ausente para bloco ativo; sentinela de aceite (`[PENDENTE:`, `SINTÉTICO DE
ACEITE`) presente; validação determinística de rascunho falhar; Template
Lock pré-render falhar; fidelidade independente pós-render falhar;
round-trip falhar; DOCX gerado malformado.

O modo de aceite/teste (que permite sentinelas explícitas, como o
artefato do Gate 6.6-A) nunca é alcançável pelo transporte público — existe
só para o pipeline de teste interno, nunca como parâmetro que um cliente
remoto possa setar para "relaxar" a validação.

## Decisão 5 — Entrega do artefato: blob inline (v1), sem bucket público

Ver detalhamento completo na resposta do Gate 6.6-B (não duplicado aqui).
Resumo da decisão:

- **v1 (tamanho atual, ~1,8 MB):** `EmbeddedResource` +
  `BlobResourceContents` (blob base64 inline na resposta da tool),
  `annotations.audience=["user"]` para sinalizar ao cliente que o
  conteúdo é para o usuário baixar, não para o modelo raciocinar sobre
  ele. Overhead medido: ~1,33x (base64), sem armazenamento adicional, sem
  problema de estatelessness do Cloud Run (nada persiste entre
  instâncias), sem superfície de autorização nova.
- **v2 condicional (documento crescer com evidência/imagens, ex. > ~8 MB):**
  arquitetura de dois passos com `ResourceLink` apontando para um URI
  próprio (`ede://artifact/<id-opaco>`) resolvido por um **resource
  template** nativo do SDK (`@server.resource("ede://artifact/{id}")`),
  backed por um objeto GCS **privado**, TTL curto (recomendado 15
  minutos), IDs opacos aleatórios, sem listagem, sem `allUsers`/
  `allAuthenticatedUsers`, nunca nome de parte na chave do objeto. Nunca
  URL assinada pública (bearer capability sem re-autenticação) como
  mecanismo primário — só como opção auditada à parte, se algum cliente
  exigir HTTP puro.
- **Nunca:** bucket público; `TextContent` com base64 (mesmo overhead da
  opção aceita, mas sem nenhuma semântica de "isto é um arquivo" — o
  conteúdo entra no contexto do modelo como texto de conversa).

## Decisão 6 — Escopo OAuth: `ede:legal` permanece único para execução

Capacidade nova (modelo institucional adicional) é publicação
administrativa server-side, nunca uma mudança de autorização do
advogado. Introduzir um escopo por peça obrigaria ~40 advogados a
reautorizar a cada modelo novo, sem ganho de segurança concreto (a
enumeração de capacidades disponíveis por conta já é decidida
independentemente da concessão OAuth). `ede:legal` continua cobrindo
`ede_preparar_contestacao` e cobrirá `ede_finalizar_peca` quando ativado.

## Decisão 7 — Descoberta de capacidades (`ede_capabilities`)

Tool pública futura, read-only, escopo `ede:legal`: lista capacidades
`READY` (id, nome de exibição, família, versão de schema,
`renderer_available`) — nunca bytes do modelo, path GCS ou infraestrutura.
Desenho reservado para quando houver mais de uma capacidade real; não
implementado nesta ADR (uma tool de descoberta com uma única entrada
constante não paga o custo de existir ainda).

## Decisão 8 — Migração sem flag-day

- **Fase 1 (atual):** `ede_preparar_contestacao` continua exatamente como
  está — nenhuma remoção, nenhuma renomeação.
- **Fase 2:** registro de capacidades + `ede_finalizar_peca` genérico,
  cobrindo só `contestacao.irregularidade_consumo`.
- **Fase 3 (avaliação futura, fora desta ADR):** um eventual
  `ede_preparar_peca` genérico substituindo `ede_preparar_contestacao` —
  decisão própria, condicionada à liberação de mais peças
  (INV-GATE-CONTESTACAO).

## Prova viva — Gate 6.6-D (ENCERRADO como PARTIAL PASS, 2026-09-22)

A primeira chamada real do ChatGPT a `ede_finalizar_peca` em produção foi
**recusada em `input_validation`, sem DOCX gerado**: densidade de bloco
excedida em `SINOPSE_FATOS` (6 parágrafos, máximo 3), `REALIDADE_FATICA`
(6, máximo 3) e `DESENVOLVIMENTO_TECNICO_IRREGULARIDADE` (10, máximo 5),
contra um rascunho de 2/2/4 no cliente. As chamadas seguintes do
ChatGPT, com parágrafo único nesses campos, terminaram `OK`
(telemetria de produção: sete invocações OK, não uma só), mas a UI do
ChatGPT não conseguiu usar o `EmbeddedResource` devolvido. A chamada do
Claude, com o mesmo payload de parágrafo único, também terminou `OK` e
devolveu **o mesmo SHA-256** do ChatGPT — mas o claude.ai recusou
explicitamente o tipo de mídia do recurso ("Resources of type
'application/vnd.openxmlformats-officedocument.wordprocessingml.
document' are not currently supported"), sem contorno algum; o log de
requisições confirma que o servidor transmitiu o `EmbeddedResource`
completo (tamanho da resposta ≈ inflação base64 esperada do documento).
Evidência completa no `CHANGELOG.md` (seção "Evidência viva — Gate
6.6-D"). O gate está encerrado; esta ADR registra as conclusões:

1. **A Decisão 4 se sustentou em tráfego real.** O caminho público é
   sempre produção-final, e a primeira entrada viva com defeito foi
   recusada antes do render, sem artefato parcial.
2. **Um valor string pode chegar ao servidor com quebras de linha que o
   autor não escreveu.** Parágrafo é linha não vazia separada por `\n`,
   e esse contrato não muda por causa disso. O servidor não junta linhas
   nem adivinha a intenção do cliente (CLAUDE.md §17). Manter o valor
   íntegro no transporte é responsabilidade do cliente.
3. **O finalizador só detecta essa inflação quando ela estoura um
   limite.** Abaixo do limite, cada quebra inserida vira um `<w:p>` real
   no DOCX (INV-PARAGRAFO-HERDA-TEMPLATE), e o round-trip passa, porque
   compara com o valor recebido e não com o rascunho do cliente. Um
   sucesso obtido com valores de parágrafo único não prova, sozinho, que
   o transporte está limpo (`docs/PENDENCIAS.md` PEND-011).
4. **A entrega v1 da Decisão 5 não funcionou nativamente em nenhum dos
   dois hosts testados.** No ChatGPT, o servidor gerou e devolveu o
   documento correto, mas a UI não expôs a URI `attachment://` do
   `EmbeddedResource`, e o ChatGPT recorreu a um canal de arquivos
   próprio (o arquivo obtido por esse contorno é idêntico byte a byte ao
   documento do servidor e mantém o timbrado — o defeito é de entrega no
   host, não de renderização). No Claude, o servidor transmitiu o
   `EmbeddedResource` completo (confirmado no log de requisições), mas o
   cliente recusou explicitamente o tipo de mídia
   `application/vnd.openxmlformats-officedocument.wordprocessingml.
   document` — nenhum contorno, nenhum byte chegou ao usuário.
5. **Isto é evidência suficiente de que a Decisão 5 não atende ao
   requisito real do produto.** Correção do servidor, validação
   produção-final e determinismo do documento (mesmo SHA-256 nas duas
   chamadas vivas com o mesmo payload) estão todos comprovados — o que
   falha é especificamente o mecanismo de entrega entre hosts
   (`EmbeddedResource`/`BlobResourceContents` inline, v1). A Decisão 5
   **não é revista por este registro**: a troca para base64 em
   `TextContent` continua vetada, URL pública segue excluída pela
   própria Decisão 5 tal como escrita, e qualquer mudança no mecanismo
   de entrega é decisão própria, avaliada em ADR-0019 (proposta, sem
   implementação) e sujeita a autorização explícita em gate próprio.
   `docs/PENDENCIAS.md` PEND-012 registra a falha de entrega dos dois
   clientes; PEND-014 registra a avaliação do redesenho.

## Consequências

- Nenhuma mudança de código de produção nesta ADR; nenhuma tool nova
  registrada; nenhum deploy.
- A implementação da Fase 2 é uma **nova capacidade pública** e precisa de
  avaliação própria de VERSION sob ADR-0008 (recomendação: `0.14.0`,
  aprovação explícita antes do bump — ver relatório do Gate 6.6-B).
- O mecanismo de entrega de artefato fica desacoplado do conteúdo
  jurídico: a camada de entrega conhece bytes/MIME/nome de arquivo/
  autorização/expiração; nunca irregularidade, corte, ligação ou
  qualquer outro fato de domínio.
