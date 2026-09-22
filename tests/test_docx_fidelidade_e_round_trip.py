# -*- coding: utf-8 -*-
"""
tests/test_docx_fidelidade_e_round_trip.py — Gate 6.6-A: verificação
estrutural INDEPENDENTE (`scripts/docx_fidelidade_independente.py`) e
round-trip (`scripts/docx_round_trip.py`) do DOCX gerado.

Dois níveis, mesmo padrão do resto do projeto:
  1. Unidade sobre XML sintético — sempre roda, prova que os dois módulos
     detectam corrupção real (não são um "sempre `ok`").
  2. `docx_real` — ponta a ponta contra o Modelo Oficial real: renderiza
     via o pipeline canônico (`docx_block_engine.gerar_peca_com_blocos`,
     nenhum renderer concorrente), depois verifica o resultado com os
     dois módulos independentes. Reaproveita o MESMO `dados`/decisões já
     usados por `test_docx_block_engine.py::
     test_pipeline_completo_com_blocos_contra_template_real` (fixture de
     regressão já existente e aprovada — não os valores de aceite do
     Gate 6.6-A, que seguem bloqueados por falha de validador própria,
     reportada à parte).
"""
import sys
import tempfile
from pathlib import Path

import lxml.etree as LET
import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import docx_block_engine as be  # noqa: E402
import docx_context_engine as ce  # noqa: E402
import docx_fidelidade_independente as fi  # noqa: E402
import docx_round_trip as rt  # noqa: E402
import validate_placeholder_semantics as vs  # noqa: E402
from docx_package import extrair_pacote_docx  # noqa: E402
from docx_template_engine import COR_CONTEUDO_GERADO  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"


def _pular_se_sem_template_real():
    if not TEMPLATE_REAL.exists():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")


# ===================================================================== unidade

CATALOGO_VAZIO = {"blocks": [], "zones": []}


CATALOGO_SIMPLES = {"blocks": [
    {"id": "A", "tag": "BLOCO:A", "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [],
     "decision_mode": "estrategista", "placeholders": [], "dependencies": [], "cardinality": "ONE"},
], "zones": []}


def _p(texto):
    return f'<w:p><w:r><w:t>{texto}</w:t></w:r></w:p>'


def _p_gerado(texto):
    return (f'<w:p><w:r><w:rPr><w:color w:val="{COR_CONTEUDO_GERADO}"/></w:rPr>'
            f'<w:t xml:space="preserve">{texto}</w:t></w:r></w:p>')


def _sdt(tag, conteudo):
    return f'<w:sdt><w:sdtPr><w:tag w:val="{tag}"/></w:sdtPr><w:sdtContent>{conteudo}</w:sdtContent></w:sdt>'


def _doc(*paragrafos):
    return f'<w:document xmlns:w="{W}"><w:body>{"".join(paragrafos)}</w:body></w:document>'


def _render_sintetico(template_xml, estados, dados, catalogo=None):
    """Mesma cadeia canônica (`compor_xml` -> `substituir_placeholders`),
    só sem renumeração (documentos sintéticos aqui não têm badge/título
    numerado) — usada para PRODUZIR o "gerado" que os testes de unidade
    então verificam com os módulos independentes."""
    import docx_template_engine as te
    composto, _ = be.compor_xml(template_xml, catalogo or CATALOGO_SIMPLES, estados)
    gerado, _ = te.substituir_placeholders(composto, dados)
    return composto, gerado


def test_sequencia_locked_aprova_render_correto():
    template = _doc(_p("Texto fixo antes."),
                     _p("{{VALOR}}"),
                     _p("Texto fixo depois."),
                     _sdt("BLOCO:A", _p("Conteúdo condicional.")))
    estados = {"A": "EXCLUIR"}
    _, gerado = _render_sintetico(template, estados, {"VALOR": "conteúdo gerado"})
    divs = fi.verificar_sequencia_locked(template, gerado, CATALOGO_SIMPLES, estados, {})
    assert divs == []


def test_sequencia_locked_detecta_alteracao_de_texto_fixo():
    template = _doc(_p("Texto fixo antes."), _p("{{VALOR}}"), _p("Texto fixo depois."))
    estados = {}
    _, gerado = _render_sintetico(template, estados, {"VALOR": "x"}, catalogo=CATALOGO_VAZIO)
    gerado_corrompido = gerado.replace("Texto fixo depois.", "TEXTO ALTERADO SEM AUTORIZAÇÃO.")
    divs = fi.verificar_sequencia_locked(template, gerado_corrompido, CATALOGO_VAZIO, estados, {})
    assert divs and any("locked" in d for d in divs)


def test_sequencia_locked_detecta_paragrafo_extra_nao_autorizado():
    template = _doc(_p("Único parágrafo fixo."))
    estados = {}
    gerado = template.replace("</w:body>", _p("PARÁGRAFO INSERIDO SEM AUTORIZAÇÃO.") + "</w:body>")
    divs = fi.verificar_sequencia_locked(template, gerado, CATALOGO_SIMPLES, estados, {})
    assert divs and any("extra" in d for d in divs)


def test_sequencia_locked_multiline_explodido_bate_com_template():
    template = _doc(_p("Antes."), _p("{{VALOR}}"), _p("Depois."))
    estados = {}
    gerado = _doc(_p("Antes."), _p_gerado("linha 1") + _p_gerado("linha 2"), _p("Depois."))
    divs = fi.verificar_sequencia_locked(template, gerado, CATALOGO_SIMPLES, estados, {})
    assert divs == []


def test_verificar_sdts_bloco_detecta_wrapper_sobrevivente():
    gerado = _doc(_sdt("BLOCO:A", _p("não deveria sobreviver ao unwrap")))
    divs = fi.verificar_sdts_bloco(gerado, CATALOGO_SIMPLES, {"A": "INCLUIR"})
    assert divs and "BLOCO:A" in divs[0]


def test_verificar_sdts_bloco_aprova_ausencia_total():
    gerado = _doc(_p("conteúdo qualquer, sem SDT nenhum"))
    assert fi.verificar_sdts_bloco(gerado, CATALOGO_SIMPLES, {"A": "EXCLUIR"}) == []


def test_escanear_tokens_residuais_detecta_placeholder_nao_substituido():
    assert fi.escanear_tokens_residuais(_doc(_p("{{RESIDUAL}}"))) == ["RESIDUAL"]
    assert fi.escanear_tokens_residuais(_doc(_p("tudo substituído"))) == []


def test_round_trip_recupera_valor_isolado_multiline():
    template = _doc(_p("Título."), _p("{{VALOR}}"), _p("Rodapé."))
    estados = {}
    dados = {"VALOR": "Linha um.\nLinha dois."}
    _, gerado = _render_sintetico(template, estados, dados, catalogo=CATALOGO_VAZIO)
    extraido = rt.extrair_valores_gerados(template, gerado, CATALOGO_VAZIO, estados, {}, nomes=["VALOR"])
    assert extraido["VALOR"] == "Linha um.\nLinha dois."
    assert rt.comparar_round_trip(dados, extraido, {"VALOR"}) == []


def test_round_trip_recupera_valor_embutido_em_texto_fixo():
    template = _doc(_p("Prefixo fixo, {{VALOR}}, sufixo fixo."))
    estados = {}
    dados = {"VALOR": "meio gerado"}
    _, gerado = _render_sintetico(template, estados, dados, catalogo=CATALOGO_VAZIO)
    extraido = rt.extrair_valores_gerados(template, gerado, CATALOGO_VAZIO, estados, {}, nomes=["VALOR"])
    assert extraido["VALOR"] == "meio gerado"


def test_round_trip_placeholder_de_bloco_excluido_e_inalcancavel():
    template = _doc(_sdt("BLOCO:A", _p("{{VALOR_A}}")))
    estados = {"A": "EXCLUIR"}
    ctx = ce.extrair_contexto(template, CATALOGO_SIMPLES)
    assert ctx["VALOR_A"][0]["bloco"] == "A"
    composto, _ = be.compor_xml(template, CATALOGO_SIMPLES, estados)
    extraido = rt.extrair_valores_gerados(template, composto, CATALOGO_SIMPLES, estados, {}, nomes=["VALOR_A"])
    assert extraido["VALOR_A"] is None
    divs = rt.comparar_round_trip({"VALOR_A": "não deveria aparecer"}, extraido, alcancaveis=set())
    assert divs == []  # inalcançável e ausente = esperado, não divergência
    divs_fantasma = rt.comparar_round_trip({"VALOR_A": "x"}, {"VALOR_A": "vazou mesmo excluído"}, alcancaveis=set())
    assert divs_fantasma and "INALCANÇÁVEL" in divs_fantasma[0]


def test_round_trip_detecta_conteudo_divergente():
    template = _doc(_p("{{VALOR}}"))
    estados = {}
    _, gerado = _render_sintetico(template, estados, {"VALOR": "texto correto"}, catalogo=CATALOGO_VAZIO)
    extraido = rt.extrair_valores_gerados(template, gerado, CATALOGO_VAZIO, estados, {}, nomes=["VALOR"])
    divs = rt.comparar_round_trip({"VALOR": "texto ESPERADO diferente"}, extraido, {"VALOR"})
    assert divs and "divergente" in divs[0]


def test_normalizacao_de_linha_em_branco_e_documentada_e_aplicada():
    """Mesma regra de `validate_paragrafos.paragrafos`: "\\n\\n" e "\\n"
    entre as mesmas duas linhas de conteúdo são equivalentes."""
    assert rt._paragrafos_visiveis_normalizados("a.\n\nb.") == rt._paragrafos_visiveis_normalizados("a.\nb.")


def test_normalizacao_de_negrito_pre_existente_e_escopada_ao_placeholder_verificado():
    """Normalização documentada #4: só se aplica ao(s) nome(s) verificados
    em `PLACEHOLDERS_COM_CARREGADOR_JA_NEGRITO` — nunca um "ignorar
    negrito sempre" genérico, que mascararia negrito incorreto em
    qualquer outro campo."""
    assert "IRREGULARIDADE_ENCONTRADA" in rt.PLACEHOLDERS_COM_CARREGADOR_JA_NEGRITO
    divs = rt.comparar_round_trip(
        {"IRREGULARIDADE_ENCONTRADA": "ligação direta", "OUTRO_CAMPO": "texto sem negrito"},
        {"IRREGULARIDADE_ENCONTRADA": "**ligação direta**", "OUTRO_CAMPO": "**texto sem negrito**"},
        {"IRREGULARIDADE_ENCONTRADA", "OUTRO_CAMPO"})
    # o campo normalizado passa; um negrito inesperado em outro campo continua reprovando
    assert not any("IRREGULARIDADE_ENCONTRADA" in d for d in divs)
    assert any("OUTRO_CAMPO" in d for d in divs)


def test_fragmento_inline_linked_preservado_quando_incluido_e_removido_quando_excluido():
    """`decision_mode="linked"` (ex. INLINE_COM_RECONVENCAO): um SDT que
    embrulha só ALGUMAS runs no MEIO de um parágrafo de texto fixo, nunca
    o parágrafo inteiro — a fidelidade precisa acompanhar os dois estados
    sem falso positivo em nenhum dos dois."""
    catalogo_linked = {"blocks": [
        {"id": "L", "tag": "INLINE:L", "tipo": "CONDICIONAL_PADRAO", "parent": None, "children": [],
         "decision_mode": "linked", "placeholders": [], "dependencies": [], "cardinality": "ONE"},
    ], "zones": []}
    template = _doc(f'<w:p><w:r><w:t>Prefixo fixo</w:t></w:r>{_sdt("INLINE:L", "<w:r><w:t> COM FRAGMENTO</w:t></w:r>")}'
                     f'<w:r><w:t>, sufixo fixo.</w:t></w:r></w:p>')
    for estado_l, esperado in (("INCLUIR", "Prefixo fixo COM FRAGMENTO, sufixo fixo."),
                               ("EXCLUIR", "Prefixo fixo, sufixo fixo.")):
        estados = {"L": estado_l}
        composto, _ = be.compor_xml(template, catalogo_linked, estados)
        divs = fi.verificar_sequencia_locked(template, composto, catalogo_linked, estados, {})
        assert divs == [], (estado_l, divs)
        texto_gerado = "".join(t.text or "" for t in LET.fromstring(composto.encode("utf-8")).iter(f"{{{W}}}t"))
        assert texto_gerado == esperado, (estado_l, texto_gerado)


# =================================================== §3: placeholder populado não implica bloco incluído

def test_placeholder_populado_nao_implica_bloco_incluido():
    """Gate 6.6-A §3 — a presença de valor em `dados` para um placeholder
    de bloco EXCLUÍDO nunca faz o bloco aparecer: `dados` nunca é
    consultado por `compor_xml`, só pelas etapas posteriores
    (substituição), que só tocam o que SOBROU depois da composição."""
    template = _doc(_sdt("BLOCO:A", _p("Título condicional.") + _p("{{VALOR_A}}")),
                     _p("Texto sempre visível."))
    estados = {"A": "EXCLUIR"}
    composto, resultado = be.compor_xml(template, CATALOGO_SIMPLES, estados)
    assert resultado["excluidos"] == ["A"]
    assert "{{VALOR_A}}" not in composto
    assert "Título condicional." not in composto
    # mesmo fornecendo dado para o placeholder do bloco excluído, a
    # validação de placeholders não o exige nem gera resíduo
    import docx_template_engine as te
    schema = {"editable_placeholders": ["VALOR_A"]}
    validacao = te.validar_placeholders(composto, {"VALOR_A": "valor fornecido mas inalcançável"}, schema)
    assert validacao["ok"], validacao["erros"]
    gerado, substituidos = te.substituir_placeholders(composto, {"VALOR_A": "valor fornecido mas inalcançável"})
    assert "VALOR_A" not in substituidos
    assert "valor fornecido mas inalcançável" not in gerado


# =============================================================== modo produção-final

def test_producao_final_rejeita_sentinela_pendente():
    dados = {"TEMPESTIVIDADE_CASO": "[PENDENTE: sem dados suficientes]"}
    erros = vs.validar_modo_producao_final(dados, {})
    assert any("[PENDENTE:" in e for e in erros)


def test_producao_final_rejeita_sentinela_sintetico_de_aceite():
    dados = {"AUTOR": "CONSUMIDOR SINTÉTICO DE ACEITE"}
    erros = vs.validar_modo_producao_final(dados, {})
    assert any("SINTÉTICO DE ACEITE" in e for e in erros)


def test_producao_final_nao_rejeita_marcador_manual_legitimo():
    """Diferente da sentinela de aceite: o marcador de pós-edição manual
    (schema.json, campos MARCADOR_MANUAL) é o valor de PRODUÇÃO legítimo,
    nunca uma sentinela."""
    dados = {"FOTOS_DA_IRREGULARIADE": "[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"}
    erros = vs.validar_modo_producao_final(dados, {})
    assert not any("FOTOS_DA_IRREGULARIADE" in e for e in erros)


def test_producao_final_exige_placeholder_sempre_visivel():
    erros = vs.validar_modo_producao_final({}, {})
    for nome in vs.PLACEHOLDERS_SEMPRE_VISIVEIS:
        assert any(nome in e for e in erros), nome


def test_producao_final_so_exige_placeholder_de_bloco_quando_bloco_ativo():
    base = {n: "x" for n in vs.PLACEHOLDERS_SEMPRE_VISIVEIS}
    # bloco EXCLUIR: nenhum dos placeholders donos dele é exigido
    erros_excluido = vs.validar_modo_producao_final(base, {"RECONVENCAO": "EXCLUIR"})
    assert not any("VALOR_FRA" in e for e in erros_excluido)
    # bloco INCLUIR: o placeholder dono passa a ser exigido
    erros_incluido = vs.validar_modo_producao_final(base, {"RECONVENCAO": "INCLUIR"})
    assert any("VALOR_FRA" in e for e in erros_incluido)


def test_producao_final_aprova_conjunto_completo_e_valido():
    dados = {n: "valor de produção legítimo" for n in vs.PLACEHOLDERS_SEMPRE_VISIVEIS}
    dados["FOTOS_DA_IRREGULARIADE"] = "[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"
    assert vs.validar_modo_producao_final(dados, {}) == []


# =========================================== negativo: decisão humana/estrategista ausente

def test_bloco_ativo_sem_decisao_estrategista_continua_fail_closed():
    """Regressão do comportamento já existente (não duplicado aqui): a
    ausência de decisão para um bloco `estrategista`/`humano` aborta ANTES
    de `validar_modo_producao_final` sequer ser chamado."""
    with pytest.raises(be.ComposicaoAbortada) as exc:
        be.validar_e_resolver_decisoes(CATALOGO_SIMPLES, {}, {})
    assert exc.value.stage == "decisao_ausente"


# ===================================================================== docx_real

@pytest.mark.docx_real
def test_real_render_valido_passa_fidelidade_e_round_trip_completos():
    """Fixture de regressão já aprovada (mesma de
    `test_docx_block_engine.py::test_pipeline_completo_com_blocos_contra_
    template_real`) — não os valores de aceite do Gate 6.6-A, que ficaram
    bloqueados por falha de validador própria (reportada à parte, nunca
    contornada aqui)."""
    _pular_se_sem_template_real()
    catalogo = be.carregar_catalogo(CATALOGO_REAL)
    be.validar_catalogo(catalogo)

    dados = {
        "JUIZO": "AO JUÍZO DA 1ª VARA CÍVEL DA COMARCA DE SALVADOR/BA (DADOS FICTÍCIOS DE TESTE)",
        "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000",
        "AUTOR": "FULANO DE TAL (DADOS FICTÍCIOS DE TESTE)",
        "TEMPESTIVIDADE_CASO": "Tempestiva, conforme certidão de intimação.",
        "SINOPSE_FATOS": "Síntese fictícia dos fatos, apenas para teste automatizado.\n\n"
                         "Segunda linha fictícia da sínopse.",
        "REALIDADE_FATICA": "Linha fictícia da realidade fática.",
        "IRREGULARIDADE_ENCONTRADA": "**ligação direta (dado fictício de teste)**",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Desenvolvimento técnico fictício de teste.",
        "FOTOS_DA_IRREGULARIADE": "(nenhuma foto anexada, dado fictício de teste)",
        "VALOR_FRA": "R$ 0,00 (dado fictício de teste)",
        "VALOR_DANO_MORAL_PRETENDIDO": "R$ 0,00 (dado fictício de teste)",
        "PEDIDOS_FINAIS": "a) pedido fictício de teste.",
        "LOCAL_DATA": "Salvador, 1º de janeiro de 2026 (dado fictício de teste)",
        "SINOPSE_FATOS_NUCLEO_OBJETO": "Objeto fictício de teste (dado fictício de teste).",
        "CONTA_CONTRATO": "0000000000",
        "NOME_TITULAR_DA_UC": "FULANO DE TAL (TITULAR FICTÍCIO)",
        "TELAS_DA_TITULARIDADE": "(nenhuma tela anexada, dado fictício de teste)",
        "VALOR_DA_CAUSA": "R$ 100,00 (dado fictício de teste)",
        "VALOR_TOTAL_PROVEITO_ECONOMICO": "R$ 100,00 (dado fictício de teste)",
    }
    decisoes = {b["id"]: {"decisao": "INCLUIR"}
                for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    fatos = {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True}

    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "regressao-6-6-a.docx"
        r = be.gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL, dados, decisoes, saida,
                                      fatos_processuais=fatos)
        assert r["status"] == "OK", r
        assert r["template_lock"] == "OK"

        estados = be.validar_e_resolver_decisoes(catalogo, decisoes, fatos)
        estados_zonas = be.resolver_estados_zonas(catalogo, estados, None, fatos)

        with tempfile.TemporaryDirectory() as tmp2:
            extrair_pacote_docx(TEMPLATE_REAL, Path(tmp2) / "t")
            template_xml = (Path(tmp2) / "t" / "word" / "document.xml").read_text(encoding="utf-8")
            extrair_pacote_docx(saida, Path(tmp2) / "g")
            gerado_xml = (Path(tmp2) / "g" / "word" / "document.xml").read_text(encoding="utf-8")

        divs_seq = fi.verificar_sequencia_locked(template_xml, gerado_xml, catalogo, estados, estados_zonas)
        assert divs_seq == [], divs_seq
        assert fi.verificar_sdts_bloco(gerado_xml, catalogo, estados) == []
        assert fi.escanear_tokens_residuais(gerado_xml) == []

        ctx = ce.extrair_contexto(template_xml, catalogo)
        extraido = rt.extrair_valores_gerados(template_xml, gerado_xml, catalogo, estados, estados_zonas,
                                               nomes=list(dados))
        alcancaveis = set(vs.PLACEHOLDERS_SEMPRE_VISIVEIS) | {
            nome for nome, bloco in vs.PLACEHOLDER_BLOCO_DONO.items() if estados.get(bloco) == "INCLUIR"
        }
        divs_rt = rt.comparar_round_trip(dados, extraido, alcancaveis)
        assert divs_rt == [], divs_rt


@pytest.mark.docx_real
def test_real_fidelidade_detecta_corrupcao_pos_render():
    """Prova negativa contra o Modelo Oficial real: um DOCX gerado
    corretamente e depois alterado por fora (texto fixo mexido) precisa
    reprovar na verificação independente — nunca passar por coincidência."""
    _pular_se_sem_template_real()
    catalogo = be.carregar_catalogo(CATALOGO_REAL)
    dados = {
        "JUIZO": "x", "NUMERO_PROCESSO": "0000000-00.0000.0.00.0000", "AUTOR": "x",
        "TEMPESTIVIDADE_CASO": "x", "SINOPSE_FATOS": "x", "REALIDADE_FATICA": "x",
        "IRREGULARIDADE_ENCONTRADA": "x", "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "x",
        "FOTOS_DA_IRREGULARIADE": "x", "VALOR_FRA": "x", "VALOR_DANO_MORAL_PRETENDIDO": "x",
        "PEDIDOS_FINAIS": "x", "LOCAL_DATA": "x", "SINOPSE_FATOS_NUCLEO_OBJETO": "x",
        "CONTA_CONTRATO": "x", "NOME_TITULAR_DA_UC": "x", "TELAS_DA_TITULARIDADE": "x",
        "VALOR_DA_CAUSA": "x", "VALOR_TOTAL_PROVEITO_ECONOMICO": "x",
    }
    # decisões "tudo incluído" (mesmo cenário já provado equivalente ao
    # template em `test_real_render_valido_passa_fidelidade_e_round_trip_
    # completos`) — deliberadamente NÃO exercita a troca de frase vinculada
    # RECONVENCAO/INLINE_COM_RECONVENCAO (decision_mode "linked", par
    # MC_PAIR): esse mecanismo já tem suíte própria em
    # `test_docx_block_engine.py`/`test_docx_numeracao_engine.py`, e
    # `verificar_sequencia_locked` não tenta reproduzi-lo (duplicaria a
    # lógica que este módulo existe para não competir).
    decisoes = {b["id"]: {"decisao": "INCLUIR"}
                for b in catalogo["blocks"] if b["decision_mode"] in ("estrategista", "humano")}
    fatos = {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True}
    estados = be.validar_e_resolver_decisoes(catalogo, decisoes, fatos)
    estados_zonas = be.resolver_estados_zonas(catalogo, estados, None, fatos)

    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "corrupcao.docx"
        r = be.gerar_peca_com_blocos(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL, dados, decisoes, saida,
                                      fatos_processuais=fatos)
        assert r["status"] == "OK", r
        with tempfile.TemporaryDirectory() as tmp2:
            extrair_pacote_docx(TEMPLATE_REAL, Path(tmp2) / "t")
            template_xml = (Path(tmp2) / "t" / "word" / "document.xml").read_text(encoding="utf-8")
            extrair_pacote_docx(saida, Path(tmp2) / "g")
            gerado_xml = (Path(tmp2) / "g" / "word" / "document.xml").read_text(encoding="utf-8")

        assert fi.verificar_sequencia_locked(template_xml, gerado_xml, catalogo, estados, estados_zonas) == []

        # corrompe um trecho de texto FIXO institucional (fora de qualquer
        # placeholder) e prova que a verificação independente reprova
        root = LET.fromstring(gerado_xml.encode("utf-8"))
        alvo = None
        for t in root.iter(f"{{{W}}}t"):
            p = fi._paragrafo_mais_proximo(t)
            r = t.getparent()
            rpr = r.find(f"{{{W}}}rPr") if r is not None else None
            gerado_por_placeholder = rpr is not None and fi._RE_COR_GERADA.search(
                LET.tostring(rpr, encoding="unicode"))
            if (t.text and len(t.text.strip()) > 20 and "x" not in t.text
                    and not gerado_por_placeholder
                    and not fi._dentro_de_fallback(t) and p is not None
                    and not fi._dentro_de_fallback(p)):
                alvo = t
                break
        assert alvo is not None, "nenhum <w:t> fixo candidato encontrado para o teste"
        alvo.text = "TEXTO INSTITUCIONAL ALTERADO SEM AUTORIZAÇÃO PELO TESTE"
        gerado_corrompido = LET.tostring(root, encoding="unicode")

        divs = fi.verificar_sequencia_locked(template_xml, gerado_corrompido, catalogo, estados, estados_zonas)
        assert divs, "a corrupção de texto fixo deveria ter sido detectada"
