#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fidelidade_comando.py — fidelidade da peça ao comando ATUAL do advogado,
verificada pelo Core antes do render (gate de qualidade de conteúdo,
10/10/2026; manifesto V1 1.4.0).

Três verificações, todas determinísticas e conservadoras:

1. Decisões aplicadas: todo tópico SIM resolve para bloco INCLUIR e todo
   tópico NÃO para EXCLUIR (defesa em profundidade sobre a tradução da
   Topic Matrix — nunca deveria falhar).
2. Coerência das partes variáveis com os tópicos excluídos: nenhuma parte
   redigida pelo host (placeholders VARIAVEL_LLM_AUTORIZADA e zonas)
   reintroduz, pelo NOME EXPLÍCITO, a tese de um bloco excluído.
   Reaproveita o vocabulário que o fluxo local já usava para
   PEDIDOS_FINAIS (`docx_block_engine.PALAVRAS_CHAVE_BLOCO_PEDIDOS`);
   nas partes narrativas, as expressões ambíguas (`regularidade do
   corte`, que a autora também usa ao contestar o corte) ficam de fora.
   Casamento por palavra inteira, sem acento e sem caixa: "ilicitude do
   corte" (alegação da autora) nunca casa com "licitude do corte".
3. Orientações do advogado (`orientacoes_advogado`, entrada opcional, uso
   interno do host): só as deterministicamente verificáveis —
   NAO_MENCIONAR (termos) e TRATAR_APENAS_COMO_FATO (conceito fechado).
   Orientação que tente mexer em texto fixo, campo calculado, tópico,
   cálculo ou fato é rejeitada; ENFATIZAR e similares são só orientação
   de redação (devolvidas como não verificadas, nunca bloqueiam).

Nada aqui é validador de linguagem natural nem detector de paráfrase: só
expressões declaradas, casadas literalmente. Nenhum conteúdo de
orientação é persistido nem gravado no DOCX — este módulo só devolve
estruturas para a resposta da requisição.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import docx_block_engine as be

MAX_ORIENTACOES = 10
MAX_TERMOS = 10
MIN_TERMO = 3
MAX_TERMO = 60

TIPOS_VERIFICAVEIS = ("NAO_MENCIONAR", "TRATAR_APENAS_COMO_FATO")
TIPOS_SO_REDACAO = ("ENFATIZAR", "REFORCAR", "DESTACAR")
"""Orientações de redação: o host as segue ao redigir, o Core não as
verifica nem bloqueia por elas nesta versão."""

CHAVES_ORIENTACAO = frozenset({"tipo", "termos", "conceito", "partes"})
"""Orientação não carrega conteúdo nem fato: só tipo, alvo e escopo."""

_MOTIVO_TIPO_PROIBIDO = {
    "INCLUIR_TOPICO": ("ALTERA_TOPICO", "Tópicos só mudam por nova decisão SIM/NÃO do advogado em 'topicos'."),
    "EXCLUIR_TOPICO": ("ALTERA_TOPICO", "Tópicos só mudam por nova decisão SIM/NÃO do advogado em 'topicos'."),
    "ALTERAR_TEXTO_FIXO": ("ALTERA_TEXTO_FIXO", "O texto fixo do Modelo Oficial nunca é alterado por orientação."),
    "ALTERAR_CALCULO": ("ALTERA_CALCULO", "Cálculos do sistema (tempestividade, proveito econômico) não são "
                                           "alteráveis por orientação."),
    "ALTERAR_CAMPO_CALCULADO": ("CAMPO_CALCULADO", "Campos calculados pelo sistema não são alteráveis por "
                                                   "orientação."),
    "INCLUIR_FATO": ("INTRODUZ_FATO", "Fatos vêm dos documentos do caso, nunca de orientação."),
}

EXPRESSOES_AMBIGUAS_NARRATIVA = frozenset({
    "regularidade do corte", "regularidade da suspensao",
})
"""Expressões do vocabulário de PEDIDOS_FINAIS que a narrativa da autora
usa legitimamente ("a autora questiona a regularidade do corte") — fora
das partes narrativas; em PEDIDOS_FINAIS continuam valendo."""

CONCEITOS_TRATAVEIS_COMO_FATO = {
    "corte_suspensao": {
        "nome_publico": "corte/suspensão do fornecimento",
        "topico": "licitude_cobranca_corte",
        "bloco": "LICITUDE_CORTE_SUSPENSAO",
        "expressoes_tese": (
            "licitude do corte", "licitude da suspensao",
            "corte foi licito", "suspensao foi licita", "corte licito", "suspensao licita",
            "legitimidade do corte", "legitimidade da suspensao", "corte legitimo", "suspensao legitima",
            "corte foi legitimo", "suspensao foi legitima",
            "regularidade do corte", "regularidade da suspensao", "corte foi regular", "suspensao foi regular",
            "exercicio regular do direito de suspender",
        ),
    },
}
"""Conceitos que o advogado pode mandar tratar só como fato. Lista
fechada: só entra conceito cuja tese tem vocabulário explícito e
verificável. A verificação recusa a qualificação jurídica (licitude,
legitimidade, regularidade) — a menção ao fato ("o fornecimento foi
suspenso em 10/03/2026") continua livre."""

ESCOPO_PADRAO_TRATAR_COMO_FATO_EXCLUI = frozenset({"SINOPSE_FATOS"})
"""A SINOPSE é narrativa da autora: por padrão não entra no escopo de
TRATAR_APENAS_COMO_FATO (a autora pode contestar a regularidade do
corte); o host a inclui explicitamente em `partes` se quiser."""


# ------------------------------------------------------------------ texto

def normalizar(texto) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem_acento.lower())


def contem_expressao(texto_normalizado: str, expressao) -> bool:
    """Expressão inteira (fronteira de palavra dos dois lados), sem acento
    e sem caixa — "ilicitude" nunca casa com "licitude"."""
    alvo = normalizar(expressao).strip()
    if not alvo:
        return False
    return re.search(r"(?<!\w)" + re.escape(alvo) + r"(?!\w)", texto_normalizado) is not None


# ------------------------------------------------------- partes e tópicos

def partes_variaveis(manifesto: dict | None) -> set:
    """Partes redigidas pelo host (placeholders e zonas
    VARIAVEL_LLM_AUTORIZADA). Sem manifesto (contrato legado), as quatro
    partes narrativas de sempre."""
    if manifesto is None:
        return {"SINOPSE_FATOS", "REALIDADE_FATICA", "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE", "PEDIDOS_FINAIS"}
    return {c["parte"] for c in _conteudos(manifesto) if c.get("modo") == "VARIAVEL_LLM_AUTORIZADA"}


def partes_por_modo(manifesto: dict | None, modo: str) -> set:
    return {c["parte"] for c in _conteudos(manifesto) if c.get("modo") == modo} if manifesto else set()


def _conteudos(manifesto: dict) -> list:
    grupos = [*(manifesto.get("topicos_decisao_advogado") or []), *(manifesto.get("secoes_incondicionais") or [])]
    return [c for g in grupos for c in g.get("conteudo") or []]


def _topicos(manifesto: dict | None) -> list:
    return list((manifesto or {}).get("topicos_decisao_advogado") or [])


def _nome_do_bloco(manifesto: dict | None, bloco: str) -> str:
    for t in _topicos(manifesto):
        if t["topic_id"] == bloco:
            return t["nome_publico"]
    return bloco


# ----------------------------------------------------------- resultados

@dataclass
class AnaliseOrientacoes:
    aceitas: list = field(default_factory=list)
    rejeitadas: list = field(default_factory=list)
    nao_verificadas: list = field(default_factory=list)


def _violacao(parte: str, regra: str, detalhe: str) -> dict:
    return {"parte": parte, "regra": regra, "detalhe": detalhe}


# ---------------------------------------------------- 1. decisões aplicadas

def verificar_decisoes_aplicadas(manifesto: dict | None, topicos: dict, estados_blocos: dict) -> list:
    """Tópico SIM -> bloco INCLUIR; tópico NÃO -> bloco EXCLUIR."""
    erros = []
    for t in _topicos(manifesto):
        resposta = (topicos or {}).get(t["chave"])
        if resposta is None:
            continue
        esperado = "INCLUIR" if resposta == "SIM" else "EXCLUIR"
        if estados_blocos.get(t["topic_id"]) != esperado:
            erros.append(_violacao(
                "topicos", "DECISAO_NAO_APLICADA",
                f"O tópico \"{t['nome_publico']}\" foi marcado {resposta} pelo advogado, mas a composição "
                f"não o refletiu."))
    return erros


# ------------------------------------------------- 2. coerência com o NÃO

def verificar_coerencia_topicos(partes: dict, estados_blocos: dict, manifesto: dict | None = None) -> list:
    """Nenhuma parte variável nomeia a tese de um bloco excluído."""
    violacoes = []
    for nome, texto in partes.items():
        if not texto:
            continue
        v = normalizar(texto)
        for bloco, expressoes in be.PALAVRAS_CHAVE_BLOCO_PEDIDOS.items():
            if estados_blocos.get(bloco) != "EXCLUIR":
                continue
            candidatas = [e for e in expressoes
                          if nome == "PEDIDOS_FINAIS" or normalizar(e) not in EXPRESSOES_AMBIGUAS_NARRATIVA]
            achadas = [e for e in candidatas if contem_expressao(v, e)]
            if achadas:
                violacoes.append(_violacao(
                    nome, "TOPICO_EXCLUIDO",
                    f"Reescreva {nome} sem a tese \"{_nome_do_bloco(manifesto, bloco)}\", marcada NÃO pelo "
                    f"advogado (expressões encontradas: {', '.join(sorted(set(achadas)))})."))
    return violacoes


# ------------------------------------------------------- 3. orientações

def analisar_orientacoes(orientacoes, manifesto: dict | None, topicos: dict,
                         campos_calculados: set) -> AnaliseOrientacoes:
    """Classifica cada orientação em aceita, rejeitada (bloqueia a
    finalização: a peça contrariaria o comando) ou não verificada (só
    redação). Nunca lê documento nem texto: decide pela forma e pelas
    decisões atuais do advogado."""
    analise = AnaliseOrientacoes()
    if not orientacoes:
        return analise
    if not isinstance(orientacoes, list) or len(orientacoes) > MAX_ORIENTACOES:
        analise.rejeitadas.append({"indice": None, "tipo": None, "motivo_codigo": "FORMA_INVALIDA",
                                   "motivo": f"'orientacoes_advogado' deve ser uma lista de até "
                                             f"{MAX_ORIENTACOES} orientações."})
        return analise

    variaveis = partes_variaveis(manifesto)
    documentais = partes_por_modo(manifesto, "DADO_DOCUMENTAL")
    topicos = topicos or {}

    for i, o in enumerate(orientacoes):
        def rejeitar(codigo, motivo, tipo=None):
            analise.rejeitadas.append({"indice": i, "tipo": tipo, "motivo_codigo": codigo, "motivo": motivo})

        if not isinstance(o, dict) or not isinstance(o.get("tipo"), str):
            rejeitar("FORMA_INVALIDA", "Cada orientação é um objeto com 'tipo'.")
            continue
        tipo = o["tipo"].strip().upper()
        extras = sorted(set(o) - CHAVES_ORIENTACAO)
        if tipo in _MOTIVO_TIPO_PROIBIDO:
            rejeitar(*_MOTIVO_TIPO_PROIBIDO[tipo], tipo=tipo)
            continue
        if tipo in TIPOS_SO_REDACAO:
            analise.nao_verificadas.append({
                "indice": i, "tipo": tipo,
                "motivo": "Orientação de redação: siga-a ao redigir as partes variáveis; o sistema não a "
                          "verifica nem a usa para recusar a peça."})
            continue
        if tipo not in TIPOS_VERIFICAVEIS:
            rejeitar("TIPO_NAO_SUPORTADO",
                     f"Tipo não suportado. O sistema verifica só {', '.join(TIPOS_VERIFICAVEIS)}; texto fixo, "
                     f"tópicos, cálculos, campos calculados e fatos não são alteráveis por orientação.", tipo)
            continue
        if extras:
            rejeitar("FORMA_INVALIDA", f"Orientação não carrega conteúdo nem fato; campos não aceitos: {extras}.",
                     tipo)
            continue

        partes = o.get("partes")
        if partes is not None and (not isinstance(partes, list) or not all(isinstance(p, str) for p in partes)
                                   or not partes):
            rejeitar("FORMA_INVALIDA", "'partes', quando informado, é uma lista não vazia de partes variáveis.",
                     tipo)
            continue
        fora = []
        for p in partes or []:
            if p in campos_calculados:
                rejeitar("CAMPO_CALCULADO", f"{p} é calculado pelo sistema; orientação não o alcança.", tipo)
                fora.append(p)
                break
            if p not in variaveis:
                origem = "dado extraído dos documentos" if p in documentais else "texto fixo ou parte desconhecida"
                rejeitar("PARTE_FORA_DO_ESCOPO",
                         f"{p} não é parte redigível ({origem}); orientações valem só para as partes variáveis "
                         f"autorizadas.", tipo)
                fora.append(p)
                break
        if fora:
            continue

        if tipo == "NAO_MENCIONAR":
            termos = o.get("termos")
            if (not isinstance(termos, list) or not termos or len(termos) > MAX_TERMOS
                    or not all(isinstance(t, str) and MIN_TERMO <= len(t.strip()) <= MAX_TERMO for t in termos)):
                rejeitar("TERMO_INVALIDO", f"NAO_MENCIONAR exige 'termos': 1 a {MAX_TERMOS} termos de "
                                           f"{MIN_TERMO} a {MAX_TERMO} caracteres.", tipo)
                continue
            if o.get("conceito") is not None:
                rejeitar("FORMA_INVALIDA", "NAO_MENCIONAR usa 'termos', não 'conceito'.", tipo)
                continue
            conflito = _conflito_com_topico_sim(termos, manifesto, topicos)
            if conflito:
                rejeitar("CONFLITA_TOPICO_SIM",
                         f"O termo \"{conflito[0]}\" corresponde ao tópico \"{conflito[1]}\", marcado SIM. Para "
                         f"retirá-lo da peça é preciso nova decisão NÃO do advogado.", tipo)
                continue
            analise.aceitas.append({"indice": i, "tipo": tipo, "termos": [t.strip() for t in termos],
                                    "partes": sorted(partes or variaveis)})
            continue

        # TRATAR_APENAS_COMO_FATO
        conceito = o.get("conceito")
        if o.get("termos") is not None:
            rejeitar("FORMA_INVALIDA", "TRATAR_APENAS_COMO_FATO usa 'conceito', não 'termos'.", tipo)
            continue
        if conceito not in CONCEITOS_TRATAVEIS_COMO_FATO:
            rejeitar("CONCEITO_NAO_SUPORTADO",
                     f"Conceito sem verificação determinística nesta versão. Conceitos aceitos: "
                     f"{', '.join(CONCEITOS_TRATAVEIS_COMO_FATO)}. Para os demais, use NAO_MENCIONAR com os "
                     f"termos a evitar.", tipo)
            continue
        info = CONCEITOS_TRATAVEIS_COMO_FATO[conceito]
        if topicos.get(info["topico"]) == "SIM":
            rejeitar("CONFLITA_TOPICO_SIM",
                     f"Tratar {info['nome_publico']} apenas como fato contradiz o tópico de licitude marcado SIM. "
                     f"É preciso nova decisão NÃO do advogado sobre esse tópico.", tipo)
            continue
        escopo = partes or sorted(variaveis - ESCOPO_PADRAO_TRATAR_COMO_FATO_EXCLUI)
        analise.aceitas.append({"indice": i, "tipo": tipo, "conceito": conceito, "partes": sorted(escopo)})
    return analise


def _conflito_com_topico_sim(termos: list, manifesto: dict | None, topicos: dict):
    for t in _topicos(manifesto):
        if topicos.get(t["chave"]) != "SIM":
            continue
        nome = normalizar(t["nome_publico"])
        teses = [normalizar(e) for e in be.PALAVRAS_CHAVE_BLOCO_PEDIDOS.get(t["topic_id"], ())]
        for termo in termos:
            if contem_expressao(nome, termo) or any(contem_expressao(e, termo) for e in teses):
                return termo.strip(), t["nome_publico"]
    return None


def verificar_orientacoes(aceitas: list, partes: dict) -> list:
    """Aplica as orientações aceitas sobre o texto das partes variáveis."""
    violacoes = []
    for o in aceitas:
        for nome in o["partes"]:
            texto = partes.get(nome)
            if not texto:
                continue
            v = normalizar(texto)
            if o["tipo"] == "NAO_MENCIONAR":
                achados = [t for t in o["termos"] if contem_expressao(v, t)]
                if achados:
                    violacoes.append(_violacao(
                        nome, "NAO_MENCIONAR",
                        f"Reescreva {nome} sem mencionar {', '.join(repr(a) for a in achados)}, conforme "
                        f"orientação do advogado."))
            else:
                info = CONCEITOS_TRATAVEIS_COMO_FATO[o["conceito"]]
                achados = [e for e in info["expressoes_tese"] if contem_expressao(v, e)]
                if achados:
                    violacoes.append(_violacao(
                        nome, "TRATAR_APENAS_COMO_FATO",
                        f"Reescreva {nome} tratando {info['nome_publico']} apenas como fato, sem qualificá-lo "
                        f"juridicamente (expressões encontradas: {', '.join(sorted(set(achados)))})."))
    return violacoes
