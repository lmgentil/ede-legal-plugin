#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_docx_package.py — regressão do runtime DOCX próprio do EDE (Etapa
5.10, ADR-0014, PEND-007).

Mesmo padrão de tests/test_docx_context_engine.py: sem framework de
teste, asserts + `if __name__ == "__main__"` (também coletável por
pytest, que já é dependência de desenvolvimento do projeto).

Todos os pacotes DOCX usados aqui são SINTÉTICOS, construídos com
`zipfile` da biblioteca padrão diretamente neste arquivo — nenhum teste
depende de `templates/contestacao/modelo-oficial.docx`, de `skills/docx/`,
do ambiente Claude Code ou de qualquer caminho do working tree do
desenvolvedor. Roda igual em clone limpo.

Uso:
  python tests/test_docx_package.py
"""
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from docx_package import (  # noqa: E402
    PacoteDocxAbortada,
    empacotar_pacote_docx,
    extrair_pacote_docx,
    validar_estrutura_minima,
)

# --------------------------------------------------------------- fixtures

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

_DOCUMENT_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b'<w:body><w:p><w:r><w:t>ola</w:t></w:r></w:p></w:body></w:document>'
)

_DOCUMENT_RELS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    b'Target="styles.xml"/></Relationships>'
)

_STYLES_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
)

# Binário arbitrário (não-texto, os 256 valores de byte possíveis
# repetidos) — parte de mídia sintética; não depende de um arquivo de
# imagem real, só precisa sobreviver ao round-trip sem alteração.
_MEDIA_BINARIA = bytes(range(256)) * 4


def _partes_minimas() -> dict:
    return {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _RELS_RAIZ,
        "word/document.xml": _DOCUMENT_XML,
        "word/_rels/document.xml.rels": _DOCUMENT_RELS,
        "word/styles.xml": _STYLES_XML,
        "word/media/image1.png": _MEDIA_BINARIA,
    }


def _criar_docx_sintetico(destino: Path, partes: dict, entradas_brutas=None) -> Path:
    """Constrói um .docx sintético em `destino` a partir de `partes`
    ({nome_no_zip: bytes}), usando `zipfile` diretamente — nunca
    `docx_package` (fixture de teste independente do código sob teste).

    `entradas_brutas`, se informado, é uma lista de
    (nome, conteudo, external_attr) para entradas que exigem controle
    fino sobre o ZipInfo (symlink, caminho perigoso) além de `partes`."""
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in partes.items():
            zf.writestr(nome, conteudo)
        for nome, conteudo, external_attr in (entradas_brutas or []):
            info = zipfile.ZipInfo(nome)
            info.external_attr = external_attr
            zf.writestr(info, conteudo)
    return destino


def _assert_aborta(chamavel, stage_esperado):
    try:
        chamavel()
    except PacoteDocxAbortada as e:
        assert e.stage == stage_esperado, f"stage {e.stage!r} != {stage_esperado!r} ({e.motivo})"
        return e
    raise AssertionError(f"deveria ter abortado com stage={stage_esperado!r}")


# --------------------------------------------------------------- extração: caminho feliz

def test_zip_valido_extrai_todas_as_partes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "modelo.docx", _partes_minimas())
        destino = tmp / "unpacked"
        extrair_pacote_docx(docx, destino)
        for nome in _partes_minimas():
            assert (destino / nome).is_file(), nome
        assert (destino / "word/document.xml").read_bytes() == _DOCUMENT_XML
        assert (destino / "word/media/image1.png").read_bytes() == _MEDIA_BINARIA


def test_validar_estrutura_minima_ok_para_pacote_valido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "valido.docx", _partes_minimas())
        destino = tmp / "unpacked"
        extrair_pacote_docx(docx, destino)
        assert validar_estrutura_minima(destino) == []


# --------------------------------------------------------------- extração: entrada inválida

def test_zip_corrompido_aborta_docx_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lixo = tmp / "nao_e_um_docx.docx"
        lixo.write_bytes(b"isto nao e um zip valido")
        _assert_aborta(lambda: extrair_pacote_docx(lixo, tmp / "unpacked"), "docx_invalido")


def test_arquivo_ausente_aborta_docx_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _assert_aborta(lambda: extrair_pacote_docx(tmp / "nao_existe.docx", tmp / "unpacked"), "docx_invalido")


def test_content_types_ausente_aborta_docx_invalido():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        del partes["[Content_Types].xml"]
        docx = _criar_docx_sintetico(tmp / "sem_content_types.docx", partes)
        e = _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")
        assert "Content_Types" in e.motivo


def test_document_xml_ausente_reportado_por_validar_estrutura_minima():
    """word/document.xml ausente não impede a EXTRAÇÃO (o pacote pode ser
    um ZIP/OPC válido sem ser especificamente um .docx utilizável) — é
    validar_estrutura_minima quem reporta a lacuna, separando "ZIP/OPC
    inválido" de "OPC válido mas sem a parte que este pipeline exige"."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        del partes["word/document.xml"]
        docx = _criar_docx_sintetico(tmp / "sem_document.docx", partes)
        destino = tmp / "unpacked"
        extrair_pacote_docx(docx, destino)
        problemas = validar_estrutura_minima(destino)
        assert any("word/document.xml" in p for p in problemas)


def test_xml_malformado_e_reportado_por_validar_estrutura_minima():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        partes["word/document.xml"] = b"<w:document><w:body><w:p>sem fechar as tags"
        docx = _criar_docx_sintetico(tmp / "malformado.docx", partes)
        destino = tmp / "unpacked"
        extrair_pacote_docx(docx, destino)  # extração não faz parsing XML — ver módulo
        problemas = validar_estrutura_minima(destino)
        assert any("malformado" in p for p in problemas)


def test_entidade_externa_no_xml_nao_e_resolvida_nem_derruba_a_validacao():
    """Confirma a decisão lxml x defusedxml registrada no módulo: um XML
    com DOCTYPE/entidade externa não é expandido nem causa acesso a
    arquivo/rede — resolve_entities=False mantém a entidade não
    resolvida, sem quebrar o parsing nem vazar conteúdo do sistema."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        partes["word/document.xml"] = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>'
        )
        docx = _criar_docx_sintetico(tmp / "xxe.docx", partes)
        destino = tmp / "unpacked"
        extrair_pacote_docx(docx, destino)
        problemas = validar_estrutura_minima(destino)
        assert isinstance(problemas, list)  # não trava, não levanta, não resolve a entidade


# --------------------------------------------------------------- extração: entrada perigosa

def test_zip_slip_com_dotdot_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "malicioso.docx", _partes_minimas(), entradas_brutas=[
            ("../fora_do_pacote.txt", b"conteudo malicioso", 0),
        ])
        alvo_externo = tmp.parent / "fora_do_pacote.txt"
        if alvo_externo.exists():
            alvo_externo.unlink()
        _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")
        assert not alvo_externo.exists(), "Zip Slip vazou para fora do diretório de destino"


def test_path_absoluto_posix_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "absoluto.docx", _partes_minimas(), entradas_brutas=[
            ("/etc/evil.txt", b"x", 0),
        ])
        _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")


def test_prefixo_de_unidade_windows_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "unidade.docx", _partes_minimas(), entradas_brutas=[
            ("C:/Windows/evil.txt", b"x", 0),
        ])
        _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")


def test_separador_windows_ambiguo_e_rejeitado():
    """Entrada com "\\" é rejeitada mesmo sem ".." explícito — em
    Windows, pathlib trataria "\\" como separador de diretório, o que
    tornaria uma checagem baseada só em PurePosixPath insuficiente
    nesse SO (ver docstring de _resolver_entrada_segura)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx = _criar_docx_sintetico(tmp / "backslash.docx", _partes_minimas(), entradas_brutas=[
            ("word\\..\\..\\evil.txt", b"x", 0),
        ])
        _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")


def test_symlink_e_rejeitado():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        modo_symlink = (stat.S_IFLNK | 0o777) << 16
        docx = _criar_docx_sintetico(tmp / "symlink.docx", _partes_minimas(), entradas_brutas=[
            ("word/evil_link", b"/etc/passwd", modo_symlink),
        ])
        _assert_aborta(lambda: extrair_pacote_docx(docx, tmp / "unpacked"), "docx_invalido")


def test_erro_e_deterministico_entre_chamadas():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lixo = tmp / "nao_e_um_docx.docx"
        lixo.write_bytes(b"lixo")
        stages = []
        for i in range(2):
            try:
                extrair_pacote_docx(lixo, tmp / f"unpacked_{i}")
            except PacoteDocxAbortada as e:
                stages.append(e.stage)
        assert stages == ["docx_invalido", "docx_invalido"]


# --------------------------------------------------------------- reempacotamento

def test_round_trip_preserva_conteudo_byte_a_byte():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        docx_original = _criar_docx_sintetico(tmp / "original.docx", partes)
        unpacked = tmp / "unpacked"
        extrair_pacote_docx(docx_original, unpacked)

        docx_saida = tmp / "saida.docx"
        empacotar_pacote_docx(unpacked, docx_saida)
        assert docx_saida.is_file()

        reunpacked = tmp / "reunpacked"
        extrair_pacote_docx(docx_saida, reunpacked)
        for nome, conteudo in partes.items():
            assert (reunpacked / nome).read_bytes() == conteudo, nome


def test_preservacao_byte_a_byte_de_partes_nao_alteradas():
    """Simula o uso real do pipeline: só word/document.xml é reescrito
    pelos motores do EDE entre extrair e empacotar; toda demais parte
    (relationships, styles, mídia binária) deve permanecer byte a byte
    idêntica ao original."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        partes = _partes_minimas()
        docx_original = _criar_docx_sintetico(tmp / "original.docx", partes)
        unpacked = tmp / "unpacked"
        extrair_pacote_docx(docx_original, unpacked)

        novo_document_xml = _DOCUMENT_XML.replace(b"ola", b"ola alterado")
        (unpacked / "word" / "document.xml").write_bytes(novo_document_xml)

        docx_saida = tmp / "saida.docx"
        empacotar_pacote_docx(unpacked, docx_saida)

        reunpacked = tmp / "reunpacked"
        extrair_pacote_docx(docx_saida, reunpacked)
        assert (reunpacked / "word" / "document.xml").read_bytes() == novo_document_xml
        for nome, conteudo in partes.items():
            if nome == "word/document.xml":
                continue
            assert (reunpacked / nome).read_bytes() == conteudo, f"parte não tocada divergiu: {nome}"


def test_empacotar_e_deterministico():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx_original = _criar_docx_sintetico(tmp / "original.docx", _partes_minimas())
        unpacked = tmp / "unpacked"
        extrair_pacote_docx(docx_original, unpacked)

        saida_a, saida_b = tmp / "saida_a.docx", tmp / "saida_b.docx"
        empacotar_pacote_docx(unpacked, saida_a)
        empacotar_pacote_docx(unpacked, saida_b)
        assert saida_a.read_bytes() == saida_b.read_bytes()


def test_empacotar_diretorio_inexistente_aborta():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _assert_aborta(
            lambda: empacotar_pacote_docx(tmp / "nao_existe", tmp / "saida.docx"),
            "docx_package_estrutura_incompleta",
        )


def test_empacotar_diretorio_vazio_aborta():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        vazio = tmp / "vazio"
        vazio.mkdir()
        _assert_aborta(
            lambda: empacotar_pacote_docx(vazio, tmp / "saida.docx"),
            "docx_package_estrutura_incompleta",
        )


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
