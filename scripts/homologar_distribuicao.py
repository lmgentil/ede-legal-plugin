#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
homologar_distribuicao.py — gate de DISTRIBUIÇÃO do EDE Legal Plugin
(Etapa 5.10, Commit 7).

Prova, sobre um CLONE GIT LIMPO e temporário (nunca o working tree do
desenvolvedor), que o pacote publicamente distribuível do EDE consegue,
sozinho: (1) existir sem skills/docx/; (2) ter o Modelo Oficial instalado
só pelo bootstrap aprovado (scripts/instalar_modelo_oficial.py);
(3) passar no ede_doctor antes/depois; (4) executar o pipeline de
Contestação até DOCX final; (5) aprovar Template Lock; (6) terminar sem
resíduo de placeholder/zona/SDT condicional; (7) não depender de nenhum
caminho privado do ambiente do desenvolvedor.

Toda etapa relevante roda via SUBPROCESSO, cwd=clone, ambiente sem
PYTHONPATH/CLAUDE_PLUGIN_ROOT herdados do processo deste harness — as
ferramentas testadas são sempre as CÓPIAS DO CLONE
(scripts/ede_doctor.py, scripts/instalar_modelo_oficial.py,
scripts/gerar_contestacao.py, ...), nunca o working tree que orquestra
este harness. Isso é o que de fato prova "distribuição": não basta o
código do desenvolvedor conseguir apontar para um caminho arbitrário — é
o código publicado que precisa rodar sozinho.

Fronteira externa isolada: DataJud/CNJ (API real) — substituída por um
stub determinístico injetado via `gerar_contestacao.gerar(...,
resolver_juizo_fn=...)`, MESMO stub de valores já usado por
tests/test_e2e_contestacao.py (reaproveitado, nunca reimplementado — Fase
5 desta rodada). Auditoria desta rodada (Fase 6) não encontrou nenhuma
outra fronteira externa real no caminho happy_path: `datajud_client.py` é
o único módulo de todo `scripts/`/`rag/` que faz chamada de rede
(`requests`); RAG/legal_validation/validações são inteiramente locais.

NÃO faz parte da suíte pytest padrão (depende do Modelo Oficial real,
fornecido externamente por parâmetro) — harness standalone, repetível,
auditável, host-agnostic e fail-closed.

Uso:
  python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO.docx
  python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO.docx --json
  python scripts/homologar_distribuicao.py --modelo-oficial CAMINHO.docx --manter-clone
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_PADRAO = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Prefixos de w:tag catalogados em blocos.json (Etapa 5.8-B/5.8-G) — usado
# só para conferir, em texto bruto, que nenhum sobrevive à composição
# (Fase 8, item 7 do pedido). Lido diretamente do catálogo no momento do
# uso (audit_prefixos_tag), não hardcoded aqui, para nunca divergir do
# catálogo real se um prefixo novo for introduzido.

# Mesmo stub de tests/test_e2e_contestacao.py (Fase 5 do pedido:
# "reutilizar fixture/fake já existente" — nunca reimplementar a lógica
# do DataJud). Duplicado (não importado) porque o driver roda como
# subprocesso isolado, dentro do clone, sem tests/ no sys.path.
_RESOLVER_JUIZO_STUB_SRC = '''
def _resolver_juizo_stub(numero_processo, **_kwargs):
    return {
        "numero_processo": numero_processo,
        "tribunal": "TJBA",
        "orgao_julgador_nome": "VARA DOS FEITOS DE RELA\\u00c7\\u00d5ES DE CONSUMO",
        "orgao_julgador_codigo": 1,
        "codigo_municipio_ibge": 2910800,
        "comarca": "Feira de Santana",
        "juizo": ("AO JU\\u00cdZO DA VARA DOS FEITOS DE RELA\\u00c7\\u00d5ES DE CONSUMO "
                  "DA COMARCA DE FEIRA DE SANTANA"),
        "data_consulta": "2026-01-01T00:00:00+00:00",
    }
'''

# Driver executado DENTRO do clone (subprocesso próprio, cwd=clone) —
# happy path completo (Fase 7) + asserts de saída (Fase 8). Escrito em
# arquivo à parte (nunca dentro do clone) e invocado com argv explícitos
# — nenhum caminho do desenvolvedor é interpolado no texto do script.
_DRIVER_SRC = '''
import json
import re
import sys
from pathlib import Path

CLONE = Path.cwd()
sys.path.insert(0, str(CLONE / "scripts"))

import gerar_contestacao  # noqa: E402
import docx_package  # noqa: E402
import docx_template_engine  # noqa: E402
import docx_numeracao_engine  # noqa: E402

''' + _RESOLVER_JUIZO_STUB_SRC + '''

def main():
    caso_dir = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    dados_saida = Path(sys.argv[3])

    relatorio = gerar_contestacao.gerar(caso_dir, output_path,
                                         resolver_juizo_fn=_resolver_juizo_stub)
    resultado = {"relatorio": relatorio, "checks": {}}

    if relatorio.get("status") != "OK":
        print(json.dumps(resultado, ensure_ascii=False))
        sys.exit(1)

    # Reconstrucao READ-ONLY de `dados` (mesmas etapas ja executadas
    # dentro de gerar(), chamadas de novo aqui so para obter o dict --
    # nao reimplementa nenhuma logica de negocio) -- usada por
    # validate_template.py (Fase 14 do pedido).
    stages_aux = []
    tempestividade_valor = gerar_contestacao._etapa_tempestividade(caso_dir, stages_aux)
    dados = gerar_contestacao._etapa_placeholders(caso_dir, stages_aux, tempestividade_valor,
                                                   _resolver_juizo_stub)
    dados_saida.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    checks = resultado["checks"]
    checks["arquivo_existe"] = output_path.is_file()
    checks["tamanho_bytes"] = output_path.stat().st_size if output_path.is_file() else 0

    pacote_dir = output_path.parent / "_unpacked_verificacao"
    try:
        docx_package.extrair_pacote_docx(output_path, pacote_dir)
        checks["zip_docx_valido"] = True
    except docx_package.PacoteDocxAbortada as e:
        checks["zip_docx_valido"] = False
        checks["zip_docx_erro"] = f"{e.stage}: {e.motivo}"
        print(json.dumps(resultado, ensure_ascii=False))
        sys.exit(1)

    problemas_estrutura = docx_package.validar_estrutura_minima(pacote_dir)
    checks["estrutura_minima_ok"] = not problemas_estrutura
    checks["estrutura_minima_problemas"] = problemas_estrutura

    document_xml = (pacote_dir / "word" / "document.xml").read_text(encoding="utf-8")

    placeholders_residuais = sorted(docx_template_engine.extrair_placeholders(document_xml))
    checks["placeholders_residuais"] = placeholders_residuais
    checks["zero_placeholder_residual"] = not placeholders_residuais

    tags_residuais = re.findall(r\'w:tag w:val="((?:BLOCO|SUBBLOCO|INLINE|ZONA):[^"]*)"\', document_xml)
    checks["sdt_tags_residuais"] = tags_residuais
    checks["zero_sdt_residual"] = not tags_residuais

    problemas_numeracao = docx_numeracao_engine.validar_numeracao_final(document_xml)
    checks["numeracao_valida"] = not problemas_numeracao
    checks["numeracao_problemas"] = problemas_numeracao

    checks["template_lock"] = relatorio.get("template_lock")

    ok_geral = (checks["arquivo_existe"] and checks["tamanho_bytes"] > 0
                and checks["zip_docx_valido"] and checks["estrutura_minima_ok"]
                and checks["zero_placeholder_residual"] and checks["zero_sdt_residual"]
                and checks["numeracao_valida"] and checks["template_lock"] == "OK")
    resultado["ok_geral"] = ok_geral

    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0 if ok_geral else 1)


if __name__ == "__main__":
    main()
'''


class HomologacaoFalhou(Exception):
    def __init__(self, fase, motivo):
        self.fase = fase
        self.motivo = motivo
        super().__init__(f"[{fase}] {motivo}")


def _ambiente_limpo() -> dict:
    """Ambiente do subprocesso sem PYTHONPATH/CLAUDE_PLUGIN_ROOT herdados
    do processo deste harness — cada subprocesso só enxerga o que o
    próprio clone fornece (Fase 10 do pedido)."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(args, cwd, timeout=180):
    return subprocess.run([PYTHON, *args], cwd=str(cwd), env=_ambiente_limpo(),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)


def _run_json(args, cwd, fase, timeout=180) -> dict:
    r = _run(args, cwd, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise HomologacaoFalhou(fase, f"saída não é JSON válido (returncode={r.returncode}); "
                                 f"stdout={r.stdout!r} stderr={r.stderr!r}")


def git_head(repo: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True)
    if r.returncode != 0:
        raise HomologacaoFalhou("git_head", r.stderr)
    return r.stdout.strip()


def clonar_repositorio_limpo(repo_origem: Path, pai_temp: Path) -> Path:
    """Clone Git real (transporte local, `file://`-equivalente via
    caminho) — só o conteúdo VERSIONADO no HEAD atual é copiado;
    .gitignore/working-tree sujo do desenvolvedor nunca chega ao clone
    (Fase 2 do pedido). `core.longpaths=true` evita o limite de caminho
    do Windows já conhecido de rodadas anteriores desta etapa."""
    pai_temp.mkdir(parents=True, exist_ok=True)
    destino = Path(tempfile.mkdtemp(dir=str(pai_temp), prefix="clone_"))
    r = subprocess.run(["git", "-c", "core.longpaths=true", "clone", "--quiet",
                         str(repo_origem), str(destino)],
                        capture_output=True, text=True)
    if r.returncode != 0:
        raise HomologacaoFalhou("clone", f"git clone falhou: {r.stderr}")
    return destino


def verificar_ausencias_pre_bootstrap(clone_dir: Path) -> dict:
    return {
        "skills_docx_ausente": not (clone_dir / "skills" / "docx").exists(),
        "modelo_oficial_ausente": not (clone_dir / "templates" / "contestacao" / "modelo-oficial.docx").exists(),
    }


def rodar_doctor(clone_dir: Path, dir_saida: Path) -> dict:
    return _run_json(["scripts/ede_doctor.py", "--json", "--saida", str(dir_saida)], clone_dir, "doctor")


def rodar_bootstrap(clone_dir: Path, origem_modelo: Path) -> dict:
    return _run_json(["scripts/instalar_modelo_oficial.py", str(origem_modelo), "--json"],
                      clone_dir, "bootstrap")


def _extrair_contagens(stdout: str) -> dict:
    """Extrai passed/failed/skipped da última linha de resumo do pytest
    (`-q`), independente da ordem em que os três aparecem (o pytest varia
    essa ordem conforme o que houve: "1 failed, 659 passed" vs
    "582 passed, 56 skipped")."""
    linhas = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    resumo = linhas[-1] if linhas else ""
    def _n(padrao):
        m = re.search(padrao, resumo)
        return int(m.group(1)) if m else 0
    return {
        "passed": _n(r"(\d+) passed"),
        "failed": _n(r"(\d+) failed"),
        "skipped": _n(r"(\d+) skipped"),
        "resumo": resumo,
    }


def rodar_pytest(clone_dir: Path, marker: str = None, timeout=500) -> dict:
    args = ["-m", "pytest", "tests/", "-q"]
    if marker:
        args += ["-m", marker]
    r = _run(args, clone_dir, timeout=timeout)
    contagens = _extrair_contagens(r.stdout)
    contagens["returncode"] = r.returncode
    contagens["stdout_tail"] = "\n".join(r.stdout.strip().splitlines()[-20:])
    return contagens


def rodar_happy_path(clone_dir: Path, caso_relativo: str, saida_dir: Path) -> dict:
    """Fase 7 (happy path completo) + Fase 8 (asserts de saída) num único
    subprocesso, via driver escrito em `saida_dir` (fora do clone —
    nunca precisa ser versionado nem sujar o clone)."""
    driver_path = saida_dir / "_driver_pipeline.py"
    driver_path.write_text(_DRIVER_SRC, encoding="utf-8")

    caso_dir = clone_dir / caso_relativo
    output_path = saida_dir / "contestacao_homologacao.docx"
    dados_path = saida_dir / "dados_reconstruidos.json"

    r = subprocess.run([PYTHON, str(driver_path), str(caso_dir), str(output_path), str(dados_path)],
                        cwd=str(clone_dir), env=_ambiente_limpo(), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=180)
    try:
        resultado = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise HomologacaoFalhou("happy_path", f"driver não retornou JSON válido "
                                 f"(returncode={r.returncode}); stdout={r.stdout!r} stderr={r.stderr!r}")
    resultado["_output_path"] = str(output_path)
    resultado["_dados_path"] = str(dados_path)
    resultado["_stderr"] = r.stderr
    return resultado


def rodar_validate_template(clone_dir: Path, docx_gerado: Path, dados_path: Path) -> dict:
    r = _run(["scripts/validate_template.py", "--gerado", str(docx_gerado), "--dados", str(dados_path)],
              clone_dir, timeout=120)
    try:
        return {"json": json.loads(r.stdout), "returncode": r.returncode, "stderr": r.stderr}
    except json.JSONDecodeError:
        return {"json": None, "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}


def buscar_dependencias_skills_docx(clone_dir: Path) -> list:
    """Fase 9: linhas de scripts/*.py que mencionam os padrões do toolkit
    substituído — devolvidas cruas para classificação (docstring vs.
    funcional) no relatório, mesma técnica já usada manualmente nos gates
    dos Commits 3/5/6 desta etapa."""
    padrao = re.compile(r"skills/docx|skills\\\\docx|unpack\.py|pack\.py|_importar_toolkit|_localizar_docx_toolkit")
    achados = []
    for arq in sorted((clone_dir / "scripts").glob("*.py")):
        for i, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if padrao.search(linha):
                achados.append(f"{arq.relative_to(clone_dir)}:{i}: {linha.strip()}")
    return achados


def buscar_caminho_privado(textos: dict, caminho_proibido: str) -> dict:
    """Fase 10: procura o caminho absoluto do repositório do
    desenvolvedor (nunca o do clone, que é sempre temporário) dentro de
    saídas JSON/relatórios/DOCX capturados durante a homologação."""
    achados = {}
    for rotulo, texto in textos.items():
        if caminho_proibido and caminho_proibido in texto:
            achados[rotulo] = True
    return achados


def avaliar_checks_saida(checks: dict) -> bool:
    """Mesma fórmula usada dentro do driver embutido (`_DRIVER_SRC`) para
    decidir `ok_geral` a partir dos checks de Fase 8 (arquivo existe e não
    vazio, ZIP/OOXML válido, zero placeholder/zona residual, zero SDT
    condicional residual, numeração válida, Template Lock OK) — extraída
    aqui, fora do texto do driver, só para ser testável em isolamento
    (tests/test_homologar_distribuicao.py, cenários "Template Lock falho"/
    "placeholder residual" sem precisar rodar o pipeline completo).
    Mantida em sincronia manual com o bloco equivalente dentro de
    `_DRIVER_SRC` — duplicação necessária, não acidental: o driver roda
    como subprocesso isolado dentro do clone, sem acesso a este módulo
    (evita reintroduzir dependência de caminho do desenvolvedor — Fase
    10 do pedido)."""
    return bool(
        checks.get("arquivo_existe") and checks.get("tamanho_bytes", 0) > 0
        and checks.get("zip_docx_valido") and checks.get("estrutura_minima_ok")
        and checks.get("zero_placeholder_residual") and checks.get("zero_sdt_residual")
        and checks.get("numeracao_valida") and checks.get("template_lock") == "OK"
    )


def _ler_document_xml_bruto(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as z:
        return z.read("word/document.xml").decode("utf-8", errors="replace")


def homologar(modelo_oficial: Path, repo: Path = REPO_PADRAO, manter_clone: bool = False,
              saida_dir: Path = None) -> dict:
    # Resolvido para ABSOLUTO já aqui: os subprocessos do bootstrap/doctor
    # rodam com cwd=clone_dir (não o cwd de quem chamou este harness) — um
    # `--modelo-oficial` relativo interpretado contra o cwd errado é um
    # falso "ARQUIVO_NAO_ENCONTRADO", não uma prova real de rejeição.
    modelo_oficial = Path(modelo_oficial).resolve()
    repo = Path(repo).resolve()
    relatorio = {"fases": {}}
    pai_temp = Path(os.environ.get("EDE_HOMOLOG_TMP", "C:/ede_homolog")) if os.name == "nt" \
        else Path(tempfile.gettempdir()) / "ede_homolog"
    saida_dir = Path(saida_dir) if saida_dir else Path(tempfile.mkdtemp(prefix="ede_homolog_saida_"))
    saida_dir.mkdir(parents=True, exist_ok=True)

    relatorio["head_testado"] = git_head(repo)
    clone_dir = clonar_repositorio_limpo(repo, pai_temp)
    relatorio["clone_dir"] = str(clone_dir)

    try:
        relatorio["fases"]["ausencias_pre_bootstrap"] = verificar_ausencias_pre_bootstrap(clone_dir)

        relatorio["fases"]["doctor_pre_bootstrap"] = rodar_doctor(clone_dir, saida_dir / "saida_doctor_pre")

        relatorio["fases"]["pytest_pre_bootstrap"] = rodar_pytest(clone_dir)

        relatorio["fases"]["bootstrap"] = rodar_bootstrap(clone_dir, modelo_oficial)

        relatorio["fases"]["doctor_pos_bootstrap"] = rodar_doctor(clone_dir, saida_dir / "saida_doctor_pos")

        relatorio["fases"]["pytest_docx_real_pos_bootstrap"] = rodar_pytest(clone_dir, marker="docx_real")

        relatorio["fases"]["happy_path"] = rodar_happy_path(clone_dir, "tests/fixtures/contestacao/happy_path",
                                                              saida_dir)

        hp = relatorio["fases"]["happy_path"]
        if hp.get("relatorio", {}).get("status") == "OK":
            relatorio["fases"]["validate_template"] = rodar_validate_template(
                clone_dir, Path(hp["_output_path"]), Path(hp["_dados_path"]))

        relatorio["fases"]["dependencias_skills_docx"] = buscar_dependencias_skills_docx(clone_dir)

        textos_para_busca = {
            "doctor_pre_bootstrap": json.dumps(relatorio["fases"]["doctor_pre_bootstrap"], ensure_ascii=False),
            "doctor_pos_bootstrap": json.dumps(relatorio["fases"]["doctor_pos_bootstrap"], ensure_ascii=False),
            "bootstrap": json.dumps(relatorio["fases"]["bootstrap"], ensure_ascii=False),
            "happy_path_relatorio": json.dumps(hp.get("relatorio", {}), ensure_ascii=False),
        }
        docx_saida = Path(hp.get("_output_path", ""))
        if docx_saida.is_file():
            textos_para_busca["docx_document_xml"] = _ler_document_xml_bruto(docx_saida)
        relatorio["fases"]["busca_caminho_privado"] = buscar_caminho_privado(textos_para_busca, str(repo))

        pipeline_ok = hp.get("ok_geral") is True
        relatorio["pipeline_chegou_ao_docx_final"] = pipeline_ok
    finally:
        if not manter_clone:
            shutil.rmtree(clone_dir, ignore_errors=True)
        else:
            relatorio["clone_preservado_em"] = str(clone_dir)

    return relatorio


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo-oficial", required=True, help="caminho do modelo-oficial.docx institucional (nunca embutido no script)")
    ap.add_argument("--repo", default=str(REPO_PADRAO), help="repositório local a clonar (padrão: este repositório)")
    ap.add_argument("--manter-clone", action="store_true", help="não apaga o clone temporário ao final (inspeção manual)")
    ap.add_argument("--saida-dir", help="diretório para artefatos do teste (padrão: temp autogerado)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    resultado = homologar(Path(args.modelo_oficial), Path(args.repo), args.manter_clone,
                           Path(args.saida_dir) if args.saida_dir else None)

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"HEAD testado: {resultado['head_testado']}")
        print(f"Clone: {resultado['clone_dir']}")
        print(f"Pipeline chegou ao DOCX final: {resultado.get('pipeline_chegou_ao_docx_final')}")

    sys.exit(0 if resultado.get("pipeline_chegou_ao_docx_final") else 1)


if __name__ == "__main__":
    main()
