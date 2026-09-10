#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ede_doctor.py — diagnóstico do ambiente do EDE Legal Plugin (Etapa 5.10,
Commit 6, ADR-0014/PEND-007).

Executa SOMENTE verificação — nunca gera peça, nunca instala nem edita
nada (para instalar o Modelo Oficial, ver
scripts/instalar_modelo_oficial.py).

Host-agnostic: `Path(__file__).resolve()` resolve o repositório por conta
própria — `CLAUDE_PLUGIN_ROOT` NUNCA é exigido como única forma de
localizar a instalação; se estiver definido, é reportado como informação
adicional (item não obrigatório), nunca condição de READY. Nenhuma
referência funcional a `skills/docx/`, `~/.claude/skills/docx` ou
`~/.agents/skills/docx` — o runtime DOCX é autônomo desde o Commit 3
(ADR-0014); este script não sabe nem precisa saber que aquele skill de
terceiro um dia existiu.

Verificação de dependências Python (item 8): usa
`importlib.util.find_spec`, que só consulta o finder — nunca importa nem
executa o módulo. Os módulos do próprio EDE que dependem de `lxml`
(`docx_package.py` e quem o importa) só são importados DEPOIS de
confirmar que `lxml` está presente — nunca antes, para que uma
dependência ausente nunca produza traceback antes do diagnóstico terminar.

Uso:
  python scripts/ede_doctor.py
  python scripts/ede_doctor.py --json
  python scripts/ede_doctor.py --saida /caminho/a/checar
"""
import argparse
import importlib.util
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = Path(__file__).resolve().parent.parent

SCRIPTS_ESSENCIAIS = (
    "docx_package.py",
    "docx_template_engine.py",
    "docx_context_engine.py",
    "docx_block_engine.py",
    "docx_numeracao_engine.py",
    "gerar_contestacao.py",
)

# (nome exibido, nome do módulo importável). Núcleo obrigatório de
# scripts/requirements.txt (lxml) + rag/requirements.txt (busca híbrida
# BM25 + TF-IDF/LSA). sentence-transformers/huggingface_hub são
# deliberadamente EXCLUÍDAS: rag/requirements.txt já as documenta como
# opcionais (search_hybrid.py cai automaticamente para o fallback
# TF-IDF+LSA quando ausentes) — marcá-las [FALTA] aqui seria falso alarme
# numa instalação normal.
DEPENDENCIAS_OBRIGATORIAS = (
    ("lxml", "lxml"),
    ("joblib", "joblib"),
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("pyarrow", "pyarrow"),
    ("scikit-learn", "sklearn"),
    ("scipy", "scipy"),
    ("rank_bm25", "rank_bm25"),
    ("pyyaml", "yaml"),
)


def _dependencia_presente(modulo: str) -> bool:
    """Checagem controlada (item 8 do pedido) — find_spec nunca importa/
    executa o módulo checado."""
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def _json_valido(caminho: Path) -> bool:
    if not Path(caminho).exists():
        return False
    try:
        json.loads(Path(caminho).read_text(encoding="utf-8"))
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _checar_dir_saida(caminho: Path):
    """(ok: bool, mensagem: str) — True se `caminho` pode ser usado como
    diretório de saída (existe ou é criável, e é gravável). Sonda com um
    arquivo-marcador real, criado e removido em seguida — nunca infere
    permissão só por os.access, que não é confiável em todo SO."""
    try:
        caminho.mkdir(parents=True, exist_ok=True)
        marcador = caminho / f".ede_doctor_write_test_{os.getpid()}.tmp"
        marcador.write_text("ok", encoding="utf-8")
        marcador.unlink()
        return True, f"gravável: {caminho}"
    except OSError as e:
        return False, f"não gravável como diretório de saída: {caminho} ({e})"


def executar_diagnostico(base: Path = BASE, dir_saida=None,
                          schema_path=None, catalogo_path=None, modelo_path=None) -> dict:
    """Diagnóstico puro — nunca gera peça, nunca escreve em `base` (só,
    opcionalmente, em `dir_saida`, para a sonda de gravação). Parâmetros
    de caminho são injetáveis para teste; usam os caminhos padrão do
    projeto (templates/contestacao/...) quando omitidos."""
    schema_path = Path(schema_path) if schema_path else base / "templates" / "contestacao" / "schema.json"
    catalogo_path = Path(catalogo_path) if catalogo_path else base / "templates" / "contestacao" / "blocos.json"
    modelo_path = Path(modelo_path) if modelo_path else base / "templates" / "contestacao" / "modelo-oficial.docx"

    checagens = []

    def _add(item, ok, obrigatorio=True, detalhe=None):
        checagens.append({"item": item, "ok": bool(ok), "obrigatorio": obrigatorio, "detalhe": detalhe})

    _add("plugin_root", base.is_dir(), detalhe=str(base))

    claude_plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    _add("ambiente:CLAUDE_PLUGIN_ROOT", claude_plugin_root is not None, obrigatorio=False,
         detalhe=claude_plugin_root or "não definido — normal fora do host Claude Code, nunca exigido")

    _add("python", sys.version_info >= (3, 9), detalhe=platform.python_version())

    for nome_exibido, modulo in DEPENDENCIAS_OBRIGATORIAS:
        _add(f"dependencia:{nome_exibido}", _dependencia_presente(modulo))

    for nome_script in SCRIPTS_ESSENCIAIS:
        _add(f"script:{nome_script}", (base / "scripts" / nome_script).is_file())

    _add("rag:config.yaml", (base / "rag" / "config.yaml").is_file())
    _add("rag:index_artigos.json", _json_valido(base / "rag" / "index_artigos.json"))

    _add("template:schema.json", _json_valido(schema_path))

    # Import guardado do runtime DOCX próprio — só tentado DEPOIS de
    # confirmar lxml presente (senão o import de docx_package.py, que faz
    # "import lxml.etree" no nível de módulo, levantaria ImportError e
    # derrubaria o diagnóstico inteiro antes de terminar — item 8 do
    # pedido: nenhuma dependência ausente pode produzir traceback cru
    # aqui). ImportError coberto por qualquer causa (não só lxml) — um
    # runtime quebrado por outro motivo também deve aparecer como [FALTA],
    # nunca como traceback do próprio ede_doctor.py.
    docx_package_mod = docx_block_engine_mod = docx_template_engine_mod = instalar_modelo_mod = None
    if _dependencia_presente("lxml"):
        try:
            import docx_block_engine as docx_block_engine_mod
            import docx_package as docx_package_mod
            import docx_template_engine as docx_template_engine_mod
            import instalar_modelo_oficial as instalar_modelo_mod
        except ImportError:
            docx_package_mod = docx_block_engine_mod = docx_template_engine_mod = instalar_modelo_mod = None
    runtime_docx_ok = docx_package_mod is not None
    _add("runtime:docx_package", runtime_docx_ok,
         detalhe="scripts/docx_package.py importável, sem skills/docx/" if runtime_docx_ok
         else "não importável — verifique dependencia:lxml acima")

    catalogo_ok, catalogo = False, None
    if docx_block_engine_mod is not None:
        try:
            catalogo = docx_block_engine_mod.carregar_catalogo(catalogo_path)
            docx_block_engine_mod.validar_catalogo(catalogo)
            catalogo_ok = True
        except docx_block_engine_mod.ComposicaoAbortada as e:
            catalogo_ok = False
            catalogo = None
            _add("template:blocos.json", False, detalhe=f"{e.stage}: {e.motivo}")
    if catalogo_ok:
        _add("template:blocos.json", True)
    elif catalogo is None and docx_block_engine_mod is None:
        _add("template:blocos.json", False, detalhe="não verificável — runtime:docx_package ausente")

    modelo_presente = Path(modelo_path).is_file()
    _add("template:modelo-oficial.docx", modelo_presente,
         detalhe=("instalado" if modelo_presente else
                  "ausente — asset institucional externo (ADR-0009, CLAUDE.md §13); "
                  "instale com scripts/instalar_modelo_oficial.py"))

    contrato_ok = False
    if modelo_presente and catalogo_ok and instalar_modelo_mod is not None and _json_valido(schema_path):
        schema = docx_template_engine_mod.carregar_schema(schema_path)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pacote_dir = Path(tmp) / "unpacked"
                docx_package_mod.extrair_pacote_docx(Path(modelo_path), pacote_dir)
                divergencias = instalar_modelo_mod.validar_contrato_modelo(pacote_dir, schema, catalogo)
            contrato_ok = not divergencias
            _add("template:contrato", contrato_ok,
                 detalhe="compatível" if contrato_ok else "; ".join(divergencias))
        except docx_package_mod.PacoteDocxAbortada as e:
            _add("template:contrato", False, detalhe=f"{e.stage}: {e.motivo}")
    else:
        _add("template:contrato", False,
             detalhe="não verificável — modelo-oficial.docx/schema.json/blocos.json/runtime ausente ou inválido")

    alvo_saida = Path(dir_saida) if dir_saida is not None else Path.cwd()
    saida_ok, saida_detalhe = _checar_dir_saida(alvo_saida)
    _add("saida:diretorio", saida_ok, detalhe=saida_detalhe)

    obrigatorias_falhando = [c["item"] for c in checagens if c["obrigatorio"] and not c["ok"]]
    return {"ready": not obrigatorias_falhando, "checks": checagens,
            "obrigatorias_falhando": obrigatorias_falhando}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", help="diretório de saída a testar (padrão: diretório atual)")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    resultado = executar_diagnostico(dir_saida=Path(args.saida) if args.saida else None)

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print("EDE Legal Plugin — Environment Check\n")
        for c in resultado["checks"]:
            marca = "OK   " if c["ok"] else ("FALTA" if c["obrigatorio"] else "info ")
            linha = f"[{marca}] {c['item']}"
            if c["detalhe"]:
                linha += f" — {c['detalhe']}"
            print(linha)
        print()
        if resultado["ready"]:
            print("READY TO GENERATE")
        else:
            print("NOT READY")
            print("Itens obrigatórios pendentes:")
            for item in resultado["obrigatorias_falhando"]:
                print(f"  - {item}")

    sys.exit(0 if resultado["ready"] else 1)


if __name__ == "__main__":
    main()
