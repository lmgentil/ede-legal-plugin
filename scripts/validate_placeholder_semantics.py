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
campos de texto longo/técnico não recebem validação de CONTEÚDO
substantivo aqui (isso é COMPORTAMENTAL, imposto pelas Skills) — mas
alguns recebem backstops LEXICAIS pontuais, sempre não-exaustivos:

- SINOPSE_FATOS (Etapa 5.2, INV-SINOPSE-ESTRITAMENTE-AUTORAL): marcadores
  defensivos ("não comprovou", "os documentos demonstram"...) — não tem
  lugar numa síntese puramente narrativa da inicial.
- TEMPESTIVIDADE_CASO, REALIDADE_FATICA, IRREGULARIDADE_ENCONTRADA,
  DESENVOLVIMENTO_TECNICO_IRREGULARIDADE, PEDIDOS_FINAIS (Etapa 5.3,
  achado grave do Teste Real 01-B): marcadores de META-PROVENIÊNCIA ("conforme informado pelo
  advogado", "segundo o RAG"...) — o documento final nunca pode revelar a
  mecânica interna de obtenção/validação de um dado; proveniência existe
  só para auditoria interna (fatos.json, tempestividade.json etc.), nunca
  verbalizada na peça.
- IRREGULARIDADE_ENCONTRADA, DESENVOLVIMENTO_TECNICO_IRREGULARIDADE
  (Etapa 5.3): marcadores sobre ASSINATURA do TOI — a peça não deve
  mencionar se o TOI foi ou não assinado (§11 do achado real).
- TODOS os placeholders (INV-CONTESTACAO-SEM-TRAVESSAO, correção pontual
  pós-teste real): travessão (—, U+2014) é proibido em qualquer conteúdo
  gerado/reescrito/humanizado — única checagem desta camada que não é um
  backstop lexical pontual por campo, roda sobre `dados` inteiro.

Todo backstop lexical desta camada é deliberadamente um backstop, não o
controle real: ocorrência lexical prova contaminação o bastante para
reprovar (CLAUDE.md §17, fail closed), mas AUSÊNCIA de qualquer marcador
aqui NÃO prova que o campo está correto — o controle substantivo é
COMPORTAMENTAL, reforçado nas instruções das Skills.

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


# Indicadores ordinais portugueses ("2ª", "3º") são alfabéticos para
# str.isalpha() mas nunca têm distinção maiúscula/minúscula real — achado
# real (INV-JUIZO-DATAJUD): órgão julgador retornado pelo DataJud como
# "2ª VARA..." disparava falso positivo de "não está em caixa alta".
_INDICADORES_ORDINAIS = ("ª", "º")


def _apenas_alfabetico_esta_em_caixa_alta(texto: str) -> bool:
    """True se todo caractere alfabético de `texto` já está em maiúscula
    (ignora dígitos/pontuação/espaço/indicador ordinal — não exige que o
    texto INTEIRO só tenha letras, só que nenhuma letra minúscula sobre)."""
    return all(c in _INDICADORES_ORDINAIS or not c.isalpha() or c.isupper() for c in texto)


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
    # Etapa 5.3 — achado real: nome deve ser produzido em caixa alta.
    if not _apenas_alfabetico_esta_em_caixa_alta(texto):
        erros.append(
            f"AUTOR deve ser produzido em CAIXA ALTA (padrão institucional, "
            f"Etapa 5.3): {valor!r}")
    return erros


# Etapa 5.3 — achado real: endereçamento frágil/genérico ("Vara Cível da
# Comarca de..."). Padrão institucional obrigatório: "AO JUÍZO DA [...]
# DA COMARCA DE [...]", inteiro em caixa alta. Não valida a parte central
# (a unidade judiciária real — "VARA", "JUIZADO ESPECIAL", "TURMA
# RECURSAL" etc. — vem do DataJud, INV-JUIZO-DATAJUD; exigir a palavra
# "VARA" especificamente já causou falso positivo real com nome de vara
# numerada retornado pelo DataJud, "2ª VARA...", além de nem toda unidade
# julgadora real se chamar "Vara"); só a moldura obrigatória.
_JUIZO_PREFIXO = "AO JUÍZO DA"
_JUIZO_INFIXO = "DA COMARCA DE"


def _validar_juizo(valor) -> list:
    texto = str(valor).strip()
    erros = []
    if not texto.startswith(_JUIZO_PREFIXO):
        erros.append(
            f"JUIZO deve seguir o padrão institucional, começando com "
            f"{_JUIZO_PREFIXO!r} (Etapa 5.3 — não usar 'Vara Cível da "
            f"Comarca...', 'Excelentíssimo Senhor...' ou construções "
            f"improvisadas): {valor!r}")
    if _JUIZO_INFIXO not in texto:
        erros.append(
            f"JUIZO deve conter {_JUIZO_INFIXO!r} seguido do nome da "
            f"comarca (Etapa 5.3): {valor!r}")
    if not _apenas_alfabetico_esta_em_caixa_alta(texto):
        erros.append(f"JUIZO deve ser produzido em CAIXA ALTA (Etapa 5.3): {valor!r}")
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
    erros = []
    achados = [m for m in _MARCADORES_DEFENSIVOS_SINOPSE if m in v]
    if achados:
        erros.append(
            f"SINOPSE_FATOS contém marcador(es) de linguagem defensiva "
            f"{achados} — INV-SINOPSE-ESTRITAMENTE-AUTORAL: a Sinopse é "
            f"exclusivamente a narrativa da inicial (fatos alegados + "
            f"pedidos), nunca a versão ou impugnação da Ré; a defesa "
            f"pertence a REALIDADE_FATICA e aos tópicos de mérito")
    erros.extend(_checar_meta_proveniencia(valor, "SINOPSE_FATOS"))
    return erros


# Etapa 5.3 — achado grave do Teste Real 01-B: a peça revelou sua própria
# mecânica interna ("conforme informação fornecida pelo advogado"). A
# proveniência existe só para auditoria interna (fatos.json,
# tempestividade.json, decisoes_blocos.json...) — nunca verbalizada no
# documento final. Lista deliberadamente ampla (cobre variações de
# fraseado) — backstop lexical, não o controle real (esse é
# comportamental, nas Skills).
_MARCADORES_META_PROVENIENCIA = (
    "conforme informação fornecida pelo advogado",
    "conforme informado pelo advogado",
    "segundo informação do advogado",
    "conforme dados fornecidos",
    "segundo os documentos enviados",
    "conforme arquivo analisado",
    "de acordo com a análise realizada",
    "conforme contexto fornecido",
    "segundo o material disponibilizado",
    "conforme input",
    "segundo o json",
    "segundo a extração",
    "conforme rag",
    "segundo o sistema",
    "conforme prompt",
    "esta ia", "esta skill", "este pipeline",
    "conforme informação processual fornecida",
)


def _checar_meta_proveniencia(valor, nome_campo: str) -> list:
    v = _sem_acento(str(valor)).lower()
    achados = [m for m in _MARCADORES_META_PROVENIENCIA if _sem_acento(m).lower() in v]
    if achados:
        return [
            f"{nome_campo} contém meta-proveniência proibida {achados} — a "
            f"peça não pode revelar a mecânica interna de obtenção/"
            f"validação de um dado (Etapa 5.3); proveniência é interna, "
            f"nunca verbalizada no documento final"]
    return []


# Etapa 5.3 — achado real (§11): a peça não deve mencionar se o TOI foi ou
# não assinado — informação irrelevante para a defesa e potencialmente
# contraproducente; pode existir na camada de extração/proveniência
# interna, nunca projetada para a redação.
_MARCADORES_ASSINATURA_TOI = (
    "assinou o toi", "toi foi assinado", "toi assinado",
    "mediante assinatura", "declaração por ela assinada",
    "recibo assinado", "assinatura da autora no toi",
    "assinatura no toi",
)


def _checar_assinatura_toi(valor, nome_campo: str) -> list:
    v = _sem_acento(str(valor)).lower()
    achados = [m for m in _MARCADORES_ASSINATURA_TOI if _sem_acento(m).lower() in v]
    if achados:
        return [
            f"{nome_campo} menciona assinatura do TOI {achados} — proibido "
            f"na redação defensiva (Etapa 5.3 §11), mesmo que a informação "
            f"exista nos documentos; não deve ser projetada para a peça"]
    return []


def _validar_realidade_fatica(valor) -> list:
    return _checar_meta_proveniencia(valor, "REALIDADE_FATICA")


# Etapa 5.3-B — §15/§18: IRREGULARIDADE_ENCONTRADA deve conter
# EXCLUSIVAMENTE o nome/tipo da irregularidade — o texto fixo do template
# já formula "Na ocasião, foi constatada irregularidade do tipo, " antes
# do placeholder e ", circunstância que impedia o registro integral..."
# depois. Backstop lexical ESPECÍFICO a esse texto fixo (não blacklist
# genérica — §18: não pode rejeitar tipos de irregularidade válidos),
# criado para a regressão real do Teste 5.3 (o valor repetiu o texto fixo
# por engano, produzindo duplicação visível no DOCX final).
_MARCADORES_DUPLICACAO_IRREGULARIDADE = (
    "na ocasiao", "foi constatada", "irregularidade do tipo",
    "circunstancia que", "impedia o registro",
)


def _validar_irregularidade_encontrada(valor) -> list:
    texto = str(valor)
    erros = _checar_meta_proveniencia(valor, "IRREGULARIDADE_ENCONTRADA")
    erros.extend(_checar_assinatura_toi(valor, "IRREGULARIDADE_ENCONTRADA"))
    v = _sem_acento(texto).lower()
    achados = [m for m in _MARCADORES_DUPLICACAO_IRREGULARIDADE if m in v]
    if achados:
        erros.append(
            f"IRREGULARIDADE_ENCONTRADA repete texto fixo do template "
            f"{achados} — contrato atômico (Etapa 5.3-B §15): o campo "
            f"deve conter EXCLUSIVAMENTE o nome/tipo da irregularidade; o "
            f"template já formula 'Na ocasião, foi constatada "
            f"irregularidade do tipo, ' antes e ', circunstância que "
            f"impedia o registro integral...' depois: {valor!r}")
    # Etapa 5.3-B §16 — reversão da Etapa 5.3 §9 para este campo
    # especificamente: redação natural em minúsculas, ressalvados nomes
    # próprios/siglas — nunca caixa alta forçada no tipo inteiro.
    letras = [c for c in texto if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        erros.append(
            f"IRREGULARIDADE_ENCONTRADA não deve ficar integralmente em "
            f"CAIXA ALTA (Etapa 5.3-B §16 — minúsculas/natural, ressalvados "
            f"nomes próprios/siglas): {valor!r}")
    return erros


# INV-NAO-REPETICAO-FATICA (Etapa 5.5 §9-13, achado real do Teste Real:
# o mesmo fato — ex. "desvio de energia antes do medidor" — reaparecia em
# REALIDADE_FATICA, IRREGULARIDADE_ENCONTRADA e DESENVOLVIMENTO_TECNICO
# quase palavra por palavra). O problema real é SEMÂNTICO (paráfrase),
# não apenas igualdade textual — controle primário é comportamental
# (Redator/Humanizer, skills/contestacao/SKILL.md), não um bloqueador
# genérico de similaridade (geraria falsos positivos, vedado pelo Etapa
# 5.5 §26). Este backstop é NARROW e determinístico, não exaustivo: só
# cobre o sintoma mais grave e detectável sem ambiguidade — o rótulo
# atômico de IRREGULARIDADE_ENCONTRADA (que por contrato, §15/Etapa
# 5.3-B, é só o nome/tipo da irregularidade) reaparecendo VERBATIM dentro
# de REALIDADE_FATICA, que por contrato (Etapa 5.5 §9) é contraposição
# global/objetiva e nunca deve antecipar esse detalhe. Mesmo padrão já
# usado em INV-SINOPSE-ESTRITAMENTE-AUTORAL (CLAUDE.md §7): backstop
# lexical não exaustivo, o controle real é comportamental.
def _validar_nao_repeticao_realidade_fatica(dados: dict) -> list:
    realidade = dados.get("REALIDADE_FATICA")
    irregularidade = dados.get("IRREGULARIDADE_ENCONTRADA")
    if not realidade or not irregularidade:
        return []
    r = _sem_acento(str(realidade)).lower()
    i = _sem_acento(str(irregularidade)).lower().strip().strip("*").strip()
    if len(i) >= 12 and i in r:
        return [
            f"REALIDADE_FATICA repete verbatim o rótulo atômico de "
            f"IRREGULARIDADE_ENCONTRADA ({irregularidade!r}) — "
            f"INV-NAO-REPETICAO-FATICA (Etapa 5.5): REALIDADE_FATICA é "
            f"contraposição global/objetiva, nunca deve antecipar o "
            f"detalhe que é responsabilidade exclusiva de "
            f"IRREGULARIDADE_ENCONTRADA/DESENVOLVIMENTO_TECNICO_"
            f"IRREGULARIDADE — um fato não deve ser reapresentado em "
            f"vários parágrafos, mesmo com palavras diferentes."]
    return []


def _validar_desenvolvimento_tecnico(valor) -> list:
    erros = _checar_meta_proveniencia(valor, "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE")
    erros.extend(_checar_assinatura_toi(valor, "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE"))
    return erros


def _validar_pedidos_finais(valor) -> list:
    return _checar_meta_proveniencia(valor, "PEDIDOS_FINAIS")


# Etapa 5.5 (achado real — redação robótica da tempestividade): backstop
# determinístico contra dump de memória de cálculo no DOCX final —
# independente da fonte do valor (fallback automático do pipeline ou
# eventual texto do redator). "Cálculo e redação são coisas diferentes":
# a memória de cálculo pertence à auditoria interna, nunca à peça.
_DATA_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MARCADORES_DUMP_TEMPESTIVIDADE = (
    "tempestivo:", "intempestivo:", "termo inicial", "termo final",
)
_MARCADORES_RITO_VEDADO_TEMPESTIVIDADE = ("9.099", "9099", "juizado especial")


def _validar_tempestividade_caso(valor) -> list:
    texto = str(valor)
    erros = _checar_meta_proveniencia(valor, "TEMPESTIVIDADE_CASO")
    if _DATA_ISO_RE.search(texto):
        erros.append(
            f"TEMPESTIVIDADE_CASO contém data em formato ISO (AAAA-MM-DD) "
            f"— proibido na redação final (Etapa 5.5); use DD/MM/AAAA ou "
            f"escreva a data por extenso: {valor!r}")
    v = _sem_acento(texto).lower()
    achados_dump = [m for m in _MARCADORES_DUMP_TEMPESTIVIDADE if m in v]
    if achados_dump:
        erros.append(
            f"TEMPESTIVIDADE_CASO contém marcador(es) de dump de memória de "
            f"cálculo {achados_dump} — proibida redação robótica tipo "
            f"'TEMPESTIVO: termo inicial ..., termo final ...' (Etapa 5.5); "
            f"a peça recebe prosa jurídica natural, a memória de cálculo "
            f"fica só na auditoria interna do pipeline: {valor!r}")
    achados_rito = [m for m in _MARCADORES_RITO_VEDADO_TEMPESTIVIDADE if m in v]
    if achados_rito:
        erros.append(
            f"TEMPESTIVIDADE_CASO menciona Lei 9.099/95/Juizado Especial "
            f"{achados_rito} — esta Contestação sempre segue o "
            f"procedimento comum do CPC (INV-TEMPESTIVIDADE-PROCEDIMENTO-"
            f"COMUM, Etapa 5.5): {valor!r}")
    return erros


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
    # Etapa 5.3 — regra institucional: local da peça é sempre Salvador,
    # independentemente da comarca do processo.
    if not texto.strip().startswith("Salvador"):
        erros.append(
            f"LOCAL_DATA deve começar com 'Salvador' — regra institucional "
            f"(Etapa 5.3): local da peça é sempre Salvador, "
            f"independentemente da comarca do processo: {valor!r}")
    return erros


# INV-CONTESTACAO-SEM-TRAVESSAO — correção pontual pós-teste real: as
# Skills redator-peca-processual-elite e humanizer-pt-br estavam inserindo
# travessão (—, U+2014) no texto gerado. Backstop determinístico,
# independente do comportamento probabilístico das Skills — roda sobre
# TODO placeholder textual (não só os campos com validador dedicado
# abaixo), universalmente, em vez de depender de instrução. NÃO
# substitui automaticamente por vírgula/hífen: a pontuação correta
# depende da estrutura sintática da frase (tarefa do Redator/Humanizer,
# não deste validador) — só rejeita, fail closed. Escopo: só o conteúdo
# VARIÁVEL (dict `dados`, o que o Template Engine substitui) — nunca o
# texto fixo institucional do template, que este módulo nem lê.
_TRAVESSAO = "—"  # — (EM DASH); hífen comum (U+002D, "-") não é afetado


def _checar_travessao(valor, nome_campo: str) -> list:
    texto = str(valor)
    if _TRAVESSAO in texto:
        return [
            f"{nome_campo} contém travessão (—, U+2014), proibido em "
            f"conteúdo gerado/reescrito/humanizado pela IA "
            f"(INV-CONTESTACAO-SEM-TRAVESSAO) — use vírgula, ponto, "
            f"ponto e vírgula, dois-pontos ou parênteses; corrija a "
            f"pontuação no Redator/Humanizer antes de prosseguir: {valor!r}"]
    return []


VALIDADORES_ESPECIFICOS = {
    "JUIZO": _validar_juizo,
    "AUTOR": _validar_autor,
    "NUMERO_PROCESSO": _validar_numero_processo,
    "TEMPESTIVIDADE_CASO": _validar_tempestividade_caso,
    "SINOPSE_FATOS": _validar_sinopse_fatos,
    "REALIDADE_FATICA": _validar_realidade_fatica,
    "IRREGULARIDADE_ENCONTRADA": _validar_irregularidade_encontrada,
    "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": _validar_desenvolvimento_tecnico,
    "VALOR_FRA": _validar_valor_fra,
    "PEDIDOS_FINAIS": _validar_pedidos_finais,
    "LOCAL_DATA": _validar_local_data,
}


def validar_semantica(dados: dict) -> tuple:
    """Retorna (ok: bool, erros: list[str])."""
    erros = []
    # INV-CONTESTACAO-SEM-TRAVESSAO — universal, roda sobre TODO
    # placeholder fornecido, não só os com validador específico abaixo.
    for nome, valor in dados.items():
        if valor is not None:
            erros.extend(_checar_travessao(valor, nome))
    for nome, validador in VALIDADORES_ESPECIFICOS.items():
        if nome in dados and dados[nome] is not None:
            erros.extend(validador(dados[nome]))
    # INV-NAO-REPETICAO-FATICA — cross-field, roda depois dos validadores
    # por campo (precisa dos dois campos juntos).
    erros.extend(_validar_nao_repeticao_realidade_fatica(dados))
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
