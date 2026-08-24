#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contexto_institucional_redator.py — guarda estrutural da Etapa 5.7-B
(INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA, docs/specs/SPEC-0001.md §56,
CLAUDE.md §7): o Redator deve receber o contexto institucional extraído
do modelo real antes de redigir cada placeholder, e o Humanizer nunca
recebe texto institucional como conteúdo a reescrever.

Mesma limitação de tests/test_orquestracao_entrega_contestacao.py: Skills
do Claude Code são arquivos de instrução para um agente LLM, não há API
Python para "executar" a leitura de instrução e observar o efeito — os
casos J/K/L/M do pedido da Etapa 5.7-B (§12) são cobertos aqui como
guardas estruturais sobre o CONTEÚDO dos SKILL.md/CLAUDE.md/SPEC-0001.md
envolvidos, mesmo padrão do restante da suíte de governança. Os casos
A-I/N-R (extração em si) estão em tests/test_docx_context_engine.py.

Uso:
  python tests/test_contexto_institucional_redator.py
"""
from pathlib import Path

BASE = Path(__file__).parent.parent
CLAUDE = BASE / "CLAUDE.md"
SPEC = BASE / "docs" / "specs" / "SPEC-0001.md"
CONTESTACAO_SKILL = BASE / "skills" / "contestacao" / "SKILL.md"
REDATOR_SKILL = BASE / "skills" / "redator-peca-processual-elite" / "SKILL.md"
HUMANIZER_SKILL = BASE / "skills" / "humanizer-pt-br" / "SKILL.md"


def _texto(caminho: Path) -> str:
    assert caminho.exists(), f"{caminho} não existe"
    return caminho.read_text(encoding="utf-8")


def _normalizado(caminho: Path) -> str:
    """Colapsa quebras de linha do prosa Markdown — uma frase pode
    quebrar entre linhas no arquivo sem deixar de ser a mesma frase."""
    return " ".join(_texto(caminho).split())


# --------------------------------------------------- invariante registrada
def test_invariante_registrada_no_claude_md():
    assert "INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA" in _texto(CLAUDE)


def test_invariante_registrada_na_spec():
    assert "INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA" in _texto(SPEC)


def test_regra_sem_placeholder_sem_escrita_gerativa_registrada():
    for caminho in (CLAUDE, SPEC, CONTESTACAO_SKILL):
        texto = _normalizado(caminho).upper()
        assert "SEM PLACEHOLDER" in texto and "SEM ESCRITA GERATIVA" in texto, (
            f"regra 'SEM PLACEHOLDER -> SEM ESCRITA GERATIVA' ausente em {caminho}")


def test_excecao_da_renumeracao_expressa_no_claude_md_e_na_spec():
    for caminho in (CLAUDE, SPEC):
        texto = _normalizado(caminho)
        assert "INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA" in texto
        assert "INV-NUMERACAO-DINAMICA-CONTESTACAO" in texto
        # a exceção precisa estar dita perto da invariante nova, não só
        # existir em algum outro lugar do documento por coincidência.
        idx_nova = texto.find("INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA")
        janela = texto[idx_nova:idx_nova + 4000]
        assert "INV-NUMERACAO-DINAMICA-CONTESTACAO" in janela, (
            f"{caminho}: exceção da renumeração não está expressa perto da nova invariante")


# --------------------------------------------------- J: Redator recebe contexto
def test_J_skill_contestacao_instrui_extrair_contexto_antes_do_redator():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "docx_context_engine" in texto
    assert "extrair_contexto_do_template" in texto
    # instrução explícita de ORDEM: extrair contexto ANTES de acionar o
    # redator — não basta as duas coisas estarem mencionadas em algum
    # lugar do arquivo, precisa estar dita como sequência.
    assert "antes** de acionar `redator-peca-processual-elite`" in texto.lower(), (
        "extração de contexto institucional precisa vir descrita "
        "explicitamente ANTES do acionamento do redator, em "
        "skills/contestacao/SKILL.md §9")


def test_J_redator_skill_menciona_consumir_contexto_institucional():
    texto = _normalizado(REDATOR_SKILL)
    assert "INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA" in texto
    assert "contexto institucional" in texto.lower()


# --------------------------------------------------- K/L: raciocínio A-E
def test_K_L_raciocinio_nao_duplicacao_registrado_na_skill_orquestradora():
    texto = _normalizado(CONTESTACAO_SKILL).lower()
    marcadores = ["não repetir", "inserir somente o dado", "não reescrever a fundamentação",
                  "não inserir"]
    faltando = [m for m in marcadores if m not in texto]
    assert not faltando, f"raciocínio A-E incompleto em {CONTESTACAO_SKILL}: faltando {faltando}"


def test_K_L_preserva_invariantes_existentes_de_nao_redundancia():
    texto = _texto(CONTESTACAO_SKILL)
    assert "INV-NAO-REDUNDANCIA-NORMATIVA" in texto
    assert "INV-NAO-REPETICAO-FATICA" in texto


# --------------------------------------------------- M: Humanizer não reescreve texto-base
def test_M_humanizer_skill_declara_contexto_nao_editavel():
    texto = _normalizado(HUMANIZER_SKILL)
    assert "CONTEXTO NÃO EDITÁVEL" in texto
    assert "modelo-oficial.docx" in texto


def test_M_contestacao_skill_declara_que_humanizer_nunca_recebe_texto_institucional():
    texto = _normalizado(CONTESTACAO_SKILL).lower()
    assert "humanizer" in texto and "nunca" in texto
    # a frase precisa existir na vizinhança da nova subseção, não em
    # qualquer menção solta a "humanizer" no resto do documento.
    idx = texto.find("contexto institucional do modelo")
    assert idx != -1
    janela = texto[idx:idx + 4000]
    assert "humanizer" in janela and "nunca" in janela


# --------------------------------------------------- não regrediu §6/§7/§8 já existentes
def test_dependencias_obrigatorias_continuam_intactas():
    texto = _texto(CONTESTACAO_SKILL)
    for skill in ("estrategista-contestacao-ede", "redator-peca-processual-elite",
                  "humanizer-pt-br"):
        assert skill in texto, f"dependência obrigatória {skill} não está mais referenciada"


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
