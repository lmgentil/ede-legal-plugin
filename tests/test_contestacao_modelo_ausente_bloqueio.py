#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contestacao_modelo_ausente_bloqueio.py — guarda estrutural do
hotfix pós-v0.11.0 (Etapa 5.11): "modelo oficial ausente ou `ede_doctor`
!= READY TO GENERATE é bloqueio absoluto da geração — não existe
fallback documental".

Achado real: em uso externo sem `templates/contestacao/modelo-oficial.docx`
instalado, a execução produziu "um documento Word autônomo" em vez de
abortar, apesar de o runtime (`scripts/gerar_contestacao.py`,
`scripts/ede_doctor.py`) já abortar corretamente quando efetivamente
invocado. A causa raiz estava na ausência, em `skills/contestacao/
SKILL.md`, de uma checagem de pré-flight e de uma proibição expressa de
gerar a peça por outro caminho — não no runtime. Este arquivo cobre as
duas frentes: (a) guardas textuais sobre o CONTEÚDO do `SKILL.md`
(mesmo padrão de tests/test_contestacao_skill_dependencies.py e
tests/test_gate_contestacao.py — semântico, não byte-a-byte de uma
frase inteira); (b) confirmação funcional de que o runtime Python
(não alterado por este hotfix) continua abortando corretamente sem o
Modelo Oficial.

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.

Uso:
  python tests/test_contestacao_modelo_ausente_bloqueio.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "contestacao" / "SKILL.md"
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"
CAMINHO_TEMPLATE_INEXISTENTE = str(
    BASE / "templates" / "contestacao" / "modelo-oficial-AUSENTE-TESTE.docx"
)

sys.path.insert(0, str(BASE / "scripts"))
import ede_doctor  # noqa: E402
from gerar_contestacao import gerar as _gerar_real  # noqa: E402


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalizado() -> str:
    """Minúsculo, com quebras de linha do prosa Markdown colapsadas —
    evita testes frágeis dependentes de como a frase quebra em linhas
    (instrução expressa deste hotfix: não transformar pontuação/quebra
    de linha em contrato acidental)."""
    return " ".join(_texto().lower().split())


def _resolver_juizo_stub(numero_processo, **_kwargs):
    """Mesmo padrão de tests/test_e2e_contestacao.py — a suíte nunca
    depende da API DataJud real. Só usado nos testes funcionais de
    regressão positiva (item 9 do pedido), onde o pipeline precisa
    avançar até um estágio posterior ao template ausente."""
    return {
        "numero_processo": numero_processo,
        "tribunal": "TJBA",
        "orgao_julgador_nome": "VARA DOS FEITOS DE RELAÇÕES DE CONSUMO",
        "orgao_julgador_codigo": 1,
        "codigo_municipio_ibge": 2910800,
        "comarca": "Feira de Santana",
        "juizo": "AO JUÍZO DA VARA DOS FEITOS DE RELAÇÕES DE CONSUMO DA COMARCA DE FEIRA DE SANTANA",
        "data_consulta": "2026-01-01T00:00:00+00:00",
    }


# --------------------------------------------------------- 1-2: pré-flight
def test_skill_exige_ede_doctor_no_preflight():
    texto = _normalizado()
    assert "ede_doctor" in texto, (
        f"{SKILL_PATH} não menciona ede_doctor.py — pré-flight não está "
        "operacionalizado no contrato do agente (achado do hotfix)")
    assert "pré-flight" in texto or "preflight" in texto, (
        f"{SKILL_PATH} não declara uma etapa de pré-flight")


def test_skill_exige_ready_to_generate():
    texto = _texto()
    assert "READY TO GENERATE" in texto, (
        f"{SKILL_PATH} não referencia o estado READY TO GENERATE de ede_doctor.py")


# --------------------------------------------------- 3-4: bloqueio absoluto
def test_ausencia_modelo_oficial_e_bloqueio_absoluto():
    texto = _normalizado()
    assert "bloqueio absoluto" in texto, (
        f"{SKILL_PATH} não declara bloqueio absoluto para ausência do modelo oficial")
    assert "modelo oficial ausente" in texto or "modelo-oficial.docx" in texto


def test_doctor_not_ready_e_bloqueio_absoluto():
    texto = _normalizado()
    # a mesma frase de bloqueio absoluto deve estar ligada tanto à ausência
    # do modelo quanto ao estado do ede_doctor — não apenas a um dos dois.
    assert "ede_doctor" in texto and "bloqueio absoluto" in texto
    assert "not ready" in texto or "!= ready to generate" in texto or \
           "não retornar" in texto or "não for" in texto, (
        f"{SKILL_PATH} não amarra o bloqueio absoluto ao estado NOT READY "
        "de ede_doctor.py, não só à ausência do arquivo")


# ------------------------------------------------- 5-6: fallback proibido
def test_skill_declara_ausencia_de_fallback_documental():
    texto = _normalizado()
    assert "fallback documental" in texto, (
        f"{SKILL_PATH} não contém a declaração normativa "
        "'não existe fallback documental'")
    assert "não existe" in texto or "nao existe" in texto


def test_host_nao_pode_gerar_por_mecanismo_alternativo():
    texto = _normalizado()
    # a proibição precisa nomear especificamente os mecanismos de desvio
    # citados no achado real (Skill genérica docx, python-docx, XML manual)
    # — não basta uma proibição genérica e vaga.
    assert "mecanismo alternativo" in texto or "outro mecanismo" in texto or \
           "outro caminho" in texto
    assert "docx" in texto and "python-docx" in texto, (
        f"{SKILL_PATH} não nomeia explicitamente a Skill genérica docx e "
        "python-docx como mecanismos de bypass vedados")


def test_bloqueio_nao_e_proibicao_generica_de_auxilio_juridico():
    """Instrução expressa do pedido: não proibir genericamente o Claude de
    prestar auxílio jurídico — o bloqueio é específico ao MODO PRODUÇÃO
    desta Skill."""
    texto = _normalizado()
    assert "não é uma proibição genérica" in texto or \
           "nao e uma proibicao generica" in texto, (
        f"{SKILL_PATH} não delimita expressamente o escopo do bloqueio "
        "(risco de generalização indevida para fora do MODO PRODUÇÃO)")


# ------------------------------------------------------- 7-8: urgência
def test_urgencia_e_prazo_nao_modificam_bloqueio():
    texto = _normalizado()
    assert "urgência não é exceção" in texto or "urgencia nao e excecao" in texto
    for marcador in ("prazo vencendo amanhã", "prazo vencendo hoje"):
        assert marcador in texto, f"{SKILL_PATH} não cobre o cenário: {marcador!r}"


def test_pedidos_explicitos_de_fallback_nao_modificam_bloqueio():
    texto = _normalizado()
    for frase in (
        "faça mesmo sem o modelo",
        "gere provisoriamente",
        "depois eu coloco no modelo",
        "faça em word normal",
        "não precisa usar o template",
    ):
        assert frase in texto, (
            f"{SKILL_PATH} não cobre textualmente o pedido de bypass: {frase!r}")


# ------------------------------------------- 9-10: runtime não alterado
def test_runtime_continua_abortando_sem_template():
    """Confirma que o runtime (não tocado por este hotfix) mantém o
    comportamento fail-closed provado na auditoria — mesmo mecanismo de
    simulação da auditoria (caminho inexistente via --template), sem
    tocar no asset protegido real (ADR-0009)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deve_ser_criado.docx"
        r = _gerar_real(FIXTURES / "happy_path", saida,
                         template=CAMINHO_TEMPLATE_INEXISTENTE,
                         resolver_juizo_fn=_resolver_juizo_stub)
        assert r["status"] == "PIPELINE_ABORTED", r
        assert r["stage"] == "contexto_institucional", r
        assert not saida.exists(), "DOCX não pode ser criado com template ausente"


def test_ede_doctor_continua_not_ready_sem_modelo():
    r = ede_doctor.executar_diagnostico(modelo_path=CAMINHO_TEMPLATE_INEXISTENTE)
    assert r["ready"] is False, r
    assert "template:modelo-oficial.docx" in r["obrigatorias_falhando"], r


# --------------------------------------- 11: regressão positiva (ambiente OK)
def test_ambiente_regularizado_ready_nao_fica_bloqueado():
    """Regressão positiva (item 9 do pedido): modelo presente + ede_doctor
    READY continua permitindo o fluxo normal. Reaproveita o template real
    já instalado localmente (mesmo padrão de skip de
    tests/test_e2e_contestacao.py — nunca falha "vermelho" só porque o
    asset externo não está instalado nesta máquina)."""
    modelo_real = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
    if not modelo_real.exists():
        print("SKIP: modelo-oficial.docx não instalado localmente (ADR-0009) "
              "— regressão positiva não verificável nesta máquina.")
        return
    r = ede_doctor.executar_diagnostico()
    assert r["ready"] is True, (
        f"ambiente com modelo oficial instalado deveria estar READY: {r['obrigatorias_falhando']}")


# ----------------------------------------------------- 12: §11 reconhece
def test_secao_11_reconhece_interrupcao_por_modelo_ausente():
    texto = _texto()
    idx_11 = texto.find("## 11.")
    assert idx_11 != -1, f"seção '## 11.' não encontrada em {SKILL_PATH}"
    secao_11 = texto[idx_11:].lower()
    assert "0a" in secao_11 or "modelo oficial ausente" in secao_11, (
        "§11 não referencia a interrupção por modelo ausente/§0A")


# --------------------------------- 13: entrega contínua subordinada ao pré-flight
def test_entrega_continua_subordinada_ao_preflight():
    texto = _texto()
    idx_11 = texto.find("## 11.")
    assert idx_11 != -1
    secao_11 = texto[idx_11:]
    idx_checkpoint = secao_11.find("execução contínua, sem checkpoint")
    assert idx_checkpoint != -1, (
        "subseção 'execução contínua, sem checkpoint' não encontrada em §11")
    trecho = secao_11[idx_checkpoint:idx_checkpoint + 400].lower()
    assert "pré-flight" in trecho or "preflight" in trecho, (
        "a regra de execução contínua/sempre entregar o DOCX não está "
        "explicitamente subordinada ao pré-flight de §0A")


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
