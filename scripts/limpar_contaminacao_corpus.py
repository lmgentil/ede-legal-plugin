#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/limpar_contaminacao_corpus.py — remoção determinística do
artefato de rodapé/marca d'água "Uso Interno CPFL" do corpus
rag/chunks_REN1000/ (Gate 6.5-B3, auditoria de higiene de corpus).

ACHADO: a fonte usada para gerar o corpus de REN ANEEL 1000/2021 era uma
cópia de trabalho interna da CPFL (distribuidora de energia), carimbada
"Uso Interno CPFL" em toda página — o texto extraído herdou o carimbo
interleavado entre linhas de corpo, em TODOS os 67 arquivos do diploma
(256 ocorrências), nunca nos outros 5 diplomas.

VERIFICAÇÃO ANTES DE LIMPAR (Gate 6.5-B3 §11): inspeção manual de
amostras (rag/chunks_REN1000/TII_C07.md, §4º e inciso XII do art. 598 —
o capítulo central "Dos Procedimentos Irregulares") confirmou que a
marca é artefato PURAMENTE ADITIVO da extração PDF→texto: ela cai
exatamente na quebra de página/linha, interrompendo uma frase que
CONTINUA no parágrafo seguinte — nunca substitui, corrompe ou remove
texto legislativo. A reconstrução (remover a marca + reunir as duas
metades da frase) produz texto idêntico, palavra por palavra, ao padrão
de construção paralela já presente no mesmo artigo (ex.: inciso X e
inciso XII do art. 598 têm a MESMA estrutura sintática uma vez
reconstituído). Isto é achado de INSPEÇÃO, não presunção — reproduzível
lendo o arquivo antes/depois deste script.

ALGORITMO (determinístico, sem heurística jurídica):
  1. Parágrafos são blocos separados por linha em branco (`\n\n`) —
     mesma convenção Markdown já usada em todo o corpus.
  2. Se um parágrafo TERMINA com a marca (ignorando espaço em branco):
     remove a marca.
  3. Se o texto resultante NÃO termina em pontuação final de frase
     (`. ; : ! ?`), a quebra de parágrafo ali é artefato da marca, não
     um parágrafo novo de verdade — o próximo parágrafo é UNIDO ao
     atual (uma única junção por ocorrência; a marca nunca aparece duas
     vezes seguidas nos dados reais, verificado).
  4. Se o texto resultante JÁ termina em pontuação final, a marca só
     encerrava uma frase já completa — a quebra de parágrafo é mantida
     como estava.

Este script NUNCA toca:
  - qualquer outro diploma (CPC/CC/CDC/L8987/L9427) — nenhum tem a
    contaminação (verificado, Gate 6.5-B3 §11);
  - qualquer arquivo fora de rag/chunks_REN1000/;
  - conteúdo legislativo (números de artigo, incisos, valores) — só a
    string literal do carimbo e a junção de parágrafo que ela quebrou.

Uso (idempotente — rodar de novo sobre corpus já limpo não altera nada):

    python scripts/limpar_contaminacao_corpus.py [--dry-run]

Após rodar, regenerar rag/corpus_manifest.json (sha256 do diploma
REN1000 e sha256_total mudam; contagem de arquivos e total_chunks NÃO
mudam — nenhum arquivo é criado/removido, só reescrito)."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIRETORIO_ALVO = BASE / "rag" / "chunks_REN1000"

MARCA = "Uso Interno CPFL"
_RE_MARCA_FINAL = re.compile(r"[ \t]*" + re.escape(MARCA) + r"[ \t]*$")
_RE_PONTUACAO_FINAL = re.compile(
    r"(?:[.;:!?]|;\s*(?:e|ou))\s*$", re.IGNORECASE
)
"""Fim de frase OU fim de item de enumeração legislativa: incisos/alíneas
terminam rotineiramente em "; e" / "; ou" (conjunção/alternância entre
itens de uma lista), nunca em ponto — achado real deste gate: a primeira
versão deste regex (só `.;:!?`) tratava "...irregularidade; ou" como
"não terminado", fundindo o inciso IV ao V seguinte (dois incisos
distintos e completos) como se a marca tivesse cortado a frase no meio.
"; e"/"; ou" É fim de item legítimo, igual a ponto final — nunca funde."""

_RE_TITULO_SECAO = re.compile(
    r"^(T[íi]tulo|Cap[íi]tulo|Se[çc][ãa]o|Subse[çc][ãa]o|Anexo|Do\s|Da\s|Dos\s|Das\s)",
    re.IGNORECASE,
)


def _e_titulo_ou_nao_prosa(paragrafo: str) -> bool:
    """Segunda exceção descoberta por inspeção (Gate 6.5-B3 §11): título
    de Capítulo/Seção ("Da Conexão", "Das Disposições Gerais") nunca
    termina em pontuação de frase, mas TAMBÉM não é frase cortada — é uma
    unidade completa por natureza. A primeira versão deste algoritmo
    fundia 18 títulos de seção ao artigo seguinte só por não terminarem
    em ponto, corrompendo o título dentro do corpo do artigo. Mesma
    lógica protege fragmentos não-textuais (linha de pontos/sublinhado de
    formulário-anexo, "(NR)") — menos de 3 letras no total não é uma
    frase capaz de continuar."""
    texto = paragrafo.strip()
    if sum(c.isalpha() for c in texto) < 3:
        return True
    if (
        _RE_TITULO_SECAO.match(texto)
        and "." not in texto
        and ";" not in texto
        and len(texto.split()) <= 12
    ):
        return True
    return False


def limpar_texto(texto: str, permitir_juncao: bool = True) -> str:
    """Aplica o algoritmo descrito no docstring do módulo a um único
    arquivo de chunk (texto completo, incluindo frontmatter — a marca
    nunca aparece dentro do frontmatter YAML, só no corpo).

    `permitir_juncao=False` (Título III — Disposições Finais e
    Transitórias, `TIII_*.md`) só remove a marca, nunca funde parágrafos:
    achado real deste gate — essa parte do diploma contém formulário-
    anexo (linha de assinatura, campo em branco, cabeçalho de ANEXO), sem
    estrutura de frase regular; a heurística de fusão (correta para
    artigos/incisos do corpo normativo) produziu ao menos um caso de
    fusão incorreta ali ("ASSINATURA ___" + "ANEXO IV — ..."). Preferir
    uma quebra de parágrafo cosmética residual a arriscar amálgama de
    conteúdo não relacionado."""
    paragrafos = texto.split("\n\n")
    resultado: list[str] = []
    i = 0
    while i < len(paragrafos):
        paragrafo = paragrafos[i]
        m = _RE_MARCA_FINAL.search(paragrafo)
        if m is None:
            resultado.append(paragrafo)
            i += 1
            continue

        sem_marca = paragrafo[: m.start()].rstrip()
        if (
            not permitir_juncao
            or _RE_PONTUACAO_FINAL.search(sem_marca)
            or _e_titulo_ou_nao_prosa(sem_marca)
            or i + 1 >= len(paragrafos)
        ):
            resultado.append(sem_marca)
            i += 1
            continue

        proximo = paragrafos[i + 1]
        resultado.append(f"{sem_marca} {proximo.lstrip()}")
        i += 2

    return "\n\n".join(resultado)


def limpar_diretorio(diretorio: Path, dry_run: bool) -> dict:
    """Aplica `limpar_texto` a todo `*.md` do diretório. Devolve um
    resumo (arquivos tocados, ocorrências removidas) — nunca imprime
    conteúdo do corpus."""
    resumo = {"arquivos_tocados": 0, "ocorrencias_removidas": 0}
    for arquivo in sorted(diretorio.glob("*.md")):
        original = arquivo.read_text(encoding="utf-8")
        ocorrencias = original.count(MARCA)
        if ocorrencias == 0:
            continue
        permitir_juncao = not arquivo.name.startswith("TIII_")
        limpo = limpar_texto(original, permitir_juncao=permitir_juncao)
        restantes = limpo.count(MARCA)
        if restantes != 0:
            raise RuntimeError(
                f"{arquivo}: {restantes} ocorrência(s) de {MARCA!r} "
                f"sobreviveram à limpeza — algoritmo não cobre este caso, "
                f"abortando sem escrever nada."
            )
        resumo["arquivos_tocados"] += 1
        resumo["ocorrencias_removidas"] += ocorrencias
        if not dry_run:
            arquivo.write_text(limpo, encoding="utf-8")
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Só reporta o que seria feito, não escreve nada.")
    args = parser.parse_args()

    if not DIRETORIO_ALVO.is_dir():
        raise SystemExit(f"Diretório alvo ausente: {DIRETORIO_ALVO}")

    resumo = limpar_diretorio(DIRETORIO_ALVO, dry_run=args.dry_run)
    modo = "DRY-RUN (nada escrito)" if args.dry_run else "APLICADO"
    print(f"{modo}: {resumo['arquivos_tocados']} arquivo(s) tocado(s), "
          f"{resumo['ocorrencias_removidas']} ocorrência(s) de {MARCA!r} removida(s).")


if __name__ == "__main__":
    main()
