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


# Teste L (INV-JUIZO-DATAJUD): nenhuma API key literal em arquivo
# rastreado. Não compara contra o valor real da chave (isso a colocaria
# no repositório) — varre pelo FORMATO do header de autenticação da API
# Pública DataJud ("Authorization: APIKey <valor>") seguido de um valor
# literal (não uma interpolação de variável, que nunca casa aqui —
# f"APIKey {api_key}" tem '{' logo depois, fora da classe de caracteres).
_PADRAO_APIKEY_LITERAL = re.compile(r"APIKey [A-Za-z0-9+/]{15,}={0,2}")


def test_L_nenhuma_apikey_datajud_literal_em_arquivo_rastreado():
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
        if _PADRAO_APIKEY_LITERAL.search(texto):
            achados.append(caminho)
    assert not achados, f"possível API key literal (padrão DataJud) em arquivo rastreado: {achados}"


def test_L_datajud_api_key_nunca_hardcoded_no_client():
    codigo = (BASE / "scripts" / "datajud_client.py").read_text(encoding="utf-8")
    # a única leitura de valor deve vir de os.environ/parâmetro — nunca de
    # uma string literal atribuída à variável.
    assert 'os.environ.get("DATAJUD_API_KEY")' in codigo
    assert not re.search(r'DATAJUD_API_KEY"?\s*[:=]\s*["\'][^"\']{10,}', codigo)


def test_L_env_example_datajud_api_key_sem_valor():
    conteudo = (BASE / ".env.example").read_text(encoding="utf-8")
    assert "DATAJUD_API_KEY" in conteudo
    for linha in conteudo.splitlines():
        if linha.startswith("DATAJUD_API_KEY="):
            assert linha.strip() == "DATAJUD_API_KEY=", f"valor não vazio em .env.example: {linha!r}"


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
