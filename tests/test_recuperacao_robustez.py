# -*- coding: utf-8 -*-
"""
tests/test_recuperacao_robustez.py — Gate 6.5-C1: robustez da recuperação
lexical de `scripts/preparar_contestacao.py` para questões jurídicas
ABSTRATAS.

Achado do Gate 6.5-C (produção, revisão ede-mcp-00014-dox): com 5 questões
abstratas, (1) o capítulo central "Dos Procedimentos Irregulares" (REN1000
TII_C07) ficava fora do top-3 da questão de regularidade do procedimento,
por diferença de flexão (procedimento/procedimentos, irregularidade/
irregulares) e acento; (2) o teto global de 10 fontes era consumido pelas
primeiras questões, deixando a 4ª com 1 fonte e a 5ª com nenhuma; (3)
vocabulário genérico do setor ("energia elétrica" no título de capítulos
de pré-pagamento) competia com o assunto real.

FIXTURE: reconstruída a partir da descrição do relatório do Gate 6.5-C —
o texto literal da chamada de produção nunca foi persistido neste
repositório. Dominio e formulação são os mesmos (questões abstratas de
regularidade de procedimento, recuperação de consumo, ônus da prova,
proteção do consumidor e dano moral). Nenhum dado real de processo.

Os testes NÃO dependem de uma frase literal: cada grupo (irregularidade,
consumidor, dano moral) é exercitado com paráfrases que variam
singular/plural, acentuação e formulação jurídica.
"""
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import preparar_contestacao as pc  # noqa: E402

CENTRAL = "REN1000/TII_C07.md"

FIXTURE_65C = [
    "Regularidade do procedimento de apuração de irregularidade de consumo de energia elétrica.",
    "Recuperação de consumo e cálculo da diferença de faturamento por irregularidade na medição.",
    "Inversão do ônus da prova em favor do consumidor.",
    "Marco de proteção do consumidor na relação entre distribuidora e unidade consumidora.",
    "Pressupostos para indenização por danos morais.",
]

# Capítulos que o gate nomeia como obviamente alheios à regularidade do
# procedimento de irregularidade (pré-pagamento, compra de energia, conexão).
RUIDO_REN1000 = (
    "REN1000/TII_C06_P01.md", "REN1000/TII_C06_P02.md",  # pré-pagamento
    "REN1000/TI_C05.md",                                  # compra de energia
    "REN1000/TI_C02_P01.md", "REN1000/TI_C02_P06.md",     # conexão
)


def _ids(questao, n=None):
    if n is not None:
        antigo = pc.MAX_FONTES_POR_QUESTAO
        pc.MAX_FONTES_POR_QUESTAO = n
        try:
            return [f"{c['diploma']}/{c['arquivo'].name}"
                    for _, _, c in pc._ranquear_candidatos(questao, pc.RAG_DIR_PADRAO)]
        finally:
            pc.MAX_FONTES_POR_QUESTAO = antigo
    return [f["source_id"] for f in pc._buscar_fontes_para_questao(questao, pc.RAG_DIR_PADRAO, 0)]


def _scores(questao):
    antigo = pc.MAX_FONTES_POR_QUESTAO
    pc.MAX_FONTES_POR_QUESTAO = 10_000
    try:
        return {f"{c['diploma']}/{c['arquivo'].name}": t
                for t, _, c in pc._ranquear_candidatos(questao, pc.RAG_DIR_PADRAO)}
    finally:
        pc.MAX_FONTES_POR_QUESTAO = antigo


# ------------------------------------------------------------ A: fixture

def test_A_fixture_65c_central_ren1000_lidera_e_e_vinculado_as_questoes_0_e_1():
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    central = next((f for f in fontes if f["source_id"] == CENTRAL), None)
    assert central is not None, [f["source_id"] for f in fontes]
    assert 0 in central["questoes_relacionadas"] and 1 in central["questoes_relacionadas"]
    assert _ids(FIXTURE_65C[0])[0] == CENTRAL
    assert _ids(FIXTURE_65C[1])[0] == CENTRAL


def test_A_fixture_65c_toda_questao_recebe_ao_menos_uma_fonte():
    """Achado (2): a 5ª questão ficava sem fonte alguma, a 4ª com uma."""
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    for i in range(len(FIXTURE_65C)):
        assert any(i in f["questoes_relacionadas"] for f in fontes), f"questão {i} ficou sem fonte"
    assert len(fontes) <= pc.MAX_FONTES_TOTAL


# ------------------------------------------- B/C: paráfrase e flexão

PARAFRASES_IRREGULARIDADE = [
    "Legalidade do procedimento de apuração da irregularidade na medição de energia",
    "Procedimentos irregulares: requisitos do termo de ocorrência e inspeção",
    "Como deve a distribuidora apurar irregularidade no medidor?",
    "Regularidade dos procedimentos de apuração de irregularidades",
    "recuperacao de consumo por irregularidade constatada",  # sem acento
]


@pytest.mark.parametrize("questao", PARAFRASES_IRREGULARIDADE)
def test_B_parafrase_de_irregularidade_recupera_o_capitulo_central(questao):
    assert CENTRAL in _ids(questao), f"{questao!r} -> {_ids(questao)}"


def test_C_flexao_singular_plural_e_derivacao_convergem_para_o_mesmo_radical():
    r = lambda w: pc._radical(pc._normalizar(w))  # noqa: E731
    assert r("procedimento") == r("procedimentos")
    assert r("irregularidade") == r("irregulares") == r("irregular")
    assert r("consumidor") == r("consumidora") == r("consumidores")
    assert r("indenização") == r("indenizar") == r("indenizações")
    assert r("danos") == r("dano")
    assert r("moral") == r("morais")
    assert r("relação") == r("relações")


def test_C_titulo_no_plural_casa_consulta_no_singular_e_vice_versa():
    """Título do capítulo: "DOS PROCEDIMENTOS IRREGULARES"."""
    titulo = pc._radicais_uteis("CAPÍTULO VII — DOS PROCEDIMENTOS IRREGULARES")
    assert pc._radicais_uteis("procedimento irregular") <= titulo
    assert pc._radicais_uteis("irregularidade do procedimento") <= titulo


def test_C_normalizacao_de_acento_e_caixa_em_consulta_e_corpus():
    assert pc._normalizar("Apuração DE Irregularidade") == "apuracao de irregularidade"
    assert pc._radicais_uteis("recuperação") == pc._radicais_uteis("RECUPERACAO")


def test_C_stopwords_acentuadas_do_corpus_agora_sao_filtradas():
    """Causa-raiz (achado 6.5-C1): a lista é escrita sem acento ("nao",
    "ate"), mas o texto só passava por `.lower()`, então "não"/"até" nunca
    eram filtrados."""
    assert pc._radicais_uteis("não até já também") == set()


# ------------------------------------------------ D/G: consumidor (CDC)

PARAFRASES_CONSUMIDOR = [
    "Proteção do consumidor nas relações de consumo de energia",
    "Aplicação do Código de Defesa do Consumidor à concessionária de energia",
    "Direitos básicos do consumidor de serviço público",
    "Defesa do consumidor na relação com a distribuidora",
    FIXTURE_65C[3],
]


@pytest.mark.parametrize("questao", PARAFRASES_CONSUMIDOR)
def test_D_G_questao_abstrata_de_protecao_do_consumidor_recupera_cdc(questao):
    ids = _ids(questao)
    assert any(i.startswith("CDC/") for i in ids), f"{questao!r} -> {ids}"


def test_G_questao_3_do_gate_65c_traz_mais_de_uma_fonte_substantiva_do_cdc():
    ids = _ids(FIXTURE_65C[3])
    assert sum(i.startswith("CDC/") for i in ids) >= 2, ids


# --------------------------------------------- E/H: dano moral (CC/CDC)

PARAFRASES_DANO_MORAL = [
    "Requisitos para indenização por dano moral",
    "Responsabilidade civil e dano moral indenizável",
    "Pressupostos da responsabilidade civil por danos morais",
    "Reparação de danos morais por cobrança indevida",
    "Indenizações por danos morais: requisitos",
    FIXTURE_65C[4],
]


@pytest.mark.parametrize("questao", PARAFRASES_DANO_MORAL)
def test_E_H_questao_abstrata_de_dano_moral_recupera_cc_ou_cdc(questao):
    ids = _ids(questao)
    assert any(i.startswith(("CC/", "CDC/")) for i in ids), f"{questao!r} -> {ids}"


def test_H_questao_4_do_gate_65c_traz_cc_em_primeiro_lugar():
    assert _ids(FIXTURE_65C[4])[0].startswith("CC/")


# ------------------------------------------------------ F/I: ranking e ruído

def test_F_central_ren1000_tem_margem_clara_sobre_qualquer_ruido():
    for questao in (FIXTURE_65C[0], FIXTURE_65C[1]):
        scores = _scores(questao)
        assert max(scores, key=scores.get) == CENTRAL
        melhor_ruido = max((scores[i] for i in RUIDO_REN1000 if i in scores), default=0.0)
        assert scores[CENTRAL] >= 1.2 * melhor_ruido, (
            f"margem insuficiente sobre ruído: {scores[CENTRAL]} vs {melhor_ruido}"
        )


def test_I_ruido_da_ren1000_nao_domina_a_selecao():
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    ids = [f["source_id"] for f in fontes]
    ruido = [i for i in ids if i in RUIDO_REN1000]
    assert len(ruido) <= len(ids) // 3, f"ruído demais no pacote: {ruido} de {ids}"
    # e nenhuma questão tem um capítulo de ruído como fonte nº 1
    for questao in FIXTURE_65C:
        assert _ids(questao)[0] not in RUIDO_REN1000


def test_I_vocabulario_do_setor_pesa_menos_que_o_assunto():
    """IDF calculado sobre o próprio corpus: 'energia'/'elétrica' são
    comuns, 'irregularidade' é rara — sem lista manual de palavras do setor."""
    idf = pc._indice_corpus(pc.RAG_DIR_PADRAO)["idf"]
    r = lambda w: pc._radical(pc._normalizar(w))  # noqa: E731
    assert idf[r("irregularidade")] > idf[r("energia")]
    assert idf[r("irregularidade")] > idf[r("elétrica")]
    assert idf[r("indenização")] > idf[r("energia")]


# ------------------------------------------------ seleção entre questões

def test_selecao_por_rodadas_nao_deixa_questao_final_sem_fonte():
    """Cinco questões cujo top-3 são todos distintos: o teto global (10)
    não pode ser consumido pelas primeiras."""
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    primeiro_de_cada = {_ids(q)[0] for q in FIXTURE_65C}
    assert primeiro_de_cada <= {f["source_id"] for f in fontes}


def test_selecao_respeita_limite_total_e_por_questao():
    fontes = pc._montar_fontes_legais(FIXTURE_65C * 1)
    assert len(fontes) <= pc.MAX_FONTES_TOTAL
    for i in range(len(FIXTURE_65C)):
        assert sum(i in f["questoes_relacionadas"] for f in fontes) <= pc.MAX_FONTES_POR_QUESTAO


# ------------------------------------------------ conceitos: sem diploma forçado

def test_conceito_so_dispara_com_todos_os_radicais_de_um_gatilho():
    _, _, ativos = pc._termos_da_consulta("A parte é consumidora do serviço prestado.")
    assert ativos == []
    _, _, ativos = pc._termos_da_consulta("Houve dano ao equipamento elétrico.")
    assert ativos == []
    _, _, ativos = pc._termos_da_consulta("Proteção do consumidor")
    assert ativos == ["PROTECAO_DO_CONSUMIDOR"]


def test_nenhum_conceito_nomeia_diploma_nem_forca_fonte():
    """Vedado: 'consumidor -> sempre CDC', 'dano -> sempre CC'. A tabela só
    acrescenta termos de consulta; nenhum campo referencia diploma/chunk."""
    proibidos = {d.lower() for d in pc.DIPLOMAS} | {"codigo civil", "l8987", "l9427"}
    for c in pc.CONCEITOS_JURIDICOS:
        assert set(c) == {"id", "gatilhos", "expansao"}
        texto = " ".join(" ".join(g) for g in c["gatilhos"]) + " " + " ".join(c["expansao"])
        assert not (set(pc._normalizar(texto).split()) & proibidos)


def test_questao_sem_dominio_consumerista_nao_recebe_cdc_forcado():
    ids = _ids("Prazo para contestar a ação")
    assert ids and not any(i.startswith("CDC/") for i in ids)


def test_termo_expandido_pesa_menos_que_termo_escrito_pelo_advogado():
    pesos, _, ativos = pc._termos_da_consulta("Marco de proteção do consumidor")
    assert ativos
    diretos = {pc._radical(pc._normalizar(w)) for w in ("marco", "protecao", "consumidor")}
    assert all(pesos[r] == 1.0 for r in diretos if r in pesos)
    assert any(p == pc.PESO_TERMO_EXPANDIDO for p in pesos.values())


# ------------------------------------------------------------ J: determinismo

def test_J_selecao_repetida_e_identica_inclusive_com_indice_reconstruido():
    a = json.dumps(pc._montar_fontes_legais(FIXTURE_65C), sort_keys=True)
    b = json.dumps(pc._montar_fontes_legais(FIXTURE_65C), sort_keys=True)
    pc._CACHE_INDICE_CORPUS.clear()
    c = json.dumps(pc._montar_fontes_legais(FIXTURE_65C), sort_keys=True)
    assert a == b == c


# ------------------------------------------- K/L: vínculo e proveniência

def test_K_vinculo_fonte_questao_consistente():
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    ids = [f["source_id"] for f in fontes]
    assert len(ids) == len(set(ids))
    for f in fontes:
        assert f["questoes_relacionadas"]
        assert all(isinstance(i, int) and 0 <= i < len(FIXTURE_65C)
                   for i in f["questoes_relacionadas"])
        assert f["questoes_relacionadas"] == sorted(set(f["questoes_relacionadas"]))


def test_L_proveniencia_preservada():
    manifesto = json.loads((pc.RAG_DIR_PADRAO / "corpus_manifest.json").read_text(encoding="utf-8"))
    fontes = pc._montar_fontes_legais(FIXTURE_65C)
    for f in fontes:
        assert f["corpus_versao"] == manifesto["versao"]
        assert f["validation_status"] == "NAO_VALIDADA"
        assert f["authority_level"] == "OFICIAL"
        assert f["vigencia"] != "VIGENTE"
        assert isinstance(f["truncado"], bool)
        assert "artigo_preciso" in f and "capitulo" in f and "artigo" in f
        assert f["retrieval"]["score_final"] >= f["retrieval"]["score_lexical"] >= 0
    central = next(f for f in fontes if f["source_id"] == CENTRAL)
    assert central["artigo"] == "589-598"
    assert central["artigo_preciso"] == "589"


# ------------------------------------------- M: propagação de alertas

def test_M_alerta_para_questao_sem_fonte_expoe_so_o_indice(monkeypatch):
    """Uma questão sem nenhuma fonte não passa em silêncio quando outras
    questões recuperaram fontes — e o alerta nunca ecoa o texto da questão."""
    import legal_readiness as lr
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                        lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                        lambda *a, **k: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(pc, "_obter_contexto_institucional_gerativo",
                        lambda *a, **k: {})
    sem_sentido = "zzqxvk wwqpl"
    entrada = {
        "fatos": [{"fact": "Fato sintético.", "source_document": "doc-sintetico.pdf",
                   "tipo": "FATO_DOCUMENTADO"}],
        "questoes_juridicas": [FIXTURE_65C[3], sem_sentido],
    }
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "OK", r.motivo
    texto = " ".join(r.pacote["alertas"])
    assert "questoes_juridicas[1]" in texto
    assert sem_sentido not in texto
    # alertas de validação/vigência continuam sendo propagados
    assert "validation_status" in texto and "vigencia" in texto


def test_M_sem_alerta_espurio_quando_todas_as_questoes_recuperam_fonte(monkeypatch):
    import legal_readiness as lr
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                        lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                        lambda *a, **k: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(pc, "_obter_contexto_institucional_gerativo",
                        lambda *a, **k: {})
    entrada = {
        "fatos": [{"fact": "Fato sintético.", "source_document": "doc-sintetico.pdf",
                   "tipo": "FATO_DOCUMENTADO"}],
        "questoes_juridicas": FIXTURE_65C,
    }
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "OK", r.motivo
    assert not any("questoes_juridicas[" in a for a in r.pacote["alertas"])
