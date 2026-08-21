#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_pacote_distribuicao.py — Fase 8 (Distribuição): lista os arquivos
efetivamente rastreados pelo git (= o que viaja com o plugin quando
instalado via marketplace, já que o `source` do plugin é a raiz do
repositório) e falha se algum padrão proibido aparecer.

Roda contra `git ls-files` — o que está no índice, não o que está no
disco (arquivo gitignored no disco não entra aqui, é exatamente o ponto).

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.
"""
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

PADROES_PROIBIDOS = {
    r"(^|/)\.env$": "segredo real (.env)",
    r"\.key$": "chave privada",
    r"\.pem$": "certificado/chave privada",
    r"(^|/)workspace/": "workspace local de elaboração de peças (CLAUDE.md §19)",
    r"(^|/)processos_reais/": "documentos processuais reais (CLAUDE.md §18)",
    r"(^|/)rag/jurisprudencia/": "jurisprudência real com dados de cliente (PEND-002/ADR-0006)",
    r"Contestacao - Skill\.skill$": "artefato-fonte legado (Fase 6 — já extraído em skills/)",
    r"modelo-oficial\.docx$": "template institucional real (ADR-0006 — asset privado, não distribuído)",
    r"\.textos_varredura/": "textos brutos de peças reais (ADR-0006)",
}


def arquivos_rastreados() -> list:
    r = subprocess.run(["git", "ls-files"], cwd=BASE, capture_output=True,
                        text=True, check=True)
    return [linha for linha in r.stdout.splitlines() if linha.strip()]


def encontrar_violacoes(arquivos: list) -> list:
    violacoes = []
    for caminho in arquivos:
        for padrao, motivo in PADROES_PROIBIDOS.items():
            if re.search(padrao, caminho):
                violacoes.append((caminho, motivo))
    return violacoes


def test_pacote_nao_contem_padroes_proibidos():
    arquivos = arquivos_rastreados()
    assert arquivos, "git ls-files não retornou nada — rodando fora de um repositório git?"
    violacoes = encontrar_violacoes(arquivos)
    assert not violacoes, "arquivo(s) proibido(s) rastreado(s) pelo git:\n" + "\n".join(
        f"  - {c} ({m})" for c, m in violacoes)


def test_gitignore_cobre_os_ativos_sensiveis_conhecidos():
    gitignore = (BASE / ".gitignore").read_text(encoding="utf-8")
    for trecho in (".env", "rag/jurisprudencia/", "modelo-oficial.docx", ".cache/"):
        assert trecho in gitignore, f".gitignore não cobre {trecho!r}"


# Etapa 5.5 (decisão expressa do projeto — SUBSTITUI a orientação
# anterior de manter a chave DataJud fora do repositório): a chave
# PÚBLICA do DataJud é versionada num único ponto canônico
# (DATAJUD_API_KEY_PADRAO em scripts/datajud_client.py) — não é mais
# tratada como "possível segredo vazado" pelo secret scan deste projeto.
# Testes A-F desta seção substituem os testes obsoletos que exigiam
# ausência da chave no repositório.
sys.path.insert(0, str(BASE / "scripts"))


def _importar_datajud_client():
    import datajud_client
    return datajud_client


# A. chave existe no ponto canônico.
def test_A_chave_datajud_existe_no_ponto_canonico():
    dj = _importar_datajud_client()
    assert isinstance(dj.DATAJUD_API_KEY_PADRAO, str) and len(dj.DATAJUD_API_KEY_PADRAO) > 20


# B. chave não está duplicada em vários arquivos rastreados.
def test_B_chave_datajud_nao_duplicada_em_arquivos_rastreados():
    dj = _importar_datajud_client()
    chave = dj.DATAJUD_API_KEY_PADRAO
    arquivos = arquivos_rastreados()
    achados = []
    for caminho in arquivos:
        completo = BASE / caminho
        if not completo.is_file():
            continue
        try:
            texto = completo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if chave in texto:
            achados.append(caminho)
    assert achados == ["scripts/datajud_client.py"], (
        f"chave DataJud deveria aparecer em exatamente um arquivo "
        f"(scripts/datajud_client.py) — encontrada em: {achados}")


# C. cliente DataJud utiliza o ponto canônico (checagem estrutural do
# código-fonte, não só do valor em memória — garante que a resolução da
# chave realmente passa por DATAJUD_API_KEY_PADRAO).
def test_C_cliente_datajud_usa_o_ponto_canonico():
    codigo = (BASE / "scripts" / "datajud_client.py").read_text(encoding="utf-8")
    assert "DATAJUD_API_KEY_PADRAO" in codigo
    assert re.search(r"api_key\s*=\s*api_key\s+or\s+os\.environ\.get\(.DATAJUD_API_KEY.\)\s+or\s+DATAJUD_API_KEY_PADRAO", codigo)


# D. ausência da chave canônica (e de qualquer override) gera erro claro.
def test_D_ausencia_da_chave_canonica_gera_erro_claro():
    dj = _importar_datajud_client()
    original = dj.DATAJUD_API_KEY_PADRAO
    valor_env_original = __import__("os").environ.pop("DATAJUD_API_KEY", None)
    dj.DATAJUD_API_KEY_PADRAO = ""
    try:
        try:
            dj.resolver_orgao_julgador("8000001-11.2026.8.05.0080", api_key=None,
                                        cache_path=Path(__import__("tempfile").mkdtemp()) / "c.json")
            assert False, "deveria ter levantado JuizoResolutionError"
        except dj.JuizoResolutionError as e:
            assert "chave" in e.motivo.lower()
    finally:
        dj.DATAJUD_API_KEY_PADRAO = original
        if valor_env_original is not None:
            __import__("os").environ["DATAJUD_API_KEY"] = valor_env_original


# E. erro de autenticação não gera fallback de JUIZO — levanta erro
# marcado (TAG_ERRO_AUTENTICACAO), nunca retorna um resultado parcial/
# inventado nem tenta buscar/gerar chave nova sozinho.
def test_E_erro_de_autenticacao_nao_gera_fallback_de_juizo():
    dj = _importar_datajud_client()
    original = dj._post_json

    def _post_json_401(url, body, headers, timeout, tentativas, nome_servico):
        # simula o que _fazer_requisicao já faz internamente ao receber
        # HTTP 401/403: converte para JuizoResolutionError marcado, nunca
        # propaga a HTTPError crua.
        raise dj.JuizoResolutionError(
            f"{nome_servico} rejeitou a credencial (HTTP 401: Unauthorized) — "
            f"a chave pública pode ter sido rotacionada pelo CNJ.",
            codigo=dj.TAG_ERRO_AUTENTICACAO)

    dj._post_json = _post_json_401
    try:
        try:
            resultado = dj.resolver_orgao_julgador(
                "8000001-11.2026.8.05.0080", api_key="qualquer",
                cache_path=Path(__import__("tempfile").mkdtemp()) / "c.json")
            assert False, f"deveria ter levantado JuizoResolutionError, retornou: {resultado!r}"
        except dj.JuizoResolutionError as e:
            assert e.codigo == dj.TAG_ERRO_AUTENTICACAO
            assert "rotacionada" in e.motivo or "credencial" in e.motivo.lower()
    finally:
        dj._post_json = original


# F. nenhuma OUTRA credencial/secret privado é versionada (a chave
# pública DataJud é exceção expressa — não é o que este teste procura).
_PADROES_OUTROS_SEGREDOS = {
    r"AKIA[0-9A-Z]{16}": "possível AWS Access Key ID",
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----": "chave privada PEM",
    r"sk-[A-Za-z0-9]{20,}": "possível API key estilo OpenAI/Anthropic",
    r"ghp_[A-Za-z0-9]{30,}": "possível GitHub personal access token",
}


def test_F_nenhuma_outra_credencial_privada_versionada():
    arquivos = arquivos_rastreados()
    achados = []
    for caminho in arquivos:
        completo = BASE / caminho
        if not completo.is_file():
            continue
        try:
            texto = completo.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for padrao, motivo in _PADROES_OUTROS_SEGREDOS.items():
            if re.search(padrao, texto):
                achados.append((caminho, motivo))
    assert not achados, f"possível credencial privada em arquivo rastreado: {achados}"


def test_nenhum_docx_solto_rastreado():
    # regra ampla do .gitignore (/*.docx) — confere que nenhum .docx da
    # raiz entrou no índice por engano em algum momento.
    arquivos = arquivos_rastreados()
    docx_na_raiz = [a for a in arquivos if a.endswith(".docx") and "/" not in a]
    assert not docx_na_raiz, f".docx solto na raiz rastreado pelo git: {docx_na_raiz}"


def test_modelo_oficial_nao_esta_no_historico_git():
    # .gitignore só protege commits futuros — não remove algo já
    # commitado no passado. Confere o HISTÓRICO inteiro, não só o índice
    # atual (consolidação pós-Fase 8: decisão de template externo
    # encerrada — o arquivo nunca pode ter entrado no repositório).
    caminho = "templates/contestacao/modelo-oficial.docx"
    r = subprocess.run(["git", "log", "--all", "--oneline", "--", caminho],
                        cwd=BASE, capture_output=True, text=True, check=True)
    assert not r.stdout.strip(), (
        f"{caminho} aparece no histórico git (commit(s) abaixo) — .gitignore "
        f"não remove isso retroativamente, precisa de saneamento específico "
        f"autorizado:\n{r.stdout}")


def test_modelo_oficial_e_asset_externo_nao_de_instalacao_base():
    # Invariante consolidada (decisão definitiva, não mais em aberto):
    # o template institucional real NUNCA é tracked/distribuído/asset de
    # marketplace, e sua ausência não pode reprovar uma instalação base
    # do plugin — só bloqueia especificamente a geração do DOCX final.
    caminho = "templates/contestacao/modelo-oficial.docx"

    # NÃO TRACKED / NÃO DISTRIBUÍDO
    assert caminho not in arquivos_rastreados()

    # NÃO MARKETPLACE ASSET — não referenciado no manifesto do marketplace
    marketplace = (BASE / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    assert "modelo-oficial" not in marketplace

    # NÃO NECESSÁRIO PARA INSTALAÇÃO BASE — validar_instalacao.py trata
    # este item como opcional, não obrigatório.
    sys.path.insert(0, str(BASE / "scripts"))
    from validar_instalacao import validar_instalacao  # noqa: E402
    r = validar_instalacao(BASE)
    item = next(c for c in r["checagens"] if c["item"].startswith("template:modelo-oficial.docx"))
    assert item["obrigatorio"] is False

    # NECESSÁRIO PARA GERAÇÃO DOCX INSTITUCIONAL — fail closed, explícito,
    # quando de fato ausente (demonstrado com caminho inexistente).
    sys.path.insert(0, str(BASE / "scripts"))
    from docx_template_engine import gerar_peca  # noqa: E402
    resultado = gerar_peca(str(BASE / "templates" / "contestacao" / "___inexistente___.docx"),
                            str(BASE / "templates" / "contestacao" / "schema.json"),
                            {}, str(BASE / "___nao_deve_ser_criado___.docx"))
    assert resultado["status"] == "FALHOU"
    assert resultado["etapa"] == "template"
    assert not (BASE / "___nao_deve_ser_criado___.docx").exists()


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
    sys.exit(0)
