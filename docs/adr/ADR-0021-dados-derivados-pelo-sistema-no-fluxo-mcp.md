# ADR-0021 — Dados derivados pelo sistema no fluxo MCP da Contestação

* **Status:** Aceito — **design aprovado, implementação pendente**
  (24/09/2026). Enquanto a implementação não for homologada, o runtime
  do homolog (`ede-mcp-homolog-00007-4rm`) continua com o comportamento
  anterior descrito em "Contexto". Produção inalterada
  (`ede-mcp-00020-gum`, contrato legado).
* **Data:** 2026-09-24
* **Relacionados:** ADR-0020 (Topic Matrix; esta ADR emenda a Decisão 3
  quanto à gratuidade), ADR-0015 (Core × adapter MCP, sem LLM no
  servidor), ADR-0010 (zonas de complementação), ADR-0018 (finalizador
  genérico); SPEC-0001 §51 (INV-JUIZO-DATAJUD), §5
  (INV-TEMPESTIVIDADE-MARCO), §64 (esta ADR); PEND-015, PEND-016,
  PEND-017, PEND-018.

## Contexto

O primeiro caso real assistido no homolog (processo de irregularidade de
consumo, Valença/BA) mostrou que a orquestração pedia ao advogado dados
que o próprio sistema deve obter, calcular ou derivar:

* decisão concessiva da gratuidade (data/ID) como condição para incluir
  o tópico de revogação;
* qual discrepância sustentar e qual o proveito econômico, no tópico de
  impugnação ao valor da causa;
* o texto de `TEMPESTIVIDADE_CASO`;
* a unidade judiciária (`JUIZO`);
* a data da peça (`LOCAL_DATA`).

Causa técnica: o manifesto V1 já declara `JUIZO`, `TEMPESTIVIDADE_CASO`
e `VALOR_TOTAL_PROVEITO_ECONOMICO` como `CALCULADO_PELO_CORE`, e o Core
já tem `datajud_client.resolver_juizo` e `calcular_tempestividade`, mas
`scripts/finalizar_peca.py` recebe esses valores prontos do host em
`placeholders` e só valida forma. A gratuidade tinha gate factual no
manifesto. As zonas de complementação não são aceitas pelo MCP
(PEND-015), o que deixaria o tópico de valor da causa com a frase fixa
"In casu, a petição inicial cumula:" sem continuação.

## Princípio

O advogado decide **quais tópicos entram** (Topic Matrix, SIM/NÃO).
Depois disso, o sistema analisa os autos, extrai fatos, faz os cálculos
autorizados, consulta as integrações autorizadas e o host redige só as
partes variáveis permitidas pelo manifesto. **Não se pergunta ao
advogado o que pode ser derivado dos autos ou obtido automaticamente.**
Pergunta ao advogado só existe para: decisão de tópico, fato público
SIM/NÃO previsto no manifesto, marco de tempestividade, e as exceções
fail-closed listadas abaixo.

## Decisões

1. **Gratuidade sem gate factual.** "Revogação da gratuidade" = SIM
   inclui o tópico sem exigir decisão concessiva, data ou ID. Se o
   deferimento não estiver documentado (fato ausente ou falso), o
   finalizador **não bloqueia e não pergunta**: acrescenta aviso não
   bloqueante em `dados_nao_bloqueantes`, que apenas informa que o
   suporte documental ao deferimento não foi localizado. O texto fixo do
   Modelo Oficial não é alterado. **Risco conhecido:** o texto fixo do
   tópico 2.2 afirma "o benefício foi deferido"; se não houver
   deferimento, a peça afirma um fato que os autos não sustentam. A
   correção é do texto institucional, reservada à responsável jurídica
   (fora desta ADR).
   Emenda `INV-TOPIC-MATRIX-DECISAO-ADVOGADO` (ADR-0020, Decisão 3):
   a gratuidade deixa a lista de tópicos com gate factual; os demais
   continuam.

2. **Topic Matrix só com decisões SIM/NÃO**
   (`INV-TOPIC-MATRIX-SO-SIM-NAO`). `topicos` contém exclusivamente
   decisões jurídicas SIM/NÃO do advogado; `fatos_publicos` continua
   SIM/NÃO, separado. Dados processuais estruturados têm **campos
   próprios** no contrato do finalizador (`marco_tempestividade`,
   `pedidos_economicos`, `zonas`, `juizo_confirmado_advogado`), nunca
   dentro da Topic Matrix. `topic_matrix.py` não passa a aceitar outros
   tipos.

3. **Tempestividade calculada pelo Core a partir da disponibilização.**
   Novo input público `marco_tempestividade = {"tipo":
   "DISPONIBILIZACAO", "data": "DD/MM/AAAA"}`; nesta versão só esse
   tipo. O Core deriva a data de publicação (primeiro dia útil seguinte
   à disponibilização, art. 224, §§ 2º e 3º, do CPC, com o calendário
   TJBA verificado), conta 15 dias úteis (art. 335 do CPC,
   `INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM`) e gera
   `TEMPESTIVIDADE_CASO`; data do ato = data corrente em
   `America/Bahia`. `TEMPESTIVIDADE_CASO` enviado pelo host é recusado.
   Fail-closed: marco ausente ou inválido → `NEEDS_INPUT` pedindo só a
   data de disponibilização; calendário do ano não verificado ou
   contagem que ultrapasse o ano coberto → recusa explicando o dado que
   falta (trava de ano, PEND-017).

4. **Intempestividade não gera peça.** Resultado `INTEMPESTIVO` → sem
   texto de tempestividade, sem render; `NEEDS_INPUT` em linguagem
   jurídica com o marco utilizado, a data de publicação derivada e o
   termo final, aguardando decisão humana. A redação "a presente
   Contestação é intempestiva" deixa de ser gerada pelo caminho MCP.

5. **Endereçamento pelo DataJud, com exceção humana só em
   indisponibilidade.** O finalizador resolve `JUIZO` por
   `datajud_client.resolver_juizo` (DataJud + IBGE) a partir de
   `NUMERO_PROCESSO`; `JUIZO` enviado pelo host em `placeholders` é
   recusado. Resposta normal do DataJud é autoritativa: sem pergunta ao
   advogado, sem override. **Exceção** (emenda a `INV-JUIZO-DATAJUD`):
   se o DataJud/IBGE estiver indisponível ou falhar por erro de
   transporte, o finalizador devolve `NEEDS_INPUT` e passa a aceitar
   `juizo_confirmado_advogado` numa nova chamada — que **só é usado se o
   DataJud falhar de novo nessa mesma chamada**; se o DataJud responder e
   divergir da confirmação, `NEEDS_INPUT` com a divergência, nunca
   escolha silenciosa. Processo não encontrado, resposta ambígua ou
   sem órgão julgador **não** abrem a exceção (continuam fail-closed,
   como hoje). Quando tecnicamente simples, `ede_preparar_contestacao`
   também resolve o juízo, para o advogado ver o endereçamento antes da
   finalização; a resolução autoritativa continua no finalizador. Sem
   LLM no servidor (ADR-0015): é chamada HTTP determinística do Core.

6. **Zonas de complementação pelo MCP — suporte genérico (PEND-015).**
   Novo input `zonas`, só para zonas declaradas como
   `VARIAVEL_LLM_AUTORIZADA` no manifesto da versão ativa; zona não
   declarada, ou de tópico excluído, é recusada. Reaproveita a
   validação e a composição já existentes (forma estruturada
   `{"conteudo", "fatos"}`, parágrafo 380, ancoragem, aritmética
   Decimal, unidades, continuidade com o texto institucional,
   `compor_zonas`), Template Lock, fidelidade e round-trip. O host
   redige; o Core valida e posiciona. Primeiro uso: composição do
   proveito econômico; a infraestrutura atende todas as zonas VLA
   autorizadas.

7. **Valor da causa: proveito econômico derivado dos autos.** O host
   extrai da inicial os pedidos economicamente mensuráveis com fonte
   (`pedidos_economicos`); o Core soma em `Decimal`, compara com
   `VALOR_DA_CAUSA`, preenche `VALOR_TOTAL_PROVEITO_ECONOMICO` e
   informa a conclusão (discrepância e diferença) ao advogado, sem
   remover o tópico por conta própria. Pedido sem valor quantificável é
   declarado como tal, nunca somado como zero. O host nunca envia
   `VALOR_TOTAL_PROVEITO_ECONOMICO`. Antes de homologar, confirmar e
   corrigir a possível duplicação "R$ R$" (o texto fixo já traz "R$"
   antes dos dois placeholders de valor; PEND-018).

8. **`LOCAL_DATA` calculado pelo Core.** "Salvador, <data corrente>",
   com "1º" no primeiro dia do mês, no fuso IANA `America/Bahia` (nunca
   offset fixo); `LOCAL_DATA` enviado pelo host é recusado.

9. **Orquestração do host.** `ede_preparar_contestacao` passa a
   orientar o host (texto de `topic_matrix.orientacao` e
   `regras_institucionais`) a perguntar ao advogado somente os itens do
   Princípio e a nunca perguntar juízo, data da peça, texto de
   tempestividade, proveito econômico ou documento concessivo da
   gratuidade.

## Preservado

Advogado decide SIM/NÃO dos tópicos; fatos públicos separados das
decisões; texto fixo institucional intocado; LLM só nas partes
autorizadas; nada de `block_decisions` no V1; nenhum fato inventado;
sem jurisprudência externa; Template Lock, fidelidade independente e
round-trip; Modelo Oficial V1 (DOCX) e catálogo V1 inalterados.

## Consequências

* **Schema público de `ede_finalizar_peca` muda** (novos campos
  `marco_tempestividade`, `pedidos_economicos`, `zonas`,
  `juizo_confirmado_advogado`) → reconexão dos clientes (cache de
  `tools/list` já observado no ChatGPT) e novo smoke cross-client.
* **Novo manifesto V1 (1.1.0)** com SHA próprio fixado em
  `scripts/modelo_oficial_versoes.py`: gratuidade sem gate;
  `LOCAL_DATA`/`VALOR_TOTAL_PROVEITO_ECONOMICO` como calculados pelo
  Core; entrada `marco_tempestividade` declarada fora de
  `topicos_decisao_advogado`. O manifesto 1.0.0 deixa de ser o
  contrato ativo da V1 (o DOCX e o catálogo não mudam).
* **Novo deploy do homolog**, com prova de saída de rede para
  `api-publica.datajud.cnj.jus.br` e `servicodados.ibge.gov.br`.
* PEND-016 só fecha com o cálculo integrado ao MCP e aprovado no smoke
  cross-client. Abertas PEND-017 (calendário fora de 2026 / trava de
  ano) e PEND-018 ("R$ R$").

## Notas de implementação (24/09/2026, pré-deploy)

* Manifesto V1 **1.1.0** em arquivo novo
  (`templates/contestacao/v1/manifesto-1.1.0.json`); o 1.0.0 fica
  intacto no repositório, como exige a ADR-0020, e não entra na imagem.
* `zonas` carrega a própria `base_documental` (fatos com fonte, mesmo
  contrato de `ede_preparar_contestacao`): sem ela a checagem de
  proveniência das zonas perderia a verificação de fonte e de número
  documental. Nenhum quinto campo público foi criado.
* Recusados do host no V1: só os quatro campos desta ADR (`JUIZO`,
  `TEMPESTIVIDADE_CASO`, `LOCAL_DATA`, `VALOR_TOTAL_PROVEITO_ECONOMICO`)
  e os estados `EXISTE_DISCREPANCIA_VALOR_CAUSA`/
  `EXISTE_CUMULACAO_PEDIDOS_ECONOMICOS`. O marcador manual
  `TELAS_DA_TITULARIDADE`, também marcado como do Core no manifesto,
  segue como antes (fora do escopo).
* O Core não classifica a diferença do valor da causa como "material":
  devolve os números exatos no aviso; a qualificação jurídica é do host
  e a decisão, do advogado (nenhuma heurística jurídica em Python).
* Exibição do juízo na preparação: **não implementada** — exigiria um
  campo novo em `ede_preparar_contestacao` (número do processo), não
  aprovado; o finalizador segue autoritativo.
* `ZoneInfo("America/Bahia")` provado na imagem pinada
  (`python:3.12-slim@sha256:78387bc3…`, Debian 13.6, tzdata do sistema
  2026b) pelo Cloud Build `cb73793a-4c42-4c52-a52c-94b30e7bc931`:
  nenhuma dependência nova.

## Ajuste pós-smoke — política de chamada ao DataJud (0.17.1)

O smoke no homolog (`00008-bnf`, 0.17.0) classificou o DataJud como
indisponível em todas as chamadas: com 3 tentativas de 10 s, nenhuma
resposta chegava a tempo. Medição direta (25/09/2026): 4 respostas 200 em
5 (21,2 s; 39,5 s; 57,1 s; 37,1 s), um 429 e, antes, um 504 depois de
~60 s. Nova política: **uma requisição por consulta**, conexão 5 s,
leitura 65 s, **sem retry** (evita multiplicar a carga no CNJ). 429, 5xx,
timeout e falha de conexão passam a ser indisponibilidade — antes, o 429
caía como erro definitivo e recusaria em vez de oferecer o fallback. O
fallback humano e a INV-JUIZO-DATAJUD ficam exatamente como aprovados.
**Pendente:** prova real end-to-end do DataJud no homolog depois do deploy
da 0.17.1. Risco: uma resolução pode levar até ~130 s (DataJud + IBGE) no
pior caso, o que pode exceder o tempo de espera de alguns clientes MCP.

