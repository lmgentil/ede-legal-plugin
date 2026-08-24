#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_numeracao_engine.py — motor de renumeração automática/dinâmica dos
títulos e subtítulos da Contestação (INV-NUMERACAO-DINAMICA-CONTESTACAO).

Causa raiz auditada diretamente no modelo-oficial.docx real (Fase 1 —
investigação estrutural, não regex cego):

  - Os títulos de NÍVEL 1 (badges: TEMPESTIVIDADE, PRELIMINARES, MÉRITO,
    LICITUDE DA COBRANÇA E CORTE, NEXO CAUSAL INDEMONSTRADO, DESCABIMENTO
    DE DANO MORAL, ÔNUS PROBATÓRIO, RECONVENÇÃO, REQUERIMENTOS) usam lista
    numerada NATIVA do Word (todos com <w:numPr><w:numId w:val="17"/>
    <w:ilvl w:val="0"/></w:numPr>, abstractNumId 6, numFmt="decimal",
    lvlText="%1.", start=1) — o número "1.", "2.", "3." NUNCA existe como
    texto literal no XML; é calculado pelo Word em tempo de abertura, a
    partir da posição do parágrafo entre os demais parágrafos numId=17/
    ilvl=0 do documento. Cada badge está corretamente aninhado dentro do
    próprio <w:sdt> do bloco a que pertence (confirmado estruturalmente —
    ver auditoria), então excluir um bloco já remove o badge inteiro; o
    Word recalcula os números remanescentes sozinho, sem lacuna. ESTA
    CAMADA JÁ É DINÂMICA POR CONSTRUÇÃO — não é a causa do bug relatado e
    este módulo NUNCA a toca (nem o numPr, nem insere dígito literal ali).

  - Os títulos de NÍVEL 2 e NÍVEL 3 (ex.: "2.1 -", "2.2 – REVOGAÇÃO...",
    "3.1 – LEGALIDADE...", "3.1.1 – SINOPSE DOS FATOS:", "3.1.2 –
    REALIDADE FÁTICA:", "3.2.", "3.3.", "3.4.", "4.1 -", "8.1 –") são
    puro TEXTO LITERAL digitado no <w:t> no momento da autoria do
    template — sem w:numPr, sem qualquer mecanismo (nativo do Word ou do
    pipeline) capaz de recalculá-los. `docx_block_engine.compor_blocos()`
    só faz unwrap/remove estrutural do SDT (INV-COMPOSICAO-BLOCOS) e nunca
    toca texto de título; `docx_template_engine.substituir_placeholders()`
    só toca runs com `{{PLACEHOLDER}}`. Resultado: excluir um bloco de
    nível 1 (ex.: PRELIMINARES) desloca corretamente os badges (via Word,
    nível 1) mas os prefixos hardcoded dos subtítulos de MÉRITO
    continuam "3.1"/"3.1.1"/"3.1.2" em vez de "2.1"/"2.1.1"/"2.1.2" — o
    salto de numeração relatado. Excluir um FILHO de nível 2 (ex.:
    DEVER_LEGAL_FISCALIZACAO = "3.2") também não fecha a lacuna para o
    irmão seguinte ("3.3" permanece "3.3" em vez de virar "3.2").

Correção: este módulo recalcula deterministicamente, a partir da árvore
JÁ COMPOSTA (blocos EXCLUIR já removidos fisicamente pelo
docx_block_engine — nenhuma heurística jurídica aqui, só aritmética de
posição), os prefixos literais de nível 2/3 — a única camada realmente
estática.

Achado adicional da Fase 3 (validação empírica contra o modelo real):
`docx_block_engine.compor_blocos()` SEMPRE remove o `<w:sdt>` do corpo,
tanto em EXCLUIR quanto em INCLUIR (unwrap — o conteúdo sobrevive, a tag
não). Ou seja, na árvore JÁ COMPOSTA nenhum `w:tag` de bloco condicional
sobrevive, incluído ou excluído — não é mais possível localizar um título
literal pela w:tag do seu SDT (essa era a estratégia original deste
módulo; abandonada após o teste contra o template real mostrar que todo
título de nível 2/3 desaparecia do plano de numeração, mesmo quando o
bloco correspondente estava INCLUIR). A única localização estrutural que
sobrevive à composição é o próprio conteúdo: cada nó é localizado pela
combinação [prefixo numérico no início de uma run] + [substring âncora,
única e auditada contra o modelo real, em algum lugar do PARÁGRAFO — não
necessariamente na mesma run do número; achado real: em "2.1 - ", número
e título vivem em runs distintas por causa da mudança de formatação]. Não
é regex cego sobre o documento inteiro: cada âncora é específica de um
único nó do catálogo, verificada contra o template real, e qualquer
ambiguidade (0 ocorrência num nó obrigatório, ou mais de 1 ocorrência)
aborta em vez de adivinhar.

`Alterar SOMENTE o número` (regra de formatação do pedido): a rescrita
substitui apenas o span inicial `\\d+(\\.\\d+)*` do <w:t> já localizado —
o restante da string (separador, espaço, título, negrito/cor/fonte do
run, `<w:pPr>`, tudo) nunca é tocado.
"""
import re

import lxml.etree as LET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
_NUM_PREFIXO_RE = re.compile(r"^(\d+(?:\.\d+)*)")


def _qn(tag):
    return f"{{{W}}}{tag}"


class NumeracaoAbortada(Exception):
    """Erro fail-closed da renumeração automática — mesmo contrato
    (stage/motivo) de docx_block_engine.ComposicaoAbortada, mas como
    classe própria: docx_block_engine já importa este módulo
    (gerar_peca_com_blocos aciona a renumeração), então importar
    ComposicaoAbortada de volta daqui criaria import circular. A etapa
    chamadora (docx_block_engine.gerar_peca_com_blocos) captura os dois
    tipos igualmente — tratamento fail-closed idêntico, nunca fallback
    silencioso."""

    def __init__(self, stage, motivo):
        self.stage = stage
        self.motivo = motivo
        super().__init__(f"stage={stage} — {motivo}")


# ============================================================== catálogo estrutural
# Ordem = ordem física no documento (auditada — Fase 1). `nivel`/`pai`
# definem a árvore de numeração; `ancora_sdt`/`ancora_sdt_pai`+
# `ancora_texto`/`ancora_texto` definem como localizar o nó estruturalmente
# (nunca por posição de índice, nunca por regex sobre o documento inteiro).
NOS_NIVEL_1 = (
    # nível 1: badges com numId=17 nativo do Word — nunca reescritos aqui,
    # só usados para CONTAR a posição atual (necessária como prefixo dos
    # filhos de nível 2). titulo_badge é o texto literal já auditado.
    {"id": "TEMPESTIVIDADE", "titulo_badge": "TEMPESTIVIDADE"},
    {"id": "PRELIMINARES", "titulo_badge": "PRELIMINARES"},
    {"id": "MERITO", "titulo_badge": "MÉRITO"},
    {"id": "LICITUDE_CORTE_SUSPENSAO", "titulo_badge": "LICITUDE DA COBRANÇA E CORTE"},
    {"id": "NEXO_CAUSAL_INDEMONSTRADO", "titulo_badge": "NEXO CAUSAL INDEMONSTRADO"},
    {"id": "DESCABIMENTO_DANO_MORAL", "titulo_badge": "DESCABIMENTO DE DANO MORAL"},
    {"id": "ONUS_PROBATORIO", "titulo_badge": "ÔNUS PROBATÓRIO"},
    {"id": "RECONVENCAO", "titulo_badge": "RECONVENÇÃO (ART. 343, CPC)"},
    {"id": "REQUERIMENTOS", "titulo_badge": "REQUERIMENTOS"},
)

NOS_LITERAIS = (
    # nível 2 — filhos de PRELIMINARES (container CONTAINER_DERIVED).
    # `ancora_texto` fica no PARÁGRAFO (não na mesma run do número: "2.1 -"
    # é uma run isolada, sem negrito, seguida por outra run com o título).
    {"id": "PRELIMINAR_CDC_INAPLICAVEL", "nivel": 2, "pai": "PRELIMINARES",
     "ancora_texto": "INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR", "obrigatorio": False},
    {"id": "PRELIMINAR_REVOGACAO_GRATUIDADE", "nivel": 2, "pai": "PRELIMINARES",
     "ancora_texto": "REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA", "obrigatorio": False},

    # nível 2/3 — dentro de MÉRITO (fixo, sempre presente)
    {"id": "LEGALIDADE_PROCEDIMENTOS", "nivel": 2, "pai": "MERITO",
     "ancora_texto": "LEGALIDADE DOS PROCEDIMENTOS", "obrigatorio": True},
    {"id": "SINOPSE_FATOS", "nivel": 3, "pai": "LEGALIDADE_PROCEDIMENTOS",
     "ancora_texto": "SINOPSE DOS FATOS", "obrigatorio": True},
    {"id": "REALIDADE_FATICA", "nivel": 3, "pai": "LEGALIDADE_PROCEDIMENTOS",
     "ancora_texto": "REALIDADE FÁTICA", "obrigatorio": True},
    {"id": "DEVER_LEGAL_FISCALIZACAO", "nivel": 2, "pai": "MERITO",
     "ancora_texto": "DEVER LEGAL DE FISCALIZAÇÃO", "obrigatorio": False},
    {"id": "DESNECESSIDADE_AVISO_PREVIO", "nivel": 2, "pai": "MERITO",
     "ancora_texto": "DESNECESSIDADE DE AVISO PRÉVIO", "obrigatorio": False},
    {"id": "CALCULOS_RECUPERACAO_CONSUMO", "nivel": 2, "pai": "MERITO",
     "ancora_texto": "CÁLCULOS DE RECUPERAÇÃO DE CONSUMO", "obrigatorio": False},

    # nível 2 — conteúdo fixo dentro do bloco LICITUDE_CORTE_SUSPENSAO;
    # some junto se o bloco-pai for EXCLUIR, por isso obrigatorio=False
    # (a ausência é legítima, não é erro).
    {"id": "TEMA_REPETITIVO_699", "nivel": 2, "pai": "LICITUDE_CORTE_SUSPENSAO",
     "ancora_texto": "TEMA REPETITIVO 699", "obrigatorio": False},

    # nível 2 — conteúdo fixo dentro do bloco RECONVENCAO; mesma lógica.
    {"id": "COBRANCA_DEBITOS_RECONVINDA", "nivel": 2, "pai": "RECONVENCAO",
     "ancora_texto": "COBRANÇA DE DÉBITOS DERIVADOS DA IRREGULARIDADE", "obrigatorio": False},
)
_NOS_LITERAIS_POR_ID = {n["id"]: n for n in NOS_LITERAIS}


# ============================================================== localização estrutural
# IMPORTANTE (achado da Fase 3 — validação empírica contra o template
# real): docx_block_engine.compor_blocos() SEMPRE remove o <w:sdt> do
# corpo, tanto em EXCLUIR (bloco inteiro descartado) quanto em INCLUIR
# (unwrap — o conteúdo é movido para o lugar do <w:sdt>, mas a tag some
# junto). Ou seja, na árvore JÁ COMPOSTA (que é o que este módulo recebe,
# por exigência do pedido — renumeração só depois da composição) NENHUM
# w:tag de bloco condicional sobrevive, includo ou excluído. Por isso a
# localização de título literal não pode se apoiar em w:tag de SDT — só
# resta o texto do próprio título, já removido/preservado pela composição
# (nunca por índice de posição, nunca por regex cego: cada nó exige a
# combinação [prefixo numérico no início da run] + [substring âncora,
# única e auditada contra o modelo real, em algum lugar do PARÁGRAFO]).
def _texto_paragrafo(p):
    return "".join(t.text or "" for t in p.iter(_qn("t")))


def _badges_nivel1_presentes(root):
    """Badges numId=17/ilvl=0 realmente presentes na árvore JÁ COMPOSTA, em
    ordem de documento — localização 100% estrutural (numPr direto do
    <w:pPr>, nunca por texto). Retorna [(id_catalogado, elemento_p), ...].
    Falha fechada se algum badge tiver texto fora do catálogo conhecido
    (template alterado indevidamente, CLAUDE.md §15) ou se a ordem relativa
    dos badges presentes não respeitar a ordem canônica (mesmo catálogo)."""
    titulos_por_id = {n["titulo_badge"]: n["id"] for n in NOS_NIVEL_1}
    ordem_canonica = [n["id"] for n in NOS_NIVEL_1]

    brutos = []
    for p in root.iter(_qn("p")):
        ppr = p.find("w:pPr", NS)
        if ppr is None:
            continue
        numPr = ppr.find("w:numPr", NS)
        if numPr is None:
            continue
        numId = numPr.find("w:numId", NS)
        ilvl = numPr.find("w:ilvl", NS)
        if numId is None or numId.get(_qn("val")) != "17":
            continue
        if ilvl is not None and ilvl.get(_qn("val")) != "0":
            continue
        texto = _texto_paragrafo(p).strip()
        if texto not in titulos_por_id:
            raise NumeracaoAbortada(
                "numeracao_badge_desconhecido",
                f"título de nível 1 fora do catálogo de numeração: {texto!r} "
                f"(template alterado indevidamente ou catálogo desatualizado)",
            )
        brutos.append((titulos_por_id[texto], p))

    # Cada badge é desenhado duas vezes (mc:Choice em DrawingML moderno +
    # mc:Fallback em VML legado — mesma forma, dois formatos de
    # compatibilidade, achado da auditoria) e as duas cópias aparecem
    # SEMPRE fisicamente adjacentes no documento, mesmo id resolvido. Para
    # CONTAR a posição de nível 1 sem contar a mesma seção duas vezes,
    # colapsa duplicatas ADJACENTES pelo id já resolvido — nunca por
    # identidade de objeto lxml (`id()` de um proxy `_Element` efêmero
    # pode ser reciclado pelo GC entre chamadas e colidir com outro nó;
    # armadilha real encontrada nesta implementação) e nunca por posição/
    # índice cru (a garantia real é "mesmo id, lado a lado", não "algum
    # padrão de contagem fixo").
    achados = []
    for bid, p in brutos:
        if achados and achados[-1][0] == bid:
            continue
        achados.append((bid, p))

    ids_achados = [a[0] for a in achados]
    posicoes = [ordem_canonica.index(i) for i in ids_achados]
    if posicoes != sorted(posicoes) or len(set(ids_achados)) != len(ids_achados):
        raise NumeracaoAbortada(
            "numeracao_ordem_badges_invalida",
            f"badges de nível 1 fora da ordem canônica ou duplicados: {ids_achados}",
        )
    return achados


def _localizar_run_literal(root, no):
    """Retorna o elemento <w:t> que carrega o prefixo numérico do título
    literal de `no`, ou None se o nó estiver legitimamente ausente (bloco
    EXCLUIR — conteúdo inteiro já descartado pela composição;
    `obrigatorio=False`). Candidato = run cujo próprio texto começa com
    `\\d+(\\.\\d+)*` E cujo PARÁGRAFO (não necessariamente a mesma run —
    achado real: "2.1 - " e o título que a segue vivem em runs distintas
    por causa de negrito/formatação) contém a substring âncora."""
    candidatos = []
    for t in root.iter(_qn("t")):
        if not _NUM_PREFIXO_RE.match(t.text or ""):
            continue
        p = t
        while p is not None and p.tag != _qn("p"):
            p = p.getparent()
        if p is not None and no["ancora_texto"] in _texto_paragrafo(p):
            candidatos.append(t)

    if not candidatos:
        if no["obrigatorio"]:
            raise NumeracaoAbortada(
                "numeracao_titulo_fixo_ausente",
                f"{no['id']}: título fixo não encontrado no template (esperado conter "
                f"{no['ancora_texto']!r}) — template alterado indevidamente ou catálogo desatualizado",
            )
        return None  # bloco condicional excluído — não reserva número
    if len(candidatos) > 1:
        raise NumeracaoAbortada(
            "numeracao_titulo_ambiguo",
            f"{no['id']}: mais de um título candidato encontrado para a âncora "
            f"{no['ancora_texto']!r} — catálogo de numeração precisa de âncora mais específica",
        )
    return candidatos[0]


# ============================================================== plano de numeração
def _planejar(root):
    """Constrói o plano de numeração da árvore JÁ COMPOSTA: {id: "N.N.N"}
    para todo nó de nível 2/3 realmente presente, junto com o elemento
    <w:t> correspondente. Não escreve nada — usado tanto por
    `renumerar_titulos` (que escreve) quanto por `validar_numeracao_final`
    (que só compara)."""
    badges = _badges_nivel1_presentes(root)
    numero_nivel1 = {bid: str(i + 1) for i, (bid, _p) in enumerate(badges)}

    numeros = dict(numero_nivel1)
    plano = []  # [(id, numero_str, elemento_w_t)]
    contadores = {}

    for no in NOS_LITERAIS:
        elemento = _localizar_run_literal(root, no)
        if elemento is None:
            continue  # bloco excluído — não reserva número (INV-NUMERACAO-DINAMICA-CONTESTACAO §1)
        pai_num = numeros.get(no["pai"])
        if pai_num is None:
            raise NumeracaoAbortada(
                "numeracao_pai_ausente",
                f"{no['id']}: título presente mas pai '{no['pai']}' ausente na "
                f"árvore composta — inconsistência entre composição de blocos e catálogo de numeração",
            )
        contadores[no["pai"]] = contadores.get(no["pai"], 0) + 1
        numero = f"{pai_num}.{contadores[no['pai']]}"
        numeros[no["id"]] = numero
        plano.append((no["id"], numero, elemento))

    return plano, numeros


def renumerar_titulos(document_xml: str):
    """Recalcula e reescreve os prefixos numéricos de nível 2/3 sobre o
    XML JÁ COMPOSTO (blocos EXCLUIR já removidos — INV-COMPOSICAO-BLOCOS).
    Nível 1 (badges numId=17) nunca é tocado — já é dinâmico via lista
    nativa do Word (ver módulo). Retorna (xml_renumerado, relatorio)."""
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)
    plano, numeros = _planejar(root)

    for _id, numero, elemento in plano:
        elemento.text = _NUM_PREFIXO_RE.sub(numero, elemento.text, count=1)

    novo_xml = LET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True).decode("utf-8")
    relatorio = {"numeracao": numeros, "titulos_renumerados": [i for i, _n, _e in plano]}
    return novo_xml, relatorio


# ============================================================== validador final (Fail Closed)
def validar_numeracao_final(document_xml: str) -> list:
    """Validação determinística e independente (defesa em profundidade,
    seção 10 do pedido): reparseia o XML final, RECALCULA do zero o plano
    de numeração esperado a partir da árvore estrutural, e confere que o
    número literal escrito em cada título bate exatamente com o esperado.
    Também varre o documento inteiro por qualquer título numerado
    (padrão N.N) fora do catálogo de numeração — número residual de bloco
    removido ou título que deveria ter sido renumerado e não foi. Retorna
    lista de erros (vazia = OK). Nunca corrige nada — só relata
    (`_checar_*`, mesmo padrão de scripts/validate_placeholder_semantics.py)."""
    erros = []
    try:
        parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
        root = LET.fromstring(document_xml.encode("utf-8"), parser)
        plano, numeros = _planejar(root)
    except NumeracaoAbortada as e:
        return [f"{e.stage}: {e.motivo}"]

    vistos = set()
    for _id, numero_esperado, elemento in plano:
        atual = _NUM_PREFIXO_RE.match(elemento.text or "")
        numero_atual = atual.group(1) if atual else None
        if numero_atual != numero_esperado:
            erros.append(
                f"{_id}: número atual {numero_atual!r} difere do esperado "
                f"{numero_esperado!r} (salto/lacuna/duplicata de numeração)"
            )
        if numero_esperado in vistos:
            erros.append(f"{_id}: número {numero_esperado!r} duplicado")
        vistos.add(numero_esperado)

    # números residuais: qualquer <w:t> com padrão "N.N..." em QUALQUER
    # lugar do documento que não seja um dos elementos já contabilizados
    # no plano é um título fora do catálogo — número de bloco removido que
    # sobrou, ou título novo que o catálogo ainda não conhece. Nunca
    # corrige; só reporta (fail closed, seção 10 do pedido).
    elementos_do_plano = {id(e) for _i, _n, e in plano}
    padrao_multi_nivel = re.compile(r"^\s*\d+\.\d+")
    for t in root.iter(_qn("t")):
        if padrao_multi_nivel.match(t.text or "") and id(t) not in elementos_do_plano:
            erros.append(f"título numerado residual/não catalogado: {(t.text or '')!r}")

    return erros


def _p_badge(texto):
    return ('<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="17"/></w:numPr></w:pPr>'
            f'<w:r><w:t>{texto}</w:t></w:r></w:p>')


def _p_texto(texto):
    return f'<w:p><w:r><w:t>{texto}</w:t></w:r></w:p>'


if __name__ == "__main__":
    # Auto-verificação mínima (ponytail: sem framework) — XML sintético já
    # PÓS-COMPOSIÇÃO (sem <w:sdt> nenhum — achado real: compor_blocos()
    # sempre remove a tag, incluído ou excluído; só o conteúdo sobrevive),
    # cobrindo o caso feliz + exclusão de container inteiro + exclusão de
    # filho intermediário sem deixar lacuna.
    XML_TUDO_INCLUIDO = (
        '<w:document xmlns:w="%s"><w:body>'
        + _p_badge("TEMPESTIVIDADE")
        + _p_badge("PRELIMINARES")
        + _p_texto("2.1 - INAPLICABILIDADE DO CÓDIGO DE DEFESA DO CONSUMIDOR")
        + _p_texto("2.2 - REVOGAÇÃO DA ASSITÊNCIA JUDICIÁRIA GRATUITA")
        + _p_badge("MÉRITO")
        + _p_texto("3.1 - LEGALIDADE DOS PROCEDIMENTOS")
        + _p_texto("3.1.1 - SINOPSE DOS FATOS")
        + _p_texto("3.1.2 - REALIDADE FÁTICA")
        + _p_texto("3.2 - DEVER LEGAL DE FISCALIZAÇÃO")
        + '</w:body></w:document>'
    ) % W

    novo_xml, rel = renumerar_titulos(XML_TUDO_INCLUIDO)
    assert rel["numeracao"]["PRELIMINAR_CDC_INAPLICAVEL"] == "2.1"
    assert rel["numeracao"]["PRELIMINAR_REVOGACAO_GRATUIDADE"] == "2.2"
    assert rel["numeracao"]["LEGALIDADE_PROCEDIMENTOS"] == "3.1"
    assert rel["numeracao"]["SINOPSE_FATOS"] == "3.1.1"
    assert rel["numeracao"]["REALIDADE_FATICA"] == "3.1.2"
    assert rel["numeracao"]["DEVER_LEGAL_FISCALIZACAO"] == "3.2"
    assert validar_numeracao_final(novo_xml) == []

    # caso B: PRELIMINARES inteiro excluído (parágrafos-badge e filhos
    # todos ausentes) — MÉRITO passa a ser o badge nº2, filhos herdam "2.x".
    XML_SEM_PRELIMINARES = (
        '<w:document xmlns:w="%s"><w:body>'
        + _p_badge("TEMPESTIVIDADE")
        + _p_badge("MÉRITO")
        + _p_texto("3.1 - LEGALIDADE DOS PROCEDIMENTOS")
        + _p_texto("3.1.1 - SINOPSE DOS FATOS")
        + _p_texto("3.1.2 - REALIDADE FÁTICA")
        + '</w:body></w:document>'
    ) % W
    _novo2, rel2 = renumerar_titulos(XML_SEM_PRELIMINARES)
    assert rel2["numeracao"]["LEGALIDADE_PROCEDIMENTOS"] == "2.1"
    assert rel2["numeracao"]["SINOPSE_FATOS"] == "2.1.1"
    assert rel2["numeracao"]["REALIDADE_FATICA"] == "2.1.2"
    assert "DEVER_LEGAL_FISCALIZACAO" not in rel2["numeracao"]

    # caso C: filho intermediário de MÉRITO excluído (3.2 some) — irmão
    # seguinte (3.3, aqui simulado como CÁLCULOS) assume "3.2", sem lacuna.
    XML_FILHO_EXCLUIDO = (
        '<w:document xmlns:w="%s"><w:body>'
        + _p_badge("TEMPESTIVIDADE")
        + _p_badge("MÉRITO")
        + _p_texto("3.1 - LEGALIDADE DOS PROCEDIMENTOS")
        + _p_texto("3.1.1 - SINOPSE DOS FATOS")
        + _p_texto("3.1.2 - REALIDADE FÁTICA")
        + _p_texto("3.3 - CÁLCULOS DE RECUPERAÇÃO DE CONSUMO")
        + '</w:body></w:document>'
    ) % W
    _novo3, rel3 = renumerar_titulos(XML_FILHO_EXCLUIDO)
    # MÉRITO é o 2º badge aqui (sem PRELIMINARES no XML sintético) — "3.2"
    # (o rótulo authored) deve virar "2.2", herdando o pai correto e sem
    # deixar lacuna no lugar do irmão excluído.
    assert rel3["numeracao"]["CALCULOS_RECUPERACAO_CONSUMO"] == "2.2"
    assert validar_numeracao_final(_novo3) == []

    print("docx_numeracao_engine: auto-verificação OK")
