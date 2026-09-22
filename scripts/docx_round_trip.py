#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_round_trip.py — extração independente + comparação round-trip do
conteúdo gerado (Gate 6.6-A §12).

`accepted structured draft -> Official Model renderer -> generated DOCX ->
independent extraction of authorized mutable regions -> normalized
structured output -> equality comparison`.

A extração lê o DOCX GERADO real (nunca `dados` cacheado do renderer): usa
o TEMPLATE só para saber ONDE (texto fixo ao redor de cada `{{TOKEN}}`,
em ordem física de documento — mesma fonte de verdade estrutural que
`docx_fidelidade_independente` usa para provar fidelidade, e que
`docx_context_engine` usa para dar contexto ao Redator), e recorta o que
o renderer efetivamente inseriu no documento GERADO. Não chama
`substituir_placeholders`/`compor_xml` nem reimporta seus resultados.

Caminha os parágrafos do template e do gerado em lockstep (mesmo
algoritmo de dois ponteiros de `docx_fidelidade_independente`, reescrito
aqui de forma independente — CAPTURA em vez de só CASAR), porque um
placeholder multiline explode em parágrafos irmãos no gerado
(INV-PARAGRAFO-HERDA-TEMPLATE): a correspondência entre os dois documentos
deixa de ser 1:1 exatamente onde isso acontece.

Normalizações documentadas (nenhuma perda silenciosa de dado):
  1. quebras de linha em branco dentro de um valor multiline são
     ignoradas na comparação (mesmo critério de
     `validate_paragrafos.paragrafos`: um valor com `\\n\\n` entre
     parágrafos vira a MESMA lista de parágrafos que um com `\\n` simples
     — a própria engine de geração já descarta linha em branco ao
     explodir o valor, então a comparação segue esse mesmo critério, não
     inventa um novo);
  2. `**negrito**` markdown vira formatação real (`<w:b/>`) na
     renderização; a extração reconstrói `**...**` a partir da presença
     de `<w:b/>` no run capturado — não distingue negrito ACRESCENTADO
     pelo renderer de negrito PRÉ-EXISTENTE no run do template. Achado
     verificado (Gate 6.6-A): o run que carrega `{{IRREGULARIDADE_
     ENCONTRADA}}` no Modelo Oficial JÁ nasce em negrito no template —
     `_rpr_vermelho_negrito` só ADICIONA `<w:b/>` quando ainda não existe
     (nunca remove), então TODO o conteúdo desse placeholder sai em
     negrito, com ou sem marcação `**...**` no valor. Isso é consistente
     com o contrato (CLAUDE.md §14: "nome do tipo em **negrito**") — o
     valor real esperado é INTEIRAMENTE `**...**`, nunca negrito parcial;
     o round-trip reproduz esse caso exatamente (teste de regressão). Só
     um valor com negrito PARCIAL dentro de um placeholder cujo run já
     nasce em negrito no template não tem representação distinguível —
     limitação conhecida, documentada, sem ocorrência real no contrato
     atual dos 19 placeholders;
  3. a cor forçada (`w:color FF0000`) é presentational, nunca comparada.
"""
import re

import lxml.etree as LET

from docx_template_engine import COR_CONTEUDO_GERADO, _PLACEHOLDER_RE

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS = {"w": W}
_RE_NUMERO_TITULO = re.compile(r"^\d+(?:\.\d+)*")
_RE_COR_GERADA = re.compile(rf'<w:color\s+w:val="{COR_CONTEUDO_GERADO}"\s*/>')


def _qn(tag):
    return f"{{{W}}}{tag}"


def _dentro_de_fallback(p) -> bool:
    """`True` quando `p` descende de `<mc:Fallback>` — o ramo VML legado
    que toda forma/textbox ancorada moderna carrega ao lado do
    `<mc:Choice>` real (mesmo achado do Gate 6.5-B3/6.6-A em
    `docx_context_engine`/`docx_numeracao_engine`: um placeholder que
    vive dentro de uma forma ancorada, como o bloco de identificação
    "PROCESSO Nº {{NUMERO_PROCESSO}}" no cabeçalho, é desenhado duas
    vezes no XML — só a cópia em `mc:Choice` é conteúdo visível."""
    return any(a.tag == f"{{{MC}}}Fallback" for a in p.iterancestors())


def _paragrafo_mais_proximo(t):
    """`<w:p>` ancestral mais próximo de `t` — usado para que o texto de
    um parágrafo NUNCA inclua `<w:t>` que na verdade pertence a um `<w:p>`
    ANINHADO dentro dele (achado do Gate 6.6-A: um parágrafo pode
    hospedar uma forma/textbox ancorada — ex. o campo "PROCESSO Nº
    {{NUMERO_PROCESSO}}" do cabeçalho — cujo `mc:Choice` contém seu
    PRÓPRIO `<w:p>` interno; sem este filtro, o `<w:p>` externo "herdaria"
    o texto do interno via `.iter()`, duplicando ou deslocando conteúdo).
    Um parágrafo que não hospeda nada aninhado não muda de comportamento:
    todo `<w:t>` dele já tem só a si mesmo como `<w:p>` mais próximo."""
    p = t.getparent()
    while p is not None and p.tag != _qn("p"):
        p = p.getparent()
    return p


def _bloco_esta_em_escopo(p, tags_fora_de_escopo: set) -> bool:
    if _dentro_de_fallback(p):
        return False
    for ancestral in p.iterancestors(_qn("sdt")):
        tag_el = ancestral.find("w:sdtPr/w:tag", NS)
        tag_val = tag_el.get(_qn("val")) if tag_el is not None else None
        if tag_val in tags_fora_de_escopo:
            return False
    return True


def _run_negrito(t) -> bool:
    r = t.getparent()
    if r is None or r.tag != _qn("r"):
        return False
    rpr = r.find("w:rPr", NS)
    return rpr is not None and rpr.find("w:b", NS) is not None


def _texto_com_negrito_reconstruido(p) -> str:
    """Concatena os `<w:t>` do parágrafo reconstruindo `**negrito**`
    markdown a partir de `<w:b/>` — inverso de `docx_template_engine.
    _segmentar_negrito`/`_corpo_com_negrito`."""
    partes = []
    negritando = False
    for t in p.iter(_qn("t")):
        texto = t.text or ""
        if not texto or _dentro_de_fallback(t) or _paragrafo_mais_proximo(t) is not p:
            continue
        eh_negrito = _run_negrito(t)
        if eh_negrito != negritando:
            partes.append("**")
        partes.append(texto)
        negritando = eh_negrito
    if negritando:
        partes.append("**")
    return "".join(partes)


def _tag_do_sdt_ancestral(t, ate):
    """Tag do `<w:sdt>` ancestral mais próximo de `t`, sem subir além de
    `ate` — mesmo helper de `docx_fidelidade_independente`, reescrito
    aqui de forma independente: reconhece um fragmento INLINE condicional
    (`decision_mode="linked"`, ex. `INLINE:COM_RECONVENCAO`) que embrulha
    só ALGUMAS runs no MEIO de um parágrafo de texto fixo, sem embrulhar
    o parágrafo inteiro."""
    el = t.getparent()
    while el is not None and el is not ate:
        if el.tag == _qn("sdt"):
            tag_el = el.find("w:sdtPr/w:tag", NS)
            return tag_el.get(_qn("val")) if tag_el is not None else None
        el = el.getparent()
    return None


def _texto_bruto_paragrafo(p, tags_linked_fora: frozenset = frozenset()) -> str:
    """Só os `<w:t>` cujo `<w:p>` mais próximo É `p` (nunca os de um
    `<w:p>` aninhado dentro dele), que não vivem no ramo `mc:Fallback` —
    ver `_paragrafo_mais_proximo`/`_dentro_de_fallback` — e que não vivem
    dentro de um fragmento INLINE condicional (`tags_linked_fora`),
    resolvido por regra própria do catálogo, fora do escopo deste
    módulo."""
    return "".join(t.text or "" for t in p.iter(_qn("t"))
                   if not _dentro_de_fallback(t) and _paragrafo_mais_proximo(t) is p
                   and _tag_do_sdt_ancestral(t, p) not in tags_linked_fora)


def _paragrafo_totalmente_gerado(p, tags_linked_fora: frozenset = frozenset()) -> bool:
    """Sinal POSICIONAL (nunca de conteúdo, mesmo critério de
    `docx_fidelidade_independente`): todo `<w:t>` não vazio do parágrafo
    tem a cor forçada de conteúdo gerado — parágrafo irmão novo, produto
    da explosão de um valor multiline, sem contrapartida física direta no
    template. É o único sinal usado para saber ONDE PARA de consumir a
    corrida de irmãos de um placeholder isolado em seu próprio parágrafo
    — nunca para decidir o CONTEÚDO capturado (isso é sempre lido do
    texto/negrito real do parágrafo)."""
    algum = False
    for t in p.iter(_qn("t")):
        if (not (t.text or "") or _dentro_de_fallback(t) or _paragrafo_mais_proximo(t) is not p
                or _tag_do_sdt_ancestral(t, p) in tags_linked_fora):
            continue
        algum = True
        r = t.getparent()
        rpr = r.find("w:rPr", NS) if r is not None else None
        if rpr is None or not _RE_COR_GERADA.search(LET.tostring(rpr, encoding="unicode")):
            return False
    return algum


def _tags_fora_de_escopo(catalogo: dict, estados_blocos: dict, estados_zonas: dict) -> set:
    fora = {b["tag"] for b in catalogo["blocks"] if estados_blocos.get(b["id"]) == "EXCLUIR"}
    fora |= {z["tag"] for z in catalogo.get("zones", []) if estados_zonas.get(z["id"]) != "INCLUIR"}
    return fora


def extrair_valores_gerados(template_xml: str, gerado_xml: str, catalogo: dict,
                             estados_blocos: dict, estados_zonas: dict = None,
                             nomes: list = None) -> dict:
    """Caminha template e gerado em lockstep (parágrafos fora de bloco/
    zona EXCLUIR) e devolve, para cada nome em `nomes`, o valor
    efetivamente presente no GERADO — reconstruído com `**negrito**` a
    partir da formatação real. `None` quando o placeholder não tem
    ocorrência alcançável nesta composição (bloco/zona-dono EXCLUIR, ou
    nenhuma ocorrência no template) — reportado como INALCANÇÁVEL, nunca
    como "conteúdo perdido"."""
    estados_zonas = estados_zonas or {}
    fora = _tags_fora_de_escopo(catalogo, estados_blocos, estados_zonas)
    # mesmo `fora` filtra a nível de run (fragmento INLINE condicional
    # "linked", nunca embrulha o parágrafo inteiro) — ver mesma decisão
    # em docx_fidelidade_independente.verificar_sequencia_locked.
    tags_linked = fora

    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root_t = LET.fromstring(template_xml.encode("utf-8"), parser)
    root_g = LET.fromstring(gerado_xml.encode("utf-8"), parser)
    paras_t = [p for p in root_t.iter(_qn("p")) if _bloco_esta_em_escopo(p, fora)]
    paras_g = [p for p in root_g.iter(_qn("p")) if _bloco_esta_em_escopo(p, fora)]
    textos_g_negrito = [_texto_com_negrito_reconstruido(p) for p in paras_g]

    nomes_alvo = set(nomes) if nomes is not None else None
    capturas: dict = {}
    i = j = 0
    while i < len(paras_t):
        texto_t = _texto_bruto_paragrafo(paras_t[i], tags_linked)
        ms = list(_PLACEHOLDER_RE.finditer(texto_t))
        if not ms:
            i += 1
            j += 1
            continue
        nome = ms[0].group(1)
        prefixo, sufixo = texto_t[:ms[0].start()], texto_t[ms[-1].end():]
        isolado = not prefixo and not sufixo
        interessa = nomes_alvo is None or nome in nomes_alvo

        if isolado:
            # token sozinho no parágrafo (sem texto fixo compartilhado): o
            # único sinal confiável de onde termina o valor é a cor
            # forçada (nunca a busca pelo texto do próximo parágrafo do
            # template — que pode, ele mesmo, conter outro placeholder e
            # nunca aparecer literalmente no gerado). Consome toda a
            # corrida de parágrafos totalmente gerados — 1 (valor de uma
            # linha) ou N (explosão multiline).
            inicio = j
            while j < len(paras_g) and _paragrafo_totalmente_gerado(paras_g[j], tags_linked):
                j += 1
            if interessa:
                linhas = textos_g_negrito[inicio:j]
                capturas.setdefault(nome, []).append("\n".join(linhas) if linhas else None)
            i += 1
            continue

        # placeholder embutido em texto fixo: prefixo/sufixo vivem no
        # MESMO parágrafo gerado — casa por regex derivada do template
        # (mesma técnica de docx_fidelidade_independente, com grupo de
        # captura em vez de curinga não-capturado) e extrai o meio.
        padrao = re.compile("^" + re.escape(prefixo) + "(.*?)" + re.escape(sufixo) + "$", re.DOTALL)
        if j < len(paras_g):
            m = padrao.match(_texto_bruto_paragrafo(paras_g[j], tags_linked))
            if interessa:
                if m:
                    capturas.setdefault(nome, []).append(textos_g_negrito[j][len(prefixo):len(textos_g_negrito[j]) - len(sufixo)]
                                                          if textos_g_negrito[j].startswith(prefixo) and textos_g_negrito[j].endswith(sufixo)
                                                          else m.group(1))
                else:
                    capturas.setdefault(nome, []).append(None)
        elif interessa:
            capturas.setdefault(nome, []).append(None)
        i += 1
        j += 1

    resultado = {}
    alvo = nomes if nomes is not None else list(capturas)
    for nome in alvo:
        valores = [v for v in capturas.get(nome, []) if v is not None]
        resultado[nome] = valores[0] if valores else None
    return resultado


PLACEHOLDERS_COM_CARREGADOR_JA_NEGRITO = frozenset({"IRREGULARIDADE_ENCONTRADA"})
"""Normalização documentada #4 (Gate 6.6-A, achado verificado no Modelo
Oficial real — ver o item 2 da docstring do módulo): o `<w:r>` que carrega
`{{IRREGULARIDADE_ENCONTRADA}}` no template JÁ nasce em negrito,
independentemente de o valor conter `**...**`. A extração reconstrói
`**...**` fielmente a partir da formatação REAL (correto: o texto sai
todo em negrito) — mas isso pode divergir do valor original quando o
autor não marcou explicitamente `**...**`, mesmo o conteúdo por extenso
sendo idêntico. Só para os nomes aqui listados (verificados, nunca uma
regra geral de "ignorar negrito sempre" — isso mascararia negrito
genuinamente incorreto em qualquer outro campo), a comparação ignora
marcadores `**` dos dois lados. Nenhuma outra diferença é tolerada."""


def _sem_marcadores_negrito(valor: str) -> str:
    return str(valor).replace("**", "")


def _paragrafos_visiveis_normalizados(valor: str) -> list:
    """Mesma regra de `validate_paragrafos.paragrafos`: linhas em branco
    são separador de espaçamento, não conteúdo — reaproveitada aqui como
    a normalização DOCUMENTADA #1 do round-trip (nunca reimplementada com
    critério diferente)."""
    return [p for p in str(valor).split("\n") if p.strip()]


def comparar_round_trip(original: dict, extraido: dict, alcancaveis: set) -> list:
    """Compara `original` (o `dados` estruturado aceito) com `extraido`
    (saída de `extrair_valores_gerados`). `alcancaveis`: nomes cujo bloco
    dono está incluído nesta composição (o `SINOPSE_FATOS_NUCLEO_OBJETO` de
    um bloco excluído, por exemplo, fica de fora). Retorna a lista de
    divergências (vazia = round-trip aprovado)."""
    divergencias = []
    for nome, valor_original in original.items():
        valor_extraido = extraido.get(nome)
        if nome not in alcancaveis:
            if valor_extraido is not None:
                divergencias.append(
                    f"{nome}: esperado INALCANÇÁVEL (bloco/zona-dono excluído), "
                    f"mas foi encontrado no documento gerado: {valor_extraido!r}")
            continue
        if valor_extraido is None:
            divergencias.append(f"{nome}: alcançável nesta composição, mas não "
                                f"foi localizado no documento gerado (âncora não bateu)")
            continue
        original_cmp, extraido_cmp = valor_original, valor_extraido
        if nome in PLACEHOLDERS_COM_CARREGADOR_JA_NEGRITO:
            original_cmp, extraido_cmp = _sem_marcadores_negrito(original_cmp), _sem_marcadores_negrito(extraido_cmp)
        if _paragrafos_visiveis_normalizados(original_cmp) != _paragrafos_visiveis_normalizados(extraido_cmp):
            divergencias.append(
                f"{nome}: round-trip divergente\n  original: {valor_original!r}\n"
                f"  extraído: {valor_extraido!r}")
    extras = set(extraido) - set(original)
    if extras:
        divergencias.append(f"placeholders extraídos sem correspondência em `original`: {sorted(extras)}")
    return divergencias
