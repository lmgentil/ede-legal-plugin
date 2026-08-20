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

lxml.etree é a tecnologia obrigatória para toda manipulação estrutural
(SDT/container/hierarquia/parágrafo/drawing/bookmark) — regex continua
reservado exclusivamente à substituição pontual de <w:t> já implementada
em docx_template_engine.py (não duplicada aqui).
"""
import json
import shutil
import sys
import tempfile
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
DECISION_MODES_VALIDOS = ("estrategista", "derived", "linked")
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


# ============================================================== Fase C/D/E/F — decisões
def validar_e_resolver_decisoes(catalogo: dict, decisoes: dict) -> dict:
    """Valida as decisões da etapa estratégica contra o catálogo, aborta
    em qualquer INDETERMINADO (mesmo com irmãos já decididos — nenhuma
    inferência jurídica parcial), e resolve os estados CONTAINER_DERIVED/
    'linked' a partir dos filhos/bloco referenciado. Retorna {id: estado}
    completo (folhas + containers + inline vinculado).

    `decisoes` deve conter, para cada bloco decision_mode='estrategista',
    {'decisao': 'INCLUIR'|'EXCLUIR'|'INDETERMINADO', ...}. Blocos
    'derived'/'linked' não devem aparecer em `decisoes`."""
    por_id = {b["id"]: b for b in catalogo["blocks"]}
    estados = {}

    for bid, b in por_id.items():
        if b["decision_mode"] != "estrategista":
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
        estados[bid] = estado

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
    intercala <w:bookmarkEnd> soltos entre parágrafos)."""
    tags_catalogo = {b["tag"]: b for b in catalogo["blocks"]}
    resultado = {"incluidos": [], "excluidos": []}

    def processar(pai):
        for filho in list(pai):
            if filho.tag != _qn("sdt"):
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
                           decisoes_blocos: dict, output_path) -> dict:
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
        estados = validar_e_resolver_decisoes(catalogo, decisoes_blocos)
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
