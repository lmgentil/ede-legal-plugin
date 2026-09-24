#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calcular_tempestividade.py — cálculo auditável de tempestividade (TJBA/2026).

SPEC-0001 REQ-011/REQ-012, CLAUDE.md §8/§17: o cálculo produz memória
auditável e, na ausência de qualquer dado essencial (datas, calendário de
feriados forenses verificado), retorna status PENDENTE_DE_VALIDACAO em vez
de presumir. Dias úteis (fins de semana) são contados por calendário
gregoriano padrão — isso não é "invenção de fato jurídico", é aritmética.
Feriados forenses e suspensões são dado jurídico específico do TJBA e
JAMAIS são presumidos por este script: só entram no cálculo se vierem do
arquivo de calendário com "verificado": true.

Uso:
  python calcular_tempestividade.py --demo
  (uso programático: ver calcular_tempestividade() abaixo)
"""
import argparse
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).parent.parent
CALENDARIO_PADRAO = BASE / "feriados_forenses_tjba_2026.json"

PENDENTE = "PENDENTE DE VALIDAÇÃO"
TEMPESTIVO = "TEMPESTIVO"
INTEMPESTIVO = "INTEMPESTIVO"


@dataclass
class ResultadoTempestividade:
    status: str
    motivo_pendencia: str = None
    data_publicacao: str = None
    data_ciencia: str = None
    termo_inicial: str = None
    prazo_legal_dias: int = None
    tipo_prazo: str = None
    fundamento_normativo: str = None
    feriados_considerados: list = field(default_factory=list)
    suspensoes_consideradas: list = field(default_factory=list)
    termo_final: str = None

    def memoria_calculo(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def carregar_calendario(caminho: Path = CALENDARIO_PADRAO) -> dict:
    if not caminho.exists():
        return {"verificado": False}
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def _para_data(valor):
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(valor)


def _em_suspensao(dia: date, suspensoes: list) -> bool:
    for s in suspensoes:
        ini, fim = _para_data(s["inicio"]), _para_data(s["fim"])
        if ini <= dia <= fim:
            return True
    return False


def contar_termo_final_dias_uteis(termo_inicial: date, prazo_dias: int,
                                   feriados: set, suspensoes: list) -> date:
    """Conta `prazo_dias` dias úteis a partir do dia seguinte ao termo
    inicial, pulando sábados, domingos, feriados forenses e períodos de
    suspensão (CPC art. 219 e 224)."""
    dia = termo_inicial
    contados = 0
    while contados < prazo_dias:
        dia += timedelta(days=1)
        if dia.weekday() >= 5:  # sábado=5, domingo=6 — aritmética, não é dado jurídico
            continue
        if dia in feriados:
            continue
        if _em_suspensao(dia, suspensoes):
            continue
        contados += 1
    return dia


def cobertura_do_calendario(calendario: dict):
    """Janela (inicio, fim) em que o calendário verificado responde por
    TODOS os feriados e suspensões — fora dela nenhuma contagem é
    confiável (PEND-017). `None` se o calendário não a declara."""
    c = calendario.get("cobertura")
    if not isinstance(c, dict) or not c.get("inicio") or not c.get("fim"):
        return None
    return _para_data(c["inicio"]), _para_data(c["fim"])


def _dia_util(dia: date, feriados: set, suspensoes: list) -> bool:
    return dia.weekday() < 5 and dia not in feriados and not _em_suspensao(dia, suspensoes)


def derivar_publicacao(data_disponibilizacao, caminho_calendario: Path = CALENDARIO_PADRAO):
    """Publicação = primeiro dia útil seguinte à disponibilização no
    Diário de Justiça eletrônico (CPC art. 224, §§ 2º e 3º). O prazo, por
    sua vez, começa no primeiro dia útil seguinte à publicação — o que
    `contar_termo_final_dias_uteis` já faz a partir do termo inicial.

    Devolve (data_publicacao, None) ou (None, motivo) — nunca presume:
    calendário não verificado, sem janela de cobertura, ou
    disponibilização/publicação fora dela é motivo de recusa."""
    calendario = carregar_calendario(caminho_calendario)
    if not calendario.get("verificado"):
        return None, "calendário forense não verificado — publicação não pode ser derivada"
    cobertura = cobertura_do_calendario(calendario)
    if cobertura is None:
        return None, "calendário forense sem janela de cobertura declarada"
    inicio, fim = cobertura
    disponibilizacao = _para_data(data_disponibilizacao)
    if not inicio <= disponibilizacao <= fim:
        return None, (f"data de disponibilização fora do período coberto pelo calendário forense "
                      f"verificado ({inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')})")
    feriados = {_para_data(d) for d in calendario.get("feriados_forenses", [])}
    suspensoes = calendario.get("suspensoes", [])
    dia = disponibilizacao + timedelta(days=1)
    while not _dia_util(dia, feriados, suspensoes):
        dia += timedelta(days=1)
    if dia > fim:
        return None, (f"a publicação derivada ultrapassa o período coberto pelo calendário forense "
                      f"verificado (até {fim.strftime('%d/%m/%Y')})")
    return dia, None


def calcular_tempestividade(data_pratica_ato, data_publicacao=None,
                             data_ciencia=None, prazo_legal_dias=None,
                             tipo_prazo="uteis", fundamento_normativo=None,
                             caminho_calendario: Path = CALENDARIO_PADRAO,
                             verificar_cobertura: bool = False
                             ) -> ResultadoTempestividade:
    """
    data_pratica_ato: data em que o ato processual foi/será praticado
                       (ex.: protocolo da petição) — usada para concluir
                       TEMPESTIVO/INTEMPESTIVO comparando com o termo final.
    Demais parâmetros: dados do processo, cada um obrigatório para concluir
    o cálculo. Se qualquer um faltar, ou se o calendário forense não
    estiver verificado, retorna PENDENTE_DE_VALIDACAO — nunca presume.
    """
    r = ResultadoTempestividade(status=PENDENTE)

    termo_inicial_data = data_ciencia or data_publicacao
    if termo_inicial_data is None:
        r.motivo_pendencia = ("Faltam data de publicação e data de ciência — "
                               "termo inicial indeterminável.")
        return r
    if prazo_legal_dias is None:
        r.motivo_pendencia = "Falta o prazo legal em dias."
        r.termo_inicial = str(_para_data(termo_inicial_data))
        return r
    if fundamento_normativo is None:
        r.motivo_pendencia = ("Falta o fundamento normativo do prazo — "
                               "cálculo não pode ser auditável sem ele.")
        r.termo_inicial = str(_para_data(termo_inicial_data))
        return r

    calendario = carregar_calendario(caminho_calendario)
    if not calendario.get("verificado"):
        r.motivo_pendencia = (
            "Calendário forense TJBA 2026 não verificado "
            f"({caminho_calendario.name}: \"verificado\": false). "
            "Feriados forenses e suspensões não podem ser presumidos "
            "como inexistentes — sem fonte oficial, o cálculo do termo "
            "final não é confiável (CLAUDE.md §8)."
        )
        r.data_publicacao = str(_para_data(data_publicacao)) if data_publicacao else None
        r.data_ciencia = str(_para_data(data_ciencia)) if data_ciencia else None
        r.termo_inicial = str(_para_data(termo_inicial_data))
        r.prazo_legal_dias = prazo_legal_dias
        r.tipo_prazo = tipo_prazo
        r.fundamento_normativo = fundamento_normativo
        return r

    feriados = {_para_data(d) for d in calendario.get("feriados_forenses", [])}
    suspensoes = calendario.get("suspensoes", [])
    termo_inicial = _para_data(termo_inicial_data)

    if tipo_prazo == "uteis":
        termo_final = contar_termo_final_dias_uteis(
            termo_inicial, prazo_legal_dias, feriados, suspensoes)
    elif tipo_prazo == "corridos":
        termo_final = termo_inicial + timedelta(days=prazo_legal_dias)
        # dia corrido que cai em feriado/fim de semana prorroga para o
        # próximo dia útil (regra geral processual)
        while termo_final.weekday() >= 5 or termo_final in feriados \
                or _em_suspensao(termo_final, suspensoes):
            termo_final += timedelta(days=1)
    else:
        r.motivo_pendencia = f"tipo_prazo desconhecido: {tipo_prazo!r}"
        return r

    if verificar_cobertura:
        # PEND-017 (ADR-0021): fora da janela do calendário verificado a
        # contagem ignoraria feriados/suspensões não cadastrados (ex.:
        # recesso a partir de 20/12, CPC art. 220) — recusa, nunca conta.
        cobertura = cobertura_do_calendario(calendario)
        if cobertura is None or not (cobertura[0] <= termo_inicial and termo_final <= cobertura[1]):
            limite = cobertura[1].strftime("%d/%m/%Y") if cobertura else "não declarado"
            r.motivo_pendencia = (
                f"a contagem do prazo ultrapassa o período coberto pelo calendário forense "
                f"verificado (até {limite}); é necessário o calendário oficial do período seguinte")
            r.termo_inicial = str(termo_inicial)
            return r

    ato = _para_data(data_pratica_ato)
    status = TEMPESTIVO if ato <= termo_final else INTEMPESTIVO

    return ResultadoTempestividade(
        status=status,
        data_publicacao=str(_para_data(data_publicacao)) if data_publicacao else None,
        data_ciencia=str(_para_data(data_ciencia)) if data_ciencia else None,
        termo_inicial=str(termo_inicial),
        prazo_legal_dias=prazo_legal_dias,
        tipo_prazo=tipo_prazo,
        fundamento_normativo=fundamento_normativo,
        feriados_considerados=sorted(str(d) for d in feriados
                                      if termo_inicial <= d <= termo_final),
        suspensoes_consideradas=suspensoes,
        termo_final=str(termo_final),
    )


def _demo():
    """Autoteste executável (`python calcular_tempestividade.py --demo`).
    Ponytail: menor verificação que já pega regressão no guard fail-closed
    e na aritmética de dias úteis."""
    import tempfile

    # 1) calendário explicitamente não verificado (stub) -> PENDENTE, nunca
    #    calcula termo final
    stub_nao_verificado = {"verificado": False}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      encoding="utf-8") as f:
        json.dump(stub_nao_verificado, f)
        caminho_nao_verificado = Path(f.name)
    try:
        r = calcular_tempestividade(
            data_pratica_ato="2026-03-10", data_publicacao="2026-02-01",
            prazo_legal_dias=15, fundamento_normativo="art. 335 CPC",
            caminho_calendario=caminho_nao_verificado)
        assert r.status == PENDENTE, r
        assert r.termo_final is None, "não pode calcular termo final sem calendário verificado"
        assert "não verificado" in r.motivo_pendencia
    finally:
        caminho_nao_verificado.unlink(missing_ok=True)

    # 2) falta data essencial -> PENDENTE antes mesmo de olhar o calendário
    r2 = calcular_tempestividade(data_pratica_ato="2026-03-10",
                                  prazo_legal_dias=15,
                                  fundamento_normativo="art. 335 CPC")
    assert r2.status == PENDENTE
    assert "termo inicial" in r2.motivo_pendencia

    # 3) calendário TJBA 2026 real (feriados_forenses_tjba_2026.json, agora
    #    verificado=true), contra o "Exemplo verificado" do próprio
    #    SKILL.md desta skill: intimação 15/05/2026 (sexta) -> pagamento
    #    15 dias úteis vence em 09/06/2026 -> impugnação, outros 15 dias
    #    úteis, vence em 07/07/2026. Isto valida a transcrição do calendário
    #    E a aritmética, contra um caso real conferido pelo usuário.
    r3 = calcular_tempestividade(
        data_pratica_ato="2026-06-09", data_publicacao="2026-05-15",
        prazo_legal_dias=15, fundamento_normativo="art. 523 c/c 219 CPC")
    assert r3.termo_final == "2026-06-09", (
        f"esperado 2026-06-09 pelo SKILL.md, obtido {r3.termo_final}")
    assert r3.status == TEMPESTIVO

    r4 = calcular_tempestividade(
        data_pratica_ato="2026-07-07", data_publicacao="2026-06-09",
        prazo_legal_dias=15, fundamento_normativo="art. 525 CPC")
    assert r4.termo_final == "2026-07-07", (
        f"esperado 2026-07-07 pelo SKILL.md, obtido {r4.termo_final}")
    assert r4.status == TEMPESTIVO

    print("OK — 4/4 checagens passaram (fail-closed sem calendário "
          "verificado; fail-closed sem data; calendário TJBA 2026 real "
          "batendo com o \"Exemplo verificado\" do SKILL.md).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true",
                     help="roda o autoteste e sai")
    args = ap.parse_args()
    if args.demo:
        _demo()
    else:
        print("Calendário forense TJBA 2026: "
              f"verificado={carregar_calendario().get('verificado')}. "
              "Use --demo para o autoteste, ou importe "
              "calcular_tempestividade() para uso programático.")
