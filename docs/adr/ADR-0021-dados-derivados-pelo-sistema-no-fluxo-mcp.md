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

## ADR-0021 — CROSS-CLIENT SMOKE 0.17.1 — PASS (27/09/2026)

Homolog 0.17.1 (`ede_health` READY; modelo v1; catálogo `3d710366…`;
manifesto 1.1.0 `42308f8a…`). **Produção não alterada** (nenhum deploy,
nenhuma mudança de tráfego ou configuração). Dados fictícios.

**Fixture positiva canônica** (a mesma nos dois hosts): processo
`8000949-25.2026.8.05.0271`; tópicos `revogacao_gratuidade` e `impugnacao_valor_causa` SIM, demais NÃO; corte
NÃO; `estado_processual` vazio; `marco_tempestividade`
DISPONIBILIZACAO 21/09/2026; `pedidos_economicos` R$ 2.097,63,
R$ 12.900,00 e um pedido sem valor; `ZONA_COMPOSICAO_PROVEITO_ECONOMICO`
com `base_documental`. Sem `JUIZO`, `LOCAL_DATA`, `TEMPESTIVIDADE_CASO`
ou `juizo_confirmado_advogado`.

* **ChatGPT — PASS** (relatado pelo titular): schema novo visível;
  positiva `OK` em ~7 s, sem timeout nem erro de transporte;
  `document_sha256`
  `cf200c0f6d42e63710a2822dcd4dfd34e9d807511dbc3e1b9cd348427dd48fd1`;
  DataJud/JUIZO, tempestividade, `LOCAL_DATA`, pedidos econômicos e zona
  corretos; sem "R$ R$"; download e Word OK.
* **Claude — PASS:** os quatro campos novos visíveis no schema sem
  reconexão. Positiva `OK` em ~3 s, sem timeout nem erro de transporte,
  sem aviso de fallback de juízo; `document_sha256`
  `cf200c0f6d42e63710a2822dcd4dfd34e9d807511dbc3e1b9cd348427dd48fd1`,
  1.753.878 bytes; `/download/<token>` HTTP 200, content-type DOCX,
  SHA-256 local idêntico, ZIP íntegro, aberto no Word (COM, somente
  leitura: 7 páginas), nenhum `{{` nem tag BLOCO/SUBBLOCO/ZONA/INLINE
  residual. Conferido no texto: "AO JUÍZO DA 2ª VARA DE FEITOS DE REL
  DE CONS. CÍVEL E COMERCIAIS DA COMARCA DE VALENÇA"; marco 22/09/2026 e
  termo final 14/10/2026; "Salvador, 27 de setembro de 2026."; valor
  atribuído R$ 15.000,00 e retificação para R$ 14.997,63; sem "R$ R$";
  zona inserida imediatamente após "In casu, a petição inicial
  cumula:". Seis `dados_nao_bloqueantes`, entre eles o aviso da
  gratuidade não documentada e o resumo do proveito (diferença R$ 2,37,
  1 pedido sem valor fora da soma).
* **Comparação:** mesmo `document_sha256` nos dois hosts
  `cf200c0f6d42e63710a2822dcd4dfd34e9d807511dbc3e1b9cd348427dd48fd1`,
  ou seja, o mesmo DOCX byte a byte.
* **DataJud real resolvido** no homolog: `JUIZO` obtido do DataJud/CNJ
  (órgão julgador) e do IBGE (comarca), sem fallback humano.
* **Negativos (Claude e ChatGPT, todos PASS):** A. licitude SIM + corte
  NÃO → `NEEDS_INPUT`/`topic_matrix`; B. `ZONA_INVENTADA` →
  `REFUSED`/`zonas`/`INPUT_VALIDATION_FAILED`; C. `LOCAL_DATA` do host →
  `REFUSED`/`input_validation`; D. `TEMPESTIVIDADE_CASO` do host →
  `REFUSED`/`input_validation`.
* Observação: uma primeira tentativa do Claude com o processo de teste
  `8000099-11.2026.8.05.0080` (fixture diferente da canônica) foi
  recusada em `enderecamento` por "processo não encontrado" — fail-closed
  correto, sem fallback humano, em ~10 s.

**Pendências:** PEND-015 e PEND-016 FECHADAS PARA V1; PEND-017 permanece
ABERTA; PEND-018 RESOLVIDA NO V1 / LEGADO CONGELADO. A prova real do
DataJud no homolog, pendente desde o ajuste da 0.17.1, está feita.
Primeiro caso real ainda não retomado.

## Emenda 0.18.0 — marco de tempestividade `CIENCIA` (27/09/2026, pré-deploy)

**Origem:** primeiro caso real (8000949-25.2026.8.05.0271). O advogado
informou "Citação: 20/09/2026", sem documento de disponibilização no
DJe. O contrato 0.17.1 só aceitava `DISPONIBILIZACAO`, e o host não pode
converter um ato processual em outro.

**Decisão:** o contrato foi ampliado para refletir a fonte normativa da
tempestividade, a Skill `calendario-forense-tjba-2026`. O `SKILL.md`
(seção "Metodologia de contagem") conta o prazo a partir da
"intimação/ciência": "o início se dá no primeiro dia útil seguinte à
intimação/ciência". Nenhuma regra jurídica nova foi criada e a Skill não
foi alterada.

Arquitetura: **Skill normativa → contrato estruturado → Core
determinístico → MCP → host.**

* `marco_tempestividade.tipo` aceita `DISPONIBILIZACAO` e `CIENCIA`.
* `CIENCIA` = data da citação/intimação/ciência, usada diretamente como
  `data_ciencia` em `calcular_tempestividade` da Skill; **não** passa
  por `derivar_publicacao`. Mesma trava de cobertura (PEND-017), mesmo
  fail-closed, mesmo texto de tempestividade. Não se pede a modalidade
  da citação nesta versão.
* `DISPONIBILIZACAO` fica exatamente como homologado na 0.17.1
  (publicação no primeiro dia útil seguinte, depois a contagem). A
  harmonização documental desse ramo com o `SKILL.md`, que não descreve
  a derivação da publicação, fica em PEND-019.
* Manifesto V1 **1.2.0** (novo SHA fixado); 1.1.0 e 1.0.0 preservados
  byte a byte, fora da imagem.
* Host: extrair o marco dos documentos primeiro; data de
  citação/intimação/ciência → `CIENCIA`; disponibilização no DJe
  especificamente → `DISPONIBILIZACAO`; sem marco documental, perguntar
  a data ao advogado; nunca converter `CIENCIA` em `DISPONIBILIZACAO`.

**Prova local:** `CIENCIA` 20/09/2026, com ato em 27/09/2026 → marco
20/09/2026, primeiro dia contado 21/09/2026, termo final 09/10/2026,
tempestivo. `DISPONIBILIZACAO` 21/09/2026 → publicação 22/09/2026,
termo final 14/10/2026 (inalterado).

**Consequências:** mudança aditiva do schema público (novo valor do
enum) → reconexão dos clientes e novo smoke cross-client; versão 0.18.0.
PEND-015 e PEND-016 continuam fechadas para o V1.

## ADR-0021 / CIENCIA — CROSS-CLIENT SMOKE 0.18.0 — PASS (28/09/2026)

Homolog 0.18.0, revisão `ede-mcp-homolog-00010-x7g`, manifesto V1
1.2.0. **Produção não alterada** (nenhum deploy, tráfego ou
configuração); rollback do homolog para `00009-fxs` (0.17.1) continua
disponível. Dados fictícios. Mesma fixture positiva canônica do smoke
0.17.1 (sem `juizo_confirmado_advogado`), alterando só
`marco_tempestividade`:

| Marco | Contagem | `document_sha256` |
|---|---|---|
| `CIENCIA` 20/09/2026 | termo final 09/10/2026 | `208069646c5450356cf5545af41c86dc4d03a7e1f1debbec498120f74d5c6d29` |
| `DISPONIBILIZACAO` 21/09/2026 | publicação 22/09/2026 → termo final 14/10/2026 | `93fbf203eed6ef1a5c571211d4002aae81c637bf97a90cbd9c47217a5ede72b9` |

Os dois documentos têm 1.753.878 bytes. O SHA depende de `LOCAL_DATA`
("Salvador, 28 de setembro de 2026."); todas as execuções ocorreram em
28/09/2026.

* **Server-side — PASS:** os dois SHAs acima.
* **ChatGPT — PASS** (relatado pelo titular): schema com `CIENCIA` e
  `DISPONIBILIZACAO`; os dois casos `OK` com os mesmos SHAs; sem timeout
  nem erro de transporte.
* **Claude.ai — PASS** (relatado pelo titular).
* **Claude Code — PASS:** schema da sessão reconectada com os dois
  valores do enum e os campos `pedidos_economicos`, `zonas`,
  `juizo_confirmado_advogado`, `topicos` e `fatos_publicos`. `CIENCIA`
  `OK` em ~67 s e `DISPONIBILIZACAO` `OK` em ~47 s, sem timeout nem
  erro de transporte, os mesmos SHAs. Download HTTP 200, content-type
  DOCX, SHA-256 local idêntico, ZIP íntegro, aberto no Word (COM,
  somente leitura: 7 páginas). Conferido no texto: juízo de Valença
  resolvido pelo DataJud, `LOCAL_DATA` automático, retificação para
  R$ 14.997,63, sem "R$ R$", zona logo após "In casu, a petição inicial
  cumula:", nenhum `{{` nem tag interna residual.
* **Comparação:** as quatro superfícies chegaram aos mesmos artefatos,
  byte a byte, onde houve comparação de SHA.
* **Tentativas anteriores do Claude Code:** duas chamadas `CIENCIA`
  (~62 s e ~61 s) voltaram `NEEDS_INPUT`/`enderecamento` por DataJud
  indisponível; uma consulta direta ao DataJud no mesmo momento levou
  52,1 s. Lentidão temporária da dependência externa, com fail-closed
  correto — não é falha da 0.18.0. Negativos não repetidos.

**Pendências:** PEND-015 e PEND-016 continuam fechadas para o V1;
PEND-019 continua aberta, sem mudança no comportamento de
`DISPONIBILIZACAO`. Primeiro caso real ainda não retomado.

## Emenda — gate de compatibilidade host (28/09/2026, pré-deploy)

**Achado.** No primeiro teste simples com o ChatGPT, o advogado deu só as
14 decisões SIM/NÃO e "Citação 21/09/2026". O host tinha os documentos
(memorial, fatura, pedido de dano moral), mas `ede_finalizar_peca`
devolveu `NEEDS_INPUT`/`topic_matrix` para cálculos, dano moral e
reconvenção. Reproduzido no homolog: os gates factuais existiam só em
`gate_factual` do manifesto e em `topic_matrix.py`; nenhuma ferramenta
MCP os publicava. `blocos_modelo[*].gate_status` dizia `sem_gate_fatico`
para esses três blocos; `estado_processual` era um mapa sem descrição;
chave desconhecida era ignorada em silêncio; o pacote não trazia o
`capability_id`.

**Decisão.** "Não expor chaves internas ao advogado" **não é** "não
expor contrato machine-readable ao host". O advogado continua vendo e
respondendo só tópicos e fatos públicos SIM/NÃO; o host recebe o
contrato do que deriva dos documentos. Nenhuma regra jurídica muda: a
Topic Matrix, os gates, `corte_efetivo` e o Modelo Oficial ficam como
estão; o Core continua sem busca textual nem prova de fatos.

* `ede_preparar_contestacao` publica `capability_id` e, em
  `topic_matrix.topicos[*]`, `suporte_factual_host` (chave de estado,
  papel — gate, suporte informativo, subbloco ou zona —, descrição,
  requisito semântico, efeito de true/false/INDETERMINADO/omitida e
  `documentos_sugeridos`) e `dados_documentais_host` (campo, tipo,
  descrição, restrições, `documentos_sugeridos`, `exigido_quando`); o
  mesmo para as seções incondicionais (`secoes_incondicionais_host`),
  mais `chaves_estado_host` e `estados_calculados_pelo_sistema`. Tudo
  derivado por `topic_matrix.descrever_contrato_host` do manifesto, do
  catálogo e do schema; o código só declara o que o manifesto não dá no
  nível do fato (`DESCRICAO_ESTADO_HOST`, `DOCUMENTOS_SUGERIDOS_*`,
  `CONTRATO_DADO_HOST`).
* **Contrato semântico, sem taxonomia de documentos.** O host reconhece
  o suporte pelo conteúdo de qualquer documento, seja qual for o nome
  ou o tipo do arquivo. `documentos_sugeridos` é orientação não
  exaustiva (identificadores do manifesto), nunca enum nem condição de
  validade; o Core não classifica documento nem valida nome.
* `partes_redigiveis_llm[*]` traz `campo_finalizador` (`placeholders` ou
  `zonas.conteudo`) e `exigido_quando` (tópico SIM, sempre, ou opcional
  para zonas). Um campo só é exigido quando o bloco que o contém compõe
  a peça — a mesma regra que o finalizador já aplicava.
* `IRREGULARIDADE_ENCONTRADA` e `VALOR_FRA` são publicados ao host com o
  contrato do comportamento real (atômico da Etapa 5.3-B; sem sentinela
  de ausência), não com o texto do schema do fluxo local.
* **Marcadores de pós-edição são do Core (decisão do titular, opção 1).**
  No V1, quando o bloco que os contém compõe a peça, o finalizador
  preenche `TELAS_DA_TITULARIDADE` ("[INSERIR MANUALMENTE AS
  TELAS/DOCUMENTOS DA TITULARIDADE DA UC]") e `FOTOS_DA_IRREGULARIADE`
  ("[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"), textos
  únicos em `validate_placeholder_semantics.MARCADORES_MANUAIS`. Coerente
  com o manifesto (`CALCULADO_PELO_CORE`), sem nova versão dele. O host
  não os envia (`campos_calculados_pelo_sistema`); valor diferente do
  institucional é recusado, nunca substituído em silêncio.
* **`VALOR_FRA` no MCP.** A regra `obrigatorio_nao_sentinela` do catálogo
  (Reconvenção incluída) passa a valer no finalizador, antes do render:
  sentinela de ausência, sentinela de aceite ou valor sem quantia
  monetária → `MISSING_REQUIRED_FIELD`. Antes, só o fluxo local a
  aplicava e o MCP gerava a peça com "NÃO INFORMADO" impresso. Vale para
  o contrato V1 e o legado.
* `gate_status` considera o `gate_factual` do manifesto; estado
  reservado aparece como `calculado_pelo_sistema`.
* `ede_finalizar_peca`: `estado_processual` segue mapa dinâmico, com
  descrição apontando para o contrato; chave fora de
  `chaves_estado_host` é recusada (`INPUT_VALIDATION_FAILED`,
  `chaves_estado_desconhecidas`); `NEEDS_INPUT`/`topic_matrix` traz
  `suporte_ausente` (`topico`, `chave_estado`, `motivo`
  AUSENTE/FALSE/INDETERMINADO) para o host rever os documentos. As
  `pendencias` continuam sem identificador interno.
* Orientação do pacote: derivar `estado_processual` dos documentos, só
  com as chaves publicadas, contradição → `INDETERMINADO`, nunca
  perguntar as chaves ao advogado; pendência ao advogado só quando a
  prova de um tópico SIM faltar de fato, em linguagem comum.

**Fora deste gate.** Tornar `corte_efetivo` obrigatório só quando a
licitude do corte for SIM (proposto no diagnóstico, não adotado).

**Consequências.** O schema público muda por adição (reconexão dos
clientes e smoke cross-client). Manifesto, catálogo e Modelo Oficial
inalterados (SHAs fixados nos testes). A validação de chave desconhecida
vale só no fluxo com manifesto; o contrato legado não muda. Testes
black-box pela camada MCP em `tests/test_compatibilidade_host_mcp.py`.

## Emenda — manifesto 1.3.0: composição do proveito econômico pelo Core (29/09/2026, pré-deploy)

**Achado (teste cross-client da 0.19.0, mesmos documentos, mesmas 14
decisões, mesma citação).** O Claude.ai escreveu a composição após "In
casu, a petição inicial cumula:" e chegou a R$ 14.997,63. O ChatGPT
omitiu a zona (o DOCX saiu com "In casu…" seguido do parágrafo
seguinte) e pediu a retificação para R$ 12.097,63. Reproduzido
localmente com o Modelo V1: o Core aceitava a zona ausente (declarada
opcional) e somava os `pedidos_economicos` do host sem conferi-los com
nada; pedidos com dano moral de R$ 10.000,00 e `VALOR_DANO_MORAL_
PRETENDIDO` de R$ 12.900,00 geravam um DOCX internamente contraditório.
O pacote 0.19.0 publicava ao host, como exemplo de formato, "R$
10.000,00" nas restrições desses campos.

**Decisão (titular, 29/09/2026).**
* Manifesto V1 **1.3.0** (1.2.0, 1.1.0 e 1.0.0 preservados byte a
  byte): `ZONA_COMPOSICAO_PROVEITO_ECONOMICO` passa de
  `VARIAVEL_LLM_AUTORIZADA` a `CALCULADO_PELO_CORE`; `pedidos_economicos`
  ganha `natureza` obrigatória (`DEBITO`, `DANO_MORAL`, `OUTRO`), nunca
  inferida da descrição. SHA fixado em `modelo_oficial_versoes.py`;
  imagem, `.dockerignore` e allowlist do workflow levam só o 1.3.0.
* **Fonte única do cálculo:** `proveito_economico.calcular_proveito`
  produz, num só laço em `Decimal`, o total, a diferença, os subtotais
  por natureza e os valores do dano moral. O mesmo resultado alimenta
  `VALOR_TOTAL_PROVEITO_ECONOMICO` (retificação), a cumulação, o aviso ao
  advogado e o texto da composição.
* **Composição determinística** (padrão validado no teste real do
  Claude): "A soma dos pedidos cumulados, débito de R$ X e danos morais
  estimados em R$ Y, alcança R$ TOTAL, e não os R$ CAUSA atribuídos à
  causa." Montada só com natureza e valor (descrição livre nunca entra);
  pedidos sem valor não entram na soma nem na frase, mas continuam
  registrados. Presente sempre que houver cumulação; um pedido só não
  compõe o subbloco. Passa pelas mesmas travas de densidade, semântica e
  continuidade das zonas.
* **Zona antiga:** o host não a envia mais; se enviar, `REFUSED`
  (`campos_calculados_enviados`). O contrato do host a publica em
  `campos_calculados_pelo_sistema`, fora de `partes_redigiveis_llm`.
* **Consistência do dano moral:** com impugnação e dano moral SIM,
  exatamente um pedido `DANO_MORAL`, com valor igual (Decimal) ao de
  `VALOR_DANO_MORAL_PRETENDIDO`; pretensão não quantificada ("a ser
  arbitrado") corresponde a pedido sem valor. Divergência, ausência ou
  ambiguidade → `REFUSED` antes do render, com `inconsistencias_valores`
  (`campo`, `motivo`, `valor_informado`, `valor_nos_pedidos`).
* **Sem** checagem cruzada entre `VALOR_FRA` e o débito dos pedidos:
  débito apurado pela Ré e débito impugnado pelo autor são fatos
  jurídicos distintos e podem divergir.
* Exemplos de formato publicados ao host passam a "R$ 1.234,56".

**Compatibilidade.** Schema público muda: `natureza` em
`PedidoEconomico`, novos campos de recusa. Hosts que enviavam a zona da
composição ou pedidos sem natureza passam a ser recusados (com
indicação estruturada). Exige reconexão e novo smoke cross-client.
Testes: `tests/test_composicao_proveito_core.py`.
