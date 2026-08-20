#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_e2e_contestacao.py — Fase 7 (SPEC-0001): integração end-to-end do
pipeline da Contestação sobre `scripts/gerar_contestacao.py`.

Cenários sintéticos em tests/fixtures/contestacao/ — nomes, processo,
documentos e valores fictícios. Nenhum dado real de cliente; nada de
`rag/jurisprudencia/`.

Escopo real do que este arquivo testa (SPEC-0001 Fase 7 §33 — não
simular execução de Skill): `estrategista-contestacao-ede`,
`redator-peca-processual-elite` e `humanizer-pt-br` são Skills do Claude
Code, não funções Python — não há como "executá-las" de dentro de um
teste automatizado. O que ESTE arquivo verifica é a integração real dos
componentes que SÃO código (validate_fatos, calendario, RAG,
legal_validation, Template Engine, Template Lock) mais a verificação
estrutural de que a saída esperada das Skills existe e tem a forma
certa. A execução real das três Skills sobre o cenário "happy_path"
(produção de `estrategia.md`, `placeholders_redator.json` e
`placeholders.json`) foi feita manualmente por este agente, registrada em
`docs/E2E_FASE7.md` — não fabricada nem simulada por código.

Cenário de Template Lock reprovando adulteração fora de placeholder já
tem cobertura equivalente em tests/test_template_engine.py
(`test_template_lock_detecta_alteracao_fora_de_placeholder` +
`test_pipeline_completo_contra_template_real`, que testa adulteração
contra o DOCX real) — não duplicado aqui (SPEC-0001 Fase 7 §28).

Mesmo padrão sem framework: asserts + `if __name__ == "__main__"`.

Uso:
  python tests/test_e2e_contestacao.py
"""
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE = Path(__file__).parent.parent
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"
sys.path.insert(0, str(BASE / "scripts"))
from gerar_contestacao import MARCADOR_FOTOS, gerar  # noqa: E402

REAL_TEMPLATE = BASE / "templates" / "contestacao" / "modelo-oficial.docx"


def _pular_se_sem_template_real():
    if not REAL_TEMPLATE.exists():
        print("SKIP (template real ausente localmente — ADR-0006, esperado em CI/clone limpo)")
        return True
    return False


# --------------------------------------------------------------- happy path
def test_happy_path_pipeline_completo():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao_sintetica.docx"
        r = gerar(FIXTURES / "happy_path", saida)

        assert r["status"] == "OK", r
        nomes_stage = {s["name"] for s in r["stages"]}
        assert nomes_stage == {"facts", "tempestividade", "strategy",
                                "block_composition_decisoes", "rag_legal_validation",
                                "drafting_humanization", "paragrafo_380", "template_engine"}
        assert all(s["status"] == "ok" for s in r["stages"]), r["stages"]

        assert r["fatos_com_proveniencia"] == 11
        assert r["citacoes_validadas"] == 7   # 7 citações reais do corpus
        assert r["citacoes_nao_validadas"] == 1  # art. 999999 — inexistente, rejeitado
        assert r["template_lock"] == "OK"
        assert r["fotos"] == "INSERÇÃO MANUAL"
        assert r["tempestividade"].startswith("TEMPESTIVO")

        assert saida.exists() and saida.stat().st_size > 0
        _validar_docx_integro(saida)
        _validar_conteudo_sintetico(saida)


def _validar_docx_integro(caminho: Path):
    # TEST-009 (SPEC-0001): DOCX final deve abrir sem corrupção — aqui,
    # verificação programática mínima: ZIP íntegro + XML bem formado.
    assert zipfile.is_zipfile(caminho)
    with zipfile.ZipFile(caminho) as z:
        ruim = z.testzip()
        assert ruim is None, f"membro corrompido no zip: {ruim}"
        nomes = z.namelist()
        assert "word/document.xml" in nomes
        assert "[Content_Types].xml" in nomes
        assert any(n.startswith("word/header") for n in nomes), \
            "nenhum header preservado no DOCX final"
        assert any(n.startswith("word/footer") for n in nomes), \
            "nenhum footer preservado no DOCX final"
        document_xml = z.read("word/document.xml").decode("utf-8")
        ET.fromstring(document_xml)  # levanta ParseError se malformado


def _validar_conteudo_sintetico(caminho: Path):
    # TEST-041 (Fase 7 §41): não basta o arquivo existir — os dados
    # sintéticos esperados precisam aparecer no XML gerado.
    with zipfile.ZipFile(caminho) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    esperados = [
        "MARIA JOS", "8000001-11.2026.8.05.0080",
        "445566-7",  # unidade consumidora, prova que IRREGULARIDADE_ENCONTRADA entrou
        "4.328,17",  # VALOR_FRA
        MARCADOR_FOTOS,
        "Feira de Santana",
    ]
    for trecho in esperados:
        assert trecho in document_xml, f"trecho esperado não encontrado no DOCX gerado: {trecho!r}"
    assert "{{" not in document_xml, "placeholder residual (chaves duplas) no XML final"
    assert 'w:val="FF0000"' in document_xml, "conteúdo gerado deveria estar em FF0000 (Etapa 3)"
    # RECONVENCAO=INCLUIR neste fixture (happy_path/decisoes_blocos.json) —
    # o inline vinculado (INLINE_COM_RECONVENCAO) deve refletir isso no
    # título (Etapa 5.2 — regressão do achado real de composição em
    # wps:txbx/w:txbxContent, ver docx_block_engine.compor_blocos).
    assert "COM RECONVENÇÃO" in document_xml, "título deveria conter 'COM RECONVENÇÃO' (RECONVENCAO=INCLUIR)"


# --------------------------------------------------------------- fail-closed
def test_fail_closed_valor_essencial_ausente():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(FIXTURES / "fail_closed_valor_ausente", saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "placeholders"
        assert "VALOR_FRA" in r["reason"]
        assert not saida.exists(), "PIPELINE_ABORTED não pode deixar DOCX no disco"


def test_fail_closed_autor_semanticamente_invalido():
    # Etapa 3 (gate pós-diagnóstico forense): AUTOR com cláusula de
    # qualificação/CPF duplicando o texto fixo do template — o padrão
    # exato do bug real — nunca pode alcançar o template.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        placeholders = json.loads((caso_tmp / "placeholders.json").read_text(encoding="utf-8"))
        placeholders["AUTOR"] = ("Fulana de Tal, já qualificada nos autos, "
                                  "portadora do CPF nº 011.730.795-56")
        (caso_tmp / "placeholders.json").write_text(json.dumps(placeholders), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "placeholders"
        assert "AUTOR" in r["reason"]
        assert not saida.exists()


def test_fail_closed_estrategista_indisponivel():
    # Simula Skill obrigatória indisponível (SPEC-0001 Fase 7 §27, terceiro
    # exemplo): copia o caso happy_path para um diretório temporário e
    # remove estrategia.md — o pipeline deve abortar no estágio "strategy",
    # nunca prosseguir como se a etapa estratégica tivesse ocorrido
    # (INV-CONTESTACAO-ESTRATEGIA).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estrategia.md").unlink()

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "strategy"
        assert not saida.exists()


def test_fail_closed_estrategia_estruturalmente_invalida():
    # Skill "executada", mas saída inválida (seções ausentes) — também não
    # pode ser tratada como concluída (§7: "produzir saída estruturalmente
    # inválida" é equiparado a falha).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estrategia.md").write_text(
            "# ANÁLISE ESTRATÉGICA\n\nTexto incompleto, sem as 15 seções do contrato.",
            encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "strategy"
        assert not saida.exists()


# ---------------------------------------------- tempestividade (INV-TEMPESTIVIDADE-MARCO)
def test_fail_closed_tempestividade_marco_ausente():
    # Teste negativo obrigatório: sem data de citação/intimação/publicação
    # nenhuma, o pipeline não pode avançar além da etapa de tempestividade
    # — nunca gera DOCX com "PENDENTE DE VALIDAÇÃO" no lugar do marco.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "tempestividade.json").write_text(json.dumps({
            "aplicavel": True, "data_pratica_ato": "2026-02-10",
            "prazo_legal_dias": 15, "tipo_prazo": "uteis",
            "fundamento_normativo": "art. 335, caput, CPC",
        }), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "tempestividade"
        assert not saida.exists()


def test_fail_closed_tempestividade_marco_sem_origem():
    # Data presente, mas sem 'marco_origem' registrado — equivalente a
    # marco ambíguo/conflitante/insuficientemente comprovado: também
    # bloqueia, nunca é tratado como documentado só porque uma data existe.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        dados = json.loads((caso_tmp / "tempestividade.json").read_text(encoding="utf-8"))
        dados.pop("marco_origem", None)
        dados.pop("marco_source_document", None)
        (caso_tmp / "tempestividade.json").write_text(json.dumps(dados), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "tempestividade"
        assert not saida.exists()


def test_tempestividade_informada_pelo_advogado():
    # Teste positivo (informado): marco não documentado nos autos, mas o
    # advogado respondeu à pergunta obrigatória — registrado com origem e
    # resposta verbatim; calendario-forense-tjba-2026 é acionado
    # normalmente e o pipeline prossegue até o fim.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "tempestividade.json").write_text(json.dumps({
            "aplicavel": True,
            "data_pratica_ato": "2026-02-10",
            "data_ciencia": "2026-01-05",
            "prazo_legal_dias": 15,
            "tipo_prazo": "uteis",
            "fundamento_normativo": "art. 335, caput, CPC",
            "marco_origem": "informado_pelo_advogado",
            "marco_resposta_advogado": "A citação ocorreu em 05/01/2026, "
                                        "conforme confirmado pelo advogado "
                                        "responsável (não constava nos "
                                        "documentos anexados).",
        }), encoding="utf-8")

        saida = Path(tmp) / "contestacao_marco_informado.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "OK", r
        tempestividade_stage = next(s for s in r["stages"] if s["name"] == "tempestividade")
        assert tempestividade_stage["status"] == "ok"
        assert tempestividade_stage["marco_origem"] == "informado_pelo_advogado"
        assert r["tempestividade"].startswith("TEMPESTIVO")
        assert saida.exists()


def test_fail_closed_template_institucional_ausente():
    # Consolidação pós-Fase 8: o template real é asset externo, nunca
    # distribuído — uma instalação pública nunca o terá até ser fornecido
    # separadamente. Isso NÃO é "instalação corrompida" (fatos, estratégia,
    # RAG e validação jurídica seguem funcionando normalmente até aqui);
    # só a geração do DOCX final para nesse ponto específico, sem
    # inventar/baixar/reconstruir template algum. Roda sempre — não
    # depende do template real existir localmente (é o inverso do caso).
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deveria_existir.docx"
        template_inexistente = Path(tmp) / "modelo-oficial-inexistente.docx"
        r = gerar(FIXTURES / "happy_path", saida, template=template_inexistente)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "template_engine"
        # todas as etapas anteriores (fatos, tempestividade, estratégia,
        # RAG/validação, redação+humanização) completaram normalmente —
        # só a etapa que depende do asset externo falhou.
        nomes_ok = {s["name"] for s in r["stages"] if s["status"] == "ok"}
        assert nomes_ok == {"facts", "tempestividade", "strategy",
                             "block_composition_decisoes", "rag_legal_validation",
                             "drafting_humanization", "paragrafo_380"}
        assert not saida.exists()


# --------------------------------------------- Etapa 5.2: INV-PARAGRAFO-380
def test_fail_closed_paragrafo_acima_de_380():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        placeholders = json.loads((caso_tmp / "placeholders.json").read_text(encoding="utf-8"))
        placeholders["PEDIDOS_FINAIS"] = "x" * 381
        (caso_tmp / "placeholders.json").write_text(json.dumps(placeholders), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "paragrafo_380"
        assert "PEDIDOS_FINAIS" in r["reason"]
        assert not saida.exists()


# ------------------------------------- Etapa 5.2: INV-RECONVENCAO-AUTORIZACAO-EXPRESSA
def test_fail_closed_reconvencao_indeterminada():
    # CENÁRIO 6 do prompt da Etapa 5.2: reconvenção sem resposta -> aborta.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        decisoes = json.loads((caso_tmp / "decisoes_blocos.json").read_text(encoding="utf-8"))
        decisoes["RECONVENCAO"] = {"decisao": "INDETERMINADO"}
        (caso_tmp / "decisoes_blocos.json").write_text(json.dumps(decisoes), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "block_composition"
        assert not saida.exists()


def test_reconvencao_nao_autorizada_pelo_advogado_nao_aparece_no_titulo():
    # CENÁRIO 7: reconvenção respondida NÃO pelo advogado -> exclui, e o
    # título final não contém "COM RECONVENÇÃO" (INLINE_COM_RECONVENCAO
    # continua espelhando RECONVENCAO).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        decisoes = json.loads((caso_tmp / "decisoes_blocos.json").read_text(encoding="utf-8"))
        decisoes["RECONVENCAO"] = {"decisao": "EXCLUIR", "fundamento": "advogado respondeu NÃO à pergunta obrigatória"}
        (caso_tmp / "decisoes_blocos.json").write_text(json.dumps(decisoes), encoding="utf-8")

        saida = Path(tmp) / "contestacao_sem_reconvencao.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "OK", r
        assert "RECONVENCAO" in r["blocos_excluidos"]
        assert "INLINE_COM_RECONVENCAO" in r["blocos_excluidos"]
        with zipfile.ZipFile(saida) as z:
            document_xml = z.read("word/document.xml").decode("utf-8")
        assert "COM RECONVENÇÃO" not in document_xml.upper().replace("Ç", "C")  # sem resíduo textual
        assert "COM RECONVEN" not in document_xml.upper()


# ------------------------------- Etapa 5.2 (correção): INV-GRATUIDADE-LINKED (state_linked)
def test_gratuidade_sem_estado_processual_resolve_para_excluir():
    # CENÁRIO 4: gratuidade apenas requerida/não concedida — sem
    # estado_processual.json algum, o vínculo determinístico resolve para
    # EXCLUIR por omissão (fail closed), sem qualquer decisão manual.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao_sem_gratuidade.docx"
        r = gerar(FIXTURES / "happy_path", saida)

        assert r["status"] == "OK", r
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" in r["blocos_excluidos"]
        assert r["containers_derivados"]["PRELIMINARES"] == "EXCLUIR"


def test_fail_closed_decisao_manual_do_estrategista_para_gratuidade_e_rejeitada():
    # A preliminar de gratuidade NÃO é decisão do estrategista — se
    # decisoes_blocos.json trouxer uma decisão para ela (mesmo coerente com
    # o estado real), o pipeline rejeita explicitamente (nunca ignora em
    # silêncio a decisão indevida).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        decisoes = json.loads((caso_tmp / "decisoes_blocos.json").read_text(encoding="utf-8"))
        decisoes["PRELIMINAR_REVOGACAO_GRATUIDADE"] = {"decisao": "EXCLUIR", "fundamento": "cenário de teste"}
        (caso_tmp / "decisoes_blocos.json").write_text(json.dumps(decisoes), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "block_composition"
        assert "não aceita decisão manual" in r["reason"]
        assert not saida.exists()


def test_gratuidade_concedida_inclui_automaticamente_a_preliminar():
    # CENÁRIO 5: gratuidade efetivamente concedida -> preliminar vinculada
    # incluída automaticamente (sem qualquer decisão em decisoes_blocos.json
    # para esse bloco) e PRELIMINARES passa a INCLUIR via ANY_CHILD_INCLUDED.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estado_processual.json").write_text(json.dumps({
            "GRATUIDADE_CONCEDIDA": {"valor": True, "fonte_documento": "decisao-fls-20.pdf"},
        }), encoding="utf-8")

        saida = Path(tmp) / "contestacao_com_revogacao.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "OK", r
        assert "PRELIMINAR_REVOGACAO_GRATUIDADE" in r["blocos_incluidos"]
        assert r["containers_derivados"]["PRELIMINARES"] == "INCLUIR"


def test_fail_closed_gratuidade_indeterminada():
    # CENÁRIO 3.1 do prompt de correção: documentos contraditórios/
    # insuficientes -> GRATUIDADE_CONCEDIDA = "INDETERMINADO" -> aborta
    # para interação com o advogado, nunca decisão silenciosa.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        (caso_tmp / "estado_processual.json").write_text(json.dumps({
            "GRATUIDADE_CONCEDIDA": "INDETERMINADO",
        }), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "block_composition"
        assert not saida.exists()


def test_fail_closed_corte_sem_efetivo():
    # CENÁRIOS 1/2: sem notícia de corte, ou só ameaça -> INCLUIR rejeitado.
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        decisoes = json.loads((caso_tmp / "decisoes_blocos.json").read_text(encoding="utf-8"))
        decisoes["LICITUDE_CORTE_SUSPENSAO"] = {"decisao": "INCLUIR", "fundamento": "cenário de teste"}
        (caso_tmp / "decisoes_blocos.json").write_text(json.dumps(decisoes), encoding="utf-8")
        # mera ameaça registrada como fato — mas CORTE_EFETIVO continua falso.
        (caso_tmp / "estado_processual.json").write_text(json.dumps({
            "CORTE_EFETIVO": False,
        }), encoding="utf-8")

        saida = Path(tmp) / "nao_deveria_existir.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "block_composition"
        assert "CORTE_EFETIVO" in r["reason"]
        assert not saida.exists()


def test_corte_efetivo_permite_inclusao_do_bloco():
    # CENÁRIO 3: corte efetivo -> bloco elegível (INCLUIR aceito).
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        caso_tmp = Path(tmp) / "caso"
        shutil.copytree(FIXTURES / "happy_path", caso_tmp)
        decisoes = json.loads((caso_tmp / "decisoes_blocos.json").read_text(encoding="utf-8"))
        decisoes["LICITUDE_CORTE_SUSPENSAO"] = {"decisao": "INCLUIR", "fundamento": "fornecimento efetivamente suspenso em 20/01/2026, conforme relato da autora e registro da concessionária"}
        (caso_tmp / "decisoes_blocos.json").write_text(json.dumps(decisoes), encoding="utf-8")
        (caso_tmp / "estado_processual.json").write_text(json.dumps({
            "CORTE_EFETIVO": True,
        }), encoding="utf-8")

        saida = Path(tmp) / "contestacao_com_corte.docx"
        r = gerar(caso_tmp, saida)

        assert r["status"] == "OK", r
        assert "LICITUDE_CORTE_SUSPENSAO" in r["blocos_incluidos"]


# ------------------------------------------------------- rastreabilidade
def test_rastreabilidade_de_execucao_no_happy_path():
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "x.docx"
        r = gerar(FIXTURES / "happy_path", saida)
        # cada stage tem nome + status verificável — não é só um "ok" solto
        for s in r["stages"]:
            assert "name" in s and "status" in s
        # a etapa estratégica tem evidência do arquivo-fonte, não só "ok"
        strategy = next(s for s in r["stages"] if s["name"] == "strategy")
        assert Path(strategy["fonte"]).name == "estrategia.md"


if __name__ == "__main__":
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in testes:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")
