#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_docx_numeracao_engine.py — regressão da renumeração automática/
dinâmica dos títulos e subtítulos da Contestação
(INV-NUMERACAO-DINAMICA-CONTESTACAO — CORREÇÃO de 2026-08-24).

Mesmo padrão de tests/test_docx_block_engine.py: sem framework de teste,
asserts + `if __name__ == "__main__"`.

Dois níveis:
  1. Testes de unidade sobre XML sintético (lxml) — sempre rodam, já
     pós-composição (sem <w:sdt> nenhum — compor_blocos() sempre remove a
     tag, incluído ou excluído; só o conteúdo literal sobrevive). Cobrem
     os casos A-L do pedido.
  2. LOCAL_ONLY — testes contra o modelo-oficial.docx real (SKIP explícito
     se ausente, ADR-0006): M (texto do título idêntico, só o número
     muda), N (OOXML/pPr preservados), O (Template Lock PASS), P (E2E
     completo via gerar_peca_com_blocos, DOCX final gerado e íntegro).

Uso:
  python tests/test_docx_numeracao_engine.py
"""
import sys
from pathlib import Path

import lxml.etree as LET
import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_numeracao_engine import (  # noqa: E402
    NumeracaoAbortada,
    renumerar_titulos,
    validar_numeracao_final,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except NumeracaoAbortada as e:
        return e


def _badge(texto):
    return ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="17"/></w:numPr></w:pPr>'
            f'<w:r><w:t>{texto}</w:t></w:r></w:p>')


def _titulo(texto, rpr="<w:b/>"):
    """Parágrafo com um título literal, preservando um <w:rPr> de exemplo
    (negrito) para os testes de preservação de formatação (caso N)."""
    return f'<w:p><w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _doc(*paragrafos):
    return f'<w:document xmlns:w="{W}"><w:body>{"".join(paragrafos)}</w:body></w:document>'


DOC_COMPLETO = _doc(
    _badge("TEMPESTIVIDADE"),
    _badge("PRELIMINARES"),
    _titulo("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR"),
    _titulo("2.2 - REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA"),
    _badge("MÉRITO"),
    _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
    _titulo("3.1.1 - SINOPSE DOS FATOS"),
    _titulo("3.1.2 - REALIDADE FÁTICA"),
    _titulo("3.2 - DEVER LEGAL DE FISCALIZAÇÃO"),
    _titulo("3.3 - DESNECESSIDADE DE AVISO PRÉVIO"),
    _titulo("3.4 - CÁLCULOS DE RECUPERAÇÃO DE CONSUMO"),
    _badge("LICITUDE DA COBRANÇA E CORTE"),
    _titulo("4.1 - TEMA REPETITIVO 699"),
    _badge("NEXO CAUSAL INDEMONSTRADO"),
    _badge("DESCABIMENTO DE DANO MORAL"),
    _badge("ÔNUS PROBATÓRIO"),
    _badge("RECONVENÇÃO (ART. 343, CPC)"),
    _titulo("8.1 - COBRANÇA DE DÉBITOS DERIVADOS DA IRREGULARIDADE"),
    _badge("REQUERIMENTOS"),
)


# --------------------------------------------------------------- A: tudo incluído
def test_A_todos_os_blocos_incluidos_sequencia_crescente_correta():
    _novo, rel = renumerar_titulos(DOC_COMPLETO)
    esperado = {
        "TEMPESTIVIDADE": "1", "PRELIMINARES": "2", "MERITO": "3",
        "LICITUDE_CORTE_SUSPENSAO": "4", "NEXO_CAUSAL_INDEMONSTRADO": "5",
        "DESCABIMENTO_DANO_MORAL": "6", "ONUS_PROBATORIO": "7",
        "RECONVENCAO": "8", "REQUERIMENTOS": "9",
        "PRELIMINAR_CDC_INAPLICAVEL": "2.1", "PRELIMINAR_REVOGACAO_GRATUIDADE": "2.2",
        "LEGALIDADE_PROCEDIMENTOS": "3.1", "SINOPSE_FATOS": "3.1.1", "REALIDADE_FATICA": "3.1.2",
        "DEVER_LEGAL_FISCALIZACAO": "3.2", "DESNECESSIDADE_AVISO_PREVIO": "3.3",
        "CALCULOS_RECUPERACAO_CONSUMO": "3.4", "TEMA_REPETITIVO_699": "4.1",
        "COBRANCA_DEBITOS_RECONVINDA": "8.1",
    }
    assert rel["numeracao"] == esperado
    assert validar_numeracao_final(_novo) == []


# --------------------------------------------------------------- B/I: nível 1 ausente
def test_B_I_exclusao_de_topico_nivel_1_desloca_seguintes_e_merito_assume_numero_seguinte():
    doc = _doc(
        _badge("TEMPESTIVIDADE"),
        # PRELIMINARES (container inteiro) ausente — nenhum filho seu aparece
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"),
        _titulo("3.1.2 - REALIDADE FÁTICA"),
        _badge("RECONVENÇÃO (ART. 343, CPC)"),
        _titulo("8.1 - COBRANÇA DE DÉBITOS DERIVADOS DA IRREGULARIDADE"),
    )
    novo, rel = renumerar_titulos(doc)
    assert "PRELIMINARES" not in rel["numeracao"]
    assert rel["numeracao"]["MERITO"] == "2"  # imediatamente seguinte a TEMPESTIVIDADE
    assert rel["numeracao"]["LEGALIDADE_PROCEDIMENTOS"] == "2.1"
    assert rel["numeracao"]["SINOPSE_FATOS"] == "2.1.1"
    assert rel["numeracao"]["REALIDADE_FATICA"] == "2.1.2"
    assert rel["numeracao"]["RECONVENCAO"] == "3"
    assert rel["numeracao"]["COBRANCA_DEBITOS_RECONVINDA"] == "3.1"
    assert validar_numeracao_final(novo) == []


# --------------------------------------------------------------- C: filho intermediário
def test_C_exclusao_de_filho_intermediario_renumera_irmaos_seguintes_sem_lacuna():
    doc = _doc(
        _badge("TEMPESTIVIDADE"),
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"),
        _titulo("3.1.2 - REALIDADE FÁTICA"),
        # 3.2 DEVER_LEGAL_FISCALIZACAO ausente (excluído)
        _titulo("3.3 - DESNECESSIDADE DE AVISO PRÉVIO"),
        _titulo("3.4 - CÁLCULOS DE RECUPERAÇÃO DE CONSUMO"),
    )
    _novo, rel = renumerar_titulos(doc)
    assert "DEVER_LEGAL_FISCALIZACAO" not in rel["numeracao"]
    assert rel["numeracao"]["DESNECESSIDADE_AVISO_PREVIO"] == "2.2"  # não "2.3" — sem lacuna
    assert rel["numeracao"]["CALCULOS_RECUPERACAO_CONSUMO"] == "2.3"


# --------------------------------------------------------------- D: vários filhos excluídos
def test_D_exclusao_de_varios_filhos_sequencia_continua():
    doc = _doc(
        _badge("TEMPESTIVIDADE"),
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"),
        _titulo("3.1.2 - REALIDADE FÁTICA"),
        # 3.2 e 3.3 ausentes (ambos excluídos) — só 3.4 sobrevive
        _titulo("3.4 - CÁLCULOS DE RECUPERAÇÃO DE CONSUMO"),
    )
    _novo, rel = renumerar_titulos(doc)
    assert rel["numeracao"]["CALCULOS_RECUPERACAO_CONSUMO"] == "2.2"  # não "2.4"


# --------------------------------------------------------------- E: container excluído, descendentes não interferem
def test_E_container_excluido_descendentes_nao_interferem_na_numeracao():
    doc = _doc(
        _badge("TEMPESTIVIDADE"),
        # PRELIMINARES e AMBOS os filhos ausentes (container EXCLUIR)
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"),
        _titulo("3.1.2 - REALIDADE FÁTICA"),
    )
    _novo, rel = renumerar_titulos(doc)
    assert "PRELIMINAR_CDC_INAPLICAVEL" not in rel["numeracao"]
    assert "PRELIMINAR_REVOGACAO_GRATUIDADE" not in rel["numeracao"]
    assert rel["numeracao"]["MERITO"] == "2"


# --------------------------------------------------------------- F: container incluído, posição correta
def test_F_container_incluido_recebe_posicao_correta():
    _novo, rel = renumerar_titulos(DOC_COMPLETO)
    assert rel["numeracao"]["PRELIMINARES"] == "2"
    assert rel["numeracao"]["PRELIMINAR_CDC_INAPLICAVEL"] == "2.1"


# --------------------------------------------------------------- G: Reconvenção
def test_G_reconvencao_incluir_excluir_numeracao_continua():
    _novo_incluir, rel_incluir = renumerar_titulos(DOC_COMPLETO)
    assert rel_incluir["numeracao"]["RECONVENCAO"] == "8"
    assert rel_incluir["numeracao"]["REQUERIMENTOS"] == "9"

    doc_sem_reconvencao = _doc(
        _badge("TEMPESTIVIDADE"), _badge("PRELIMINARES"),
        _titulo("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR"),
        _titulo("2.2 - REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA"),
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA"),
        _badge("ÔNUS PROBATÓRIO"),
        # RECONVENÇÃO ausente
        _badge("REQUERIMENTOS"),
    )
    _novo, rel = renumerar_titulos(doc_sem_reconvencao)
    assert "RECONVENCAO" not in rel["numeracao"]
    assert rel["numeracao"]["REQUERIMENTOS"] == "5"  # imediatamente seguinte a ÔNUS PROBATÓRIO


# --------------------------------------------------------------- H: Licitude/corte
def test_H_bloco_de_corte_incluir_excluir_numeracao_continua():
    _novo_incluir, rel_incluir = renumerar_titulos(DOC_COMPLETO)
    assert rel_incluir["numeracao"]["LICITUDE_CORTE_SUSPENSAO"] == "4"
    assert rel_incluir["numeracao"]["TEMA_REPETITIVO_699"] == "4.1"

    doc_sem_licitude = _doc(
        _badge("TEMPESTIVIDADE"), _badge("PRELIMINARES"),
        _titulo("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR"),
        _titulo("2.2 - REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA"),
        _badge("MÉRITO"),
        _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
        _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA"),
        # LICITUDE DA COBRANÇA E CORTE ausente
        _badge("NEXO CAUSAL INDEMONSTRADO"),
    )
    _novo, rel = renumerar_titulos(doc_sem_licitude)
    assert "LICITUDE_CORTE_SUSPENSAO" not in rel["numeracao"]
    assert "TEMA_REPETITIVO_699" not in rel["numeracao"]
    assert rel["numeracao"]["NEXO_CAUSAL_INDEMONSTRADO"] == "4"


# --------------------------------------------------------------- J/K: combinações, sem duplicata/salto
def test_J_K_combinacoes_variadas_sem_duplicata_e_sem_salto():
    combinacoes = [
        DOC_COMPLETO,
        _doc(_badge("TEMPESTIVIDADE"), _badge("MÉRITO"),
             _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
             _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA")),
        _doc(_badge("TEMPESTIVIDADE"), _badge("PRELIMINARES"),
             _titulo("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR"),
             _badge("MÉRITO"),
             _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
             _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA"),
             _badge("REQUERIMENTOS")),
    ]
    for doc in combinacoes:
        novo, rel = renumerar_titulos(doc)
        numeros = list(rel["numeracao"].values())
        assert len(numeros) == len(set(numeros)), f"número duplicado em {rel['numeracao']}"
        assert validar_numeracao_final(novo) == []


# --------------------------------------------------------------- L: hierarquia pai/filho
def test_L_hierarquia_pai_filho_correta():
    _novo, rel = renumerar_titulos(DOC_COMPLETO)
    n = rel["numeracao"]
    assert n["SINOPSE_FATOS"].startswith(n["LEGALIDADE_PROCEDIMENTOS"] + ".")
    assert n["REALIDADE_FATICA"].startswith(n["LEGALIDADE_PROCEDIMENTOS"] + ".")
    assert n["PRELIMINAR_CDC_INAPLICAVEL"].startswith(n["PRELIMINARES"] + ".")
    assert n["TEMA_REPETITIVO_699"].startswith(n["LICITUDE_CORTE_SUSPENSAO"] + ".")
    assert n["COBRANCA_DEBITOS_RECONVINDA"].startswith(n["RECONVENCAO"] + ".")


# --------------------------------------------------------------- M: só o número muda
def test_M_texto_do_titulo_preservado_so_o_numero_muda():
    doc = _doc(
        _badge("TEMPESTIVIDADE"), _badge("MÉRITO"),
        _titulo("3.1 – LEGALIDADE DOS PROCEDIMENTOS ADOTADOS – ALGO:"),
        _titulo("3.1.1 – SINOPSE DOS FATOS:"),
        _titulo("3.1.2 – REALIDADE FÁTICA:"),
    )
    novo, _rel = renumerar_titulos(doc)
    assert "2.1 – LEGALIDADE DOS PROCEDIMENTOS ADOTADOS – ALGO:" in novo
    assert "2.1.1 – SINOPSE DOS FATOS:" in novo
    assert "2.1.2 – REALIDADE FÁTICA:" in novo
    assert "3.1 – LEGALIDADE" not in novo  # número antigo não sobrevive


# --------------------------------------------------------------- N: formatação OOXML preservada
def test_N_formatacao_ooxml_preservada_exceto_o_numero():
    doc = _doc(_badge("TEMPESTIVIDADE"), _badge("MÉRITO"),
               _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS", rpr="<w:b/><w:color w:val=\"FF0000\"/>"),
               _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA"))
    novo, _rel = renumerar_titulos(doc)
    assert '<w:b/><w:color w:val="FF0000"/>' in novo  # rPr intocado
    assert novo.count("<w:p>") == doc.count("<w:p>")  # nenhum parágrafo criado/removido


# --------------------------------------------------------------- negativos (fail closed)
def test_titulo_fixo_ausente_aborta():
    doc = _doc(_badge("TEMPESTIVIDADE"), _badge("MÉRITO"))  # sem 3.1/3.1.1/3.1.2
    e = _abortou(renumerar_titulos, doc)
    assert e is not None and e.stage == "numeracao_titulo_fixo_ausente"


def test_badge_desconhecido_aborta():
    doc = _doc(_badge("TEMPESTIVIDADE"), _badge("SEÇÃO INVENTADA"))
    e = _abortou(renumerar_titulos, doc)
    assert e is not None and e.stage == "numeracao_badge_desconhecido"


def test_validador_detecta_numero_adulterado_apos_renumeracao():
    novo, _rel = renumerar_titulos(DOC_COMPLETO)
    adulterado = novo.replace(">2.1<", ">9.9<", 1) if ">2.1<" in novo else novo.replace("2.1 -", "9.9 -", 1)
    erros = validar_numeracao_final(adulterado)
    assert erros, "validador deveria detectar número adulterado após a renumeração"


# --------------------------------------------------------------- LOCAL_ONLY (template real): M, N, O, P
@pytest.mark.docx_real
def test_O_P_pipeline_completo_gera_docx_com_numeracao_e_template_lock_ok():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ADR-0006).")
        return

    import tempfile

    from docx_block_engine import carregar_catalogo, gerar_peca_com_blocos, validar_catalogo

    catalogo = carregar_catalogo(CATALOGO_REAL)
    validar_catalogo(catalogo)

    dados = {
        "JUIZO": "1ª Vara Cível da Comarca de Salvador/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "ligação direta (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
    }
    # cenário deliberadamente PARCIAL — exclui PRELIMINAR_CDC_INAPLICAVEL
    # (nível 2) e mantém PRELIMINARES via GRATUIDADE (state_linked), para
    # exercitar o mesmo salto que motivou a correção (§ causa raiz).
    decisoes = {b["id"]: {"decisao": "INCLUIR"}
                for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    decisoes["PRELIMINAR_CDC_INAPLICAVEL"] = {"decisao": "EXCLUIR"}
    decisoes.pop("LICITUDE_CORTE_SUSPENSAO", None)  # sem decisão + CORTE_EFETIVO=False -> EXCLUIR automático
    fatos = {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": False}

    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao-numeracao-teste.docx"
        r = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes, saida, fatos_processuais=fatos)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"  # caso O
        assert saida.exists() and saida.stat().st_size > 0  # caso P

        numeracao = r["numeracao"]
        # PRELIMINAR_CDC_INAPLICAVEL excluído -> GRATUIDADE assume "2.1", não "2.2"
        assert numeracao["PRELIMINAR_REVOGACAO_GRATUIDADE"] == "2.1"
        assert "PRELIMINAR_CDC_INAPLICAVEL" not in numeracao
        # LICITUDE_CORTE_SUSPENSAO excluído -> NEXO_CAUSAL assume o número dele
        assert "LICITUDE_CORTE_SUSPENSAO" not in numeracao
        assert numeracao["MERITO"] == "3"
        assert numeracao["NEXO_CAUSAL_INDEMONSTRADO"] == "4"

        # caso M/N: reabrir o DOCX final e confirmar que o título de nível
        # 2 aparece com o número recalculado, texto e negrito intactos.
        unpack_mod, _pack_mod = __import__("docx_template_engine")._importar_toolkit()
        unpacked = Path(tmp) / "gerado_unpacked"
        unpack_mod.unpack(str(saida), str(unpacked))
        doc_xml = (unpacked / "word" / "document.xml").read_text(encoding="utf-8")
        assert "2.1 – REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA" in doc_xml
        assert "2.2 – REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA" not in doc_xml
        assert "3.1 – LEGALIDADE DOS PROCEDIMENTOS" in doc_xml  # MÉRITO continua "3" (nada acima dele mudou)


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
