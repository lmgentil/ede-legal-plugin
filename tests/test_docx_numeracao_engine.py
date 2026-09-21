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
    _badges_nivel1_presentes,
    _texto_paragrafo,
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
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")

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
        # Etapa 5.8-G: exigido por PRELIMINAR_INEPCIA_INICIAL, que entra em
        # `decisoes` abaixo (decision_mode="estrategista", INCLUIR).
        "SINOPSE_FATOS_NUCLEO_OBJETO": "Objeto fictício de teste (dado fictício de teste).",
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
        from docx_package import extrair_pacote_docx
        unpacked = Path(tmp) / "gerado_unpacked"
        extrair_pacote_docx(saida, unpacked)
        doc_xml = (unpacked / "word" / "document.xml").read_text(encoding="utf-8")
        # Pontuação real do template (auditada diretamente no XML gerado em
        # 09/09/2026): "N.N. TÍTULO" com PONTO, não travessão, logo após o
        # número — o travessão do texto original só aparece mais adiante,
        # dentro do próprio título ("...GRATUITA – AUSÊNCIA DOS
        # REQUISITOS..."). As asserções anteriores usavam "–" logo após o
        # número, que nunca existiu neste título — desatualizadas desde
        # antes da Etapa 5.8-G, só nunca exercitadas neste cenário exato.
        assert "2.1. REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA" in doc_xml
        assert "2.2. REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA" not in doc_xml
        assert "3.1. LEGALIDADE DOS PROCEDIMENTOS" in doc_xml  # MÉRITO continua "3" (nada acima dele mudou)


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()


# =====================================================================
# Gate 6.6-A — mc:Fallback (VML legado) nunca é conteúdo visível
# =====================================================================
#
# Achado (auditoria obrigatória do gate, medido no Modelo Oficial real):
# `_texto_paragrafo` somava o texto dos ramos `mc:Choice` (moderno, o que o
# Word exibe) e `mc:Fallback` (VML legado, oculto) — 24 dos 342 parágrafos
# saíam com texto duplicado ("PRELIMINARESPRELIMINARES"). A numeração só
# funcionava por um workaround que colapsava badges duplicados ADJACENTES.
# Mesma classe de defeito já corrigida em docx_context_engine (Gate 6.5-B3).

MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _alternate(interno_choice, interno_fallback):
    """Parágrafo externo com a mesma forma desenhada em mc:Choice + mc:Fallback."""
    return (f'<w:p><w:r><mc:AlternateContent xmlns:mc="{MC}">'
            f'<mc:Choice Requires="wps">{interno_choice}</mc:Choice>'
            f'<mc:Fallback>{interno_fallback}</mc:Fallback>'
            '</mc:AlternateContent></w:r></w:p>')


def _doc_mc(*paragrafos):
    return (f'<w:document xmlns:w="{W}" xmlns:mc="{MC}"><w:body>'
            f'{"".join(paragrafos)}</w:body></w:document>')


def test_texto_do_paragrafo_ignora_o_ramo_fallback():
    doc = _doc_mc(_alternate(_badge("PRELIMINARES"), _badge("PRELIMINARES")))
    externo = LET.fromstring(doc.encode("utf-8")).find(".//w:body/w:p", NS)
    assert _texto_paragrafo(externo) == "PRELIMINARES"  # nunca "PRELIMINARESPRELIMINARES"


def test_badges_com_choice_e_fallback_nao_adjacentes_sao_contados_uma_vez():
    """O ramo Fallback é ignorado pela causa: não depende mais de a cópia
    legada estar fisicamente ao lado da moderna."""
    titulos = ["TEMPESTIVIDADE", "PRELIMINARES", "MÉRITO"]
    choices = [_alternate(_badge(t), "") for t in titulos]
    fallbacks = [_alternate("", _badge(t)) for t in titulos]  # todos os Fallback depois dos Choice
    root = LET.fromstring(_doc_mc(*choices, *fallbacks).encode("utf-8"))
    achados = _badges_nivel1_presentes(root)
    assert len(achados) == 3 and len({a[0] for a in achados}) == 3


def test_badge_visivel_duplicado_continua_abortando():
    """Sem o colapso por adjacência, uma duplicata VISÍVEL real é erro."""
    doc = _doc(_badge("TEMPESTIVIDADE"), _badge("TEMPESTIVIDADE"), _badge("PRELIMINARES"))
    e = _abortou(renumerar_titulos, doc)
    assert e is not None and e.stage == "numeracao_ordem_badges_invalida"


def test_renumeracao_com_estrutura_choice_fallback_igual_a_sem_ela():
    base = [_badge("TEMPESTIVIDADE"), _badge("PRELIMINARES"),
            _titulo("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR"),
            _badge("MÉRITO"), _titulo("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
            _titulo("3.1.1 - SINOPSE DOS FATOS"), _titulo("3.1.2 - REALIDADE FÁTICA")]
    com_mc = [_alternate(x, x) if x.startswith("<w:p><w:pPr>") else x for x in base]

    def numeros(xml):
        return [t.text for t in LET.fromstring(xml.encode("utf-8")).iter(f"{{{W}}}t")
                if t.text and t.text[:1].isdigit()]

    simples, _ = renumerar_titulos(_doc(*base))
    duplo, _ = renumerar_titulos(_doc_mc(*com_mc))
    assert numeros(simples) == numeros(duplo) and numeros(simples)


def test_residual_numerado_so_no_fallback_e_ignorado_mas_o_visivel_e_apontado():
    base, _ = renumerar_titulos(DOC_COMPLETO)  # documento completo e válido
    oculto = _alternate("<w:p><w:r><w:t>texto</w:t></w:r></w:p>",
                        "<w:p><w:r><w:t>9.9 residual oculto</w:t></w:r></w:p>")
    assert validar_numeracao_final(base) == []
    com_oculto = base.replace("</w:body>", oculto + "</w:body>")
    assert validar_numeracao_final(com_oculto) == []  # número só no ramo Fallback: nunca exibido
    com_visivel = base.replace("</w:body>", _titulo("9.9 residual visível") + "</w:body>")
    assert any("residual" in e for e in validar_numeracao_final(com_visivel))


# ---------------------------------------------------- docx_real (modelo real)
def _xml_do_modelo_real():
    import tempfile

    from docx_package import extrair_pacote_docx
    with tempfile.TemporaryDirectory() as tmp:
        extrair_pacote_docx(TEMPLATE_REAL, Path(tmp) / "u")
        return (Path(tmp) / "u" / "word" / "document.xml").read_text(encoding="utf-8")


def _em_fallback(el):
    return any(a.tag == f"{{{MC}}}Fallback" for a in el.iterancestors())


@pytest.mark.docx_real
def test_real_nenhum_paragrafo_tem_texto_duplicado_pelo_ramo_fallback():
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — asset institucional externo (ADR-0009).")
    root = LET.fromstring(_xml_do_modelo_real().encode("utf-8"))
    diverge_do_bruto = 0
    for p in root.iter(f"{{{W}}}p"):
        visivel = "".join(t.text or "" for t in p.iter(f"{{{W}}}t") if not _em_fallback(t))
        bruto = "".join(t.text or "" for t in p.iter(f"{{{W}}}t"))
        assert _texto_paragrafo(p) == visivel
        diverge_do_bruto += bruto != visivel
    # o modelo real AINDA tem Fallback (senão o teste seria vácuo)
    assert diverge_do_bruto > 0
    titulos_de_badge = ("TEMPESTIVIDADE", "PRELIMINARES", "MÉRITO", "REQUERIMENTOS", "RECONVENÇÃO")
    for p in root.iter(f"{{{W}}}p"):  # por parágrafo (o aninhado já é contado no externo)
        texto = _texto_paragrafo(p)
        assert not any(t + t in texto for t in titulos_de_badge), texto[:80]


@pytest.mark.docx_real
def test_real_nove_badges_de_nivel_1_unicos_e_todos_visiveis():
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — asset institucional externo (ADR-0009).")
    root = LET.fromstring(_xml_do_modelo_real().encode("utf-8"))
    achados = _badges_nivel1_presentes(root)
    assert len(achados) == 9 and len({a[0] for a in achados}) == 9
    assert not any(_em_fallback(p) for _bid, p in achados)


@pytest.mark.docx_real
def test_real_numeracao_do_documento_completo_igual_a_do_documento_sem_o_ramo_fallback():
    """Propriedade metamórfica: como o Fallback não é conteúdo visível, remover
    fisicamente os ramos mc:Fallback do XML não pode mudar NENHUM número
    escrito — vale para o modelo cru e para composições de blocos."""
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — asset institucional externo (ADR-0009).")
    import random

    import docx_block_engine as be

    catalogo = be.carregar_catalogo(CATALOGO_REAL)
    be.validar_catalogo(catalogo)
    xml_cru = _xml_do_modelo_real()

    def sem_fallback(xml):
        root = LET.fromstring(xml.encode("utf-8"))
        for f in list(root.iter(f"{{{MC}}}Fallback")):
            f.getparent().remove(f)
        return LET.tostring(root, encoding="unicode")

    def numeros(xml):
        return [t.text for t in LET.fromstring(xml.encode("utf-8")).iter(f"{{{W}}}t")
                if t.text and t.text[:1].isdigit() and not _em_fallback(t)]

    cenarios = [xml_cru]
    for seed in range(6):
        rnd = random.Random(seed)
        fatos = {b["linked_fact"]: rnd.random() < .5 for b in catalogo["blocks"] if b["decision_mode"] == "state_linked"}
        fatos["CORTE_EFETIVO"] = rnd.random() < .5
        dec = {}
        for b in catalogo["blocks"]:
            if b["decision_mode"] in ("estrategista", "humano"):
                if b["id"] == "LICITUDE_CORTE_SUSPENSAO" and not fatos["CORTE_EFETIVO"]:
                    continue
                dec[b["id"]] = {"decisao": "INCLUIR" if rnd.random() < .55 else "EXCLUIR"}
        estados = be.validar_e_resolver_decisoes(catalogo, dec, fatos)
        cenarios.append(be.compor_xml(xml_cru, catalogo, estados)[0])
    for xml in cenarios:
        completo, _ = renumerar_titulos(xml)
        reduzido, _ = renumerar_titulos(sem_fallback(xml))
        assert numeros(completo) == numeros(reduzido)
        assert validar_numeracao_final(completo) == []
