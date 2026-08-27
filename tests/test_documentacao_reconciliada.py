#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guardas dos contratos documentais reconciliados após a auditoria."""

import json
import re
from pathlib import Path


BASE = Path(__file__).parent.parent
PENDENCIAS = BASE / "docs" / "PENDENCIAS.md"
SCHEMA = BASE / "templates" / "contestacao" / "schema.json"
CONTESTACAO_SKILL = BASE / "skills" / "contestacao" / "SKILL.md"
README = BASE / "README.md"


def _texto(path: Path) -> str:
    assert path.exists(), f"{path} não existe"
    return path.read_text(encoding="utf-8")


def _secao_pendencia(texto: str, pendencia: str) -> str:
    padrao = rf"^## {re.escape(pendencia)}\b.*?(?=\n---\n|\Z)"
    match = re.search(padrao, texto, flags=re.M | re.S)
    assert match, f"seção {pendencia} não encontrada"
    return match.group(0)


def _status_tabela(texto: str, pendencia: str) -> str:
    match = re.search(
        rf"^\| {re.escape(pendencia)} \|\s*([^|]+?)\s*\|",
        texto,
        flags=re.M,
    )
    assert match, f"status de {pendencia} não encontrado na tabela"
    return match.group(1).strip()


def test_pend_006_esta_resolvida_sem_fechamento_contraditorio():
    texto = _texto(PENDENCIAS)
    secao = _secao_pendencia(texto, "PEND-006")

    assert _status_tabela(texto, "PEND-006").startswith("RESOLVIDA")
    assert "**Status:** RESOLVIDA" in secao
    assert "Em aberto" not in secao
    assert "placeholder que aparecia duas vezes" not in secao


def test_pend_005_permanece_aberta_so_para_migracao_nativa():
    texto = _texto(PENDENCIAS)
    secao = _secao_pendencia(texto, "PEND-005")

    assert _status_tabela(texto, "PEND-005") == "ABERTA"
    assert "docx_numeracao_engine.py" in secao
    assert "INV-NUMERACAO-DINAMICA-CONTESTACAO" in secao
    assert "não renumera automaticamente" not in secao
    assert "sem tentar renumerar" not in secao
    assert "saltos visíveis" not in secao


def test_pend_003_distingue_tamanho_de_compatibilidade_do_rag():
    texto = _texto(PENDENCIAS)
    secao = _secao_pendencia(texto, "PEND-003")

    assert _status_tabela(texto, "PEND-003") == "ABERTA"
    assert "81 MB" in secao
    assert "ADR-0011" in secao
    assert "runtime" in secao.lower()


def test_contagem_de_placeholders_e_consistente_entre_contratos():
    schema = json.loads(_texto(SCHEMA))
    skill = _texto(CONTESTACAO_SKILL)
    quantidade = len(schema["editable_placeholders"])

    assert quantidade == 13
    assert len(schema["placeholder_contracts"]) == quantidade
    assert f"Geração dos {quantidade} placeholders" in skill
    assert f"Contrato semântico dos {quantidade} placeholders" in schema[
        "_nota_placeholder_contracts"
    ]


def test_readme_nao_trata_sincronismo_do_cowork_como_homologacao():
    texto = _texto(README).lower().replace("*", "")

    assert "cowork" in texto
    assert "não foi\nhomologado de ponta a ponta" in texto
    assert "synced" in texto
    assert "não comprova" in texto
