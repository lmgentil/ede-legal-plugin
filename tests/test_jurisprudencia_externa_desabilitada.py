#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_jurisprudencia_externa_desabilitada.py — guarda de governança contra
ferramenta externa de jurisprudência (INV-JURISPRUDENCIA-EXTERNA-
DESABILITADA, achado do Teste Real 01-B — "Calling Jurisprudências.ai
5 times").

Auditoria forense encontrou a causa habilitante em skills/contestacao/
SKILL.md §7: a única ocorrência, em todo o repositório, de uma instrução
nomeando "pesquisa externa" como fonte aceitável de citação
jurisprudencial. Este teste garante que essa linguagem (e qualquer
referência a Jurisprudências.ai/agente/MCP externo de jurisprudência como
caminho válido) não volte a aparecer nas três Skills da Contestação, e
que a invariante esteja registrada em SPEC/CLAUDE.md.

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.
"""
from pathlib import Path

BASE = Path(__file__).parent.parent
SPEC = BASE / "docs" / "specs" / "SPEC-0001.md"
CLAUDE = BASE / "CLAUDE.md"
SKILLS_CONTESTACAO = [
    BASE / "skills" / "contestacao" / "SKILL.md",
    BASE / "skills" / "estrategista-contestacao-ede" / "SKILL.md",
    BASE / "skills" / "redator-peca-processual-elite" / "SKILL.md",
]

# Padrões que, se encontrados, indicariam autorização (ainda que
# implícita) de pesquisa jurisprudencial externa. "pesquisa externa"
# sozinho é intencionalmente amplo — é a frase exata que causou o achado.
PADROES_PROIBIDOS = (
    "jurisprudências.ai",
    "jurisprudencias.ai",
    "pesquisa externa explícita",
    "pesquisa externa explicita",
)


def _texto(caminho: Path) -> str:
    assert caminho.exists(), f"{caminho} não existe"
    return caminho.read_text(encoding="utf-8")


def _normalizado(caminho: Path) -> str:
    # Colapsa quebras de linha do prosa Markdown (frases longas quebram em
    # várias linhas no arquivo-fonte) — mesmo padrão de
    # tests/test_gate_contestacao.py.
    return " ".join(_texto(caminho).lower().split())


# --------------------------------------------------------------- 1: invariante registrada
def test_invariante_registrada_na_spec():
    assert "INV-JURISPRUDENCIA-EXTERNA-DESABILITADA" in _texto(SPEC)


def test_invariante_registrada_no_claude_md():
    assert "INV-JURISPRUDENCIA-EXTERNA-DESABILITADA" in _texto(CLAUDE)


# --------------------------------------------------------------- 2: nenhuma skill autoriza pesquisa externa
_PALAVRAS_DE_PROIBICAO = ("nunca", "não", "proib", "vedad", "desabilitad")


def test_nenhuma_skill_da_contestacao_menciona_jurisprudencias_ai_como_fonte_valida():
    # A skill orquestradora PRECISA nomear "Jurisprudências.ai" para
    # proibi-la explicitamente (INV-JURISPRUDENCIA-EXTERNA-DESABILITADA)
    # — o que este teste garante é que toda menção venha acompanhada de
    # linguagem de proibição próxima (mesma linha ou até 3 linhas antes,
    # cobrindo o caso de item de lista introduzido por um cabeçalho de
    # proibição), nunca de autorização isolada.
    for caminho in SKILLS_CONTESTACAO:
        linhas = _texto(caminho).splitlines()
        for i, linha in enumerate(linhas):
            l = linha.lower()
            if "jurisprudências.ai" not in l and "jurisprudencias.ai" not in l:
                continue
            janela = " ".join(linhas[max(0, i - 3):i + 1]).lower()
            assert any(p in janela for p in _PALAVRAS_DE_PROIBICAO), (
                f"{caminho}:{i + 1} menciona Jurisprudências.ai sem linguagem "
                f"de proibição nas proximidades: {linha!r}")


def test_nenhuma_skill_da_contestacao_autoriza_pesquisa_externa_explicita():
    # A frase exata que causou o achado real não pode reaparecer.
    for caminho in SKILLS_CONTESTACAO:
        texto = _normalizado(caminho)
        assert "pesquisa externa explícita" not in texto and "pesquisa externa explicita" not in texto, (
            f"{caminho} ainda autoriza 'pesquisa externa explícita' como fonte de citação")


def test_contestacao_skill_proibe_explicitamente_ferramenta_externa():
    texto = _normalizado(SKILLS_CONTESTACAO[0])  # skills/contestacao/SKILL.md
    assert "mcp" in texto and "jurisprud" in texto
    assert "não aciona" in texto or "nunca aciona" in texto or "nunca" in texto


def test_estrategista_skill_declara_marcador_nao_e_instrucao_de_busca():
    texto = _normalizado(SKILLS_CONTESTACAO[1])  # estrategista-contestacao-ede
    assert "pesquisa jurisprudencial necessária" in texto
    assert "nunca uma instrução" in texto or "não aciona" in texto


def test_redator_skill_nao_busca_jurisprudencia_por_conta_propria():
    texto = _normalizado(SKILLS_CONTESTACAO[2])  # redator-peca-processual-elite
    assert "jurisprud" in texto
    assert "por conta própria" in texto or "não a busque" in texto or "nunca a busque" in texto


# --------------------------------------------------------------- 3: RAG local preservado
def test_rag_local_permanece_mencionado_como_autorizado():
    # A correção não pode ter removido a menção ao RAG local obrigatório.
    texto = _normalizado(SKILLS_CONTESTACAO[0])
    assert "search_hybrid" in texto
    assert "legal_validation" in texto or "validar_citacao" in texto


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
