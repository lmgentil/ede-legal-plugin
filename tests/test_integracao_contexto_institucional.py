#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_integracao_contexto_institucional.py — Etapa 5.7-C
(INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA, SPEC-0001 §57): demonstra que a
extração de contexto institucional faz parte FORMAL e OBRIGATÓRIA da
orquestração (`scripts/gerar_contestacao.py`), não apenas uma instrução
comportamental em SKILL.md — a sequência obrigatória:

    contexto extraído -> contexto disponível -> Redator autorizado

e o inverso:

    contexto ausente/falha -> Redator NÃO autorizado

"Redator autorizado" é operacionalizado aqui, no nível de código, como:
o pipeline só chega a `drafting_humanization` (a etapa que consome
`placeholders.json` — a SAÍDA do redator/humanizer, único ponto onde este
script "enxerga" o resultado do redator, já que Skills não são chamáveis
de Python, mesma limitação documentada em `scripts/gerar_contestacao.py`)
se `contexto_institucional` já tiver sido a PRIMEIRA etapa concluída com
sucesso na mesma execução. Falha na extração aborta o pipeline antes de
qualquer outra etapa — inclusive antes de ler um único documento do caso.

LOCAL_ONLY — SKIP explícito se o modelo-oficial.docx real não existir
localmente (ADR-0006).

Uso:
  python tests/test_integracao_contexto_institucional.py
"""
import hashlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "rag"))
sys.path.insert(0, str(BASE / "skills" / "calendario-forense-tjba-2026" / "scripts"))

import gerar_contestacao  # noqa: E402
# reaproveita o stub de JUIZO já usado por test_e2e_contestacao.py (fixture
# happy_path usa um número de processo fictício, que a API real do DataJud
# nunca vai encontrar — nenhum teste depende de rede) em vez de duplicá-lo.
from test_e2e_contestacao import _resolver_juizo_stub  # noqa: E402

TEMPLATE_REAL = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_REAL = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_REAL = BASE / "templates" / "contestacao" / "blocos.json"
FIXTURES = BASE / "tests" / "fixtures" / "contestacao"

pytestmark = pytest.mark.docx_real

PLACEHOLDERS_GERATIVOS_ESPERADOS = {
    "TEMPESTIVIDADE_CASO", "SINOPSE_FATOS", "REALIDADE_FATICA",
    "IRREGULARIDADE_ENCONTRADA", "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE",
    "PEDIDOS_FINAIS",
}
PLACEHOLDERS_DETERMINISTICOS = {
    "JUIZO", "FOTOS_DA_IRREGULARIADE", "NUMERO_PROCESSO", "AUTOR",
    "VALOR_FRA", "VALOR_DANO_MORAL_PRETENDIDO", "LOCAL_DATA",
}
# Etapa 5.8-B: zona é ponto gerativo (o Redator precisa do contexto
# institucional para aplicar o teste de necessidade), mas NÃO é
# placeholder — vem do catálogo, não do schema. Lida do catálogo real em
# vez de hardcoded aqui, para que este teste continue exato quando uma
# zona futura for autorizada.
ZONAS_ESPERADAS = {
    z["id"] for z in json.loads(CATALOGO_REAL.read_text(encoding="utf-8")).get("zones", [])
}


def _pular_se_sem_template_real():
    if not TEMPLATE_REAL.exists():
        print(f"SKIP: {TEMPLATE_REAL} não existe localmente (esperado — "
              "template institucional fora do git, ADR-0006).")
        return True
    return False


# --------------------------------------------------------------- 1: caminho feliz
def test_contexto_extraido_contexto_disponivel_redator_autorizado():
    """Sequência positiva: extração é a PRIMEIRA etapa, sucede, e o
    pipeline só chega a `drafting_humanization` (consumo da saída do
    redator/humanizer) depois dela."""
    if _pular_se_sem_template_real():
        return
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "contestacao.docx"
        r = gerar_contestacao.gerar(FIXTURES / "happy_path", saida,
                                     resolver_juizo_fn=_resolver_juizo_stub)

        assert r["status"] == "OK", r
        assert r["contexto_institucional"] == "OK"

        stages = r["stages"]
        assert stages[0]["name"] == "contexto_institucional"
        assert stages[0]["status"] == "ok"

        nomes = [s["name"] for s in stages]
        idx_contexto = nomes.index("contexto_institucional")
        idx_redator = nomes.index("drafting_humanization")
        assert idx_contexto < idx_redator, (
            "a extração de contexto institucional precisa concluir ANTES "
            "da etapa que consome a saída do redator/humanizer")


def test_contexto_disponibilizado_e_apenas_o_gerativo():
    """Item 4/5 do pedido: só os 6 placeholders efetivamente redigidos
    pela IA recebem contexto — placeholders determinísticos/documentais
    (JUIZO/FOTOS/NUMERO_PROCESSO/AUTOR/valores) nunca aparecem aqui, e
    esta etapa nunca passa a "gerá-los" no lugar de DataJud/script/
    extração factual."""
    if _pular_se_sem_template_real():
        return
    stages = []
    contexto = gerar_contestacao._etapa_contexto_institucional(
        TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL, stages)
    assert set(contexto.keys()) == PLACEHOLDERS_GERATIVOS_ESPERADOS | ZONAS_ESPERADAS
    assert not (set(contexto.keys()) & PLACEHOLDERS_DETERMINISTICOS)
    # a zona nunca é confundida com placeholder no contexto entregue ao Redator
    for zid in ZONAS_ESPERADAS:
        assert contexto[zid][0]["tipo"] == "zona"
        assert contexto[zid][0]["normalmente_vazia"] is True


# --------------------------------------------------------------- 2: caminho inverso
def test_contexto_ausente_redator_nao_autorizado():
    """Sequência negativa (o inverso pedido explicitamente): template
    ausente -> falha na PRIMEIRA etapa -> pipeline aborta antes de
    qualquer outra coisa -> `drafting_humanization` (proxy code-level de
    "a saída do redator foi consumida") NUNCA aparece nas stages, mesmo
    que placeholders.json já exista pronto no caso (fixture happy_path
    tem o arquivo — a ausência de contexto barra o pipeline mesmo assim,
    antes de sequer abrir esse arquivo)."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deveria_existir.docx"
        template_inexistente = Path(tmp) / "modelo-oficial-inexistente.docx"
        r = gerar_contestacao.gerar(FIXTURES / "happy_path", saida,
                                     template=template_inexistente)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "contexto_institucional"
        nomes = [s["name"] for s in r["stages"]]
        assert nomes == ["contexto_institucional"]
        assert "drafting_humanization" not in nomes
        assert not saida.exists()


def test_contexto_corrompido_tambem_barra_o_redator():
    """Template presente mas não é um .docx válido (zip corrompido) —
    mesma barreira, mesmo stage; nunca degrada para gerar sem contexto."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "nao_deveria_existir.docx"
        template_corrompido = Path(tmp) / "modelo-oficial.docx"
        template_corrompido.write_bytes(b"isto nao e um docx valido")
        r = gerar_contestacao.gerar(FIXTURES / "happy_path", saida,
                                     template=template_corrompido)

        assert r["status"] == "PIPELINE_ABORTED"
        assert r["stage"] == "contexto_institucional"
        assert [s["name"] for s in r["stages"]] == ["contexto_institucional"]
        assert not saida.exists()


# --------------------------------------------------------------- item 10: hash, não transcrição
def test_hash_reportado_e_do_template_corrente_desta_execucao():
    if _pular_se_sem_template_real():
        return
    hash_esperado = hashlib.sha256(TEMPLATE_REAL.read_bytes()).hexdigest()
    stages = []
    gerar_contestacao._etapa_contexto_institucional(TEMPLATE_REAL, SCHEMA_REAL, CATALOGO_REAL, stages)
    assert stages[0]["template_hash_sha256"] == hash_esperado


def test_etapa_nao_le_arquivo_de_caso_nenhum_so_o_template_ao_vivo():
    """Garantia estrutural (item 10 — 'nunca de conteúdo transcrito
    manualmente'): a assinatura da etapa nem aceita um diretório de caso
    — é fisicamente impossível ela ler um `contexto_institucional.json`
    pré-existente/desatualizado como fonte, só o `.docx` ao vivo passado
    em `template`."""
    parametros = set(inspect.signature(gerar_contestacao._etapa_contexto_institucional).parameters)
    assert parametros == {"template", "schema_path", "catalogo_blocos", "stages"}
    assert "caso" not in parametros


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
