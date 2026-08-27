# ADR-0011 — Compatibilidade e integridade dos artefatos LSA do RAG

* **Status:** Aceito
* **Data:** 2026-08-27
* **Relacionado:** SPEC-0001, REQ-045

## Contexto

Os estimadores `vectorizer.joblib` e `svd.joblib` haviam sido gerados com
scikit-learn 1.7.2 e eram carregados por um runtime com scikit-learn 1.9.0.
O carregamento entre versões não é suportado pelo formato Joblib/Pickle e
emitia avisos de incompatibilidade. Além disso, o manifesto não permitia
provar em qual runtime os artefatos foram gerados nem se haviam sido
alterados depois do build.

## Decisão

O fallback TF-IDF+LSA passa a ter um runtime canônico, fixado em
`rag/requirements.txt`, com Python 3.12.10 e versões exatas das bibliotecas
que afetam geração, persistência e leitura.

O builder registra em `rag/embeddings/manifest.json`:

- versão exata do Python e dos pacotes relevantes;
- hash SHA-256 do Parquet combinado, do vetorizador e do SVD.

Antes de abrir Parquet ou desserializar Joblib, o loader compara o runtime
instalado com o manifesto e verifica existência, nome e hash dos arquivos.
Qualquer divergência aborta a busca LSA e orienta a regeneração. Compatibilidade
nunca é presumida nem reduzida a warning.

## Alternativas consideradas

- **Manter os binários antigos e instalar scikit-learn 1.7.2:** rejeitada;
  conserva artefatos sem proveniência e posterga a incompatibilidade.
- **Silenciar os warnings:** rejeitada; oculta risco de resultado incorreto ou
  falha futura sem estabelecer compatibilidade.
- **Migrar agora para ONNX ou skops:** rejeitada nesta correção; aumentaria o
  escopo e não é necessária para o índice local de 434 chunks.

## Consequências

- Mudança de Python ou de qualquer pacote declarado exige regenerar o índice.
- Artefatos legados ou adulterados falham antes da desserialização.
- O build torna-se reproduzível e auditável, ao custo de versões deliberadamente
  rígidas no runtime LSA.
- O índice semântico opcional permanece independente; este contrato se aplica
  aos artefatos do fallback TF-IDF+LSA.
