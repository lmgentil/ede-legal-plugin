#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_marketplace.py — Fase 8 (Distribuição): valida
.claude-plugin/marketplace.json e a sincronização de versão entre
VERSION, plugin.json e o manifesto do marketplace.

`claude plugin tag . --dry-run` é o mecanismo OFICIAL equivalente
(confirmado nesta fase: valida que plugin.json e a entrada do
marketplace concordam antes de liberar uma tag de release) — este
arquivo cobre o mesmo contrato como teste automatizado de repositório,
sem depender de rodar o CLI.

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
MARKETPLACE_PATH = BASE / ".claude-plugin" / "marketplace.json"
PLUGIN_PATH = BASE / ".claude-plugin" / "plugin.json"
VERSION_PATH = BASE / "VERSION"


def _marketplace() -> dict:
    return json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))


def _plugin() -> dict:
    return json.loads(PLUGIN_PATH.read_text(encoding="utf-8"))


def test_marketplace_json_parseavel():
    m = _marketplace()
    assert isinstance(m, dict)


def test_marketplace_campos_obrigatorios():
    m = _marketplace()
    assert m.get("name"), "marketplace precisa de 'name'"
    assert m.get("owner", {}).get("name"), "marketplace precisa de 'owner.name'"
    assert isinstance(m.get("plugins"), list) and m["plugins"], \
        "marketplace precisa de 'plugins' (lista não vazia)"


def test_marketplace_nome_e_identidade_preservados():
    # CLAUDE.md/SPEC não autorizam renomear o marketplace/plugin
    # silenciosamente — nomes conferidos contra a identidade já
    # consolidada em plugin.json (auditada antes de escrever o
    # marketplace, Fase 8 §11).
    m = _marketplace()
    assert m["name"] == "ede"
    nomes_plugins = [p["name"] for p in m["plugins"]]
    assert "ede-legal-plugin" in nomes_plugins  # nome já existente em plugin.json


def test_plugin_listado_tem_source_resolvivel():
    m = _marketplace()
    entrada = next(p for p in m["plugins"] if p["name"] == "ede-legal-plugin")
    assert "source" in entrada
    origem = (MARKETPLACE_PATH.parent.parent / entrada["source"]).resolve()
    assert origem.exists(), f"source do plugin não resolve para um caminho real: {entrada['source']}"
    assert (origem / ".claude-plugin" / "plugin.json").exists(), \
        "source do plugin não contém .claude-plugin/plugin.json"


def test_entrada_do_marketplace_nao_declara_version_propria():
    # Achado confirmado nesta fase: se marketplace.json e plugin.json
    # declararem 'version' cada um, o valor de plugin.json vence
    # silenciosamente — nunca fica claro qual foi usado. Única fonte:
    # plugin.json (que por sua vez é sincronizado com VERSION).
    m = _marketplace()
    entrada = next(p for p in m["plugins"] if p["name"] == "ede-legal-plugin")
    assert "version" not in entrada, \
        "entrada do marketplace não deve declarar 'version' própria — plugin.json é a fonte"


def test_version_sincronizada_entre_version_e_plugin_json():
    versao_arquivo = VERSION_PATH.read_text(encoding="utf-8").strip()
    versao_plugin = _plugin()["version"]
    assert versao_arquivo == versao_plugin, (
        f"VERSION ({versao_arquivo!r}) != plugin.json version ({versao_plugin!r}) "
        f"— fonte canônica é VERSION (SPEC-0001 Fase 8 §15); sincronize antes de commitar.")


def test_plugin_json_tem_identidade_minima():
    p = _plugin()
    for campo in ("name", "version", "description", "author"):
        assert p.get(campo), f"plugin.json sem campo '{campo}'"
    assert p["name"] == "ede-legal-plugin"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
