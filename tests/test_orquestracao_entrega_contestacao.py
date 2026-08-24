#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_orquestracao_entrega_contestacao.py — guarda estrutural da Etapa 5.6
(INV-CONTESTACAO-ENTREGA-DOCX, docs/specs/SPEC-0001.md §54, CLAUDE.md §7):
em MODO PRODUÇÃO, a Contestação deve entregar o DOCX final, não etapas
internas do pipeline (análise estratégica, RAG, redator, humanizer).

Skills do Claude Code são arquivos de instrução para um agente LLM — não
há API Python para "executar" o pipeline completo e observar se ele parou
cedo (mesma limitação documentada em scripts/gerar_contestacao.py,
"LIMITAÇÃO CONHECIDA"). Por isso este teste segue o mesmo padrão do
restante da suíte de governança (tests/test_contestacao_skill_
dependencies.py, tests/test_gate_contestacao.py): asserts estruturais
sobre o CONTEÚDO de CLAUDE.md, SPEC-0001.md e dos SKILL.md envolvidos —
não simulação de execução.

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.

Uso:
  python tests/test_orquestracao_entrega_contestacao.py
"""
import re
from pathlib import Path

BASE = Path(__file__).parent.parent
CLAUDE = BASE / "CLAUDE.md"
SPEC = BASE / "docs" / "specs" / "SPEC-0001.md"
CONTESTACAO_SKILL = BASE / "skills" / "contestacao" / "SKILL.md"
ESTRATEGISTA_SKILL = BASE / "skills" / "estrategista-contestacao-ede" / "SKILL.md"

# Frases que a resposta final em modo produção nunca pode conter —
# indicam entrega intermediária travestida de conclusão.
FRASES_PROXIMO_PASSO = (
    "próximo passo recomendado",
    "posso gerar a contestação",
    "se quiser, prossigo",
    "agora devemos seguir para",
)


def _texto(caminho: Path) -> str:
    assert caminho.exists(), f"{caminho} não existe"
    return caminho.read_text(encoding="utf-8")


def _normalizado(caminho: Path) -> str:
    """Minúsculo, quebras de linha do prosa Markdown colapsadas."""
    return " ".join(_texto(caminho).lower().split())


def _secao(texto: str, titulo_regex: str) -> str:
    """Extrai um bloco '## <titulo>' até o próximo '## ' ou fim do arquivo."""
    m = re.search(titulo_regex + r".*?\n(.*?)(?=\n##\s|\Z)", texto, re.S)
    assert m, f"seção {titulo_regex!r} não encontrada"
    return m.group(1)


# --------------------------------------------------- invariante registrada
def test_inv_entrega_docx_registrada_no_claude_md():
    assert "INV-CONTESTACAO-ENTREGA-DOCX" in _texto(CLAUDE), (
        f"INV-CONTESTACAO-ENTREGA-DOCX não está registrada em {CLAUDE}")


def test_inv_entrega_docx_registrada_na_spec():
    assert "INV-CONTESTACAO-ENTREGA-DOCX" in _texto(SPEC), (
        f"INV-CONTESTACAO-ENTREGA-DOCX não está registrada em {SPEC}")


def test_inv_entrega_docx_registrada_na_skill_orquestradora():
    assert "INV-CONTESTACAO-ENTREGA-DOCX" in _texto(CONTESTACAO_SKILL)


# --------------------------------------------------- (A/M) modo produção exige DOCX, proíbe "próximo passo"
def test_modo_producao_exige_docx_como_saida():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "docx final" in texto or "contestação final em docx" in texto
    assert "modo produção" in texto or "modo producao" in texto


def test_proibicao_de_frases_de_proximo_passo_em_modo_producao():
    texto = _normalizado(CONTESTACAO_SKILL)
    for frase in FRASES_PROXIMO_PASSO:
        assert frase in texto, (
            f"{CONTESTACAO_SKILL} não lista a frase proibida {frase!r} — "
            "sem essa checklist explícita, nada impede a recorrência do "
            "achado do Teste Real (Etapa 5.6)")


# --------------------------------------------------- (B/C/D/E) etapas internas não encerram execução
def test_analise_estrategica_nao_e_resposta_final_ao_advogado():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "não é a resposta ao advogado" in texto or \
           "nao e a resposta ao advogado" in texto, (
        f"{CONTESTACAO_SKILL} não afirma explicitamente que a análise "
        "estratégica não é a entrega final ao advogado")


def test_etapas_internas_nao_encerram_a_execucao():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "etapas internas do mesmo fluxo" in texto
    assert "nenhuma delas encerra a execução" in texto or \
           "nenhuma delas encerra a execucao" in texto


def test_rag_nao_e_checkpoint_humano():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "deseja que eu prossiga para o rag" in texto, (
        f"{CONTESTACAO_SKILL} não nega explicitamente o checkpoint de RAG")
    assert "automático quando previsto" in texto or \
           "automatico quando previsto" in texto


def test_redator_e_humanizer_nao_pedem_autorizacao():
    texto = _texto(CONTESTACAO_SKILL)
    # A seção 9 (Redator e humanização) e a seção 11 (modo de operação)
    # devem cobrir redator/humanizer como etapas que não param a execução.
    assert "Redação e humanização (obrigatórias)" in texto
    secao11 = _secao(texto, r"##\s*11\.\s*Modo de operação")
    assert "redator" in secao11.lower() and "humanizer" in secao11.lower()


# --------------------------------------------------- (F/G/H/I) gate humano restrito ao pendente
def test_gate_humano_restrito_a_reconvencao_e_corte():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "decisão humana obrigatória pendente" in texto or \
           "decisao humana obrigatoria pendente" in texto
    assert "reconvenção" in texto and "corte" in texto


def test_pergunta_somente_a_decisao_pendente_nao_ambas_por_habito():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "nunca ambas por hábito" in texto or "nunca as duas por hábito" in texto \
        or "nunca ambas por habito" in texto or "nunca as duas por habito" in texto


def test_nao_pergunta_de_novo_se_ja_respondido_no_pedido_inicial():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "não pergunte de novo" in texto or "nao pergunte de novo" in texto


# --------------------------------------------------- (J/K) retomada automática após gate
def test_retomada_automatica_apos_resposta_ao_gate():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "retome automaticamente" in texto or "retomar automaticamente" in texto \
        or "retomar automaticamente a execução" in texto
    assert "fail-closed" in texto


def test_fail_closed_pergunta_somente_o_necessario():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "pergunte somente o dado necessário" in texto or \
           "pergunte somente o dado necessario" in texto


# --------------------------------------------------- (N) resposta final mínima
def test_resposta_final_minima_sem_despejo_de_artefatos_internos():
    texto = _normalizado(CONTESTACAO_SKILL)
    secao11 = _secao(_texto(CONTESTACAO_SKILL), r"##\s*11\.\s*Modo de operação")
    secao11_norm = " ".join(secao11.lower().split())
    assert "resposta final" in secao11_norm
    assert "não despeje" in secao11_norm or "nao despeje" in secao11_norm


# --------------------------------------------------- (L) modo análise/consultivo preservados
def test_modos_analise_e_consultivo_distinguidos_de_producao():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "**análise**" in texto or "**analise**" in texto
    assert "**consultivo**" in texto
    assert "entrega intermediária é a resposta correta" in texto or \
           "entrega intermediaria e a resposta correta" in texto


def test_estrategista_distingue_acionamento_orquestrado_de_direto():
    texto = _texto(ESTRATEGISTA_SKILL)
    secao9 = _secao(texto, r"##\s*9\.\s*Depois da análise")
    secao9_norm = " ".join(secao9.lower().split())
    assert "contestacao" in secao9_norm  # referência à orquestradora
    assert "insumo interno" in secao9_norm
    assert "resposta final" in secao9_norm
    # comportamento antigo (entregar + sugerir próximo passo) preservado
    # apenas para o acionamento direto pelo usuário
    assert "acionada diretamente pelo usuário" in secao9 or \
           "acionada diretamente pelo usuario" in secao9.lower()


def test_estrategista_nao_entrega_proximo_passo_quando_orquestrada():
    texto = _texto(ESTRATEGISTA_SKILL)
    secao9 = _secao(texto, r"##\s*9\.\s*Depois da análise")
    # a primeira metade (acionamento pela orquestradora) não pode
    # instruir "sugira o próximo passo" — essa instrução deve estar
    # condicionada exclusivamente ao acionamento direto.
    pos_orquestradora = secao9.lower().find("acionada pela skill orquestradora")
    pos_direto = secao9.lower().find("acionada diretamente pelo usuário")
    assert pos_orquestradora != -1 and pos_direto != -1
    trecho_orquestrado = secao9[pos_orquestradora:pos_direto].lower()
    assert "sugira o próximo passo" not in trecho_orquestrado
    assert "próximo passo recomendado" not in trecho_orquestrado


# --------------------------------------------------- causa raiz auditada (Etapa 5.6, §14 do pedido de correção)
def test_causa_raiz_documentada_na_spec():
    texto = _normalizado(SPEC)
    assert "etapa 5.6" in texto
    assert "causa raiz" in texto


# --------------------------------------------------- escopo da correção
def test_escopo_da_correcao_e_apenas_orquestracao():
    texto = _normalizado(CONTESTACAO_SKILL)
    assert "correção corrige exclusivamente orquestração e entrega" in texto or \
           "esta seção corrige exclusivamente orquestração e entrega" in texto


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
