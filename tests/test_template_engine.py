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
     template real (que é institucional, fora do git — ADR-0006).
  2. Teste de ponta a ponta contra templates/contestacao/modelo-oficial.docx
     — só roda se o arquivo existir localmente; do contrário, SKIP
     explícito (não é falha: ausência do template é esperada em clone
     limpo/CI).

Uso:
  python tests/test_template_engine.py
"""
import sys
from pathlib import Path

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
XML_SINTETICO = (
    '<w:document><w:body>'
    '<w:p><w:r><w:t>{{JUIZO}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:t xml:space="preserve">Salvador, {{LOCAL_DATA}}.</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>{{SINOPSE_FATOS}}</w:t></w:r></w:p>'
    '</w:body></w:document>'
)
SCHEMA_SINTETICO = {"editable_placeholders": ["JUIZO", "LOCAL_DATA", "SINOPSE_FATOS"]}


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


def test_substituicao_multilinha_usa_br_sem_tocar_paragrafo():
    xml, _ = substituir_placeholders(XML_SINTETICO, {"SINOPSE_FATOS": "Primeira linha.\nSegunda linha."})
    assert "<w:br/>" in xml
    assert "Primeira linha." in xml and "Segunda linha." in xml
    # continua um único <w:p> (não vira dois parágrafos) — só o run se abre em runs/br
    assert xml.count("<w:p>") == XML_SINTETICO.count("<w:p>")


def test_escapa_caracteres_xml_no_valor():
    xml, _ = substituir_placeholders(XML_SINTETICO, {"JUIZO": "Vara & Cia <teste>"})
    assert "Vara &amp; Cia &lt;teste&gt;" in xml
    assert "Vara & Cia <teste>" not in xml  # não pode vazar & / < / > crus


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
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada — dado fictício de teste)",
        "ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA": "Argumento fictício de teste.",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
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


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
