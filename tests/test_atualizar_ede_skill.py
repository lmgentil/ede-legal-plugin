#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_atualizar_ede_skill.py — guarda estrutural do contrato de
skills/atualizar-ede/SKILL.md após a correção pontual de caminhos
relativos (dependência indevida do cwd do advogado).

Como esta Skill é prosa/instruções em Markdown (não um script Python
executável), o teste verifica o CONTEÚDO do arquivo — mesmo padrão de
tests/test_contestacao_skill_dependencies.py: asserts sobre presença/
ausência de trechos e posição relativa entre eles, sem framework.
"""
import re
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "atualizar-ede" / "SKILL.md"


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


# ------------------------------------------------------- A: gate de ambiente
def test_gate_ambiente_mensagem_curta_presente():
    texto = _texto()
    assert "A atualização do EDE deve ser executada no Claude Code onde o plugin" in texto


def test_gate_ambiente_manda_parar_sem_fallback():
    texto = " ".join(_texto().lower().split())
    assert "cwd corrente como substituto" in texto or "não use o" in texto and "cwd" in texto
    assert "sandbox/web como fallback" in texto or ("fallback" in texto and "sandbox" in texto)
    assert "pare" in texto or "e pare" in texto


def test_gate_ambiente_vem_antes_da_identificacao_de_versao():
    # a checagem de CLAUDE_PLUGIN_ROOT precisa anteceder qualquer outra ação
    # (item 2 da correção pontual) — posição textual do "Passo 0" antes do
    # "Passo 1".
    texto = _texto()
    pos_gate = texto.find("Passo 0")
    pos_passo1 = texto.find("Passo 1")
    assert pos_gate != -1 and pos_passo1 != -1
    assert pos_gate < pos_passo1


# --------------------------------------------------- B/C/M: caminhos e cwd
def test_caminhos_usam_claude_plugin_root():
    texto = _texto()
    for alvo in ("VERSION", ".claude-plugin/plugin.json", "scripts/validar_instalacao.py"):
        assert f"$CLAUDE_PLUGIN_ROOT/{alvo}" in texto, \
            f"{alvo} não é referenciado via $CLAUDE_PLUGIN_ROOT"


def test_nenhum_caminho_relativo_bare_para_validar_instalacao():
    # a forma antiga ("python scripts/validar_instalacao.py", sem prefixo
    # de variável) não pode mais aparecer — era a causa raiz da dependência
    # do cwd do advogado.
    texto = _texto()
    assert "python scripts/validar_instalacao.py" not in texto
    assert 'python "$CLAUDE_PLUGIN_ROOT/scripts/validar_instalacao.py"' in texto


def test_declara_independencia_do_cwd():
    texto = _texto().lower()
    assert "cwd" in texto
    assert "pasta do caso" in texto or "diretório de trabalho do advogado" in texto


def test_validacao_pos_atualizacao_usa_claude_plugin_root_e_json():
    texto = _texto()
    assert 'python "$CLAUDE_PLUGIN_ROOT/scripts/validar_instalacao.py" --json' in texto


# ------------------------------------------------- D: VERSION x plugin.json
def test_divergencia_version_plugin_json_e_fail_closed():
    texto = " ".join(_texto().split())
    m = re.search(r"divergirem.{0,400}", texto, re.S)
    assert m, "trecho sobre divergência entre VERSION e plugin.json não encontrado"
    trecho = m.group(0).lower()
    assert "fail-closed" in trecho or "fail closed" in trecho
    assert "inconsistente" in trecho
    assert "não" in trecho and ("avance" in trecho or "orientar" in trecho)


# --------------------------------------------------------------- E/F/G/H: escopo
def test_escopo_nunca_hardcoded_como_user():
    texto = _texto()
    # o comando de atualização usa um placeholder, não um valor fixo
    assert "--scope <SCOPE_DETECTADO>" in texto
    assert "--scope user" not in texto.replace("--scope <SCOPE_DETECTADO>", "")


def test_escopo_menciona_as_tres_opcoes():
    texto = _texto()
    for escopo in ("user", "project", "local"):
        assert f"`{escopo}`" in texto, f"escopo {escopo!r} não é mencionado como opção válida"


def test_nunca_assumir_scope_user_por_padrao():
    texto = _texto().lower()
    assert "nunca assuma" in texto or "nunca escolha um sozinho" in texto


def test_plugin_list_nao_e_executado_programaticamente():
    texto = _texto().lower()
    assert "não pode ser executado programaticamente" in texto


# ------------------------------------------------------ I/J: identidade fixa
def test_marketplace_e_plugin_corretos_no_comando():
    texto = _texto()
    assert "/plugin marketplace update ede" in texto
    assert "/plugin update ede-legal-plugin@ede --scope <SCOPE_DETECTADO>" in texto


# --------------------------------------------------- K/L: saídas finais
def test_saida_sucesso_com_diff_de_versao():
    texto = _texto()
    assert "Versão anterior: X" in texto
    assert "Versão atual: Y" in texto
    assert "EDE Legal Plugin atualizado com sucesso." in texto


def test_saida_ja_atualizado_quando_versao_igual():
    texto = _texto()
    assert "EDE Legal Plugin já estava atualizado." in texto


def test_saida_falha_nunca_afirma_sucesso():
    texto = _texto()
    normalizado = " ".join(texto.split())
    assert "Atualização não concluída." in texto
    assert "nunca afirme que a atualização terminou corretamente" in normalizado


# ------------------------------------------------- N/O: sem self-update real
def test_nao_ha_tentativa_de_self_update_por_shell():
    texto = " ".join(_texto().lower().split())
    assert "não existe" in texto and "programaticamente" in texto
    assert "não reabra a discussão" in texto or "decisão está encerrada" in texto


def test_nenhuma_ferramenta_dispara_slash_command_sozinha():
    texto = " ".join(_texto().lower().split())
    assert "nenhuma ferramenta desta skill os invoca por conta própria" in texto or \
        "não são binários de shell" in texto


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
