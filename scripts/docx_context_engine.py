#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_context_engine.py — extração SOMENTE LEITURA do contexto
institucional do modelo-oficial.docx ao redor de cada placeholder
(Etapa 5.7-B, INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA — SPEC-0001 §56).

Objetivo: dar ao Redator, de forma DETERMINÍSTICA e DERIVADA DO TEMPLATE
REAL (nunca por transcrição manual em SKILL.md — achado da Etapa 5.7-A),
o texto fixo institucional imediatamente relacionado a cada placeholder,
para que ele saiba o que o modelo já diz antes de redigir o valor
variável — sem nunca escrever fora dos 13 placeholders autorizados.

Princípios não negociáveis (herdados de docx_template_engine.py/
docx_block_engine.py, não duplicados aqui):
  - SOMENTE LEITURA: este módulo nunca serializa (`lxml.etree.tostring`)
    nem grava o XML de volta. Não altera `document.xml`, não altera o
    template. `extrair_contexto_do_template()` só abre o `.docx` mestre
    para CÓPIA (INV-012, mesmo padrão de `docx_template_engine.gerar_peca`
    — nunca lê/escreve o arquivo original diretamente), descartando a
    cópia desempacotada ao final.
  - Não decide nada: não valida SDT contra catálogo (já feito por
    `docx_block_engine.validar_sdts_contra_catalogo` no caminho de
    geração real), não valida placeholders contra schema (já feito por
    `docx_template_engine.validar_placeholders`) — este módulo é puramente
    informativo/consultivo, nunca autoritativo. Tag de SDT desconhecida
    no catálogo aqui só resulta em `bloco: None` para o contexto daquele
    placeholder, nunca um abort — o abort estrutural já existe alhures.
  - lxml.etree é a tecnologia obrigatória para toda manipulação
    estrutural (mesma convenção de docx_block_engine.py) — regex só é
    usado para reconhecer o token `{{PLACEHOLDER}}` dentro do texto já
    extraído de um `<w:t>` (reaproveita `_PLACEHOLDER_RE` de
    docx_template_engine.py, não duplicado aqui).

Uso programático:
    from docx_context_engine import extrair_contexto_do_template
    contexto = extrair_contexto_do_template(
        "templates/contestacao/modelo-oficial.docx",
        "templates/contestacao/blocos.json",
    )
    # contexto["SINOPSE_FATOS"] -> [{"titulo": ..., "antes": ..., "depois": ..., "bloco": ...}]
"""
import re
import shutil
import tempfile
from pathlib import Path

import lxml.etree as LET

from docx_block_engine import carregar_catalogo, validar_catalogo
from docx_template_engine import _PLACEHOLDER_RE, _importar_toolkit

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

# Mesmo critério estrutural já auditado/usado por docx_numeracao_engine.py
# para localizar título de nível 2/3 (número no início do parágrafo,
# seguido de separador) — reaproveitado aqui só como HEURÍSTICA DE LEITURA
# (identificar qual parágrafo anterior "parece um título"), nunca como
# fonte de verdade estrutural (essa continua sendo docx_numeracao_engine.py
# para fins de renumeração). Nível 1 (badges numId=17) é reconhecido à
# parte, por estrutura (w:numPr), não por regex.
_TITULO_LITERAL_RE = re.compile(r"^\s*\d+(?:\.\d+)*\s*[-–—]")


def _qn(tag):
    return f"{{{W}}}{tag}"


class ContextoAbortada(Exception):
    """Fail-closed deste módulo — mesmo contrato (stage/motivo) de
    ComposicaoAbortada/NumeracaoAbortada. Escopo deliberadamente estreito:
    só cobre falhas de LEITURA (template ausente, unpack falhou, XML sem
    <w:body>) — nunca decide sobre conteúdo jurídico."""

    def __init__(self, stage, motivo):
        self.stage = stage
        self.motivo = motivo
        super().__init__(f"stage={stage} — {motivo}")


def _texto_paragrafo(p) -> str:
    return "".join(t.text or "" for t in p.iter(_qn("t")))


def _eh_titulo_nivel1(p) -> bool:
    """Badge de nível 1 — lista numerada nativa do Word (numId=17,
    ilvl=0), mesmo critério de docx_numeracao_engine._badges_nivel1_presentes,
    aqui só para RECONHECER (não para contar/validar contra catálogo)."""
    ppr = p.find("w:pPr", NS)
    if ppr is None:
        return False
    num_pr = ppr.find("w:numPr", NS)
    if num_pr is None:
        return False
    num_id = num_pr.find("w:numId", NS)
    if num_id is None or num_id.get(_qn("val")) != "17":
        return False
    ilvl = num_pr.find("w:ilvl", NS)
    return ilvl is None or ilvl.get(_qn("val")) == "0"


def _eh_titulo(p) -> bool:
    return _eh_titulo_nivel1(p) or bool(_TITULO_LITERAL_RE.match(_texto_paragrafo(p)))


def _bloco_ancestral(p, tags_para_id: dict):
    """Id (catálogo) do <w:sdt> ancestral mais próximo de `p`, ou None se
    o placeholder não vive dentro de nenhum bloco condicional. Tag de SDT
    fora do catálogo é ignorada aqui (não é papel deste módulo abortar por
    isso — ver docstring do módulo); cai para o próximo ancestral."""
    for ancestral in p.iterancestors(_qn("sdt")):
        tag_el = ancestral.find("w:sdtPr/w:tag", NS)
        tag_val = tag_el.get(_qn("val")) if tag_el is not None else None
        if tag_val in tags_para_id:
            return tags_para_id[tag_val]
    return None


def extrair_contexto(document_xml: str, catalogo: dict) -> dict:
    """Função pura: XML (string) + catálogo já carregado -> dict de
    contexto. Nunca grava nada, nunca reserializa a árvore — só percorre.

    Retorna {NOME_PLACEHOLDER: [ocorrencia, ...]} em ordem de documento;
    um placeholder que aparece mais de uma vez no template (ex.: VALOR_FRA,
    IRREGULARIDADE_ENCONTRADA, NUMERO_PROCESSO — achado da Etapa 5.7-A)
    recebe uma entrada por ocorrência física, cada uma com seu próprio
    contexto (podem viver em blocos condicionais diferentes). Cada
    ocorrência é {"titulo": str|None, "antes": str, "depois": str,
    "bloco": str|None}.

    "antes"/"depois": texto do PRÓPRIO parágrafo do placeholder, antes/
    depois do token; quando o placeholder está sozinho no parágrafo (texto
    local vazio de um dos lados, achado comum na Etapa 5.7-A: a maioria dos
    13 placeholders vive em parágrafo próprio), cai para o parágrafo
    não-vazio mais próximo na mesma direção, em ORDEM FÍSICA do documento
    (nunca por índice de bloco/sdt — mesmo princípio de docx_numeracao_
    engine._planejar, que também nunca assume índice de parágrafo == índice
    de filho do corpo)."""
    parser = LET.XMLParser(remove_blank_text=False, strip_cdata=False)
    root = LET.fromstring(document_xml.encode("utf-8"), parser)
    body = root.find("w:body", NS)
    if body is None:
        raise ContextoAbortada("template_invalido", "documento sem <w:body>")

    tags_para_id = {b["tag"]: b["id"] for b in catalogo["blocks"]}

    paragrafos = list(root.iter(_qn("p")))
    textos = [_texto_paragrafo(p) for p in paragrafos]

    def _titulo_anterior(idx):
        for j in range(idx - 1, -1, -1):
            if _eh_titulo(paragrafos[j]):
                texto = textos[j].strip()
                if texto:
                    return texto
        return None

    def _paragrafo_nao_vazio_mais_proximo(idx, passo):
        j = idx + passo
        while 0 <= j < len(paragrafos):
            texto = textos[j].strip()
            if texto:
                return texto
            j += passo
        return None

    contexto = {}
    for idx, p in enumerate(paragrafos):
        texto = textos[idx]
        for m in _PLACEHOLDER_RE.finditer(texto):
            nome = m.group(1)
            antes = texto[:m.start()].strip() or _paragrafo_nao_vazio_mais_proximo(idx, -1) or ""
            depois = texto[m.end():].strip() or _paragrafo_nao_vazio_mais_proximo(idx, +1) or ""
            ocorrencia = {
                "titulo": _titulo_anterior(idx),
                "antes": antes,
                "depois": depois,
                "bloco": _bloco_ancestral(p, tags_para_id),
            }
            contexto.setdefault(nome, []).append(ocorrencia)

    return contexto


def extrair_contexto_do_template(template_path, catalogo_path) -> dict:
    """Wrapper de conveniência: desempacota uma CÓPIA do `.docx` mestre
    (INV-012 — nunca abre o original em modo escrita, nunca reempacota)
    e chama `extrair_contexto`. A pasta temporária é sempre descartada ao
    final (`with tempfile.TemporaryDirectory()`), inclusive em erro."""
    template_path = Path(template_path)
    if not template_path.exists():
        raise ContextoAbortada("template_ausente", f"template não encontrado: {template_path}")

    catalogo = carregar_catalogo(catalogo_path)
    validar_catalogo(catalogo)
    unpack_mod, _pack_mod = _importar_toolkit()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copia = tmp / "template_copy.docx"
        shutil.copy2(template_path, copia)  # nunca lê o mestre diretamente

        unpacked = tmp / "template_unpacked"
        _, msg = unpack_mod.unpack(str(copia), str(unpacked))
        documento = unpacked / "word" / "document.xml"
        # Achado real desta implementação: `unpack_mod.unpack()` (toolkit
        # externo "docx", não vendorizado) pode criar `unpacked` mesmo
        # quando o .docx de entrada é inválido (zip corrompido/arquivo
        # arbitrário) — checar só `unpacked.exists()` não é suficiente
        # (deixava um FileNotFoundError não tratado escapar na leitura
        # abaixo, violando fail-closed — item 6 da Etapa 5.7-C). Checa o
        # arquivo que de fato importa.
        if not documento.exists():
            raise ContextoAbortada("unpack_falhou", msg or f"{template_path}: falha ao "
                                    "desempacotar (word/document.xml ausente após unpack — "
                                    "arquivo não é um .docx válido)")

        document_xml = documento.read_text(encoding="utf-8")

    return extrair_contexto(document_xml, catalogo)
