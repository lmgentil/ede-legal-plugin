#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_fatos.py — validação estrutural de fatos extraídos com proveniência
(SPEC-0001 REQ-030), usada pela Skill `contestacao` (Fase 6).

A extração de fatos em si é tarefa do agente (leitura dos documentos do
processo fornecidos pelo advogado) — não é algo deterministicamente
automatizável, por isso não há um "extrator" de código aqui (ver
skills/contestacao/SKILL.md, seção de extração factual). O que ESTE script
garante é que, uma vez que o agente produziu a lista de fatos, ela respeita
o contrato mínimo de proveniência antes de alimentar o redator — fail
closed (CLAUDE.md §17): fato sem proveniência não é fato utilizável.

Contrato de cada fato (SPEC-0001 §20, REQ-030):
  {
    "fact": "A linha foi cancelada em 12/11/2025.",
    "source_document": "documento-x.pdf",
    "page": 4,                     # opcional, inteiro se presente
    "confidence": 0.99,            # opcional, mas se presente deve estar em [0, 1]
    "tipo": "FATO_DOCUMENTADO"     # opcional (Fase 7, SPEC-0001 §9); default
                                    # FATO_DOCUMENTADO se omitido — ver TIPOS_VALIDOS
  }

`tipo` existe para que o pipeline NUNCA trate alegação da parte autora,
sem contraprova, como fato incontroverso, nem inferência como fato
documental (SPEC-0001 §9, Fase 7):

  FATO_DOCUMENTADO  — comprovado por documento dos autos.
  ALEGACAO_AUTORAL  — dito pela parte autora, sem prova documental própria.
  INFERENCIA        — conclusão derivada de outros fatos, não afirmação
                       direta de um documento.
  DADO_NAO_INFORMADO — a informação é relevante, mas não consta dos
                        elementos disponibilizados (nunca inventada).

Uso:
  python scripts/validate_fatos.py --dados fatos.json
"""
import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CAMPOS_OBRIGATORIOS = ("fact", "source_document")
TIPOS_VALIDOS = ("FATO_DOCUMENTADO", "ALEGACAO_AUTORAL", "INFERENCIA", "DADO_NAO_INFORMADO")


def validar_fatos(fatos) -> tuple:
    """Retorna (ok: bool, erros: list[str]). Nunca lança para entrada mal
    formada — reporta como erro de validação, não como exceção não tratada
    (quem chama isso é, tipicamente, um passo de pipeline que precisa de
    uma resposta estruturada, não de um traceback)."""
    if not isinstance(fatos, list):
        return False, ["a entrada deve ser uma lista de fatos"]

    erros = []
    for i, f in enumerate(fatos):
        if not isinstance(f, dict):
            erros.append(f"fato[{i}]: não é um objeto")
            continue
        for campo in CAMPOS_OBRIGATORIOS:
            valor = f.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                erros.append(f"fato[{i}]: campo obrigatório '{campo}' ausente ou vazio")
        if f.get("confidence") is not None:
            c = f["confidence"]
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not (0.0 <= c <= 1.0):
                erros.append(f"fato[{i}]: confidence deve ser número entre 0 e 1, recebeu {c!r}")
        if f.get("page") is not None:
            p = f["page"]
            if isinstance(p, bool) or not isinstance(p, int):
                erros.append(f"fato[{i}]: page deve ser inteiro, recebeu {p!r}")
        if f.get("tipo") is not None and f["tipo"] not in TIPOS_VALIDOS:
            erros.append(f"fato[{i}]: tipo deve ser um de {TIPOS_VALIDOS}, recebeu {f['tipo']!r}")
    return (len(erros) == 0), erros


def tipo_de(fato: dict) -> str:
    """Tipo efetivo do fato — default FATO_DOCUMENTADO se omitido
    (retrocompatível com fatos que só usavam fact/source_document)."""
    return fato.get("tipo") or "FATO_DOCUMENTADO"


# ============================================================== Etapa 5.8-C — proveniência da Zona de Complementação
# Diagnóstico da Etapa 5.8-C: o contrato original de `zonas.json` era
# `{ZONA_ID: "texto"}` — nenhuma proveniência, nada ligando o conteúdo da
# zona a documento algum. Enquanto todo fato da peça exige
# `source_document` (REQ-030), a zona podia afirmar número, data e
# dispositivo sem lastro. Como a Etapa 5.8-C ampliou o teto agregado da
# zona justamente para permitir densidade documental, a ampliação é paga
# aqui: forma estruturada obrigatória e verificação determinística de que
# nenhum dado numérico do texto foi inventado.
#
# Etapa 5.8-C.1 — a ancoragem lexical provava que todo número do texto
# aparecia em ALGUM dado declarado, e só isso. Não provava que o dado
# estava atribuído à fonte certa, que a unidade fazia sentido, nem que as
# contas fechavam: o achado que motivou esta etapa é uma redação de teste
# que afirmava "2.412 kWh x R$ 1,7947/kWh = R$ 4.328,17" como se fosse a
# fórmula do memorial (o produto real é R$ 4.328,82) e ainda assim
# aprovada por todas as validações então existentes. Uma defesa não pode
# afirmar cálculo incompatível com a própria memória que invoca — mas o
# gate de fechamento também confirmou, auditando o memorial diretamente,
# que ele NÃO apresenta aquela multiplicação como fórmula do total: os
# R$ 4.328,17 são preservados como valor documental; o fato correspondente
# simplesmente não declara `operacao` quando o documento não afirma uma
# (ver `valor_total_apurado` em blocos.json/SPEC-0001 §59.2/§59.6). Camadas
# acrescentadas, todas determinísticas:
#
#   (a) contrato por fato — tipo/valor/unidade/fonte/natureza, em vez de
#       prosa livre em `dado`, para que o dado seja legível por máquina;
#   (b) fonte correta — os números de um dado `documental` precisam constar
#       de fato do caso oriundo DAQUELE documento (mesma base de
#       `fatos.json`; a zona não abre base probatória própria);
#   (c) aritmética — soma/subtração/multiplicação/média conferidas em
#       `Decimal` (nunca float para dinheiro) sempre que o fato declarar a
#       operação, inclusive quando o valor é documental: valor impresso que
#       não fecha com os próprios componentes é fail-closed, e o pipeline
#       nunca escolhe entre o documental e o derivado;
#   (d) unidade — álgebra de unidades com cancelamento (kWh/ciclo x ciclo =
#       kWh; kWh x R$/kWh = R$), para que a operação não some laranja com
#       maçã nem produza resultado na unidade errada.
#
# LIMITE CONHECIDO E DELIBERADO: nada aqui é interpretação de linguagem
# natural. Prova-se ancoragem, atribuição de fonte, unidade e aritmética
# declarada — não que a frase leia corretamente o significado do dado. Não
# há, e não deve haver, validador NLP genérico: só relações estruturadas.
# Correção material continua sendo do Redator e da revisão do advogado.
_TOKEN_NUMERICO_RE = re.compile(r"\d[\d.,/:ºª°-]*")

NATUREZAS_ZONA = ("documental", "derivado")
OPERACOES_ZONA = ("soma", "subtracao", "multiplicacao", "media")
ZONA_FATO_CAMPOS = ("tipo", "valor", "fonte", "natureza")

# §"PROIBIÇÃO DE FRASES VAZIAS" (Etapa 5.8-C): conclusões genéricas que o
# texto institucional já formula. Só são rejeitadas quando aparecem como
# parágrafo inteiro SEM nenhum dado concreto — acompanhadas de
# concretização factual, são legítimas.
_FRASES_VAZIAS = (
    "procedimento foi regular", "observou a legislacao", "observou a legislação",
    "cobranca e legitima", "cobrança é legítima", "valores estao corretos",
    "valores estão corretos", "nao houve arbitrariedade", "não houve arbitrariedade",
    "conforme documentos anexos", "constam do memorial", "conforme memorial anexo",
    "conforme documentacao anexa", "conforme documentação anexa",
)


def _tokens_numericos(texto: str) -> list:
    """Tokens com dígito no texto, normalizados (sem pontuação final).
    Cada um precisa estar ancorado num dado documental declarado."""
    brutos = _TOKEN_NUMERICO_RE.findall(str(texto))
    return [t.rstrip(".,:;/-º ª°") for t in brutos if t.rstrip(".,:;/-º ª°")]


def _quantidade(valor):
    """Decimal a partir de literal em português ("R$ 4.328,17", "1,7947",
    "612"). Retorna None quando o valor não é uma quantidade — é o caso
    legítimo de um dado como "art. 595, III, da REN 1.000/2021", que tem
    número mas não é operando de conta alguma."""
    t = re.sub(r"[R$\s]", "", str(valor))
    if not re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?|-?\d+(,\d+)?", t):
        return None
    try:
        return Decimal(t.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def _unidade(bruta):
    """Unidade como fração (numerador, denominador) para permitir
    cancelamento: "kWh/ciclo" -> (["kwh"], ["ciclo"]); "" -> ([], [])."""
    partes = [p.strip().casefold() for p in str(bruta or "").split("/")]
    num = [partes[0]] if partes and partes[0] else []
    return (sorted(num), sorted(p for p in partes[1:] if p))


def _multiplicar_unidades(a, b):
    num, den = sorted(a[0] + b[0]), sorted(a[1] + b[1])
    for u in list(num):
        if u in den:
            num.remove(u)
            den.remove(u)
    return (sorted(num), sorted(den))


def _fmt_unidade(u):
    num, den = u
    return ("*".join(num) or "1") + ("/" + "*".join(den) if den else "")


def _calcular(op: str, valores: list, unidades: list):
    """Retorna (resultado, unidade, erro). Aritmética em Decimal — dinheiro
    nunca em float."""
    if op == "multiplicacao":
        resultado, unidade = Decimal(1), ([], [])
        for v, u in zip(valores, unidades):
            resultado *= v
            unidade = _multiplicar_unidades(unidade, u)
        return resultado, unidade, None
    if any(u != unidades[0] for u in unidades[1:]):
        return None, None, (f"operandos de '{op}' em unidades diferentes "
                            f"({[_fmt_unidade(u) for u in unidades]}) — só se soma, "
                            f"subtrai ou faz média de grandezas da mesma espécie")
    if op == "soma":
        return sum(valores, Decimal(0)), unidades[0], None
    if op == "subtracao":
        resultado = valores[0]
        for v in valores[1:]:
            resultado -= v
        return resultado, unidades[0], None
    return sum(valores, Decimal(0)) / Decimal(len(valores)), unidades[0], None  # media


def _valor_conflitante(a, b) -> bool:
    """Dois registros do MESMO dado divergem? Compara como quantidade
    quando ambos são quantidade (para que "2.412" e "2412" não sejam
    tratados como contradição), e literalmente no resto."""
    qa, qb = _quantidade(a), _quantidade(b)
    if qa is not None and qb is not None:
        return qa != qb
    return str(a).strip() != str(b).strip()


def _validar_aritmetica_zona(fatos: list, zona_id: str) -> list:
    """CONTROLE DE COERÊNCIA das relações declaradas entre os dados da zona
    (§4/§5 da Etapa 5.8-C.1). NÃO é um mecanismo de recálculo da cobrança.

    A cobrança já foi constituída no procedimento administrativo. Os
    documentos oficiais da apuração — Memorial de Cálculo e Memorial de
    Faturamento — são a FONTE DE VERDADE dos valores: consumo recuperado,
    período, ciclos, critério, tarifa, diferenças e valor final. O papel
    desta função é impedir que a peça AFIRME uma operação que os documentos
    não sustentam; nunca substituir o valor documental por um cálculo
    próprio da IA.

    Daí as três regras, nesta ordem:

      1. Contradição documental — o mesmo dado registrado com valores
         divergentes em documentos oficiais diferentes (o Memorial de
         Cálculo diz uma coisa, o de Faturamento diz outra) é fail-closed.
         Essa é a contradição interna REAL. Registro repetido com o mesmo
         valor é confirmação cruzada, não conflito.

      2. Valor DERIVADO que não fecha — quando a peça apresenta um número
         como resultado de uma conta (`natureza: "derivado"`), ela está
         afirmando a conta. Se a conta não fecha, a afirmação é falsa:
         fail-closed, sempre.

      3. Valor DOCUMENTAL que não fecha com uma operação declarada — o
         valor consta expressamente do documento oficial e é PRESERVADO.
         A divergência aritmética aparente é sinal de que a apuração tem
         componente não reproduzido na conta simples: apuração por
         estimativa segundo o critério regulamentar, proporcionalização,
         bandeira tarifária, tributos, arredondamento. Nada disso é
         defeito — ESTIMATIVA REGULAMENTAR NÃO É ARBITRARIEDADE. O fato
         declara então `metodologia` ({"descricao", "fonte"}), apontando
         onde o documento oficial explica a diferença, e a zona segue.
         Sem essa declaração o pipeline aborta — não porque o documento
         esteja errado, mas porque a peça estaria reproduzindo uma conta
         que o próprio documento não fecha, e é preciso consultar a
         metodologia documental antes de afirmá-la.

    Fato documental sem `operacao` é aceito como está, sem recálculo — o
    pipeline não inventa contas que o documento não fez.
    """
    erros = []
    por_tipo = {}
    for f in fatos:
        if not isinstance(f, dict):
            continue
        tipo = f.get("tipo")
        if not (isinstance(tipo, str) and tipo.strip()):
            continue
        anterior = por_tipo.get(tipo)
        if anterior is None:
            por_tipo[tipo] = f
        elif _valor_conflitante(anterior.get("valor"), f.get("valor")):
            erros.append(
                f"{zona_id}: contradição documental em {tipo!r} — "
                f"{anterior.get('fonte')!r} registra {anterior.get('valor')!r} e "
                f"{f.get('fonte')!r} registra {f.get('valor')!r}. Os documentos oficiais "
                f"da apuração divergem entre si sobre o mesmo dado; a defesa não escolhe "
                f"um deles nem concilia por conta própria")

    for f in fatos:
        if not isinstance(f, dict):
            continue
        tipo, op = f.get("tipo"), f.get("operacao")
        natureza = f.get("natureza")
        if natureza == "derivado" and not isinstance(op, dict):
            erros.append(f"{zona_id}: {tipo!r} é 'derivado' mas não declara 'operacao' — "
                         f"dado derivado identifica os fatos de origem que o produziram")
            continue
        if not isinstance(op, dict):
            continue

        nome, operandos = op.get("op"), op.get("operandos")
        if nome not in OPERACOES_ZONA:
            erros.append(f"{zona_id}: {tipo!r} declara operação {nome!r} não suportada "
                         f"(suportadas: {OPERACOES_ZONA})")
            continue
        if not isinstance(operandos, list) or len(operandos) < 2:
            erros.append(f"{zona_id}: {tipo!r} declara 'operandos' inválido — a operação "
                         f"precisa referenciar ao menos dois dados declarados")
            continue
        faltando = [o for o in operandos if o not in por_tipo]
        if faltando:
            erros.append(f"{zona_id}: {tipo!r} depende de dado(s) não declarado(s) {faltando} — "
                         f"sem os componentes documentais o cálculo não é reproduzido nem "
                         f"presumido; declare o componente ou não afirme a operação")
            continue

        valores = [_quantidade(por_tipo[o].get("valor")) for o in operandos]
        nao_numericos = [o for o, v in zip(operandos, valores) if v is None]
        if nao_numericos:
            erros.append(f"{zona_id}: {tipo!r} usa como operando dado sem valor numérico "
                         f"{nao_numericos}")
            continue
        unidades = [_unidade(por_tipo[o].get("unidade")) for o in operandos]
        resultado, unidade, erro = _calcular(nome, valores, unidades)
        if erro:
            erros.append(f"{zona_id}: {tipo!r}: {erro}")
            continue

        declarado = _quantidade(f.get("valor"))
        if declarado is None:
            erros.append(f"{zona_id}: {tipo!r} é resultado de operação mas seu 'valor' "
                         f"({f.get('valor')!r}) não é uma quantidade")
            continue
        if unidade != _unidade(f.get("unidade")):
            erros.append(f"{zona_id}: {tipo!r}: unidade incompatível — {nome} dos operandos "
                         f"produz {_fmt_unidade(unidade)}, mas o dado declara "
                         f"{_fmt_unidade(_unidade(f.get('unidade')))}")
            continue
        casas = max(0, -declarado.as_tuple().exponent)
        arredondado = resultado.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
        if arredondado == declarado:
            continue

        metodologia = f.get("metodologia")
        if natureza == "documental" and isinstance(metodologia, dict) and \
                str(metodologia.get("descricao") or "").strip() and \
                str(metodologia.get("fonte") or "").strip():
            # Regra 3: valor documental PRESERVADO. A diferença está
            # explicada pela metodologia do próprio documento oficial.
            continue
        if natureza == "documental":
            erros.append(
                f"{zona_id}: {tipo!r}: a operação reproduzida na peça não fecha com o valor "
                f"documental — {nome} de {[str(v) for v in valores]} daria {arredondado}, e o "
                f"documento oficial registra {declarado}. O valor documental NÃO é substituído "
                f"por cálculo próprio: consulte no Memorial de Cálculo/Faturamento a "
                f"metodologia, os parâmetros, a proporcionalização, a bandeira, os tributos ou "
                f"o arredondamento que explicam a diferença e declare-os em 'metodologia' "
                f"({{'descricao', 'fonte'}}); ou não afirme a operação no texto")
        else:
            erros.append(
                f"{zona_id}: {tipo!r}: inconsistência aritmética — a peça apresenta este valor "
                f"como resultado de {nome} de {[str(v) for v in valores]}, que dá "
                f"{arredondado}, e não {declarado}. Dado derivado é afirmação da própria "
                f"conta; sem os componentes que a sustentem, a conta não é afirmada")
    return erros


def _fatos_por_fonte(fatos_do_caso) -> dict:
    """Índice {source_document: texto de todos os fatos daquele documento},
    a partir de `fatos.json` — a base probatória que já sustenta a peça."""
    indice = {}
    for f in fatos_do_caso or []:
        if isinstance(f, dict) and isinstance(f.get("source_document"), str):
            indice.setdefault(f["source_document"], []).append(str(f.get("fact", "")))
    return {k: " | ".join(v) for k, v in indice.items()}


def normalizar_conteudo_zona(bruto):
    """Aceita as duas formas de valor em `zonas.json`:

      - string vazia/em branco (ou None) -> zona vazia, o estado normal;
      - objeto {"conteudo": str, "fatos": [{"tipo","valor","unidade",
        "fonte","natureza", "operacao"?}, ...]}.

    String NAO VAZIA e rejeitada: desde a Etapa 5.8-C, conteudo de zona
    sem declaracao de proveniencia nao e aceito. Retorna
    (conteudo: str, fatos: list, erros: list)."""
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return "", [], []
    if isinstance(bruto, str):
        return "", [], [
            "conteudo de zona fornecido como texto simples - desde a Etapa 5.8-C e "
            "obrigatoria a forma {\"conteudo\": ..., \"fatos\": [{\"tipo\": ..., "
            "\"valor\": ..., \"fonte\": ..., \"natureza\": ...}]}, para que cada dado "
            "seja rastreavel ao documento"]
    if not isinstance(bruto, dict):
        return "", [], [f"conteudo de zona deve ser objeto ou string vazia, recebeu {type(bruto).__name__}"]

    conteudo = bruto.get("conteudo")
    if conteudo is None or not str(conteudo).strip():
        return "", [], []
    fatos = bruto.get("fatos")
    if not isinstance(fatos, list):
        return "", [], ["'fatos' ausente ou nao e lista - proveniencia obrigatoria"]
    return str(conteudo), fatos, []


def validar_proveniencia_zona(conteudo: str, fatos: list, zona_id: str,
                               fatos_do_caso=None) -> list:
    """Retorna a lista de erros de proveniência da zona.

      - cada fato declarado precisa de tipo/valor/fonte/natureza;
      - `fonte` precisa ser um documento que já sustenta a peça (mesma base
        de `fatos.json`) — fonte inventada não passa;
      - dado `documental` precisa ter seus números respaldados por fato do
        caso oriundo DAQUELE documento — atribuir à fonte errada é
        fail-closed (§3 da Etapa 5.8-C.1);
      - relações matemáticas declaradas são conferidas (§4/§5);
      - todo token numérico do texto precisa estar ancorado em algum
        `valor` declarado (anti-invenção de número, data e dispositivo);
      - conteúdo sem NENHUM dado concreto é rejeitado: a zona existe para
        acrescentar particularidade documental, e texto sem dado só pode
        estar parafraseando o texto institucional;
      - parágrafo composto só de conclusão genérica, sem dado, é
        rejeitado (§"PROIBIÇÃO DE FRASES VAZIAS")."""
    erros = []
    declarados = []
    indice_fontes = _fatos_por_fonte(fatos_do_caso)
    fontes_conhecidas = set(indice_fontes) or None

    for i, f in enumerate(fatos):
        if not isinstance(f, dict):
            erros.append(f"{zona_id}: fato[{i}] não é um objeto")
            continue
        for campo in ZONA_FATO_CAMPOS:
            valor = f.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                erros.append(f"{zona_id}: fato[{i}] sem {campo!r} — desde a Etapa 5.8-C.1 cada "
                             f"dado da zona declara tipo, valor, fonte e natureza "
                             f"(unidade quando houver)")
        natureza, fonte, valor = f.get("natureza"), f.get("fonte"), f.get("valor")
        if isinstance(natureza, str) and natureza not in NATUREZAS_ZONA:
            erros.append(f"{zona_id}: fato[{i}] natureza {natureza!r} inválida "
                         f"(válidas: {NATUREZAS_ZONA})")
        metodologia = f.get("metodologia")
        if metodologia is not None:
            # A conciliação de uma diferença aritmética só vale se apontar
            # para o documento oficial que a explica — nunca para uma
            # explicação criada pela IA (§4 da Etapa 5.8-C.1).
            if not isinstance(metodologia, dict):
                erros.append(f"{zona_id}: fato[{i}] 'metodologia' deve ser objeto "
                             f"{{'descricao', 'fonte'}}")
            else:
                for campo in ("descricao", "fonte"):
                    if not str(metodologia.get(campo) or "").strip():
                        erros.append(f"{zona_id}: fato[{i}] 'metodologia' sem {campo!r} — a "
                                     f"diferença só é conciliada por metodologia constante do "
                                     f"documento oficial da apuração")
                mf = metodologia.get("fonte")
                if (fontes_conhecidas is not None and isinstance(mf, str)
                        and mf.strip() and mf not in fontes_conhecidas):
                    erros.append(f"{zona_id}: fato[{i}] 'metodologia' cita fonte {mf!r} fora da "
                                 f"base documental do caso ({sorted(fontes_conhecidas)})")
        if isinstance(valor, str):
            declarados.append(valor)
        if not isinstance(fonte, str) or not fonte.strip():
            continue
        if fontes_conhecidas is not None and fonte not in fontes_conhecidas:
            erros.append(f"{zona_id}: fato[{i}] cita fonte {fonte!r} que não consta da base "
                         f"documental do caso ({sorted(fontes_conhecidas)})")
        elif natureza == "documental" and isinstance(valor, str):
            # §3: o dado documental tem que estar NAQUELE documento. Dado
            # derivado não passa por aqui — seu valor pode não estar
            # impresso em lugar nenhum, e é a aritmética que o sustenta.
            corpus = indice_fontes.get(fonte, "")
            sem_respaldo = [t for t in _tokens_numericos(valor) if t not in corpus]
            if sem_respaldo:
                erros.append(
                    f"{zona_id}: fato[{i}] atribui a {fonte!r} dado(s) que não constam desse "
                    f"documento na base do caso: {sem_respaldo} — a redação não pode vincular "
                    f"um dado a documento diferente daquele que efetivamente o suporta")

    erros.extend(_validar_aritmetica_zona(fatos, zona_id))

    texto_declarado = " | ".join(declarados)
    tokens = _tokens_numericos(conteudo)
    nao_ancorados = sorted({t for t in tokens if t not in texto_declarado})
    if nao_ancorados:
        erros.append(
            f"{zona_id}: dado(s) numérico(s) no texto sem lastro documental declarado: "
            f"{nao_ancorados} — número, data e dispositivo só podem aparecer se constarem "
            f"de 'fatos' com fonte; nunca completar por inferência ou plausibilidade")

    if not tokens:
        erros.append(
            f"{zona_id}: conteúdo sem nenhum dado concreto — a zona acrescenta "
            f"particularidade documental ao texto institucional; texto sem dado apenas "
            f"reafirma o que o modelo já diz. Sem informação documental suficiente, a "
            f"zona deve ficar vazia, nunca ser preenchida com linguagem genérica")

    for i, p in enumerate(l for l in str(conteudo).split("\n") if l.strip()):
        if any(ch.isdigit() for ch in p):
            continue
        minusculo = p.lower()
        for frase in _FRASES_VAZIAS:
            if frase in minusculo:
                erros.append(
                    f"{zona_id}: parágrafo {i + 1} é conclusão genérica sem concretização "
                    f"factual ({frase!r}) — o texto institucional já afirma isso; a zona só "
                    f"pode repeti-lo acompanhado do dado que o justifica")
                break
    return erros


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dados", required=True, help="JSON com lista de fatos")
    args = ap.parse_args()

    with open(args.dados, encoding="utf-8") as f:
        fatos = json.load(f)

    ok, erros = validar_fatos(fatos)
    if ok:
        print(f"OK — {len(fatos)} fato(s), todos com proveniência válida.")
        sys.exit(0)
    print(f"FALHA — {len(erros)} problema(s):")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)


if __name__ == "__main__":
    main()
