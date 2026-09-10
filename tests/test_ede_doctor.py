#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ede_doctor.py — diagnóstico de ambiente (Etapa 5.10, Commit 6:
"feat(plugin): adicionar bootstrap do modelo oficial e ede doctor").

Mesmo par SCHEMA/CATALOGO sintético mínimo de
tests/test_instalar_modelo_oficial.py (duplicado aqui, não importado —
mesmo padrão de independência já usado entre
tests/test_docx_package.py e tests/test_fail_closed_docx_package.py).

Todos os cenários usam `executar_diagnostico(base=BASE, ...)` com os
caminhos de schema/catálogo/modelo injetados — BASE continua sendo o
repositório real (scripts/, rag/ já existem e são parte do que está sob
teste), mas o contrato institucional (schema/catálogo/modelo) é sempre
sintético, então nenhum teste aqui depende de modelo-oficial.docx real
nem de skills/docx/.

Uso:
  python tests/test_ede_doctor.py
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import ede_doctor  # noqa: E402

# --------------------------------------------------------------- fixtures sintéticas
# (mesmo conteúdo de tests/test_instalar_modelo_oficial.py — duplicado
# deliberadamente, ver docstring do módulo)
_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" ContentType='
    b'"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    b'</Types>'
)
_RELS_RAIZ = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    b'Target="word/document.xml"/></Relationships>'
)
_CORPO_VALIDO = (
    b'<w:sdt><w:sdtPr><w:tag w:val="BLOCO:FOO"/></w:sdtPr>'
    b'<w:sdtContent><w:p><w:r><w:t>{{FOO}}</w:t></w:r></w:p></w:sdtContent></w:sdt>'
)
_CORPO_INCOMPATIVEL = b'<w:p><w:r><w:t>nada de FOO ou SDT aqui</w:t></w:r></w:p>'

SCHEMA_MINIMO = {"editable_placeholders": ["FOO"], "version": "9.9.9-teste"}
CATALOGO_MINIMO = {
    "version": "9.9.9-teste",
    "blocks": [
        {"id": "BLOCO_FOO", "tag": "BLOCO:FOO", "tipo": "FIXO", "parent": None,
         "children": [], "decision_mode": "estrategista", "cardinality": "ONE"},
    ],
    "zones": [],
}


def _document_xml(corpo_bytes: bytes) -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:body>' + corpo_bytes + b'</w:body></w:document>'
    )


def _criar_docx(destino: Path, corpo_bytes: bytes) -> Path:
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS_RAIZ)
        zf.writestr("word/document.xml", _document_xml(corpo_bytes))
    return destino


def _escrever_json(caminho: Path, dado: dict) -> Path:
    caminho.write_text(json.dumps(dado, ensure_ascii=False), encoding="utf-8")
    return caminho


def _ambiente_compativel(tmp: Path):
    """(schema_path, catalogo_path, modelo_path) mutuamente compatíveis —
    cenário 'ambiente pronto'."""
    schema_path = _escrever_json(tmp / "schema.json", SCHEMA_MINIMO)
    catalogo_path = _escrever_json(tmp / "blocos.json", CATALOGO_MINIMO)
    modelo_path = _criar_docx(tmp / "modelo-oficial.docx", _CORPO_VALIDO)
    return schema_path, catalogo_path, modelo_path


def _item(checks, nome):
    for c in checks:
        if c["item"] == nome:
            return c
    raise AssertionError(f"item {nome!r} não encontrado nos checks: {[c['item'] for c in checks]}")


# --------------------------------------------------------------- A: ambiente pronto
def test_A_ambiente_pronto_reporta_ready_true():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
        assert r["ready"] is True, r["obrigatorias_falhando"]
        assert r["obrigatorias_falhando"] == []
        assert _item(r["checks"], "template:contrato")["ok"] is True


# --------------------------------------------------------------- B: modelo ausente
def test_B_modelo_ausente_reporta_motivo_explicito_sem_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, _ = _ambiente_compativel(tmp)
        modelo_inexistente = tmp / "nao_instalado.docx"
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_inexistente)
        assert r["ready"] is False
        assert "template:modelo-oficial.docx" in r["obrigatorias_falhando"]
        item = _item(r["checks"], "template:modelo-oficial.docx")
        assert "ausente" in item["detalhe"]
        assert "instalar_modelo_oficial" in item["detalhe"]
        assert "Traceback" not in item["detalhe"]


# --------------------------------------------------------------- C: dependência Python ausente
def test_C_dependencia_python_ausente_reportada_sem_crash(monkeypatch):
    original = ede_doctor._dependencia_presente

    def _fake(modulo):
        if modulo == "numpy":
            return False
        return original(modulo)

    monkeypatch.setattr(ede_doctor, "_dependencia_presente", _fake)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
    assert r["ready"] is False
    assert "dependencia:numpy" in r["obrigatorias_falhando"]
    # lxml continua presente de verdade — o runtime DOCX próprio não é afetado
    assert _item(r["checks"], "dependencia:lxml")["ok"] is True
    assert _item(r["checks"], "runtime:docx_package")["ok"] is True


# --------------------------------------------------------------- D: schema ausente
def test_D_schema_ausente():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        schema_inexistente = tmp / "schema_nao_existe.json"
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_inexistente, catalogo_path=catalogo_path, modelo_path=modelo_path)
        assert r["ready"] is False
        assert "template:schema.json" in r["obrigatorias_falhando"]


# --------------------------------------------------------------- E: blocos.json ausente
def test_E_blocos_json_ausente_sem_traceback():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, _, modelo_path = _ambiente_compativel(tmp)
        catalogo_inexistente = tmp / "blocos_nao_existe.json"
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_inexistente, modelo_path=modelo_path)
        assert r["ready"] is False
        assert "template:blocos.json" in r["obrigatorias_falhando"]
        item = _item(r["checks"], "template:blocos.json")
        assert "Traceback" not in (item["detalhe"] or "")


# --------------------------------------------------------------- F: runtime DOCX ausente/inimportável
def test_F_runtime_docx_inimportavel_quando_lxml_ausente_sem_crash(monkeypatch):
    """Item 8 do pedido, na prática: docx_package.py faz "import lxml" no
    nível de módulo — sem a checagem controlada (find_spec, nunca import
    direto do runtime) isto derrubaria o diagnóstico inteiro. Confirma que
    executar_diagnostico() nunca levanta, mesmo com lxml "ausente"."""
    original = ede_doctor._dependencia_presente

    def _fake(modulo):
        if modulo == "lxml":
            return False
        return original(modulo)

    monkeypatch.setattr(ede_doctor, "_dependencia_presente", _fake)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(  # não deve levantar
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
    assert r["ready"] is False
    assert "dependencia:lxml" in r["obrigatorias_falhando"]
    assert "runtime:docx_package" in r["obrigatorias_falhando"]
    assert "template:contrato" in r["obrigatorias_falhando"]
    assert len(r["checks"]) > 0  # diagnóstico terminou, não abortou no meio


# --------------------------------------------------------------- G: template incompatível
def test_G_template_incompativel_reportado_no_contrato():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, _ = _ambiente_compativel(tmp)
        modelo_incompativel = _criar_docx(tmp / "modelo-oficial.docx", _CORPO_INCOMPATIVEL)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_incompativel)
        assert r["ready"] is False
        assert "template:contrato" in r["obrigatorias_falhando"]
        item = _item(r["checks"], "template:contrato")
        assert "FOO" in item["detalhe"] or "tag_ausente" in item["detalhe"]


# --------------------------------------------------------------- H: diretório de saída sem permissão
def test_H_diretorio_saida_nao_utilizavel_reportado(tmp_path):
    """Simulação portátil (Windows/POSIX) de "não é possível usar como
    diretório de saída": aponta para um caminho que já existe como
    ARQUIVO comum — mkdir(parents=True, exist_ok=True) falha em ambos os
    SOs, sem depender de chmod (não confiável no Windows)."""
    arquivo_no_caminho = tmp_path / "isto_e_um_arquivo_nao_um_dir"
    arquivo_no_caminho.write_text("ocupado", encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=arquivo_no_caminho,
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
        assert r["ready"] is False
        assert "saida:diretorio" in r["obrigatorias_falhando"]


# --------------------------------------------------------------- host-agnostic (item 7 do pedido)
def test_claude_plugin_root_e_informativo_nunca_obrigatorio(monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
        item = _item(r["checks"], "ambiente:CLAUDE_PLUGIN_ROOT")
        assert item["obrigatorio"] is False
        assert item["ok"] is False  # não definido
        assert r["ready"] is True  # ausência de CLAUDE_PLUGIN_ROOT não impede READY


def test_claude_plugin_root_presente_e_so_informativo(monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(BASE))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, modelo_path = _ambiente_compativel(tmp)
        r = ede_doctor.executar_diagnostico(
            base=BASE, dir_saida=tmp / "saida",
            schema_path=schema_path, catalogo_path=catalogo_path, modelo_path=modelo_path)
        item = _item(r["checks"], "ambiente:CLAUDE_PLUGIN_ROOT")
        assert item["obrigatorio"] is False
        assert item["ok"] is True
        assert item["detalhe"] == str(BASE)


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        import inspect
        if "monkeypatch" in inspect.signature(t).parameters or "tmp_path" in inspect.signature(t).parameters:
            continue  # exigem fixture do pytest — só via `pytest`, não neste runner manual
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes executados (alguns exigem pytest, ver acima).")


if __name__ == "__main__":
    main()
