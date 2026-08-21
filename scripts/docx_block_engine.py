#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_block_engine.py — motor de composição dos blocos condicionais/
container da Contestação (Etapa 5, INV-COMPOSICAO-BLOCOS — SPEC-0001 §5).

Separação estrita entre DECISÃO e MECÂNICA:
  - a DECISÃO jurídica (incluir/excluir cada tese condicional) é
    responsabilidade EXCLUSIVA da etapa estratégica obrigatória
    (estrategista-contestacao-ede, via Skill `contestacao` —
    INV-CONTESTACAO-ESTRATEGIA). Este módulo nunca decide nada por conta
    própria: não há heurística jurídica aqui (nenhum
    "if consumidor: incluir_cdc()").
  - a MECÂNICA documental (validar o catálogo, validar as decisões
    recebidas, resolver estados CONTAINER_DERIVED, cruzar o catálogo
    contra os SDTs reais do template, executar deterministicamente
    unwrap/remove via lxml.etree) é o único papel deste módulo.

Fail-closed em cada etapa — ver ComposicaoAbortada. Nenhuma etapa produz
DOCX parcial: qualquer falha aborta antes da escrita final.

Etapa 5.2 (calibração pós-Teste Real 01) acrescenta três conceitos
puramente mecânicos, nenhum deles heurística jurídica:
  - decision_mode "humano": mesmo contrato de decisão que "estrategista"
    (decisoes_blocos.json), só documenta que a origem exigida da decisão é
    autorização expressa do advogado, não a análise estratégica sozinha
    (RECONVENCAO — INV-RECONVENCAO-AUTORIZACAO-EXPRESSA). Sem decisão
    registrada, o fail-closed de sempre (decisao_ausente/
    decisao_indeterminada) já cobre o caso — nenhuma mecânica nova.
  - `requires_fact` (catálogo): GATE fático opcional por bloco
    'estrategista'/'humano' — INCLUIR só é aceito se
    `fatos_processuais[key]` for verdadeiro; a decisão de INCLUIR vs.
    EXCLUIR quando o fato é verdadeiro continua exclusivamente
    estratégica. Infraestrutura geral do motor, disponível para futuros
    blocos — nenhum bloco do catálogo atual o usa (LICITUDE_CORTE_
    SUSPENSAO migrou para `state_linked` numa correção arquitetural
    posterior, ver abaixo — INV-CORTE-LINKED).
  - decision_mode "state_linked" + `linked_fact` (catálogo, correção
    pontual pós-Etapa 5.2): VÍNCULO determinístico ESTADO PROCESSUAL ->
    BLOCO — o estado do bloco *é* `fatos_processuais[linked_fact]`
    (true->INCLUIR, false->EXCLUIR, 'INDETERMINADO'->aborta); nenhuma
    decisão da etapa estratégica é aceita (PRELIMINAR_REVOGACAO_
    GRATUIDADE — INV-GRATUIDADE-LINKED; LICITUDE_CORTE_SUSPENSAO —
    INV-CORTE-LINKED, correção arquitetural: modelagem anterior como
    gate + decisão estratégica permitiu, em teste real, inclusão baseada
    em mera alegação da autora, não em corte efetivamente comprovado).
    Diferente de "linked"
    (BLOCO -> BLOCO, ex.: INLINE_COM_RECONVENCAO -> RECONVENCAO,
    preservado intocado) e diferente de `requires_fact` (que é um gate,
    não um vínculo — ainda deixa a decisão para o estrategista). Estado
    processual resolvido pela Skill `contestacao` a partir dos
    documentos, nunca por busca lexical em texto.

lxml.etree é a tecnologia obrigatória para toda manipulação estrutural
(SDT/container/hierarquia/parágrafo/drawing/bookmark) — regex continua
reservado exclusivamente à substituição pontual de <w:t> já implementada
em docx_template_engine.py (não duplicada aqui).
"""
import json
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

import lxml.etree as LET

sys.path.insert(0, str(Path(__file__).parent))
from docx_template_engine import (  # noqa: E402
    _importar_toolkit,
    carregar_schema,
    substituir_placeholders,
    validar_placeholders,
    verificar_template_lock,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ESTADOS_VALIDOS = ("INCLUIR", "EXCLUIR", "INDETERMINADO")
TIPOS_VALIDOS = ("FIXO", "CONDICIONAL_PADRAO", "CONDICIONAL_HIBRIDO", "CONTAINER_DERIVED")
# "humano" (Etapa 5.2, INV-RECONVENCAO-AUTORIZACAO-EXPRESSA): mesmo contrato
# de decisão que "estrategista" (vem de decisoes_blocos.json, um dos três
# estados) — a diferença é só documental/de origem: sinaliza que a decisão
# não pode ser tomada pela análise estratégica sozinha, e sim por
# autorização expressa do advogado (AskUserQuestion na Skill `contestacao`).
# Sem resposta, o bloco fica ausente/INDETERMINADO em decisoes_blocos.json
# e o fail-closed já existente (decisao_ausente/decisao_indeterminada)
# aborta o pipeline — nenhuma mecânica nova precisa disso além do rótulo.
#
# "state_linked" (correção pontual pós-Etapa 5.2 — INV-GRATUIDADE-LINKED):
# vínculo determinístico ESTADO PROCESSUAL -> BLOCO, distinto de "linked"
# (que é BLOCO -> BLOCO, ex.: INLINE_COM_RECONVENCAO -> RECONVENCAO, e
# permanece intocado). Um bloco "state_linked" declara `linked_fact: "<KEY>"`
# no catálogo; seu estado é resolvido exclusivamente a partir de
# `fatos_processuais[KEY]` (true->INCLUIR, false->EXCLUIR,
# "INDETERMINADO"->aborta) — NUNCA aceita decisão manual em
# decisoes_blocos.json (mesmo tratamento fail-closed já dado a
# "derived"/"linked": decisão fornecida é rejeitada, não ignorada). Isto é
# deliberadamente diferente de `requires_fact` (gate + decisão
# estratégica — infraestrutura geral, sem uso atual no catálogo desde
# que LICITUDE_CORTE_SUSPENSAO migrou para `state_linked`,
# INV-CORTE-LINKED): `requires_fact` é um GATE que só restringe INCLUIR,
# deixando a decisão INCLUIR/EXCLUIR para a etapa estratégica quando o
# fato é verdadeiro; `state_linked` não deixa
# decisão alguma para o estrategista — o estado do bloco *é* o estado
# processual, sempre.
DECISION_MODES_VALIDOS = ("estrategista", "humano", "derived", "linked", "state_linked")
# Blocos cujo decision_mode aceita decisão registrada em decisoes_blocos.json
# (folhas "reais" — não containers/inline resolvidos automaticamente).
DECISION_MODES_MANUAIS = ("estrategista", "humano")
CARDINALIDADES_VALIDAS = ("ONE", "MC_PAIR")
_CARDINALIDADE_ESPERADA = {"ONE": 1, "MC_PAIR": 2}


def _qn(tag):
    return f"{{{W}}}{tag}"


class ComposicaoAbortada(Exception):
    """Erro fail-closed de qualquer etapa da composição de blocos.
    `stage` identifica em qual etapa (Fase A-M, SPEC-0001) a falha
    ocorreu — nunca deve virar fallback silencioso; a etapa chamadora
    (scripts/gerar_contestacao.py) propaga stage/motivo no relatório."""

    def __init__(self, stage, motivo):
        self.stage = stage
        self.motivo = motivo
        super().__init__(f"stage={stage} — {motivo}")


# ============================================================== Fase A/B — catálogo
def carregar_catalogo(caminho) -> dict:
    caminho = Path(caminho)
    if not caminho.exists():
        raise ComposicaoAbortada("catalogo_ausente", f"catálogo não encontrado: {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ComposicaoAbortada("catalogo_invalido", f"JSON malformado: {e}")


def validar_catalogo(catalogo: dict) -> None:
    """Validação estrutural pura do catálogo — não olha decisões nem
    template. ids/tags únicos, parent/children existentes e coerentes nos
    dois sentidos, sem ciclos, tipo/decision_mode/cardinality válidos e
    consistentes entre si, dependencies referenciando placeholders
    declarados. Qualquer falha aborta com stage='catalogo_invalido'."""
    blocos = catalogo.get("blocks")
    if not isinstance(blocos, list) or not blocos:
        raise ComposicaoAbortada("catalogo_invalido", "catálogo sem 'blocks' (lista não vazia)")

    ids_vistos, tags_vistas, por_id = set(), set(), {}
    for b in blocos:
        for campo in ("id", "tag", "tipo", "parent", "children", "decision_mode", "cardinality"):
            if campo not in b:
                raise ComposicaoAbortada("catalogo_invalido", f"bloco sem campo obrigatório '{campo}': {b}")
        bid, tag = b["id"], b["tag"]
        if bid in ids_vistos:
            raise ComposicaoAbortada("catalogo_invalido", f"id duplicado no catálogo: {bid}")
        if tag in tags_vistas:
            raise ComposicaoAbortada("catalogo_invalido", f"tag duplicada no catálogo: {tag}")
        ids_vistos.add(bid)
        tags_vistas.add(tag)
        por_id[bid] = b

        if b["tipo"] not in TIPOS_VALIDOS:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: tipo inválido '{b['tipo']}'")
        if b["decision_mode"] not in DECISION_MODES_VALIDOS:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: decision_mode inválido '{b['decision_mode']}'")
        if b["cardinality"] not in CARDINALIDADES_VALIDAS:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: cardinality inválida '{b['cardinality']}'")

        if b["tipo"] == "CONTAINER_DERIVED" and b["decision_mode"] != "derived":
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: CONTAINER_DERIVED exige decision_mode='derived'")
        if b["tipo"] != "CONTAINER_DERIVED" and b["decision_mode"] == "derived":
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: decision_mode='derived' exige tipo CONTAINER_DERIVED")
        if b["tipo"] == "CONTAINER_DERIVED" and not b["children"]:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: CONTAINER_DERIVED sem children")
        if b["tipo"] != "CONTAINER_DERIVED" and b["children"]:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: apenas CONTAINER_DERIVED pode declarar children ({b['children']})")
        if b["tipo"] == "CONTAINER_DERIVED" and not b.get("derived_rule"):
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: CONTAINER_DERIVED sem derived_rule")
        if b["decision_mode"] == "linked" and not b.get("linked_to"):
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: decision_mode='linked' sem linked_to")
        if b["decision_mode"] == "state_linked" and not str(b.get("linked_fact", "")).strip():
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: decision_mode='state_linked' sem linked_fact")
        if b["decision_mode"] != "state_linked" and b.get("linked_fact"):
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: linked_fact só é válido em decision_mode='state_linked'")

        # Etapa 5.2 — requires_fact: gate fático
        # opcional (estado processual, não outro bloco) que condiciona
        # INCLUIR. Puramente estrutural aqui — nenhuma heurística jurídica:
        # só garante que, quando declarado, tem a forma esperada.
        # Infraestrutura geral, sem uso atual no catálogo (LICITUDE_CORTE_
        # SUSPENSAO migrou para state_linked — INV-CORTE-LINKED).
        gate = b.get("requires_fact")
        if gate is not None:
            if b["decision_mode"] not in DECISION_MODES_MANUAIS:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: requires_fact só é válido em blocos decision_mode {DECISION_MODES_MANUAIS}")
            if not isinstance(gate, dict) or not str(gate.get("key", "")).strip():
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: requires_fact malformado (precisa de 'key' não vazia): {gate}")

    for b in blocos:
        bid, parent = b["id"], b["parent"]
        if parent is not None:
            if parent not in por_id:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: parent inexistente '{parent}'")
            if bid not in por_id[parent]["children"]:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: não listado em children de '{parent}'")
        for c in b["children"]:
            if c not in por_id:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: child inexistente '{c}'")
            if por_id[c]["parent"] != bid:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: child '{c}' não referencia '{bid}' como parent")
        if b.get("linked_to") and b["linked_to"] not in por_id:
            raise ComposicaoAbortada("catalogo_invalido", f"{bid}: linked_to inexistente '{b['linked_to']}'")
        for dep in b.get("dependencies", []):
            if "placeholder" not in dep or "quando" not in dep:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: dependency malformada {dep}")
            if dep["placeholder"] not in b.get("placeholders", []):
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: dependency referencia placeholder não declarado: {dep['placeholder']}")
            if dep["quando"] not in ESTADOS_VALIDOS:
                raise ComposicaoAbortada("catalogo_invalido", f"{bid}: dependency.quando inválido '{dep['quando']}'")

    cor = {bid: 0 for bid in por_id}  # 0=branco 1=cinza 2=preto

    def visita(bid):
        cor[bid] = 1
        for c in por_id[bid]["children"]:
            if cor[c] == 1 or (cor[c] == 0 and visita(c)):
                return True
        cor[bid] = 2
        return False

    if any(cor[bid] == 0 and visita(bid) for bid in por_id):
        raise ComposicaoAbortada("catalogo_invalido", "ciclo detectado na hierarquia parent/children")


def _fato_processual_verdadeiro(fatos_processuais: dict, key: str) -> bool:
    """Lê um estado processual (ex.: CORTE_EFETIVO) de forma puramente
    mecânica — nunca interpreta texto, só o booleano já resolvido pela
    Skill `contestacao`/pelo estrategista a partir dos documentos
    (fail-closed: ausente ou mal formado conta como falso, nunca como
    verdadeiro por omissão). Aceita tanto `{"KEY": true}` quanto
    `{"KEY": {"valor": true, ...proveniência...}}`. Usado só pelo gate
    `requires_fact` (infraestrutura geral, sem uso atual no catálogo) —
    para `state_linked` (INV-GRATUIDADE-LINKED/INV-CORTE-LINKED), ver
    `_estado_fato_processual` abaixo, que
    distingue um terceiro estado (`INDETERMINADO`)."""
    valor = (fatos_processuais or {}).get(key)
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, dict):
        return valor.get("valor") is True
    return False


def _estado_fato_processual(fatos_processuais: dict, key: str, bid: str) -> str:
    """Resolve um estado processual para exatamente um destes três:
    'TRUE', 'FALSE', 'INDETERMINADO' — usado pelos blocos 'state_linked'
    (INV-GRATUIDADE-LINKED). Diferença deliberada de
    `_fato_processual_verdadeiro`: aqui a ausência simples da chave conta
    como FALSE (nunca vira ambiguidade — "não transformar simples
    ausência de decisão em ambiguidade"), mas um valor presente e
    reconhecido como indeterminado (`"INDETERMINADO"`) é distinguido de
    falso, e propaga a mesma ambiguidade em vez de ser tratado como
    corte/gratuidade não concedida. Qualquer valor fora do contrato
    aceito (não é bool, não é 'INDETERMINADO', não é um dict com esses
    valores em 'valor') aborta explicitamente — nunca interpretado
    silenciosamente."""
    fatos_processuais = fatos_processuais or {}
    if key not in fatos_processuais:
        return "FALSE"
    bruto = fatos_processuais[key]
    if isinstance(bruto, dict):
        bruto = bruto.get("valor")
    if bruto is True:
        return "TRUE"
    if bruto is False:
        return "FALSE"
    if bruto == "INDETERMINADO":
        return "INDETERMINADO"
    raise ComposicaoAbortada(
        "estado_processual_invalido",
        f"{bid}: estado processual '{key}' com valor não reconhecido "
        f"{bruto!r} (esperado true, false ou 'INDETERMINADO')",
    )


# ============================================================== Fase C/D/E/F — decisões
def validar_e_resolver_decisoes(catalogo: dict, decisoes: dict, fatos_processuais: dict = None) -> dict:
    """Valida as decisões da etapa estratégica contra o catálogo, aborta
    em qualquer INDETERMINADO (mesmo com irmãos já decididos — nenhuma
    inferência jurídica parcial), e resolve os estados CONTAINER_DERIVED/
    'linked' a partir dos filhos/bloco referenciado. Retorna {id: estado}
    completo (folhas + containers + inline vinculado).

    `decisoes` deve conter, para cada bloco decision_mode em
    ('estrategista', 'humano'), {'decisao': 'INCLUIR'|'EXCLUIR'|
    'INDETERMINADO', ...}. Blocos 'derived'/'linked'/'state_linked' não
    devem aparecer em `decisoes` — decisão manual para qualquer um deles é
    rejeitada explicitamente, nunca ignorada em silêncio.

    `fatos_processuais` (opcional) é o estado processual (ex.:
    {"GRATUIDADE_CONCEDIDA": true, "CORTE_EFETIVO": false}), com dois usos
    distintos:
      - blocos que declaram `requires_fact` (infraestrutura geral, sem
        uso atual no catálogo): GATE — INCLUIR só é aceito se o fato for
        verdadeiro; a decisão INCLUIR/EXCLUIR em si continua exclusivamente da etapa
        estratégica quando o fato é verdadeiro.
      - blocos 'state_linked' (INV-GRATUIDADE-LINKED): VÍNCULO
        determinístico — o estado do bloco *é* o estado processual
        (true->INCLUIR, false->EXCLUIR, 'INDETERMINADO'->aborta); não há
        decisão alguma da etapa estratégica para esses blocos."""
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    estados = {}

    for bid, b in por_id.items():
        if b["decision_mode"] not in DECISION_MODES_MANUAIS:
            if bid in decisoes:
                raise ComposicaoAbortada(
                    "decisao_invalida",
                    f"{bid}: decision_mode='{b['decision_mode']}' não aceita decisão manual",
                )
            continue
        if bid not in decisoes:
            raise ComposicaoAbortada("decisao_ausente", f"{bid}: sem decisão da etapa estratégica")
        d = decisoes[bid]
        estado = d.get("decisao") if isinstance(d, dict) else d
        if estado not in ESTADOS_VALIDOS:
            raise ComposicaoAbortada("decisao_invalida", f"{bid}: estado inválido '{estado}' (sem normalização — só INCLUIR/EXCLUIR/INDETERMINADO)")
        if estado == "INDETERMINADO":
            raise ComposicaoAbortada("decisao_indeterminada", f"{bid}: permanece INDETERMINADO")
        gate = b.get("requires_fact")
        if estado == "INCLUIR" and gate and not _fato_processual_verdadeiro(fatos_processuais, gate["key"]):
            raise ComposicaoAbortada(
                "gate_fatico_nao_satisfeito",
                f"{bid}: INCLUIR exige estado processual '{gate['key']}' confirmado "
                f"(ausente ou falso em estado_processual.json) — suporte fático "
                f"insuficiente para a tese, independentemente da análise estratégica.",
            )
        estados[bid] = estado

    # 'state_linked' (INV-GRATUIDADE-LINKED) resolve ANTES dos containers
    # 'derived' — um bloco state_linked pode ser filho de um container
    # (ex.: PRELIMINAR_REVOGACAO_GRATUIDADE é filho de PRELIMINARES), e o
    # loop de containers abaixo exige todos os filhos já resolvidos.
    for bid, b in por_id.items():
        if b["decision_mode"] != "state_linked":
            continue
        estado_fato = _estado_fato_processual(fatos_processuais, b["linked_fact"], bid)
        if estado_fato == "INDETERMINADO":
            raise ComposicaoAbortada(
                "decisao_indeterminada",
                f"{bid}: estado processual '{b['linked_fact']}' está "
                f"INDETERMINADO — documentos contraditórios ou insuficientes "
                f"para determinar o fato; requer interação com o advogado, "
                f"nunca decisão silenciosa.",
            )
        estados[bid] = "INCLUIR" if estado_fato == "TRUE" else "EXCLUIR"

    pendentes = [b for b in por_id.values() if b["decision_mode"] == "derived"]
    mudou = True
    while pendentes and mudou:
        mudou, ainda = False, []
        for b in pendentes:
            filhos = b["children"]
            if not all(c in estados for c in filhos):
                ainda.append(b)
                continue
            regra = b["derived_rule"]
            if regra == "ANY_CHILD_INCLUDED":
                estados[b["id"]] = "INCLUIR" if any(estados[c] == "INCLUIR" for c in filhos) else "EXCLUIR"
            else:
                raise ComposicaoAbortada("catalogo_invalido", f"{b['id']}: derived_rule desconhecida '{regra}'")
            mudou = True
        pendentes = ainda
    if pendentes:
        raise ComposicaoAbortada("catalogo_invalido", f"containers com dependência irresolúvel: {[b['id'] for b in pendentes]}")

    for b in por_id.values():
        if b["decision_mode"] == "linked":
            alvo = b["linked_to"]
            if alvo not in estados:
                raise ComposicaoAbortada("catalogo_invalido", f"{b['id']}: linked_to '{alvo}' sem estado resolvido")
            estados[b["id"]] = estados[alvo]

    faltando = set(por_id) - set(estados)
    if faltando:
        raise ComposicaoAbortada("decisao_ausente", f"blocos sem estado resolvido: {sorted(faltando)}")
    return estados


# ============================================================== Etapa 5.3 — pedidos × blocos
# Achado real (Teste Real 01-B §18): PEDIDOS_FINAIS reintroduzindo tese já
# EXCLUÍDA pelo motor composicional (ex.: pedido de revogação de
# gratuidade mesmo com PRELIMINAR_REVOGACAO_GRATUIDADE = EXCLUIR). Isso
# tem que ser determinístico — não um lembrete na Skill. Cada bloco
# relevante para os pedidos finais declara aqui as palavras-chave que só
# fazem sentido no texto de PEDIDOS_FINAIS quando o bloco correspondente
# está INCLUIR; se EXCLUIR, a presença de qualquer uma delas é erro.
# Backstop lexical (mesma limitação de qualquer backstop deste projeto:
# ausência de palavra-chave não prova coerência, só a presença prova
# incoerência) — o controle substantivo continua sendo da Skill.
PALAVRAS_CHAVE_BLOCO_PEDIDOS = {
    "PRELIMINAR_CDC_INAPLICAVEL": (
        "inaplicabilidade do cdc", "cdc não se aplica", "cdc nao se aplica",
        "afastamento do cdc", "inaplicabilidade do código de defesa",
    ),
    "PRELIMINAR_REVOGACAO_GRATUIDADE": (
        "revogação da gratuidade", "revogacao da gratuidade",
        "revogação da assistência judiciária", "revogacao da assistencia judiciaria",
        "revogação da justiça gratuita", "revogacao da justica gratuita",
    ),
    "RECONVENCAO": ("reconvenção", "reconvencao"),
    # INV-CORTE-LINKED: bloco excluído (sem corte efetivo comprovado)
    # não pode ter sua tese reintroduzida em PEDIDOS_FINAIS por outro
    # caminho.
    "LICITUDE_CORTE_SUSPENSAO": (
        "licitude do corte", "licitude da suspensão", "licitude da suspensao",
        "corte foi lícito", "corte foi licito", "regularidade do corte",
        "regularidade da suspensão", "regularidade da suspensao",
    ),
}


def validar_pedidos_composicionais(pedidos_texto: str, estados: dict) -> list:
    """Retorna a lista de erros (vazia se PEDIDOS_FINAIS não menciona
    nenhuma tese de bloco EXCLUÍDO). `estados` é o dict {id: estado}
    já resolvido por `validar_e_resolver_decisoes`."""
    v = "".join(
        c for c in unicodedata.normalize("NFD", str(pedidos_texto).lower())
        if unicodedata.category(c) != "Mn"
    )
    erros = []
    for bid, palavras in PALAVRAS_CHAVE_BLOCO_PEDIDOS.items():
        if estados.get(bid) != "EXCLUIR":
            continue
        achadas = [p for p in palavras if
                   "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn") in v]
        if achadas:
            erros.append(
                f"PEDIDOS_FINAIS menciona {achadas} mas {bid} = EXCLUIR — "
                f"pedido não pode reintroduzir tese excluída pelo motor "
                f"composicional (Etapa 5.3 §18)")
    return erros


# ============================================================== Fase H — template x catálogo
def _sdts_por_tag(root):
    mapa = {}
    for sdt in root.findall(".//w:sdt", NS):
        tag_el = sdt.find("w:sdtPr/w:tag", NS)
        if tag_el is None:
            raise ComposicaoAbortada("sdt_sem_tag", "SDT sem w:tag encontrado no template")
        tag_val = tag_el.get(_qn("val"))
        content = sdt.find("w:sdtContent", NS)
        if content is None:
            raise ComposicaoAbortada("sdt_sem_content", f"{tag_val}: SDT sem w:sdtContent")
        mapa.setdefault(tag_val, []).append(sdt)
    return mapa


def validar_sdts_contra_catalogo(root, catalogo: dict) -> dict:
    """Cruza os SDTs reais do template contra o catálogo: toda tag no
    documento precisa existir no catálogo com cardinalidade compatível
    (sem duplicata não autorizada para cardinality ONE); todo bloco do
    catálogo precisa existir no documento. Retorna o mapa tag->elementos."""
    mapa = _sdts_por_tag(root)
    tags_catalogo = {b["tag"]: b for b in catalogo["blocks"]}

    for tag_val, elementos in mapa.items():
        if tag_val not in tags_catalogo:
            raise ComposicaoAbortada("tag_desconhecida", f"tag no template sem entrada no catálogo: {tag_val}")
        esperado = _CARDINALIDADE_ESPERADA[tags_catalogo[tag_val]["cardinality"]]
        if len(elementos) != esperado:
            raise ComposicaoAbortada(
                "cardinalidade_invalida",
                f"{tag_val}: {len(elementos)} ocorrência(s) no template, catálogo espera {esperado}",
            )

    for b in catalogo["blocks"]:
        if b["tag"] not in mapa:
            raise ComposicaoAbortada("tag_ausente", f"bloco do catálogo sem SDT correspondente no template: {b['tag']}")

    return mapa


# ============================================================== Fase I — composição estrutural
def compor_blocos(root, catalogo: dict, estados: dict) -> dict:
    """Executa deterministicamente as decisões já resolvidas sobre a
    árvore lxml (mutação em memória). Profundidade primeiro, pós-ordem —
    resolve o conteúdo de cada SDT antes do próprio nó. INCLUIR = unwrap
    (os filhos reais de w:sdtContent tomam o lugar do <w:sdt>, elementos
    preservados por referência — nunca recriados). EXCLUIR = remove o
    <w:sdt> inteiro. Nunca assume índice de parágrafo == índice de filho
    do corpo — sempre caminha list(pai) diretamente (o template real
    intercala <w:bookmarkEnd> soltos entre parágrafos).

    Recursão totalmente genérica — desce por QUALQUER elemento, não só por
    w:sdtContent — porque um SDT do catálogo pode estar aninhado dentro de
    parágrafo/run/drawing/shape/textbox (achado real da Etapa 5.2:
    INLINE:COM_RECONVENCAO vive dentro de wps:txbx/w:txbxContent, a caixa
    de texto do título — não filho direto de w:body nem de outro
    w:sdtContent; a versão anterior, que só recursava sdtContent, nunca
    alcançava esse SDT e o deixava intocado, qualquer que fosse a decisão).
    A cirurgia (remove/insert) continua sempre relativa ao pai imediato do
    próprio <w:sdt>, então descer por qualquer nível é seguro."""
    tags_catalogo = {b["tag"]: b for b in catalogo["blocks"]}
    resultado = {"incluidos": [], "excluidos": []}

    def processar(pai):
        for filho in list(pai):
            if filho.tag != _qn("sdt"):
                processar(filho)  # desce por qualquer elemento não-sdt em busca de SDTs aninhados
                continue
            tag_el = filho.find("w:sdtPr/w:tag", NS)
            if tag_el is None:
                raise ComposicaoAbortada("sdt_sem_tag", "SDT sem w:tag durante composição")
            tag_val = tag_el.get(_qn("val"))
            content = filho.find("w:sdtContent", NS)
            if content is None:
                raise ComposicaoAbortada("sdt_sem_content", f"{tag_val}: sem w:sdtContent durante composição")

            processar(content)  # filhos antes do próprio nó

            bloco = tags_catalogo.get(tag_val)
            if bloco is None:
                raise ComposicaoAbortada("tag_desconhecida", f"tag sem entrada no catálogo durante composição: {tag_val}")
            estado = estados.get(bloco["id"])
            if estado not in ("INCLUIR", "EXCLUIR"):
                raise ComposicaoAbortada("estado_invalido", f"{bloco['id']}: estado '{estado}' inválido para composição")

            idx = list(pai).index(filho)
            pai.remove(filho)
            if estado == "INCLUIR":
                for i, neto in enumerate(list(content)):
                    pai.insert(idx + i, neto)
                resultado["incluidos"].append(bloco["id"])
            else:
                resultado["excluidos"].append(bloco["id"])

    body = root.find("w:body", NS)
    if body is None:
        raise ComposicaoAbortada("template_invalido", "documento sem <w:body>")
    processar(body)
    return resultado


def compor_xml(document_xml: str, catalogo: dict, estados: dict):
    """Wrapper string->string: parse -> valida SDTs contra catálogo ->
    compõe -> reserializa. Usado tanto na geração real quanto pelo
    Template Lock composicional (mesma função em ambos os lados,
    garantindo que 'esperado' e 'gerado' venham do mesmo caminho de
    código)."""
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)
    validar_sdts_contra_catalogo(root, catalogo)
    resultado = compor_blocos(root, catalogo, estados)
    novo_xml = LET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True).decode("utf-8")
    return novo_xml, resultado


# ============================================================== Fase G-M — orquestração
def gerar_peca_com_blocos(template_path, schema_path, catalogo_path, dados: dict,
                           decisoes_blocos: dict, output_path, fatos_processuais: dict = None) -> dict:
    """Pipeline completo com composição de blocos: valida catálogo ->
    valida/resolve decisões -> abre template -> valida SDTs contra
    catálogo -> compõe (unwrap/remove) -> substitui placeholders (já
    aplica FF0000, docx_template_engine.py) -> Template Lock composicional
    -> reempacota. Reaproveita toda a mecânica de placeholder/Template
    Lock/pack já existente em docx_template_engine.py — não duplica nada
    disso, só insere a composição de blocos ANTES da substituição.

    Nunca produz DOCX parcial: qualquer ComposicaoAbortada interrompe
    antes de qualquer escrita em output_path."""
    template_path = Path(template_path)
    if not template_path.exists():
        return {"status": "FALHOU", "etapa": "template", "erros": [f"template não encontrado: {template_path}"]}

    try:
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
        estados = validar_e_resolver_decisoes(catalogo, decisoes_blocos, fatos_processuais)
    except ComposicaoAbortada as e:
        return {"status": "FALHOU", "etapa": e.stage, "erros": [e.motivo]}

    schema = carregar_schema(schema_path)
    unpack_mod, pack_mod = _importar_toolkit()

    def transformar(template_xml):
        composto_xml, _ = compor_xml(template_xml, catalogo, estados)
        return substituir_placeholders(composto_xml, dados)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copia_template = tmp / "template_copy.docx"
        shutil.copy2(template_path, copia_template)  # INV-012: nunca ler/escrever o mestre diretamente

        unpacked_template = tmp / "template_unpacked"
        _, msg = unpack_mod.unpack(str(copia_template), str(unpacked_template))
        if not unpacked_template.exists():
            return {"status": "FALHOU", "etapa": "unpack", "erros": [msg]}

        template_xml = (unpacked_template / "word" / "document.xml").read_text(encoding="utf-8")

        try:
            composto_xml, resultado_composicao = compor_xml(template_xml, catalogo, estados)
        except ComposicaoAbortada as e:
            return {"status": "FALHOU", "etapa": e.stage, "erros": [e.motivo]}

        validacao = validar_placeholders(composto_xml, dados, schema)
        if not validacao["ok"]:
            return {"status": "FALHOU", "etapa": "validacao_placeholders", "erros": validacao["erros"]}

        gerado_xml, substituidos = substituir_placeholders(composto_xml, dados)
        gerado_dir = tmp / "gerado"
        shutil.copytree(unpacked_template, gerado_dir)
        (gerado_dir / "word" / "document.xml").write_text(gerado_xml, encoding="utf-8")

        lock = verificar_template_lock(unpacked_template, gerado_dir, dados, transformar_xml=transformar)
        if not lock["ok"]:
            return {"status": "FALHOU", "etapa": "template_lock", "erros": lock["divergencias"]}

        output_path = Path(output_path)
        _, msg_pack = pack_mod.pack(
            str(gerado_dir), str(output_path),
            original_file=str(copia_template), validate=True,
        )
        if not output_path.exists():
            return {"status": "FALHOU", "etapa": "pack", "erros": [msg_pack]}

        containers_derivados = [b["id"] for b in catalogo["blocks"] if b["decision_mode"] == "derived"]
        return {
            "status": "OK",
            "template": str(template_path),
            "template_version": schema.get("version"),
            "documento_final": str(output_path),
            "placeholders_substituidos": sorted(substituidos),
            "blocos_incluidos": sorted(resultado_composicao["incluidos"]),
            "blocos_excluidos": sorted(resultado_composicao["excluidos"]),
            "containers_derivados": {cid: estados[cid] for cid in containers_derivados},
            "blocos_indeterminados": [],
            "template_lock": "OK",
            "mensagem_pack": msg_pack,
        }
