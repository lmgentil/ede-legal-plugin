# EDE Legal Plugin

Plugin jurídico para [Claude Code](https://claude.com/claude-code) destinado
à elaboração assistida de peças processuais, combinando Skills jurídicas
especializadas, um modelo DOCX institucional protegido (Template Lock) e um
RAG jurídico próprio (busca híbrida lexical + vetorial sobre legislação e
jurisprudência).

O primeiro módulo processual suportado é a **Contestação**. A arquitetura é
projetada para permanecer extensível a outros tipos de peça — ver
[`CLAUDE.md`](./CLAUDE.md) e [`docs/specs/SPEC-0001.md`](./docs/specs/SPEC-0001.md).

## Status atual (v0.7.0 — Fase 7 de 9 aprovada)

🚧 **Em desenvolvimento. A integração end-to-end da Contestação está
comprovada sobre um caso sintético (Fase 7); atualização/distribuição
(Fase 8) e hardening final (Fase 9) ainda não foram feitos.**

| Camada | Status |
|---|---|
| Estrutura do plugin, versionamento, segurança básica | ✅ Fase 1 |
| Skills transversais (redator, humanizer, calendário) | ✅ Fase 2 |
| Template Engine + Template Lock | ✅ Fase 3 — ver pendência PEND-001 abaixo |
| RAG jurídico | ✅ Fase 4 (legislação/regulamentos); jurisprudência adiada — `PEND-002` |
| Validação jurídica (citações, vigência, rastreabilidade) | ✅ Fase 5 |
| Skill Contestação + estrategista-contestacao-ede (orquestração obrigatória) | ✅ Fase 6 |
| Integração end-to-end (`scripts/gerar_contestacao.py`) | ✅ Fase 7 — caso sintético, ver `docs/E2E_FASE7.md` |
| Atualização/distribuição (`/updateEde`) | ⏳ Fase 8 |
| Hardening final | ⏳ Fase 9 |

O progresso por fase é controlado por gates explícitos — ver `CLAUDE.md §4`.
Nenhuma fase é iniciada sem autorização.

> **PEND-001** (`docs/PENDENCIAS.md`, status `DEFERRED` desde a correção
> v0.6.1): suporte a imagem embutida no placeholder
> `FOTOS_DA_IRREGULARIADE` não será automatizado na V1 — decisão explícita
> do usuário. O campo recebe um marcador textual de inserção manual pelo
> advogado. Não bloqueia a Fase 8.

## RAG jurídico (já funcional)

O componente de recuperação de conhecimento jurídico (`rag/`) foi migrado de
um projeto anterior e já está operacional, independente do restante do
plugin:

- 434 chunks cobrindo 6 diplomas (CPC, Código Civil, CDC, Lei 8.987/1995,
  Lei 9.427/1996, REN ANEEL 1.000/2021), com cobertura de artigos de 100%.
- Busca híbrida (BM25 + embeddings) com lookup direto por número de artigo.
- Camada de confiança calibrada (alta/média/baixa) e avaliação de regressão
  contra um gold-set de consultas.

```bash
pip install -r rag/requirements.txt
python rag/search_hybrid.py "prazo para contestação no procedimento comum"
python rag/search_hybrid.py "art. 373 CPC"
```

Detalhes em [`rag/CONTEXTO_RAG.md`](./rag/CONTEXTO_RAG.md).

> A jurisprudência curada do escritório (`rag/jurisprudencia/`) existe
> localmente mas **não é distribuída com o repositório público** e ainda não
> está integrada à busca híbrida — ver
> [`docs/adr/ADR-0006-assets-institucionais.md`](./docs/adr/ADR-0006-assets-institucionais.md).

## Documentação

- [`CLAUDE.md`](./CLAUDE.md) — regras operacionais permanentes do agente.
- [`docs/specs/SPEC-0001.md`](./docs/specs/SPEC-0001.md) — especificação da Arquitetura v1.
- [`docs/adr/`](./docs/adr/) — decisões arquiteturais registradas.
- [`docs/PENDENCIAS.md`](./docs/PENDENCIAS.md) — pendências abertas com ID rastreável e fase de bloqueio.
- [`CHANGELOG.md`](./CHANGELOG.md) — histórico de mudanças.

## Licença

Ver [`LICENSE`](./LICENSE). Repositório público para fins de transparência;
não constitui licença de uso, cópia ou redistribuição.
