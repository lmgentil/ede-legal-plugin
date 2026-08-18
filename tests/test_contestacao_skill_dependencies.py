#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contestacao_skill_dependencies.py — guarda estrutural do contrato de
orquestração de skills/contestacao/SKILL.md (CLAUDE.md §7,
INV-CONTESTACAO-ESTRATEGIA, SPEC-0001 §5).

Não basta a Skill existir como diretório — este teste lê o CONTEÚDO de
skills/contestacao/SKILL.md e falha se `estrategista-contestacao-ede`
deixar de estar declarada como dependência OBRIGATÓRIA (não opcional,
recomendada ou facultativa), ou se `redator-peca-processual-elite`/
`humanizer-pt-br` deixarem de estar declaradas como obrigatórias.

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.
"""
import re
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "contestacao" / "SKILL.md"

PALAVRAS_QUE_ENFRAQUECEM = ("opcional", "recomendad", "facultativ", "dispens")


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


def _secao_dependencias(texto: str) -> str:
    """Extrai o bloco '## 0. Dependências obrigatórias' até o próximo '## '."""
    m = re.search(r"##\s*0\.\s*Dependências obrigatórias.*?\n(.*?)\n##\s", texto, re.S)
    assert m, ("seção '## 0. Dependências obrigatórias' não encontrada em "
                f"{SKILL_PATH} — contrato de orquestração não está mais "
                "declarado de forma parseável")
    return m.group(1)


def _linha_da_dependencia(bloco: str, nome_skill: str) -> str:
    linha = next((l for l in bloco.splitlines() if nome_skill in l), None)
    assert linha is not None, f"'{nome_skill}' não está listada na seção de dependências"
    return linha


# --------------------------------------------------------------- testes
def test_skill_existe_e_declara_secao_de_dependencias():
    texto = _texto()
    bloco = _secao_dependencias(texto)
    assert bloco.strip(), "seção de dependências está vazia"


def test_estrategista_declarado_como_obrigatorio():
    bloco = _secao_dependencias(_texto())
    linha = _linha_da_dependencia(bloco, "estrategista-contestacao-ede").lower()
    assert "obrigat" in linha, f"linha não afirma obrigatoriedade: {linha!r}"
    for palavra in PALAVRAS_QUE_ENFRAQUECEM:
        assert palavra not in linha, f"linguagem que enfraquece obrigatoriedade ({palavra!r}) em: {linha!r}"


def test_redator_continua_obrigatorio():
    bloco = _secao_dependencias(_texto())
    linha = _linha_da_dependencia(bloco, "redator-peca-processual-elite").lower()
    assert "obrigat" in linha


def test_humanizer_continua_obrigatorio():
    bloco = _secao_dependencias(_texto())
    linha = _linha_da_dependencia(bloco, "humanizer-pt-br").lower()
    assert "obrigat" in linha


def test_calendario_declarado_obrigatorio_quando_aplicavel():
    bloco = _secao_dependencias(_texto())
    linha = _linha_da_dependencia(bloco, "calendario-forense-tjba-2026").lower()
    assert "obrigat" in linha


def test_nenhuma_ocorrencia_de_estrategista_no_arquivo_usa_linguagem_fraca():
    # guarda ampla: em qualquer lugar do arquivo (não só na seção 0), uma
    # linha que menciona estrategista-contestacao-ede não pode, ao mesmo
    # tempo, descrevê-la como opcional/recomendada/facultativa/dispensável.
    # ("recomendadas"/"recomendável" em outro contexto, sem a skill citada
    # na mesma linha, não é capturado aqui — verificação é linha a linha.)
    texto = _texto()
    for i, linha in enumerate(texto.splitlines(), start=1):
        if "estrategista-contestacao-ede" not in linha:
            continue
        l = linha.lower()
        for palavra in PALAVRAS_QUE_ENFRAQUECEM:
            assert palavra not in l, (
                f"{SKILL_PATH}:{i} associa estrategista-contestacao-ede a "
                f"'{palavra}': {linha!r}")


def test_pipeline_menciona_estrategista_antes_do_redator():
    # a etapa estratégica precede a redação (INV-CONTESTACAO-ESTRATEGIA) —
    # checagem posicional simples: primeira menção ao estrategista aparece
    # antes da primeira menção ao redator no corpo do arquivo.
    texto = _texto()
    pos_estrategista = texto.find("estrategista-contestacao-ede")
    pos_redator = texto.find("redator-peca-processual-elite")
    assert pos_estrategista != -1 and pos_redator != -1
    assert pos_estrategista < pos_redator, (
        "menção ao estrategista aparece depois do redator — "
        "INV-CONTESTACAO-ESTRATEGIA exige a etapa estratégica antes da redação")


def test_declara_fail_closed_sem_fallback_silencioso():
    # normaliza quebras de linha do prosa em Markdown (frases longas
    # quebram em várias linhas no arquivo-fonte) antes de procurar a frase.
    texto = " ".join(_texto().lower().split())
    assert "fallback silencioso" in texto or "sem fallback" in texto
    assert "pipeline" in texto and ("não pode prosseguir" in texto or "não avança" in texto or "impede" in texto)


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
