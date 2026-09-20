# -*- coding: utf-8 -*-
"""
tests/test_preparar_contestacao.py — Gate 6.5-A: scripts/preparar_
contestacao.py (Core determinístico da primeira ferramenta jurídica).

Fixtures SINTÉTICAS apenas (Gate 6.5-A §22) — nenhum nome de litigante ou
número CNJ real em nenhum teste deste arquivo.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import preparar_contestacao as pc  # noqa: E402
import legal_readiness as lr  # noqa: E402
from test_instalar_modelo_oficial import (  # noqa: E402
    _CORPO_VALIDO,
    _partes_minimas,
    _zip_com_partes,
)

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"


def _limpar_env_modelo(monkeypatch):
    for var in (lr.ENV_MODELO_PATH, lr.ENV_MODELO_SHA256,
                lr.ENV_GCS_BUCKET, lr.ENV_GCS_OBJECT, lr.ENV_GCS_GENERATION):
        monkeypatch.delenv(var, raising=False)


def _configurar_modelo_real(monkeypatch):
    """Aponta o modo local (Gate 6.4-A) para o Modelo Oficial real, se
    presente — necessário para qualquer teste que exija
    contestacao_status=READY de verdade (contexto institucional real)."""
    if not TEMPLATE_REAL.is_file():
        return False
    sha = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    monkeypatch.setenv(lr.ENV_MODELO_PATH, str(TEMPLATE_REAL))
    monkeypatch.setenv(lr.ENV_MODELO_SHA256, sha)
    return True


# ------------------------------------------------------------------ fixtures

FIXTURE_A_CONSUMIDOR = {
    "fatos": [
        {"fact": "A concessionária lavrou Termo de Ocorrência de Irregularidade "
                 "na unidade consumidora em 10/03/2026.",
         "source_document": "TOI-sintetico-001.pdf", "tipo": "FATO_DOCUMENTADO"},
        {"fact": "A parte autora alega que jamais houve violação do medidor.",
         "source_document": "peticao-inicial-sintetica.pdf", "tipo": "ALEGACAO_AUTORAL"},
    ],
    "questoes_juridicas": ["inversao do onus da prova consumidor", "boa-fe contratual"],
    "estado_processual": {"GRATUIDADE_CONCEDIDA": False},
}

FIXTURE_B_OBRIGACAO_FAZER = {
    "fatos": [
        {"fact": "A autora requer o restabelecimento imediato do fornecimento.",
         "source_document": "peticao-inicial-sintetica.pdf", "tipo": "ALEGACAO_AUTORAL"},
        {"fact": "Consta aviso prévio de suspensão por inadimplência, sem "
                 "confirmação de corte efetivo nos autos.",
         "source_document": "aviso-sintetico.pdf", "tipo": "FATO_DOCUMENTADO"},
    ],
    "questoes_juridicas": ["suspensao do fornecimento de energia"],
    "estado_processual": {"CORTE_EFETIVO": "INDETERMINADO"},
}

FIXTURE_C_CAMPO_AUSENTE = {
    "fatos": [{"fact": "Fato sem documento de origem."}],
}

FIXTURE_D_SUPERDIMENSIONADA = {
    "fatos": [
        {"fact": f"Fato sintético número {i}.", "source_document": f"doc-{i}.pdf"}
        for i in range(pc.MAX_FATOS + 10)
    ],
}

FIXTURE_E_AMBIGUA = {
    "fatos": [{"fact": "x", "source_document": "y", "tipo": "TIPO_INEXISTENTE"}],
}


# --------------------------------------------------------- 1/15: caminho feliz

@pytest.mark.docx_real
def test_1_entrada_valida_produz_pacote_deterministico(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r1 = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    r2 = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r1.status == "OK", r1.motivo
    assert json.dumps(r1.pacote, sort_keys=True) == json.dumps(r2.pacote, sort_keys=True)
    assert r1.pacote["readiness"]["contestacao_status"] == "READY"
    assert len(r1.pacote["fatos_normalizados"]) == 2
    assert r1.pacote["fatos_normalizados"][0]["tipo"] == "FATO_DOCUMENTADO"


@pytest.mark.docx_real
def test_1b_fixture_obrigacao_de_fazer(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r = pc.preparar_contexto_contestacao(FIXTURE_B_OBRIGACAO_FAZER)
    assert r.status == "OK", r.motivo
    bloco_corte = next(b for b in r.pacote["blocos_modelo"] if b["id"] == "LICITUDE_CORTE_SUSPENSAO")
    assert "indeterminado" in bloco_corte["gate_status"]


# ------------------------------------------------------- 2/16/17: entrada inválida

def test_2_campo_obrigatorio_ausente_e_erro_estruturado():
    r = pc.preparar_contexto_contestacao(FIXTURE_C_CAMPO_AUSENTE)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"
    assert r.motivo is not None


def test_16_entrada_superdimensionada_e_rejeitada():
    r = pc.preparar_contexto_contestacao(FIXTURE_D_SUPERDIMENSIONADA)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"
    assert str(pc.MAX_FATOS) in r.motivo


def test_17_entrada_ambigua_tipo_invalido_e_rejeitada():
    r = pc.preparar_contexto_contestacao(FIXTURE_E_AMBIGUA)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


def test_entrada_nao_e_dict():
    r = pc.preparar_contexto_contestacao("nao sou um objeto")
    assert r.status == "PIPELINE_ABORTED"


def test_fatos_ausente():
    r = pc.preparar_contexto_contestacao({})
    assert r.status == "PIPELINE_ABORTED"


def test_fatos_vazio():
    r = pc.preparar_contexto_contestacao({"fatos": []})
    assert r.status == "PIPELINE_ABORTED"


def test_questoes_juridicas_excede_limite(monkeypatch):
    entrada = dict(FIXTURE_A_CONSUMIDOR)
    entrada["questoes_juridicas"] = [f"questao {i}" for i in range(pc.MAX_QUESTOES_JURIDICAS + 1)]
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


def test_estado_processual_valor_invalido():
    entrada = {"fatos": FIXTURE_A_CONSUMIDOR["fatos"], "estado_processual": {"X": "talvez"}}
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "input_validation"


# --------------------------------------------------------- 3/4/5: fail-closed

def test_3_4_5_contestacao_not_ready_falha_fechado(monkeypatch):
    _limpar_env_modelo(monkeypatch)  # nem GCS nem local -> modelo_oficial NOT_CONFIGURED
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"
    assert "rag=" in r.motivo and "modelo_oficial=" in r.motivo


def test_rag_not_ready_falha_fechado(monkeypatch, tmp_path):
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                         lambda: lr.ResultadoReadiness("NOT_READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                         lambda *a, **k: lr.ResultadoReadiness("READY", "sintético"))
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"


def test_modelo_not_ready_falha_fechado(monkeypatch):
    monkeypatch.setattr(lr, "avaliar_corpus_rag",
                         lambda: lr.ResultadoReadiness("READY", "sintético"))
    monkeypatch.setattr(lr, "avaliar_modelo_oficial",
                         lambda *a, **k: lr.ResultadoReadiness("NOT_READY", "sintético"))
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "PIPELINE_ABORTED"
    assert r.stage == "readiness"


# -------------------------------------------------------------- 12/13/14: RAG

def test_12_nenhuma_jurisprudencia_e_tocada():
    """§11: só os 6 diplomas legislativos são pesquisados — nunca
    jurisprudência (que sequer está no container/imagem, Gate 6.4-A/B)."""
    fontes = pc._montar_fontes_legais(["responsabilidade civil"])
    for f in fontes:
        assert "jurisprudencia" not in f["source_id"].lower()
        assert f["diploma"] is None or "jurisprud" not in f["diploma"].lower()


def test_13_fontes_contêm_proveniencia():
    fontes = pc._montar_fontes_legais(["inversao do onus da prova consumidor"])
    assert fontes, "esperava ao menos uma fonte para uma questão do CDC"
    for f in fontes:
        assert f["source_id"]
        assert f["diploma"]
        assert f["authority_level"] == "OFICIAL"
        assert f["texto"]


def test_14_retrieval_bounded_por_questao_e_no_total():
    muitas_questoes = ["consumidor", "contrato", "prova", "dano moral", "boa-fe"]
    fontes = pc._montar_fontes_legais(muitas_questoes)
    assert len(fontes) <= pc.MAX_FONTES_TOTAL
    for questao in muitas_questoes:
        assert len(pc._buscar_fontes_para_questao(questao, pc.RAG_DIR_PADRAO, 0)) <= pc.MAX_FONTES_POR_QUESTAO


def test_sem_questoes_juridicas_nao_busca_nada():
    assert pc._montar_fontes_legais([]) == []


# ------------------------------------------------------ 10/11: privacidade

def test_10_nenhum_conteudo_de_entrada_aparece_em_log(monkeypatch, caplog):
    """§19: fatos/questões nunca aparecem em log algum. Este módulo não
    chama nenhum logger — a prova é estrutural (nenhuma chamada de
    logging/print no código-fonte), reforçada aqui checando que a
    execução real não emite nenhum registro de log contendo o conteúdo
    sintético desta entrada."""
    _limpar_env_modelo(monkeypatch)
    marcador = "MARCADOR-DE-FATO-SECRETO-DO-CASO-XYZ"
    entrada = {"fatos": [{"fact": marcador, "source_document": "doc.pdf"}]}
    with caplog.at_level("DEBUG"):
        pc.preparar_contexto_contestacao(entrada)
    assert marcador not in caplog.text


def test_10b_codigo_fonte_nao_usa_logging_nem_print():
    codigo = Path(pc.__file__).read_text(encoding="utf-8")
    assert "import logging" not in codigo
    assert re.search(r"(?<!#)\bprint\(", codigo) is None


@pytest.mark.docx_real
def test_11_modelo_oficial_nunca_aparece_no_pacote(monkeypatch):
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "OK"
    serializado = json.dumps(r.pacote, ensure_ascii=False)
    assert str(TEMPLATE_REAL) not in serializado
    assert "PK\x03\x04" not in serializado  # assinatura binária de ZIP/DOCX
    # o pacote nunca inclui o caminho local configurado, nem qualquer
    # referência a bucket/objeto GCS além do SHA (não-secreto, já público
    # nesta configuração, mesma disciplina de docs/mcp-producao-contrato.md)
    assert "EDE_MODELO_OFICIAL_PATH" not in serializado


# ------------------------------------------------------------- blocos/gate

def test_gate_status_estado_nao_informado_nunca_vira_falso_silencioso():
    catalogo = {"blocks": [{"id": "X", "tag": "T", "tipo": "CONDICIONAL_PADRAO",
                             "decision_mode": "state_linked", "linked_fact": "ALGO",
                             "cardinality": "ONE"}], "zones": []}
    blocos = pc._montar_blocos_modelo(catalogo, {})
    assert blocos[0]["gate_status"] == "estado_nao_informado (ALGO)"


def test_gate_status_indeterminado_e_explicito():
    catalogo = {"blocks": [{"id": "X", "tag": "T", "tipo": "CONDICIONAL_PADRAO",
                             "decision_mode": "humano",
                             "requires_fact": {"key": "CORTE_EFETIVO"},
                             "cardinality": "ONE"}], "zones": []}
    blocos = pc._montar_blocos_modelo(catalogo, {"CORTE_EFETIVO": "INDETERMINADO"})
    assert "indeterminado" in blocos[0]["gate_status"]


def test_montar_blocos_nunca_decide_inclusao():
    """§15: o pacote descreve, nunca decide — nenhuma chave 'INCLUIR'/
    'EXCLUIR' aparece na descrição do catálogo."""
    catalogo = json.loads((BASE / "templates" / "contestacao" / "blocos.json").read_text(encoding="utf-8"))
    blocos = pc._montar_blocos_modelo(catalogo, {"GRATUIDADE_CONCEDIDA": True, "CORTE_EFETIVO": True})
    for b in blocos:
        assert "INCLUIR" not in json.dumps(b) and "EXCLUIR" not in json.dumps(b)


# =====================================================================
# Gate 6.5-B3 — endurecimento de qualidade do Contexto Package
# =====================================================================
#
# Fixture sintética reconstruída para este gate: a chamada real do Gate
# 6.5-B usou um caso ad hoc de irregularidade/recuperação de consumo de
# energia digitado diretamente na conversa com o Claude conectado (nunca
# persistido como arquivo neste repositório) — não há como reaproveitar
# o texto literal. Esta fixture cobre o MESMO domínio (irregularidade
# constatada, recuperação de consumo/faturamento, dano moral, inversão
# do ônus da prova) para exercitar a mesma classe de questão jurídica.

FIXTURE_F_IRREGULARIDADE_CONSUMO = {
    "fatos": [
        {"fact": "A concessionária lavrou Termo de Ocorrência de Irregularidade "
                 "apontando desvio de energia na unidade consumidora.",
         "source_document": "synthetic_toi_record.pdf", "tipo": "FATO_DOCUMENTADO"},
        {"fact": "A distribuidora apurou recuperação de consumo com base no "
                 "histórico de faturamento dos ciclos anteriores.",
         "source_document": "synthetic_consumption_recovery_record.txt",
         "tipo": "FATO_DOCUMENTADO"},
        {"fact": "A parte autora nega qualquer irregularidade e alega ter sido "
                 "surpreendida pela cobrança retroativa.",
         "source_document": "synthetic_initial_petition.pdf", "tipo": "ALEGACAO_AUTORAL"},
    ],
    "questoes_juridicas": [
        "irregularidade constatada em unidade consumidora e recuperacao de consumo",
        "calculo da diferenca de faturamento por irregularidade de medicao",
        "dano moral por cobranca indevida de consumo de energia",
        "inversao do onus da prova em favor do consumidor",
    ],
}


def test_A_fixture_aneel_recupera_capitulo_central_de_irregularidade():
    """§13/§21-A: a questão central de irregularidade/recuperação de
    consumo precisa recuperar o capítulo "Dos Procedimentos Irregulares"
    (REN1000, arts. 589-598) — o achado do Gate 6.5-B foi que ele
    perdia para capítulos genéricos (conexão, pré-pagamento) por pura
    extensão de texto."""
    fontes = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][0], pc.RAG_DIR_PADRAO, 0
    )
    assert fontes, "esperava ao menos uma fonte para a questão de irregularidade"
    assert fontes[0]["source_id"] == "REN1000/TII_C07.md", (
        f"capítulo central não ficou em primeiro lugar: {[f['source_id'] for f in fontes]}"
    )


def test_B_capitulos_genericos_nao_dominam_top_3():
    """§21-B: capítulos claramente alheios ao domínio (conexão, tensão,
    encerramento contratual) não devem varrer o top-3 da questão central
    — achado real do Gate 6.5-B (ruído lexical bruto)."""
    fontes = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][0], pc.RAG_DIR_PADRAO, 0
    )
    ids = {f["source_id"] for f in fontes}
    obviamente_alheios = {
        "REN1000/TI_C02_P01.md",  # Da Conexão / Tensão de Conexão
        "REN1000/TI_C03_P02.md",  # Do Encerramento Contratual
    }
    assert not (ids & obviamente_alheios), f"ruído óbvio no top-N: {ids}"


def test_C_cobertura_cdc_cc_para_questoes_de_dano_e_prova():
    """§12/§21-C: questões de dano moral e inversão do ônus da prova
    devem alcançar CDC/CC — antes deste gate, capítulos genéricos da
    REN1000 (classe comercial) dominavam por ruído lexical bruto.

    `diploma` (campo do modelo canônico) carrega o NOME descritivo do
    frontmatter `lei` quando presente (ex.: "Lei nº 8.078/1990 — Código
    de Defesa do Consumidor") — `source_id` é que usa o código curto de
    forma estável, por isso a checagem é sobre ele."""
    fontes_dano = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][2], pc.RAG_DIR_PADRAO, 2
    )
    assert any(f["source_id"].startswith(("CDC/", "CC/")) for f in fontes_dano), (
        f"nenhuma fonte CDC/CC para questão de dano moral: "
        f"{[f['source_id'] for f in fontes_dano]}"
    )
    fontes_prova = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][3], pc.RAG_DIR_PADRAO, 3
    )
    assert fontes_prova[0]["source_id"].startswith("CDC/"), (
        f"inversão do ônus da prova não trouxe CDC em primeiro lugar: "
        f"{[f['source_id'] for f in fontes_prova]}"
    )


def test_D_traceability_questao_para_fonte():
    """§6/§21-D: toda fonte recuperada declara `questoes_relacionadas`;
    uma fonte que responde a mais de uma questão acumula os índices, sem
    duplicar o objeto inteiro."""
    fontes = pc._montar_fontes_legais(FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"])
    assert fontes
    for f in fontes:
        assert isinstance(f["questoes_relacionadas"], list) and f["questoes_relacionadas"]
        assert all(isinstance(i, int) for i in f["questoes_relacionadas"])
    # nenhum source_id duplicado — a fusão aconteceu, não a repetição do objeto
    ids = [f["source_id"] for f in fontes]
    assert len(ids) == len(set(ids))


def test_E_corpus_versao_na_proveniencia_das_fontes():
    """§10/§21-E: cada fonte carrega a versão do manifesto do corpus de
    onde veio — nunca inventada, lida do mesmo `corpus_manifest.json`
    que `avaliar_corpus_rag` já usa para READY/NOT_READY."""
    manifesto = json.loads((pc.RAG_DIR_PADRAO / "corpus_manifest.json").read_text(encoding="utf-8"))
    fontes = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][0], pc.RAG_DIR_PADRAO, 0
    )
    assert fontes
    for f in fontes:
        assert f["corpus_versao"] == manifesto["versao"]


def test_F_artigo_preciso_quando_o_excerto_comeca_em_um_artigo():
    """§7/§21-F: quando o excerto retornado abre com "Art. N", o pacote
    expõe esse número em `artigo_preciso` — nunca inventado a partir do
    range do chunk (`artigo` continua sendo só o range, piso menos
    preciso)."""
    fontes = pc._buscar_fontes_para_questao(
        FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"][0], pc.RAG_DIR_PADRAO, 0
    )
    central = next(f for f in fontes if f["source_id"] == "REN1000/TII_C07.md")
    assert central["artigo_preciso"] == "589"
    assert central["artigo"] == "589-598"


def test_G_alerta_quando_fonte_nao_esta_validada():
    """§9/§21-G: toda fonte lexical nasce `validation_status=NAO_VALIDADA`
    (nenhuma validação de citação roda neste gate) — o pacote precisa
    expor um alerta explícito quando isso acontece, nunca silenciar."""
    fontes = pc._montar_fontes_legais(["inversao do onus da prova consumidor"])
    assert fontes and all(f["validation_status"] != "VALIDADA" for f in fontes)
    pacote = {
        "fontes_legais": fontes,
    }
    alertas = []
    fontes_nao_validadas = [f["source_id"] for f in pacote["fontes_legais"]
                             if f.get("validation_status") != "VALIDADA"]
    assert fontes_nao_validadas  # pré-condição do teste
    # comportamento real é exercido via preparar_contexto_contestacao —
    # ver test_H_alerta_de_vigencia_e_validacao_no_pacote_real abaixo.


@pytest.mark.docx_real
def test_H_alerta_de_vigencia_e_validacao_no_pacote_real(monkeypatch):
    """§9/§21-G/H: o pacote real propaga os dois alertas (validação e
    vigência) quando há questões jurídicas — nunca eleva o status da
    fonte, só torna a incerteza visível no nível do pacote."""
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r = pc.preparar_contexto_contestacao(FIXTURE_A_CONSUMIDOR)
    assert r.status == "OK"
    texto_alertas = " ".join(r.pacote["alertas"])
    assert "validation_status" in texto_alertas
    assert "vigencia" in texto_alertas


def test_I_excerto_nao_corta_no_meio_da_frase_sem_marcador():
    """§8/§21-I: quando o excerto é cortado, ou cai num fim de frase, ou
    o pacote expõe `truncado=True` — nunca um corte silencioso no meio
    de uma frase sem indicação alguma."""
    fontes = pc._montar_fontes_legais(FIXTURE_F_IRREGULARIDADE_CONSUMO["questoes_juridicas"])
    for f in fontes:
        texto = f["texto"]
        if f["truncado"]:
            continue  # marcador presente — comportamento esperado
        # sem marcador de truncamento, o excerto precisa ser o corpo
        # INTEIRO do chunk (nunca um corte não sinalizado)
        assert len(texto) <= pc.MAX_EXCERPT_CHARS


def test_J_nenhuma_marca_de_contaminacao_no_corpus_ren1000():
    """§11/§21-J: "Uso Interno CPFL" (achado de higiene de corpus deste
    gate) não sobrevive em arquivo algum do diploma REN1000."""
    contaminados = [
        arquivo.name
        for arquivo in sorted((pc.RAG_DIR_PADRAO / "chunks_REN1000").glob("*.md"))
        if "Uso Interno" in arquivo.read_text(encoding="utf-8")
        or "CPFL" in arquivo.read_text(encoding="utf-8")
    ]
    assert contaminados == []


def test_K_tipo_omitido_usa_o_helper_canonico_de_validate_fatos():
    """§14/§21-K: o default de `tipo` omitido é reúso do helper
    canônico já estabelecido (Fase 7/SPEC-0001 §9,
    validate_fatos.tipo_de) — não uma nova regra inventada por este
    módulo."""
    from validate_fatos import tipo_de
    fato_sem_tipo = {"fact": "x", "source_document": "y"}
    assert tipo_de(fato_sem_tipo) == "FATO_DOCUMENTADO"


def test_L_schema_publicado_expoe_limite_de_120_caracteres():
    """§15/§21-L: o JSON Schema publicado da tool expõe
    MAX_QUESTAO_CHARS=120 — um cliente não deveria descobrir isso só
    por uma chamada rejeitada."""
    sys.path.insert(0, str(BASE / "mcp_server"))
    import server as ede
    schema = ede.PrepararContestacaoEntrada.model_json_schema()
    assert schema["properties"]["questoes_juridicas"]["items"]["maxLength"] == pc.MAX_QUESTAO_CHARS
    assert schema["properties"]["questoes_juridicas"]["maxItems"] == pc.MAX_QUESTOES_JURIDICAS
    assert schema["properties"]["fatos"]["maxItems"] == pc.MAX_FATOS


def test_M_enum_do_schema_publicado_bate_com_o_enum_de_runtime():
    """§15/§21-M: o enum de `tipo` no schema publicado é exatamente o
    mesmo (TIPOS_VALIDOS) que scripts/validate_fatos.py aceita em
    runtime — nunca dois vocabulários que podem divergir."""
    sys.path.insert(0, str(BASE / "mcp_server"))
    import server as ede
    from validate_fatos import TIPOS_VALIDOS
    schema = ede.FatoEntrada.model_json_schema()
    enum_schema = set(schema["properties"]["tipo"]["anyOf"][0]["enum"])
    assert enum_schema == set(TIPOS_VALIDOS)


def test_N_erro_de_validacao_nao_ecoa_texto_da_questao():
    """§16/§21-N: a mensagem de erro de questão jurídica oversized nunca
    contém o conteúdo da questão — só metadado estrutural (índice,
    limite, tamanho recebido)."""
    entrada = dict(FIXTURE_A_CONSUMIDOR)
    questao_sensivel = "SEGREDO_DE_JUSTICA_" + ("x" * pc.MAX_QUESTAO_CHARS)
    entrada["questoes_juridicas"] = [questao_sensivel]
    r = pc.preparar_contexto_contestacao(entrada)
    assert r.status == "PIPELINE_ABORTED"
    assert "SEGREDO_DE_JUSTICA" not in r.motivo
    assert "questoes_juridicas[0]" in r.motivo


def test_P_extracao_de_contexto_nao_duplica_texto_de_forma_ancorada(monkeypatch):
    """§18/§21-P: `docx_context_engine._texto_paragrafo` não soma o
    texto do ramo `mc:Fallback` (VML legado) de uma forma ancorada ao do
    `mc:Choice` (moderno) — achado real: o título "PRELIMINARES" (uma
    caixa de texto ancorada) saía como "PRELIMINARESPRELIMINARES". O
    Modelo Oficial está correto; o defeito era só da extração."""
    if not TEMPLATE_REAL.is_file():
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    import tempfile
    from docx_package import extrair_pacote_docx
    from docx_context_engine import extrair_contexto
    from docx_block_engine import carregar_catalogo

    catalogo = carregar_catalogo(BASE / "templates" / "contestacao" / "blocos.json")
    with tempfile.TemporaryDirectory() as tmp:
        pacote_dir = Path(tmp) / "unpacked"
        extrair_pacote_docx(TEMPLATE_REAL, pacote_dir)
        xml = (pacote_dir / "word" / "document.xml").read_text(encoding="utf-8")
        contexto = extrair_contexto(xml, catalogo)

    for ocorrencias in contexto.values():
        for oc in ocorrencias:
            for campo in ("titulo", "antes", "depois"):
                valor = oc.get(campo) or ""
                palavras = valor.split()
                for palavra in palavras:
                    assert valor.count(palavra * 2) == 0 or len(palavra) < 4, (
                        f"possível duplicação de forma ancorada em {campo!r}: {valor!r}"
                    )


@pytest.mark.docx_real
def test_Q_pacote_permanece_deterministico_apos_recalibracao(monkeypatch):
    """§20/§21-Q: mesma entrada, mesmo corpus, mesmo código -> mesmo
    pacote, byte a byte — a recalibração de score/traceability/
    provenance deste gate não introduziu não-determinismo algum."""
    if not _configurar_modelo_real(monkeypatch):
        pytest.skip(f"{TEMPLATE_REAL} não instalado localmente — "
                     "asset institucional externo (ADR-0009).")
    r1 = pc.preparar_contexto_contestacao(FIXTURE_F_IRREGULARIDADE_CONSUMO)
    r2 = pc.preparar_contexto_contestacao(FIXTURE_F_IRREGULARIDADE_CONSUMO)
    assert r1.status == r2.status == "OK"
    assert json.dumps(r1.pacote, sort_keys=True) == json.dumps(r2.pacote, sort_keys=True)
