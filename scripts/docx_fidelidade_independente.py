#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_fidelidade_independente.py — verificação estrutural INDEPENDENTE do
DOCX gerado contra o Modelo Oficial (Gate 6.6-A §11).

Diferente de `docx_template_engine.verificar_template_lock` (que recomputa
o "esperado" chamando a MESMA cadeia de transformação do renderer —
`compor_xml` -> `compor_zonas_xml` -> `renumerar_titulos` ->
`substituir_placeholders` — e compara byte a byte com o gerado): este
módulo NUNCA chama nenhuma dessas quatro funções de mutação. A partir só
do TEMPLATE (texto fixo + tokens `{{...}}` ainda não substituídos), deriva
um PADRÃO esperado por conta própria (regex construída por substring, não
importada do renderer) e casa esse padrão contra o documento GERADO real
— uma auditoria de RESULTADO por um caminho de código genuinamente
diferente do de geração, não uma repetição do PROCESSO de geração.

Uso de `dados`/`conteudo_zonas`: nenhum. A verificação de conteúdo fixo
não depende de conhecer os valores fornecidos — só de o TEMPLATE (fonte
de verdade do que é fixo) e do documento GERADO real. A cor forçada
(`docx_template_engine.COR_CONTEUDO_GERADO`) é usada apenas como sinal
POSICIONAL auxiliar, para reconhecer quando um placeholder multiline foi
explodido em parágrafos irmãos (INV-PARAGRAFO-HERDA-TEMPLATE) — nunca
para decidir se o CONTEÚDO está correto (isso é feito pelo casamento de
padrão derivado do template).

Reaproveita `docx_block_engine._sdts_por_tag` (helper de LEITURA
estrutural, já usado por `validar_sdts_contra_catalogo`) e
`docx_template_engine._PLACEHOLDER_RE`/`COR_CONTEUDO_GERADO` — nunca a
lógica de composição/mutação em si.
"""
import re

import lxml.etree as LET

from docx_block_engine import _sdts_por_tag
from docx_template_engine import COR_CONTEUDO_GERADO, _PLACEHOLDER_RE

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS = {"w": W}

_RE_COR_GERADA = re.compile(rf'<w:color\s+w:val="{COR_CONTEUDO_GERADO}"\s*/>')
_RE_NUMERO_TITULO = re.compile(r"^\d+(?:\.\d+)*")


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
    """`False` quando `p` vive dentro de um SDT (bloco ou zona) cujo
    estado resolvido é EXCLUIR — todo aquele subtree é removido pelo
    renderer e não tem contrapartida no documento gerado, então não entra
    na comparação."""
    for ancestral in p.iterancestors(_qn("sdt")):
        tag_el = ancestral.find("w:sdtPr/w:tag", NS)
        tag_val = tag_el.get(_qn("val")) if tag_el is not None else None
        if tag_val in tags_fora_de_escopo:
            return False
    return True


def _tag_do_sdt_ancestral(t, ate):
    """Tag do `<w:sdt>` ancestral mais próximo de `t`, sem subir além de
    `ate` (o parágrafo `p` corrente) — usado só para reconhecer um
    fragmento INLINE condicional (`decision_mode="linked"`, ex.
    `INLINE:COM_RECONVENCAO`: o SDT embrulha só ALGUMAS runs no MEIO de
    um parágrafo de texto fixo, sem embrulhar o parágrafo inteiro — nunca
    aparece como ancestral de `t.getparent()`'s próprio `<w:p>`, então
    `_bloco_esta_em_escopo` — que só olha ancestrais do PARÁGRAFO — nunca
    o vê)."""
    el = t.getparent()
    while el is not None and el is not ate:
        if el.tag == _qn("sdt"):
            tag_el = el.find("w:sdtPr/w:tag", NS)
            return tag_el.get(_qn("val")) if tag_el is not None else None
        el = el.getparent()
    return None


def _texto_bruto_paragrafo(p, tags_linked_fora: frozenset = frozenset()) -> str:
    """Só os `<w:t>` cujo `<w:p>` mais próximo É `p` (nunca os de um
    `<w:p>` aninhado dentro dele), que não vivem no ramo `mc:Fallback`
    (ver `_paragrafo_mais_proximo`/`_dentro_de_fallback`), e que não vivem
    dentro de um fragmento INLINE condicional (`tags_linked_fora` —
    `decision_mode="linked"`, ex. `INLINE:COM_RECONVENCAO`): esse
    mecanismo é resolvido por regra própria do catálogo (par MC_PAIR,
    testado em `docx_block_engine`/`docx_numeracao_engine`) — fora do
    escopo desta verificação, exatamente como blocos `derived` o são para
    `verificar_sdts_bloco`."""
    return "".join(t.text or "" for t in p.iter(_qn("t"))
                   if not _dentro_de_fallback(t) and _paragrafo_mais_proximo(t) is p
                   and _tag_do_sdt_ancestral(t, p) not in tags_linked_fora)


def _paragrafo_totalmente_gerado(p, tags_linked_fora: frozenset = frozenset()) -> bool:
    """Sinal POSICIONAL (nunca de conteúdo): todo <w:t> não vazio do
    parágrafo tem a cor forçada de conteúdo gerado — parágrafo irmão novo,
    produto da explosão de um valor multiline, sem contrapartida física
    direta no template."""
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


def _normalizar_titulo(texto: str) -> str:
    return _RE_NUMERO_TITULO.sub("§N§", texto)


def _padrao_do_paragrafo_template(texto: str):
    """Deriva, POR SUBSTRING (nunca por importar a engine de
    substituição), o padrão esperado de um parágrafo do template: texto
    fixo escapado como regex, cada `{{TOKEN}}` virando um grupo curinga
    não guloso `.*?` (equivalente estrutural de `texto.replace(token,
    valor)`, mas calculado aqui de forma independente). `(padrao, bloco_isolado)`;
    `padrao` é `None` quando o parágrafo não contém nenhum token (comparação
    correta é igualdade literal, não regex). `bloco_isolado` é `True` quando
    o parágrafo não tem NENHUM texto fixo compartilhando-o com o token (só
    `{{TOKEN}}`, prefixo e sufixo vazios) — o único caso em que, na prática,
    a engine explode o valor em parágrafos irmãos quando ele é multiline
    (`_substituir_um_no`): um valor multiline que compartilhasse a mesma
    <w:t> com texto fixo grudaria o prefixo/sufixo só no primeiro/último
    irmão, fora do escopo desta verificação (nenhum dos 19 placeholders do
    contrato atual faz isso — todos os multiline vivem em parágrafo
    próprio, e a suíte de regressão prova essa premissa)."""
    if "{{" not in texto:
        return None, False
    ms = list(_PLACEHOLDER_RE.finditer(texto))
    prefixo, sufixo = texto[:ms[0].start()], texto[ms[-1].end():]
    partes = []
    pos = 0
    for m in ms:
        partes.append(re.escape(texto[pos:m.start()]))
        partes.append(r".*?")
        pos = m.end()
    partes.append(re.escape(texto[pos:]))
    padrao = re.compile("^" + "".join(partes) + "$", re.DOTALL)
    return padrao, (not prefixo and not sufixo)


def verificar_sequencia_locked(template_xml: str, gerado_xml: str, catalogo: dict,
                                estados_blocos: dict, estados_zonas: dict) -> list:
    """Prova que, fora dos blocos/zonas EXCLUÍDOS, a estrutura de
    parágrafos do gerado corresponde à do template — mesma ordem, mesmo
    texto fixo, únicas diferenças autorizadas sendo o conteúdo de
    placeholder/zona (casado contra um padrão DERIVADO do próprio texto do
    template, nunca contra `dados`) e o dígito de títulos renumerados
    (INV-NUMERACAO-DINAMICA-CONTESTACAO). Não chama nenhuma função de
    composição/substituição do renderer.

    Algoritmo de dois ponteiros (i = parágrafo do template, j = parágrafo
    do gerado), porque um placeholder multiline explode em N parágrafos
    irmãos no gerado — a correspondência deixa de ser 1:1:
      - parágrafo do template sem token: exige igualdade literal
        (normalizada só quanto ao prefixo numérico) com o parágrafo do
        gerado na mesma posição;
      - parágrafo do template com token: primeiro tenta casar o padrão
        derivado contra o PRÓPRIO parágrafo do gerado na mesma posição
        (caso comum — token e eventual texto fixo compartilham o mesmo
        parágrafo, sem explosão); se não casar, consome os parágrafos
        seguintes do gerado enquanto forem "totalmente gerados" (sinal de
        cor, nunca de conteúdo) — a explosão multiline consecutiva —, e
        exige que pelo menos um exista (explosão vazia é divergência)."""
    fora = {b["tag"] for b in catalogo["blocks"] if estados_blocos.get(b["id"]) == "EXCLUIR"}
    fora |= {z["tag"] for z in catalogo.get("zones", []) if estados_zonas.get(z["id"]) != "INCLUIR"}
    # Mesmo `fora` também filtra a nível de RUN (não só de parágrafo
    # inteiro via `_bloco_esta_em_escopo`): um bloco `decision_mode=
    # "linked"` (ex. INLINE_COM_RECONVENCAO, par MC_PAIR) embrulha só
    # ALGUMAS runs no MEIO de um parágrafo de texto fixo, nunca o
    # parágrafo inteiro — quando resolvido EXCLUIR, seu conteúdo (aqui,
    # "COM RECONVENÇÃO") desaparece do gerado mas continua fisicamente no
    # template; quando INCLUIR, permanece nos dois lados. O MESMO estado
    # já resolvido (`estados_blocos`) decide os dois níveis — nenhuma
    # regra de resolução própria do "linked" é reimplementada aqui.
    tags_linked = fora

    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root_t = LET.fromstring(template_xml.encode("utf-8"), parser)
    root_g = LET.fromstring(gerado_xml.encode("utf-8"), parser)

    paras_t = [p for p in root_t.iter(_qn("p")) if _bloco_esta_em_escopo(p, fora)]
    paras_g = [p for p in root_g.iter(_qn("p")) if _bloco_esta_em_escopo(p, fora)]

    divergencias = []
    i = j = 0
    while i < len(paras_t):
        if j >= len(paras_g):
            divergencias.append(f"parágrafo template #{i} sem contrapartida no gerado (gerado terminou antes)")
            break
        texto_t = _texto_bruto_paragrafo(paras_t[i], tags_linked)
        padrao, bloco_isolado = _padrao_do_paragrafo_template(texto_t)
        if padrao is None:
            texto_g = _texto_bruto_paragrafo(paras_g[j], tags_linked)
            if _normalizar_titulo(texto_t) != _normalizar_titulo(texto_g):
                divergencias.append(
                    f"parágrafo locked #{i}/#{j}: esperado {texto_t[:90]!r}, "
                    f"obtido {texto_g[:90]!r}")
            i += 1
            j += 1
            continue

        if bloco_isolado:
            # token sozinho no parágrafo (sem texto fixo compartilhado):
            # o único sinal confiável de onde termina o valor é a cor —
            # tentar casar regex contra UM parágrafo aqui seria ambíguo
            # (um padrão vazio-prefixo/vazio-sufixo casa com quase
            # qualquer coisa, inclusive só a PRIMEIRA linha de um valor
            # multiline explodido). Consome toda a corrida de parágrafos
            # totalmente gerados — 1 (valor de uma linha) ou N (explosão).
            consumidos = 0
            while j < len(paras_g) and _paragrafo_totalmente_gerado(paras_g[j], tags_linked):
                j += 1
                consumidos += 1
            if consumidos == 0:
                texto_g = _texto_bruto_paragrafo(paras_g[j], tags_linked) if j < len(paras_g) else "<fim do documento>"
                divergencias.append(
                    f"parágrafo template #{i} com placeholder isolado {texto_t[:90]!r} "
                    f"não tem parágrafo gerado correspondente em #{j} {texto_g[:90]!r}")
                j += 1  # evita loop infinito; segue tentando o próximo template
            i += 1
            continue

        texto_g = _texto_bruto_paragrafo(paras_g[j], tags_linked)
        if padrao.match(texto_g):
            i += 1
            j += 1
            continue

        divergencias.append(
            f"parágrafo template #{i} com placeholder embutido em texto fixo "
            f"{texto_t[:90]!r} não casou com o gerado #{j} {texto_g[:90]!r}")
        i += 1
        j += 1

    if j < len(paras_g):
        divergencias.append(
            f"{len(paras_g) - j} parágrafo(s) extra(s) no gerado sem contrapartida "
            f"no template, a partir da posição #{j}")
    return divergencias


def verificar_sdts_bloco(gerado_xml: str, catalogo: dict, estados_blocos: dict) -> list:
    """Nenhum wrapper `<w:sdt>` de bloco/zona sobrevive à composição —
    `compor_blocos` sempre faz unwrap (INCLUIR: mantém o conteúdo, remove
    só o invólucro `<w:sdt>`) ou remove por completo (EXCLUIR): a tag do
    catálogo nunca aparece de volta no documento final, em NENHUM dos dois
    estados. Detecta um wrapper que sobrou por engano — sinal de bug na
    composição, de qualquer estado."""
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root_g = LET.fromstring(gerado_xml.encode("utf-8"), parser)
    mapa_g = _sdts_por_tag(root_g)
    divergencias = []
    for b in catalogo["blocks"]:
        n = len(mapa_g.get(b["tag"], []))
        if n:
            divergencias.append(
                f"{b['id']} ({b['tag']}): {n} wrapper(s) <w:sdt> sobrevivente(s) no "
                f"gerado — nenhum bloco/zona deveria manter o invólucro após a "
                f"composição, estado resolvido {estados_blocos.get(b['id'])!r}")
    return divergencias


def escanear_tokens_residuais(gerado_xml: str) -> list:
    """`{{PLACEHOLDER}}` sobrevivente no documento final — nunca aceitável
    (mesma checagem que `docx_template_engine.validar_placeholders` já
    faz, reexecutada aqui de forma independente sobre o XML final real, não
    sobre o XML intermediário do próprio renderer)."""
    return sorted(set(_PLACEHOLDER_RE.findall(gerado_xml)))
