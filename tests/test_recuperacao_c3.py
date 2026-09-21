# -*- coding: utf-8 -*-
"""
tests/test_recuperacao_c3.py — Gate 6.5-C3: precisão da recuperação jurídica e
profundidade de dispositivos (artigos) de `scripts/preparar_contestacao.py`.

Achados do Gate 6.5-C2 (produção, revisão ede-mcp-00016-yej), fixture exata
aprovada (SHA-256 canônico d9059ef3…292ef, tests/fixtures/
preparar_contestacao_gate_65c2.json):

  Q2 "Exigibilidade da cobrança de recuperação de consumo à luz da Resolução
  Normativa ANEEL nº 1.000/2021": os 5 primeiros eram capítulos do CPC sobre
  CUMPRIMENTO DE SENTENÇA. Causa medida: (a) título com IDF² dava 27,2 de
  bônus a UMA palavra rara ("exigibilidade") num título de ~10 termos; (b) a
  própria referência normativa ("000", "2021", "aneel", "normativa") era
  pontuada como conteúdo e favorecia Disposições Finais e Transitórias; (c)
  "luz" (de "à luz da") pesava como assunto (IDF 5,4).
  Q3: capítulos de setor ("Compra de energia", pré-pagamento) ocupavam as
  vagas depois do CDC_002.
  Profundidade: o excerto de 400 caracteres do TII_C07 (arts. 589-598)
  cobria só o art. 589.

Os testes NÃO dependem de uma frase literal: cada grupo usa paráfrases, e há
contraexemplos reais de CPC para provar que o sistema aprendeu CONTEXTO e não
uma lista negra.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import preparar_contestacao as pc  # noqa: E402

FIXTURE_PATH = BASE / "tests" / "fixtures" / "preparar_contestacao_gate_65c2.json"
FIXTURE_SHA256 = "d9059ef30d94d57db1b5060df2f997cd4ea6523bd1ac9f1129cdf3b6936292ef"
C07 = "REN1000/TII_C07.md"


def _canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@pytest.fixture(scope="module")
def fixture_aprovada():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["entrada"]


@pytest.fixture(scope="module")
def questoes(fixture_aprovada):
    return fixture_aprovada["questoes_juridicas"]


@pytest.fixture(scope="module")
def fontes(questoes):
    return pc._montar_fontes_legais(questoes)


def _top(questao, n=3):
    return [f"{c['diploma']}/{c['arquivo'].name}"
            for _, _, c, _ in pc._ranquear_candidatos(questao, pc.RAG_DIR_PADRAO)[:n]]


def _com_limite(questao, n):
    antigo = pc.MAX_FONTES_POR_QUESTAO
    pc.MAX_FONTES_POR_QUESTAO = n
    try:
        return pc._ranquear_candidatos(questao, pc.RAG_DIR_PADRAO)
    finally:
        pc.MAX_FONTES_POR_QUESTAO = antigo


# ------------------------------------------------------------- A: fixture

def test_A_fixture_exata_tem_o_sha_canonico_aprovado(fixture_aprovada):
    """A fixture de aceitação é a MESMA do Gate 6.5-C2 — nunca reconstruída."""
    assert hashlib.sha256(_canonico(fixture_aprovada).encode("utf-8")).hexdigest() == FIXTURE_SHA256
    assert len(fixture_aprovada["questoes_juridicas"]) == 5


# --------------------------------------------- B/C: Q2 contexto correto

def test_B_Q2_recupera_a_regulamentacao_da_ren1000_e_nao_o_cpc(questoes):
    top = _top(questoes[2])
    assert C07 in top, top
    assert all(i.startswith("REN1000/") for i in top), top


def test_C_Q2_nenhuma_fonte_do_cpc_no_pacote_para_a_questao(fontes):
    do_q2 = [f["source_id"] for f in fontes if 2 in f["questoes_relacionadas"]]
    assert do_q2 and not any(i.startswith("CPC/") for i in do_q2), do_q2


def test_C_Q2_causa_raiz_o_titulo_do_cpc_nao_pontua_mais_por_uma_palavra_rara(questoes):
    """O bônus de título do CPC que dominava o Q2 (27,2) fica agora abaixo
    de 1/4 do que era e muito abaixo do score de corpo do capítulo central."""
    consulta = pc._consulta(questoes[2])
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    termos = sorted(r for r in consulta["pesos"] if r in idf)
    cpc = next(c for c in pc._indice_corpus(pc.RAG_DIR_PADRAO)["chunks"]
               if c["arquivo"].name.startswith("Chunk_058_DO_CUMPRIMENTO_DEFINITIVO"))
    _, _, comp = pc._pontuar_chunk(cpc, consulta, idf, termos)
    assert "exigibil" in cpc["radicais_titulo"]
    assert comp["titulo"] < 27.2 / 4


# ------------------------------------------- referência normativa explícita

@pytest.mark.parametrize("texto", [
    "Exigibilidade à luz da Resolução Normativa ANEEL nº 1.000/2021",
    "conforme a REN ANEEL 1.000/2021",
    "nos termos da REN 1000",
    "Resolução Normativa nº 1.000/2021 da ANEEL",
    "Res. Normativa ANEEL n° 1.000/2021",
    "REN aneel 1000/2021",
])
def test_referencia_canonica_da_ren1000_e_reconhecida(texto):
    assert "REN1000" in pc._consulta(texto)["diplomas"]


def test_referencia_reconhece_outros_diplomas_do_corpus():
    assert "CDC" in pc._consulta("Aplicação do Código de Defesa do Consumidor")["diplomas"]
    assert "CPC" in pc._consulta("prazo previsto no CPC")["diplomas"]
    assert "CC" in pc._consulta("nos termos da Lei nº 10.406/2002")["diplomas"]


def test_referencia_numerica_sai_do_conteudo_e_nome_tematico_fica():
    pesos = pc._consulta("cobrança à luz da Resolução Normativa ANEEL nº 1.000/2021")["pesos"]
    for lixo in ("000", "2021", "normativ", "resolu", "luz"):
        assert lixo not in pesos, pesos
    # o NOME do CDC é assunto: "consumidor" continua contando
    assert pc._radical("consumidor") in pc._consulta("Código de Defesa do Consumidor")["pesos"]


def test_referencia_sozinha_nao_forca_nenhum_chunk():
    """Uma questão que só cita o diploma, sem conteúdo, não recupera nada:
    a referência explícita impulsiona, nunca inclui (Gate 6.5-C3 §7)."""
    assert pc._ranquear_candidatos("Resolução Normativa ANEEL nº 1.000/2021", pc.RAG_DIR_PADRAO) == []
    assert pc._ranquear_candidatos("REN 1000 zzqxvk wwqpl", pc.RAG_DIR_PADRAO) == []


def test_boost_de_diploma_nunca_cria_pontuacao_do_nada():
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    consulta = pc._consulta("Resolução Normativa ANEEL nº 1.000/2021 zzqxvk")
    chunk = {"diploma": "REN1000", "frequencias": {}, "radicais_titulo": set(), "bigramas": set()}
    total, _, comp = pc._pontuar_chunk(chunk, consulta, idf, [])
    assert total == 0 and comp["diploma_explicito"] is False


def test_boost_de_diploma_eleva_o_diploma_citado_mas_so_com_conteudo(questoes):
    consulta = pc._consulta(questoes[2])
    assert consulta["diplomas"] == frozenset({"REN1000"})
    ranking = _com_limite(questoes[2], 10)
    assert ranking and all(c[3]["diploma_explicito"] == (c[2]["diploma"] == "REN1000") for c in ranking)
    assert all(c[3]["corpo"] > 0 or c[3]["titulo"] > 0 or c[3]["frase"] > 0 for c in ranking)


def test_enquadramento_a_luz_da_sai_mas_luz_como_assunto_permanece():
    assert pc._radical("luz") not in pc._consulta("à luz da lei, cobrança")["pesos"]
    assert pc._radical("luz") in pc._consulta("tarifa de luz elétrica")["pesos"]


# ------------------------------------------ título por cobertura (§8)

def test_titulo_termo_raro_isolado_em_titulo_longo_vale_menos_que_titulo_curto_coberto():
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    consulta = pc._consulta("procedimentos irregulares e exigibilidade")
    termos = sorted(r for r in consulta["pesos"] if r in idf)
    comum = {"diploma": "CPC", "frequencias": {}, "bigramas": set()}
    longo = dict(comum, radicais_titulo=pc._radicais_uteis(
        "DO CUMPRIMENTO DEFINITIVO DA SENTENÇA QUE RECONHECE A EXIGIBILIDADE DE "
        "OBRIGAÇÃO DE PAGAR QUANTIA CERTA"))
    curto = dict(comum, radicais_titulo=pc._radicais_uteis("DOS PROCEDIMENTOS IRREGULARES"))
    assert pc._pontuar_chunk(curto, consulta, idf, termos)[2]["titulo"] > \
        3 * pc._pontuar_chunk(longo, consulta, idf, termos)[2]["titulo"]


def test_titulo_estrutura_numerica_nao_dilui_a_cobertura():
    limpo = pc._texto_de_titulo({"titulo": "TÍTULO II — PARTE ESPECIAL",
                                 "capitulo": "CAPÍTULO VII — DOS PROCEDIMENTOS IRREGULARES"})
    assert pc._radicais_uteis(limpo) == pc._radicais_uteis("DOS PROCEDIMENTOS IRREGULARES")
    # "civil" (letras romanas) não é confundido com numeral
    assert pc._radical("civil") in pc._radicais_uteis(
        pc._texto_de_titulo({"titulo": "TÍTULO IX — DA RESPONSABILIDADE CIVIL"}))


# --------------------------------------- D: CPC verdadeiro positivo (§21)

@pytest.mark.parametrize("questao", [
    "Exigibilidade da obrigação no cumprimento de sentença.",
    "Cumprimento de sentença que reconhece a exigibilidade de obrigação de pagar quantia certa.",
    "Impugnação ao cumprimento de sentença e exigibilidade do título executivo",
])
def test_D_exigibilidade_em_contexto_de_cpc_continua_recuperando_cpc(questao):
    assert any(i.startswith("CPC/") for i in _top(questao)), _top(questao)


# ------------------------------------------ Q2: paráfrases (§20)

@pytest.mark.parametrize("questao", [
    "Validade da cobrança de recuperação de consumo de energia elétrica",
    "Fundamento regulatório para a cobrança de consumo em unidade com irregularidade",
    "Exigibilidade da fatura de recuperação de consumo por irregularidade na medição",
    "Base normativa para o faturamento de consumo irregular de energia",
    "Exigibilidade da cobrança de recuperação de consumo segundo a REN 1000",
])
def test_paráfrases_de_exigibilidade_da_recuperacao_ficam_na_regulamentacao(questao):
    top = _top(questao)
    assert any(i.startswith("REN1000/") for i in top), top
    assert not any(i.startswith("CPC/") for i in top), top


# --------------------------------------------------- E/F: Q3 CDC e ruído

RUIDO_SETOR = {
    "REN1000/TI_C05.md", "REN1000/TII_C06_P01.md", "REN1000/TII_C06_P02.md",
    "REN1000/TI_C01_P01a.md", "REN1000/TI_C01_P01b.md", "REN1000/TI_C02_P01.md",
    "REN1000/TI_C02_P02.md", "REN1000/TII_C04_P01.md", "REN1000/TIII_P01.md",
    "REN1000/TIII_P02.md", "REN1000/TIII_P04a.md",
}


def test_E_Q3_mantem_cdc_relevante_em_primeiro_ou_segundo(questoes):
    assert any(i.startswith("CDC/") for i in _top(questoes[3])[:2]), _top(questoes[3])


def test_F_Q3_capitulos_genericos_do_setor_nao_consomem_as_vagas(questoes):
    top = _top(questoes[3])
    assert sum(i in RUIDO_SETOR for i in top) <= 1, top
    assert sum(i.startswith("CDC/") for i in top) >= 2, top


@pytest.mark.parametrize("questao", [
    "Aplicabilidade do Código de Defesa do Consumidor à concessionária de energia elétrica",
    "Relação de consumo entre distribuidora e unidade consumidora",
    "A relação entre a distribuidora e o consumidor é relação de consumo?",
    "Proteção do consumidor de energia elétrica",
    "Direitos básicos do consumidor perante a distribuidora de energia",
])
def test_paráfrases_de_protecao_do_consumidor_retornam_cdc_no_topo(questao):
    assert any(i.startswith("CDC/") for i in _top(questao)[:2]), (questao, _top(questao))


def test_conceito_nao_forca_cdc_para_questao_sem_o_dominio():
    """Vedado: 'consumidor -> sempre CDC'."""
    assert pc._consulta("Prazo para contestar a ação")["conceitos"] == []
    assert not any(i.startswith("CDC/") for i in _top("Prazo para contestar a ação"))


# --------------------------------------------- G/H/I: sem regressão

def test_G_Q0_preservada(questoes):
    assert _top(questoes[0])[0] == C07


def test_H_Q1_preservada(questoes):
    assert _top(questoes[1])[0] == C07


def test_I_Q4_preservada(questoes):
    top = _top(questoes[4])
    assert top[0].startswith("CC/") and any(i.startswith(("CC/", "CDC/")) for i in top)


def test_I_Q4_paraphrases_de_dano_moral_seguem_no_cc_ou_cdc():
    for q in ["Requisitos para indenização por dano moral",
              "Responsabilidade civil e dano moral indenizável",
              "Pressupostos da responsabilidade civil por danos morais",
              "Reparação de danos morais por cobrança indevida"]:
        assert any(i.startswith(("CC/", "CDC/")) for i in _top(q)), (q, _top(q))


# ------------------------------------------------ J: parser de artigos

def _chunk(corpo: str, ini: int, fim: int, extra: str = "") -> dict:
    texto = f"---\nart_inicio: {ini}\nart_fim: {fim}\n{extra}---\n{corpo}"
    return {"texto": texto, "meta": {"art_inicio": str(ini), "art_fim": str(fim)}}


def test_J_parser_extrai_artigos_contiguos_com_paragrafos_e_incisos():
    corpo = ("\nCAPÍTULO I\n\nDO TESTE\n\nArt. 1º Caput um.\n\n§ 1º Parágrafo.\n\nI - inciso;\n\n"
             "II - inciso.\n\nArt. 2º Caput dois, conforme o\nArt. 9 desta lei.\n\nArt. 3º Caput três.\n")
    u = pc._extrair_unidades(_chunk(corpo, 1, 3))
    assert [x["artigo"] for x in u] == ["1", "2", "3"]
    assert "§ 1º" in u[0]["texto"] and "II - inciso" in u[0]["texto"]
    # "Art. 9" no início de linha é referência cruzada (não é o próximo da sequência)
    assert "Art. 9 desta lei" in u[1]["texto"] and u[1]["texto"].startswith("Art. 2º")


def test_J_parser_aceita_artigo_com_letra_e_numero_com_ponto_de_milhar():
    u = pc._extrair_unidades(_chunk("\nArt. 589. A.\n\nArt. 589-A. B.\n\nArt. 590. C.\n", 589, 590))
    assert [x["artigo"] for x in u] == ["589", "589-A", "590"]
    u = pc._extrair_unidades(_chunk("\nArt. 1.045. X.\n\nArt. 1.046. Y.\n", 1045, 1046))
    assert [x["artigo"] for x in u] == ["1.045", "1.046"]


def test_J_parser_apara_cabecalho_estrutural_do_fim_do_artigo_sem_alterar_o_texto():
    corpo = "\nArt. 1º Primeiro.\n\nSeção II\n\nDo Procedimento\n\nArt. 2º Segundo.\n"
    u = pc._extrair_unidades(_chunk(corpo, 1, 2))
    assert u[0]["texto"] == "Art. 1º Primeiro."
    assert u[0]["texto"] in _chunk(corpo, 1, 2)["texto"]


def test_J_cabecalho_que_e_parte_do_texto_nao_e_aparado():
    corpo = "\nArt. 1º Primeiro.\n\nSeção II do regimento aplica-se ao caso.\n\nArt. 2º Segundo.\n"
    assert "Seção II do regimento" in pc._extrair_unidades(_chunk(corpo, 1, 2))[0]["texto"]


# ------------------------------------------------------- N: fallback

@pytest.mark.parametrize("corpo, ini, fim", [
    ("\nArt. 244. A.\n\nAt. 245. B (typo do corpus).\n\nArt. 246. C.\n", 244, 246),  # "At."
    ("\nArt. 1º A.\n\nArt. 3º C.\n", 1, 3),                                          # lacuna
    ("\nArt. 1º A.\n\nArt. 2º B.\n", 1, 3),                                          # não fecha em art_fim
    ("\nArt. 2º A.\n\nArt. 3º B.\n", 1, 3),                                          # não abre em art_inicio
    ("\nSem artigos aqui.\n", 1, 1),
])
def test_N_estrutura_nao_confiavel_cai_no_modo_trecho_sem_reconstruir(corpo, ini, fim):
    assert pc._extrair_unidades(_chunk(corpo, ini, fim)) == []


def test_N_frontmatter_sem_art_inicio_cai_no_fallback():
    assert pc._extrair_unidades({"texto": "---\ntipo: x\n---\nArt. 1º A.\n", "meta": {}}) == []


def test_N_chunk_real_com_typo_no_corpus_cai_em_trecho_e_preserva_o_excerto():
    """TI_C08_P01 (arts. 228-247) tem "At. 245." no corpus: o parser recusa em
    vez de corrigir."""
    chunk = next(c for c in pc._indice_corpus(pc.RAG_DIR_PADRAO)["chunks"]
                 if c["arquivo"].name == "TI_C08_P01.md")
    assert "At. 245." in chunk["texto"]
    modo, disp, motivo = pc._dispositivos_relevantes(
        chunk, {0: pc._consulta("medição para faturamento")},
        pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"])
    assert (modo, disp, motivo) == ("trecho", [], "estrutura_de_artigos_nao_confiavel")


def test_N_fonte_em_trecho_expoe_modo_e_motivo_e_mantem_texto():
    f = pc._buscar_fontes_para_questao("medição para faturamento", pc.RAG_DIR_PADRAO, 0)
    em_trecho = [x for x in f if x["modo_extrato"] == "trecho"]
    for x in em_trecho:
        assert x["dispositivos_relevantes"] == [] and x["motivo_modo_trecho"] and x["texto"]


# ------------------------------------- K/L: existência e procedência literal

def _chunk_de(source_id: str) -> dict:
    diploma, nome = source_id.split("/")
    return next(c for c in pc._indice_corpus(pc.RAG_DIR_PADRAO)["chunks"]
                if c["diploma"] == diploma and c["arquivo"].name == nome)


def test_K_todo_artigo_devolvido_existe_no_chunk_de_origem(fontes):
    for f in fontes:
        if f["modo_extrato"] != "dispositivo":
            continue
        arquivo = _chunk_de(f["source_id"])["texto"]
        rotulos = {m.group(1).rstrip(".") for m in re.finditer(r"(?m)^[ \t]*Art\.[ \t]*([\d\.]+)", arquivo)}
        for d in f["dispositivos_relevantes"]:
            numero = re.match(r"[\d\.]+", d["artigo"]).group(0)
            assert numero in rotulos, (f["source_id"], d["artigo"])


def test_K_artigo_devolvido_esta_dentro_do_intervalo_do_chunk_e_nao_vem_so_do_range(fontes):
    for f in fontes:
        meta = _chunk_de(f["source_id"])["meta"]
        for d in f["dispositivos_relevantes"]:
            n = int(re.match(r"[\d\.]+", d["artigo"]).group(0).replace(".", ""))
            assert int(meta["art_inicio"]) <= n <= int(meta["art_fim"])
            # o número aparece NO TEXTO devolvido: nunca inferido do range
            assert re.match(rf"\s*Art\.\s*{re.escape(d['artigo'].split('-')[0])}", d["texto"])


def test_L_texto_do_dispositivo_e_prefixo_literal_do_corpus(fontes):
    for f in fontes:
        arquivo = _chunk_de(f["source_id"])["texto"]
        assert f["texto"] in arquivo or f["texto"].rstrip() in arquivo
        for d in f["dispositivos_relevantes"]:
            assert d["texto"] in arquivo, (f["source_id"], d["artigo"])
            assert len(d["texto"]) <= pc.MAX_DISPOSITIVO_CHARS


def test_L_corpus_inteiro_toda_unidade_parseada_e_literal_contigua_e_fecha_o_intervalo():
    total = 0
    for c in pc._indice_corpus(pc.RAG_DIR_PADRAO)["chunks"]:
        u = pc._unidades_do_chunk(c)
        if u is None:
            continue
        nums = [int(re.match(r"[\d\.]+", x["artigo"]).group(0).replace(".", "")) for x in u]
        assert nums == sorted(nums)
        assert nums[0] == int(c["meta"]["art_inicio"]) and nums[-1] == int(c["meta"]["art_fim"])
        for x in u:
            assert x["texto"] in c["texto"], (c["arquivo"].name, x["artigo"])
            assert re.match(r"Art\.", x["texto"])
            total += 1
    assert total > 3000  # o parser cobre a esmagadora maioria do corpus


def test_L_dispositivo_truncado_e_prefixo_e_sinaliza_truncado():
    c07 = _chunk_de(C07)
    u = pc._unidades_do_chunk(c07)
    longo = max(u, key=lambda x: len(x["texto"]))
    assert len(longo["texto"]) > pc.MAX_DISPOSITIVO_CHARS
    cortado, truncado = pc._truncar_com_limite_de_frase(longo["texto"], pc.MAX_DISPOSITIVO_CHARS)
    assert truncado and longo["texto"].startswith(cortado)


# ---------------------------------- M: seleção de artigos relevantes

def test_M_c07_devolve_artigos_alem_do_caput_introdutorio_e_nao_o_capitulo_inteiro(fontes):
    f = next(x for x in fontes if x["source_id"] == C07)
    assert f["modo_extrato"] == "dispositivo"
    arts = [d["artigo"] for d in f["dispositivos_relevantes"]]
    assert 1 <= len(arts) <= pc.MAX_DISPOSITIVOS_POR_FONTE < 10
    assert any(a != "589" for a in arts), arts        # profundidade além do art. 589
    assert arts == sorted(arts, key=lambda a: int(a.split("-")[0]))  # ordem do diploma
    assert f["artigo_preciso"] == "589" and f["artigo"] == "589-598"  # contrato preservado


def test_M_cada_dispositivo_explica_por_que_foi_escolhido(fontes):
    for f in fontes:
        for d in f["dispositivos_relevantes"]:
            assert d["score"] > 0
            assert d["questoes_relacionadas"] and set(d["questoes_relacionadas"]) <= set(f["questoes_relacionadas"])
            assert isinstance(d["truncado"], bool)


def test_M_o_artigo_mais_relevante_depende_da_questao():
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    c07 = _chunk_de(C07)
    a = pc._dispositivos_relevantes(c07, {0: pc._consulta("período de duração da irregularidade limitado a seis ciclos")}, idf)[1]
    b = pc._dispositivos_relevantes(c07, {0: pc._consulta("comprovantes de notificação, agendamento e reagendamento da avaliação técnica")}, idf)[1]
    assert a and b
    melhor = lambda ds: max(ds, key=lambda d: d["score"])["artigo"]  # noqa: E731
    assert melhor(a) != melhor(b)


def test_M_piso_relativo_evita_completar_o_teto_com_artigo_fraco():
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    disp = pc._dispositivos_relevantes(_chunk_de(C07), {0: pc._consulta("período de duração da irregularidade seis ciclos")}, idf)[1]
    melhor = max(d["score"] for d in disp)
    assert all(d["score"] >= pc.FRACAO_MIN_DISPOSITIVO * melhor for d in disp)


def test_M_dispositivo_operativo_de_profundidade_do_q1(fontes):
    """Aceite de profundidade (§18): para Q1 e TII_C07 o pacote expõe texto
    literal de artigo(s) que tratam de procedimento (apuração/instrução) além
    do art. 589 — sem exigir um número de artigo pré-escrito."""
    f = next(x for x in fontes if x["source_id"] == C07)
    d1 = [d for d in f["dispositivos_relevantes"] if 1 in d["questoes_relacionadas"]]
    assert d1 and any(d["artigo"] != "589" for d in d1)
    radicais_q1 = pc._radicais_uteis("inspeção apuração recuperação de consumo procedimento")
    assert any(radicais_q1 & pc._radicais_uteis(d["texto"]) for d in d1)


# ----------------------------------- O: tamanho, P: determinismo, Q: vínculo

def test_O_tamanho_do_pacote_de_fontes_e_limitado(fontes):
    bytes_fontes = len(json.dumps(fontes, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    teto = pc.MAX_FONTES_TOTAL * (pc.MAX_DISPOSITIVOS_POR_FONTE * (pc.MAX_DISPOSITIVO_CHARS + 400) + 3000)
    assert bytes_fontes <= teto
    assert bytes_fontes <= 80_000  # fixture aprovada: ~36 KB medidos
    for f in fontes:
        assert len(f["dispositivos_relevantes"]) <= pc.MAX_DISPOSITIVOS_POR_FONTE


def test_P_determinismo_completo_inclusive_com_indice_reconstruido(questoes):
    a = _canonico(pc._montar_fontes_legais(questoes))
    b = _canonico(pc._montar_fontes_legais(questoes))
    pc._CACHE_INDICE_CORPUS.clear()
    c = _canonico(pc._montar_fontes_legais(questoes))
    assert a == b == c


def test_P_componentes_de_score_sao_deterministicos_e_expostos(fontes):
    for f in fontes:
        comp = f["score_componentes"]
        assert set(comp) == {"corpo", "titulo", "frase", "diploma_explicito"}
        assert isinstance(comp["diploma_explicito"], bool)


def test_Q_vinculo_fonte_questao_ordenado_e_toda_questao_tem_fonte(fontes, questoes):
    ids = [f["source_id"] for f in fontes]
    assert len(ids) == len(set(ids)) and len(fontes) <= pc.MAX_FONTES_TOTAL
    for f in fontes:
        assert f["questoes_relacionadas"] == sorted(set(f["questoes_relacionadas"]))
        assert all(0 <= i < len(questoes) for i in f["questoes_relacionadas"])
    for i in range(len(questoes)):
        assert any(i in f["questoes_relacionadas"] for f in fontes)


# ------------------------- R: validação/vigência e proveniência preservadas

def test_R_precisao_do_texto_nao_eleva_validacao_nem_vigencia(fontes):
    for f in fontes:
        assert f["validation_status"] == "NAO_VALIDADA"
        assert f["vigencia"] != "VIGENTE"
        assert f["authority_level"] == "OFICIAL"


def test_R_proveniencia_e_contrato_anterior_preservados(fontes):
    manifesto = json.loads((pc.RAG_DIR_PADRAO / "corpus_manifest.json").read_text(encoding="utf-8"))
    for f in fontes:
        assert f["corpus_versao"] == manifesto["versao"]
        for chave in ("source_id", "diploma", "artigo", "texto", "capitulo", "artigo_preciso",
                      "truncado", "questoes_relacionadas", "retrieval", "modo_extrato",
                      "dispositivos_relevantes"):
            assert chave in f, chave
        assert f["modo_extrato"] in ("dispositivo", "trecho")


def test_R_alertas_de_validacao_e_vigencia_continuam_no_pacote(monkeypatch, fixture_aprovada):
    import legal_readiness as lr
    monkeypatch.setattr(lr, "avaliar_corpus_rag", lambda: lr.ResultadoReadiness("READY", "s"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial", lambda *a, **k: lr.ResultadoReadiness("READY", "s"))
    monkeypatch.setattr(pc, "_obter_contexto_institucional_gerativo", lambda *a, **k: {})
    r = pc.preparar_contexto_contestacao(fixture_aprovada)
    assert r.status == "OK", r.motivo
    texto = " ".join(r.pacote["alertas"])
    assert "validation_status" in texto and "vigencia" in texto
    assert not any("questoes_juridicas[" in a for a in r.pacote["alertas"])


# --------------------------------------------- privacidade (código-fonte)

def test_U_modulo_nao_loga_nem_imprime_e_nao_ecoa_conteudo_de_questao():
    codigo = Path(pc.__file__).read_text(encoding="utf-8")
    assert "import logging" not in codigo
    assert re.search(r"(?<!#)\bprint\(", codigo) is None


def test_sem_jurisprudencia_nem_rede_no_novo_caminho():
    codigo = Path(pc.__file__).read_text(encoding="utf-8")
    importados = set(re.findall(r"^(?:import|from) ([\w\.]+)", codigo, re.MULTILINE))
    for proibido in ("requests", "urllib", "httpx", "socket", "aiohttp", "http"):
        assert proibido not in importados, proibido
    assert re.search(r"(?:requests|urllib|httpx)\.\w+\(", codigo) is None
    for f in pc._montar_fontes_legais(["responsabilidade civil"]):
        assert "jurisprud" not in f["source_id"].lower()


def test_dependencias_do_modulo_continuam_biblioteca_padrao():
    codigo = Path(pc.__file__).read_text(encoding="utf-8")
    novos = set(re.findall(r"^(?:import|from) (\w+)", codigo, re.MULTILINE))
    assert {"math", "unicodedata", "collections"} <= novos  # stdlib
    for pesado in ("numpy", "pandas", "sklearn", "rank_bm25", "pyarrow"):
        assert pesado not in novos
