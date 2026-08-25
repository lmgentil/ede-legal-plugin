#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_infra_garantir_utf8_import_safe.py — guarda de infraestrutura: importar
módulos que usam garantir_utf8()/reexecutar_utf8() (scripts/docx_template_
engine.py) nunca pode encerrar o processo do importador.

Achado real: garantir_utf8() era chamada no nível de módulo (fora de
main()/`if __name__ == "__main__":`) em scripts/gerar_contestacao.py,
tests/test_template_engine.py e tests/test_argumentacao_evolucao_consumo_
removida.py — no Windows, sem PEP 540 ativo, isso disparava sys.exit()
durante o próprio `import`, e o pytest 9.1.1 aborta a fase de collection
com INTERNALERROR ao encontrar um SystemExit inesperado no meio da
importação de um módulo de teste (0 testes executados). Correção:
reexecutar_utf8() (biblioteca) nunca chama sys.exit() — só retorna um
código de saída ou None; apenas garantir_utf8() (entrypoint de CLI),
chamada só a partir de main()/`__main__`, converte isso em sys.exit().

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__":`.
"""
import importlib
import subprocess
import sys
from pathlib import Path
from unittest import mock

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import docx_template_engine  # noqa: E402


# A. importar scripts/docx_template_engine.py não encerra o processo (já
# aconteceu ao importar acima, no nível de módulo deste arquivo — chegar
# até aqui já é a prova; reforçado explicitamente por clareza do teste).
def test_import_docx_template_engine_nao_encerra_processo():
    importlib.reload(docx_template_engine)


# B. importar os módulos historicamente quebrados não provoca SystemExit,
# em subprocesso limpo — reproduz exatamente o que pytest faz na collection.
def test_import_modulos_antes_quebrados_nao_gera_systemexit():
    alvos = [
        "scripts/gerar_contestacao.py",
        "tests/test_template_engine.py",
        "tests/test_argumentacao_evolucao_consumo_removida.py",
    ]
    for alvo in alvos:
        r = subprocess.run(
            [sys.executable, "-c", f"import runpy; runpy.run_path(r'{BASE / alvo}')"],
            cwd=str(BASE), capture_output=True, text=True,
        )
        assert r.returncode == 0, (
            f"importar {alvo} encerrou o processo (returncode={r.returncode}): "
            f"{r.stderr[-2000:]}"
        )


# C. reexecutar_utf8() (biblioteca) preserva o comportamento funcional:
# quando o reexec é necessário, ainda relança via subprocess e devolve o
# returncode do filho — nunca chama sys.exit() sozinha.
def test_reexecutar_utf8_relanca_quando_necessario_sem_sys_exit():
    with mock.patch.object(docx_template_engine, "_precisa_reexec_utf8", return_value=True), \
         mock.patch("subprocess.run") as m_run:
        m_run.return_value = mock.Mock(returncode=7)
        codigo = docx_template_engine.reexecutar_utf8()
    assert codigo == 7
    assert m_run.called


def test_reexecutar_utf8_no_op_quando_ja_utf8():
    with mock.patch.object(docx_template_engine, "_precisa_reexec_utf8", return_value=False), \
         mock.patch("subprocess.run") as m_run:
        codigo = docx_template_engine.reexecutar_utf8()
    assert codigo is None
    assert not m_run.called


# D. falha real de validação (returncode != 0 do subprocesso relançado)
# continua propagada — só de forma controlada (sys.exit no ponto certo,
# não como efeito colateral de import).
# E. entrypoint CLI (garantir_utf8) ainda converte isso em sys.exit() com o
# código de saída apropriado.
def test_garantir_utf8_cli_propaga_falha_via_sys_exit():
    with mock.patch.object(docx_template_engine, "reexecutar_utf8", return_value=1):
        try:
            docx_template_engine.garantir_utf8()
        except SystemExit as e:
            assert e.code == 1
        else:
            raise AssertionError("garantir_utf8() deveria ter chamado sys.exit(1)")


def test_garantir_utf8_cli_nao_sai_quando_reexec_nao_e_necessario():
    with mock.patch.object(docx_template_engine, "reexecutar_utf8", return_value=None):
        docx_template_engine.garantir_utf8()  # não deve levantar SystemExit


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
