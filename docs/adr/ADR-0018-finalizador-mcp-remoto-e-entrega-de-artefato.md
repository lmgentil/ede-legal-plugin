# ADR-0018 — Finalizador MCP remoto: contrato multi-peça e entrega de DOCX

* **Status:** Proposto (auditoria de arquitetura — Gate 6.6-B; nenhuma tool
  pública criada, nenhum deploy realizado por esta ADR)
* **Data:** 2026-09-22
* **Relacionado:** ADR-0015 (fronteira Core/Adapter/MCP), ADR-0016/0017
  (OAuth e ativação de produção), ADR-0009 (Modelo Oficial externo);
  Gate 6.5-A/B3/C1-C4 (`ede_preparar_contestacao`, escopo `ede:legal`);
  Gate 6.6-A (renderer do Modelo Oficial, Template Lock, fidelidade
  independente, round-trip, modo produção-final)

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
