# ADR-0013 — Compactação do artefato LSA distribuído

* **Status:** Aceito
* **Data:** 2026-08-27
* **Relacionado:** SPEC-0001, REQ-019, REQ-021, REQ-045; PEND-003; ADR-0011

## Contexto

O fallback TF-IDF+LSA precisa acompanhar o plugin para que a busca híbrida
funcione localmente e sem preparação manual. O artefato
`rag/embeddings/svd.joblib`, porém, ocupava 81.097.447 bytes (77,34 MiB) e
respondia pela maior parte do repositório distribuído.

A decomposição do objeto mostrou que 81.090.560 bytes estavam concentrados
em `TruncatedSVD.components_`, uma matriz `(256, 39595)` em `float64`. Os
demais arrays do estimador somavam somente 6 KiB. Portanto, a redução poderia
ser obtida no próprio formato numérico, sem retirar o índice do pacote nem
redesenhar a recuperação.

Ensaios sobre o artefato real produziram:

| Variante | Tamanho | Carga aproximada | Gold-set |
|---|---:|---:|---:|
| `float64`, sem compressão (anterior) | 77,34 MiB | 0,32 s | 18/24 top-1; 21/24 top-3 |
| `float64`, zlib nível 3 | 67,90 MiB | 2,95 s | equivalente |
| `float32`, sem compressão | 38,67 MiB | 0,19 s | equivalente |
| `float32`, zlib nível 3 | 33,74 MiB no ensaio | 1,46 s | equivalente |
| `float16`, zlib nível 3 | 17,73 MiB | 0,26 s | equivalente no gold-set atual |

## Decisão

O builder converte exclusivamente `TruncatedSVD.components_` para `float32`
depois do treinamento e serializa o estimador com Joblib usando zlib nível 3.
O modelo continua sendo um `TruncatedSVD` padrão; a interface do loader e a
dimensão 256 permanecem inalteradas.

O manifesto passa a declarar o contrato de armazenamento:

```json
{
  "svd_components_dtype": "float32",
  "joblib_compress": "zlib",
  "joblib_compress_level": 3
}
```

O loader exige correspondência exata desse contrato antes de desserializar os
artefatos. Runtime e SHA-256 continuam validados segundo o ADR-0011.

Após a regeneração oficial, `svd.joblib` passou a 35.848.840 bytes
(34,19 MiB), redução de 55,8% em relação ao artefato anterior.

## Alternativas consideradas

- **`float16` + zlib:** rejeitada. Embora tenha preservado o gold-set atual,
  reduz excessivamente a margem numérica para ganho que não é necessário à
  distribuição presente.
- **Somente compressão, mantendo `float64`:** rejeitada. Reduz pouco o arquivo
  e aumenta o tempo de carga mais que a solução escolhida.
- **Reconstrução local na primeira utilização:** rejeitada. Retiraria o peso
  do pacote, mas exigiria runtime de build, aumentaria muito a primeira
  execução e exporia ao advogado uma preparação que a SPEC procura ocultar.
- **Git LFS ou asset externo:** rejeitada para esta correção. Muda onde o blob
  é armazenado, mas não garante redução do pacote instalado nem funcionamento
  offline imediato.

## Consequências

- O fallback LSA permanece incluído, local, offline e imediatamente utilizável.
- Não há dependência nova, download posterior ou mudança no corpus/ranking.
- O carregamento do SVD compactado tem pequeno custo adicional, medido em
  aproximadamente 1,5 s no ambiente de referência.
- Builders antigos e manifestos sem o contrato de armazenamento passam a ser
  rejeitados explicitamente e devem regenerar o índice.
- Alterar dtype ou compressão exige nova decisão, regeneração e atualização do
  manifesto, dos hashes e do teste de recuperação.
