# ADR-0020 — Versionamento do Modelo Oficial e Topic Matrix pública

* **Status:** Aceito — ativação **só no homolog** (`ede-mcp-homolog`).
  Produção inalterada (`ede-mcp-00020-gum`, contrato legado).
* **Data:** 2026-09-24
* **Relacionados:** ADR-0009 (Modelo Oficial externo), ADR-0015 (Core ×
  adapter MCP, sem LLM no servidor), ADR-0017 (aquisição pinada por
  GCS/SHA), ADR-0018 (finalizador genérico), ADR-0010 (zonas).

## Contexto

A responsável jurídica aprovou o Modelo Oficial V1 da capability
`contestacao.irregularidade_consumo` (DOCX `1e2aa2a5…747a9e`), com novos
subblocos condicionais (A1 factuais, A2 do ônus) e uma **Topic Matrix**:
14 decisões públicas SIM/NÃO do advogado + o fato público "corte/
suspensão efetivamente ocorrido". O padrão de escrita e o texto fixo do
modelo são alterados exclusivamente pela responsável jurídica; a LLM
nunca os altera.

Até aqui o runtime tinha um único contrato (`templates/contestacao/
blocos.json`), acoplado ao modelo vigente. Trocar esse arquivo para a V1
quebraria o modelo em produção (o contrato é conferido contra os bytes
do DOCX) e o fluxo local da Skill.

## Decisões

1. **Contrato por versão, escolhido pelo SHA pinado.**
   `scripts/modelo_oficial_versoes.py` associa o SHA-256 do Modelo
   Oficial (o mesmo `EDE_MODELO_OFICIAL_SHA256` que o runtime já confere)
   ao catálogo e ao manifesto daquela versão. Nenhuma variável nova,
   nenhuma escolha do cliente. SHA legado ou desconhecido → contrato
   legado, idêntico ao anterior. Catálogo e manifesto de cada versão são
   fixados por SHA-256 e conferidos na carga; o manifesto também precisa
   apontar para o SHA do modelo e do catálogo da mesma versão.
2. **Manifesto imutável e neutro quanto a ambiente** (D2). V1:
   `manifesto_versao 1.0.0`, `status APROVADO`, SHA `f703966d…0414a5b`.
   Nada de "ativo em homolog/produção" dentro dele: ativação é
   configuração de deploy (SHA + objeto + geração GCS pinados).
3. **O advogado decide; o fato é só gate** (D1,
   `INV-TOPIC-MATRIX-DECISAO-ADVOGADO`, substitui `INV-GRATUIDADE-
   LINKED`). NÃO exclui o tópico mesmo com o fato presente; SIM exige
   gate satisfeito; SIM sem suporte → `NEEDS_INPUT`. Como o catálogo V1
   é imutável (SHA aprovado) e mantém `state_linked` em quatro blocos,
   `scripts/topic_matrix.py` entrega ao motor `fato AND SIM` nesses
   vínculos — `state_linked` vira só o veículo mecânico.
4. **`NEEDS_INPUT` como terceiro resultado do finalizador**, antes de
   qualquer render, com `pendencias` em linguagem jurídica (sem id de
   bloco, tag, placeholder ou chave de estado). Em `OK`,
   `dados_nao_bloqueantes` lista os trechos factuais omitidos por falta
   de prova.
5. **Topic Matrix pública derivada só do manifesto.**
   `ede_preparar_contestacao` publica perguntas, fatos públicos e as
   partes redigíveis pela LLM (Skills autorizadas/vedadas, validações);
   `ede_finalizar_peca` recebe `topicos`/`fatos_publicos` no lugar de
   `block_decisions` quando a versão ativa tem manifesto (e recusa
   `block_decisions` nesse caso, e `topicos` no contrato legado).

## Persistência do Modelo V1

Objeto novo, sem sobrescrever o vigente:
`gs://ede-legal-mcp-01-modelo-oficial-privado/modelo-oficial/v1/modelo-oficial.docx`,
geração `1790263782666106`, 1.803.017 bytes, criado com
`--if-generation-match=0` e verificado por download da geração exata
(SHA-256 idêntico). O objeto vigente
(`modelo-oficial/modelo-oficial.docx#1789696822240267`) está intacto. O
DOCX nunca entra no Git nem na imagem (ADR-0009); cópia local de
desenvolvimento em `templates/contestacao/v1/modelo-oficial.docx`
(gitignored).

## Achado corrigido no mesmo gate

Round-trip com dois placeholders no mesmo parágrafo (tópico 2.4) sempre
falhava — defeito preexistente, também no modelo atual, fail-closed.
`scripts/docx_round_trip.py` passou a exigir todos os segmentos fixos e
uma captura por ocorrência (SPEC §63.4). Template Lock, fidelidade
independente e renderer inalterados. Não há hotfix em produção: a
correção só vai para produção depois de provada no homolog.

## Fora do escopo (pendências)

* Zonas VLA pelo MCP — PEND-015 (D3).
* Tempestividade E2 — PEND-016 (D4); `TEMPESTIVIDADE_CASO` segue vindo
  do host.
* Orquestração voltada ao advogado não é declarada concluída.

## Consequências

* O mesmo código serve a produção (contrato legado) e o homolog (V1),
  decidido só pela configuração pinada; promover a V1 para produção será
  uma troca de configuração (objeto/geração/SHA), com autorização
  própria.
* Uma versão futura do modelo = nova entrada no registro + catálogo e
  manifesto fixados por SHA, nunca edição da versão anterior.
