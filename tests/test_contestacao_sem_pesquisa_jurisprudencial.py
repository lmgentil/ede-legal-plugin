#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contestacao_sem_pesquisa_jurisprudencial.py — guarda de governança
para INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL (docs/specs/
SPEC-0001.md §46, CLAUDE.md, skills/contestacao/SKILL.md §7).

Substitui/absorve o teste anterior (INV-JURISPRUDENCIA-EXTERNA-
DESABILITADA), renomeado — a regra deixou de ser "vedação de ferramenta
externa condicionada a PEND-002" e passou a ser "a Contestação nunca
trabalha com jurisprudência", decisão arquitetural permanente da peça.

Origem: Teste Real 01-B observou "Calling Jurisprudências.ai 5 times".
Auditoria forense encontrou a causa habilitante em skills/contestacao/
SKILL.md §7 (versão histórica): a única ocorrência, em todo o
repositório, de uma instrução nomeando "pesquisa externa" como fonte
aceitável de citação jurisprudencial.

Este teste é deliberadamente uma regra PERMANENTE, não uma checagem
específica de uma ferramenta hoje conhecida: audita o TEXTO das três
Skills da Contestação por instrução POSITIVA de pesquisa/uso de
jurisprudência, então sobrevive à existência futura de qualquer
ferramenta (Jurisprudências.ai, MCP jurídico, busca web, ou outra ainda
não inventada) — disponibilidade da ferramenta não é autorização de uso.

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.
"""
from pathlib import Path

BASE = Path(__file__).parent.parent
SPEC = BASE / "docs" / "specs" / "SPEC-0001.md"
CLAUDE = BASE / "CLAUDE.md"
PENDENCIAS = BASE / "docs" / "PENDENCIAS.md"
SKILLS_CONTESTACAO = [
    BASE / "skills" / "contestacao" / "SKILL.md",
    BASE / "skills" / "estrategista-contestacao-ede" / "SKILL.md",
    BASE / "skills" / "redator-peca-processual-elite" / "SKILL.md",
]

# Frases que, se encontradas SEM linguagem de proibição próxima, indicam
# instrução positiva de pesquisa/uso de jurisprudência — exatamente o que
# causou o achado real. Deliberadamente ampla (não é uma lista de nomes de
# ferramenta específica) para sobreviver à existência futura de qualquer
# ferramenta de pesquisa.
_GATILHOS_DE_PESQUISA = (
    "jurisprudências.ai",
    "jurisprudencias.ai",
    "pesquisa externa explícita",
    "pesquisa externa explicita",
    "pesquisar jurisprudência",
    "pesquisar jurisprudencia",
    "buscar precedente",
    "busca web",
    "consulte a jurisprudência",
    "consulte a jurisprudencia",
)
_PALAVRAS_DE_PROIBICAO = ("nunca", "não", "proib", "vedad", "desabilitad", "obsolet")


def _texto(caminho: Path) -> str:
    assert caminho.exists(), f"{caminho} não existe"
    return caminho.read_text(encoding="utf-8")


def _normalizado(caminho: Path) -> str:
    # Colapsa quebras de linha do prosa Markdown — mesmo padrão de
    # tests/test_gate_contestacao.py.
    return " ".join(_texto(caminho).lower().split())


# --------------------------------------------------------------- 1: invariante registrada
def test_invariante_registrada_na_spec():
    assert "INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL" in _texto(SPEC)


def test_invariante_registrada_no_claude_md():
    assert "INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL" in _texto(CLAUDE)


def test_invariante_e_regra_permanente_nao_condicionada_a_pend_002():
    # A formulação precisa deixar claro que não é uma restrição temporária
    # ligada ao status de PEND-002 (diferença central da correção).
    for caminho in (SPEC, CLAUDE):
        texto = _normalizado(caminho)
        assert "permanente" in texto, f"{caminho} não descreve a invariante como permanente"


def test_invariante_anterior_nao_aparece_mais_isolada():
    # A regra antiga (condicionada a PEND-002) foi substituída/absorvida —
    # se ainda existir, deve aparecer só como referência histórica, nunca
    # como o nome ativo da invariante corrente.
    for caminho in (SPEC, CLAUDE):
        texto = _texto(caminho)
        if "INV-JURISPRUDENCIA-EXTERNA-DESABILITADA" in texto:
            # Permitido apenas em nota histórica que também cita o nome novo.
            assert "INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL" in texto


# --------------------------------------------------------------- 2: nenhuma skill instrui pesquisa
def test_nenhuma_skill_da_contestacao_instrui_pesquisa_jurisprudencial():
    for caminho in SKILLS_CONTESTACAO:
        linhas = _texto(caminho).splitlines()
        for i, linha in enumerate(linhas):
            l = linha.lower()
            gatilho = next((g for g in _GATILHOS_DE_PESQUISA if g in l), None)
            if gatilho is None:
                continue
            janela = " ".join(linhas[max(0, i - 3):i + 1]).lower()
            assert any(p in janela for p in _PALAVRAS_DE_PROIBICAO), (
                f"{caminho}:{i + 1} contém {gatilho!r} sem linguagem de "
                f"proibição nas proximidades: {linha!r}")


def test_marcador_pesquisa_jurisprudencial_necessaria_nao_e_mais_instrucao_ativa():
    # O marcador pode aparecer só para explicar que está obsoleto — nunca
    # como algo a ser produzido/usado ativamente.
    for caminho in SKILLS_CONTESTACAO:
        linhas = _texto(caminho).splitlines()
        for i, linha in enumerate(linhas):
            if "pesquisa jurisprudencial necessária" not in linha.lower():
                continue
            l = linha.lower()
            assert "obsolet" in l or "não produz" in l or "nao produz" in l, (
                f"{caminho}:{i + 1} ainda trata o marcador como ativo: {linha!r}")


def test_estrategista_nao_produz_secao_de_jurisprudencia():
    texto = _normalizado(SKILLS_CONTESTACAO[1])  # estrategista-contestacao-ede
    assert "não pesquisa e não usa" in texto or "nao pesquisa e nao usa" in texto


def test_redator_probe_frases_de_autoridade_jurisprudencial_generica():
    texto = _normalizado(SKILLS_CONTESTACAO[2])  # redator-peca-processual-elite
    assert "entendimento consolidado" in texto
    assert "não invente autoridade jurisprudencial" in texto or "nao invente autoridade jurisprudencial" in texto


def test_reference_de_jurisprudencia_do_estrategista_esta_marcada_obsoleta():
    ref = BASE / "skills" / "estrategista-contestacao-ede" / "references" / "06_risco_documentos_jurisprudencia.md"
    texto = _normalizado(ref)
    assert "obsoleto" in texto
    assert "pesquisa jurisprudencial necessária" not in texto or "obsolet" in texto


# --------------------------------------------------------------- 3: RAG local preservado
def test_rag_local_permanece_mencionado_como_autorizado():
    texto = _normalizado(SKILLS_CONTESTACAO[0])
    assert "search_hybrid" in texto
    assert "legal_validation" in texto or "validar_citacao" in texto


# --------------------------------------------------------------- 4: PEND-002 não encerrada indevidamente
def test_pend_002_permanece_aberta_com_nota_de_desacoplamento():
    # A auditoria concluiu que PEND-002 tem finalidade distinta (infra do
    # RAG) e não deve ser encerrada por esta correção — só anotada.
    texto = _texto(PENDENCIAS)
    assert "PEND-002" in texto and "ABERTA" in texto
    assert "INV-CONTESTACAO-SEM-PESQUISA-JURISPRUDENCIAL" in texto


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
