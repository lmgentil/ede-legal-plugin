#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_template.py — CLI do Template Lock (SPEC-0001 REQ-016, TEST-001,
TEST-002), como checagem independente do pipeline de geração (útil para
regressão/CI: valida um .docx já gerado contra o template, a qualquer
momento depois).

Estratégia: regenera uma peça de referência com os MESMOS dados via
gerar_peca_com_blocos() — o MESMO mecanismo real de geração da
Contestação (composição de blocos condicionais, zonas de complementação,
renumeração, substituição de placeholders, Template Lock interno,
reempacotamento; docx_block_engine.py) — e compara, parte por parte, o
resultado contra o .docx auditado. Isso evita dois tipos de falso
resultado:

  - falso-positivo por ruído de formatação (o pretty-print/condense do
    parser não é perfeitamente idempotente entre gerações — confirmado em
    auditoria anterior desta etapa: uma comparação ingênua contra um único
    unpack do template acusava divergência puramente de espaço em branco
    entre tags, fora de qualquer <w:t>). Com a mesma quantidade de ciclos
    dos dois lados, a comparação fica exata.
  - falso-negativo por arquitetura desalinhada (Etapa 5.10, Commit 7 —
    achado real desta etapa): até este microfix, a referência era
    reconstruída por docx_template_engine.gerar_peca() — motor de
    substituição de placeholder ISOLADO, que nunca compõe blocos/zonas e
    deixa todos os <w:sdt> condicionais intactos no XML. Contra uma
    Contestação real (sempre gerada por gerar_peca_com_blocos(), com
    blocos legitimamente excluídos), a referência produzida por
    gerar_peca() é uma peça ESTRUTURALMENTE DIFERENTE — a comparação
    reprovava sistematicamente peças corretas. Corrigido alinhando a
    reconstrução ao mecanismo real; nenhuma lógica de composição nova foi
    escrita aqui — só passou a se chamar a função de orquestração já
    existente com os mesmos insumos (blocos.json, decisões, fatos
    processuais, conteúdo de zonas) que uma geração real usaria.

Insumos adicionais em relação à versão anterior deste script:
`--decisoes-blocos` (obrigatório — mesmo contrato de decisoes_blocos.json),
`--fatos-processuais`/`--conteudo-zonas` (opcionais — mesmo contrato de
estado_processual.json e do dicionário {zona_id: texto} já resolvido que
gerar_peca_com_blocos() consome; ausência de qualquer um dos dois equivale
a "{}", mesmo default do pipeline real quando o arquivo correspondente não
existe no diretório do caso). Este script nunca re-executa a validação de
proveniência/densidade/continuidade de zona (isso é
gerar_contestacao._etapa_zonas) — recebe o conteúdo de zona JÁ RESOLVIDO,
do mesmo jeito que já recebia `--dados` como placeholders JÁ RESOLVIDOS.

Contrato de saída inalterado: {"ok": bool, "divergencias": [...]}. Erro
documental esperado (pacote OOXML inválido/incompleto, referência
impossível de gerar) nunca é traceback cru — sempre `ok: false` com
divergência explícita (Microfix 7.1, gap A). Bug de programação genuíno
continua se propagando sem mascaramento — nenhum `except Exception` amplo
neste módulo.

Uso:
  python validate_template.py --gerado saida/peca.docx --dados dados.json \\
      --decisoes-blocos decisoes_blocos.json
  python validate_template.py --gerado saida/peca.docx --dados dados.json \\
      --decisoes-blocos decisoes_blocos.json \\
      --fatos-processuais estado_processual.json --conteudo-zonas zonas_resolvidas.json
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from docx_block_engine import gerar_peca_com_blocos  # noqa: E402
from docx_package import PacoteDocxAbortada, extrair_pacote_docx, validar_estrutura_minima  # noqa: E402
from docx_template_engine import garantir_utf8  # noqa: E402

TEMPLATE_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"


def _carregar_json(caminho, padrao=None):
    if caminho is None:
        return {} if padrao is None else padrao
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def _diff_diretorios(dir_a: Path, dir_b: Path, rotulo_a: str, rotulo_b: str) -> list:
    arquivos_a = {f.relative_to(dir_a) for f in dir_a.rglob("*") if f.is_file()}
    arquivos_b = {f.relative_to(dir_b) for f in dir_b.rglob("*") if f.is_file()}
    divergencias = [f"arquivo em {rotulo_a} ausente em {rotulo_b}: {r}" for r in sorted(arquivos_a - arquivos_b)]
    divergencias += [f"arquivo novo em {rotulo_b} (ausente em {rotulo_a}): {r}" for r in sorted(arquivos_b - arquivos_a)]
    for rel in sorted(arquivos_a & arquivos_b):
        if (dir_a / rel).read_bytes() != (dir_b / rel).read_bytes():
            divergencias.append(f"arquivo difere entre {rotulo_a} e {rotulo_b}: {rel}")
    return divergencias


def _extrair_ou_divergencia(docx_path: Path, destino_dir: Path, rotulo: str) -> list:
    """Extrai `docx_path` para `destino_dir`; devolve lista de
    divergências (vazia = ok) em vez de deixar PacoteDocxAbortada crua se
    propagar para quem chamou este script (Microfix 7.1, gap A) — mesmo
    padrão fail-closed-com-contrato-próprio já usado pelo resto do
    pipeline (nunca `except Exception` amplo: só a exceção documental já
    nomeada por docx_package.py é capturada aqui; qualquer outra continua
    se propagando com traceback completo, como bug real que é)."""
    try:
        extrair_pacote_docx(docx_path, destino_dir)
    except PacoteDocxAbortada as e:
        return [f"PACOTE_DOCX_INVALIDO ({rotulo}, stage={e.stage}): {e.motivo}"]
    problemas = validar_estrutura_minima(destino_dir)
    if problemas:
        return [f"ESTRUTURA_DOCX_INCOMPLETA ({rotulo}): {p}" for p in problemas]
    return []


def validar_template(gerado, dados: dict, decisoes_blocos: dict, template=TEMPLATE_PADRAO,
                      schema=SCHEMA_PADRAO, catalogo=CATALOGO_PADRAO,
                      fatos_processuais: dict = None, conteudo_zonas: dict = None) -> dict:
    """Função pura reutilizável (CLI e testes): reconstrói a peça de
    referência pelo mecanismo real de composição e compara contra
    `gerado`. Nunca levanta exceção para condição documental esperada —
    contrato de saída sempre {"ok": bool, "divergencias": [...]}."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        referencia = tmp / "referencia.docx"
        relatorio_geracao = gerar_peca_com_blocos(
            str(template), str(schema), str(catalogo), dados, decisoes_blocos, str(referencia),
            fatos_processuais=fatos_processuais or {}, conteudo_zonas=conteudo_zonas or {})
        if relatorio_geracao["status"] != "OK":
            return {"ok": False, "divergencias": [
                f"TEMPLATE_INCOMPATIVEL: não foi possível gerar peça de referência para "
                f"comparação (etapa={relatorio_geracao.get('etapa')})",
                *relatorio_geracao.get("erros", []),
            ]}

        ref_dir, aud_dir = tmp / "ref_unpacked", tmp / "aud_unpacked"
        divergencias = _extrair_ou_divergencia(referencia, ref_dir, "referência")
        divergencias += _extrair_ou_divergencia(Path(gerado), aud_dir, "auditado")
        if divergencias:
            return {"ok": False, "divergencias": divergencias}

        divergencias = _diff_diretorios(ref_dir, aud_dir, "referência", "auditado")
        return {"ok": not divergencias, "divergencias": divergencias}


def main():
    garantir_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", default=str(TEMPLATE_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--catalogo", default=str(CATALOGO_PADRAO), help="blocos.json — composição real (Microfix 7.1)")
    ap.add_argument("--gerado", required=True, help=".docx já gerado a auditar")
    ap.add_argument("--dados", required=True, help="JSON com os placeholders usados na geração original")
    ap.add_argument("--decisoes-blocos", required=True,
                     help="JSON com as decisões de blocos condicionais (mesmo contrato de decisoes_blocos.json)")
    ap.add_argument("--fatos-processuais",
                     help="JSON com o estado processual (mesmo contrato de estado_processual.json); "
                          "opcional, default {}")
    ap.add_argument("--conteudo-zonas",
                     help="JSON com o conteúdo JÁ RESOLVIDO das zonas ({zona_id: texto}); "
                          "opcional, default {}")
    args = ap.parse_args()

    dados = _carregar_json(args.dados)
    decisoes_blocos = _carregar_json(args.decisoes_blocos)
    fatos_processuais = _carregar_json(args.fatos_processuais, padrao={})
    conteudo_zonas = _carregar_json(args.conteudo_zonas, padrao={})

    resultado = validar_template(args.gerado, dados, decisoes_blocos, args.template, args.schema,
                                  args.catalogo, fatos_processuais, conteudo_zonas)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    sys.exit(0 if resultado["ok"] else 1)


if __name__ == "__main__":
    main()
