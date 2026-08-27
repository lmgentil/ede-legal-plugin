# Compactação do artefato LSA do RAG — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduzir o peso distribuído de `rag/embeddings/svd.joblib` sem retirar o fallback TF-IDF+LSA local, alterar o ranking jurídico ou adicionar dependências.

**Architecture:** O builder continuará produzindo um estimador `TruncatedSVD` Joblib compatível com o loader atual, mas converterá `components_` de `float64` para `float32` e usará compressão zlib nível 3. O manifesto registrará esse contrato de armazenamento; o loader o validará antes da desserialização, preservando a política fail-closed do ADR-0011.

**Tech Stack:** Python 3.12.10, NumPy 2.4.2, scikit-learn 1.9.0, Joblib 1.5.3, pytest 9.1.1.

**Spec:** `docs/specs/SPEC-0001.md` (REQ-019, REQ-021, REQ-045 e Fase 8 §53); `docs/adr/ADR-0011-compatibilidade-artefatos-rag.md`; decisão aprovada nesta tarefa e registrada em `docs/adr/ADR-0013-compactacao-artefato-lsa.md`.

## Global Constraints

- Preservar a busca híbrida e o fallback 100% local/offline.
- Não adicionar dependência nem reconstrução obrigatória na primeira utilização.
- Manter validação de runtime, integridade e armazenamento antes da desserialização.
- Não aceitar regressão no gold-set: mínimo existente de 18/24 top-1 e 21/24 top-3.
- Não alterar o corpus, o chunking, `N_COMPONENTS=256`, pesos do ranking ou embeddings dos documentos.
- Não realizar commit automático.

---

### Task 1: Contrato de armazenamento compacto

**Files:**
- Modify: `tests/test_rag_artifact_contract.py`
- Modify: `rag/embeddings/artifact_contract.py`

**Interfaces:**
- Consumes: `validar_contrato_lsa(manifesto: dict, diretorio: Path) -> None`.
- Produces: `formato_armazenamento_lsa() -> dict` e validação do campo `armazenamento` do manifesto.

- [ ] **Step 1: Write the failing tests**

Adicionar testes que exijam o contrato canônico `{"svd_components_dtype": "float32", "joblib_compress": "zlib", "joblib_compress_level": 3}` e rejeitem manifesto ausente ou divergente.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rag_artifact_contract.py -q`

Expected: FAIL porque o manifesto atual não declara `armazenamento` e o contrato ainda não o valida.

- [ ] **Step 3: Write minimal implementation**

Definir o formato canônico em `artifact_contract.py`, expô-lo por função que devolva cópia e compará-lo integralmente durante `validar_contrato_lsa`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rag_artifact_contract.py -q`

Expected: testes do contrato passam após os fixtures válidos declararem o novo campo.

### Task 2: Serialização compacta determinística

**Files:**
- Modify: `tests/test_rag_artifact_contract.py`
- Modify: `rag/embeddings/build_embeddings.py`
- Regenerate: `rag/embeddings/svd.joblib`
- Regenerate: `rag/embeddings/manifest.json`

**Interfaces:**
- Consumes: `formato_armazenamento_lsa() -> dict`.
- Produces: `compactar_svd(svd: TruncatedSVD) -> TruncatedSVD`, com `components_.dtype == numpy.float32`.

- [ ] **Step 1: Write the failing test**

Executar o builder sobre corpus mínimo e afirmar dtype `float32`, metadados canônicos no manifesto e arquivo compactado menor que a matriz `float64` equivalente.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rag_artifact_contract.py::test_build_grava_svd_float32_compressao_zlib -q`

Expected: FAIL porque o builder ainda grava `float64` sem compressão.

- [ ] **Step 3: Write minimal implementation**

Converter somente `svd.components_` com `astype(np.float32, copy=False)`, gravar com `joblib.dump(..., compress=("zlib", 3))` e incluir o contrato de armazenamento no manifesto antes do cálculo dos hashes.

- [ ] **Step 4: Run tests to verify it passes**

Run: `python -m pytest tests/test_rag_artifact_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Regenerate official artifacts**

Run: `python rag/embeddings/build_embeddings.py`

Expected: novo `svd.joblib` em torno de 34 MiB e `manifest.json` com hashes atualizados.

### Task 3: Documentação e encerramento da pendência

**Files:**
- Create: `docs/adr/ADR-0013-compactacao-artefato-lsa.md`
- Modify: `docs/PENDENCIAS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: medições reais de tamanho, tempo de carga e gold-set.
- Produces: decisão arquitetural auditável e encerramento de `PEND-003`.

- [ ] **Step 1: Record the accepted decision**

Documentar alternativas medidas: float32+zlib recomendada; float16 rejeitada por margem numérica; reconstrução sob demanda rejeitada por UX/runtime; Git LFS rejeitado por não reduzir o pacote instalado.

- [ ] **Step 2: Reconcile pending work**

Mover `PEND-003` para resolvida, registrar tamanho anterior/novo, impacto e referência ao ADR-0013.

- [ ] **Step 3: Update changelog**

Registrar a compactação em `[Não publicado]`, sem declarar versão ou publicação.

### Task 4: Verificação final

**Files:**
- Verify: `rag/embeddings/manifest.json`
- Verify: `tests/test_rag_artifact_contract.py`
- Verify: `tests/test_rag_search.py`
- Verify: `tests/test_pacote_distribuicao.py`

**Interfaces:**
- Consumes: artefatos regenerados e documentação atualizada.
- Produces: evidência de compatibilidade, qualidade e redução distributiva.

- [ ] **Step 1: Run focused contract tests**

Run: `python -m pytest tests/test_rag_artifact_contract.py -q`

- [ ] **Step 2: Run RAG segment and gold-set**

Run: `python -m pytest -m rag -q`

Run: `python rag/avaliar_recuperacao.py`

- [ ] **Step 3: Run distribution tests**

Run: `python -m pytest tests/test_pacote_distribuicao.py tests/test_marketplace.py -q`

- [ ] **Step 4: Run full suite applicable to the repository**

Run: `python -m pytest -q`

- [ ] **Step 5: Inspect final state**

Run: `git diff --check`

Run: `git status --short`

Expected: no whitespace errors; only scoped changes plus pre-existing `.claude/` and generated `graphify-out/` remain untracked.
