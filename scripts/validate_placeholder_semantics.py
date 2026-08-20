#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_placeholder_semantics.py — validação SEMÂNTICA do conteúdo dos
placeholders (Etapa 3, pós-diagnóstico forense do bug real de paginação
registrado no primeiro teste real da Contestação).

Camada distinta da validação ESTRUTURAL (scripts/validate_placeholders.py,
que confere se os placeholders batem com o schema/template real). Esta
aqui nunca abre o .docx nem depende do toolkit OOXML — valida só os
VALORES (dict PLACEHOLDER: valor) contra o contrato semântico declarado
em templates/contestacao/schema.json ("placeholder_contracts"). Funciona
mesmo sem o template institucional presente (ADR-0006/0009) — importante
para continuar rodando em CI/instalação pública.

Achado real que motivou esta camada: `AUTOR` preenchido com "Nome, já
qualificada nos autos, portadora do CPF nº..." — conteúdo redundante com
o texto fixo do próprio template, que já formula a cláusula de
qualificação na sequência do placeholder — causou quebra de página real
(parágrafo dividido entre páginas, confirmado por isolamento causal:
encurtar só o AUTOR eliminou a quebra, nada mais precisou mudar).

Só valida os campos com regra objetivamente segura (CLAUDE.md: preferir
falhar explicitamente só quando o padrão é confiável, nunca bloquear
texto jurídico legítimo por heurística agressiva de comprimento). Os
campos de texto longo/técnico (REALIDADE_FATICA, IRREGULARIDADE_ENCONTRADA
etc.) não recebem validação semântica de conteúdo aqui.

SINOPSE_FATOS (Etapa 5.2, INV-SINOPSE-ESTRITAMENTE-AUTORAL) é exceção
parcial: recebe um backstop LEXICAL — uma lista fechada de marcadores
defensivos que não têm lugar numa síntese puramente narrativa da inicial
("não comprovou", "não merece prosperar", "os documentos demonstram"...).
Isto é deliberadamente um backstop, não o controle real: ocorrência
lexical prova contaminação defensiva o bastante para reprovar
(CLAUDE.md §17, fail closed), mas AUSÊNCIA de qualquer marcador aqui NÃO
prova que a Sinopse está correta — texto defensivo bem escrito, sem essas
palavras específicas, passa por este validador sem ser pego. O controle
real (a Sinopse é estritamente a narrativa da inicial, nunca a versão da
Ré) é COMPORTAMENTAL — reforçado nas instruções de
skills/contestacao/SKILL.md e skills/redator-peca-processual-elite/
SKILL.md, não algo que uma lista de palavras-proibidas resolve sozinha.

Uso:
  python validate_placeholder_semantics.py --dados dados.json
"""
import argparse
import json
import re
import sys
import unicodedata

_CPF_RE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")

# Marcadores de cláusula de qualificação/dado cadastral que NÃO pertencem
# a AUTOR — o template já formula essa cláusula (nome, "já qualificado(a)
# nos autos", CPF) imediatamente depois do placeholder.
_MARCADORES_QUALIFICACAO_AUTOR = (
    "QUALIFICAD",  # qualificado / qualificada
    "NOS AUTOS",
    "CPF",
    "RG N",
    "RESIDENTE",
    "DOMICILIAD",
    "PORTADOR",
    "PROFISSAO",
    "ESTADO CIVIL",
    "CASADO", "CASADA", "SOLTEIRO", "SOLTEIRA",
    "DIVORCIADO", "DIVORCIADA", "VIUVO", "VIUVA",
    "UNIAO ESTAVEL",
)

_NUMERO_PROCESSO_RE = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")

SENTINELA_AUSENCIA = "NÃO INFORMADO"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _validar_autor(valor) -> list:
    texto = str(valor)
    v = _sem_acento(texto).upper()
    erros = []
    if _CPF_RE.search(texto):
        erros.append(
            "AUTOR contém padrão de CPF — o template já formula a "
            "qualificação (incluindo CPF, quando aplicável) imediatamente "
            "depois do placeholder; AUTOR deve conter só o nome da parte")
    achados = [m for m in _MARCADORES_QUALIFICACAO_AUTOR if m in v]
    if achados:
        erros.append(
            f"AUTOR contém marcador(es) de cláusula de qualificação "
            f"{achados} — o template já formula essa cláusula na sequência "
            f"do placeholder; AUTOR deve conter apenas o nome da parte")
    return erros


def _validar_numero_processo(valor) -> list:
    if not _NUMERO_PROCESSO_RE.match(str(valor).strip()):
        return [f"NUMERO_PROCESSO não bate com o formato CNJ "
                f"(NNNNNNN-DD.AAAA.J.TR.OOOO): {valor!r}"]
    return []


def _validar_valor_fra(valor) -> list:
    texto = str(valor)
    if _sem_acento(SENTINELA_AUSENCIA).upper() in _sem_acento(texto).upper():
        return []  # sentinela de ausência — tratada à parte pelo orquestrador
    if not re.search(r"\d", texto):
        return [f"VALOR_FRA não contém nenhum dígito — não parece um "
                f"valor monetário nem a sentinela de ausência: {valor!r}"]
    return []


# Etapa 5.2 — INV-SINOPSE-ESTRITAMENTE-AUTORAL: marcadores defensivos que
# não pertencem à Sinopse (função exclusivamente narrativa da inicial).
# Lista fechada e deliberadamente conservadora (só frases inequivocamente
# defensivas) — ver docstring do módulo sobre os limites deste backstop.
_MARCADORES_DEFENSIVOS_SINOPSE = (
    "NAO COMPROVOU", "NAO MERECE PROSPERAR", "AO CONTRARIO DO ALEGADO",
    "OS DOCUMENTOS DEMONSTRAM", "NAO HA PROVA", "NAO HA PROVAS",
    "COBRANCA E LEGITIMA", "LEGITIMIDADE DA COBRANCA",
    "REGULARIDADE DA ATUACAO", "ATUACAO REGULAR DA RE",
    "IMPROCEDE", "IMPROCEDENTE",
)


def _validar_sinopse_fatos(valor) -> list:
    v = _sem_acento(str(valor)).upper()
    achados = [m for m in _MARCADORES_DEFENSIVOS_SINOPSE if m in v]
    if achados:
        return [
            f"SINOPSE_FATOS contém marcador(es) de linguagem defensiva "
            f"{achados} — INV-SINOPSE-ESTRITAMENTE-AUTORAL: a Sinopse é "
            f"exclusivamente a narrativa da inicial (fatos alegados + "
            f"pedidos), nunca a versão ou impugnação da Ré; a defesa "
            f"pertence a REALIDADE_FATICA e aos tópicos de mérito"]
    return []


def _validar_local_data(valor) -> list:
    texto = str(valor)
    erros = []
    if len(texto) > 150:
        erros.append(f"LOCAL_DATA muito longo ({len(texto)} caracteres) "
                      f"para um campo de local/data — parece conter "
                      f"narrativa jurídica indevida")
    if texto.count(".") > 1:
        erros.append("LOCAL_DATA contém múltiplas frases (mais de um "
                      "ponto final) — parece conter narrativa jurídica "
                      "indevida")
    return erros


# Só campos com regra objetivamente segura entram aqui — texto
# narrativo/técnico livre (SINOPSE_FATOS, REALIDADE_FATICA,
# IRREGULARIDADE_ENCONTRADA, DESENVOLVIMENTO_TECNICO_IRREGULARIDADE,
# ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA, PEDIDOS_FINAIS,
# TEMPESTIVIDADE_CASO) fica de fora deliberadamente.
VALIDADORES_ESPECIFICOS = {
    "AUTOR": _validar_autor,
    "NUMERO_PROCESSO": _validar_numero_processo,
    "VALOR_FRA": _validar_valor_fra,
    "LOCAL_DATA": _validar_local_data,
    "SINOPSE_FATOS": _validar_sinopse_fatos,
}


def validar_semantica(dados: dict) -> tuple:
    """Retorna (ok: bool, erros: list[str])."""
    erros = []
    for nome, validador in VALIDADORES_ESPECIFICOS.items():
        if nome in dados and dados[nome] is not None:
            erros.extend(validador(dados[nome]))
    return (len(erros) == 0), erros


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dados", required=True, help="JSON com {PLACEHOLDER: valor}")
    args = ap.parse_args()

    with open(args.dados, encoding="utf-8") as f:
        dados = json.load(f)

    ok, erros = validar_semantica(dados)
    if ok:
        print("OK — conteúdo semântico dos placeholders validado sem problemas.")
        sys.exit(0)
    print(f"FALHA — {len(erros)} problema(s):")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)


if __name__ == "__main__":
    main()
