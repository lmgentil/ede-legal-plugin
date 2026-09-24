#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topic_matrix.py — tradução DETERMINÍSTICA da Topic Matrix pública (as
decisões SIM/NÃO do advogado, declaradas no manifesto do Modelo Oficial)
para a entrada do motor documental (`docx_block_engine`) — Gate de
ativação do Modelo Oficial V1 no homolog, ADR-0020.

Fonte única: o manifesto versionado (`modelo_oficial_versoes`). Este
módulo não conhece nenhum tópico por nome; lê `topicos_decisao_advogado`,
`entradas_factuais_publicas` e os subblocos derivados do manifesto e o
`decision_mode` de cada bloco no catálogo da MESMA versão.

Regras (todas fail-closed, nenhuma heurística jurídica):

- Toda pergunta pública precisa de resposta SIM/NÃO; faltando alguma, o
  resultado é NEEDS_INPUT com a pergunta em linguagem jurídica, nunca um
  default.
- SIM exige TODO o suporte factual do tópico (`gate_factual`)
  confirmado (`true`). Fato ausente, falso ou indeterminado nunca vira
  inclusão silenciosa: NEEDS_INPUT, explicando o que falta.
- O fato público "corte/suspensão efetivamente ocorrido" e a decisão de
  incluir o tópico de licitude do corte são entradas SEPARADAS: nenhuma é
  inferida da outra.
- Blocos `estrategista`/`humano` recebem a decisão como
  `block_decisions`. Blocos `state_linked` (o estado do bloco é o fato
  vinculado) recebem, no estado processual entregue ao MOTOR, o fato
  vinculado AND a decisão do advogado: SIM só passa com o fato confirmado
  (logo, `true`); NÃO entrega `false` ao motor para aquele vínculo. Isso
  é a decisão efetiva de composição, não uma afirmação factual: o fato
  informado pelo host nunca é reescrito na resposta nem vira texto.
- Subblocos factuais sem prova são omitidos pelo próprio motor (vínculo
  `state_linked`, fato ausente -> EXCLUIR); este módulo só produz o aviso
  não bloqueante correspondente.
- Tópico sem gate, mas com `suporte_informativo` no manifesto (ADR-0021:
  revogação da gratuidade): SIM inclui o tópico; se o fato informado pelo
  host não for `true`, só um aviso não bloqueante — nunca pergunta, nunca
  bloqueio. O aviso é lido do fato ANTES de o vínculo mecânico
  `state_linked` sobrescrevê-lo.
- A Topic Matrix é só SIM/NÃO (INV-TOPIC-MATRIX-SO-SIM-NAO): dados de
  outro tipo têm campos próprios no finalizador, nunca aqui.

Nenhuma mensagem expõe tag SDT, id de bloco, placeholder ou chave de
estado interno: só `nome_publico`/`pergunta` do manifesto e as
descrições em linguagem jurídica abaixo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RESPOSTAS_VALIDAS = ("SIM", "NAO")

DESCRICAO_SUPORTE_FACTUAL = {
    "GRATUIDADE_CONCEDIDA": "a decisão que concedeu a gratuidade de justiça à parte autora",
    "AUSENCIA_TENTATIVA_ADMINISTRATIVA_COMPROVADA":
        "a comprovação de que a parte autora não buscou previamente a solução administrativa",
    "UC_TITULARIDADE_TERCEIRO_COMPROVADA":
        "a comprovação documental de que a unidade consumidora está em nome de terceiro",
    "DEFICIENCIAS_INICIAL_DOCUMENTADAS": "a indicação documentada das deficiências concretas da petição inicial",
    "EXISTE_DISCREPANCIA_VALOR_CAUSA":
        "a demonstração de que o valor da causa diverge do proveito econômico pretendido",
    "EVOLUCAO_CONSUMO_DOCUMENTADA": "o histórico de consumo anterior e posterior à regularização",
    "FATURA_RECUPERACAO_DOCUMENTADA": "a fatura ou o memorial da recuperação de consumo",
    "CORTE_EFETIVO": "a ocorrência efetiva de corte ou suspensão do fornecimento",
    "PEDIDO_DANO_MORAL_NA_INICIAL": "o pedido de indenização por dano moral formulado na petição inicial",
    "VALOR_FRA_DOCUMENTADO": "o valor do débito apurado, documentado na fatura de recuperação",
}
"""Uma descrição por fato de gate declarado no manifesto; a suíte exige
cobertura total (fato de gate sem descrição é defeito do plugin)."""

SUBBLOCOS_FACTUAIS_COM_AVISO = (
    "SUBBLOCO_CONFORMIDADE_ART_590",
    "SUBBLOCO_REGISTRO_FOTOGRAFICO",
    "SUBBLOCO_ACOMPANHAMENTO_INSPECAO",
    "SUBBLOCO_NOTIFICACAO_ADMINISTRATIVA",
    "SUBBLOCO_LEVANTAMENTO_CARGA",
)
"""Os trechos factuais aprovados na V1 (A1): sem prova, só o trecho sai e
o advogado é avisado. `SUBBLOCO_CUMULACAO_PEDIDOS`/`SUBBLOCO_AUSENCIA_
TRANSFERENCIA_TITULARIDADE` são anteriores à V1 e não têm aviso aprovado."""

AVISO_PADRAO_SUBBLOCO = {
    "SUBBLOCO_LEVANTAMENTO_CARGA":
        "Não foi comprovado o levantamento de carga da unidade consumidora; a afirmação correspondente foi omitida.",
}
"""Só para subbloco aprovado cujo manifesto não traz `aviso_se_omitido`."""


class ManifestoIncompativel(Exception):
    """Manifesto e catálogo da mesma versão não se correspondem (tópico
    apontando para bloco inexistente ou de modo não suportado, fato de
    gate sem descrição). Defeito do pacote do plugin, nunca do cliente."""


@dataclass(frozen=True)
class ResultadoTopicMatrix:
    status: Literal["OK", "NEEDS_INPUT", "INVALID"]
    block_decisions: dict = field(default_factory=dict)
    estado_processual_motor: dict = field(default_factory=dict)
    pendencias: tuple[str, ...] = ()
    erros: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()
    """Não bloqueantes (ADR-0021), só em OK: vão para
    `dados_nao_bloqueantes` da resposta."""


def _topicos(manifesto: dict) -> list[dict]:
    return manifesto.get("topicos_decisao_advogado") or []


def _entradas_factuais(manifesto: dict) -> list[dict]:
    return manifesto.get("entradas_factuais_publicas") or []


def verificar_compatibilidade(manifesto: dict, catalogo: dict) -> None:
    por_id = {b["id"]: b for b in catalogo.get("blocks", [])}
    manuais_cobertos = set()
    for t in _topicos(manifesto):
        bloco = por_id.get(t["topic_id"])
        if bloco is None:
            raise ManifestoIncompativel(f"tópico {t['chave']} aponta para bloco inexistente")
        modo = bloco["decision_mode"]
        if modo not in ("estrategista", "humano", "state_linked"):
            raise ManifestoIncompativel(f"tópico {t['chave']}: decision_mode {modo!r} não suportado")
        if modo != "state_linked":
            manuais_cobertos.add(bloco["id"])
        for fato in t.get("gate_factual", []):
            if fato not in DESCRICAO_SUPORTE_FACTUAL:
                raise ManifestoIncompativel(f"fato de gate sem descrição pública: {fato}")
        info = t.get("suporte_informativo")
        if info is not None and (not isinstance(info, dict) or not info.get("fato")
                                 or not str(info.get("aviso_se_nao_documentado") or "").strip()):
            raise ManifestoIncompativel(f"tópico {t['chave']}: suporte_informativo malformado")
    manuais = {b["id"] for b in por_id.values() if b["decision_mode"] in ("estrategista", "humano")}
    if manuais - manuais_cobertos:
        raise ManifestoIncompativel("bloco de decisão manual sem pergunta pública na Topic Matrix")
    for e in _entradas_factuais(manifesto):
        if e.get("tipo") != "SIM_NAO":
            raise ManifestoIncompativel(f"entrada factual {e['chave']}: tipo não suportado")


def descrever_topic_matrix_publica(manifesto: dict) -> dict:
    """O que o host pode mostrar ao advogado: chave pública, nome e
    pergunta. Nada de id de bloco, tag, placeholder ou estado interno."""
    return {
        "topicos": [
            {"chave": t["chave"], "nome_publico": t["nome_publico"], "pergunta": t["pergunta"]}
            for t in _topicos(manifesto)
        ],
        "fatos_publicos": [
            {"chave": e["chave"], "nome_publico": e["nome_publico"], "pergunta": e["pergunta"],
             "obrigatorio": bool(e.get("obrigatorio"))}
            for e in _entradas_factuais(manifesto)
        ],
        "respostas_validas": list(RESPOSTAS_VALIDAS),
    }


def _pendencia_suporte(nome_topico: str, fato: str, valor) -> str:
    descricao = DESCRICAO_SUPORTE_FACTUAL[fato]
    if fato == "CORTE_EFETIVO" and valor is False:
        return (f"O tópico \"{nome_topico}\" foi marcado como SIM, mas foi informado que não houve "
                f"corte ou suspensão efetiva do fornecimento. Confirme a ocorrência do corte ou "
                f"responda NÃO para este tópico.")
    if valor == "INDETERMINADO":
        return (f"O tópico \"{nome_topico}\" foi marcado como SIM, mas os documentos são contraditórios "
                f"quanto a {descricao}. Esclareça esse ponto ou responda NÃO para este tópico.")
    return (f"O tópico \"{nome_topico}\" foi marcado como SIM, mas não há suporte documental informado "
            f"para {descricao}. Apresente esse suporte ou responda NÃO para este tópico.")


def traduzir(manifesto: dict, catalogo: dict, topicos: dict, fatos_publicos: dict,
             estado_processual: dict) -> ResultadoTopicMatrix:
    verificar_compatibilidade(manifesto, catalogo)
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    topicos = topicos or {}
    fatos_publicos = fatos_publicos or {}
    estado_processual = dict(estado_processual or {})

    chaves_topicos = {t["chave"] for t in _topicos(manifesto)}
    chaves_fatos = {e["chave"] for e in _entradas_factuais(manifesto)}
    erros = [f"tópico desconhecido: {k}" for k in sorted(set(topicos) - chaves_topicos)]
    erros += [f"informação factual desconhecida: {k}" for k in sorted(set(fatos_publicos) - chaves_fatos)]
    erros += [f"resposta inválida para {k}: use SIM ou NAO" for k, v in sorted({**topicos, **fatos_publicos}.items())
              if v not in RESPOSTAS_VALIDAS]
    if erros:
        return ResultadoTopicMatrix(status="INVALID", erros=tuple(erros))

    pendencias = []
    fatos_resolvidos = {}
    fatos_publicos_pendentes = set()
    for e in _entradas_factuais(manifesto):
        chave_estado = e["alimenta_fato"]
        documental = estado_processual.get(chave_estado)
        publico = fatos_publicos.get(e["chave"])
        if publico is not None:
            valor = publico == "SIM"
            if isinstance(documental, bool) and documental != valor:
                pendencias.append(f"A resposta sobre \"{e['nome_publico']}\" diverge do que consta dos "
                                  f"documentos. Confirme a informação correta.")
                fatos_publicos_pendentes.add(chave_estado)
                continue
            fatos_resolvidos[chave_estado] = valor
        elif isinstance(documental, bool):
            fatos_resolvidos[chave_estado] = documental
        elif e.get("obrigatorio"):
            pendencias.append(f"Responda SIM ou NÃO: {e['pergunta']}")
            fatos_publicos_pendentes.add(chave_estado)

    for t in _topicos(manifesto):
        if t["chave"] not in topicos:
            pendencias.append(f"Responda SIM ou NÃO: {t['pergunta']}")

    estado_motor = {**estado_processual, **fatos_resolvidos}
    block_decisions = {}
    avisos = []
    for t in _topicos(manifesto):
        resposta = topicos.get(t["chave"])
        if resposta is None:
            continue
        bloco = por_id[t["topic_id"]]
        incluir = resposta == "SIM"
        if incluir:
            faltas = [f for f in t.get("gate_factual", []) if estado_motor.get(f) is not True]
            for f in faltas:
                if f not in fatos_publicos_pendentes:  # a pergunta do próprio fato já foi feita acima
                    pendencias.append(_pendencia_suporte(t["nome_publico"], f, estado_motor.get(f)))
            if faltas:
                continue
            info = t.get("suporte_informativo")
            if info and estado_processual.get(info["fato"]) is not True:
                avisos.append(info["aviso_se_nao_documentado"])
        if bloco["decision_mode"] == "state_linked":
            estado_motor[bloco["linked_fact"]] = incluir
        else:
            block_decisions[bloco["id"]] = "INCLUIR" if incluir else "EXCLUIR"

    if pendencias:
        return ResultadoTopicMatrix(status="NEEDS_INPUT", pendencias=tuple(dict.fromkeys(pendencias)))
    return ResultadoTopicMatrix(status="OK", block_decisions=block_decisions, estado_processual_motor=estado_motor,
                                avisos=tuple(avisos))


def dados_nao_bloqueantes(manifesto: dict, estados_blocos: dict) -> tuple[str, ...]:
    """Avisos dos trechos factuais omitidos por falta de prova, só quando
    o tópico/seção que os contém foi efetivamente incluído."""
    avisos = []
    grupos = [(t.get("subblocos_derivados") or [], estados_blocos.get(t["topic_id"]) == "INCLUIR")
              for t in _topicos(manifesto)]
    grupos += [(s.get("subblocos_derivados") or [], True) for s in manifesto.get("secoes_incondicionais") or []]
    for subblocos, pai_incluido in grupos:
        if not pai_incluido:
            continue
        for sb in subblocos:
            if sb["id"] not in SUBBLOCOS_FACTUAIS_COM_AVISO or estados_blocos.get(sb["id"]) == "INCLUIR":
                continue
            aviso = sb.get("aviso_se_omitido") or AVISO_PADRAO_SUBBLOCO.get(sb["id"])
            if aviso:
                avisos.append(aviso)
    return tuple(avisos)
