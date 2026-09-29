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

Contrato do HOST (gate de compatibilidade host, emenda da ADR-0021):
"não expor chaves internas ao advogado" não é "não expor contrato ao
host". `descrever_contrato_host` publica, machine-readable, os estados
que o host deriva dos documentos (chave, significado, fonte, efeito de
true/false/INDETERMINADO), os dados documentais de cada tópico e as
chaves aceitas; `ResultadoTopicMatrix.suporte_ausente` devolve ao host a
chave de cada pendência de suporte. Nada disso entra em `pendencias`.
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

DESCRICAO_ESTADO_HOST = {
    **DESCRICAO_SUPORTE_FACTUAL,
    "METODOLOGIA_APURACAO_DOCUMENTADA":
        "a metodologia de apuração efetivamente aplicada (critério do art. 595 da REN ANEEL 1.000/2021, "
        "período, ciclos e valores), registrada no memorial de cálculo ou de faturamento",
    "PROCEDIMENTO_ART_590_DOCUMENTADO":
        "a observância documentada das providências do art. 590 da REN ANEEL 1.000/2021 na inspeção",
    "REGISTRO_FOTOGRAFICO_DOCUMENTADO": "as fotografias da irregularidade registradas na inspeção",
    "INSPECAO_ACOMPANHADA_DOCUMENTADA":
        "o acompanhamento da inspeção por representante da unidade consumidora, registrado no TOI",
    "NOTIFICACAO_AUTORA_DOCUMENTADA":
        "a entrega comprovada à parte autora da documentação do procedimento (TOI, memorial de cálculo)",
    "LEVANTAMENTO_CARGA_DOCUMENTADO": "o levantamento da carga instalada na unidade consumidora",
    "AUSENCIA_TRANSFERENCIA_TITULARIDADE_COMPROVADA":
        "a comprovação de que não houve pedido nem efetivação de transferência da titularidade da unidade "
        "consumidora",
}
"""Contrato do HOST (gate de compatibilidade host, emenda da ADR-0021):
toda chave de `estado_processual` que o host pode derivar dos documentos
tem significado publicado por `ede_preparar_contestacao`. Estende
`DESCRICAO_SUPORTE_FACTUAL` (mesmas descrições para os fatos de gate)
com os estados de zona e de subbloco. `verificar_compatibilidade` exige
cobertura total."""

DOCUMENTOS_SUGERIDOS_ESTADO_HOST = {
    "PROCEDIMENTO_ART_590_DOCUMENTADO": ["toi", "documentos_procedimento_administrativo"],
    "REGISTRO_FOTOGRAFICO_DOCUMENTADO": ["registro_fotografico_inspecao"],
    "INSPECAO_ACOMPANHADA_DOCUMENTADA": ["toi"],
    "NOTIFICACAO_AUTORA_DOCUMENTADA": ["comprovante_entrega_documentacao"],
}
"""Orientação NÃO exaustiva, só onde o manifesto não dá nenhuma (os
subblocos das seções incondicionais não têm `campos_documentais`). Nos
demais casos a sugestão é o `campos_documentais` do tópico ou as fontes
da zona, lidas do manifesto. Nunca enum, nunca condição de validade: o
host reconhece o suporte pelo conteúdo de qualquer documento."""

DOCUMENTOS_SUGERIDOS_DADO_HOST = {
    "NUMERO_PROCESSO": ["peticao_inicial"],
    "AUTOR": ["peticao_inicial"],
    "IRREGULARIDADE_ENCONTRADA": ["toi"],
    "FOTOS_DA_IRREGULARIADE": ["registro_fotografico_inspecao"],
}
"""Mesmo critério, para os campos documentais (seções sem
`campos_documentais` e a irregularidade, cujo tópico da Reconvenção só
lista a fatura e o memorial)."""

CONTRATO_DADO_HOST = {
    "IRREGULARIDADE_ENCONTRADA": {
        "descricao": "Somente o nome ou tipo da irregularidade constatada no TOI, em redação natural e "
                     "minúsculas, ressalvados nomes próprios e siglas (ex.: desvio de energia antes do "
                     "medidor). O modelo já exibe o campo em negrito; a marcação **...**, se usada, envolve "
                     "o valor inteiro, nunca parte dele.",
        "restricoes": [
            "não repetir o texto fixo que envolve o campo ('Na ocasião, foi constatada irregularidade do "
            "tipo,' antes e ', circunstância que impedia o registro integral...' depois)",
            "não explicar tecnicamente a irregularidade (isso é DESENVOLVIMENTO_TECNICO_IRREGULARIDADE)",
            "não escrever integralmente em caixa alta",
            "não mencionar assinatura do TOI nem a origem do dado",
        ],
    },
    "VALOR_FRA": {
        "descricao": "Valor do débito da recuperação de consumo, em formato monetário brasileiro (ex.: "
                     "R$ 2.097,63), exatamente como consta da fatura de recuperação ou do memorial; nunca "
                     "calculado, estimado nem arredondado pelo host. Só é enviado com a reconvenção SIM.",
        "restricoes": [
            "valor documentado -> preencher o campo e VALOR_FRA_DOCUMENTADO = true",
            "sem valor documentado -> VALOR_FRA_DOCUMENTADO false ou omitido; o finalizador devolve "
            "NEEDS_INPUT e a pendência vai ao advogado",
            "valores divergentes entre documentos -> VALOR_FRA_DOCUMENTADO = INDETERMINADO",
            "nunca usar sentinela de ausência ('NÃO INFORMADO') nem valor provisório para atravessar a "
            "finalização",
        ],
    },
}
"""Onde o texto do schema serve ao fluxo legado mas induziria o host MCP a
erro (gate de compatibilidade host, revisão de 28/09/2026): o contrato
publicado ao host é o do comportamento real. `IRREGULARIDADE_ENCONTRADA`:
contrato atômico da Etapa 5.3-B (`validate_placeholder_semantics.
_validar_irregularidade_encontrada`, CLAUDE.md §14). `VALOR_FRA`: no V1 o
campo só existe dentro da Reconvenção, cujo tópico SIM exige
`VALOR_FRA_DOCUMENTADO` true; a sentinela do schema ("NÃO INFORMADO")
pertence ao fluxo local, que aborta com ela (`gerar_contestacao.
PLACEHOLDERS_CRITICOS_NAO_SENTINELA`)."""

REGRA_ESTADO_HOST = {
    "gate_factual": {
        "true": "Consta de documento do caso, com proveniência: o tópico marcado SIM pode ser incluído.",
        "false": "Os documentos não trazem esse suporte: com o tópico SIM, o finalizador devolve NEEDS_INPUT "
                 "(suporte_ausente); apresente a pendência ao advogado em linguagem comum.",
        "INDETERMINADO": "Documentos contraditórios: com o tópico SIM, o finalizador devolve NEEDS_INPUT por "
                         "contradição.",
        "omitida": "Mesmo efeito de false.",
    },
    "suporte_informativo": {
        "true": "Suporte localizado: nenhum aviso.",
        "false": "O tópico SIM é incluído mesmo assim, com aviso não bloqueante (dados_nao_bloqueantes).",
        "INDETERMINADO": "Mesmo efeito de false.",
        "omitida": "Mesmo efeito de false.",
    },
    "subbloco": {
        "true": "O trecho factual correspondente permanece na peça.",
        "false": "O trecho é omitido; o finalizador devolve aviso não bloqueante (dados_nao_bloqueantes).",
        "INDETERMINADO": "Documentos contraditórios: a composição é recusada, mesmo que o tópico do trecho "
                         "não seja incluído.",
        "omitida": "Mesmo efeito de false.",
    },
    "zona": {
        "true": "A zona pode receber conteúdo (opcional) em 'zonas', com a base documental, quando o tópico "
                "for incluído.",
        "false": "Zona excluída: não envie conteúdo para ela (conteúdo enviado é recusado).",
        "INDETERMINADO": "Documentos contraditórios: a composição é recusada quando o tópico for incluído.",
        "omitida": "Mesmo efeito de false.",
    },
}

REGRA_ESPECIFICA_ESTADO_HOST = {
    "CORTE_EFETIVO": {
        "true": "Só com evidência que a Ré não contradiga (ex.: registro operacional da concessionária). "
                "Alegação da autora, ameaça ou aviso de suspensão, pedido preventivo, pedido de "
                "restabelecimento isolado ou débito nunca bastam.",
        "false": "Não há corte ou suspensão efetiva documentada.",
        "INDETERMINADO": "Documentos contraditórios: com o tópico SIM, NEEDS_INPUT por contradição.",
        "omitida": "O fato é perguntado ao advogado (fatos_publicos.corte_efetivo).",
        "nota": "Fato separado da decisão do tópico: nunca inferido dela, nem o inverso. Se o advogado também "
                "responder fatos_publicos.corte_efetivo e divergir dos documentos, NEEDS_INPUT.",
    },
}
"""INV-CORTE-GATE-HUMANO, só descrita para o host; a semântica é a de
`traduzir`, inalterada."""

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
    suporte_ausente: tuple[dict, ...] = ()
    """Só em NEEDS_INPUT, para o HOST (nunca exibido ao advogado):
    `{topico, chave_estado, motivo: AUSENTE|FALSE|INDETERMINADO}` de cada
    pendência de suporte factual, para o host rever o `estado_processual`
    derivado dos documentos antes de levar a pendência ao advogado."""


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
    # Contrato do host: todo estado publicado tem significado (as sugestões
    # de documento são orientação, nunca exigidas).
    fatos_zona = _fatos_por_zona(catalogo)
    for grupo in [*_topicos(manifesto), *(manifesto.get("secoes_incondicionais") or [])]:
        for chave, _papel, _documentos in _estados_host(grupo, fatos_zona, _reservados(manifesto)):
            if chave not in DESCRICAO_ESTADO_HOST:
                raise ManifestoIncompativel(f"estado do host sem descrição: {chave}")


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


# ------------------------------------------------ contrato do host (estado)

def _fatos_por_zona(catalogo: dict) -> dict:
    return {z["id"]: list(z.get("requires_facts") or []) for z in catalogo.get("zones", [])}


def _reservados(manifesto: dict) -> set:
    return set(manifesto.get("estados_reservados_ao_core") or [])


def _documentos_sugeridos(override, *candidatos) -> list:
    for c in (override, *candidatos):
        if c:
            return list(c)
    return []


def _entrada_estado(chave: str, papel: str, documentos: list) -> dict:
    return {
        "chave_estado": chave,
        "papel": papel,
        "descricao": DESCRICAO_ESTADO_HOST[chave],
        "requisito": f"Algum documento do caso, qualquer que seja o nome, o formato ou o tipo do arquivo, "
                     f"demonstra {DESCRICAO_ESTADO_HOST[chave]}.",
        "documentos_sugeridos": documentos,
        "regra": dict(REGRA_ESPECIFICA_ESTADO_HOST.get(chave) or REGRA_ESTADO_HOST[papel]),
    }


def _estados_host(grupo: dict, fatos_zona: dict, reservados: set) -> list[tuple[str, str, list]]:
    """(chave, papel, documentos_sugeridos) dos estados que o host deriva dos
    documentos para um tópico ou seção incondicional, lidos do manifesto
    (`gate_factual`, `suporte_informativo`, `subblocos_derivados`, zonas
    do `conteudo`) e dos `requires_facts` das zonas no catálogo. Estados
    reservados ao Core nunca entram."""
    campos = grupo.get("campos_documentais") or []
    itens = [(f, "gate_factual", None) for f in grupo.get("gate_factual") or []]
    info = grupo.get("suporte_informativo")
    if info:
        itens.append((info["fato"], "suporte_informativo", None))
    itens += [(sb["fato"], "subbloco", None) for sb in grupo.get("subblocos_derivados") or []]
    for c in grupo.get("conteudo") or []:
        if c.get("parte") in fatos_zona:
            fontes_zona = [f for f in c.get("fontes") or [] if f != "fatos_com_proveniencia"]
            itens += [(f, "zona", fontes_zona) for f in fatos_zona[c["parte"]]]
    return [(chave, papel, _documentos_sugeridos(DOCUMENTOS_SUGERIDOS_ESTADO_HOST.get(chave), fontes_zona, campos))
            for chave, papel, fontes_zona in itens if chave not in reservados]


def _suporte_factual_host(grupo: dict, fatos_zona: dict, reservados: set) -> list:
    return [_entrada_estado(chave, papel, documentos)
            for chave, papel, documentos in _estados_host(grupo, fatos_zona, reservados)]


def _dado_host(campo: str, schema: dict, campos: list, exigido_quando: dict) -> dict:
    contrato = (schema.get("placeholder_contracts") or {}).get(campo) or {}
    host = CONTRATO_DADO_HOST.get(campo) or {}
    return {
        "campo": campo,
        "campo_finalizador": "placeholders",
        "descricao": host.get("descricao") or contrato.get("descricao", ""),
        "restricoes": list(host.get("restricoes") or contrato.get("restricoes") or []),
        "documentos_sugeridos": _documentos_sugeridos(DOCUMENTOS_SUGERIDOS_DADO_HOST.get(campo), campos),
        "exigido_quando": exigido_quando,
    }


def _dados_documentais_host(grupo: dict, schema: dict, exigido_quando: dict) -> list:
    """Campos que o host preenche em `placeholders` a partir dos
    documentos: as partes `DADO_DOCUMENTAL` do grupo. Marcadores de
    pós-edição manual (telas, fotos) são do Core, nunca do host."""
    campos = grupo.get("campos_documentais") or []
    return [_dado_host(c["parte"], schema, campos, exigido_quando)
            for c in grupo.get("conteudo") or [] if c.get("modo") == "DADO_DOCUMENTAL"]


def _campos_calculados(manifesto: dict) -> list:
    """O que o sistema preenche sozinho e o host não envia: partes
    `CALCULADO_PELO_CORE` do manifesto e os campos contidos em subblocos
    (`contem`, ex.: marcador das fotos)."""
    grupos = [*_topicos(manifesto), *(manifesto.get("secoes_incondicionais") or [])]
    campos = {c["parte"] for g in grupos for c in g.get("conteudo") or [] if c.get("modo") == "CALCULADO_PELO_CORE"}
    campos |= {x for g in grupos for sb in g.get("subblocos_derivados") or [] for x in sb.get("contem") or []}
    return sorted(campos)


def descrever_contrato_host(manifesto: dict, catalogo: dict, schema: dict) -> dict:
    """Contrato machine-readable do HOST (gate de compatibilidade host,
    emenda da ADR-0021) — distinto da Topic Matrix pública: o que o
    host deriva dos documentos e envia ao finalizador, nunca o que ele
    pergunta ao advogado. Derivado do manifesto, do catálogo e do schema
    de placeholders (nenhuma regra jurídica nova)."""
    fatos_zona = _fatos_por_zona(catalogo)
    reservados = _reservados(manifesto)
    por_topico = {
        t["chave"]: {
            "suporte_factual_host": _suporte_factual_host(t, fatos_zona, reservados),
            "dados_documentais_host": _dados_documentais_host(
                t, schema, {"topico": t["chave"], "resposta": "SIM"}),
        }
        for t in _topicos(manifesto)
    }
    secoes = []
    for s in manifesto.get("secoes_incondicionais") or []:
        suporte = _suporte_factual_host(s, fatos_zona, reservados)
        dados = _dados_documentais_host(s, schema, {"sempre": True})
        if suporte or dados:
            secoes.append({"secao": s["id"], "suporte_factual_host": suporte, "dados_documentais_host": dados})
    chaves = {e["chave_estado"] for g in [*por_topico.values(), *secoes] for e in g["suporte_factual_host"]}
    return {
        "por_topico": por_topico,
        "secoes_incondicionais": secoes,
        "chaves_estado_host": sorted(chaves),
        "estados_calculados_pelo_sistema": sorted(reservados),
        "campos_calculados_pelo_sistema": _campos_calculados(manifesto),
    }


def chaves_estado_host(manifesto: dict, catalogo: dict) -> frozenset:
    """As únicas chaves de `estado_processual` aceitas do host no fluxo
    do manifesto — as mesmas que `ede_preparar_contestacao` publica."""
    return frozenset(descrever_contrato_host(manifesto, catalogo, {})["chaves_estado_host"])


_MOTIVO_SUPORTE = {None: "AUSENTE", False: "FALSE", "INDETERMINADO": "INDETERMINADO"}


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
    suporte_ausente = []
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
                    suporte_ausente.append({"topico": t["chave"], "chave_estado": f,
                                            "motivo": _MOTIVO_SUPORTE.get(estado_motor.get(f), "AUSENTE")})
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
        return ResultadoTopicMatrix(status="NEEDS_INPUT", pendencias=tuple(dict.fromkeys(pendencias)),
                                    suporte_ausente=tuple(suporte_ausente))
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
