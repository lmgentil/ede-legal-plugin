#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_docx_context_engine.py — regressão da extração de contexto
institucional (Etapa 5.7-B, INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA —
SPEC-0001 §56).

Mesmo padrão de tests/test_docx_numeracao_engine.py: sem framework de
teste, asserts + `if __name__ == "__main__"`.

Dois níveis:
  1. Testes de unidade sobre XML sintético (lxml) — sempre rodam. Cobrem
     os casos A-D do pedido (ETAPA 5.7-B §12): antes/depois dentro do
     próprio parágrafo e por fallback ao parágrafo vizinho não-vazio,
     título de nível 1 (badge) e nível 2/3 (literal), placeholder dentro
     de SDT, placeholder duplicado dentro do mesmo bloco (E), e a garantia
     estrutural de não-escrita (G/N — o módulo nunca serializa XML).
  2. LOCAL_ONLY — contra o modelo-oficial.docx real (SKIP explícito se
     ausente, ADR-0006): E (VALOR_FRA duplicado dentro de RECONVENCAO), F
     (mc:Choice/Fallback do título não gera contexto falso), H (hash do
     arquivo mestre inalterado), O (os 13 placeholders batem exatamente
     com schema.json), R (E2E contra o template real).

Uso:
  python tests/test_docx_context_engine.py
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_context_engine import (  # noqa: E402
    ContextoAbortada,
    extrair_contexto,
    extrair_contexto_do_template,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


def _abortou(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except ContextoAbortada as e:
        return e


def _p(texto):
    return f'<w:p><w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _badge(texto):
    return ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="17"/></w:numPr></w:pPr>'
            f'<w:r><w:t>{texto}</w:t></w:r></w:p>')


def _sdt(tag_val, *paragrafos):
    return (f'<w:sdt><w:sdtPr><w:tag w:val="{tag_val}"/><w:id w:val="1"/></w:sdtPr>'
            f'<w:sdtContent>{"".join(paragrafos)}</w:sdtContent></w:sdt>')


def _doc(*paragrafos):
    return f'<w:document xmlns:w="{W}"><w:body>{"".join(paragrafos)}</w:body></w:document>'


CATALOGO_TESTE = {"blocks": [
    {"id": "BLOCO_X", "tag": "BLOCO:X"},
    {"id": "INLINE_X", "tag": "INLINE:X"},
]}

# --------------------------------------------------------------- documento sintético
# p0: badge nível 1 (título) | p1/p2: títulos literais 3.1/3.1.1
# p3: SINOPSE_FATOS isolada no próprio parágrafo (antes/depois vazios ->
#     fallback ao parágrafo vizinho) | p4: texto fixo depois
# duas cópias adjacentes de INLINE:X (simula mc:Choice/mc:Fallback), sem
#     placeholder algum dentro — não pode gerar contexto nem contaminar o
#     que vem depois
# BLOCO:X com dois placeholders VALOR_TESTE (duplicado no mesmo bloco,
#     caso E) + um AUTOR_TESTE fora de qualquer SDT (bloco=None)
DOC = _doc(
    _badge("MÉRITO"),
    _p("3.1 - LEGALIDADE DOS PROCEDIMENTOS"),
    _p("3.1.1 - SINOPSE DOS FATOS"),
    _p("{{SINOPSE_FATOS}}"),
    _p("Texto fixo depois da sinopse."),
    _sdt("INLINE:X", _p("CONTESTAÇÃO")),
    _sdt("INLINE:X", _p("CONTESTAÇÃO")),
    _p("{{AUTOR_TESTE}}, já qualificado nos autos."),
    _sdt("BLOCO:X",
         _p("O débito totaliza {{VALOR_TESTE}}, conforme fatura anexa."),
         _p("Total devido: {{VALOR_TESTE}}.")),
)


# --------------------------------------------------------------- A: texto anterior
def test_A_antes_dentro_do_proprio_paragrafo():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    ocorrencias = ctx["VALOR_TESTE"]
    assert ocorrencias[0]["antes"] == "O débito totaliza"


def test_A_antes_por_fallback_ao_paragrafo_anterior_quando_isolado():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["SINOPSE_FATOS"][0]["antes"] == "3.1.1 - SINOPSE DOS FATOS"


# --------------------------------------------------------------- B: texto posterior
def test_B_depois_dentro_do_proprio_paragrafo():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["VALOR_TESTE"][0]["depois"] == ", conforme fatura anexa."


def test_B_depois_por_fallback_ao_paragrafo_seguinte_quando_isolado():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["SINOPSE_FATOS"][0]["depois"] == "Texto fixo depois da sinopse."


# --------------------------------------------------------------- C: título relacionado
def test_C_titulo_nivel1_badge_reconhecido():
    doc_so_com_badge = _doc(
        _badge("MÉRITO"),
        _sdt("INLINE:X", _p("CONTESTAÇÃO")),
        _sdt("INLINE:X", _p("CONTESTAÇÃO")),
        _p("{{AUTOR_TESTE}}, já qualificado nos autos."),
    )
    ctx = extrair_contexto(doc_so_com_badge, CATALOGO_TESTE)
    # AUTOR_TESTE vem depois das cópias duplicadas de INLINE:X, sem nenhum
    # título literal entre o badge MÉRITO e ele — deve remontar até o badge.
    assert ctx["AUTOR_TESTE"][0]["titulo"] == "MÉRITO"


def test_C_titulo_remonta_ate_o_mais_proximo_entre_varios_precedentes():
    # nearest preceding heading — não o primeiro do documento, o mais
    # próximo fisicamente (achado do próprio teste E/F: DOC tem 3 títulos
    # antes de AUTOR_TESTE, o mais próximo é o literal de nível 3).
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["AUTOR_TESTE"][0]["titulo"] == "3.1.1 - SINOPSE DOS FATOS"


def test_C_titulo_literal_nivel_2_3_reconhecido():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["SINOPSE_FATOS"][0]["titulo"] == "3.1.1 - SINOPSE DOS FATOS"


def test_C_titulo_ausente_vira_none_nunca_string_vazia_ou_inventada():
    doc_sem_titulo = _doc(_p("{{ISOLADO}}"))
    ctx = extrair_contexto(doc_sem_titulo, CATALOGO_TESTE)
    assert ctx["ISOLADO"][0]["titulo"] is None


# --------------------------------------------------------------- D: placeholder dentro de SDT
def test_D_bloco_ancestral_identificado_pelo_catalogo():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["VALOR_TESTE"][0]["bloco"] == "BLOCO_X"


def test_D_placeholder_fora_de_sdt_tem_bloco_none():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx["SINOPSE_FATOS"][0]["bloco"] is None
    assert ctx["AUTOR_TESTE"][0]["bloco"] is None


# --------------------------------------------------------------- E: duplicado no mesmo bloco
def test_E_placeholder_duplicado_no_mesmo_bloco_gera_duas_ocorrencias_distintas():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    ocorrencias = ctx["VALOR_TESTE"]
    assert len(ocorrencias) == 2
    assert all(o["bloco"] == "BLOCO_X" for o in ocorrencias)
    assert ocorrencias[0]["antes"] != ocorrencias[1]["antes"]  # contextos realmente distintos


# --------------------------------------------------------------- F: mc:Choice/Fallback não contamina
def test_F_sdt_duplicada_sem_placeholder_nao_gera_contexto_falso():
    ctx = extrair_contexto(DOC, CATALOGO_TESTE)
    assert "INLINE_X" not in ctx  # nada de contexto para tag sem placeholder algum
    # placeholder físico DEPOIS das duas cópias adjacentes não herda bloco delas
    assert ctx["AUTOR_TESTE"][0]["bloco"] is None


# --------------------------------------------------------------- fail closed
def test_documento_sem_body_aborta():
    e = _abortou(extrair_contexto, f'<w:document xmlns:w="{W}"></w:document>', CATALOGO_TESTE)
    assert e is not None and e.stage == "template_invalido"


def test_template_ausente_aborta():
    e = _abortou(extrair_contexto_do_template, BASE / "nao-existe.docx", CATALOGO_REAL)
    assert e is not None and e.stage == "template_ausente"


def test_template_corrompido_aborta_fail_closed_nunca_crasha():
    """Achado real: .docx corrompido/inválido não gera ContextoAbortada
    automaticamente pela simples ausência de `unpacked.exists()` — o
    toolkit externo pode criar o diretório mesmo sem conseguir extrair
    word/document.xml. Sem a checagem específica, um FileNotFoundError
    não tratado escaparia (violação de fail-closed, item 6 da Etapa
    5.7-C)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        falso_docx = Path(tmp) / "modelo-oficial.docx"
        falso_docx.write_bytes(b"isto nao e um docx valido")
        e = _abortou(extrair_contexto_do_template, falso_docx, CATALOGO_REAL)
        assert e is not None and e.stage == "unpack_falhou"


# --------------------------------------------------------------- G/N: garantia estrutural de leitura
def test_G_N_modulo_nunca_serializa_ou_grava_xml():
    """Garantia estrutural (não só comportamental): o módulo não pode
    conter nenhuma chamada de serialização/gravação do XML — a prova de
    que "nunca escreve" é estar ausente do código, não só não ter sido
    exercitada por um teste de comportamento."""
    fonte = (BASE / "scripts" / "docx_context_engine.py").read_text(encoding="utf-8")
    # forma de CHAMADA (com parêntese) — não basta checar o nome, a própria
    # docstring do módulo MENCIONA "lxml.etree.tostring" em prosa, como
    # explicação do que ele NUNCA faz; sem o "(" o teste acusaria a própria
    # documentação como violação.
    proibidos = ["LET.tostring(", "etree.tostring(", ".write_text(", ".write_bytes(",
                 "pack_mod.pack(", "pack.pack("]
    achados = [p for p in proibidos if p in fonte]
    assert not achados, f"docx_context_engine.py contém operação de escrita proibida: {achados}"


def test_G_extracao_e_idempotente_e_nunca_muta_o_xml_de_entrada():
    xml_original = DOC
    ctx1 = extrair_contexto(DOC, CATALOGO_TESTE)
    assert DOC == xml_original  # string Python é imutável, mas confirma que ninguém reatribuiu/alterou o módulo
    ctx2 = extrair_contexto(DOC, CATALOGO_TESTE)
    assert ctx1 == ctx2


# --------------------------------------------------------------- LOCAL_ONLY (template real)
@pytest.mark.docx_real
def test_E_valor_fra_duplicado_dentro_de_reconvencao_no_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ADR-0006).")
        return
    ctx = extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    ocorrencias = ctx["VALOR_FRA"]
    assert len(ocorrencias) == 2
    assert all(o["bloco"] == "RECONVENCAO" for o in ocorrencias)


@pytest.mark.docx_real
def test_F_mc_choice_fallback_nao_gera_contexto_falso_no_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente.")
        return
    ctx = extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    # AUTOR vem logo depois da caixa de título duplicada (mc:Choice/
    # mc:Fallback, INLINE:COM_RECONVENCAO) — não pode herdar bloco dela
    # (a tag não está no catálogo de blocos "reais", só a de containers).
    assert ctx["AUTOR"][0]["bloco"] is None
    assert len(ctx["AUTOR"]) == 1  # não duplica por causa da caixa de título repetida


@pytest.mark.docx_real
def test_H_hash_do_template_mestre_inalterado_apos_extracao():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente.")
        return
    antes = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    depois = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    assert antes == depois


@pytest.mark.docx_real
def test_O_treze_placeholders_batem_exatamente_com_schema_no_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente.")
        return
    schema = json.loads(SCHEMA_REAL.read_text(encoding="utf-8"))
    catalogo = json.loads(CATALOGO_REAL.read_text(encoding="utf-8"))
    ctx = extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    # Etapa 5.8-B: o template passa a conter também os tokens das Zonas de
    # Complementação catalogadas. A asserção continua EXATA — nenhum token
    # no template pode existir fora dessas duas listas (INV-ZONA-
    # COMPLEMENTACAO: sem placeholder ou zona catalogada, sem escrita
    # gerativa) — e os 13 placeholders oficiais continuam sendo 13.
    zonas = {z["id"] for z in catalogo.get("zones", [])}
    assert set(ctx.keys()) == set(schema["editable_placeholders"]) | zonas
    assert len(schema["editable_placeholders"]) == 13
    assert not (zonas & set(schema["editable_placeholders"]))


@pytest.mark.docx_real
def test_R_e2e_contexto_institucional_completo_contra_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente.")
        return
    ctx = extrair_contexto_do_template(TEMPLATE_REAL, CATALOGO_REAL)
    # JUIZO é resolvido via DataJud (INV-JUIZO-DATAJUD) — nunca tem título/
    # bloco jurídico ao redor, é isolado no endereçamento.
    assert ctx["JUIZO"][0]["bloco"] is None
    # VALOR_DANO_MORAL_PRETENDIDO vive dentro de DESCABIMENTO_DANO_MORAL.
    assert ctx["VALOR_DANO_MORAL_PRETENDIDO"][0]["bloco"] == "DESCABIMENTO_DANO_MORAL"
    # IRREGULARIDADE_ENCONTRADA aparece 2x — uma fora de SDT, outra dentro
    # da Reconvenção (achado da Etapa 5.7-A) — mesma chave, contextos
    # distintos, nunca colapsados numa só ocorrência.
    ocorrencias_irregularidade = ctx["IRREGULARIDADE_ENCONTRADA"]
    assert len(ocorrencias_irregularidade) == 2
    assert {o["bloco"] for o in ocorrencias_irregularidade} == {None, "RECONVENCAO"}
    # SINOPSE_FATOS deve ter contexto textual não vazio ao redor (é isolada
    # no próprio parágrafo — precisa do fallback para não vir vazia).
    assert ctx["SINOPSE_FATOS"][0]["antes"] or ctx["SINOPSE_FATOS"][0]["depois"]


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
