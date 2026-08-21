#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_template_engine.py — motor de preenchimento de placeholders sobre o
DOCX oficial da Contestação, com Template Lock (SPEC-0001 REQ-013 a REQ-016,
REQ-032 a REQ-034; CLAUDE.md §13, §15, §16).

Princípios não negociáveis:
  - INV-012: o motor NUNCA reconstrói o DOCX do zero. Sempre parte de uma
    cópia de trabalho do template oficial; o template mestre nunca é lido
    em modo escrita nem sobrescrito.
  - Template Lock: o documento gerado deve ser, byte a byte, o template
    original com APENAS os nós <w:t> de placeholder alterados e a cor do
    run correspondente forçada para FF0000 (Etapa 3, regra transversal:
    todo conteúdo inserido pelo plugin fica em vermelho — texto fixo
    institucional nunca muda de cor). Qualquer outra diferença (cabeçalho,
    rodapé, estilo, fonte, imagem, parágrafo adicionado/removido) reprova
    a geração.
  - Fail closed: schema ausente, placeholder desconhecido, placeholder sem
    dado fornecido (geraria resíduo) ou toolkit OOXML ausente => falha
    explícita, nunca geração silenciosa incorreta.

Dependência externa (não vendorizada): o skill "docx" (unpack.py / pack.py /
validate.py), o mesmo procedimento já documentado em
skills/redator-peca-processual-elite/references/edicao-docx-timbrado.md.
Não reimplementamos desempacotamento/reempacotamento OOXML — reaproveitamos
o que já existe e já foi validado (REQ-045: evitar dependência/duplicação
desnecessária). Localizado em tempo de execução, nunca hardcodado a um único
caminho de máquina — ver _localizar_docx_toolkit().

Uso programático:
    from docx_template_engine import gerar_peca
    relatorio = gerar_peca(
        template_path="templates/contestacao/modelo-oficial.docx",
        schema_path="templates/contestacao/schema.json",
        dados={"JUIZO": "...", "AUTOR": "...", ...},
        output_path="saida/contestacao-caso-x.docx",
    )
"""
import copy
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import lxml.etree as LET

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W}


def _qn(tag):
    return f"{{{_W}}}{tag}"

# Casa opcionalmente o <w:rPr> anterior ao <w:t> (sempre o primeiro filho
# de <w:r> quando presente, por schema OOXML — nunca some nada semântico
# entre eles dentro da mesma run) + o próprio <w:t>. Entre rPr e t só pode
# haver espaço em branco insignificante — o toolkit unpack.py PRETTY-PRINTA
# o XML (indentação/quebra de linha) durante o desempacotamento, então
# "imediatamente adjacente" não pode exigir zero caracteres (achado real:
# exigir isso fazia cair no ramo "sem rPr" e criar um <w:rPr> duplicado,
# inválido — confirmado via validação XSD real desta implementação). O
# conteúdo do <w:rPr>, quando existe, nunca contém outro <w:rPr>/<w:t>
# aninhado (schema CT_RPr só tem propriedades simples), então o
# "não-guloso" aqui é seguro — diferente de tentar casar <w:p>/<w:r>
# inteiros, que PODEM conter cópias aninhadas via shape/txbxContent
# (achado real da Etapa 2 do diagnóstico forense).
_RUN_RE = re.compile(
    r"(?P<rpr_full><w:rPr>(?:(?!</w:rPr>).)*?</w:rPr>|<w:rPr/>)?"
    r"(?P<entre>[ \t\r\n]*)"
    r"<w:t(?P<tattrs>(?:\s[^>]*)?)>(?P<ttext>[^<]*)</w:t>",
    re.DOTALL,  # o próprio conteúdo do <w:rPr> pode vir pretty-printado
                # (uma propriedade por linha) pelo unpack.py — "." precisa
                # casar \n aqui, ou o rPr inteiro nunca é capturado (achado
                # real: caía silenciosamente no ramo "sem rPr" e duplicava).
)
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
_COLOR_RE = re.compile(r"<w:color\b[^/]*/>")

# Decisão aprovada (gate pós-diagnóstico forense): todo conteúdo inserido
# pelo plugin fica em FF0000 — regra transversal ao motor documental, não
# exclusiva da Contestação. Texto fixo do template nunca é tocado.
COR_CONTEUDO_GERADO = "FF0000"


def garantir_utf8():
    """No Windows, o encoding padrão de arquivo/console costuma ser cp1252,
    não UTF-8 — e o validador do skill 'docx' (dependência externa) não
    força encoding explícito em todas as leituras/prints, o que já causou
    UnicodeDecodeError/UnicodeEncodeError reais nesta auditoria ao validar
    o template oficial (acentuação em português). Em vez de deixar esse erro
    de terceiro vazar de forma confusa, os CLIs deste módulo relançam a si
    mesmos como subprocesso em modo UTF-8 (PEP 540) antes de tocar no
    toolkit. Chamar no início de main(), antes de qualquer outro trabalho.

    Usa subprocess (não os.execvpe): execvpe truncou o processo com
    segmentation fault quando testado via Git Bash/MSYS neste ambiente —
    a emulação de exec() no Windows é frágil o bastante para não valer o
    ganho de não ter um processo filho."""
    if os.name == "nt" and not sys.flags.utf8_mode:
        import subprocess
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-X", "utf8", *sys.argv], env=env)
        sys.exit(r.returncode)


# --------------------------------------------------------------- toolkit OOXML
def _localizar_docx_toolkit():
    """Localiza o diretório com unpack.py/pack.py/validate.py do skill
    'docx'. Não hardcodar um único caminho — procura nos locais usuais de
    instalação de skills do Claude Code (pessoal, projeto, e o padrão de
    sessões remotas tipo Cowork, se existir)."""
    import os

    home = Path.home()
    candidatos = [
        Path(os.environ["CLAUDE_PLUGIN_ROOT"]) / "skills" / "docx" / "scripts" / "office"
        if os.environ.get("CLAUDE_PLUGIN_ROOT") else None,
        home / ".claude" / "skills" / "docx" / "scripts" / "office",
        home / ".agents" / "skills" / "docx" / "scripts" / "office",
    ]
    try:
        candidatos += list(Path("/").glob("sessions/*/mnt/.claude/skills/docx/scripts/office"))
    except OSError:
        pass

    for c in candidatos:
        if c and (c / "unpack.py").exists() and (c / "pack.py").exists():
            return c
    return None


def _importar_toolkit():
    toolkit_dir = _localizar_docx_toolkit()
    if toolkit_dir is None:
        raise RuntimeError(
            "skill 'docx' (unpack.py/pack.py) não encontrado em nenhum local "
            "conhecido (~/.claude/skills/docx, ~/.agents/skills/docx, "
            "$CLAUDE_PLUGIN_ROOT/skills/docx). A geração não pode prosseguir "
            "sem ele — não há fallback de reconstrução do zero (INV-012)."
        )
    sys.path.insert(0, str(toolkit_dir))
    try:
        unpack_mod = importlib.import_module("unpack")
        pack_mod = importlib.import_module("pack")
    finally:
        sys.path.remove(str(toolkit_dir))
    return unpack_mod, pack_mod


# --------------------------------------------------------------- schema/dados
def carregar_schema(schema_path) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extrair_placeholders(texto_xml: str) -> set:
    return set(_PLACEHOLDER_RE.findall(texto_xml))


# --------------------------------------------------------------- substituição
def _xml_escape(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rpr_inner(rpr_full):
    """Conteúdo interno do <w:rPr> original (sem as tags de abertura/
    fechamento) — string vazia se não havia rPr algum ou se era
    <w:rPr/> (self-closing, sem propriedades)."""
    if not rpr_full or rpr_full == "<w:rPr/>":
        return ""
    return rpr_full[len("<w:rPr>"):-len("</w:rPr>")]


# CT_RPr (OOXML/ECMA-376) exige sequência fixa de elementos — w:color não
# pode ser simplesmente prependido: se o rPr já tiver w:rFonts/w:b/w:i/...
# (que precedem color no schema), inserir color antes deles invalida o
# documento ("Element rPr: This element is not expected", confirmado nesta
# implementação). Sequência oficial completa (CT_RPr) — usada para inserir
# qualquer propriedade nova (cor, negrito) na posição correta, dado o que
# já existe no rPr original.
_RPR_SEQUENCIA = (
    "w:rStyle", "w:rFonts", "w:b", "w:bCs", "w:i", "w:iCs", "w:caps",
    "w:smallCaps", "w:strike", "w:dstrike", "w:outline", "w:shadow",
    "w:emboss", "w:imprint", "w:noProof", "w:snapToGrid", "w:vanish",
    "w:webHidden", "w:color", "w:spacing", "w:w", "w:kern", "w:position",
    "w:sz", "w:szCs", "w:highlight", "w:u", "w:effect", "w:bdr", "w:shd",
    "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang",
    "w:eastAsianLayout", "w:specVanish", "w:oMath",
)


def _inserir_na_posicao_certa(rpr_sem_tag: str, elemento_xml: str, nome_tag: str) -> str:
    """Insere `elemento_xml` (ex.: '<w:b/>') em `rpr_sem_tag` na posição
    exigida pela sequência CT_RPr — imediatamente antes do primeiro
    elemento existente que deva vir depois de `nome_tag`; ao final do rPr
    se nenhum existir."""
    idx_alvo = _RPR_SEQUENCIA.index(nome_tag)
    pos_insercao = len(rpr_sem_tag)
    for tag in _RPR_SEQUENCIA[idx_alvo + 1:]:
        m = re.search(r"<" + re.escape(tag) + r"\b", rpr_sem_tag)
        if m and m.start() < pos_insercao:
            pos_insercao = m.start()
    return rpr_sem_tag[:pos_insercao] + elemento_xml + rpr_sem_tag[pos_insercao:]


def _inserir_cor_na_posicao_certa(rpr_sem_cor: str) -> str:
    return _inserir_na_posicao_certa(rpr_sem_cor, f'<w:color w:val="{COR_CONTEUDO_GERADO}"/>', "w:color")


def _rpr_com_cor_forcada(rpr_full) -> str:
    """<w:rPr> com <w:color w:val="FF0000"/> — única propriedade
    adicionada/sobrescrita, na posição exigida pela sequência do schema
    CT_RPr; qualquer <w:color/> pré-existente (inclusive o EE0000 já usado
    em parte do template real, tratado como inconsistência histórica do
    asset, não convenção) é removido antes. Todas as demais propriedades
    do run (fonte, tamanho, negrito, itálico...) permanecem exatamente
    como estavam, na mesma ordem relativa entre si."""
    sem_cor = _COLOR_RE.sub("", _rpr_inner(rpr_full))
    return f"<w:rPr>{_inserir_cor_na_posicao_certa(sem_cor)}</w:rPr>"


# Etapa 5.3 — §9: nome do tipo de irregularidade em negrito dentro do
# placeholder (marcação `**texto**` no valor, convenção já usada nos
# exemplos do achado real). Diferente de w:color (que tinha uma variante
# legada EE0000 a limpar), w:b/w:bCs é só ausência-ou-presença — só
# adiciona se ainda não existir, nunca remove negrito já presente no run
# original.
def _rpr_vermelho_negrito(rpr_full) -> str:
    """Mesma base de `_rpr_com_cor_forcada`, com <w:b/><w:bCs/> adicionados
    (se ainda não presentes) na posição correta do CT_RPr."""
    vermelho_inner = _rpr_inner(_rpr_com_cor_forcada(rpr_full))
    if "<w:b/>" not in vermelho_inner and "<w:b " not in vermelho_inner:
        vermelho_inner = _inserir_na_posicao_certa(vermelho_inner, "<w:b/>", "w:b")
    if "<w:bCs/>" not in vermelho_inner and "<w:bCs " not in vermelho_inner:
        vermelho_inner = _inserir_na_posicao_certa(vermelho_inner, "<w:bCs/>", "w:bCs")
    return f"<w:rPr>{vermelho_inner}</w:rPr>"


# Etapa 5.3 — §9: nome do tipo de irregularidade "**em negrito**" dentro
# do valor de um placeholder. Convenção markdown minimalista, escopo
# deliberadamente estreito (só negrito, só dentro de uma linha — nunca
# atravessa `<w:br/>`).
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _segmentar_negrito(texto: str) -> list:
    """[(texto_segmento, negrito: bool), ...] a partir de marcações
    **negrito** em `texto` (já escapado para XML — '*' não é caractere
    especial em XML, então a ordem escapar-depois-segmentar é segura)."""
    segmentos = []
    pos = 0
    for m in _BOLD_RE.finditer(texto):
        if m.start() > pos:
            segmentos.append((texto[pos:m.start()], False))
        segmentos.append((m.group(1), True))
        pos = m.end()
    if pos < len(texto) or not segmentos:
        segmentos.append((texto[pos:], False))
    return segmentos


# Etapa 5.3-B — INV-PARAGRAFO-HERDA-TEMPLATE: marca explícita e inequívoca
# de "este <w:br/> nasceu da expansão de um placeholder multiline", para
# _explodir_paragrafos_multilinha() converter cada linha lógica num <w:p>
# irmão real (clone do w:pPr do parágrafo-placeholder), em vez de deixar
# tudo dentro de um único <w:p>. Deliberadamente NÃO usa a cor FF0000 como
# sinal (frágil/inferido — um <w:br/> vermelho poderia existir por outro
# motivo no futuro); usa um atributo em namespace próprio, autocontido no
# elemento (não precisa ser declarado em lugar nenhum do documento) e
# removido junto com o marcador antes do XML final ser gravado — nunca
# alcança o schema OOXML/validate.py.
_NS_MARCADOR = "urn:ede:motor:marcador-quebra-multilinha"
_MARCADOR_BR = f'<w:br xmlns:ede="{_NS_MARCADOR}" ede:quebra="1"/>'
# Além do <w:br> marcado (fronteira entre linhas), cada <w:t> de conteúdo
# GERADO por esta expansão também carrega o mesmo sinal — necessário para
# _explodir_paragrafos_multilinha() distinguir "run nosso, pode mover para
# o novo parágrafo" de texto fixo do template que porventura exista na
# MESMA <w:p> logo após o placeholder (ex.: IRREGULARIDADE_ENCONTRADA tem
# um sufixo fixo — ", circunstância que..." — na própria run seguinte;
# sem este sinal, a expansão arrastaria esse sufixo para o parágrafo
# errado). Não é suficiente confiar apenas no marcador de quebra (§8: essa
# fronteira sozinha não diz até onde vai o conteúdo nosso quando há texto
# fixo interpolado).
_MARCADOR_LINHA_ATTR = f' xmlns:ede="{_NS_MARCADOR}" ede:linha="1"'


def _corpo_com_negrito(rpr_normal: str, rpr_negrito: str, attrs_ps: str, linhas: list) -> str:
    """Constrói a sequência de <w:rPr><w:t marcado>/<w:br marcado> para
    `linhas` (cada uma podendo ter **negrito**), agrupando <w:t>
    consecutivos de mesmo estado (negrito ou não) num único <w:r> real —
    só fecha/reabre run (`</w:r><w:r>`) quando o estado muda. Cada quebra
    entre linhas lógicas vira um <w:br/> marcado (ver _MARCADOR_BR),
    sempre isolado no seu próprio <w:r> — nunca agrupado com texto — para
    _explodir_paragrafos_multilinha() poder cortar exatamente ali."""
    itens = []  # ('t', texto, negrito) | ('br', None, None)
    for i, linha in enumerate(linhas):
        segmentos = _segmentar_negrito(linha)
        for texto_seg, negrito in segmentos:
            itens.append(("t", texto_seg, negrito))
        if i < len(linhas) - 1:
            itens.append(("br", None, None))

    grupos = []  # [(negrito, [filhos_xml], eh_marcador_isolado)]
    for kind, texto_seg, negrito in itens:
        if kind == "br":
            grupos.append((False, [_MARCADOR_BR], True))
            continue
        filho = f"<w:t{attrs_ps}{_MARCADOR_LINHA_ATTR}>{texto_seg}</w:t>"
        if grupos and grupos[-1][0] == negrito and not grupos[-1][2]:
            grupos[-1][1].append(filho)
        else:
            grupos.append((negrito, [filho], False))

    return "</w:r><w:r>".join(
        f"{rpr_negrito if negrito else rpr_normal}{''.join(filhos)}"
        for negrito, filhos, _ in grupos
    )


def _explodir_paragrafos_multilinha(document_xml: str) -> str:
    """Etapa 5.3-B / INV-PARAGRAFO-HERDA-TEMPLATE: converte cada marcador
    _MARCADOR_BR em um <w:p> irmão real, clonando (deep copy) o <w:pPr>
    do parágrafo que originou a quebra — em vez de manter as linhas
    lógicas como <w:br/> dentro de um único <w:p>. Isso faz cada linha de
    um valor multiline herdar exatamente jc/spacing/ind/keepNext/
    keepLines/widowControl/contextualSpacing/tabs/rPr-base do modelo, sem
    listar propriedade por propriedade (clonagem estrutural, não
    reconstrução manual) e sem exigir mudança se o modelo alterar seu
    w:pPr no futuro.

    Só age sobre marcadores explícitos (nunca sobre <w:br/> legítimo já
    existente no template — não tem o atributo do namespace próprio) e é
    idempotente por construção: só consome marcadores, nunca cria novos;
    chamar de novo sobre a própria saída é um no-op (fast path abaixo)."""
    if _NS_MARCADOR not in document_xml:
        return document_xml  # nenhum conteúdo gerado por _corpo_com_negrito

    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)

    p_tag, r_tag, t_tag, br_tag, rpr_tag = _qn("p"), _qn("r"), _qn("t"), _qn("br"), _qn("rPr")
    marcador_quebra_attr = f"{{{_NS_MARCADOR}}}quebra"
    marcador_linha_attr = f"{{{_NS_MARCADOR}}}linha"

    def eh_marcador(elemento):
        if elemento.tag != r_tag:
            return False
        conteudo = [f for f in elemento if f.tag != rpr_tag]  # ignora o <w:rPr> do run
        return len(conteudo) == 1 and conteudo[0].tag == br_tag and conteudo[0].get(marcador_quebra_attr) == "1"

    def eh_conteudo_gerado(elemento):
        """<w:r> cujo conteúdo (fora rPr) é só <w:t> marcados por nós —
        distingue de texto FIXO do template que porventura seja run-irmão
        na mesma <w:p> logo após o placeholder (ex.: sufixo fixo depois de
        IRREGULARIDADE_ENCONTRADA) — esse texto fixo não deve ser
        arrastado para o novo parágrafo."""
        if elemento.tag != r_tag:
            return False
        conteudo = [f for f in elemento if f.tag != rpr_tag]
        return bool(conteudo) and all(
            f.tag == t_tag and f.get(marcador_linha_attr) == "1" for f in conteudo
        )

    for p in list(root.iter(p_tag)):
        pai = p.getparent()
        if pai is None:
            continue
        atual = p
        while True:
            marcador = next((f for f in atual if eh_marcador(f)), None)
            if marcador is None:
                break
            pos = list(pai).index(atual)
            novo_p = LET.Element(p_tag)
            pprs = atual.find("w:pPr", _NS)
            if pprs is not None:
                novo_p.append(copy.deepcopy(pprs))
            pai.insert(pos + 1, novo_p)
            mover = False
            for irmao in list(atual):
                if irmao is marcador:
                    mover = True
                    atual.remove(irmao)
                    continue
                if not mover:
                    continue
                # só arrasta para o novo parágrafo o que é comprovadamente
                # nosso (outro marcador de quebra ou conteúdo marcado); ao
                # primeiro elemento não-marcado (texto fixo do template,
                # ex.: sufixo depois de IRREGULARIDADE_ENCONTRADA), para —
                # ele permanece no parágrafo atual, na posição em que já
                # estava (§8/§9: nunca inferir por heurística de cor).
                if eh_marcador(irmao) or eh_conteudo_gerado(irmao):
                    atual.remove(irmao)
                    novo_p.append(irmao)
                else:
                    break
            atual = novo_p

    # Marcador de linha (<w:t ede:linha="1">) já cumpriu seu papel — nunca
    # deve sobreviver ao XML final (schema OOXML não o conhece); some
    # também no caminho sem <w:br/> nenhum (valor multiline com uma única
    # linha lógica + **negrito**, onde nada precisa ser explodido).
    for t in root.iter(t_tag):
        if marcador_linha_attr in t.attrib:
            del t.attrib[marcador_linha_attr]

    saida = LET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True).decode("utf-8")
    # Remoção do atributo acima não apaga a declaração xmlns:ede residual do
    # elemento (lxml não faz GC de namespace por atributo removido) — NÃO
    # usar lxml.etree.cleanup_namespaces() aqui: ele varre a árvore inteira
    # e (confirmado empiricamente contra o template real) remove também as
    # declarações w14/w15/w16.../mc que o próprio documento usa em
    # mc:Ignorable no elemento raiz
    # (usadas só textualmente ali, não via elemento/atributo namespaced —
    # lxml não enxerga esse uso e as trata como "não usadas", quebrando
    # `pack.py --validate`). Troca segura e equivalente: remoção textual da
    # única string literal que este módulo é capaz de emitir.
    return saida.replace(f' xmlns:ede="{_NS_MARCADOR}"', "")


def _substituir_um_no(rpr_full, entre: str, attrs: str, texto: str, dados: dict, substituidos: set) -> str:
    tokens = _PLACEHOLDER_RE.findall(texto)
    rpr_original = rpr_full or ""
    if not tokens:
        return f"{rpr_original}{entre}<w:t{attrs}>{texto}</w:t>"
    if len(tokens) > 1:
        raise ValueError(
            f"Nó <w:t> com mais de um placeholder não é suportado por esta "
            f"engine (fail closed, evita substituição ambígua): {texto!r}"
        )
    nome = tokens[0]
    if nome not in dados:
        # placeholder sem dado fornecido: mantém como está aqui (rPr
        # original e espaçamento entre tags incluídos, intocados); é
        # rejeitado antes disso por validar_placeholders() (evita gerar
        # resíduo).
        return f"{rpr_original}{entre}<w:t{attrs}>{texto}</w:t>"

    substituidos.add(nome)
    token = "{{" + nome + "}}"
    valor_bruto = str(dados[nome])
    linhas = [_xml_escape(l) for l in valor_bruto.split("\n")]
    attrs_ps = attrs if "xml:space" in attrs else attrs + ' xml:space="preserve"'
    rpr_vermelho = _rpr_com_cor_forcada(rpr_full)

    if len(linhas) == 1 and "**" not in valor_bruto:
        # caminho rápido, comportamento idêntico ao anterior à Etapa 5.3
        # (placeholder de uma linha, sem negrito — nenhum <w:p> extra).
        return f"{rpr_vermelho}{entre}<w:t{attrs_ps}>{texto.replace(token, linhas[0])}</w:t>"

    if len(linhas) == 1:
        partes = [texto.replace(token, linhas[0])]
    else:
        prefixo, sufixo = texto.split(token, 1)
        n = len(linhas)
        partes = []
        for i, linha in enumerate(linhas):
            p = linha
            if i == 0:
                p = prefixo + p
            if i == n - 1:
                p = p + sufixo
            partes.append(p)

    # Etapa 5.3 §9: **negrito** por segmento. Etapa 5.3-B: quando há mais
    # de uma linha lógica, cada quebra entra marcada (_MARCADOR_BR) para
    # _explodir_paragrafos_multilinha() convertê-la em <w:p> irmão real.
    rpr_vermelho_negrito = _rpr_vermelho_negrito(rpr_full)
    corpo = _corpo_com_negrito(rpr_vermelho, rpr_vermelho_negrito, attrs_ps, partes)
    return f"{entre}{corpo}"


def substituir_placeholders(document_xml: str, dados: dict):
    """Retorna (xml_modificado, nomes_efetivamente_substituidos)."""
    substituidos = set()

    def _cb(m):
        return _substituir_um_no(m.group("rpr_full"), m.group("entre"),
                                  m.group("tattrs"), m.group("ttext"),
                                  dados, substituidos)

    novo = _RUN_RE.sub(_cb, document_xml)
    # Etapa 5.3-B / INV-PARAGRAFO-HERDA-TEMPLATE: expande linhas lógicas
    # marcadas em <w:p> irmãos reais, herdando o w:pPr do parágrafo-
    # placeholder (ver _explodir_paragrafos_multilinha).
    novo = _explodir_paragrafos_multilinha(novo)
    return novo, substituidos


# --------------------------------------------------------------- validação
def validar_placeholders(template_xml: str, dados: dict, schema: dict) -> dict:
    """REQ-034. TEST-003: placeholder fora do schema falha. Também falha se
    faltar dado para algum placeholder presente no template — gerar com
    placeholder residual (TEST-004) nunca é aceitável."""
    autorizados = set(schema["editable_placeholders"])
    no_template = extrair_placeholders(template_xml)
    fornecidos = set(dados.keys())

    erros = []
    fora_do_schema = fornecidos - autorizados
    if fora_do_schema:
        erros.append(f"dados fornecidos para placeholders fora do schema: {sorted(fora_do_schema)}")
    nao_previstos = no_template - autorizados
    if nao_previstos:
        erros.append(f"placeholders no DOCX não previstos no schema: {sorted(nao_previstos)}")
    faltando = no_template - fornecidos
    if faltando:
        erros.append(f"placeholders do template sem dado fornecido: {sorted(faltando)}")

    return {"ok": not erros, "erros": erros}


# --------------------------------------------------------------- Template Lock
def verificar_template_lock(template_dir: Path, gerado_dir: Path, dados: dict, transformar_xml=None) -> dict:
    """TEST-001/TEST-002: o gerado deve ser idêntico ao template exceto pela
    substituição controlada em word/document.xml. Qualquer outra diferença
    (cabeçalho, rodapé, imagem, estilo, parágrafo novo/removido) reprova.

    `transformar_xml`, se informado, substitui `substituir_placeholders`
    como função de recomputação do "esperado" — assinatura
    `(template_xml: str) -> (esperado_xml: str, info)`. Extensão usada pela
    composição de blocos condicionais (docx_block_engine.py): o "esperado"
    passa a ser template -> composição de blocos -> substituição de
    placeholders, mas a lógica de diff arquivo-a-arquivo abaixo (a parte
    que garante que NADA fora do document.xml foi tocado) permanece
    exatamente a mesma — não duplicada."""
    template_dir, gerado_dir = Path(template_dir), Path(gerado_dir)
    divergencias = []
    doc_xml_rel = Path("word/document.xml")

    arquivos_template = {f.relative_to(template_dir) for f in template_dir.rglob("*") if f.is_file()}
    arquivos_gerado = {f.relative_to(gerado_dir) for f in gerado_dir.rglob("*") if f.is_file()}

    for rel in sorted(arquivos_template - arquivos_gerado):
        divergencias.append(f"arquivo do template ausente no gerado: {rel}")
    for rel in sorted(arquivos_gerado - arquivos_template):
        divergencias.append(f"arquivo novo não autorizado no gerado: {rel}")

    for rel in sorted(arquivos_template & arquivos_gerado):
        if rel == doc_xml_rel:
            continue
        if (template_dir / rel).read_bytes() != (gerado_dir / rel).read_bytes():
            divergencias.append(f"arquivo alterado fora de word/document.xml (não autorizado): {rel}")

    template_xml = (template_dir / doc_xml_rel).read_text(encoding="utf-8")
    transformar = transformar_xml or (lambda xml: substituir_placeholders(xml, dados))
    esperado_xml, _ = transformar(template_xml)
    gerado_xml = (gerado_dir / doc_xml_rel).read_text(encoding="utf-8")
    if esperado_xml != gerado_xml:
        divergencias.append(
            "word/document.xml difere do esperado (template + substituição "
            "controlada dos placeholders) — alteração fora dos placeholders "
            "autorizados foi detectada"
        )

    residuais = extrair_placeholders(gerado_xml)
    if residuais:
        divergencias.append(f"placeholders residuais no documento gerado: {sorted(residuais)}")

    return {"ok": not divergencias, "divergencias": divergencias}


# --------------------------------------------------------------- orquestração
def gerar_peca(template_path, schema_path, dados: dict, output_path) -> dict:
    """Pipeline completo: valida -> substitui sobre cópia -> reempacota ->
    Template Lock. O template mestre é aberto só para leitura; toda escrita
    ocorre em diretório temporário e no output_path informado."""
    template_path = Path(template_path)
    if not template_path.exists():
        return {"status": "FALHOU", "etapa": "template", "erros": [f"template não encontrado: {template_path}"]}

    schema = carregar_schema(schema_path)
    unpack_mod, pack_mod = _importar_toolkit()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copia_template = tmp / "template_copy.docx"
        shutil.copy2(template_path, copia_template)  # INV-012: nunca ler/escrever o mestre diretamente

        unpacked_template = tmp / "template_unpacked"
        _, msg = unpack_mod.unpack(str(copia_template), str(unpacked_template))
        if not unpacked_template.exists():
            return {"status": "FALHOU", "etapa": "unpack", "erros": [msg]}

        template_xml = (unpacked_template / "word" / "document.xml").read_text(encoding="utf-8")

        validacao = validar_placeholders(template_xml, dados, schema)
        if not validacao["ok"]:
            return {"status": "FALHOU", "etapa": "validacao_placeholders", "erros": validacao["erros"]}

        gerado_xml, substituidos = substituir_placeholders(template_xml, dados)
        gerado_dir = tmp / "gerado"
        shutil.copytree(unpacked_template, gerado_dir)
        (gerado_dir / "word" / "document.xml").write_text(gerado_xml, encoding="utf-8")

        # Template Lock ANTES de reempacotar — mais barato e mais cedo falha
        lock = verificar_template_lock(unpacked_template, gerado_dir, dados)
        if not lock["ok"]:
            return {"status": "FALHOU", "etapa": "template_lock", "erros": lock["divergencias"]}

        output_path = Path(output_path)
        _, msg_pack = pack_mod.pack(
            str(gerado_dir), str(output_path),
            original_file=str(copia_template), validate=True,
        )
        if not output_path.exists():
            return {"status": "FALHOU", "etapa": "pack", "erros": [msg_pack]}

        return {
            "status": "OK",
            "template": str(template_path),
            "template_version": schema.get("version"),
            "documento_final": str(output_path),
            "placeholders_substituidos": sorted(substituidos),
            "template_lock": "OK",
            "mensagem_pack": msg_pack,
        }
