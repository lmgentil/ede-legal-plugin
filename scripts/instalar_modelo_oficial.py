#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
instalar_modelo_oficial.py — bootstrap do Modelo Oficial da Contestação
(Etapa 5.10, Commit 6, ADR-0014/PEND-007).

O Modelo Oficial (`templates/contestacao/modelo-oficial.docx`) continua
FORA DO GIT (ADR-0009, CLAUDE.md §13) — este script é o único caminho
suportado para instalá-lo localmente a partir de um arquivo fornecido
explicitamente pelo advogado. Nunca procura automaticamente em
Downloads/Desktop/etc.; nunca baixa, reconstrói ou adivinha o arquivo.

Host-agnostic (mesma regra de portabilidade de `docx_package.py`,
ADR-0014): nenhuma dependência de Claude Code (`CLAUDE_PLUGIN_ROOT`,
`SKILL.md`, `~/.claude`, `~/.agents`), OpenAI, Apps SDK ou MCP. Toda
entrada é um `Path` explícito.

Fluxo (fail-closed em cada etapa, nunca instala parcialmente):
    1. confirma que a origem existe e tem extensão .docx;
    2. abre como pacote OOXML via docx_package.extrair_pacote_docx
       (runtime próprio do EDE — nunca skills/docx/);
    3. valida a estrutura mínima do pacote (docx_package.validar_estrutura_minima);
    4. valida o CONTRATO institucional do template — placeholders físicos
       batendo com schema.json, SDTs de bloco/zona batendo com blocos.json
       (reaproveita docx_template_engine.extrair_placeholders e
       docx_block_engine.validar_sdts_contra_catalogo — nenhum parser/regex
       novo é criado aqui só para isso);
    5. só então copia para o destino, de forma atômica (arquivo temporário
       no mesmo diretório + os.replace — nunca substitui um modelo válido
       já instalado por um arquivo que ainda não passou por 1-4).

O contrato NÃO usa SHA-256 como gate de compatibilidade — o hash do
arquivo instalado é calculado e devolvido só para fins de auditoria/
diagnóstico (ver `_registro_auditoria`), nunca para decidir se o arquivo
é aceito.

Uso:
  python scripts/instalar_modelo_oficial.py CAMINHO_DO_ARQUIVO
  python scripts/instalar_modelo_oficial.py CAMINHO_DO_ARQUIVO --json
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import lxml.etree as LET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    validar_catalogo,
    validar_sdts_contra_catalogo,
)
from docx_package import (  # noqa: E402
    PacoteDocxAbortada,
    extrair_pacote_docx,
    validar_estrutura_minima,
)
from docx_template_engine import carregar_schema, extrair_placeholders  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DESTINO_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

# Motivos de rejeição — vocabulário fechado, consumido por quem chama este
# módulo programaticamente (ex.: futura integração com ede_doctor.py) e
# pela saída --json. "MODELO_INSTITUCIONAL_DESATUALIZADO" reaproveita o
# mesmo rótulo já usado por docx_block_engine._validar_zonas_contra_template
# para o caso específico de zona ausente — generalizado aqui para qualquer
# divergência de contrato (placeholder/SDT/zona), nunca um "tag_ausente"
# cru chegando ao advogado.
MOTIVO_ARQUIVO_NAO_ENCONTRADO = "ARQUIVO_NAO_ENCONTRADO"
MOTIVO_EXTENSAO_INVALIDA = "EXTENSAO_INVALIDA"
MOTIVO_MODELO_INVALIDO = "MODELO_INSTITUCIONAL_INVALIDO"
MOTIVO_MODELO_DESATUALIZADO = "MODELO_INSTITUCIONAL_DESATUALIZADO"


def validar_contrato_modelo(pacote_dir: Path, schema: dict, catalogo: dict) -> list:
    """Confere o pacote OOXML já extraído (`pacote_dir`) contra o contrato
    institucional vigente (schema.json + blocos.json). Retorna lista de
    divergências (vazia = compatível) — nunca levanta exceção para
    incompatibilidade esperada de input, mesmo padrão de
    `docx_package.validar_estrutura_minima`.

    Reaproveita integralmente funções já existentes e testadas, sem
    duplicar parser/regex:
      - `docx_package.validar_estrutura_minima` — partes OPC/OOXML mínimas
        + boa-formação XML (itens A/B/C/G do pedido);
      - `docx_template_engine.extrair_placeholders` — placeholders físicos
        do documento, mesma regex usada pelo motor de geração real (item D);
      - `docx_block_engine.validar_sdts_contra_catalogo` — SDTs de bloco/
        zona contra o catálogo, incluindo token de zona isolado/único/
        bloco-pai correto (itens E/F/G — mesma função usada por
        `compor_xml` no caminho de geração real)."""
    divergencias = list(validar_estrutura_minima(pacote_dir))
    if divergencias:
        # sem document.xml íntegro/bem-formado, nada mais é verificável
        return divergencias

    document_xml = (pacote_dir / "word" / "document.xml").read_text(encoding="utf-8")

    ids_zona = {z["id"] for z in catalogo.get("zones", [])}
    esperados = set(schema.get("editable_placeholders", []))
    # token de zona casa com a mesma regex de placeholder ({{...}}) — não é
    # placeholder do schema, então é excluído antes da comparação (mesma
    # distinção já feita por docx_context_engine.extrair_contexto).
    fisicos = extrair_placeholders(document_xml) - ids_zona

    for faltante in sorted(esperados - fisicos):
        divergencias.append(f"placeholder esperado pelo schema ausente no documento: {{{{{faltante}}}}}")
    for inesperado in sorted(fisicos - esperados):
        divergencias.append(f"placeholder presente no documento sem entrada no schema: {{{{{inesperado}}}}}")

    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)
    try:
        validar_sdts_contra_catalogo(root, catalogo)
    except ComposicaoAbortada as e:
        divergencias.append(f"{e.stage}: {e.motivo}")

    return divergencias


def _versao_plugin(base: Path) -> str:
    version_file = base / "VERSION"
    try:
        if version_file.exists():
            texto = version_file.read_text(encoding="utf-8").strip()
            if texto:
                return texto
    except OSError:
        pass
    return "sem versão explícita"


def _registro_auditoria(destino: Path, schema: dict, catalogo: dict) -> dict:
    """Hash + versões — SOMENTE para diagnóstico/auditoria (nunca gate de
    compatibilidade, ver docstring do módulo). Sem versionamento inventado:
    schema.json e blocos.json já declaram 'version' própria; quando um dos
    dois não declarar, registra o texto fixo abaixo em vez de um número
    fabricado."""
    return {
        "hash_sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
        "plugin_versao": _versao_plugin(BASE),
        "schema_versao": schema.get("version") or "sem versão explícita",
        "catalogo_versao": catalogo.get("version") or "sem versão explícita",
    }


def instalar_modelo_oficial(origem, destino=DESTINO_PADRAO,
                             schema_path=SCHEMA_PADRAO,
                             catalogo_path=CATALOGO_PADRAO) -> dict:
    """Instala `origem` em `destino` se, e somente se, passar por todas as
    validações (existência, extensão, pacote OOXML válido, contrato
    institucional). Instalação atômica: nada em `destino` é tocado antes da
    última etapa — falha em qualquer ponto anterior preserva o modelo
    atualmente instalado intacto (item 4 do pedido)."""
    origem = Path(origem)
    destino = Path(destino)

    if not origem.exists():
        return {"status": "REJEITADO", "motivo": MOTIVO_ARQUIVO_NAO_ENCONTRADO,
                "divergencias": [f"arquivo não encontrado: {origem}"]}
    if origem.suffix.lower() != ".docx":
        return {"status": "REJEITADO", "motivo": MOTIVO_EXTENSAO_INVALIDA,
                "divergencias": [f"extensão esperada '.docx', recebida: {origem.suffix!r}"]}

    schema = carregar_schema(schema_path)
    catalogo = carregar_catalogo(catalogo_path)
    validar_catalogo(catalogo)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pacote_dir = tmp / "unpacked"
        try:
            extrair_pacote_docx(origem, pacote_dir)
        except PacoteDocxAbortada as e:
            return {"status": "REJEITADO", "motivo": MOTIVO_MODELO_INVALIDO,
                    "divergencias": [e.motivo]}

        divergencias = validar_contrato_modelo(pacote_dir, schema, catalogo)
        if divergencias:
            return {"status": "REJEITADO", "motivo": MOTIVO_MODELO_DESATUALIZADO,
                    "divergencias": divergencias}

        # Só a partir daqui o destino é tocado — validar origem -> validar
        # contrato -> copiar para arquivo temporário no destino -> troca
        # atômica (item 4 do pedido).
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp_destino = destino.with_name(destino.name + ".tmp")
        try:
            shutil.copy2(origem, tmp_destino)
        except OSError:
            tmp_destino.unlink(missing_ok=True)
            raise
        os.replace(tmp_destino, destino)

    return {
        "status": "INSTALADO",
        "motivo": None,
        "divergencias": [],
        "destino": str(destino),
        "auditoria": _registro_auditoria(destino, schema, catalogo),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("origem", help="caminho do arquivo .docx fornecido pelo advogado")
    ap.add_argument("--destino", default=str(DESTINO_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--catalogo", default=str(CATALOGO_PADRAO))
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    try:
        resultado = instalar_modelo_oficial(args.origem, Path(args.destino),
                                             Path(args.schema), Path(args.catalogo))
    except (PacoteDocxAbortada, ComposicaoAbortada) as e:
        # Falha na leitura do próprio schema.json/blocos.json do plugin (não
        # do arquivo do advogado) — condição de instalação quebrada do
        # plugin em si, não "erro esperado de input" do modelo fornecido.
        resultado = {"status": "REJEITADO", "motivo": "INSTALACAO_PLUGIN_INVALIDA",
                     "divergencias": [f"{e.stage}: {e.motivo}"]}

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        if resultado["status"] == "INSTALADO":
            print(f"Modelo instalado com sucesso em: {resultado['destino']}")
            for chave, valor in resultado["auditoria"].items():
                print(f"  {chave}: {valor}")
        else:
            print(f"REJEITADO ({resultado['motivo']}):")
            for d in resultado["divergencias"]:
                print(f"  - {d}")

    sys.exit(0 if resultado["status"] == "INSTALADO" else 1)


if __name__ == "__main__":
    main()
