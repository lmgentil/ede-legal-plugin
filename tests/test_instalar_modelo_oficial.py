#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_instalar_modelo_oficial.py — bootstrap do Modelo Oficial (Etapa
5.10, Commit 6: "feat(plugin): adicionar bootstrap do modelo oficial e
ede doctor").

Todos os cenários mecânicos (arquivo ausente/extensão inválida/ZIP
inválido/estrutura incompleta/contrato incompatível/instalação atômica)
usam um par SCHEMA/CATALOGO sintético mínimo próprio deste arquivo — não
o schema.json/blocos.json reais (19 placeholders, 18 blocos, 5 zonas
seria peso desnecessário só para exercitar os ramos de
`validar_contrato_modelo`). A compatibilidade total contra o contrato
REAL (schema.json/blocos.json versionados no git + modelo-oficial.docx
privado) é coberta à parte, por um único teste `docx_real` — mesmo
padrão recomendado no pedido: "Preferir DOCX sintético quando possível;
para validação completa do contrato, pode existir teste de integração
com modelo real, marcado docx_real".

Uso:
  python tests/test_instalar_modelo_oficial.py
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from instalar_modelo_oficial import (  # noqa: E402
    MOTIVO_ARQUIVO_NAO_ENCONTRADO,
    MOTIVO_EXTENSAO_INVALIDA,
    MOTIVO_MODELO_DESATUALIZADO,
    MOTIVO_MODELO_INVALIDO,
    instalar_modelo_oficial,
    validar_contrato_modelo,
)
from docx_package import extrair_pacote_docx  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"

pytestmark_real = pytest.mark.docx_real

# --------------------------------------------------------------- fixtures sintéticas
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

# Contrato sintético mínimo: um único placeholder (FOO) dentro de um único
# bloco condicional (BLOCO:FOO) — o suficiente para exercitar todos os
# ramos de validar_contrato_modelo sem replicar o catálogo real.
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


_CORPO_VALIDO = (
    b'<w:sdt><w:sdtPr><w:tag w:val="BLOCO:FOO"/></w:sdtPr>'
    b'<w:sdtContent><w:p><w:r><w:t>{{FOO}}</w:t></w:r></w:p></w:sdtContent></w:sdt>'
)
_CORPO_PLACEHOLDER_FALTANTE = (
    b'<w:sdt><w:sdtPr><w:tag w:val="BLOCO:FOO"/></w:sdtPr>'
    b'<w:sdtContent><w:p><w:r><w:t>sem token nenhum aqui</w:t></w:r></w:p></w:sdtContent></w:sdt>'
)
_CORPO_PLACEHOLDER_INESPERADO = (
    b'<w:sdt><w:sdtPr><w:tag w:val="BLOCO:FOO"/></w:sdtPr>'
    b'<w:sdtContent><w:p><w:r><w:t>{{FOO}}</w:t></w:r></w:p></w:sdtContent></w:sdt>'
    b'<w:p><w:r><w:t>{{BAR}}</w:t></w:r></w:p>'
)
_CORPO_SDT_AUSENTE = b'<w:p><w:r><w:t>{{FOO}}</w:t></w:r></w:p>'  # placeholder presente, SDT nao


def _zip_com_partes(destino: Path, partes: dict) -> Path:
    """Mesma técnica de tests/test_docx_package.py e
    tests/test_fail_closed_docx_package.py — zipfile puro, independente do
    código sob teste."""
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in partes.items():
            zf.writestr(nome, conteudo)
    return destino


def _partes_minimas(corpo_bytes: bytes) -> dict:
    return {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _RELS_RAIZ,
        "word/document.xml": _document_xml(corpo_bytes),
    }


def _escrever_json(caminho: Path, dado: dict) -> Path:
    caminho.write_text(json.dumps(dado, ensure_ascii=False), encoding="utf-8")
    return caminho


def _preparar_ambiente(tmp: Path):
    """(schema_path, catalogo_path, destino) prontos para
    instalar_modelo_oficial() com o contrato sintético mínimo."""
    schema_path = _escrever_json(tmp / "schema.json", SCHEMA_MINIMO)
    catalogo_path = _escrever_json(tmp / "blocos.json", CATALOGO_MINIMO)
    destino = tmp / "instalado" / "modelo-oficial.docx"
    return schema_path, catalogo_path, destino


# --------------------------------------------------------------- item 1/2: input básico
def test_arquivo_inexistente_e_rejeitado_sem_tocar_destino():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        r = instalar_modelo_oficial(tmp / "nao_existe.docx", destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_ARQUIVO_NAO_ENCONTRADO
        assert not destino.exists()


def test_extensao_invalida_e_rejeitada():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.pdf"
        origem.write_bytes(b"conteudo irrelevante, extensao errada")
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_EXTENSAO_INVALIDA
        assert not destino.exists()


# --------------------------------------------------------------- item 3/4: pacote inválido/incompleto
def test_zip_invalido_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        origem.write_bytes(b"isto nao e um zip valido")
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_MODELO_INVALIDO
        assert not destino.exists()


def test_estrutura_ooxml_incompleta_e_rejeitada():
    """word/document.xml ausente (Content_Types/.rels presentes — o ZIP em
    si é um pacote OPC minimamente válido, mas incompleto para o contrato
    de Contestação): extrair_pacote_docx sucede, validar_estrutura_minima
    (dentro de validar_contrato_modelo) detecta a parte obrigatória
    ausente."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, {
            "[Content_Types].xml": _CONTENT_TYPES,
            "_rels/.rels": _RELS_RAIZ,
        })
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_MODELO_DESATUALIZADO
        assert any("word/document.xml" in d for d in r["divergencias"])
        assert not destino.exists()


# --------------------------------------------------------------- item: contrato incompatível
def test_placeholder_faltante_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_PLACEHOLDER_FALTANTE))
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_MODELO_DESATUALIZADO
        assert any("{{FOO}}" in d and "ausente" in d for d in r["divergencias"])
        assert not destino.exists()


def test_placeholder_inesperado_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_PLACEHOLDER_INESPERADO))
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_MODELO_DESATUALIZADO
        assert any("{{BAR}}" in d and "sem entrada no schema" in d for d in r["divergencias"])
        assert not destino.exists()


def test_sdt_obrigatorio_faltante_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_SDT_AUSENTE))
        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r["status"] == "REJEITADO"
        assert r["motivo"] == MOTIVO_MODELO_DESATUALIZADO
        assert any("tag_ausente" in d and "BLOCO:FOO" in d for d in r["divergencias"])
        assert not destino.exists()


# --------------------------------------------------------------- instalação válida / atômica
def test_instalacao_valida_grava_e_registra_auditoria():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_VALIDO))

        r = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)

        assert r["status"] == "INSTALADO"
        assert r["divergencias"] == []
        assert destino.is_file()
        assert destino.read_bytes() == origem.read_bytes()

        auditoria = r["auditoria"]
        import hashlib
        assert auditoria["hash_sha256"] == hashlib.sha256(origem.read_bytes()).hexdigest()
        assert auditoria["schema_versao"] == "9.9.9-teste"
        assert auditoria["catalogo_versao"] == "9.9.9-teste"
        assert "plugin_versao" in auditoria

        # item 4: substituição atômica — nenhum .tmp residual
        assert not destino.with_name(destino.name + ".tmp").exists()
        assert list(destino.parent.iterdir()) == [destino]


def test_instalacao_e_hash_estavel_para_o_mesmo_arquivo():
    """Duas instalações do mesmo arquivo produzem o mesmo hash — o hash é
    do conteúdo instalado, não de um timestamp/nonce (item 5)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_VALIDO))

        r1 = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        r2 = instalar_modelo_oficial(origem, destino, schema_path, catalogo_path)
        assert r1["auditoria"]["hash_sha256"] == r2["auditoria"]["hash_sha256"]


def test_modelo_anterior_preservado_quando_nova_instalacao_falha():
    """Item 4/item 11 do pedido: um modelo válido já instalado nunca é
    substituído por um arquivo que não passou por todas as validações —
    nem parcialmente, nem por um instante."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        schema_path, catalogo_path, destino = _preparar_ambiente(tmp)

        origem_valida = tmp / "modelo_valido.docx"
        _zip_com_partes(origem_valida, _partes_minimas(_CORPO_VALIDO))
        r1 = instalar_modelo_oficial(origem_valida, destino, schema_path, catalogo_path)
        assert r1["status"] == "INSTALADO"
        conteudo_anterior = destino.read_bytes()

        origem_incompativel = tmp / "modelo_incompativel.docx"
        _zip_com_partes(origem_incompativel, _partes_minimas(_CORPO_PLACEHOLDER_FALTANTE))
        r2 = instalar_modelo_oficial(origem_incompativel, destino, schema_path, catalogo_path)
        assert r2["status"] == "REJEITADO"

        assert destino.read_bytes() == conteudo_anterior
        assert not destino.with_name(destino.name + ".tmp").exists()


# --------------------------------------------------------------- validar_contrato_modelo isolado
def test_validar_contrato_modelo_retorna_lista_vazia_para_pacote_compativel():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        origem = tmp / "modelo.docx"
        _zip_com_partes(origem, _partes_minimas(_CORPO_VALIDO))
        pacote_dir = tmp / "unpacked"
        extrair_pacote_docx(origem, pacote_dir)
        assert validar_contrato_modelo(pacote_dir, SCHEMA_MINIMO, CATALOGO_MINIMO) == []


# --------------------------------------------------------------- docx_real: contrato real completo
@pytest.mark.docx_real
def test_modelo_oficial_real_instala_com_contrato_atual_compativel():
    """Único teste de integração deste arquivo contra o par real
    schema.json/blocos.json/modelo-oficial.docx — nunca escreve no destino
    versionado, só num diretório temporário."""
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "modelo-oficial.docx"
        r = instalar_modelo_oficial(TEMPLATE_REAL, destino, SCHEMA_REAL, CATALOGO_REAL)
        assert r["status"] == "INSTALADO", r
        assert r["divergencias"] == []
        assert destino.read_bytes() == TEMPLATE_REAL.read_bytes()


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        if getattr(t, "pytestmark", None):
            continue  # docx_real — só via pytest, com skip explícito
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes executados.")


if __name__ == "__main__":
    main()
