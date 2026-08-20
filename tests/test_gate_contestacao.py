#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_gate_contestacao.py — guarda estrutural do `INV-GATE-CONTESTACAO`
(Gate 5.1): enquanto a Contestação não for validada pelo usuário em uso
real, nenhuma nova peça processual pode ser iniciada, e nenhuma suíte
técnica verde pode ser tratada como validação final.

Mesmo padrão sem framework do resto do projeto (ver
tests/test_contestacao_skill_dependencies.py): asserts semânticos sobre o
CONTEÚDO da SPEC/CLAUDE.md — não byte-a-byte de uma frase inteira — mais
uma checagem estrutural direta de que nenhuma Skill/template de outra
peça foi de fato criado no repositório.

Uso:
  python tests/test_gate_contestacao.py
"""
from pathlib import Path

BASE = Path(__file__).parent.parent
SPEC = BASE / "docs" / "specs" / "SPEC-0001.md"
CLAUDE = BASE / "CLAUDE.md"

# Skills/templates transversais ou já autorizados antes deste gate — a
# única peça processual permitida é a Contestação; qualquer diretório de
# peça além destes é violação da trava.
SKILLS_PERMITIDAS = {
    "atualizar-ede", "calendario-forense-tjba-2026", "contestacao",
    "estrategista-contestacao-ede", "humanizer-pt-br",
    "redator-peca-processual-elite",
}
TEMPLATES_PERMITIDOS = {"contestacao"}

# Nomes de peça cuja simples existência como diretório em skills/ ou
# templates/ já violaria a trava (lista aberta — não exaustiva, mas cobre
# os exemplos citados explicitamente na invariante).
PECAS_VEDADAS_ENQUANTO_ATIVA = (
    "recurso-inominado", "embargos-de-declaracao", "embargos-execucao",
    "manifestacao",
)

# Padrões de abstração multipeça prematura — não podem existir como
# diretório/módulo no repositório enquanto a trava estiver ativa.
ABSTRACOES_MULTIPECA_VEDADAS = (
    "piece_registry", "piece_factory", "generic_piece_engine",
    "base_piece", "piece_type",
)


def _texto(caminho: Path) -> str:
    assert caminho.exists(), f"{caminho} não existe"
    return caminho.read_text(encoding="utf-8")


def _normalizado(caminho: Path) -> str:
    """Minúsculo, com quebras de linha do prosa Markdown colapsadas —
    evita testes frágeis dependentes de como a frase quebra em linhas."""
    return " ".join(_texto(caminho).lower().split())


# --------------------------------------------------------------- 1-2: existência
def test_inv_gate_contestacao_existe_na_spec():
    assert "INV-GATE-CONTESTACAO" in _texto(SPEC), (
        f"INV-GATE-CONTESTACAO não está registrada em {SPEC}")


def test_inv_gate_contestacao_existe_no_claude_md():
    assert "INV-GATE-CONTESTACAO" in _texto(CLAUDE), (
        f"INV-GATE-CONTESTACAO não está registrada em {CLAUDE}")


# --------------------------------------------------------------- 3: liberação por manifestação expressa
def test_validacao_expressa_do_usuario_e_condicao_de_liberacao():
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "manifestação expressa" in texto or "manifestacao expressa" in texto, (
            f"{caminho} não condiciona a liberação a manifestação expressa do usuário")
        assert "usuário" in texto or "usuario" in texto


# --------------------------------------------------------------- 4: testes ≠ validação final
def test_testes_automatizados_nao_equivalem_a_validacao_final():
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "validação técnica" in texto or "validacao tecnica" in texto, (
            f"{caminho} não distingue validação técnica de validação final")
        assert "não substituem" in texto or "nao substituem" in texto or \
               "não substitui" in texto or "nao substitui" in texto, (
            f"{caminho} não afirma que testes/relatório não substituem a validação humana")


# --------------------------------------------------------------- 5: novas peças proibidas
def test_novas_pecas_permanecem_proibidas_antes_da_liberacao():
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "recurso inominado" in texto, f"{caminho} não cita Recurso Inominado como vedado"
        assert "embargos" in texto, f"{caminho} não cita Embargos como vedado"
        assert "vedado" in texto or "proibido" in texto or "proíbe" in texto or "proibe" in texto


# --------------------------------------------------------------- 6: generalização multipeça proibida
def test_generalizacao_multipeca_prematura_permanece_proibida():
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "multipeça" in texto or "multipeca" in texto or "multipeças" in texto or "multipecas" in texto, (
            f"{caminho} não menciona a proibição de generalização multipeça")


# --------------------------------------------------------------- 7: Contestação é a única peça autorizada
def test_contestacao_permanece_a_unica_peca_autorizada():
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "única peça processual autorizada" in texto or "unica peca processual autorizada" in texto, (
            f"{caminho} não declara a Contestação como única peça autorizada")


# --------------------------------------------------------------- 8: próximo estágio é teste real
def test_proximo_estagio_e_teste_real_da_contestacao():
    texto = _normalizado(SPEC)
    assert "testes reais" in texto or "teste real" in texto, (
        f"{SPEC} não referencia testes reais como o próximo estágio")


# --------------------------------------------------------------- guarda estrutural direta
def test_nenhuma_skill_de_outra_peca_foi_criada():
    skills_dir = BASE / "skills"
    existentes = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    inesperadas = existentes - SKILLS_PERMITIDAS
    assert not inesperadas, (
        f"diretório(s) de Skill não previsto(s) em skills/: {sorted(inesperadas)} — "
        f"possível violação de INV-GATE-CONTESTACAO (nova peça iniciada)")
    for peca in PECAS_VEDADAS_ENQUANTO_ATIVA:
        assert peca not in existentes, f"skills/{peca}/ existe — viola INV-GATE-CONTESTACAO"


def test_nenhum_template_de_outra_peca_foi_criado():
    templates_dir = BASE / "templates"
    existentes = {p.name for p in templates_dir.iterdir() if p.is_dir()}
    inesperados = existentes - TEMPLATES_PERMITIDOS
    assert not inesperados, (
        f"diretório(s) de template não previsto(s) em templates/: {sorted(inesperados)} — "
        f"possível violação de INV-GATE-CONTESTACAO (nova peça iniciada)")


def test_nenhuma_abstracao_multipeca_prematura_no_codigo():
    scripts_dir = BASE / "scripts"
    nomes_arquivos = {p.stem.lower() for p in scripts_dir.glob("*.py")}
    for abstracao in ABSTRACOES_MULTIPECA_VEDADAS:
        assert abstracao not in nomes_arquivos, (
            f"scripts/{abstracao}.py existe — generalização multipeça prematura, viola INV-GATE-CONTESTACAO")


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
