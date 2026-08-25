#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_argumentacao_evolucao_consumo_removida.py — guarda de governança
para a remoção definitiva de `ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA`
(docs/specs/SPEC-0001.md §49, CLAUDE.md, docs/PENDENCIAS.md PEND-006).

Decisão: o placeholder não deve mais existir em nenhum contrato ativo do
projeto — não renomeado, sem alias, sem substituto equivalente. O texto
institucional sobre evolução de consumo pertence exclusivamente ao
modelo oficial (bloco `EVOLUCAO_CONSUMO`, hoje `CONDICIONAL_PADRAO`,
sem placeholder próprio).

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_block_engine import carregar_catalogo, gerar_peca_com_blocos  # noqa: E402
from docx_template_engine import garantir_utf8  # noqa: E402

TERMO = "ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA"
TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"

# Arquivos que documentam a remoção em si (história/decisão) — mencionar
# o termo aqui é esperado e não é uma ocorrência funcional ativa.
ARQUIVOS_HISTORICOS_PERMITIDOS = {
    BASE / "docs" / "specs" / "SPEC-0001.md",
    BASE / "CLAUDE.md",
    BASE / "docs" / "PENDENCIAS.md",
    BASE / "docs" / "E2E_FASE7.md",  # registro histórico de execução manual (Fase 7)
    BASE / "skills" / "contestacao" / "SKILL.md",  # nota de remoção no próprio texto da Skill
    Path(__file__),
}


def _pular_se_sem_template_real():
    if not TEMPLATE_REAL.exists():
        print("SKIP (template real ausente localmente — ADR-0006, esperado em CI/clone limpo)")
        return True
    return False


# A. zero ocorrência nos contratos ativos (código, schema, catálogo, fixtures) do projeto.
def test_A_zero_ocorrencia_em_contratos_ativos():
    alvos = list(BASE.glob("scripts/*.py")) + list(BASE.glob("templates/contestacao/*.json")) \
        + list(BASE.glob("tests/fixtures/**/*.json")) + list(BASE.glob("tests/test_*.py"))
    achados = []
    for f in alvos:
        if f.resolve() == Path(__file__).resolve():
            continue
        texto = f.read_text(encoding="utf-8")
        if TERMO in texto:
            # só é aceitável mencionar o termo dentro de um comentário que
            # documenta a remoção (Python "#") ou de uma nota de
            # documentação em JSON (convenção já usada no projeto: chave
            # "_nota"/"_nota_*") — nunca como chave de dict/dados ativa.
            for linha in texto.splitlines():
                s = linha.strip()
                if TERMO in linha and not s.startswith("#") and '"_nota' not in linha:
                    achados.append((str(f), s))
    assert not achados, f"ocorrência funcional ativa de {TERMO}: {achados}"


# B. zero marcador residual no DOCX final; F. bloco composicional continua funcionando; I. Template Lock íntegro.
def test_B_F_I_docx_real_sem_marcador_bloco_funciona_lock_integro():
    if _pular_se_sem_template_real():
        return
    catalogo = carregar_catalogo(CATALOGO_REAL)
    dados = {
        "JUIZO": "1ª Vara Cível da Comarca de Salvador/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "**ligação direta** (dado fictício de teste)",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
    }
    assert TERMO not in dados

    decisoes = {b["id"]: {"decisao": "INCLUIR"}
                for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    fatos_processuais = {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True}

    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao-teste.docx"
        r = gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL,
                                   dados, decisoes, saida, fatos_processuais=fatos_processuais)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"  # I
        assert "EVOLUCAO_CONSUMO" in r["blocos_incluidos"]  # F: bloco continua funcionando

        import zipfile as _zf
        with _zf.ZipFile(saida) as z:
            gerado_xml = z.read("word/document.xml").decode("utf-8")
        assert "{{" not in gerado_xml  # B: nenhum placeholder residual (nenhum, não só este)
        assert f"{{{{{TERMO}}}}}" not in gerado_xml  # B, redundante e explícito para este termo
        # C: texto institucional fixo do bloco aparece exatamente uma vez.
        assert gerado_xml.count("levantamento de carga instalada") == 1
        # H: os demais placeholders continuam substituídos normalmente.
        assert "FULANO DE TAL" in gerado_xml
        assert "R$ 0,00" in gerado_xml


# D/E. pipeline não exige o placeholder; ausência não causa fail-closed.
def test_D_E_ausencia_do_placeholder_nao_e_exigida_nem_aborta():
    schema = json.loads(SCHEMA_REAL.read_text(encoding="utf-8")) if SCHEMA_REAL.exists() else None
    if schema is not None:
        assert TERMO not in schema["editable_placeholders"]
        assert TERMO not in schema.get("placeholder_contracts", {})

    sys.path.insert(0, str(BASE / "scripts"))
    from gerar_contestacao import PLACEHOLDERS_OBRIGATORIOS_NAO_VAZIOS
    assert TERMO not in PLACEHOLDERS_OBRIGATORIOS_NAO_VAZIOS

    from validate_placeholder_semantics import VALIDADORES_ESPECIFICOS
    assert TERMO not in VALIDADORES_ESPECIFICOS

    from validate_paragrafos import LIMITES_DENSIDADE_BLOCO
    assert TERMO not in LIMITES_DENSIDADE_BLOCO


# Catálogo: bloco EVOLUCAO_CONSUMO não referencia mais placeholder algum.
def test_catalogo_evolucao_consumo_sem_placeholder_proprio():
    catalogo = carregar_catalogo(CATALOGO_REAL)
    bloco = next(b for b in catalogo["blocks"] if b["id"] == "EVOLUCAO_CONSUMO")
    assert bloco["placeholders"] == []
    assert bloco["dependencies"] == []
    assert bloco["tipo"] == "CONDICIONAL_PADRAO"


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    garantir_utf8()
    main()
