"""
Gate de qualidade de conteúdo (10/10/2026, manifesto V1 1.4.0) — feedback
de advogado após uso real pelo ChatGPT: SINOPSE resumida demais,
desenvolvimento técnico raso e necessidade de fidelidade ao comando atual.

A-D: calibração de SINOPSE_FATOS, DESENVOLVIMENTO_TECNICO_IRREGULARIDADE e
     do contrato atômico de IRREGULARIDADE_ENCONTRADA.
E:   tópico NÃO não reaparece em nenhuma parte variável (validação que
     antes só existia, para PEDIDOS_FINAIS, no fluxo local).
F-G: orientações do advogado verificáveis (NAO_MENCIONAR,
     TRATAR_APENAS_COMO_FATO) e as que o Core recusa.
H:   conteúdo obviamente sintético de fixture recusado em produção-final.
Host Contract 1.4.0 e caminho MCP de ponta a ponta.

Todo texto abaixo é fictício (nenhum dado real de cliente).
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "mcp_server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fidelidade_comando as fc  # noqa: E402
import finalizar_peca as fp  # noqa: E402
import validate_paragrafos as vp  # noqa: E402
import validate_placeholder_semantics as vs  # noqa: E402
import test_topic_matrix_v1 as T  # noqa: E402
from test_topic_matrix_v1 import ambiente_v1, modelo_v1_local  # noqa: E402,F401
import test_compatibilidade_host_mcp as H  # noqa: E402
from test_compatibilidade_host_mcp import ambiente  # noqa: E402,F401

SCHEMA = json.loads((BASE / "templates" / "contestacao" / "schema.json").read_text(encoding="utf-8"))

# Seis elementos do roteiro de cobertura, um por parágrafo, na voz da autora.
SINOPSE_COMPLETA = "\n".join([
    "A parte autora afirma ser titular da unidade consumidora residencial atendida pela ré, com fornecimento "
    "regular e faturas quitadas em dia ao longo de vários anos de relação contratual.",
    "Narra que, em março de 2026, prepostos da ré compareceram ao imóvel sem aviso prévio, examinaram o "
    "medidor e lavraram termo de ocorrência, sem lhe explicar o motivo da visita.",
    "Relata que, semanas depois, recebeu fatura de recuperação de consumo referente a período pretérito, "
    "emitida a partir daquela inspeção e lançada junto com o consumo do mês.",
    "Sustenta que a cobrança, de R$ 2.097,63, decorreria de suposto desvio de energia que nega ter praticado, "
    "e que o valor seria desproporcional ao seu histórico de consumo.",
    "Afirma que a cobrança lhe causou angústia, que teve receio de ficar sem energia e que precisou procurar "
    "atendimento presencial diversas vezes sem solução administrativa.",
    "Requer a declaração de inexistência do débito, a abstenção de qualquer suspensão do fornecimento e a "
    "condenação da ré ao pagamento de indenização por danos morais de R$ 12.900,00.",
])

DESENVOLVIMENTO_COMPLETO = "\n".join([
    "Na inspeção de 12/03/2026, registrada no TOI nº 000123, a equipe técnica constatou derivação de condutor "
    "conectada ao ramal de entrada antes do medidor, alimentando parte das cargas do imóvel.",
    "A ligação era feita por condutor de seção inferior ao padrão, emendado no ramal e embutido na parede, o "
    "que permitia o uso de energia sem passagem pelo equipamento de medição.",
    "O ponto atingido foi o ramal de entrada, no trecho entre a rede e a caixa de medição, área sob "
    "responsabilidade da unidade consumidora, conforme o croqui anexado ao TOI.",
    "Com o desvio, parte da energia consumida não era registrada pelo medidor, o que explica a queda abrupta "
    "do consumo faturado a partir de outubro de 2025, visível no histórico da unidade.",
    "A equipe retirou a derivação no próprio ato e normalizou a ligação, com registro fotográfico antes e "
    "depois da intervenção e lacração da caixa de medição.",
    "Após a normalização, o consumo médio da unidade voltou ao patamar anterior, o que confirma a influência "
    "do desvio sobre os registros do período irregular.",
    "A recuperação abrangeu o período apurado no memorial de cálculo, com o critério regulamentar ali "
    "indicado e o valor final de R$ 2.097,63, detalhados no tópico próprio da metodologia.",
])


def _limites(nome):
    return vp.LIMITES_DENSIDADE_BLOCO[nome]


# ======================================================== A-C: calibração

def test_A_sinopse_com_os_seis_elementos_passa_sem_compressao():
    paras = vp.paragrafos(SINOPSE_COMPLETA)
    assert len(paras) == 6
    total = sum(len(p) for p in paras)
    assert 600 < total <= _limites("SINOPSE_FATOS")["max_total_chars"]  # o teto antigo (600) a comprimiria
    assert vp.validar_densidade_blocos({"SINOPSE_FATOS": SINOPSE_COMPLETA}) == (True, [])
    assert vp.validar_paragrafos_placeholders({"SINOPSE_FATOS": SINOPSE_COMPLETA}, SCHEMA) == (True, [])
    assert vs.validar_semantica({"SINOPSE_FATOS": SINOPSE_COMPLETA}) == (True, [])


def test_A_limites_novos_sao_teto():
    assert _limites("SINOPSE_FATOS") == {"max_paragrafos": 6, "max_total_chars": 1800}
    assert _limites("DESENVOLVIMENTO_TECNICO_IRREGULARIDADE") == {"max_paragrafos": 8, "max_total_chars": 2400}
    sete = SINOPSE_COMPLETA + "\nA autora junta fotografias do imóvel e cópia das faturas do período."
    ok, erros = vp.validar_densidade_blocos({"SINOPSE_FATOS": sete})
    assert not ok and "7 parágrafos" in erros[0]


def test_B_sinopse_sem_um_elemento_nao_exige_invencao():
    """Sem mínimo: elemento sem suporte documental é omitido e nada falta."""
    sem_consequencias = "\n".join(p for i, p in enumerate(vp.paragrafos(SINOPSE_COMPLETA)) if i != 4)
    for texto in (sem_consequencias, vp.paragrafos(SINOPSE_COMPLETA)[1]):
        assert vp.validar_densidade_blocos({"SINOPSE_FATOS": texto}) == (True, [])
        assert vs.validar_semantica({"SINOPSE_FATOS": texto}) == (True, [])


def test_C_desenvolvimento_substancial_cabe_no_novo_teto():
    paras = vp.paragrafos(DESENVOLVIMENTO_COMPLETO)
    total = sum(len(p) for p in paras)
    assert len(paras) == 7 and 700 < total <= 2400  # o teto antigo (700) o barraria
    dados = {"DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": DESENVOLVIMENTO_COMPLETO}
    assert vp.validar_densidade_blocos(dados) == (True, [])
    assert vp.validar_paragrafos_placeholders(dados, SCHEMA) == (True, [])
    assert vs.validar_semantica(dados) == (True, [])
    longo = DESENVOLVIMENTO_COMPLETO + "\n" + "\n".join(["Parágrafo adicional de detalhamento técnico." * 4] * 2)
    assert not vp.validar_densidade_blocos({"DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": longo})[0]


# ============================================== D: irregularidade atômica

@pytest.mark.parametrize("valor", ["desvio de energia antes do medidor", "**desvio de energia antes do medidor**",
                                   "ligação direta na rede de baixa tensão (BT)"])
def test_D_irregularidade_em_uma_linha_passa(valor):
    dados = {"IRREGULARIDADE_ENCONTRADA": valor}
    assert vs.validar_semantica(dados) == (True, [])
    assert vp.validar_densidade_blocos(dados) == (True, [])


def test_D_irregularidade_multilinha_e_recusada():
    valor = "desvio de energia antes do medidor\nderivação no ramal de entrada"
    ok, erros = vs.validar_semantica({"IRREGULARIDADE_ENCONTRADA": valor})
    assert not ok and any("uma única linha" in e for e in erros)


def test_D_irregularidade_com_explicacao_longa_e_recusada():
    valor = ("desvio de energia antes do medidor, mediante derivação de condutor no ramal de entrada que "
             "alimentava parte das cargas do imóvel sem registro")
    ok, erros = vs.validar_semantica({"IRREGULARIDADE_ENCONTRADA": valor})
    assert not ok and any("máximo 120" in e for e in erros)


def test_D_schema_publica_irregularidade_como_campo_de_uma_linha():
    contrato = SCHEMA["placeholder_contracts"]["IRREGULARIDADE_ENCONTRADA"]
    assert contrato["multiline"] is False
    desenvolvimento = SCHEMA["placeholder_contracts"]["DESENVOLVIMENTO_TECNICO_IRREGULARIDADE"]["descricao"]
    assert "artigo-por-artigo" not in desenvolvimento and "nunca exposição artigo por artigo" in desenvolvimento


# ============================================ E: tópico NÃO não reaparece

EXCLUIDOS = {b: "EXCLUIR" for b in fc.be.PALAVRAS_CHAVE_BLOCO_PEDIDOS}
PARTES_NARRATIVAS = ("SINOPSE_FATOS", "REALIDADE_FATICA", "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE",
                     "PEDIDOS_FINAIS", "ZONA_METODOLOGIA_APURACAO")


@pytest.mark.parametrize("parte", PARTES_NARRATIVAS)
@pytest.mark.parametrize("bloco,trecho", [
    ("PRELIMINAR_CDC_INAPLICAVEL", "Impõe-se a inaplicabilidade do CDC à relação."),
    ("PRELIMINAR_REVOGACAO_GRATUIDADE", "Cabe a revogação da gratuidade concedida."),
    ("RECONVENCAO", "O débito é objeto de reconvenção."),
    ("LICITUDE_CORTE_SUSPENSAO", "Demonstra-se a licitude do corte realizado."),
])
def test_E_topico_nao_em_qualquer_parte_variavel_e_violacao(parte, bloco, trecho):
    violacoes = fc.verificar_coerencia_topicos({parte: trecho}, {bloco: "EXCLUIR"}, T.MANIFESTO)
    assert len(violacoes) == 1 and violacoes[0]["parte"] == parte
    assert violacoes[0]["regra"] == "TOPICO_EXCLUIDO" and parte in violacoes[0]["detalhe"]


@pytest.mark.parametrize("parte", PARTES_NARRATIVAS)
def test_E_topico_sim_pode_ser_mencionado(parte):
    trecho = "Demonstra-se a licitude do corte realizado."
    assert fc.verificar_coerencia_topicos({parte: trecho}, {"LICITUDE_CORTE_SUSPENSAO": "INCLUIR"}) == []


@pytest.mark.parametrize("parte,texto", [
    # Alegação da autora: "ilicitude" nunca casa com "licitude" (palavra inteira).
    ("SINOPSE_FATOS", "A autora sustenta a ilicitude do corte e pede o restabelecimento."),
    # Expressão ambígua só vale em PEDIDOS_FINAIS: na narrativa, é a autora contestando.
    ("SINOPSE_FATOS", "A autora questiona a regularidade do corte do fornecimento."),
    # Menção ao fato, sem tese.
    ("REALIDADE_FATICA", "O fornecimento foi suspenso em 10/03/2026 e restabelecido no dia seguinte."),
    ("REALIDADE_FATICA", "A autora é consumidora residencial e a relação é de consumo."),
    ("DESENVOLVIMENTO_TECNICO_IRREGULARIDADE", "A gratuidade de justiça foi requerida na inicial."),
])
def test_E_negativas_e_citacoes_contextuais_nao_sao_falso_positivo(parte, texto):
    assert fc.verificar_coerencia_topicos({parte: texto}, EXCLUIDOS) == []


def test_E_pedidos_finais_mantem_a_regra_existente_inclusive_ambigua():
    violacoes = fc.verificar_coerencia_topicos(
        {"PEDIDOS_FINAIS": "Requer seja reconhecida a regularidade do corte."},
        {"LICITUDE_CORTE_SUSPENSAO": "EXCLUIR"})
    assert len(violacoes) == 1


def test_E_decisao_do_advogado_aplicada_na_composicao():
    topicos = {"inaplicabilidade_cdc": "SIM", "reconvencao_cobranca_debito": "NAO"}
    ok = {"PRELIMINAR_CDC_INAPLICAVEL": "INCLUIR", "RECONVENCAO": "EXCLUIR"}
    assert fc.verificar_decisoes_aplicadas(T.MANIFESTO, topicos, ok) == []
    divergente = {"PRELIMINAR_CDC_INAPLICAVEL": "EXCLUIR", "RECONVENCAO": "INCLUIR"}
    assert len(fc.verificar_decisoes_aplicadas(T.MANIFESTO, topicos, divergente)) == 2


# ===================================================== F-G: orientações

CALCULADOS = fc.partes_por_modo(T.MANIFESTO, "CALCULADO_PELO_CORE") | fp.DERIVADOS_ADR_0021


def _analisar(orientacoes, topicos=None):
    return fc.analisar_orientacoes(orientacoes, T.MANIFESTO, topicos or T._todos("NAO"), CALCULADOS)


def test_F_nao_mencionar_presente_e_recusado_com_a_parte_a_reescrever():
    a = _analisar([{"tipo": "NAO_MENCIONAR", "termos": ["negativação"]}])
    assert not a.rejeitadas and len(a.aceitas) == 1
    partes = {"SINOPSE_FATOS": "A autora diz ter sofrido NEGATIVACAO do nome.",
              "REALIDADE_FATICA": "Não houve inscrição em cadastro."}
    violacoes = fc.verificar_orientacoes(a.aceitas, partes)
    assert [v["parte"] for v in violacoes] == ["SINOPSE_FATOS"]
    assert violacoes[0]["regra"] == "NAO_MENCIONAR" and "negativação" in violacoes[0]["detalhe"]


def test_F_nao_mencionar_respeita_o_escopo_e_a_palavra_inteira():
    a = _analisar([{"tipo": "NAO_MENCIONAR", "termos": ["SPC"], "partes": ["REALIDADE_FATICA"]}])
    partes = {"SINOPSE_FATOS": "A autora menciona o SPC.", "REALIDADE_FATICA": "Os SPCs regionais não constam."}
    assert fc.verificar_orientacoes(a.aceitas, partes) == []


def test_F_nao_mencionar_termo_de_topico_sim_e_rejeitado():
    a = _analisar([{"tipo": "NAO_MENCIONAR", "termos": ["reconvenção"]}],
                  {**T._todos("NAO"), "reconvencao_cobranca_debito": "SIM"})
    assert a.rejeitadas[0]["motivo_codigo"] == "CONFLITA_TOPICO_SIM" and not a.aceitas


def test_G_tratar_corte_como_fato_recusa_qualificacao_juridica():
    a = _analisar([{"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "corte_suspensao"}])
    assert len(a.aceitas) == 1 and "SINOPSE_FATOS" not in a.aceitas[0]["partes"]
    violacoes = fc.verificar_orientacoes(a.aceitas, {
        "REALIDADE_FATICA": "O fornecimento foi suspenso em 10/03/2026, e o corte foi legítimo.",
        "SINOPSE_FATOS": "A autora questiona a regularidade do corte.",
    })
    assert [v["parte"] for v in violacoes] == ["REALIDADE_FATICA"]
    assert violacoes[0]["regra"] == "TRATAR_APENAS_COMO_FATO"


def test_G_tratar_corte_como_fato_admite_o_fato():
    a = _analisar([{"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "corte_suspensao"}])
    assert fc.verificar_orientacoes(a.aceitas, {
        "REALIDADE_FATICA": "O fornecimento foi suspenso em 10/03/2026 e restabelecido em 11/03/2026."}) == []


def test_G_tratar_como_fato_contra_topico_sim_e_rejeitado():
    a = _analisar([{"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "corte_suspensao"}],
                  {**T._todos("NAO"), "licitude_cobranca_corte": "SIM"})
    assert a.rejeitadas[0]["motivo_codigo"] == "CONFLITA_TOPICO_SIM"


@pytest.mark.parametrize("orientacao,codigo", [
    ({"tipo": "INCLUIR_TOPICO"}, "ALTERA_TOPICO"),
    ({"tipo": "EXCLUIR_TOPICO"}, "ALTERA_TOPICO"),
    ({"tipo": "ALTERAR_TEXTO_FIXO"}, "ALTERA_TEXTO_FIXO"),
    ({"tipo": "ALTERAR_CALCULO"}, "ALTERA_CALCULO"),
    ({"tipo": "ALTERAR_CAMPO_CALCULADO"}, "CAMPO_CALCULADO"),
    ({"tipo": "INCLUIR_FATO"}, "INTRODUZ_FATO"),
    ({"tipo": "QUALQUER_OUTRO"}, "TIPO_NAO_SUPORTADO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["x"]}, "TERMO_INVALIDO"),
    ({"tipo": "NAO_MENCIONAR"}, "TERMO_INVALIDO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["corte"], "partes": ["TEMPESTIVIDADE_CASO"]}, "CAMPO_CALCULADO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["corte"], "partes": ["ZONA_COMPOSICAO_PROVEITO_ECONOMICO"]},
     "CAMPO_CALCULADO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["corte"], "partes": ["AUTOR"]}, "PARTE_FORA_DO_ESCOPO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["corte"], "partes": ["texto_fixo_generico"]}, "PARTE_FORA_DO_ESCOPO"),
    ({"tipo": "NAO_MENCIONAR", "termos": ["corte"], "fato": "a autora confessou"}, "FORMA_INVALIDA"),
    ({"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "negativacao"}, "CONCEITO_NAO_SUPORTADO"),
])
def test_orientacao_que_alteraria_o_contrato_e_rejeitada(orientacao, codigo):
    a = _analisar([orientacao])
    assert [r["motivo_codigo"] for r in a.rejeitadas] == [codigo] and not a.aceitas


def test_enfatizar_e_so_redacao_nunca_bloqueia():
    a = _analisar([{"tipo": "ENFATIZAR"}, {"tipo": "reforcar"}])
    assert not a.rejeitadas and not a.aceitas and [x["tipo"] for x in a.nao_verificadas] == ["ENFATIZAR", "REFORCAR"]


# ================================================= H: fixtures sintéticas

@pytest.mark.parametrize("valor", ["FULANO DE TAL", "Ciclano de Tal", "Maria (dado fictício de teste)",
                                   "R$ 1,00 (DADOS FICTÍCIOS DE TESTE)", "0000000-00.0000.0.00.0000"])
def test_H_marcador_sintetico_e_recusado_em_producao_final(valor):
    erros = vs.validar_modo_producao_final({"AUTOR": valor}, {})
    assert any("sentinela de modo ACEITE" in e for e in erros)


@pytest.mark.parametrize("valor", ["MARIA DE TAL VAZ", "JOSÉ FULANO DOS SANTOS", "Talita de Tal Ferreira",
                                   "0000123-45.2026.8.05.0001", "dado de teste do medidor"])
def test_H_nomes_e_expressoes_legitimos_nao_sao_bloqueados(valor):
    assert vs.sentinelas_fixture_presentes(valor) == []


# ============================================ Host Contract 1.4.0 (MCP)

def _pacote():
    import preparar_contestacao
    r = preparar_contestacao.preparar_contexto_contestacao({"fatos": H.FATOS_SINTETICOS})
    assert r.status == "OK", r
    return r.pacote


def test_host_contract_publica_roteiro_limites_e_orientacoes(ambiente):
    tmx = _pacote()["topic_matrix"]
    partes = {p["parte"]: p for p in tmx["partes_redigiveis_llm"]}
    sinopse, desenv = partes["SINOPSE_FATOS"], partes["DESENVOLVIMENTO_TECNICO_IRREGULARIDADE"]
    assert len(sinopse["roteiro_cobertura"]) == 6 and len(desenv["roteiro_cobertura"]) == 8
    assert "Nunca invente" in sinopse["regra_cobertura"] and "ZONA_METODOLOGIA_APURACAO" in desenv["regra_cobertura"]
    assert sinopse["limites"]["max_paragrafos"] == 6 and sinopse["limites"]["max_caracteres_total"] == 1800
    assert desenv["limites"]["max_paragrafos"] == 8 and desenv["limites"]["max_caracteres_total"] == 2400
    assert all("coerencia_topicos" in p["validacoes"] for p in partes.values())
    assert set(tmx["orientacoes_advogado"]["tipos_verificaveis"]) == set(fc.TIPOS_VERIFICAVEIS)
    assert list(tmx["orientacoes_advogado"]["conceitos_trataveis_como_fato"]) == ["corte_suspensao"]
    irreg = [d for t in tmx["topicos"] for d in t["dados_documentais_host"] if d["campo"] == "IRREGULARIDADE_ENCONTRADA"]
    irreg += [d for s in tmx["secoes_incondicionais_host"] for d in s["dados_documentais_host"]
              if d["campo"] == "IRREGULARIDADE_ENCONTRADA"]
    assert irreg and all(any("uma única linha" in r for r in d["restricoes"]) for d in irreg)
    assert "orientacoes_advogado" in tmx["orientacao"]


# ============================================== finalizador (pré-render)

def _entrada(placeholders=None, orientacoes=None, topicos=None, estado=None):
    topicos = topicos or T._todos("NAO")
    entrada = {"capability_id": T.CAP, "placeholders": {**T._placeholders(), **(placeholders or {})},
               "topicos": topicos, "fatos_publicos": {"corte_efetivo": "NAO"},
               "estado_processual": {**{f: True for f in T.FATOS_SUBBLOCOS.values()}, **(estado or {})},
               **T._extras(topicos)}
    if orientacoes is not None:
        entrada["orientacoes_advogado"] = orientacoes
    return entrada


def test_E_finalizador_recusa_topico_nao_reintroduzido_antes_do_render(ambiente_v1):
    r = fp.finalizar_peca(_entrada({"REALIDADE_FATICA": "A cobrança decorre de inspeção regular e a licitude do "
                                                        "corte é manifesta."}))
    assert (r.status, r.stage, r.error_code) == ("REFUSED", "fidelidade_comando", "INPUT_VALIDATION_FAILED")
    assert r.documento_bytes is None and r.violacoes_fidelidade[0]["parte"] == "REALIDADE_FATICA"


def test_F_finalizador_recusa_termo_vedado(ambiente_v1):
    r = fp.finalizar_peca(_entrada({"SINOPSE_FATOS": "A autora relata negativação do nome."},
                                   [{"tipo": "NAO_MENCIONAR", "termos": ["negativação"]}]))
    assert r.stage == "fidelidade_comando" and r.violacoes_fidelidade[0]["regra"] == "NAO_MENCIONAR"
    assert r.orientacoes_aplicadas[0]["termos"] == ["negativação"]


def test_orientacao_rejeitada_recusa_antes_de_calcular_qualquer_coisa(ambiente_v1, monkeypatch):
    monkeypatch.setattr(fp, "_derivar_juizo", lambda *a, **k: pytest.fail("DataJud não deveria ser consultado"))
    r = fp.finalizar_peca(_entrada(orientacoes=[{"tipo": "INCLUIR_TOPICO"}]))
    assert (r.status, r.stage) == ("REFUSED", "fidelidade_comando")
    assert r.orientacoes_rejeitadas[0]["motivo_codigo"] == "ALTERA_TOPICO"


def test_H_finalizador_recusa_fixture_sintetica(ambiente_v1):
    r = fp.finalizar_peca(_entrada({"AUTOR": "FULANO DE TAL"}))
    assert (r.status, r.error_code) == ("REFUSED", "SYNTHETIC_SENTINEL_REJECTED")


def test_adapter_mcp_serializa_violacoes_e_orientacoes(ambiente_v1):
    import server
    entrada = server.EdeFinalizarPecaEntrada(**_entrada(
        {"SINOPSE_FATOS": "A autora relata negativação do nome."},
        [{"tipo": "NAO_MENCIONAR", "termos": ["negativação"]}, {"tipo": "ENFATIZAR"}]))
    corpo = json.loads(server.ede_finalizar_peca(entrada)[0].text)
    assert corpo["status"] == "REFUSED" and corpo["stage"] == "fidelidade_comando"
    assert corpo["violacoes_fidelidade"][0] == {
        "parte": "SINOPSE_FATOS", "regra": "NAO_MENCIONAR",
        "detalhe": "Reescreva SINOPSE_FATOS sem mencionar 'negativação', conforme orientação do advogado."}
    assert corpo["orientacoes_nao_verificadas"][0]["tipo"] == "ENFATIZAR"


def test_adapter_mcp_recusa_orientacao_com_conteudo_no_perimetro():
    import server
    with pytest.raises(Exception):
        server.OrientacaoAdvogado(tipo="NAO_MENCIONAR", termos=["corte"], fato="a autora confessou")


# ================================================ ponta a ponta com DOCX

@pytest.mark.docx_real
def test_peca_completa_com_orientacao_aplicada_e_sem_rastro_no_docx(modelo_v1_local):
    termo = "inscrição em cadastro restritivo"
    r = fp.finalizar_peca(_entrada(
        {"SINOPSE_FATOS": SINOPSE_COMPLETA, "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": DESENVOLVIMENTO_COMPLETO,
         "IRREGULARIDADE_ENCONTRADA": "desvio de energia antes do medidor"},
        [{"tipo": "NAO_MENCIONAR", "termos": [termo]},
         {"tipo": "TRATAR_APENAS_COMO_FATO", "conceito": "corte_suspensao"}]))
    assert r.status == "OK", (r.stage, r.error_code, r.motivo, r.violacoes_fidelidade)
    assert [o["tipo"] for o in r.orientacoes_aplicadas] == ["NAO_MENCIONAR", "TRATAR_APENAS_COMO_FATO"]
    corpo = T._texto(T._xml(r.documento_bytes))
    for p in vp.paragrafos(SINOPSE_COMPLETA) + vp.paragrafos(DESENVOLVIMENTO_COMPLETO):
        assert p in corpo
    for rastro in (termo, "NAO_MENCIONAR", "TRATAR_APENAS_COMO_FATO", "corte_suspensao", "orientac"):
        assert rastro not in corpo


@pytest.mark.docx_real
def test_mesmo_comando_gera_os_mesmos_topicos(modelo_v1_local):
    """Critério black-box 1, aqui determinístico: mesmos documentos e
    mesmos comandos -> mesmo conjunto de blocos no DOCX."""
    topicos = {**T._todos("NAO"), "inaplicabilidade_cdc": "SIM", "descabimento_dano_moral": "SIM"}
    resultados = [fp.finalizar_peca(_entrada(topicos=topicos, estado={"PEDIDO_DANO_MORAL_NA_INICIAL": True}))
                  for _ in range(2)]
    assert all(r.status == "OK" for r in resultados), [(r.stage, r.motivo, r.pendencias) for r in resultados]
    corpos = [T._texto(T._xml(r.documento_bytes)) for r in resultados]
    assert corpos[0] == corpos[1]
    assert "utilizam a energia como insumo" in corpos[0]          # CDC SIM
    assert "COM RECONVENÇÃO" not in corpos[0].upper()              # Reconvenção NÃO
