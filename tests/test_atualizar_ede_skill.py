#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_atualizar_ede_skill.py — Etapa 5.9-I (Gate Final): guarda estrutural
do contrato de skills/atualizar-ede/SKILL.md como VERIFICADOR DE VERSÃO
puro, incluindo:

- a distinção obrigatória entre versão de desenvolvimento (`main`) e
  versão oficialmente publicada (última GitHub Release não-draft/
  não-prerelease com tag SemVer válida) — ver ADR-0008, seção revisada,
  e SPEC-0001 REQ-039;
- a REVOGAÇÃO da exigência de asset `.zip` para considerar uma Release
  válida (decisão descartada no Gate Final, antes de qualquer commit).

Skill é prosa/instruções em Markdown (não script executável): o teste
verifica o CONTEÚDO do arquivo — mesmo padrão de
tests/test_contestacao_skill_dependencies.py — sem framework.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_PATH = BASE / "skills" / "atualizar-ede" / "SKILL.md"
SPEC_PATH = BASE / "docs" / "specs" / "SPEC-0001.md"


def _texto() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} não existe"
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalizado(texto: str) -> str:
    # junta linhas quebradas de um mesmo parágrafo/blockquote em uma string
    # contígua, removendo o marcador "> " do início de linha de resposta.
    sem_marcador = re.sub(r"^>\s?", "", texto, flags=re.M)
    return " ".join(sem_marcador.split())


def _linhas_resposta(texto: str) -> list:
    # linhas de exemplo de resposta ao advogado (blockquote "> ...").
    return [l for l in texto.splitlines() if l.strip().startswith(">")]


def _spec() -> str:
    assert SPEC_PATH.exists(), f"{SPEC_PATH} não existe"
    return SPEC_PATH.read_text(encoding="utf-8")


# --------------------------------------------------- A: Release 0.10.1 + instalada 0.10.0 → disponível
def test_atualizacao_disponivel_quando_publicada_maior():
    texto = _texto()
    assert "Há uma nova versão do EDE Legal Plugin disponível." in texto
    assert "Versão instalada: X" in texto
    assert "Versão mais recente: Y" in texto


# --------------------------------------------------- B: Release 0.10.1 + instalada 0.10.1 → atualizado
def test_atualizado_quando_versoes_iguais():
    texto = _texto()
    assert "EDE Legal Plugin está atualizado." in texto
    assert "Versão instalada: X" in texto
    assert "Versão mais recente: X" in texto
    assert "Nenhuma ação necessária." in texto


# --------------------------------------------------- C: instalada 0.10.2 + Release 0.10.1 → inconsistência
def test_instalada_maior_reporta_inconsistencia_nao_downgrade():
    texto = _normalizado(_texto())
    assert "A versão instalada do EDE é superior à última versão oficial publicada." in texto
    assert "Instalada: X" in texto
    assert "Última versão publicada: Y." in texto
    assert "Nenhuma atualização é recomendada." in texto
    assert "downgrade" in texto.lower()


# --------------------------------------------------- D: main/VERSION maior → main não interfere
def test_distingue_versao_desenvolvimento_de_publicada():
    texto = _texto()
    assert "VERSÃO DE DESENVOLVIMENTO" in texto
    assert "VERSÃO OFICIALMENTE PUBLICADA" in texto
    assert "nunca" in texto.lower() and "main" in texto


def test_nao_consulta_main_version_raw():
    # a fonte antiga (raw.githubusercontent.com/.../main/VERSION) só pode
    # aparecer na prosa dizendo "nunca consulte isto" — nunca dentro de um
    # bloco ```text (é assim que o endpoint realmente consultado, a API de
    # Releases, é apresentado).
    texto = _texto()
    blocos_text = re.findall(r"```text\n(.*?)```", texto, re.S)
    assert blocos_text, "nenhum bloco ```text encontrado"
    assert not any("raw.githubusercontent.com" in b for b in blocos_text)
    assert any(
        "https://api.github.com/repos/lmgentil/ede-legal-plugin/releases/latest" in b
        for b in blocos_text
    )


# --------------------------------------------------- E: Release draft → não considerada oficial
def test_release_draft_nao_e_considerada_oficial():
    texto = _texto()
    assert "`draft: true`" in texto
    assert "não houvesse Release válida" in texto


# --------------------------------------------------- F: Release prerelease → não considerada estável
def test_release_prerelease_nao_e_considerada_estavel():
    texto = _texto()
    assert "`prerelease: true`" in texto
    normalizado = " ".join(texto.split())
    assert "não-draft e não-prerelease" in normalizado


# --------------------------------------------------- G: tag SemVer inválida → fail-closed
def test_tag_semver_invalida_cai_no_erro_generico():
    texto = _normalizado(_texto())
    assert "tag_name` que não valida como" in texto or "tag_name que não valida como" in texto
    assert "Não foi possível verificar a versão do EDE neste momento. Tente novamente mais tarde." in texto


# --------------------------------------------------- H: releases/latest 404 → nenhuma Release publicada
def test_nenhuma_release_publicada_e_estado_tratado_nao_como_falha():
    texto = _texto()
    assert "Não há versão oficial publicada disponível para comparação neste" in texto
    assert "404" in texto  # documentado como o estado real auditado nesta revisão
    # mensagem distinta da mensagem de erro genérica (§3.3) — nunca a mesma frase
    assert "Não há versão oficial publicada disponível para comparação neste momento." != \
        "Não foi possível verificar a versão do EDE neste momento. Tente novamente mais tarde."


# --------------------------------------------------- I: GitHub indisponível → erro controlado
def test_github_indisponivel_erro_controlado():
    texto = _texto()
    assert "Não foi possível verificar a versão do EDE neste momento. Tente" in texto
    assert "novamente mais tarde." in texto


# --------------------------------------------------- versão instalada indeterminável → erro controlado
def test_versao_instalada_indeterminavel_erro_controlado():
    texto = _texto()
    assert "Não foi possível identificar com segurança a versão instalada do EDE." in texto


# --------------------------------------------------- SemVer numérico (não string) — delegado
def test_menciona_comparacao_numerica_nao_lexicografica():
    texto = _texto().lower()
    assert "nunca" in texto and "lexicográfica de string" in texto
    assert "0.10.10" in texto and "0.10.9" in texto


# --------------------------------------------------- J: link e versão vêm da mesma resposta (mesma Release)
def test_link_e_versao_vem_da_mesma_resposta_json():
    texto = _texto().lower()
    assert "html_url" in texto
    assert "mesma resposta" in texto or "mesma release" in texto
    assert "nunca reconstrua" in texto or "nunca link fixo" in texto


def test_resposta_nao_hardcoda_link_de_releases_latest_como_destino_final():
    # /releases/latest é usado só como ENDPOINT DE CONSULTA (API), nunca
    # como o link final entregue ao advogado — esse é sempre o html_url
    # dinâmico da resposta.
    texto = _texto()
    assert "https://github.com/lmgentil/ede-legal-plugin/releases/latest" not in texto


# --------------------------------------------------- K: nenhuma resposta menciona ZIP obrigatoriamente
def test_nenhuma_resposta_menciona_zip_ou_asset():
    texto = _texto()
    linhas = _linhas_resposta(texto)
    assert linhas, "nenhum bloco de resposta de exemplo encontrado"
    proibidos = ("zip", "asset", "/plugin")
    for l in linhas:
        l_lower = l.lower()
        for termo in proibidos:
            assert termo not in l_lower, f"resposta de exemplo menciona {termo!r}: {l!r}"


# --------------------------------------------------- L: nenhuma lógica exige asset .zip
def test_nenhuma_logica_exige_asset_zip():
    texto = _texto()
    # formulações da exigência REVOGADA não podem voltar a aparecer como
    # regra vigente (só podem aparecer no §3 como histórico do que foi
    # descartado, o que os testes abaixo verificam explicitamente).
    assert "só existe pacote oficial disponível se" not in texto
    assert "pelo menos um item cujo nome termine em" not in texto
    assert "revogada" in texto.lower() or "revogado" in texto.lower()
    assert "ZIP oficial não faz parte da arquitetura" in " ".join(texto.split())


def test_nao_tenta_self_update():
    texto = _texto().lower()
    assert "tenta se autoatualizar" in texto  # listado explicitamente como proibido
    assert "git pull" in texto  # também listado como proibido


# --------------------------------------------------- não depende de marketplace
def test_marketplace_nunca_e_fonte_de_verdade():
    texto = _texto()
    assert "Marketplace nunca é fonte de verdade" in texto
    assert "loaded" in texto and "synced" in texto


# --------------------------------------------------- não depende de scope
def test_nao_identifica_nem_pergunta_escopo():
    texto = _texto().lower()
    assert "identifica ou pergunta escopo" in texto
    assert "--scope" not in texto
    assert "scope_detectado" not in texto


# --------------------------------------------------- não depende de CLAUDE_PLUGIN_ROOT via Bash
def test_nao_depende_de_claude_plugin_root_via_bash():
    texto = _texto()
    # allowed-tools do frontmatter não inclui Bash: nenhuma ferramenta de
    # shell fica disponível para esta Skill em tempo de execução — a
    # menção textual a CLAUDE_PLUGIN_ROOT (explicando que NÃO é preciso)
    # é aceitável, um `echo $CLAUDE_PLUGIN_ROOT` executado via Bash não é.
    frontmatter = texto.split("---")[1]
    assert "Bash" not in frontmatter
    assert "echo $" not in texto and "echo \"$" not in texto


# --------------------------------------------------- contrato único Code/Cowork
def test_contrato_unico_claude_code_e_cowork():
    texto = _texto()
    assert "Claude Code e Cowork — mesmo contrato" in texto
    normalizado = " ".join(texto.lower().split())
    assert "nunca duplique o fluxo de verificação por ambiente" in normalizado


# --------------------------------------------------- M: versão instalada embutida e sincronizada
def test_versao_instalada_embutida_e_sincronizada_com_version_e_plugin_json():
    texto = _texto()
    m = re.search(r"Versão instalada neste pacote: `([0-9]+\.[0-9]+\.[0-9]+)`", texto)
    assert m, "marcador de versão instalada não encontrado no formato esperado"
    versao_skill = m.group(1)

    versao_version_file = (BASE / "VERSION").read_text(encoding="utf-8").strip()
    versao_plugin_json = json.loads(
        (BASE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]

    assert versao_skill == versao_version_file == versao_plugin_json, (
        f"versão desincronizada: SKILL.md={versao_skill!r} "
        f"VERSION={versao_version_file!r} plugin.json={versao_plugin_json!r}"
    )


# --------------------------------------------------- N: SemVer 0.10.10 > 0.10.9 (comparar_versao.py real)
def test_comparar_versao_0_10_10_maior_que_0_10_9():
    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    from comparar_versao import comparar_semver  # noqa: E402
    assert comparar_semver("0.10.10", "0.10.9") == 1
    assert comparar_semver("0.10.9", "0.10.10") == -1


# --------------------------------------------------- O: REQ-039 corresponde ao contrato atual
def test_req_039_reflete_verificador_de_versao_sem_zip():
    spec = _spec()
    m = re.search(r"## REQ-039.*?(?=\n## |\n# )", spec, re.S)
    assert m, "seção REQ-039 não encontrada em SPEC-0001.md"
    trecho = m.group(0)

    assert "VERIFICADOR DE VERSÃO" in trecho
    assert "oficialmente publicada" in trecho.lower()
    assert "não deverá" in trecho.lower() and "self-update" in trecho.lower()
    assert "ZIP oficial não é" in trecho or "não verifica, não exige nem menciona asset" in trecho

    # a formulação antiga ("atualizar somente se necessário" como item do
    # fluxo ATUAL) e a exigência de ZIP (revogada) não podem aparecer como
    # comportamento vigente — só dentro de blocos de histórico rotulados.
    blocos_historico = [mo.start() for mo in re.finditer(r"\*\*Histórico", trecho)]
    assert blocos_historico, "seção precisa registrar o(s) histórico(s) das versões anteriores"
    fora_do_historico = trecho[:blocos_historico[0]]
    assert "atualizar somente se necessário" not in fora_do_historico.lower()
    assert "pacote ZIP do EDE como asset" not in fora_do_historico
    assert "exigir" not in fora_do_historico.lower() or ".zip" not in fora_do_historico.lower()


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
