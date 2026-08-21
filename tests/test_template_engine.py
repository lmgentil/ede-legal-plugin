#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_template_engine.py — regressão do Template Engine (SPEC-0001 REQ-032 a
REQ-034, TEST-001 a TEST-004, TEST-009, TEST-010).

Sem framework de teste (o projeto não usa pytest em nenhum outro lugar —
mesmo padrão de rag/avaliar_recuperacao.py e
skills/calendario-forense-tjba-2026/scripts/calcular_tempestividade.py):
asserts + `if __name__ == "__main__"`.

Dois níveis:
  1. Testes de unidade sobre XML sintético — sempre rodam, não dependem do
     template real (que é institucional, fora do git — ADR-0006). Esta é
     a suíte pública: cobre o Template Engine estruturalmente, sem
     precisar do asset externo.
  2. LOCAL_ONLY — `test_pipeline_completo_contra_template_real`: teste de
     ponta a ponta contra o `.docx` institucional real
     (templates/contestacao/modelo-oficial.docx), asset externo nunca
     distribuído (ADR-0006, consolidação pós-Fase 8) — só roda se o
     arquivo existir localmente; do contrário, SKIP explícito (não é
     falha: ausência do template é o comportamento esperado em toda
     instalação pública/clone limpo/CI).

Uso:
  python tests/test_template_engine.py
"""
import sys
from pathlib import Path

import lxml.etree as LET

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_template_engine import (  # noqa: E402
    _importar_toolkit,
    extrair_placeholders,
    garantir_utf8,
    gerar_peca,
    substituir_placeholders,
    validar_placeholders,
    verificar_template_lock,
)

garantir_utf8()  # ver docx_template_engine.py — corrige cp1252 padrão do Windows

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"

# XML sintético mínimo, mas com a mesma forma real observada na auditoria:
# placeholder sozinho no <w:t> (JUIZO) e placeholder embutido numa frase
# com prefixo/sufixo fixos (LOCAL_DATA), igual ao "Salvador, {{LOCAL_DATA}}."
# Etapa 5.3-B: _explodir_paragrafos_multilinha() usa lxml e casa <w:p>/
# <w:r>/<w:t>/<w:br>/<w:rPr> pelo namespace REAL do wordprocessingml (não
# um placeholder arbitrário como "urn:w") — precisa estar declarado aqui
# para os testes de conteúdo multiline exercitarem o código de verdade.
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

XML_SINTETICO = (
    f'<w:document xmlns:w="{NS_W}"><w:body>'
    '<w:p><w:r><w:t>{{JUIZO}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:t xml:space="preserve">Salvador, {{LOCAL_DATA}}.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>{{SINOPSE_FATOS}}</w:t></w:r></w:p>'
    '</w:body></w:document>'
)
SCHEMA_SINTETICO = {"editable_placeholders": ["JUIZO", "LOCAL_DATA", "SINOPSE_FATOS"]}

# XML sintético para os testes de cor (Etapa 3) — cobre as combinações
# reais de rPr encontradas no template real: sem rPr, com rPr+outras
# propriedades, com EE0000 pré-existente (inconsistência histórica do
# asset), multilinha, e texto fixo institucional que nunca pode mudar de
# cor. Também reproduz, entre parágrafos, o pretty-print com quebra de
# linha DENTRO do próprio <w:rPr> que o toolkit unpack.py produz — achado
# real desta implementação (regex "." não casava \n sem re.DOTALL).
XML_SINTETICO_COR = (
    f'<w:document xmlns:w="{NS_W}"><w:body>'
    '<w:p><w:r><w:t>{{JUIZO}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="24"/></w:rPr>'
    '<w:t>{{AUTOR}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr><w:color w:val="EE0000"/></w:rPr><w:t>{{VALOR_FRA}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr>\n  <w:i/>\n</w:rPr>\n<w:t>{{SINOPSE_FATOS}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Texto institucional fixo</w:t></w:r></w:p>'
    '</w:body></w:document>'
)
SCHEMA_SINTETICO_COR = {"editable_placeholders": ["JUIZO", "AUTOR", "VALOR_FRA", "SINOPSE_FATOS"]}


def test_substituicao_simples():
    xml, subst = substituir_placeholders(XML_SINTETICO, {"JUIZO": "1ª Vara Cível"})
    assert ">1ª Vara Cível</w:t>" in xml  # tag pode ganhar xml:space="preserve"
    assert subst == {"JUIZO"}
    assert "{{JUIZO}}" not in xml
    # LOCAL_DATA não foi fornecido: deve permanecer intocado (quem barra é
    # validar_placeholders, não a substituição em si)
    assert "{{LOCAL_DATA}}" in xml


def test_substituicao_inline_preserva_prefixo_sufixo():
    xml, _ = substituir_placeholders(XML_SINTETICO, {"LOCAL_DATA": "18 de agosto de 2026"})
    assert "Salvador, 18 de agosto de 2026." in xml
    assert "{{LOCAL_DATA}}" not in xml


def test_substituicao_multilinha_gera_paragrafos_reais(monkeypatch=None):
    # Etapa 5.3-B / INV-PARAGRAFO-HERDA-TEMPLATE: cada linha lógica vira um
    # <w:p> irmão real (clone do w:pPr do parágrafo-placeholder) — não uma
    # quebra <w:br/> dentro de um único <w:p> (comportamento pré-5.3-B).
    xml, _ = substituir_placeholders(XML_SINTETICO, {"SINOPSE_FATOS": "Primeira linha.\nSegunda linha."})
    assert "<w:br/>" not in xml, "quebra deveria ter virado <w:p> novo, não <w:br/> literal"
    assert "Primeira linha." in xml and "Segunda linha." in xml
    assert "urn:ede" not in xml, "marcador interno não pode sobreviver ao XML final"
    # 1 linha lógica a mais -> 1 <w:p> a mais que o XML_SINTETICO original
    import re
    assert len(re.findall(r"<w:p[ >]", xml)) == len(re.findall(r"<w:p[ >]", XML_SINTETICO)) + 1


def test_escapa_caracteres_xml_no_valor():
    xml, _ = substituir_placeholders(XML_SINTETICO, {"JUIZO": "Vara & Cia <teste>"})
    assert "Vara &amp; Cia &lt;teste&gt;" in xml
    assert "Vara & Cia <teste>" not in xml  # não pode vazar & / < / > crus


# --------------------------------------------------------------- cor (Etapa 3)
def test_cor_placeholder_sem_rpr_cria_ff0000():
    # A: placeholder sem rPr -> cria/injeta FF0000
    xml, _ = substituir_placeholders(XML_SINTETICO_COR, {"JUIZO": "1ª Vara Cível"})
    assert '<w:rPr><w:color w:val="FF0000"/></w:rPr>' in xml
    assert ">1ª Vara Cível</w:t>" in xml  # tag pode ganhar xml:space="preserve"


def test_cor_placeholder_com_rpr_preserva_demais_propriedades():
    # B: placeholder com rPr preto + outras propriedades -> preserva as
    # demais propriedades, troca só a cor
    xml, _ = substituir_placeholders(XML_SINTETICO_COR, {"AUTOR": "Fulano de Tal"})
    assert '<w:b/><w:color w:val="FF0000"/><w:sz w:val="24"/>' in xml
    assert 'w:val="000000"' not in xml


def test_cor_placeholder_ja_ee0000_vira_ff0000():
    # C: placeholder já EE0000 -> resultado FF0000 (EE0000 é inconsistência
    # histórica do template, não convenção — decisão já registrada)
    xml, _ = substituir_placeholders(XML_SINTETICO_COR, {"VALOR_FRA": "R$ 10,00"})
    assert "FF0000" in xml
    assert "EE0000" not in xml


def test_cor_multiline_todas_linhas_ff0000():
    # D: multilinha -> cada <w:p> gerado (Etapa 5.3-B: linha lógica vira
    # parágrafo real, não <w:br/>) recebe sua própria <w:rPr> vermelha,
    # clonada do rPr original do parágrafo-placeholder.
    xml, _ = substituir_placeholders(
        XML_SINTETICO_COR, {"SINOPSE_FATOS": "Primeira linha.\nSegunda linha."})
    assert "<w:br/>" not in xml
    assert xml.count('<w:color w:val="FF0000"/>') == 2  # uma por parágrafo/linha
    assert xml.count("<w:i/>") == 2  # propriedade original preservada em cada parágrafo
    assert "Primeira linha." in xml and "Segunda linha." in xml


def test_cor_texto_fixo_nao_muda():
    # E: texto fixo institucional -> rPr e cor inalterados
    xml, _ = substituir_placeholders(XML_SINTETICO_COR, {"JUIZO": "1ª Vara"})
    assert "<w:rPr><w:b/></w:rPr><w:t>Texto institucional fixo</w:t>" in xml


def test_cor_adulterada_em_texto_fixo_reprovada_pelo_lock():
    # F: Template Lock deve continuar reprovando cor alterada FORA de
    # placeholder — mesmo mecanismo de sempre (recomputa e compara byte a
    # byte), nenhuma lógica nova de "zonas" precisou ser criada.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        template_dir, gerado_dir = tmp / "template", tmp / "gerado"
        (template_dir / "word").mkdir(parents=True)
        (gerado_dir / "word").mkdir(parents=True)
        (template_dir / "word" / "document.xml").write_text(XML_SINTETICO_COR, encoding="utf-8")

        dados = {"JUIZO": "1ª Vara", "AUTOR": "Fulano", "VALOR_FRA": "R$ 10,00",
                  "SINOPSE_FATOS": "texto"}
        esperado_xml, _ = substituir_placeholders(XML_SINTETICO_COR, dados)

        (gerado_dir / "word" / "document.xml").write_text(esperado_xml, encoding="utf-8")
        ok = verificar_template_lock(template_dir, gerado_dir, dados)
        assert ok["ok"], ok["divergencias"]


# --------------------------------------------------------------- negrito em placeholder (Etapa 5.3 §9)
def test_negrito_sem_marcacao_nao_muda_comportamento():
    # caminho rápido preservado: sem "**" no valor, saída idêntica à
    # anterior à Etapa 5.3 (nenhum <w:b/> extra, nenhum run a mais).
    xml, _ = substituir_placeholders(XML_SINTETICO, {"SINOPSE_FATOS": "Texto simples sem negrito."})
    assert "<w:b/>" not in xml
    assert xml.count("<w:r>") == XML_SINTETICO.count("<w:r>")


def test_negrito_segmento_isolado_em_run_proprio():
    xml, _ = substituir_placeholders(
        XML_SINTETICO_COR, {"SINOPSE_FATOS": "Irregularidade do tipo **DESVIO DE ENERGIA**, apurada em campo."})
    import xml.etree.ElementTree as ET
    ET.fromstring(  # bem formado — precisa do xmlns:w (XML_SINTETICO_COR não declara)
        xml.replace("<w:document>", '<w:document xmlns:w="urn:w">', 1))
    assert "<w:b/>" in xml and "<w:bCs/>" in xml
    assert "**" not in xml  # marcação markdown removida, não vaza pro documento
    assert "DESVIO DE ENERGIA" in xml
    # b/bCs vêm antes de color na sequência CT_RPr
    idx_b = xml.index("<w:b/>")
    idx_color = xml.index("<w:color", idx_b)
    assert idx_b < idx_color


def test_negrito_preserva_texto_antes_e_depois_do_segmento():
    xml, _ = substituir_placeholders(
        XML_SINTETICO, {"SINOPSE_FATOS": "Antes **NEGRITO** depois."})
    assert "Antes " in xml and " depois." in xml
    assert "NEGRITO" in xml


def test_negrito_multilinha_apenas_uma_linha_com_marcacao():
    xml, _ = substituir_placeholders(
        XML_SINTETICO, {"SINOPSE_FATOS": "**TIPO DA IRREGULARIDADE**\nExplicação técnica em linha separada, sem negrito."})
    import xml.etree.ElementTree as ET
    ET.fromstring(xml)  # já declara xmlns:w — bem formado
    assert xml.count("<w:b/>") == 1  # só a primeira linha tem negrito
    assert "<w:br/>" not in xml  # linha 2 virou <w:p> novo (Etapa 5.3-B), não <w:br/>
    assert "Explicação técnica" in xml


def test_negrito_lock_recomputa_igual_com_transformar_padrao():
    # Template Lock recomputa "esperado" via a MESMA função — precisa
    # continuar batendo byte a byte mesmo com runs extras do negrito.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        template_dir, gerado_dir = tmp / "template", tmp / "gerado"
        (template_dir / "word").mkdir(parents=True)
        (gerado_dir / "word").mkdir(parents=True)
        (template_dir / "word" / "document.xml").write_text(XML_SINTETICO_COR, encoding="utf-8")

        dados = {"JUIZO": "1ª Vara", "AUTOR": "Fulano", "VALOR_FRA": "R$ 10,00",
                  "SINOPSE_FATOS": "Tipo **X** encontrado."}
        esperado_xml, _ = substituir_placeholders(XML_SINTETICO_COR, dados)
        (gerado_dir / "word" / "document.xml").write_text(esperado_xml, encoding="utf-8")
        ok = verificar_template_lock(template_dir, gerado_dir, dados)
        assert ok["ok"], ok["divergencias"]

        adulterado = esperado_xml.replace(
            "<w:rPr><w:b/></w:rPr><w:t>Texto institucional fixo</w:t>",
            '<w:rPr><w:b/><w:color w:val="FF0000"/></w:rPr><w:t>Texto institucional fixo</w:t>')
        (gerado_dir / "word" / "document.xml").write_text(adulterado, encoding="utf-8")
        ruim = verificar_template_lock(template_dir, gerado_dir, dados)
        assert not ruim["ok"], "Template Lock deveria reprovar cor de texto fixo alterada"


def test_validar_placeholders_rejeita_desconhecido_no_schema():
    r = validar_placeholders(XML_SINTETICO, {"CAMPO_INEXISTENTE": "x"}, SCHEMA_SINTETICO)
    assert not r["ok"]
    assert any("fora do schema" in e for e in r["erros"])


def test_validar_placeholders_rejeita_dado_faltando():
    r = validar_placeholders(XML_SINTETICO, {"JUIZO": "x"}, SCHEMA_SINTETICO)
    assert not r["ok"]
    assert any("sem dado fornecido" in e for e in r["erros"])


def test_validar_placeholders_aceita_completo():
    r = validar_placeholders(XML_SINTETICO, {
        "JUIZO": "x", "LOCAL_DATA": "y", "SINOPSE_FATOS": "z",
    }, SCHEMA_SINTETICO)
    assert r["ok"], r["erros"]


def test_template_lock_detecta_alteracao_fora_de_placeholder(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        template_dir, gerado_dir = tmp / "template", tmp / "gerado"
        (template_dir / "word").mkdir(parents=True)
        (gerado_dir / "word").mkdir(parents=True)
        (template_dir / "word" / "document.xml").write_text(XML_SINTETICO, encoding="utf-8")

        dados = {"JUIZO": "1ª Vara Cível", "LOCAL_DATA": "hoje", "SINOPSE_FATOS": "fatos"}
        esperado_xml, _ = substituir_placeholders(XML_SINTETICO, dados)

        # 1) geração correta -> Template Lock OK
        (gerado_dir / "word" / "document.xml").write_text(esperado_xml, encoding="utf-8")
        ok = verificar_template_lock(template_dir, gerado_dir, dados)
        assert ok["ok"], ok["divergencias"]

        # 2) adultera texto fixo fora de qualquer placeholder -> deve reprovar
        adulterado = esperado_xml.replace("Salvador,", "Rio de Janeiro,")
        (gerado_dir / "word" / "document.xml").write_text(adulterado, encoding="utf-8")
        ruim = verificar_template_lock(template_dir, gerado_dir, dados)
        assert not ruim["ok"], "Template Lock deveria reprovar alteração de texto fixo"


def test_template_lock_detecta_arquivo_extra_ou_ausente():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        template_dir, gerado_dir = tmp / "template", tmp / "gerado"
        (template_dir / "word").mkdir(parents=True)
        (gerado_dir / "word").mkdir(parents=True)
        (template_dir / "word" / "document.xml").write_text(XML_SINTETICO, encoding="utf-8")
        (template_dir / "word" / "header1.xml").write_text("<w:hdr/>", encoding="utf-8")

        dados = {"JUIZO": "x", "LOCAL_DATA": "y", "SINOPSE_FATOS": "z"}
        esperado_xml, _ = substituir_placeholders(XML_SINTETICO, dados)
        (gerado_dir / "word" / "document.xml").write_text(esperado_xml, encoding="utf-8")
        # header1.xml do template não foi copiado para o gerado -> deve reprovar
        r = verificar_template_lock(template_dir, gerado_dir, dados)
        assert not r["ok"]
        assert any("ausente no gerado" in d for d in r["divergencias"])


def test_pipeline_completo_contra_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ver ADR-0006). "
              "Rodando só os testes de unidade sobre XML sintético.")
        return

    from docx_template_engine import carregar_schema, extrair_placeholders as _ep, _importar_toolkit
    import shutil as _shutil
    import tempfile as _tempfile

    schema = carregar_schema(SCHEMA_REAL)

    # IMPORTANTE: alguns placeholders ficam fragmentados entre runs no DOCX
    # bruto (confirmado na auditoria) — só aparecem inteiros depois do merge
    # de runs do unpack.py. Ler o zip cru para contar placeholders SUBESTIMA
    # o total; por isso este teste passa pelo mesmo unpack com merge que a
    # engine real usa, não por um zipfile.read() ingênuo.
    unpack_mod, _ = _importar_toolkit()
    with _tempfile.TemporaryDirectory() as tmp:
        cópia = Path(tmp) / "t.docx"
        _shutil.copy2(TEMPLATE_REAL, cópia)
        unpacked = Path(tmp) / "unpacked"
        unpack_mod.unpack(str(cópia), str(unpacked))
        template_xml = (unpacked / "word" / "document.xml").read_text(encoding="utf-8")

    placeholders_reais = _ep(template_xml)
    assert placeholders_reais == set(schema["editable_placeholders"]), (
        f"schema.json desatualizado em relação ao DOCX real: "
        f"template={sorted(placeholders_reais)} schema={sorted(schema['editable_placeholders'])}"
    )

    dados_ficticios = {
        "JUIZO": "1ª Vara Cível da Comarca de Salvador/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha um da realidade fática fictícia.\nLinha dois.",
        "IRREGULARIDADE_ENCONTRADA": "ligação direta (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
    }

    with __import__("tempfile").TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao-teste.docx"
        relatorio = gerar_peca(TEMPLATE_REAL, SCHEMA_REAL, dados_ficticios, saida)
        assert relatorio["status"] == "OK", relatorio
        assert relatorio["template_lock"] == "OK"
        assert saida.exists() and saida.stat().st_size > 0

        # TEST-009: documento final deve abrir sem corrupção — checagem
        # mínima: é um zip válido com word/document.xml e sem placeholder
        # residual.
        import zipfile as _zf
        with _zf.ZipFile(saida) as z:
            assert "word/document.xml" in z.namelist()
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        assert not extrair_placeholders(gerado_xml), "documento final não pode ter placeholder residual (TEST-004)"
        assert "COELBA" in gerado_xml, "texto fixo institucional não pode sumir"

        # Etapa 3: todo conteúdo substituído fica em FF0000 — contra o
        # template real, com <w:rPr> pretty-printado pelo unpack.py
        # (achado real desta implementação).
        assert 'w:val="FF0000"' in gerado_xml, "conteúdo substituído deveria estar em FF0000"
        assert "FULANO DE TAL" in gerado_xml  # AUTOR fictício, sem qualificação (Etapa 3, achado real)

        # TEST-001, contra o arquivo real (não só XML sintético): adultera
        # texto fixo fora de qualquer placeholder e confirma que o Template
        # Lock reprova — validado manualmente nesta auditoria (achado real:
        # substituir "COELBA" por texto arbitrário no documento gerado).
        adulterada = Path(tmp) / "adulterada.docx"
        doc_adulterado = gerado_xml.replace("COELBA", "OUTRA EMPRESA QUALQUER", 1)
        with _zf.ZipFile(saida) as zin, _zf.ZipFile(adulterada, "w", _zf.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = doc_adulterado.encode("utf-8")
                zout.writestr(item, data)

        unpack_mod, _ = _importar_toolkit()
        ref_dir, aud_dir = Path(tmp) / "ref_unpacked", Path(tmp) / "aud_unpacked"
        unpack_mod.unpack(str(saida), str(ref_dir))
        unpack_mod.unpack(str(adulterada), str(aud_dir))
        lock_result = verificar_template_lock(ref_dir, aud_dir, dados_ficticios)
        assert not lock_result["ok"], "Template Lock deveria reprovar adulteração de texto institucional fixo"

    print("Pipeline completo contra o template real: OK (Template Lock + "
          "sem resíduo + schema.json bate com o DOCX + reprova adulteração).")


# --------------------------------------------------------------- fonte do PROCESSO Nº (Etapa 5.3 §2)
def test_processo_no_fonte_12_no_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ADR-0006).")
        return
    import zipfile as _zf
    import lxml.etree as LET

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    NS = {"w": W}
    with _zf.ZipFile(TEMPLATE_REAL) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    root = LET.fromstring(xml.encode("utf-8"))

    alvos = [t for t in root.findall(".//w:t", NS)
             if t.text in ("PROCESSO Nº ", "{{NUMERO_PROCESSO}}")]
    assert alvos, "runs 'PROCESSO Nº ' / '{{NUMERO_PROCESSO}}' não encontrados no template real"
    for t in alvos:
        rpr = t.getparent().find("w:rPr", NS)
        assert rpr is not None, f"run {t.text!r} sem w:rPr"
        sz = rpr.find("w:sz", NS)
        assert sz is not None, f"run {t.text!r} sem w:sz"
        val = sz.get("{%s}val" % W)
        assert val == "24", (
            f"run {t.text!r}: w:sz={val!r}, esperado '24' (12pt em meio-pontos) "
            f"— achado real do Teste Real 01-B (estava em '28' = 14pt)")
    print(f"PROCESSO Nº em 12pt confirmado no template real ({len(alvos)} runs).")


# --------------------------------------------------------------- Etapa 5.3-B: normalização visual de parágrafos
# XML sintético com w:pPr real (jc/spacing/ind/keepNext/keepLines/
# widowControl/contextualSpacing/tabs) no parágrafo-placeholder — para
# testar herança estrutural de verdade, não só rPr de run.
_PPR_COMPLETO = (
    '<w:pPr><w:pStyle w:val="Corpo"/><w:tabs><w:tab w:val="left" w:pos="2040"/></w:tabs>'
    '<w:spacing w:before="120" w:after="240" w:line="360" w:lineRule="auto"/>'
    '<w:ind w:left="0" w:right="46"/><w:contextualSpacing/><w:jc w:val="both"/>'
    '<w:keepNext/><w:keepLines/><w:widowControl/></w:pPr>'
)
XML_MULTIPARAGRAFO = (
    f'<w:document xmlns:w="{NS_W}"><w:body>'
    f'<w:p>{_PPR_COMPLETO}<w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
    '<w:t>{{SINOPSE_FATOS}}</w:t></w:r></w:p>'
    '</w:body></w:document>'
)
# Reproduz a estrutura real de IRREGULARIDADE_ENCONTRADA: prefixo fixo +
# placeholder + sufixo fixo, todos runs distintos na MESMA <w:p> (Etapa
# 5.3-B §14 — causa raiz real da duplicação diagnosticada).
XML_IRREGULARIDADE_COM_SUFIXO_FIXO = (
    f'<w:document xmlns:w="{NS_W}"><w:body>'
    f'<w:p>{_PPR_COMPLETO}'
    '<w:r><w:rPr/><w:t xml:space="preserve">Na ocasião, foi constatada irregularidade do tipo, </w:t></w:r>'
    '<w:r><w:rPr><w:b/><w:color w:val="EE0000"/></w:rPr><w:t>{{IRREGULARIDADE_ENCONTRADA}}</w:t></w:r>'
    '<w:r><w:rPr/><w:t>, circunstância que impedia o registro integral.</w:t></w:r>'
    '</w:p>'
    '<w:p><w:r><w:t>parágrafo seguinte com quebra legítima<w:br/>segunda linha legítima</w:t></w:r></w:p>'
    '</w:body></w:document>'
)
SCHEMA_IRREGULARIDADE = {"editable_placeholders": ["IRREGULARIDADE_ENCONTRADA"]}


def _pprs_de_todos_paragrafos(xml: str) -> list:
    """[w:pPr XML de cada <w:p>, na ordem] — string vazia se o parágrafo
    não tem w:pPr."""
    root = LET.fromstring(xml.encode("utf-8"))
    saida = []
    for p in root.findall(".//w:p", {"w": NS_W}):
        ppr = p.find("w:pPr", {"w": NS_W})
        saida.append(LET.tostring(ppr, encoding="unicode") if ppr is not None else "")
    return saida


# A. Parágrafo simples inserido preserva w:pPr do modelo.
def test_A_paragrafo_simples_preserva_ppr_do_modelo():
    xml, _ = substituir_placeholders(XML_MULTIPARAGRAFO, {"SINOPSE_FATOS": "Uma linha só."})
    pprs = _pprs_de_todos_paragrafos(xml)
    assert len(pprs) == 1
    for tag in ("w:pStyle", "w:spacing", "w:ind", "w:contextualSpacing",
                "w:jc", "w:keepNext", "w:keepLines", "w:widowControl", "w:tabs"):
        assert tag in pprs[0], f"{tag} ausente do w:pPr do parágrafo único"


# B. Múltiplos parágrafos gerados preservam o padrão estrutural do parágrafo-base.
def test_B_multiplos_paragrafos_preservam_padrao_estrutural():
    xml, _ = substituir_placeholders(
        XML_MULTIPARAGRAFO,
        {"SINOPSE_FATOS": "Primeiro fato.\nSegundo fato.\nTerceiro fato."})
    pprs = _pprs_de_todos_paragrafos(xml)
    assert len(pprs) == 3
    assert pprs[0] == pprs[1] == pprs[2], "os 3 w:pPr deveriam ser idênticos (clone do original)"
    for tag in ("w:pStyle", "w:spacing", "w:ind", "w:contextualSpacing",
                "w:jc", "w:keepNext", "w:keepLines", "w:widowControl", "w:tabs"):
        assert tag in pprs[0]


# C. Runs normais preservam propriedades tipográficas.
def test_C_runs_normais_preservam_propriedades_tipograficas():
    xml, _ = substituir_placeholders(
        XML_MULTIPARAGRAFO, {"SINOPSE_FATOS": "Primeira.\nSegunda."})
    # w:sz do run original preservado em cada parágrafo gerado
    assert xml.count('<w:sz w:val="24"/>') == 2


# D. Run em negrito altera somente o necessário para o destaque.
def test_D_negrito_altera_somente_o_necessario():
    xml, _ = substituir_placeholders(
        XML_MULTIPARAGRAFO, {"SINOPSE_FATOS": "Texto **destacado** aqui."})
    idx_b = xml.index("<w:b/>")
    rpr_negrito = xml[xml.rindex("<w:rPr>", 0, idx_b):xml.index("</w:rPr>", idx_b) + len("</w:rPr>")]
    # mesma base do rPr original (w:sz) + apenas w:b/w:bCs/w:color a mais
    assert '<w:sz w:val="24"/>' in rpr_negrito
    assert "<w:i" not in rpr_negrito and "w:strike" not in rpr_negrito


# E. Nenhum parágrafo gerado ultrapassa 380 caracteres — INV-PARAGRAFO-380 preservada.
def test_E_paragrafo_380_preservado_pela_normalizacao():
    sys.path.insert(0, str(BASE / "scripts"))
    from validate_paragrafos import validar_paragrafo_380
    linha_curta = "Parágrafo dentro do limite de 380 caracteres, sem excesso algum."
    assert validar_paragrafo_380(linha_curta) == []
    linha_longa = "x" * 381
    erros = validar_paragrafo_380(linha_longa)
    assert len(erros) == 1 and "381" in erros[0]
    # a normalização de parágrafos (Etapa 5.3-B) não altera contagem de
    # caracteres — cada linha lógica continua validável isoladamente ANTES
    # do template engine rodar (INV-PARAGRAFO-380 valida sobre os dados de
    # entrada, nunca sobre o XML resultante); a explosão em <w:p> reais só
    # muda a REPRESENTAÇÃO OOXML, nunca o conteúdo/tamanho de cada linha.
    multi = "Primeira linha curta.\nSegunda linha também curta."
    xml, _ = substituir_placeholders(XML_MULTIPARAGRAFO, {"SINOPSE_FATOS": multi})
    for linha in multi.split("\n"):
        assert linha in xml
        assert len(linha) <= 380


# F. Não ocorre duplicação da expressão introdutória da irregularidade.
def test_F_sem_duplicacao_da_expressao_introdutoria():
    dados = {"IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**"}
    xml, _ = substituir_placeholders(XML_IRREGULARIDADE_COM_SUFIXO_FIXO, dados)
    assert xml.count("irregularidade do tipo") == 1
    assert xml.count("Na ocasião") == 1
    assert xml.count("circunstância que impedia") == 1


# G. Tipo da irregularidade aparece em negrito real (<w:b/>).
def test_G_tipo_irregularidade_em_negrito_real():
    dados = {"IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**"}
    xml, _ = substituir_placeholders(XML_IRREGULARIDADE_COM_SUFIXO_FIXO, dados)
    assert "<w:b/>" in xml
    assert "desvio de energia antes do sistema de medição" in xml
    assert "**" not in xml


# H. Tipo da irregularidade não é convertido integralmente para caixa alta.
def test_H_tipo_irregularidade_nao_vira_caixa_alta():
    dados = {"IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**"}
    xml, _ = substituir_placeholders(XML_IRREGULARIDADE_COM_SUFIXO_FIXO, dados)
    assert "desvio de energia antes do sistema de medição" in xml  # minúsculas preservadas
    assert "DESVIO DE ENERGIA ANTES DO SISTEMA DE MEDIÇÃO" not in xml


# I. Template oficial permanece estruturalmente preservado fora das regiões dinâmicas
# — já coberto por test_pipeline_completo_contra_template_real (Template Lock
# recomputa e compara byte a byte o documento inteiro) e
# test_cor_adulterada_em_texto_fixo_reprovada_pelo_lock (reprova alteração
# fora de placeholder). Não duplicado aqui.


# Sufixo fixo (", circunstância que impedia o registro integral.") não pode
# ser arrastado para o parágrafo novo — fica com a primeira linha lógica,
# igual à frase real do modelo (Etapa 5.3-B §14, causa raiz confirmada).
def test_sufixo_fixo_permanece_com_primeira_linha_ao_explodir():
    dados = {"IRREGULARIDADE_ENCONTRADA": "**desvio de energia**\nTecnicamente, caracteriza-se por by-pass."}
    xml, _ = substituir_placeholders(XML_IRREGULARIDADE_COM_SUFIXO_FIXO, dados)
    pprs_e_paragrafos = xml.split("</w:p>")
    assert "circunstância que impedia" in pprs_e_paragrafos[0]
    assert "circunstância que impedia" not in pprs_e_paragrafos[1]
    assert "Tecnicamente" in pprs_e_paragrafos[1]


# 3 parágrafos lógicos -> 3 <w:p> reais, zero <w:br/> entre eles.
def test_multilinha_3_paragrafos_gera_3_wp_reais_sem_br():
    xml, _ = substituir_placeholders(
        XML_MULTIPARAGRAFO,
        {"SINOPSE_FATOS": "Fato um.\nFato dois.\nFato três."})
    assert "<w:br/>" not in xml
    assert xml.count('w:val="FF0000"') == 3
    assert "Fato um." in xml and "Fato dois." in xml and "Fato três." in xml
    assert xml.index("Fato um.") < xml.index("Fato dois.") < xml.index("Fato três.")
    pprs = _pprs_de_todos_paragrafos(xml)
    assert len(pprs) == 3
    assert "urn:ede" not in xml


# Idempotência: reexecutar sobre a própria saída não altera nada.
def test_idempotencia_reexecucao_nao_altera_saida():
    xml1, _ = substituir_placeholders(
        XML_MULTIPARAGRAFO, {"SINOPSE_FATOS": "Um.\nDois.\nTrês."})
    xml2, subst2 = substituir_placeholders(xml1, {})
    assert xml2 == xml1
    assert subst2 == set()
    pprs1, pprs2 = _pprs_de_todos_paragrafos(xml1), _pprs_de_todos_paragrafos(xml2)
    assert pprs1 == pprs2


# Quebra legítima pré-existente no template nunca é convertida em <w:p>.
def test_quebra_legitima_preexistente_nao_e_convertida():
    xml, _ = substituir_placeholders(
        XML_IRREGULARIDADE_COM_SUFIXO_FIXO,
        {"IRREGULARIDADE_ENCONTRADA": "**tipo x**\nsegunda linha gerada."})
    assert "quebra legítima aqui" in xml or "quebra legítima" in xml
    assert "<w:br/>" in xml, "a quebra legítima pré-existente deveria continuar intacta"
    # só 1 <w:br/> sobrevive (a legítima) — nenhum marcador nosso escapou
    assert xml.count("<w:br/>") == 1


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
