#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_legal_validation.py — Fase 5 (Validação Jurídica), SPEC-0001 §27-32.

Mesmo padrão de tests/test_rag_search.py e tests/test_template_engine.py:
sem framework, asserts + `if __name__ == "__main__"`.

Usa exclusivamente o corpus legislativo público (CPC/CC/CDC/L8987/L9427/
REN1000) já versionado no núcleo do plugin. Nenhuma fixture usa dado real
de cliente/processo — PEND-002/ADR-0006: rag/jurisprudencia/ não é lido
aqui, nem em nenhum outro teste deste arquivo.

Uso:
  python tests/test_legal_validation.py
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "rag"))
from legal_validation import (  # noqa: E402
    classificar_autoridade,
    enriquecer_resultados,
    fonte_juridica,
    parse_citacao,
    validar_citacao,
    vigencia_de,
)
from legal_validation.models import AUTHORITY_LEVELS, VALIDATION_STATUS, VIGENCIA_STATUS  # noqa: E402


# ------------------------------------------------------ §27 — metadados
def test_metadados_modelo_canonico_completo():
    f = fonte_juridica(source_id="x", tipo="legislacao", diploma="D", norma="N",
                        artigo="1", texto="t", fonte="F", url="http://x",
                        vigencia="VIGENTE", data_verificacao="2026-01-01",
                        authority_level="OFICIAL", validation_status="VALIDADA")
    assert f["diploma"] == "D" and f["url"] == "http://x"
    assert f["vigencia"] == "VIGENTE" and f["data_verificacao"] == "2026-01-01"


def test_metadados_modelo_canonico_parcial_nao_inventa_campo_ausente():
    # campos não informados ficam None/default explícito — nunca preenchidos
    # por adivinhação.
    f = fonte_juridica(source_id="x", tipo="legislacao")
    assert f["url"] is None
    assert f["data_verificacao"] is None
    assert f["paragrafo"] is None and f["inciso"] is None and f["alinea"] is None
    assert f["vigencia"] == "NAO_VERIFICADA"          # default fail-closed
    assert f["authority_level"] == "NAO_VERIFICADA"   # default fail-closed
    assert f["validation_status"] == "NAO_VALIDADA"   # default fail-closed


def test_metadados_enum_invalido_falha_explicito():
    try:
        fonte_juridica(source_id="x", tipo="legislacao", vigencia="INVENTADA")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


def test_metadados_autoridade_oficial_para_corpus_conhecido():
    assert classificar_autoridade("CPC") == "OFICIAL"
    assert classificar_autoridade("REN1000") == "OFICIAL"


def test_metadados_autoridade_nao_verificada_para_corpus_desconhecido():
    # fonte desconhecida (ex.: corpus ainda não indexado) -> NAO_VERIFICADA,
    # nunca um nível de confiança inventado.
    assert classificar_autoridade("JURISPRUDENCIA_INEXISTENTE") == "NAO_VERIFICADA"
    assert classificar_autoridade("") == "NAO_VERIFICADA"


def test_metadados_vigencia_sempre_nao_verificada_hoje():
    # REQ-026: sem fonte real de verificação de vigência na infraestrutura
    # atual, o estado é sempre NAO_VERIFICADA — nunca VIGENTE por presunção.
    assert vigencia_de("CPC", 373) == "NAO_VERIFICADA"
    assert vigencia_de("CORPUS_QUALQUER", None) == "NAO_VERIFICADA"


def test_metadados_ausencia_de_url_e_data_verificacao_ficam_null():
    r = validar_citacao("art. 373, II, CPC", sugerir_candidato=False)
    assert r["fonte"]["url"] is None
    assert r["fonte"]["data_verificacao"] is None


# ------------------------------------------------------ §28 — citações
def test_citacao_artigo_existente():
    r = validar_citacao("art. 335 do CPC", sugerir_candidato=False)
    assert r["status"] == "VALIDADA"
    assert r["fonte"]["artigo"] == "335"


def test_citacao_artigo_inexistente():
    r = validar_citacao("art. 9999 do CPC", sugerir_candidato=False)
    assert r["status"] == "NAO_VALIDADA"
    assert r["fonte"] is None


def test_citacao_inciso_correto():
    r = validar_citacao("art. 373, II, CPC", sugerir_candidato=False)
    assert r["status"] == "VALIDADA"
    assert r["fonte"]["inciso"] == "II"


def test_citacao_inciso_incorreto():
    # art. 373 caput só tem I e II — III só existe dentro do § 3º.
    r = validar_citacao("art. 373, III, CPC", sugerir_candidato=False)
    assert r["status"] == "NAO_VALIDADA"
    assert "III" in r["motivo"]


def test_citacao_paragrafo_correto():
    r = validar_citacao("art. 370, paragrafo unico, CPC", sugerir_candidato=False)
    assert r["status"] == "VALIDADA"
    assert r["fonte"]["paragrafo"] == "unico"


def test_citacao_paragrafo_inexistente():
    r = validar_citacao("art. 335, § 9º, CPC", sugerir_candidato=False)
    assert r["status"] == "NAO_VALIDADA"
    assert "§ 9" in r["motivo"]


def test_citacao_diploma_correto():
    r = validar_citacao("art. 335 do CPC", sugerir_candidato=False)
    assert r["parsed"]["corpus"] == "CPC"


def test_citacao_diploma_incompativel():
    # art. 373 existe no CPC, não no CDC.
    r = validar_citacao("art. 373, II, CDC", sugerir_candidato=False)
    assert r["status"] == "NAO_VALIDADA"


def test_citacao_referencia_abreviada():
    r1 = validar_citacao("art. 335 CPC", sugerir_candidato=False)
    r2 = validar_citacao("artigo 335 do Código de Processo Civil", sugerir_candidato=False)
    assert r1["status"] == "VALIDADA"
    # "código de processo civil" por extenso também deve resolver o corpus
    assert r2["parsed"]["corpus"] == "CPC"


def test_citacao_referencia_ambigua():
    r = validar_citacao("art. 5º", sugerir_candidato=False)
    assert r["status"] == "AMBIGUA"


# ------------------------------------------------- §29 — anti-hallucination
def test_anti_hallucination_artigo_inexistente_nunca_vira_proximo():
    r = validar_citacao("art. 9999 do CPC", sugerir_candidato=True)
    assert r["status"] == "NAO_VALIDADA"
    # mesmo com sugestão de busca híbrida disponível, o status NUNCA muda
    # para VALIDADA a partir de um candidato por similaridade.
    assert r["source_id"] is None
    assert r["fonte"] is None


# ------------------------------------------------- §30 — incompatibilidade
def test_incompatibilidade_inciso_nao_e_promovida_por_proximidade():
    # se o candidato mais parecido (art. 373 I) não for o pedido (art. 373
    # III), o resultado tem que ser NAO_VALIDADA, nunca "quase certo".
    r = validar_citacao("art. 373, III, CPC", sugerir_candidato=False)
    assert r["status"] == "NAO_VALIDADA"
    assert r["confidence"] == 0.0


# --------------------------------------------------- §31 — vigência desconhecida
def test_vigencia_desconhecida_nao_vira_vigente_mesmo_com_artigo_validado():
    r = validar_citacao("art. 373, II, CPC", sugerir_candidato=False)
    assert r["status"] == "VALIDADA"                    # existência confirmada
    assert r["fonte"]["vigencia"] == "NAO_VERIFICADA"    # vigência não é inferida disso


# --------------------------------------------------- §32 — separação de scores
def test_score_alto_nao_implica_validado():
    sys.path.insert(0, str(BASE / "rag"))
    from search_hybrid import HybridSearcher
    s = HybridSearcher()
    res = s.search("servico adequado ao pleno atendimento dos usuarios", k=1)
    assert res[0]["score"] > 0.5  # score de fusão alto
    enr = enriquecer_resultados(res)
    assert enr[0]["validation_status"] == "NAO_VALIDADA"  # recuperado != validado
    assert enr[0]["vigencia"] == "NAO_VERIFICADA"


def test_indice_artigos_eh_validado_por_correspondencia_exata():
    sys.path.insert(0, str(BASE / "rag"))
    from search_hybrid import HybridSearcher
    s = HybridSearcher()
    res = s.query("art. 335 do CPC", k=1)
    enr = enriquecer_resultados(res)
    assert enr[0]["validation_status"] == "VALIDADA"


# --------------------------------------------------------- enums coerentes
def test_enums_sao_conjuntos_distintos():
    # os três eixos não podem colidir por acidente de nomenclatura.
    assert not (set(VALIDATION_STATUS) & set(AUTHORITY_LEVELS) - {"NAO_VERIFICADA"})
    assert "NAO_VERIFICADA" in VIGENCIA_STATUS
    assert "NAO_VERIFICADA" in AUTHORITY_LEVELS
    assert "NAO_VERIFICADA" not in VALIDATION_STATUS  # eixo de citação usa NAO_VALIDADA


def test_nenhum_corpus_indexado_e_jurisprudencia():
    # guarda de escopo (ADR-0006/PEND-002): a validação jurídica desta fase
    # só enxerga os corpora legislativos já indexados — jurisprudência
    # segue fora, nenhum source_id pode vir de lá.
    indice = json.load(open(BASE / "rag" / "index_artigos.json", encoding="utf-8"))
    assert "jurisprudencia" not in {c.lower() for c in indice["corpora"]}


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
