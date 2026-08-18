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
    for trecho in (".env", "rag/jurisprudencia/", "modelo-oficial.docx"):
        assert trecho in gitignore, f".gitignore não cobre {trecho!r}"


def test_nenhum_docx_solto_rastreado():
    # regra ampla do .gitignore (/*.docx) — confere que nenhum .docx da
    # raiz entrou no índice por engano em algum momento.
    arquivos = arquivos_rastreados()
    docx_na_raiz = [a for a in arquivos if a.endswith(".docx") and "/" not in a]
    assert not docx_na_raiz, f".docx solto na raiz rastreado pelo git: {docx_na_raiz}"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
    sys.exit(0)
