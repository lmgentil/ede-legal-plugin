#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rag_search.py — regressão do que a Fase 4 (RAG Jurídico) alterou em
rag/search_hybrid.py: religação de rag/config.yaml (REQ-044) e o novo
estágio de reranking (SPEC-0001 §15: fusão -> reranking -> contexto).

Sem framework de teste — mesmo padrão de rag/avaliar_recuperacao.py e
tests/test_template_engine.py: asserts + `if __name__ == "__main__"`.

A qualidade de recuperação em si (ingestão/chunking/embeddings/busca
lexical/busca vetorial/fusão já existentes antes da Fase 4) é coberta por
rag/avaliar_recuperacao.py contra o gold-set — chamado aqui como guarda de
regressão (TEST-007), não reimplementado.

Uso:
  python tests/test_rag_search.py
"""
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "rag"))
import search_hybrid as sh  # noqa: E402

pytestmark = pytest.mark.rag


def test_config_yaml_foi_lido():
    # Se pyyaml está instalado (requirements.txt) e rag/config.yaml existe,
    # _CONFIG não pode ficar vazio — senão REQ-044 silenciosamente voltou a
    # usar só os defaults hardcoded sem avisar por que.
    assert sh.yaml is not None, "pyyaml ausente — instale (rag/requirements.txt)"
    assert sh._CONFIG, "config.yaml não foi carregado (ficou {})"
    assert sh._CONFIG["busca_hibrida"]["alpha"] == sh.ALPHA_PADRAO


def test_config_valores_batem_com_defaults_originais():
    # config.yaml precisa refletir os mesmos números que já estavam
    # hardcoded (nenhuma mudança de comportamento é esperada da religação).
    assert sh.ALPHA_PADRAO == 0.65
    assert sh.CONF_LSA == {"alta_bm": 10.0, "alta_cos": 0.60, "alta_cob": 0.85,
                            "baixa_bm": 6.0, "baixa_cos": 0.50, "baixa_cob": 0.50}
    assert sh.CONF_SEM == {"alta_bm": 9.0, "alta_cob": 0.75,
                            "alta_cos": 0.55, "baixa_S": 1.4}


def test_config_ausente_cai_para_defaults(tmp_path=None):
    # _cfg() com caminho inexistente sempre retorna o default pedido,
    # simulando config.yaml sem uma chave nova (fail-open, não fail-closed —
    # REQ-044 é sobre organização de config, não integridade jurídica).
    assert sh._cfg(["chave", "que", "nao", "existe"], "default") == "default"
    assert sh._cfg(["busca_hibrida", "alpha"], "default") == 0.65


def test_tokenize_normaliza_acentos_e_remove_stopword():
    # comportamento pré-existente (não alterado nesta fase): STOPWORDS tem
    # entradas acentuadas ("não", "à") que não batem contra token já
    # normalizado ("nao") — "nao" passa. Registrado aqui como característica
    # conhecida, não como bug corrigido nesta fase.
    toks = sh.tokenize("A Contestação não foi apresentada")
    assert toks == ["contestacao", "nao", "apresentada"]


def test_detect_articles_simples_e_multiplo():
    arts, corpus = sh.detect_articles("art. 335 do CPC")
    assert arts == [335]
    assert corpus == "CPC"
    arts2, _ = sh.detect_articles("arts. 186, 927 e 944 do Código Civil")
    assert arts2 == [186, 927, 944]


def test_rerank_reordena_por_cobertura():
    # candidato B tem score de fusão menor, mas cobertura bem maior —
    # com peso alto o suficiente, deve passar à frente de A.
    candidatos = [
        {"score": 0.50, "cobertura": 0.10, "id": "A"},
        {"score": 0.48, "cobertura": 0.90, "id": "B"},
    ]
    resultado = sh.HybridSearcher._rerank(candidatos, peso_cobertura=1.0)
    assert [c["id"] for c in resultado] == ["B", "A"]
    # com peso 0, a ordem de fusão original (por score) é preservada
    resultado0 = sh.HybridSearcher._rerank(candidatos, peso_cobertura=0.0)
    assert [c["id"] for c in resultado0] == ["A", "B"]


def test_lookup_article_e_ranking_hibrido_smoke():
    s = sh.HybridSearcher()
    # camada 1: lookup exato por artigo — determinístico, não depende de
    # ranking de embeddings.
    hits = s.lookup_article(335, corpus="CPC")
    assert any(h["file_name"] == "Chunk_047_DA_CONTESTACAO.md" for h in hits)
    # camada 2: busca híbrida deve retornar k resultados válidos, todos com
    # os campos que o reranking espera.
    res = s.search("serviço adequado ao pleno atendimento dos usuários", k=3)
    assert len(res) <= 3
    assert all({"score", "cobertura", "via"} <= r.keys() for r in res)


def test_regressao_gold_set():
    # Guarda de regressão de qualidade (TEST-007): mesmo comando que
    # CLAUDE.md §22 manda rodar antes de fechar a fase. avaliar_recuperacao.py
    # já sai com código != 0 se top-1 cair abaixo de 60%.
    r = subprocess.run([sys.executable, str(BASE / "rag" / "avaliar_recuperacao.py")],
                        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"regressão na recuperação do RAG:\n{r.stdout}\n{r.stderr}"


if __name__ == "__main__":
    testes = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
