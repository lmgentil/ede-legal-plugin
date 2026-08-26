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
    `fatos_processuais[key]` estiver resolvido para TRUE (ver
    `_estado_fato_processual` abaixo); quando o fato é FALSE/ausente e
    NENHUMA decisão manual está registrada, o gate resolve sozinho para
    EXCLUIR (sem perguntar — nada a decidir sobre uma tese sem suporte
    fático); quando o fato é TRUE e nenhuma decisão está registrada, o
    fail-closed de sempre (decisao_ausente) aborta, sinalizando que uma
    decisão humana ainda precisa ser tomada; a decisão INCLUIR vs. EXCLUIR
    quando o fato é TRUE continua exclusivamente da etapa
    estratégica/humana — o gate nunca decide por conta própria, só
    restringe. Usado por LICITUDE_CORTE_SUSPENSAO (decision_mode
    'humano') — INV-CORTE-GATE-HUMANO, Etapa 5.5, 3ª correção
    arquitetural: as duas modelagens anteriores (gate puro sem checagem
    adicional; depois `state_linked` puro) se mostraram incorretas em
    testes reais — ver `INV-CORTE-GATE-HUMANO` em
    skills/contestacao/SKILL.md §4A e docs/specs/SPEC-0001.md.
  - decision_mode "state_linked" + `linked_fact` (catálogo, correção
    pontual pós-Etapa 5.2): VÍNCULO determinístico ESTADO PROCESSUAL ->
    BLOCO — o estado do bloco *é* `fatos_processuais[linked_fact]`
    (true->INCLUIR, false->EXCLUIR, 'INDETERMINADO'->aborta); nenhuma
    decisão da etapa estratégica é aceita. Usado por PRELIMINAR_REVOGACAO_
    GRATUIDADE (INV-GRATUIDADE-LINKED) — único bloco do catálogo atual
    neste modo; LICITUDE_CORTE_SUSPENSAO usou este modo numa correção
    intermediária (INV-CORTE-LINKED, já superada — ver acima), mas um
    teste real seguinte mostrou que corte efetivo comprovado não deve
    incluir automaticamente sem decisão do advogado, daí a migração para
    `requires_fact` + `humano`. Diferente de "linked"
    (BLOCO -> BLOCO, ex.: INLINE_COM_RECONVENCAO -> RECONVENCAO,
    preservado intocado) e diferente de `requires_fact` (que é um gate,
    não um vínculo — ainda deixa a decisão para o estrategista/humano).
    Estado processual resolvido pela Skill `contestacao` a partir dos
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
from docx_numeracao_engine import (  # noqa: E402
    NumeracaoAbortada,
    renumerar_titulos,
    validar_numeracao_final,
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
# estratégica/humana — usado por LICITUDE_CORTE_SUSPENSAO,
# INV-CORTE-GATE-HUMANO, Etapa 5.5): `requires_fact` é um GATE que só
# restringe INCLUIR, deixando a decisão INCLUIR/EXCLUIR para a etapa
# estratégica/humana quando o fato é verdadeiro; `state_linked` não deixa
# decisão alguma para o estrategista — o estado do bloco *é* o estado
# processual, sempre.
DECISION_MODES_VALIDOS = ("estrategista", "humano", "derived", "linked", "state_linked")
# Blocos cujo decision_mode aceita decisão registrada em decisoes_blocos.json
# (folhas "reais" — não containers/inline resolvidos automaticamente).
DECISION_MODES_MANUAIS = ("estrategista", "humano")
CARDINALIDADES_VALIDAS = ("ONE", "MC_PAIR")
_CARDINALIDADE_ESPERADA = {"ONE": 1, "MC_PAIR": 2}

# ---------------------------------------------------------------- Etapa 5.8-B
# INV-ZONA-COMPLEMENTACAO (SPEC-0001 §58, ADR-0010). Zona de Complementação
# é uma terceira categoria, distinta das duas já existentes:
#   - BLOCO  -> tem decision_mode, entra em derived_rule, é decidido pela
#               etapa estratégica ou pelo advogado, compõe a estrutura;
#   - PLACEHOLDER -> campo de finalidade semântica fixa, listado em
#               schema.json editable_placeholders (13, e continuam 13);
#   - ZONA   -> pertence a UM bloco-pai, é normalmente VAZIA, nunca é
#               decidida (nem pelo estrategista nem pelo advogado), nunca
#               provoca inclusão de nada, e só existe quando há suporte
#               fático documentado E o Redator produziu conteúdo.
# A tag do SDT de zona usa prefixo próprio para que a composição de blocos
# a IGNORE na primeira passada (compor_blocos) e a resolva depois
# (compor_zonas) — ver docstring de compor_zonas.
ZONA_TAG_PREFIXO = "ZONA:"
ZONA_CAMPOS_OBRIGATORIOS = (
    "id", "tag", "bloco_pai", "finalidade", "tipo_conteudo", "requires_facts",
    "max_paragrafos", "max_caracteres_paragrafo", "max_caracteres_total",
    "comportamento_vazia",
)
# Piloto (Etapa 5.8-B §4): só 'dado_documental'. 'complemento_factual' NÃO
# está liberado — ampliar exige autorização expressa, como qualquer zona nova.
TIPOS_CONTEUDO_ZONA_VALIDOS = ("dado_documental",)
COMPORTAMENTOS_VAZIA_VALIDOS = ("remover_sdt",)


def token_da_zona(zona: dict) -> str:
    """Token que a zona ocupa no template. Deliberadamente derivado do `id`
    (nunca um campo próprio no catálogo, que poderia divergir do id em
    silêncio): id `ZONA_METODOLOGIA_APURACAO` -> `{{ZONA_METODOLOGIA_APURACAO}}`."""
    return "{{" + zona["id"] + "}}"


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
        # Usado por LICITUDE_CORTE_SUSPENSAO (decision_mode 'humano') —
        # INV-CORTE-GATE-HUMANO, Etapa 5.5.
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

    validar_catalogo_zonas(catalogo, ids_blocos=set(por_id), tags_blocos=tags_vistas)


def validar_catalogo_zonas(catalogo: dict, ids_blocos: set, tags_blocos: set) -> None:
    """Etapa 5.8-B — validação estrutural pura da lista `zones` (não olha
    template nem conteúdo). Chave ausente ou lista vazia é legítimo: um
    template sem zona alguma continua válido, e essa é a configuração
    esperada de qualquer instalação anterior à Etapa 5.8-B.

    Nunca valida decision_mode/children/derived_rule — zona não é bloco e
    não pode ganhar autonomia composicional (§11 da Etapa 5.8-A)."""
    zonas = catalogo.get("zones", [])
    if not isinstance(zonas, list):
        raise ComposicaoAbortada("catalogo_invalido", "'zones' deve ser uma lista")

    ids_vistos, tags_vistas = set(), set()
    for z in zonas:
        if not isinstance(z, dict):
            raise ComposicaoAbortada("catalogo_invalido", f"zona não é um objeto: {z!r}")
        for campo in ZONA_CAMPOS_OBRIGATORIOS:
            if campo not in z:
                raise ComposicaoAbortada("catalogo_invalido",
                                          f"zona sem campo obrigatório '{campo}': {z.get('id', z)}")
        zid, tag = z["id"], z["tag"]
        if zid in ids_vistos:
            raise ComposicaoAbortada("catalogo_invalido", f"id de zona duplicado no catálogo: {zid}")
        if zid in ids_blocos:
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: id de zona colide com id de bloco — zona não é bloco")
        if tag in tags_vistas or tag in tags_blocos:
            raise ComposicaoAbortada("catalogo_invalido", f"tag de zona duplicada no catálogo: {tag}")
        ids_vistos.add(zid)
        tags_vistas.add(tag)

        if not tag.startswith(ZONA_TAG_PREFIXO):
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: tag de zona deve começar com '{ZONA_TAG_PREFIXO}', recebeu {tag!r}")
        if z["bloco_pai"] not in ids_blocos:
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: bloco_pai inexistente '{z['bloco_pai']}'")
        if z["tipo_conteudo"] not in TIPOS_CONTEUDO_ZONA_VALIDOS:
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: tipo_conteudo inválido '{z['tipo_conteudo']}' "
                                      f"(válidos: {TIPOS_CONTEUDO_ZONA_VALIDOS})")
        if z["comportamento_vazia"] not in COMPORTAMENTOS_VAZIA_VALIDOS:
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: comportamento_vazia inválido '{z['comportamento_vazia']}'")
        # Gate fático obrigatório e não vazio: INV-BLOCO-SUPORTE-FATICO
        # aplicado à zona — nenhuma zona pode existir só porque está
        # catalogada (§3/§7 da Etapa 5.8-A).
        req = z["requires_facts"]
        if not isinstance(req, list) or not req or not all(
                isinstance(k, str) and k.strip() for k in req):
            raise ComposicaoAbortada("catalogo_invalido",
                                      f"{zid}: requires_facts deve ser lista NÃO VAZIA de chaves de "
                                      f"estado processual — zona sem suporte fático obrigatório não é "
                                      f"admitida (INV-ZONA-COMPLEMENTACAO)")
        for campo in ("max_paragrafos", "max_caracteres_paragrafo", "max_caracteres_total"):
            valor = z[campo]
            if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
                raise ComposicaoAbortada("catalogo_invalido",
                                          f"{zid}: {campo} deve ser inteiro positivo, recebeu {valor!r}")
        # zona não pode declarar nada que a faria parecer bloco
        for proibido in ("decision_mode", "children", "derived_rule", "linked_to",
                         "linked_fact", "parent", "cardinality"):
            if proibido in z:
                raise ComposicaoAbortada("catalogo_invalido",
                                          f"{zid}: zona não pode declarar '{proibido}' — zona não é "
                                          f"bloco (INV-ZONA-COMPLEMENTACAO)")


def _estado_fato_processual(fatos_processuais: dict, key: str, bid: str) -> str:
    """Resolve um estado processual (ex.: CORTE_EFETIVO, GRATUIDADE_
    CONCEDIDA) para exatamente um destes três: 'TRUE', 'FALSE',
    'INDETERMINADO' — nunca interpreta texto, só o valor já resolvido
    pela Skill `contestacao`/estrategista a partir dos documentos. Aceita
    tanto `{"KEY": true}` quanto `{"KEY": {"valor": true,
    ...proveniência...}}`. Usado pelos blocos 'state_linked'
    (INV-GRATUIDADE-LINKED) e, desde a Etapa 5.5, também pela resolução
    de gate fático + decisão humana de blocos com `requires_fact`
    (INV-CORTE-GATE-HUMANO) quando não há decisão registrada. A ausência
    simples da chave conta como FALSE (nunca vira ambiguidade — "não
    transformar simples ausência de decisão em ambiguidade"), mas um
    valor presente e reconhecido como indeterminado (`"INDETERMINADO"`)
    é distinguido de falso, e propaga a mesma ambiguidade em vez de ser
    tratado como corte/gratuidade não concedida. Qualquer valor fora do
    contrato aceito (não é bool, não é 'INDETERMINADO', não é um dict com
    esses valores em 'valor') aborta explicitamente — nunca interpretado
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
      - blocos que declaram `requires_fact` (ex.: LICITUDE_CORTE_
        SUSPENSAO — INV-CORTE-GATE-HUMANO, Etapa 5.5): GATE FÁTICO +
        DECISÃO HUMANA. Fato falso/ausente -> EXCLUIR automático, SEM
        exigir decisão em `decisoes` (nada a perguntar sobre tese sem
        suporte). Fato INDETERMINADO -> aborta (`decisao_indeterminada`),
        com ou sem decisão presente. Fato verdadeiro SEM decisão em
        `decisoes` -> aborta (`decisao_ausente`) — a Skill orquestradora
        interpreta isso como "pergunte ao advogado". Fato verdadeiro COM
        decisão -> INCLUIR/EXCLUIR conforme a decisão registrada.
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
        gate = b.get("requires_fact")
        if bid not in decisoes:
            # Etapa 5.5 (INV-CORTE-GATE-HUMANO): bloco com gate fático +
            # decisão manual — sem suporte fático algum, não há nada a
            # perguntar (nunca desperdiçar interação humana com tese sem
            # suporte): resolve automaticamente para EXCLUIR, sem exigir
            # entrada em decisoes_blocos.json. Fato INDETERMINADO aborta
            # (mesmo sem decisão pendente, a incerteza factual em si já é
            # fail-closed). Só quando o fato é verdadeiro E não há decisão
            # é que cai no abort padrão abaixo — que a Skill orquestradora
            # interpreta como "pergunte ao advogado".
            if gate:
                estado_fato = _estado_fato_processual(fatos_processuais, gate["key"], bid)
                if estado_fato == "INDETERMINADO":
                    raise ComposicaoAbortada(
                        "decisao_indeterminada",
                        f"{bid}: estado processual '{gate['key']}' está "
                        f"INDETERMINADO — documentos contraditórios ou "
                        f"insuficientes para determinar o fato; requer "
                        f"interação com o advogado antes de decidir o bloco.")
                if estado_fato == "FALSE":
                    estados[bid] = "EXCLUIR"
                    continue
                # estado_fato == "TRUE": gate satisfeito, mas nenhuma
                # decisão humana registrada — cai no abort abaixo.
            raise ComposicaoAbortada("decisao_ausente", f"{bid}: sem decisão da etapa estratégica")
        d = decisoes[bid]
        estado = d.get("decisao") if isinstance(d, dict) else d
        if estado not in ESTADOS_VALIDOS:
            raise ComposicaoAbortada("decisao_invalida", f"{bid}: estado inválido '{estado}' (sem normalização — só INCLUIR/EXCLUIR/INDETERMINADO)")
        if estado == "INDETERMINADO":
            raise ComposicaoAbortada("decisao_indeterminada", f"{bid}: permanece INDETERMINADO")
        if estado == "INCLUIR" and gate:
            estado_fato = _estado_fato_processual(fatos_processuais, gate["key"], bid)
            if estado_fato == "INDETERMINADO":
                raise ComposicaoAbortada(
                    "decisao_indeterminada",
                    f"{bid}: estado processual '{gate['key']}' está "
                    f"INDETERMINADO — documentos contraditórios ou "
                    f"insuficientes para determinar o fato; requer "
                    f"interação com o advogado antes de decidir o bloco.")
            if estado_fato != "TRUE":
                raise ComposicaoAbortada(
                    "gate_fatico_nao_satisfeito",
                    f"{bid}: INCLUIR exige estado processual '{gate['key']}' confirmado "
                    f"(ausente ou falso em estado_processual.json) — suporte fático "
                    f"insuficiente para a tese, independentemente da decisão registrada.",
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
    catálogo precisa existir no documento. Retorna o mapa tag->elementos.

    Etapa 5.8-B: tags com prefixo ZONA: são validadas à parte, por
    `_validar_zonas_contra_template` (contrato próprio — bloco-pai real,
    token único e isolado), nunca pela mecânica de bloco."""
    mapa = _sdts_por_tag(root)
    tags_catalogo = {b["tag"]: b for b in catalogo["blocks"]}

    for tag_val, elementos in mapa.items():
        if tag_val.startswith(ZONA_TAG_PREFIXO):
            continue  # validado em _validar_zonas_contra_template, abaixo
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

    _validar_zonas_contra_template(root, catalogo, mapa, tags_catalogo)
    return mapa


def _texto_do(elemento) -> str:
    return "".join(t.text or "" for t in elemento.iter(_qn("t")))


def _validar_zonas_contra_template(root, catalogo: dict, mapa: dict, tags_catalogo: dict) -> None:
    """Etapa 5.8-B §14 — checagem BIDIRECIONAL zona × template, fail-closed
    em todos os casos:

      - SDT ZONA:* no template sem entrada em `zones` -> zona_nao_catalogada;
      - zona em `zones` sem SDT no template -> MODELO_INSTITUCIONAL_
        DESATUALIZADO (§15: erro operacional que diz o que o advogado precisa
        fazer, não um `tag_ausente` cru — o plugin NUNCA busca, baixa ou
        edita o modelo automaticamente);
      - mais de um SDT com a mesma tag de zona -> zona_cardinalidade_invalida;
      - bloco_pai declarado no catálogo diferente do SDT ancestral REAL na
        árvore -> zona_bloco_pai_divergente (o catálogo declara, a árvore
        manda);
      - token ausente dentro do SDT -> zona_token_ausente;
      - token em mais de um lugar do documento -> zona_token_duplicado;
      - token acompanhado de outro texto no mesmo parágrafo ->
        zona_token_nao_isolado (o parágrafo hospedeiro precisa ser só do
        token: é o w:pPr dele que os parágrafos gerados clonam, e texto fixo
        na mesma <w:p> seria arrastado pela expansão multilinha).
    """
    zonas = catalogo.get("zones", [])
    tags_zonas = {z["tag"] for z in zonas}

    for tag_val in mapa:
        if tag_val.startswith(ZONA_TAG_PREFIXO) and tag_val not in tags_zonas:
            raise ComposicaoAbortada(
                "zona_nao_catalogada",
                f"SDT de zona no template sem entrada em 'zones' do catálogo: {tag_val} — "
                f"nenhuma escrita gerativa é autorizada fora de placeholder ou zona "
                f"expressamente catalogada (INV-ZONA-COMPLEMENTACAO)")

    texto_documento = _texto_do(root)
    for z in zonas:
        elementos = mapa.get(z["tag"], [])
        if not elementos:
            raise ComposicaoAbortada(
                "modelo_institucional_desatualizado",
                f"MODELO_INSTITUCIONAL_DESATUALIZADO: o catálogo declara a zona de "
                f"complementação {z['id']} (tag {z['tag']}), mas o "
                f"modelo-oficial.docx em uso não a contém. Este modelo é anterior à "
                f"arquitetura de Zonas de Complementação e precisa ser substituído pela "
                f"versão compatível, fornecida separadamente (o plugin nunca baixa, "
                f"reconstrói nem edita o modelo automaticamente). Nenhuma peça é gerada "
                f"até que o modelo seja atualizado.")
        if len(elementos) != 1:
            raise ComposicaoAbortada(
                "zona_cardinalidade_invalida",
                f"{z['id']}: {len(elementos)} SDT(s) com a tag {z['tag']} no template, esperado exatamente 1")

        sdt = elementos[0]
        ancestral = None
        for a in sdt.iterancestors(_qn("sdt")):
            tag_el = a.find("w:sdtPr/w:tag", NS)
            tag_ancestral = tag_el.get(_qn("val")) if tag_el is not None else None
            if tag_ancestral in tags_catalogo:
                ancestral = tags_catalogo[tag_ancestral]["id"]
                break
        if ancestral != z["bloco_pai"]:
            raise ComposicaoAbortada(
                "zona_bloco_pai_divergente",
                f"{z['id']}: catálogo declara bloco_pai '{z['bloco_pai']}', mas o SDT "
                f"ancestral real no template é {ancestral!r}")

        token = token_da_zona(z)
        ocorrencias_documento = texto_documento.count(token)
        if ocorrencias_documento == 0:
            raise ComposicaoAbortada(
                "zona_token_ausente",
                f"{z['id']}: SDT presente no template, mas o token {token} não foi encontrado")
        if ocorrencias_documento > 1:
            raise ComposicaoAbortada(
                "zona_token_duplicado",
                f"{z['id']}: token {token} aparece {ocorrencias_documento} vezes no template, esperado 1")

        paragrafos_com_token = [p for p in sdt.iter(_qn("p")) if token in _texto_do(p)]
        if not paragrafos_com_token:
            raise ComposicaoAbortada(
                "zona_token_ausente",
                f"{z['id']}: o token {token} existe no documento, mas fora do SDT {z['tag']}")
        if _texto_do(paragrafos_com_token[0]).strip() != token:
            raise ComposicaoAbortada(
                "zona_token_nao_isolado",
                f"{z['id']}: o token {token} deve estar sozinho em seu parágrafo; "
                f"parágrafo hospedeiro contém {_texto_do(paragrafos_com_token[0])!r}")


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

    def resolver(tag_val):
        # Etapa 5.8-B: SDT de zona não pertence a esta passada — permanece
        # intocado aqui e é resolvido por compor_zonas(), DEPOIS. Quando o
        # bloco-pai é EXCLUIR, o SDT da zona desaparece junto com ele, sem
        # nenhum tratamento especial (é descendente do w:sdt removido) —
        # é assim que "bloco_pai EXCLUIR => zona EXCLUIR" (§6) se cumpre
        # estruturalmente, não por regra duplicada.
        if tag_val.startswith(ZONA_TAG_PREFIXO):
            return None, None
        bloco = tags_catalogo.get(tag_val)
        if bloco is None:
            raise ComposicaoAbortada("tag_desconhecida", f"tag sem entrada no catálogo durante composição: {tag_val}")
        estado = estados.get(bloco["id"])
        if estado not in ("INCLUIR", "EXCLUIR"):
            raise ComposicaoAbortada("estado_invalido", f"{bloco['id']}: estado '{estado}' inválido para composição")
        return estado, bloco["id"]

    incluidos, excluidos = _compor_sdts_do_corpo(root, resolver)
    return {"incluidos": incluidos, "excluidos": excluidos}


def _compor_sdts_do_corpo(root, resolver) -> tuple:
    """Percurso genérico de composição, compartilhado por compor_blocos e
    compor_zonas (Etapa 5.8-B — mesma cirurgia, critérios de decisão
    diferentes; duplicar este percurso seria duplicar a parte mais
    delicada do motor).

    `resolver(tag_val) -> (estado, rotulo)`, onde estado é 'INCLUIR',
    'EXCLUIR', ou None para "este SDT não pertence a esta passada"
    (permanece intocado, mas seu conteúdo continua sendo percorrido)."""
    body = root.find("w:body", NS)
    if body is None:
        raise ComposicaoAbortada("template_invalido", "documento sem <w:body>")

    incluidos, excluidos = [], []

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

            estado, rotulo = resolver(tag_val)
            if estado is None:
                continue

            idx = list(pai).index(filho)
            pai.remove(filho)
            if estado == "INCLUIR":
                for i, neto in enumerate(list(content)):
                    pai.insert(idx + i, neto)
                incluidos.append(rotulo)
            else:
                excluidos.append(rotulo)

    processar(body)
    return incluidos, excluidos


# ============================================================== Etapa 5.8-B — zonas de complementação
def resolver_estados_zonas(catalogo: dict, estados_blocos: dict, conteudo_zonas: dict = None,
                            fatos_processuais: dict = None) -> dict:
    """Regra de ativação de INV-ZONA-COMPLEMENTACAO, em cascata (§7 da
    Etapa 5.8-B). A zona é NORMALMENTE VAZIA — 'INCLUIR' é a exceção, não
    o padrão. Retorna {zona_id: 'INCLUIR'|'EXCLUIR'}.

      1. bloco-pai EXCLUIR                      -> EXCLUIR
      2. algum requires_facts 'INDETERMINADO'   -> aborta (zona_indeterminada)
      3. algum requires_facts falso/ausente     -> EXCLUIR, SEM perguntar
      4. fatos presentes, conteúdo não vazio    -> INCLUIR
      5. fatos presentes, conteúdo vazio        -> EXCLUIR

    A ordem 2 antes de 3 é deliberada: ambiguidade documental nunca pode
    ser silenciosamente resolvida como "sem suporte fático" (mesmo
    princípio de INV-CORTE-GATE-HUMANO, onde 'INDETERMINADO' aborta com ou
    sem decisão registrada).

    Nenhuma pergunta ao advogado em nenhum ramo: zona não tem decisão
    humana (§6/§21 — zona não é bloco).

    Conteúdo fornecido para zona que a cascata resolve como EXCLUIR por
    falta de bloco-pai ou de suporte fático é INCOERÊNCIA de pipeline, não
    sobra inofensiva: aborta (zona_incoerente) em vez de descartar em
    silêncio (CLAUDE.md §17)."""
    conteudo_zonas = conteudo_zonas or {}
    estados = {}

    for z in catalogo.get("zones", []):
        zid = z["id"]
        conteudo = str(conteudo_zonas.get(zid) or "").strip()

        estado_pai = estados_blocos.get(z["bloco_pai"])
        if estado_pai is None:
            raise ComposicaoAbortada(
                "zona_bloco_pai_desconhecido",
                f"{zid}: bloco_pai '{z['bloco_pai']}' sem estado resolvido")

        if estado_pai == "EXCLUIR":
            if conteudo:
                raise ComposicaoAbortada(
                    "zona_incoerente",
                    f"{zid}: conteúdo fornecido para zona cujo bloco-pai "
                    f"'{z['bloco_pai']}' foi EXCLUÍDO — a zona não existe na peça; "
                    f"conteúdo produzido para ela indica decisão incoerente entre a "
                    f"etapa estratégica e a redação")
            estados[zid] = "EXCLUIR"
            continue

        indeterminados = [k for k in z["requires_facts"]
                          if _estado_fato_processual(fatos_processuais, k, zid) == "INDETERMINADO"]
        if indeterminados:
            raise ComposicaoAbortada(
                "zona_indeterminada",
                f"{zid}: estado(s) processual(is) {indeterminados} com valor "
                f"'INDETERMINADO' — suporte fático da zona é ambíguo nos documentos; "
                f"resolver com o advogado antes de gerar (nunca presumir)")

        ausentes = [k for k in z["requires_facts"]
                    if _estado_fato_processual(fatos_processuais, k, zid) != "TRUE"]
        if ausentes:
            if conteudo:
                raise ComposicaoAbortada(
                    "zona_incoerente",
                    f"{zid}: conteúdo fornecido sem o suporte fático exigido {ausentes} "
                    f"(ausente ou falso em estado_processual.json) — INV-BLOCO-SUPORTE-FATICO "
                    f"aplicado à zona; nenhuma complementação sem proveniência")
            estados[zid] = "EXCLUIR"
            continue

        estados[zid] = "INCLUIR" if conteudo else "EXCLUIR"

    return estados


def compor_zonas(root, catalogo: dict, estados_zonas: dict) -> dict:
    """Executa as decisões já resolvidas sobre os SDTs de zona da árvore JÁ
    COMPOSTA (blocos EXCLUIR removidos). INCLUIR = unwrap (o parágrafo do
    token toma o lugar do w:sdt, para a substituição normal de placeholder
    colocar o conteúdo ali, em FF0000, com o w:pPr do próprio parágrafo
    hospedeiro). EXCLUIR = remove o w:sdt inteiro — o parágrafo hospedeiro
    some junto, sem deixar linha em branco nem token residual.

    Zona cujo bloco-pai foi EXCLUÍDO já não está na árvore (foi removida
    junto com o bloco); é por isso que este passo roda DEPOIS de
    compor_blocos e não precisa reimplementar a regra do bloco-pai."""
    zonas_por_tag = {z["tag"]: z for z in catalogo.get("zones", [])}

    def resolver(tag_val):
        if not tag_val.startswith(ZONA_TAG_PREFIXO):
            return None, None  # blocos já foram compostos na passada anterior
        zona = zonas_por_tag.get(tag_val)
        if zona is None:
            raise ComposicaoAbortada("zona_nao_catalogada",
                                      f"tag de zona sem entrada no catálogo durante composição: {tag_val}")
        estado = estados_zonas.get(zona["id"])
        if estado not in ("INCLUIR", "EXCLUIR"):
            raise ComposicaoAbortada("zona_estado_invalido",
                                      f"{zona['id']}: estado '{estado}' inválido para composição")
        return estado, zona["id"]

    incluidas, excluidas = _compor_sdts_do_corpo(root, resolver)
    return {"incluidas": incluidas, "excluidas": excluidas}


def compor_zonas_xml(document_xml: str, catalogo: dict, estados_zonas: dict):
    """Wrapper string->string de compor_zonas — mesma função usada na
    geração real e na recomputação do Template Lock."""
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)
    resultado = compor_zonas(root, catalogo, estados_zonas)
    novo_xml = LET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True).decode("utf-8")
    return novo_xml, resultado


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
                           decisoes_blocos: dict, output_path, fatos_processuais: dict = None,
                           conteudo_zonas: dict = None) -> dict:
    """Pipeline completo com composição de blocos: valida catálogo ->
    valida/resolve decisões -> abre template -> valida SDTs contra
    catálogo -> compõe (unwrap/remove) -> RENUMERA títulos/subtítulos
    (docx_numeracao_engine, INV-NUMERACAO-DINAMICA-CONTESTACAO — só depois
    da árvore final, nunca antes) -> valida a numeração final -> substitui
    placeholders (já aplica FF0000, docx_template_engine.py) -> Template
    Lock composicional -> reempacota. Reaproveita toda a mecânica de
    placeholder/Template Lock/pack já existente em docx_template_engine.py
    — não duplica nada disso, só insere composição+renumeração ANTES da
    substituição.

    Nunca produz DOCX parcial: qualquer ComposicaoAbortada (composição OU
    renumeração — mesmo tipo de exceção, mesmo tratamento fail-closed)
    interrompe antes de qualquer escrita em output_path."""
    template_path = Path(template_path)
    if not template_path.exists():
        return {"status": "FALHOU", "etapa": "template", "erros": [f"template não encontrado: {template_path}"]}

    try:
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
        estados = validar_e_resolver_decisoes(catalogo, decisoes_blocos, fatos_processuais)
        estados_zonas = resolver_estados_zonas(catalogo, estados, conteudo_zonas, fatos_processuais)
    except ComposicaoAbortada as e:
        return {"status": "FALHOU", "etapa": e.stage, "erros": [e.motivo]}

    schema = carregar_schema(schema_path)
    unpack_mod, pack_mod = _importar_toolkit()

    # Etapa 5.8-B: o conteúdo das zonas INCLUIR entra no MESMO dicionário de
    # substituição dos placeholders — reaproveitando integralmente FF0000,
    # **negrito**, escape XML e a expansão multilinha em <w:p> irmãos com
    # herança do w:pPr (INV-PARAGRAFO-HERDA-TEMPLATE). Nenhuma lógica
    # paralela de cor ou de parágrafo (§11/§12 do pedido).
    tokens_zona = sorted(zid for zid, estado in estados_zonas.items() if estado == "INCLUIR")
    dados_efetivos = dict(dados)
    for zid in tokens_zona:
        dados_efetivos[zid] = conteudo_zonas[zid]

    def transformar(template_xml):
        composto_xml, _ = compor_xml(template_xml, catalogo, estados)
        com_zonas_xml, _ = compor_zonas_xml(composto_xml, catalogo, estados_zonas)
        renumerado_xml, _ = renumerar_titulos(com_zonas_xml)
        return substituir_placeholders(renumerado_xml, dados_efetivos)

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
            com_zonas_xml, resultado_zonas = compor_zonas_xml(composto_xml, catalogo, estados_zonas)
            renumerado_xml, relatorio_numeracao = renumerar_titulos(com_zonas_xml)
        except (ComposicaoAbortada, NumeracaoAbortada) as e:
            return {"status": "FALHOU", "etapa": e.stage, "erros": [e.motivo]}

        erros_numeracao = validar_numeracao_final(renumerado_xml)
        if erros_numeracao:
            return {"status": "FALHOU", "etapa": "numeracao_final", "erros": erros_numeracao}

        validacao = validar_placeholders(renumerado_xml, dados_efetivos, schema, tokens_zona=tokens_zona)
        if not validacao["ok"]:
            return {"status": "FALHOU", "etapa": "validacao_placeholders", "erros": validacao["erros"]}

        gerado_xml, substituidos = substituir_placeholders(renumerado_xml, dados_efetivos)
        gerado_dir = tmp / "gerado"
        shutil.copytree(unpacked_template, gerado_dir)
        (gerado_dir / "word" / "document.xml").write_text(gerado_xml, encoding="utf-8")

        lock = verificar_template_lock(unpacked_template, gerado_dir, dados_efetivos, transformar_xml=transformar)
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
            "zonas_incluidas": sorted(resultado_zonas["incluidas"]),
            "zonas_excluidas": sorted(resultado_zonas["excluidas"]),
            "zonas": dict(estados_zonas),
            "numeracao": relatorio_numeracao["numeracao"],
            "template_lock": "OK",
            "mensagem_pack": msg_pack,
        }
