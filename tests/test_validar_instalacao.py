#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validar_instalacao.py — Fase 8: regressão de
scripts/validar_instalacao.py, incluindo o caso fail-closed (§35:
atualização/instalação incompleta não pode ser reportada como sucesso).

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.
"""
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from validar_instalacao import SKILLS_ESSENCIAIS, validar_instalacao  # noqa: E402


def test_instalacao_atual_do_repositorio_passa():
    # "instalação limpa" simulada: valida o próprio checkout do repositório
    # (equivalente ao que uma instalação via marketplace entregaria, já
    # que o source do plugin é a raiz do repo).
    r = validar_instalacao(BASE)
    assert r["status"] == "OK", r["obrigatorias_falhando"]
    assert r["versao"], "versão não detectada"


def test_falta_skill_obrigatoria_reporta_update_failed():
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "instalacao"
        # copia só o necessário para o teste ser rápido, sem rag/embeddings/
        # (pesado) — simula uma instalação incompleta de propósito, faltando
        # justamente as skills.
        (alvo / ".claude-plugin").mkdir(parents=True)
        (alvo / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "ede-legal-plugin", "version": "0.0.0-teste"}', encoding="utf-8")
        (alvo / "VERSION").write_text("0.0.0-teste", encoding="utf-8")
        (alvo / "templates" / "contestacao").mkdir(parents=True)
        (alvo / "templates" / "contestacao" / "schema.json").write_text("{}", encoding="utf-8")
        (alvo / "rag").mkdir()
        (alvo / "rag" / "config.yaml").write_text("x: 1", encoding="utf-8")
        (alvo / "rag" / "index_artigos.json").write_text("{}", encoding="utf-8")
        # nenhuma skill copiada de propósito

        r = validar_instalacao(alvo)
        assert r["status"] == "UPDATE_FAILED"
        assert len(r["obrigatorias_falhando"]) == len(SKILLS_ESSENCIAIS)


def test_template_institucional_ausente_nao_falha_instalacao():
    # o .docx real é asset privado (ADR-0006) — instalação do plugin
    # público não pode depender dele para reportar sucesso. Fixture
    # mínima (não copia rag/embeddings/ pesado) com tudo obrigatório
    # presente, exceto o .docx institucional.
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "instalacao"
        for nome in SKILLS_ESSENCIAIS:
            (alvo / "skills" / nome).mkdir(parents=True)
            (alvo / "skills" / nome / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        (alvo / ".claude-plugin").mkdir(parents=True)
        (alvo / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "ede-legal-plugin", "version": "0.0.0-teste"}', encoding="utf-8")
        (alvo / "VERSION").write_text("0.0.0-teste", encoding="utf-8")
        (alvo / "templates" / "contestacao").mkdir(parents=True)
        (alvo / "templates" / "contestacao" / "schema.json").write_text("{}", encoding="utf-8")
        # modelo-oficial.docx deliberadamente NÃO criado
        (alvo / "rag").mkdir()
        (alvo / "rag" / "config.yaml").write_text("x: 1", encoding="utf-8")
        (alvo / "rag" / "index_artigos.json").write_text("{}", encoding="utf-8")

        r = validar_instalacao(alvo)
        item_template = next(c for c in r["checagens"]
                              if c["item"].startswith("template:modelo-oficial.docx"))
        assert item_template["ok"] is False
        assert item_template["obrigatorio"] is False
        # e mesmo assim, com tudo o resto presente, o status geral é OK
        assert r["status"] == "OK", r["obrigatorias_falhando"]


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
