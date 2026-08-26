#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contestacao_skill_caminhos.py — guarda estrutural da correção de
portabilidade de caminhos em skills/contestacao/SKILL.md (Etapa 5.9-B):
todo recurso PERTENCENTE AO PLUGIN citado como comando executável é
resolvido via $CLAUDE_PLUGIN_ROOT, nunca via caminho relativo dependente
do cwd; recursos do CASO (fatos.json etc.) continuam relativos ao
workspace do advogado, nunca redirecionados para $CLAUDE_PLUGIN_ROOT.

Esta etapa não declara compatibilidade com Claude Cowork — só elimina
dependência indevida do cwd, mesmo princípio já validado em
test_atualizar_ede_skill.py.

Como a Skill é prosa/Markdown, o teste verifica o CONTEÚDO do arquivo —
mesmo padrão sem framework de test_contestacao_skill_dependencies.py.
"""
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "contestacao" / "SKILL.md"


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalizado() -> str:
    return " ".join(_texto().split())


# --------------------------------------------- A/B: sem dependência do cwd
def test_declara_regra_de_portabilidade():
    texto = _normalizado()
    assert "$CLAUDE_PLUGIN_ROOT" in texto
    assert "nunca do `cwd`" in texto or "nunca do cwd" in texto.replace("`", "")


def test_nenhuma_invocacao_bare_de_validate_fatos():
    texto = _texto()
    assert "python scripts/validate_fatos.py" not in texto
    assert 'python "$CLAUDE_PLUGIN_ROOT/scripts/validate_fatos.py" --dados fatos.json' in texto


def test_nenhum_sys_path_insert_scripts_bare():
    # a forma antiga (sys.path.insert(0, 'scripts')) não pode mais existir —
    # dependia do cwd ser a raiz do checkout do plugin.
    texto = _texto()
    assert "sys.path.insert(0, 'scripts')" not in texto
    assert 'os.path.join(root, \'scripts\')' in texto or \
        'sys.path.insert(0, os.path.join(root' in texto


def test_nenhum_sys_path_insert_rag_bare():
    texto = _texto()
    assert 'sys.path.insert(0, "rag")' not in texto
    assert "sys.path.insert(0, 'rag')" not in texto
    ocorrencias = texto.count(
        'sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "rag"))'
    )
    assert ocorrencias == 2, (
        "esperava 2 ocorrências (search_hybrid + legal_validation) do setup "
        f"de sys.path via CLAUDE_PLUGIN_ROOT para rag/, encontrei {ocorrencias}")


def test_modelo_oficial_e_blocos_json_resolvidos_via_plugin_root():
    # a forma antiga passava os caminhos bare, direto como argumento de
    # extrair_contexto_do_template(...) — a correta envolve cada um em
    # os.path.join(root, ...), nunca a string sozinha como argumento.
    texto = _texto()
    assert "extrair_contexto_do_template(\n    'templates/contestacao/modelo-oficial.docx'" not in texto
    assert "os.path.join(root, 'templates/contestacao/modelo-oficial.docx')" in texto
    assert "os.path.join(root, 'templates/contestacao/blocos.json')" in texto


# ------------------------------------------------------ C: paths com espaço
def test_quoting_seguro_para_caminho_com_espaco():
    # a invocação bash usa aspas duplas ao redor de "$CLAUDE_PLUGIN_ROOT/...";
    # as substituições em python -c ocorrem via os.environ/os.path.join
    # (nunca concatenação crua sem aspas em contexto de shell), então um
    # valor de CLAUDE_PLUGIN_ROOT com espaço nunca quebra a invocação.
    texto = _texto()
    assert '"$CLAUDE_PLUGIN_ROOT/scripts/validate_fatos.py"' in texto


# --------------------------------------------------- E: recursos do caso
def test_fatos_json_continua_relativo_ao_caso():
    texto = _normalizado()
    assert "--dados fatos.json" in texto
    assert "$CLAUDE_PLUGIN_ROOT/fatos.json" not in texto
    assert "recurso do caso" in texto


# --------------------------------------------------- F: fail-closed
def test_fail_closed_sem_claude_plugin_root():
    texto = _normalizado()
    assert "FAIL-CLOSED" in texto
    assert "./scripts" in texto and "../scripts" in texto
    assert "diretório alternativo" in texto or "não presuma" in texto.lower()


def test_keyerror_sem_fallback_no_heredoc_context_engine():
    texto = _normalizado()
    assert 'KeyError' in texto
    assert "nenhum fallback para" in texto.lower() or "nenhum fallback" in texto.lower()


# ----------------------------------------------- G: sem referência antiga
def test_nenhuma_referencia_antiga_python_scripts_bare():
    for linha_num, linha in enumerate(_texto().splitlines(), start=1):
        stripped = linha.strip()
        if stripped.startswith("python scripts/") or stripped.startswith("python3 scripts/"):
            raise AssertionError(
                f"{SKILL_PATH}:{linha_num} ainda invoca script do plugin por "
                f"caminho relativo bare: {linha!r}")


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
