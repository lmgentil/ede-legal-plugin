# ADR-0019 — Redesenho da entrega de artefato entre hosts MCP (proposta)

* **Status:** Proposto — avaliação técnica autorizada pelo usuário;
  **implementação NÃO autorizada**. Nenhum código, bucket, IAM, Resource
  Descope, deploy ou revisão de infraestrutura foi criado por este
  documento.
* **Data:** 2026-09-22
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
| URL assinada de curta duração | V4 signed URL (Cloud Storage), TTL alvo de **15 minutos** |
| Exclusão automática por ciclo de vida (rede de segurança) | Regra de `lifecycle` no bucket (ex.: `age` em horas), como último recurso caso uma exclusão explícita pós-download falhe ou nunca ocorra |
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
  que o EDE nunca a registre — mitigação de TTL curto (15 minutos
  alvo) reduz a janela, não elimina a exposição;
* a mitigação real não é "não vai vazar", e sim "a janela de validade é
  curta o bastante para que um vazamento tenha valor mínimo" — TTL
  curto, uso único quando tecnicamente viável (V4 signed URLs do GCS não
  suportam nativamente invalidação após o primeiro uso; simular isso
  exigiria um passo adicional de verificação no servidor, avaliação
  futura), e exclusão do objeto por ciclo de vida como rede de segurança
  final;
* isto é uma aceitação de risco, não uma eliminação — qualquer
  implementação da Candidata A precisa declarar este trade-off ao
  usuário de novo no momento da aprovação de implementação, não só
  aqui.

## Consequências desta ADR (proposta)

* Nenhuma mudança de código, infraestrutura, IAM, bucket ou deploy.
  `ede_finalizar_peca`, o renderer, o Template Lock e a validação
  produção-final permanecem exatamente como o Gate 6.6-C/D os deixou.
* A Decisão 5 da ADR-0018 não é revista por este documento — ela
  permanece o mecanismo em produção até uma decisão explícita do
  usuário adotar uma candidata daqui (ou outra) e um gate de
  implementação ser autorizado e concluído com prova viva própria.
* PEND-014 (`docs/PENDENCIAS.md`) referencia este documento como o
  registro da avaliação; seu critério de resolução exige decisão
  explícita do usuário, não a existência desta ADR sozinha.
* Itens em aberto que uma implementação futura precisa resolver antes
  do gate de prova viva: (1) confirmar se algum log de infraestrutura
  do Cloud Run/GCS captura a query string da URL assinada por padrão da
  plataforma; (2) decidir sobre uso único vs. reutilizável dentro do TTL;
  (3) pesquisar o comportamento do Claude quanto a reapresentar Bearer
  OAuth em requisição separada (Candidata B), hoje não investigado; (4)
  confirmar que Public Access Prevention e a política de IAM do bucket
  novo são verificadas por teste automatizado antes de qualquer tráfego
  real, mesma disciplina do Gate 6.4-B para o bucket do Modelo Oficial.
