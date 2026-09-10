#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_template.py — Etapa 5.10, Microfix 7.1: "fix(template):
alinhar validador ao pipeline por blocos".

Cobre os dois gaps revelados pelo Commit 7 (homologação de distribuição):
  A. scripts/validate_template.py podia propagar PacoteDocxAbortada crua
     para input DOCX inválido/incompleto.
  B. scripts/validate_template.py produzia falso negativo contra o Modelo
     Oficial real porque reconstruía a peça de referência via
     docx_template_engine.gerar_peca() (sem composição de blocos/zonas),
     enquanto toda Contestação real é gerada via
     docx_block_engine.gerar_peca_com_blocos().

Por que estes testes usam o Modelo Oficial REAL (docx_real), não um
catálogo sintético mínimo: `docx_numeracao_engine.py` (acionado por
gerar_peca_com_blocos em toda geração) localiza os títulos de nível 2/3
por ÂNCORAS DE TEXTO HARDCODED, específicas do template real (`NOS_
LITERAIS`) — não deriva nada de blocos.json. Não é possível reproduzir
`gerar_peca_com_blocos()` chegando ao fim (renumeração/Template Lock)
contra um template sintético com nós fora desse catálogo; o mesmo motivo
já leva os testes completos equivalentes de docx_block_engine.py
(`test_pipeline_completo_com_blocos_contra_template_real`, em
test_docx_block_engine.py) a serem `docx_real`, não sintéticos — este
arquivo segue a mesma convenção já estabelecida, não inventa uma nova. O
único cenário aqui que dispensa o asset é o de "bug inesperado" (item 7),
que nunca chega a uma composição real (a função é substituída por um
mock antes de qualquer geração).

Uso:
  python tests/test_validate_template.py
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import validate_template as vt  # noqa: E402
from docx_package import empacotar_pacote_docx, extrair_pacote_docx  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"
FIXTURE_HAPPY_PATH = BASE / "tests" / "fixtures" / "contestacao" / "happy_path"

# Âncora institucional real, hardcoded pelo próprio docx_numeracao_engine.py
# (NOS_LITERAIS, nó "LEGALIDADE_PROCEDIMENTOS", obrigatório em toda
# Contestação) — reaproveitada aqui como alvo de adulteração no teste 6
# (texto fixo, nunca gerado/tocado pelo pipeline), não um valor novo
# inventado por este arquivo.
_ANCORA_INSTITUCIONAL_REAL = "LEGALIDADE DOS PROCEDIMENTOS"


def _pular_se_sem_template_real():
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")


def _reconstruir_dados_e_decisoes():
    """(dados, decisoes_blocos) do cenário happy_path real — mesma técnica
    de reconstrução read-only já usada por scripts/homologar_distribuicao.py
    (chama de novo as etapas determinísticas de gerar_contestacao.py, sem
    reimplementar nada nem depender de DataJud real)."""
    sys.path.insert(0, str(BASE / "scripts"))
    import gerar_contestacao  # noqa: E402
    from test_e2e_contestacao import _resolver_juizo_stub  # noqa: E402

    decisoes_blocos = json.loads((FIXTURE_HAPPY_PATH / "decisoes_blocos.json").read_text(encoding="utf-8"))
    stages_aux = []
    tempestividade_valor = gerar_contestacao._etapa_tempestividade(FIXTURE_HAPPY_PATH, stages_aux)
    dados = gerar_contestacao._etapa_placeholders(FIXTURE_HAPPY_PATH, stages_aux, tempestividade_valor,
                                                   _resolver_juizo_stub)
    assert isinstance(dados, dict), dados  # não PIPELINE_ABORTED
    return dados, decisoes_blocos


def _gerar_docx_real(tmp: Path, dados: dict, decisoes_blocos: dict) -> Path:
    from docx_block_engine import gerar_peca_com_blocos
    gerado = tmp / "gerado.docx"
    relatorio = gerar_peca_com_blocos(str(TEMPLATE_REAL), str(SCHEMA_REAL), str(CATALOGO_REAL),
                                       dados, decisoes_blocos, str(gerado))
    assert relatorio["status"] == "OK", relatorio
    return gerado


# --------------------------------------------------------------- 3: sem falso negativo (gap B)
@pytest.mark.docx_real
def test_modelo_oficial_real_sem_falso_negativo_por_blocos_excluidos():
    """Reproduz exatamente o cenário que revelou o gap B no Commit 7:
    happy_path real (vários blocos EXCLUIR — PRELIMINAR_ILEGITIMIDADE_
    ATIVA_TERCEIRO/PRELIMINAR_IMPUGNACAO_VALOR_CAUSA/LICITUDE_CORTE_
    SUSPENSAO/etc., cujos placeholders CONTA_CONTRATO/NOME_TITULAR_DA_UC/
    VALOR_DA_CAUSA/VALOR_TOTAL_PROVEITO_ECONOMICO nunca aparecem em
    `dados`) contra o Modelo Oficial real — antes do microfix, `ok` vinha
    `false` cobrando exatamente esses placeholders como residuais; agora
    deve validar normalmente (item 4 do pedido: bloco excluído não exige
    o placeholder correspondente)."""
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()
    assert "CONTA_CONTRATO" not in dados  # confirma a premissa do gap: bloco excluído, dado nunca fornecido
    assert "VALOR_DA_CAUSA" not in dados

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gerado = _gerar_docx_real(tmp, dados, decisoes_blocos)
        r = vt.validar_template(gerado, dados, decisoes_blocos, TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)
        assert r["ok"] is True, r["divergencias"]
        assert r["divergencias"] == []


# --------------------------------------------------------------- 4: alternar bloco para EXCLUIR
@pytest.mark.docx_real
def test_bloco_excluido_nao_exige_placeholder_residual():
    """DESCABIMENTO_DANO_MORAL alternado de INCLUIR (baseline) para
    EXCLUIR — `dados` continua trazendo VALOR_DANO_MORAL_PRETENDIDO (não
    filtrado, mesmo dict do caso), mas o placeholder não sobrevive à
    composição; não pode ser cobrado como residual."""
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()
    decisoes_blocos = dict(decisoes_blocos)
    decisoes_blocos["DESCABIMENTO_DANO_MORAL"] = {"decisao": "EXCLUIR"}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gerado = _gerar_docx_real(tmp, dados, decisoes_blocos)
        r = vt.validar_template(gerado, dados, decisoes_blocos, TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)
        assert r["ok"] is True, r["divergencias"]


# --------------------------------------------------------------- 5: alternar bloco para INCLUIR sem dado
@pytest.mark.docx_real
def test_bloco_incluido_continua_exigindo_placeholder():
    """PRELIMINAR_INEPCIA_INICIAL (decision_mode='estrategista', placeholder
    próprio SINOPSE_FATOS_NUCLEO_OBJETO) alternado de EXCLUIR (baseline)
    para INCLUIR sem fornecer esse placeholder — a própria RECONSTRUÇÃO da
    referência deve falhar (validacao_placeholders), provando que a
    correção do gap B não enfraqueceu a exigência de placeholder para
    bloco incluído."""
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()
    assert "SINOPSE_FATOS_NUCLEO_OBJETO" not in dados  # confirma a premissa antes de alternar
    decisoes_blocos = dict(decisoes_blocos)
    decisoes_blocos["PRELIMINAR_INEPCIA_INICIAL"] = {"decisao": "INCLUIR"}

    r = vt.validar_template("qualquer.docx", dados, decisoes_blocos, TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)
    assert r["ok"] is False
    assert any("TEMPLATE_INCOMPATIVEL" in d for d in r["divergencias"])
    assert any("SINOPSE_FATOS_NUCLEO_OBJETO" in d for d in r["divergencias"])


# --------------------------------------------------------------- 1: DOCX corrompido (gap A)
@pytest.mark.docx_real
def test_docx_corrompido_como_gerado_produz_ok_false_sem_traceback():
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gerado_corrompido = tmp / "corrompido.docx"
        gerado_corrompido.write_bytes(b"isto nao e um docx valido")

        r = vt.validar_template(gerado_corrompido, dados, decisoes_blocos,
                                 TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)

        assert r["ok"] is False
        assert any("PACOTE_DOCX_INVALIDO" in d and "auditado" in d for d in r["divergencias"])


# --------------------------------------------------------------- 2: estrutura mínima incompleta (gap A)
@pytest.mark.docx_real
def test_estrutura_minima_incompleta_como_gerado_produz_motivo_explicito():
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gerado_incompleto = tmp / "incompleto.docx"
        with zipfile.ZipFile(gerado_incompleto, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml",
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                        '<Default Extension="rels" ContentType='
                        '"application/vnd.openxmlformats-package.relationships+xml"/></Types>')
            zf.writestr("_rels/.rels",
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
            # word/document.xml deliberadamente ausente

        r = vt.validar_template(gerado_incompleto, dados, decisoes_blocos,
                                 TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)

        assert r["ok"] is False
        assert any("ESTRUTURA_DOCX_INCOMPLETA" in d and "auditado" in d and "document.xml" in d
                   for d in r["divergencias"])


# --------------------------------------------------------------- 6: alteração fora de zona ainda reprova
@pytest.mark.docx_real
def test_alteracao_texto_institucional_fixo_ainda_reprova():
    _pular_se_sem_template_real()
    dados, decisoes_blocos = _reconstruir_dados_e_decisoes()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gerado = _gerar_docx_real(tmp, dados, decisoes_blocos)

        unpacked = tmp / "unpacked_adulterado"
        extrair_pacote_docx(gerado, unpacked)
        doc_path = unpacked / "word" / "document.xml"
        texto = doc_path.read_text(encoding="utf-8")
        assert _ANCORA_INSTITUCIONAL_REAL in texto  # confirma a premissa antes de adulterar
        doc_path.write_text(texto.replace(_ANCORA_INSTITUCIONAL_REAL,
                                           "TEXTO ADULTERADO SEM AUTORIZACAO"), encoding="utf-8")
        gerado_adulterado = tmp / "gerado_adulterado.docx"
        empacotar_pacote_docx(unpacked, gerado_adulterado)

        r = vt.validar_template(gerado_adulterado, dados, decisoes_blocos,
                                 TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL)
        assert r["ok"] is False
        assert any("document.xml" in d and "difere" in d for d in r["divergencias"])


# --------------------------------------------------------------- 7: bug inesperado não mascarado
def test_bug_inesperado_na_composicao_nao_e_mascarado(monkeypatch):
    """Sintético e independente do Modelo Oficial: a função de composição
    é substituída por um mock ANTES de qualquer tentativa real de gerar a
    peça de referência — o template/schema/catálogo passados nunca chegam
    a ser lidos."""
    def _bug_simulado(*args, **kwargs):
        raise TypeError("bug de programacao simulado — nunca deve virar ok=False silencioso")

    monkeypatch.setattr(vt, "gerar_peca_com_blocos", _bug_simulado)

    with pytest.raises(TypeError, match="bug de programacao simulado"):
        vt.validar_template("qualquer.docx", {"FOO": "x"}, {}, "template.docx", "schema.json", "blocos.json")


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        if getattr(t, "pytestmark", None):
            continue  # docx_real — só via pytest
        import inspect
        if "monkeypatch" in inspect.signature(t).parameters:
            continue
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes executados (alguns exigem pytest, ver acima).")


if __name__ == "__main__":
    main()
