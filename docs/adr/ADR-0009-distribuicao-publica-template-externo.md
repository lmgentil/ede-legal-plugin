# ADR-0009 — Distribuição pública do plugin com template institucional externo

## Status

Aceito (2026-08-18) — consolidação pós-Fase 8. Publicação externa (remote
GitHub, visibilidade, push, release) **não autorizada por esta ADR** — só
a decisão arquitetural e a arquitetura técnica que a implementa.

## Contexto

`ADR-0008` (Fase 8) deixou dois pontos explicitamente em aberto: (1) se o
repositório seria de fato publicado publicamente, e (2) o destino do
template institucional real (`templates/contestacao/modelo-oficial.docx`),
com três alternativas apresentadas em `ADR-0006` (público / privado
separado / download autenticado). Esta ADR fecha os dois — não como uma
nova análise, mas como registro formal de decisões já tomadas pelo
titular do projeto.

## Decisão

1. **Repositório e plugin serão públicos no GitHub.** Qualquer pessoa
   poderá tecnicamente visualizar, clonar e baixar o código, adicionar o
   marketplace e instalar o plugin — sem precisar ser colaborador
   autorizado do repositório. Isso é **acesso técnico**, não é o mesmo
   que **autorização jurídica irrestrita**: os direitos de uso,
   modificação, redistribuição e exploração continuam disciplinados pela
   `LICENSE` (redação final pendente — `PEND-004`, gate próprio, não
   decidida por esta ADR).
2. **`templates/contestacao/modelo-oficial.docx` é definitivamente um
   asset externo ao plugin — decisão encerrada.** Não integra o
   repositório, não é distribuído com o plugin, não é asset do
   marketplace, nunca é baixado/reconstruído automaticamente. É fornecido
   fora deste repositório, diretamente, aos usuários autorizados a
   recebê-lo. **Não reabrir as alternativas A/B/C de `ADR-0006`** — a
   pergunta ali estava "o que fazer com o template", a resposta é esta.
3. **Separação motor × asset institucional, formalizada:**

   ```text
   EDE LEGAL PLUGIN (público, motor)          MODELO OFICIAL (externo)
   ├── Skills                                 └── modelo-oficial.docx
   ├── scripts (RAG, validação, Template          fornecido separadamente,
   │   Engine, Template Lock)                     fora do plugin, a quem
   ├── rag/ (corpus legislativo + embeddings)      tiver autorização
   ├── templates/contestacao/schema.json
   ├── tests/
   └── documentação
   ```

   `schema.json` (o contrato de 13 placeholders entre a Skill
   `contestacao` e o Template Engine) **permanece público** — ele não
   contém o timbrado, só a lista de campos.
4. **Ausência do template não é falha de instalação.** Uma instalação
   pública limpa nunca terá o `.docx` — isso é esperado, não um sinal de
   plugin quebrado. `scripts/validar_instalacao.py` já trata esse item
   como opcional (não obrigatório) para reportar `STATUS: OK`.
5. **Fail closed, só na etapa que depende do asset.** Gerar o DOCX final
   sem o template presente interrompe especificamente o estágio
   `template_engine` do pipeline (`scripts/gerar_contestacao.py` →
   `PIPELINE_ABORTED`), preservando todo o restante do fluxo (fatos,
   tempestividade, estratégia, RAG, validação jurídica, redação,
   humanização) como já concluído. Nunca inventa, baixa ou reconstrói um
   template substituto.

## Razões

* Instalação simples via Claude Code Plugin Marketplace, sem exigir Git
  do usuário final (CLAUDE.md §25).
* Transparência técnica: o repositório serve como demonstração pública de
  arquitetura de software jurídico (RAG, validação anti-alucinação,
  proveniência factual, orquestração de Skills, Template Lock) sem expor
  nenhum dado confidencial — nem de cliente, nem do próprio timbrado do
  escritório.
* Separação clara de responsabilidade: o motor é reaproveitável por
  qualquer escritório que forneça seu próprio template; o timbrado nunca
  precisa (nem deve) viajar pelo mesmo canal de distribuição pública do
  código.

## Alternativas consideradas

Já registradas e descartadas em `ADR-0006` (opção A — template público
junto do plugin; opção C — download de origem autenticada, não
implementado). Esta ADR não reabre essa análise — confirma a opção B
(template privado, fornecido separadamente) como decisão final.

## Consequências

* `ADR-0006` deixa de ter esse ponto como questão aberta — atualizada com
  referência cruzada a esta ADR.
* `tests/test_pacote_distribuicao.py` ganha checagens permanentes: o
  template nunca esteve no histórico git (não só fora do índice atual),
  não é referenciado no `marketplace.json`, e o Template Engine falha
  explicitamente (não silenciosamente) quando ausente.
* `README.md` ganha seção própria ("Template institucional") explicando
  isso a quem for instalar.
* A publicação pública em si (remote, push, visibilidade, release)
  continua bloqueada por `PEND-004` (definição da `LICENSE`) — essa ADR
  não a desbloqueia.

## Atualização — Gate PEND-004 resolvido (2026-08-18)

`PEND-004` foi resolvida: `LICENSE` reescrita como licença proprietária
source-available, implementando a matriz de direitos aprovada
(permitido sem autorização / permitido com condições / proibido sem
autorização prévia por escrito) — ver `docs/PENDENCIAS.md` para o
mapeamento seção a seção. Isso remove o único bloqueio jurídico
identificado por esta ADR para a publicação externa. Nenhum remote foi
criado, nenhum push ou publicação foi realizado — essa continua sendo
uma decisão e ação operacional futura, separada da definição da licença.
