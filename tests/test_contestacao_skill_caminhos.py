#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressão da resolução de recursos em ``skills/contestacao/SKILL.md``.

O contrato do host substitui ``${CLAUDE_PLUGIN_ROOT}`` diretamente no
conteúdo da Skill. A Skill não pode tratar o token como variável de ambiente
do Bash/Python, pois esse ambiente não é o contrato da expansão. Arquivos do
caso continuam relativos ao workspace do advogado.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "contestacao" / "SKILL.md"
TOKEN_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalizado() -> str:
    return " ".join(_texto().split())


def _expandir_como_host(texto: str, root: str) -> str:
    return texto.replace(TOKEN_PLUGIN_ROOT, root)


def test_recursos_do_plugin_usam_token_de_expansao_inline_do_host():
    texto = _texto()

    assert TOKEN_PLUGIN_ROOT in texto
    assert "$CLAUDE_PLUGIN_ROOT" not in texto
    assert not re.search(r"os\.environ(?:\.get)?\s*[\[(].*CLAUDE_PLUGIN_ROOT", texto)


def test_expansao_inline_resolve_comando_fora_do_cwd_e_com_espacos():
    root = r"C:\Plugin EDE\versao instalada"
    expandido = _expandir_como_host(_texto(), root)

    assert TOKEN_PLUGIN_ROOT not in expandido
    assert f'python "{root}/scripts/validate_fatos.py" --dados fatos.json' in expandido
    assert "$CLAUDE_PLUGIN_ROOT" not in expandido


def test_script_expandido_executa_com_caso_relativo_e_sem_variavel_de_ambiente(
    tmp_path, monkeypatch
):
    fatos = tmp_path / "fatos.json"
    fatos.write_text(
        json.dumps(
            [{"fact": "Fato documentado.", "source_document": "prova.pdf"}]
        ),
        encoding="utf-8",
    )
    script = Path(
        _expandir_como_host("${CLAUDE_PLUGIN_ROOT}/scripts/validate_fatos.py", str(BASE))
    )
    ambiente = os.environ.copy()
    ambiente.pop("CLAUDE_PLUGIN_ROOT", None)
    monkeypatch.chdir(tmp_path)

    resultado = subprocess.run(
        [sys.executable, str(script), "--dados", "fatos.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ambiente,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr or resultado.stdout
    assert "proveniência válida" in resultado.stdout


def test_snippets_python_recebem_root_expandido_sem_ler_ambiente():
    texto = _texto()

    assert 'Path(r"""${CLAUDE_PLUGIN_ROOT}""")' in texto
    assert "plugin_root / \"rag\"" in texto
    assert re.search(r"plugin_root / ['\"]scripts['\"]", texto)
    assert re.search(
        r"plugin_root / ['\"]templates['\"] / ['\"]contestacao['\"]", texto
    )
    assert "os.environ" not in texto


def test_skill_define_fail_closed_para_token_nao_expandido_ou_root_invalido():
    texto = _normalizado()

    assert "token não expandido" in texto.lower()
    assert ".claude-plugin/plugin.json" in texto
    assert "FAIL-CLOSED" in texto
    assert "cwd" in texto


def test_fatos_json_continua_relativo_ao_workspace_do_caso():
    texto = _normalizado()

    assert "--dados fatos.json" in texto
    assert "${CLAUDE_PLUGIN_ROOT}/fatos.json" not in texto
    assert "recurso do caso" in texto


def test_nao_restam_invocacoes_bare_de_recursos_do_plugin():
    texto = _texto()

    proibidos = (
        "python scripts/",
        "python3 scripts/",
        "sys.path.insert(0, 'scripts')",
        'sys.path.insert(0, "rag")',
        "sys.path.insert(0, 'rag')",
    )
    for proibido in proibidos:
        assert proibido not in texto


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for teste in testes:
        teste()
        print(f"OK  {teste.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
