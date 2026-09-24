#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proveito_economico.py — soma do proveito econômico pretendido e
comparação com o valor da causa (ADR-0021, SPEC-0001 §64.4).

Divisão de trabalho: o HOST extrai da petição inicial os pedidos
economicamente mensuráveis, cada um com a fonte documental; este módulo
só faz a aritmética, em `Decimal` (nunca float para dinheiro). Pedido
sem valor quantificado na inicial é declarado como tal e nunca somado
como zero.

Não há limiar de "materialidade" aqui: dizer se uma diferença é
juridicamente relevante é juízo jurídico, não aritmética (CLAUDE.md §7 —
nenhuma heurística jurídica em Python). O módulo devolve os números
exatos; a conclusão ao advogado é do host, e a decisão de manter ou
retirar o tópico continua sendo do advogado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_VALOR_BR_RE = re.compile(r"^\s*(?:R\$\s?)?(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*$")

MAX_PEDIDOS = 20


class EntradaProveitoInvalida(ValueError):
    """Pedido malformado (sem descrição/fonte, valor fora do formato
    monetário brasileiro). Mensagem sem conteúdo do caso além do índice."""


def valor_para_decimal(texto: str) -> Decimal:
    """'R$ 1.234,56' ou '1.234,56' -> Decimal('1234.56'). Qualquer outro
    formato é recusado — nunca adivinhado."""
    m = _VALOR_BR_RE.match(str(texto or ""))
    if not m:
        raise EntradaProveitoInvalida("valor fora do formato monetário brasileiro (ex.: R$ 1.234,56)")
    try:
        return Decimal(m.group(1).replace(".", "") + "." + m.group(2))
    except InvalidOperation as e:  # defensivo: a regex já garante dígitos
        raise EntradaProveitoInvalida("valor monetário ilegível") from e


def formatar_brl(valor: Decimal, com_simbolo: bool = True) -> str:
    q = valor.quantize(Decimal("0.01"))
    sinal = "-" if q < 0 else ""
    inteiro, centavos = f"{abs(q):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    texto = f"{sinal}{'.'.join(grupos)},{centavos}"
    return f"R$ {texto}" if com_simbolo else texto


@dataclass(frozen=True)
class ResultadoProveito:
    total: Decimal
    valor_da_causa: Decimal
    diferenca: Decimal
    """valor da causa − total (positivo: causa acima do proveito)."""
    pedidos_quantificados: int
    pedidos_sem_valor: tuple[str, ...]

    @property
    def cumulacao_economica(self) -> bool:
        """Mais de um pedido com conteúdo econômico (quantificado ou não)."""
        return self.pedidos_quantificados + len(self.pedidos_sem_valor) > 1

    def resumo(self) -> str:
        """Frase neutra, só com números — nunca juízo de relevância."""
        partes = [f"Soma dos pedidos com valor na inicial: {formatar_brl(self.total)}",
                  f"valor atribuído à causa: {formatar_brl(self.valor_da_causa)}"]
        if self.diferenca == 0:
            partes.append("os valores coincidem")
        else:
            partes.append(f"diferença de {formatar_brl(abs(self.diferenca))}")
        texto = "; ".join(partes) + "."
        if self.pedidos_sem_valor:
            texto += (f" {len(self.pedidos_sem_valor)} pedido(s) sem valor quantificado na inicial "
                      f"não entraram na soma.")
        return texto


def calcular_proveito(pedidos: list, valor_da_causa: str) -> ResultadoProveito:
    """`pedidos`: lista de {"descricao", "valor" (texto monetário ou
    None/""), "fonte"}. `valor_da_causa`: o valor atribuído pela inicial
    (mesmo formato)."""
    if not isinstance(pedidos, list) or not pedidos:
        raise EntradaProveitoInvalida("informe ao menos um pedido economicamente mensurável")
    if len(pedidos) > MAX_PEDIDOS:
        raise EntradaProveitoInvalida(f"no máximo {MAX_PEDIDOS} pedidos")
    total = Decimal("0.00")
    quantificados = 0
    sem_valor = []
    for i, p in enumerate(pedidos):
        if not isinstance(p, dict):
            raise EntradaProveitoInvalida(f"pedido[{i}] não é um objeto")
        descricao = str(p.get("descricao") or "").strip()
        fonte = str(p.get("fonte") or "").strip()
        if not descricao or not fonte:
            raise EntradaProveitoInvalida(f"pedido[{i}] sem descrição ou sem fonte documental")
        valor = p.get("valor")
        if valor is None or not str(valor).strip():
            sem_valor.append(descricao)
            continue
        total += valor_para_decimal(valor)
        quantificados += 1
    causa = valor_para_decimal(valor_da_causa)
    return ResultadoProveito(total=total, valor_da_causa=causa, diferenca=causa - total,
                             pedidos_quantificados=quantificados, pedidos_sem_valor=tuple(sem_valor))
