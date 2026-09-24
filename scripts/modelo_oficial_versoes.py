#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modelo_oficial_versoes.py — registro DETERMINÍSTICO das versões do
Modelo Oficial e do contrato (catálogo + manifesto) que acompanha cada
uma (Gate de ativação do Modelo Oficial V1 no homolog, ADR-0020).

O Modelo Oficial é asset privado externo (ADR-0009/ADR-0017): o runtime
nunca o descobre — só lê o objeto/geração configurados e confere o
SHA-256 pinado em `EDE_MODELO_OFICIAL_SHA256`. Este módulo usa ESSE
MESMO SHA pinado para escolher o contrato correspondente:

    SHA pinado conhecido  -> catálogo/manifesto daquela versão
    SHA pinado da versão legada, desconhecido ou ausente
                          -> contrato legado (templates/contestacao/
                             blocos.json, sem manifesto) — exatamente o
                             comportamento anterior a este gate; o
                             contrato continua sendo conferido contra os
                             bytes reais por `validar_contrato_modelo`,
                             então um arquivo que não bate com ele segue
                             NOT_READY, nunca "funciona por acaso".

Nenhuma variável nova de ambiente, nenhuma escolha do cliente MCP: a
versão é consequência do modelo que o titular provisionou e pinou.
Catálogo e manifesto de cada versão são fixados por SHA-256 aqui e
conferidos byte a byte na carga — divergência é fail-closed
(`IntegridadeVersaoModelo`), nunca um catálogo "parecido".
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIR_CONTESTACAO = BASE / "templates" / "contestacao"

ENV_MODELO_SHA256 = "EDE_MODELO_OFICIAL_SHA256"


class IntegridadeVersaoModelo(Exception):
    """Catálogo/manifesto da versão ausente, ilegível ou com SHA-256
    diferente do fixado aqui, ou manifesto que não aponta para o modelo/
    catálogo desta versão. Sempre defeito do próprio pacote do plugin,
    nunca do cliente."""


@dataclass(frozen=True)
class VersaoModelo:
    """Contrato imutável de UMA versão do Modelo Oficial — environment-
    neutral (D2 do gate V1): nenhuma versão sabe em que ambiente está
    ativa. Ativação por ambiente é só configuração de deploy (o SHA
    pinado em `EDE_MODELO_OFICIAL_SHA256` + objeto/geração GCS)."""

    versao_id: str
    status: str
    modelo_sha256: str | None
    catalogo_path: Path
    catalogo_sha256: str | None
    manifesto_path: Path | None = None
    manifesto_sha256: str | None = None
    placeholder_bloco_dono_extra: dict = field(default_factory=dict)
    """Placeholders que o contrato legado trata como sempre visíveis e
    que nesta versão passaram a viver dentro de um subbloco condicional
    (ex.: V1 moveu `FOTOS_DA_IRREGULARIADE` para
    `SUBBLOCO_REGISTRO_FOTOGRAFICO`). Só alteram a exigência de
    produção-final e o conjunto alcançável do round-trip."""

    @property
    def usa_topic_matrix(self) -> bool:
        return self.manifesto_path is not None


VERSAO_LEGADA = VersaoModelo(
    versao_id="legado",
    status="LEGADO",
    modelo_sha256="53adf880cb35a016986f482d6d9bc609118951b9684b77d413fae12a611104d8",
    catalogo_path=DIR_CONTESTACAO / "blocos.json",
    catalogo_sha256=None,
)
"""Contrato vigente em produção antes deste gate. `catalogo_sha256=None`
de propósito: o catálogo legado continua sendo o arquivo editável do
plugin local (Skill `contestacao`), já protegido pela suíte existente."""

VERSAO_V1 = VersaoModelo(
    versao_id="v1",
    status="APROVADO",
    modelo_sha256="1e2aa2a52c3341e680acd674658b41c27004a27f5f99c7343643d4d254747a9e",
    catalogo_path=DIR_CONTESTACAO / "v1" / "blocos.json",
    catalogo_sha256="3d710366ab4b06a223712c304ebfb3cfef9ea9206ff025dcd6eb8f973d7b2ac2",
    # Manifesto 1.1.0 (ADR-0021): arquivo NOVO; o 1.0.0 (`manifesto.json`,
    # f703966d…0414a5b) fica preservado sem edição, como exige a ADR-0020.
    manifesto_path=DIR_CONTESTACAO / "v1" / "manifesto-1.1.0.json",
    manifesto_sha256="42308f8a3f7c52461b0094979426e67fcdb577629fd7683e6d48d048c37c28d6",
    placeholder_bloco_dono_extra={"FOTOS_DA_IRREGULARIADE": "SUBBLOCO_REGISTRO_FOTOGRAFICO"},
)

VERSOES_POR_SHA: dict[str, VersaoModelo] = {
    VERSAO_LEGADA.modelo_sha256: VERSAO_LEGADA,
    VERSAO_V1.modelo_sha256: VERSAO_V1,
}


def resolver_versao(modelo_sha256: str | None) -> VersaoModelo:
    if not modelo_sha256:
        return VERSAO_LEGADA
    return VERSOES_POR_SHA.get(modelo_sha256.strip().lower(), VERSAO_LEGADA)


def resolver_versao_do_ambiente(env=None) -> VersaoModelo:
    env = os.environ if env is None else env
    return resolver_versao(env.get(ENV_MODELO_SHA256))


def _sha256_arquivo(caminho: Path) -> str:
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError as e:
        raise IntegridadeVersaoModelo(f"arquivo de contrato ausente/ilegível: {caminho.name}") from e


def verificar_integridade(versao: VersaoModelo) -> None:
    """Confere catálogo e manifesto contra os SHA-256 fixados e, no
    manifesto, a amarração modelo/catálogo. Levanta
    `IntegridadeVersaoModelo` em qualquer divergência."""
    if versao.catalogo_sha256 is not None:
        if _sha256_arquivo(versao.catalogo_path) != versao.catalogo_sha256:
            raise IntegridadeVersaoModelo(f"catálogo da versão {versao.versao_id} diverge do SHA-256 fixado")
    if versao.manifesto_path is None:
        return
    if _sha256_arquivo(versao.manifesto_path) != versao.manifesto_sha256:
        raise IntegridadeVersaoModelo(f"manifesto da versão {versao.versao_id} diverge do SHA-256 fixado")
    manifesto = json.loads(versao.manifesto_path.read_text(encoding="utf-8"))
    modelo = manifesto.get("modelo_oficial") or {}
    if modelo.get("sha256") != versao.modelo_sha256:
        raise IntegridadeVersaoModelo("manifesto não aponta para o Modelo Oficial desta versão")
    if modelo.get("catalogo_sha256") != versao.catalogo_sha256:
        raise IntegridadeVersaoModelo("manifesto não aponta para o catálogo desta versão")


def carregar_manifesto(versao: VersaoModelo) -> dict | None:
    """Manifesto já conferido por `verificar_integridade`; `None` para a
    versão legada (sem Topic Matrix)."""
    verificar_integridade(versao)
    if versao.manifesto_path is None:
        return None
    return json.loads(versao.manifesto_path.read_text(encoding="utf-8"))


def descrever_versao(versao: VersaoModelo) -> str:
    """Rótulo público e seguro para `ede_health`: identifica versão,
    catálogo e manifesto (arquivos públicos do plugin) — nunca o SHA do
    Modelo Oficial, nunca bucket/objeto/geração."""
    partes = [f"versão do modelo: {versao.versao_id}"]
    if versao.catalogo_sha256:
        partes.append(f"catálogo sha256={versao.catalogo_sha256}")
    if versao.manifesto_sha256:
        manifesto = json.loads(versao.manifesto_path.read_text(encoding="utf-8"))
        partes.append(f"manifesto {manifesto.get('manifesto_versao')} sha256={versao.manifesto_sha256}")
    return "; ".join(partes)
