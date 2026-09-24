#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round-trip com VÁRIOS placeholders no mesmo parágrafo (gate V1): a âncora
exige, na ordem, todos os segmentos fixos e uma captura por ocorrência.
Defeito anterior (reproduzido no Modelo Oficial atual e na V1): todo o
miolo entre o 1º e o último placeholder era atribuído ao 1º, e o 2º nunca
era localizado — tópico 2.4 sempre ROUND_TRIP_FAILED (fail-closed).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "tests"))

import docx_block_engine as be  # noqa: E402
import docx_round_trip as rt  # noqa: E402
import finalizar_peca as fp  # noqa: E402
from docx_package import extrair_pacote_docx  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CAT_VAZIO = {"blocks": [], "zones": []}


def _doc(*paragrafos: str) -> str:
    corpo = "".join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragrafos)
    return f'<w:document xmlns:w="{W}"><w:body>{corpo}</w:body></w:document>'


TEMPLATE = _doc("Início fixo.", "A conta {{X}} (meio + fixo [1]) pertence a {{Y}}, fim.", "Outro {{Z}} só.")
ORIGINAL = {"X": "123", "Y": "FULANO", "Z": "valor z"}


def _gerado(x="123", meio="(meio + fixo [1])", y="FULANO", fim=", fim.", z="valor z"):
    return _doc("Início fixo.", f"A conta {x} {meio} pertence a {y}{fim}", f"Outro {z} só.")


def _divergencias(gerado_xml, original=ORIGINAL):
    extraido = rt.extrair_valores_gerados(TEMPLATE, gerado_xml, CAT_VAZIO, {}, {}, nomes=list(original))
    return rt.comparar_round_trip(original, extraido, set(original))


def test_dois_placeholders_mesmo_paragrafo_capturados_em_ordem():
    extraido = rt.extrair_valores_gerados(TEMPLATE, _gerado(), CAT_VAZIO, {}, {}, nomes=list(ORIGINAL))
    assert extraido == ORIGINAL
    assert _divergencias(_gerado()) == []


def test_primeiro_valor_alterado_falha():
    assert _divergencias(_gerado(x="999"))


def test_segundo_valor_alterado_falha():
    assert _divergencias(_gerado(y="CICLANO"))


def test_texto_fixo_intermediario_alterado_falha():
    d = _divergencias(_gerado(meio="(meio alterado)"))
    assert any("X" in x and "âncora" in x for x in d) and any("Y" in x and "âncora" in x for x in d)


def test_valores_invertidos_falham():
    assert _divergencias(_gerado(x="FULANO", y="123"))


def test_conteudo_residual_no_fim_falha():
    assert _divergencias(_gerado(fim=", fim. EXTRA"))


def test_placeholder_ausente_falha():
    gerado = _doc("Início fixo.", "A conta 123 pertence a FULANO, fim.", "Outro valor z só.")
    assert _divergencias(gerado)


def test_caso_de_um_placeholder_continua_igual():
    assert rt.extrair_valores_gerados(TEMPLATE, _gerado(), CAT_VAZIO, {}, {}, nomes=["Z"]) == {"Z": "valor z"}
    assert _divergencias(_gerado(z="outro"))


# ====================================================== modelos reais (2.4)

import test_topic_matrix_v1 as T  # noqa: E402

MODELO_ATUAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"


class _Transporte:
    def enviar(self, *a):
        pass

    def excluir(self, *a):
        return True

    def listar(self, *a):
        return []


def _preparar(monkeypatch, caminho: Path, sha_exigido: str | None = None):
    if not caminho.is_file():
        pytest.skip(f"{caminho} não instalado localmente — asset institucional externo (ADR-0009).")
    sha = hashlib.sha256(caminho.read_bytes()).hexdigest()
    if sha_exigido and sha != sha_exigido:
        pytest.fail(f"Modelo local com SHA-256 {sha} diferente do aprovado {sha_exigido}.")
    for var in ("EDE_MODELO_OFICIAL_GCS_BUCKET", "EDE_MODELO_OFICIAL_GCS_OBJECT", "EDE_MODELO_OFICIAL_GCS_GENERATION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("EDE_MODELO_OFICIAL_PATH", str(caminho))
    monkeypatch.setenv("EDE_MODELO_OFICIAL_SHA256", sha)
    monkeypatch.setattr(fp, "_obter_transporte_artefato", lambda: _Transporte())
    monkeypatch.setattr(fp, "_obter_base_url_download", lambda: "https://ede.example.test")


def _xml(caminho_ou_bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        docx = Path(tmp) / "d.docx"
        docx.write_bytes(caminho_ou_bytes if isinstance(caminho_ou_bytes, bytes) else caminho_ou_bytes.read_bytes())
        extrair_pacote_docx(docx, Path(tmp) / "u")
        return (Path(tmp) / "u" / "word" / "document.xml").read_text(encoding="utf-8")


def _checar_adulteracoes(template_xml, gerado_xml, catalogo, estados):
    dados = T._placeholders()
    nomes = ["CONTA_CONTRATO", "NOME_TITULAR_DA_UC"]
    extraido = rt.extrair_valores_gerados(template_xml, gerado_xml, catalogo, estados, {}, nomes=nomes)
    original = {n: dados[n] for n in nomes}
    assert rt.comparar_round_trip(original, extraido, set(nomes)) == []
    for adulterado in ({**original, "CONTA_CONTRATO": "1111111111"},
                       {**original, "NOME_TITULAR_DA_UC": "OUTRA PESSOA"},
                       {"CONTA_CONTRATO": original["NOME_TITULAR_DA_UC"],
                        "NOME_TITULAR_DA_UC": original["CONTA_CONTRATO"]}):
        assert rt.comparar_round_trip(adulterado, extraido, set(nomes))


@pytest.mark.docx_real
def test_modelo_atual_ilegitimidade_ativa_renderiza_e_passa_round_trip(monkeypatch):
    _preparar(monkeypatch, MODELO_ATUAL)
    catalogo = json.loads((BASE / "templates" / "contestacao" / "blocos.json").read_text(encoding="utf-8"))
    decisoes = {b["id"]: "EXCLUIR" for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    fatos = {"UC_TITULARIDADE_TERCEIRO_COMPROVADA": True}
    r = fp.finalizar_peca({"capability_id": T.CAP, "placeholders": T._placeholders(),
                           "block_decisions": decisoes, "estado_processual": fatos})
    assert r.status == "OK", (r.stage, r.error_code, r.motivo)
    estados = be.validar_e_resolver_decisoes(catalogo, {k: {"decisao": v} for k, v in decisoes.items()}, fatos)
    assert estados["PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO"] == "INCLUIR"
    _checar_adulteracoes(_xml(MODELO_ATUAL), _xml(r.documento_bytes), catalogo, estados)


@pytest.mark.docx_real
def test_v1_ilegitimidade_ativa_renderiza_e_passa_round_trip(monkeypatch):
    caminho = BASE / "templates" / "contestacao" / "v1" / "modelo-oficial.docx"
    _preparar(monkeypatch, caminho, T.V1.modelo_sha256)
    topicos = {**T._todos("NAO"), "ilegitimidade_ativa_titularidade": "SIM"}
    fatos = {"UC_TITULARIDADE_TERCEIRO_COMPROVADA": True}
    r = fp.finalizar_peca({"capability_id": T.CAP, "placeholders": T._placeholders(), "topicos": topicos,
                           "fatos_publicos": {"corte_efetivo": "NAO"}, "estado_processual": fatos})
    assert r.status == "OK", (r.stage, r.error_code, r.motivo, r.pendencias)
    trad = T.tm.traduzir(T.MANIFESTO, T.CATALOGO, topicos, {"corte_efetivo": "NAO"}, fatos)
    estados = be.validar_e_resolver_decisoes(
        T.CATALOGO, {k: {"decisao": v} for k, v in trad.block_decisions.items()}, trad.estado_processual_motor)
    assert estados["PRELIMINAR_ILEGITIMIDADE_ATIVA_TERCEIRO"] == "INCLUIR"
    _checar_adulteracoes(_xml(caminho), _xml(r.documento_bytes), T.CATALOGO, estados)
