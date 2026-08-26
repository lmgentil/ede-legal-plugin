#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_contestacao.py — orquestrador executável da Contestação (Fase 7,
SPEC-0001 REQ-031 + skills/contestacao/SKILL.md).

COORDENA — não reimplementa — os componentes já existentes:
  fatos.json        -> scripts/validate_fatos.py       (REQ-030)
  tempestividade.json -> skills/calendario-forense-tjba-2026/scripts/
                         calcular_tempestividade.py     (REQ-005/011/012)
  estrategia.md      -> saída de estrategista-contestacao-ede (Skill —
                         não invocável de dentro deste script; ver
                         "Limitação conhecida" abaixo). Este orquestrador
                         só confere que a saída existe e é estruturalmente
                         válida (bate com o contrato de 15 seções do
                         SKILL.md dela) — não a produz.
  citacoes.json      -> rag/search_hybrid.py + rag/legal_validation/
                         (validar_citacao) — Fases 4/5
  placeholders.json   -> saída de redator-peca-processual-elite +
                         humanizer-pt-br (mesma limitação: Skills não são
                         invocáveis daqui; o script só consome o
                         resultado já produzido)
  Template Engine     -> scripts/docx_template_engine.py (gerar_peca) — Fase 3

LIMITAÇÃO CONHECIDA (SPEC-0001 Fase 7 §33): Skills do Claude Code
(`estrategista-contestacao-ede`, `redator-peca-processual-elite`,
`humanizer-pt-br`) são arquivos de instrução para um agente LLM — não há
API Python para "executá-las" de dentro de um script. Este orquestrador
NÃO finge o contrário: ele valida que a SAÍDA dessas Skills existe e tem
a forma esperada (evidência estrutural), mas a execução real delas é um
procedimento manual assistido (rodado pelo agente, fora deste script) —
ver docs/E2E_FASE7.md para o procedimento e o registro de uma execução
real.

Fail closed (CLAUDE.md §17): qualquer etapa ausente, inválida, ou
placeholder essencial sem conteúdo real interrompe o pipeline com
PIPELINE_ABORTED — nunca gera DOCX "como se" a etapa tivesse ocorrido.

Uso:
  python scripts/gerar_contestacao.py --caso tests/fixtures/contestacao/happy_path \
      --output /tmp/saida.docx --relatorio /tmp/relatorio.json
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "rag"))
sys.path.insert(0, str(BASE / "skills" / "calendario-forense-tjba-2026" / "scripts"))

from calcular_tempestividade import INTEMPESTIVO, PENDENTE, TEMPESTIVO, calcular_tempestividade  # noqa: E402
import datajud_client  # noqa: E402
from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    gerar_peca_com_blocos,
    validar_catalogo,
    validar_e_resolver_decisoes,
    validar_pedidos_composicionais,
)
from docx_context_engine import ContextoAbortada, extrair_contexto_do_template  # noqa: E402
from docx_template_engine import carregar_schema, garantir_utf8  # noqa: E402
from legal_validation import validar_citacao  # noqa: E402
from validate_fatos import (  # noqa: E402
    normalizar_conteudo_zona,
    validar_fatos,
    validar_proveniencia_zona,
)
from validate_paragrafos import (  # noqa: E402
    validar_densidade_blocos,
    validar_densidade_zonas,
    validar_paragrafos_placeholders,
)
from validate_placeholder_semantics import (validar_semantica, validar_semantica_zonas,  # noqa: E402
                                             validar_continuidade_zonas)

TEMPLATE_PADRAO = BASE / "templates" / "contestacao" / "modelo-oficial.docx"
SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_BLOCOS_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"

MARCADOR_FOTOS = "[INSERIR MANUALMENTE AS FOTOGRAFIAS DA IRREGULARIDADE]"

# Etapa 5.7-C (INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA, SPEC-0001 §57):
# "gerativo" = campo onde o Redator/Humanizer compõem prosa argumentativa
# nova (schema.json, placeholder_contracts.tipo). Reaproveita a
# classificação já existente em schema.json em vez de duplicar uma lista
# própria — IDENTIFICADOR/VALOR/MARCADOR_MANUAL são dado documental/
# determinístico (extração, DataJud, script), nunca redação da IA; só
# TEXTO_TECNICO/TEXTO_LONGO recebem contexto institucional, porque só
# esses são efetivamente redigidos pela IA (item 4 do pedido — "apenas o
# contexto necessário aos placeholders gerativos que ele efetivamente
# produzirá").
TIPOS_GERATIVOS = ("TEXTO_TECNICO", "TEXTO_LONGO")

# Contrato de 15 seções de estrategista-contestacao-ede (SKILL.md §7) — a
# saída não é "estruturalmente válida" se faltar qualquer uma.
SECOES_ESTRATEGIA_OBRIGATORIAS = [
    "## I. Diagnóstico executivo", "## II. Fatos relevantes",
    "## III. Pedidos do autor", "## IV. Preliminares recomendadas",
    "## V. Tese central de mérito", "## VI. Teses complementares",
    "## VII. Teses subsidiárias",
    "## VIII. Fundamentação na REN ANEEL",
    "## IX. Fundamentação processual", "## X. Impugnação dos pedidos",
    "## XI. Provas", "## XII. Riscos", "## XIII. Documentos a destacar",
    "## XIV. Pontos que não devem ser alegados",
    "## XV. Estrutura da contestação",
]

# Placeholders cujo conteúdo é um compromisso factual/numérico concreto —
# não podem ficar como sentinela de ausência (isso interrompe o pipeline,
# CLAUDE.md §17 "placeholder ausente -> falhar"). Os demais (narrativos)
# podem legitimamente conter a sentinela dentro do texto (REQ-030/§9) sem
# abortar o pipeline inteiro.
PLACEHOLDERS_CRITICOS_NAO_SENTINELA = ["VALOR_FRA"]
SENTINELA_AUSENCIA = "NÃO INFORMADO"

PLACEHOLDERS_OBRIGATORIOS_NAO_VAZIOS = [
    "JUIZO", "NUMERO_PROCESSO", "AUTOR", "SINOPSE_FATOS", "REALIDADE_FATICA",
    "IRREGULARIDADE_ENCONTRADA", "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE",
    "VALOR_FRA", "PEDIDOS_FINAIS", "LOCAL_DATA",
]

# Correção — dano moral pretendido: VALOR_DANO_MORAL_PRETENDIDO NÃO entra
# em nenhuma das duas listas acima, deliberadamente. Diferente de
# VALOR_FRA (sempre presente na narrativa central do caso), este
# placeholder só existe dentro do bloco condicional
# DESCABIMENTO_DANO_MORAL — ausência de pedido de dano moral na inicial
# é o cenário comum, e o bloco fica EXCLUIR (SDT removido antes da
# substituição); tratá-lo como obrigatório aqui quebraria exatamente esse
# caso comum. Quando o bloco está INCLUIR, a obrigatoriedade já é
# garantida automaticamente por docx_template_engine.validar_placeholders
# ("placeholders do template sem dado fornecido") sobre a XML já
# composta — nenhuma lista global adicional necessária. E diferente da
# sentinela fail-closed de VALOR_FRA, "a ser arbitrado pelo Juízo" é
# conteúdo legítimo para este campo, não pode abortar o pipeline.


def _abortar(stages: list, etapa: str, motivo: str) -> dict:
    stages.append({"name": etapa, "status": "abortado", "motivo": motivo})
    return {"status": "PIPELINE_ABORTED", "stage": etapa, "reason": motivo,
            "stages": stages}


def _etapa_contexto_institucional(template: Path, schema_path: Path, catalogo_blocos: Path,
                                   stages: list):
    """Etapa 5.7-C — INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA (SPEC-0001
    §56/§57): PRIMEIRA etapa do pipeline, incondicional. Extrai — SOMENTE
    LEITURA, sempre do `modelo-oficial.docx` REAL desta execução, nunca de
    arquivo intermediário/cache que pudesse ficar desatualizado ou ser
    transcrito à mão — o contexto institucional de cada placeholder
    GERATIVO (TIPOS_GERATIVOS acima; placeholders determinísticos/
    documentais como JUIZO/FOTOS_DA_IRREGULARIADE/NUMERO_PROCESSO/AUTOR/
    valores nunca recebem contexto aqui — item 5 do pedido, não introduz
    IA onde hoje existe resolução determinística).

    REGRA: `REDATOR NÃO PODE SER ACIONADO SEM CONTEXTO INSTITUCIONAL
    EXTRAÍDO` — como Skills não são chamáveis por este script (mesma
    limitação de sempre, ver docstring do módulo, "LIMITAÇÃO CONHECIDA"),
    o que é code-level e fail-closed aqui é o inverso, equivalente e
    verificável: nenhuma execução deste pipeline chega a
    `_etapa_placeholders` (que consome a SAÍDA do redator/humanizer) sem
    que esta etapa tenha rodado com sucesso PRIMEIRO, na mesma execução,
    contra o template vigente. Falha aqui (template ausente, corrompido,
    ou XML sem <w:body>) aborta o pipeline ANTES de qualquer leitura de
    `placeholders.json` — `PIPELINE_ABORTED`, `stage=contexto_
    institucional`; nunca gera DOCX silenciosamente sem essa etapa ter
    ocorrido (item 6 do pedido)."""
    try:
        contexto = extrair_contexto_do_template(template, catalogo_blocos)
    except ContextoAbortada as e:
        return _abortar(stages, "contexto_institucional", f"{e.stage}: {e.motivo}")

    schema = carregar_schema(schema_path)
    gerativos = {p for p, c in schema["placeholder_contracts"].items()
                 if c["tipo"] in TIPOS_GERATIVOS}
    # Etapa 5.8-B (§18): zona é, por definição, ponto gerativo — o Redator
    # não pode aplicar o teste de necessidade sem conhecer o texto
    # institucional que a cerca. Entra pela mesma porta dos placeholders
    # gerativos, sem virar placeholder (não está no schema, e é daí que
    # vem a necessidade desta união explícita).
    try:
        zonas_catalogo = carregar_catalogo(catalogo_blocos).get("zones", [])
    except ComposicaoAbortada as e:
        return _abortar(stages, "contexto_institucional", f"{e.stage}: {e.motivo}")
    gerativos |= {z["id"] for z in zonas_catalogo}
    contexto_gerativo = {p: v for p, v in contexto.items() if p in gerativos}

    # item 10 do pedido: prova de que o contexto vem do template CORRENTE
    # desta execução (não de transcrição manual em SKILL.md nem de cache
    # velho) — hash do arquivo efetivamente lido acima, nesta mesma
    # chamada, nunca de um valor gravado antes.
    hash_template = hashlib.sha256(Path(template).read_bytes()).hexdigest()

    stages.append({"name": "contexto_institucional", "status": "ok",
                    "template_hash_sha256": hash_template,
                    "placeholders_com_contexto": sorted(contexto_gerativo)})
    return contexto_gerativo


def _etapa_fatos(caso: Path, stages: list):
    caminho = caso / "fatos.json"
    if not caminho.exists():
        return _abortar(stages, "facts", "fatos.json (REQ-030) ausente")
    fatos = json.loads(caminho.read_text(encoding="utf-8"))
    ok, erros = validar_fatos(fatos)
    if not ok:
        return _abortar(stages, "facts", f"fatos.json estruturalmente inválido: {erros}")
    stages.append({"name": "facts", "status": "ok", "count": len(fatos),
                    "fonte": str(caminho)})
    return fatos


MARCO_ORIGENS_VALIDAS = ("documental", "informado_pelo_advogado")
# Campos de proveniência do marco — nunca repassados a calcular_tempestividade()
# (que só aceita os parâmetros do cálculo em si).
CAMPOS_TEMPESTIVIDADE_META = ("aplicavel", "marco_origem",
                               "marco_source_document", "marco_page",
                               "marco_resposta_advogado")

# INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM (Etapa 5.5 — decisão de produto
# fixa e permanente, registrada aqui para impedir que Skills futuras
# tentem escolher outro rito): esta Contestação SEMPRE calcula
# tempestividade pelo procedimento comum do CPC — prazo de 15 dias,
# contagem em dias úteis. Nunca a lógica do Juizado Especial (Lei
# 9.099/95), mesmo quando o caso concreto tramita por um rito que
# admitiria essa aplicação subsidiária. tempestividade.json que não
# especificar prazo_legal_dias/tipo_prazo/fundamento_normativo recebe
# esse padrão fixo; se especificar algo incompatível, o pipeline aborta
# — nunca escolhe silenciosamente outro rito.
PRAZO_LEGAL_DIAS_PADRAO = 15
TIPO_PRAZO_PADRAO = "uteis"
FUNDAMENTO_NORMATIVO_PADRAO = "art. 335 do CPC (procedimento comum)"
_MARCADORES_RITO_VEDADO = ("9.099", "9099", "juizado especial", "lei 9.099")


def _etapa_tempestividade(caso: Path, stages: list):
    """INV-TEMPESTIVIDADE-MARCO (SPEC-0001 §5, CLAUDE.md §8): nenhuma
    Contestação alcança a etapa de template com tempestividade PENDENTE —
    nem por marco temporal (citação/intimação/publicação) ausente ou sem
    proveniência, nem por qualquer outro dado essencial faltando (prazo
    legal, fundamento normativo, calendário não verificado). Perguntar ao
    advogado é responsabilidade da Skill `contestacao` (AskUserQuestion,
    já declarada em allowed-tools) — este script só verifica a EVIDÊNCIA
    estrutural de que isso foi resolvido, o mesmo padrão já usado para
    INV-CONTESTACAO-ESTRATEGIA (ver _etapa_estrategia)."""
    caminho = caso / "tempestividade.json"
    if not caminho.exists():
        stages.append({"name": "tempestividade", "status": "nao_aplicavel"})
        return "NÃO APLICÁVEL"
    t = json.loads(caminho.read_text(encoding="utf-8"))
    if not t.get("aplicavel", True):
        stages.append({"name": "tempestividade", "status": "nao_aplicavel"})
        return "NÃO APLICÁVEL"

    marco_origem = t.get("marco_origem")
    tem_marco = bool(t.get("data_ciencia") or t.get("data_publicacao"))
    if not tem_marco:
        return _abortar(stages, "tempestividade",
            "marco temporal (data da citação, intimação ou publicação) "
            "ausente — INV-TEMPESTIVIDADE-MARCO exige que a Skill "
            "`contestacao` pergunte obrigatoriamente ao advogado antes de "
            "prosseguir; pipeline não pode avançar sem data concreta.")
    if marco_origem not in MARCO_ORIGENS_VALIDAS:
        return _abortar(stages, "tempestividade",
            f"marco temporal presente sem 'marco_origem' válido "
            f"({MARCO_ORIGENS_VALIDAS}) — INV-TEMPESTIVIDADE-MARCO exige "
            f"proveniência explícita, nunca uma data solta sem origem "
            f"registrada (ambígua, conflitante ou insuficientemente "
            f"comprovada conta como ausente).")
    if marco_origem == "documental" and not str(t.get("marco_source_document", "")).strip():
        return _abortar(stages, "tempestividade",
            "marco_origem='documental' exige 'marco_source_document' "
            "(proveniência do marco, mesmo contrato de fatos.json/REQ-030) "
            "— INV-TEMPESTIVIDADE-MARCO.")
    if marco_origem == "informado_pelo_advogado" and not str(t.get("marco_resposta_advogado", "")).strip():
        return _abortar(stages, "tempestividade",
            "marco_origem='informado_pelo_advogado' exige "
            "'marco_resposta_advogado' (registro da resposta dada pelo "
            "advogado) — INV-TEMPESTIVIDADE-MARCO.")

    args = {k: v for k, v in t.items() if k not in CAMPOS_TEMPESTIVIDADE_META}

    # INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM: aplica o padrão fixo quando
    # não especificado; aborta se algo incompatível for especificado —
    # nunca escolhe silenciosamente outro rito.
    prazo_informado = args.get("prazo_legal_dias")
    if prazo_informado is None:
        args["prazo_legal_dias"] = PRAZO_LEGAL_DIAS_PADRAO
    elif prazo_informado != PRAZO_LEGAL_DIAS_PADRAO:
        return _abortar(stages, "tempestividade",
            f"prazo_legal_dias={prazo_informado!r} incompatível com a regra "
            f"fixa deste projeto (procedimento comum do CPC, sempre "
            f"{PRAZO_LEGAL_DIAS_PADRAO} dias úteis) — "
            f"INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM.")
    tipo_informado = args.get("tipo_prazo")
    if tipo_informado is None:
        args["tipo_prazo"] = TIPO_PRAZO_PADRAO
    elif tipo_informado != TIPO_PRAZO_PADRAO:
        return _abortar(stages, "tempestividade",
            f"tipo_prazo={tipo_informado!r} incompatível com a regra fixa "
            f"deste projeto (sempre dias úteis) — "
            f"INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM.")
    fundamento_informado = str(args.get("fundamento_normativo") or "")
    if any(m in fundamento_informado.lower() for m in _MARCADORES_RITO_VEDADO):
        return _abortar(stages, "tempestividade",
            f"fundamento_normativo menciona Lei 9.099/95/Juizado Especial "
            f"— incompatível com a regra fixa deste projeto (sempre "
            f"procedimento comum do CPC) — "
            f"INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM: {fundamento_informado!r}")
    if not fundamento_informado:
        args["fundamento_normativo"] = FUNDAMENTO_NORMATIVO_PADRAO

    r = calcular_tempestividade(**args)
    if r.status == PENDENTE:
        # Marco resolvido, mas outro dado essencial falta (prazo legal,
        # fundamento normativo, calendário não verificado) — mesma regra:
        # "PENDENTE DE VALIDAÇÃO" nunca alcança o DOCX final.
        return _abortar(stages, "tempestividade", r.motivo_pendencia)

    stages.append({"name": "tempestividade", "status": "ok",
                    "marco_origem": marco_origem,
                    "memoria_calculo": r.memoria_calculo()})
    # Etapa 5.5 (achado real — redação robótica): a memória de cálculo
    # completa (acima) é só para auditoria interna — NUNCA despejada no
    # DOCX. TEMPESTIVIDADE_CASO recebe prosa jurídica natural, sem dump
    # de relatório, sem data em formato ISO, sem menção a rito alheio ao
    # procedimento comum.
    return _redigir_tempestividade_natural(r)


def _data_br(data_iso: str) -> str:
    """"YYYY-MM-DD" -> "DD/MM/YYYY" (nunca ISO na redação final)."""
    from datetime import datetime as _dt
    return _dt.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def _redigir_tempestividade_natural(r) -> str:
    """Transforma o resultado determinístico de calcular_tempestividade()
    em prosa jurídica curta e institucional (Etapa 5.5 §3) — nunca
    algoritmo/cálculo interno/input/advogado/sistema/JSON/calendário como
    ferramenta/proveniência verbalizados na peça.

    r.status já não pode ser PENDENTE aqui (_etapa_tempestividade aborta
    antes de chamar esta função) — só resta TEMPESTIVO/INTEMPESTIVO, e o
    resultado precisa declarar explicitamente qual dos dois é o caso
    (nunca uma frase ambígua que sirva para ambos — regressão real do
    formato robótico antigo, que ao menos prefixava "INTEMPESTIVO:")."""
    marco = _data_br(r.termo_inicial)
    termo_final = _data_br(r.termo_final)
    if r.status == TEMPESTIVO:
        return (
            f"A presente Contestação é tempestiva. Considerado o marco "
            f"processual ocorrido em {marco} e a contagem do prazo de 15 "
            f"(quinze) dias úteis, nos termos do art. 335 do Código de "
            f"Processo Civil, o prazo defensivo encerra-se em "
            f"{termo_final}, razão pela qual a defesa é apresentada "
            f"tempestivamente.")
    if r.status == INTEMPESTIVO:
        return (
            f"Considerado o marco processual ocorrido em {marco} e a "
            f"contagem do prazo de 15 (quinze) dias úteis, nos termos do "
            f"art. 335 do Código de Processo Civil, o prazo defensivo "
            f"encerrou-se em {termo_final}, de modo que a presente "
            f"Contestação é intempestiva.")
    raise ValueError(f"status de tempestividade não reconhecido: {r.status!r} — "
                      f"fail-closed, nunca gerar redação para um status "
                      f"desconhecido/ambíguo.")


def _etapa_estrategia(caso: Path, stages: list):
    caminho = caso / "estrategia.md"
    if not caminho.exists():
        return _abortar(stages, "strategy",
                         "estrategia.md (saída de estrategista-contestacao-ede) "
                         "ausente — INV-CONTESTACAO-ESTRATEGIA exige a etapa "
                         "estratégica antes da redação; pipeline não pode "
                         "avançar sem evidência de execução.")
    texto = caminho.read_text(encoding="utf-8")
    faltando = [s for s in SECOES_ESTRATEGIA_OBRIGATORIAS if s not in texto]
    if len(texto.strip()) < 200 or faltando:
        return _abortar(stages, "strategy",
                         f"saída do estrategista estruturalmente inválida "
                         f"(seções ausentes: {faltando})")
    stages.append({"name": "strategy", "status": "ok", "fonte": str(caminho),
                    "tamanho_chars": len(texto)})
    return texto


def _etapa_blocos(caso: Path, stages: list, catalogo_path: Path = CATALOGO_BLOCOS_PADRAO):
    """INV-COMPOSICAO-BLOCOS (SPEC-0001 §5, REQ-002-B): as decisões de
    inclusão/exclusão de teses condicionais vêm exclusivamente da etapa
    estratégica (registradas pela Skill `contestacao` em
    `decisoes_blocos.json` — ver skills/contestacao/SKILL.md §4A). Este
    script só valida o catálogo e as decisões recebidas (mecânica, nunca
    decide) — qualquer INDETERMINADO, decisão ausente ou catálogo
    inconsistente aborta antes de qualquer redação/geração.

    `estado_processual.json` (Etapa 5.2, opcional — ausente conta como
    "{}") carrega os estados processuais usados pelo bloco state_linked
    de INV-GRATUIDADE-LINKED e pelo gate `requires_fact` de
    INV-CORTE-GATE-HUMANO (Etapa 5.5) (ex.: {"GRATUIDADE_CONCEDIDA": true,
    "CORTE_EFETIVO": true}); a resolução em si é feita por
    docx_block_engine.validar_e_resolver_decisoes, não duplicada aqui —
    este script só carrega o arquivo se existir."""
    caminho = caso / "decisoes_blocos.json"
    if not caminho.exists():
        return _abortar(stages, "block_composition",
                         "decisoes_blocos.json (decisões de blocos condicionais da "
                         "etapa estratégica — INV-COMPOSICAO-BLOCOS) ausente")
    decisoes = json.loads(caminho.read_text(encoding="utf-8"))

    caminho_estado = caso / "estado_processual.json"
    if caminho_estado.exists():
        fatos_processuais = json.loads(caminho_estado.read_text(encoding="utf-8"))
        if not isinstance(fatos_processuais, dict):
            return _abortar(stages, "block_composition",
                             "estado_processual.json deve ser um objeto {ESTADO: valor}")
    else:
        fatos_processuais = {}

    try:
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
    except ComposicaoAbortada as e:
        return _abortar(stages, e.stage, e.motivo)

    stages.append({"name": "block_composition_decisoes", "status": "ok",
                    "fonte": str(caminho), "catalogo": str(catalogo_path)})
    return decisoes, fatos_processuais


def _etapa_rag_validacao(caso: Path, stages: list):
    caminho = caso / "citacoes.json"
    if not caminho.exists():
        stages.append({"name": "rag_legal_validation", "status": "nao_necessario"})
        return [], []
    citacoes = json.loads(caminho.read_text(encoding="utf-8"))
    validadas, nao_validadas = [], []
    for c in citacoes:
        r = validar_citacao(c, sugerir_candidato=True)
        item = {"input": c, "status": r["status"], "source_id": r["source_id"],
                "motivo": r["motivo"]}
        (validadas if r["status"] in ("VALIDADA", "PARCIALMENTE_VALIDADA")
         else nao_validadas).append(item)
    stages.append({"name": "rag_legal_validation", "status": "ok",
                    "citacoes_validadas": len(validadas),
                    "citacoes_nao_validadas": len(nao_validadas)})
    return validadas, nao_validadas


def _etapa_juizo(dados: dict, stages: list, resolver_juizo_fn=None):
    """INV-JUIZO-DATAJUD: {{JUIZO}} deixa de ser conteúdo gerativo do
    redator — é resolvido deterministicamente via DataJud/CNJ (+ IBGE
    para a comarca) a partir de NUMERO_PROCESSO. Fail-closed em qualquer
    cenário de indisponibilidade/ambiguidade (datajud_client.py) — nunca
    presume a vara. `resolver_juizo_fn` é injetável (testabilidade — a
    suíte automatizada nunca depende da API real, CLAUDE.md/instrução
    desta correção); por padrão usa datajud_client.resolver_juizo."""
    if str(dados.get("JUIZO", "")).strip():
        return _abortar(stages, "juizo_datajud",
                         "JUIZO não deve ser fornecido em placeholders.json "
                         "(saída do redator/humanizer) — é resolvido "
                         "automaticamente via DataJud/CNJ (INV-JUIZO-DATAJUD); "
                         "remova o campo da saída do redator.")
    numero_processo = str(dados.get("NUMERO_PROCESSO", "")).strip()
    if not numero_processo:
        return _abortar(stages, "juizo_datajud",
                         "NUMERO_PROCESSO ausente/vazio — necessário para "
                         "resolver {{JUIZO}} via DataJud/CNJ antes de "
                         "prosseguir.")
    resolver = resolver_juizo_fn or datajud_client.resolver_juizo
    try:
        resolucao = resolver(numero_processo)
    except datajud_client.JuizoResolutionError as e:
        return _abortar(stages, "juizo_datajud", e.motivo)

    dados["JUIZO"] = resolucao["juizo"]
    stages.append({"name": "juizo_datajud", "status": "ok",
                    "tribunal": resolucao.get("tribunal"),
                    "orgao_julgador": resolucao.get("orgao_julgador_nome"),
                    "comarca": resolucao.get("comarca")})
    return True


def _etapa_placeholders(caso: Path, stages: list, tempestividade_valor: str, resolver_juizo_fn=None):
    caminho = caso / "placeholders.json"
    if not caminho.exists():
        return _abortar(stages, "drafting_humanization",
                         "placeholders.json (saída de redator-peca-processual-"
                         "elite + humanizer-pt-br) ausente")
    dados = dict(json.loads(caminho.read_text(encoding="utf-8")))
    dados["FOTOS_DA_IRREGULARIADE"] = MARCADOR_FOTOS
    if not str(dados.get("TEMPESTIVIDADE_CASO", "")).strip():
        dados["TEMPESTIVIDADE_CASO"] = tempestividade_valor

    juizo_ok = _etapa_juizo(dados, stages, resolver_juizo_fn)
    if isinstance(juizo_ok, dict) and juizo_ok.get("status") == "PIPELINE_ABORTED":
        return juizo_ok

    faltando = [p for p in PLACEHOLDERS_OBRIGATORIOS_NAO_VAZIOS
                if not str(dados.get(p, "")).strip()]
    if faltando:
        return _abortar(stages, "placeholders",
                         f"placeholders obrigatórios ausentes/vazios: {faltando}")

    sem_conteudo_real = [p for p in PLACEHOLDERS_CRITICOS_NAO_SENTINELA
                          if SENTINELA_AUSENCIA in str(dados.get(p, "")).upper()]
    if sem_conteudo_real:
        return _abortar(stages, "placeholders",
                         f"dado essencial ausente para: {sem_conteudo_real} — "
                         f"o redator sinalizou corretamente a ausência (não "
                         f"inventou o valor), mas um compromisso financeiro/"
                         f"factual concreto não pode ficar como sentinela de "
                         f"ausência no documento final (CLAUDE.md §17).")

    # Etapa 3 (gate pós-diagnóstico forense): conteúdo semanticamente
    # incompatível com o contrato do placeholder (ex.: AUTOR com cláusula
    # de qualificação/CPF duplicando o texto fixo do template — achado
    # real que causou quebra de página) nunca alcança o template.
    ok_semantica, erros_semantica = validar_semantica(dados)
    if not ok_semantica:
        return _abortar(stages, "placeholders",
                         f"conteúdo semanticamente inválido: {erros_semantica}")

    stages.append({"name": "drafting_humanization", "status": "ok",
                    "fonte": str(caminho)})
    return dados


def _etapa_paragrafo_380(dados: dict, schema_path: Path, stages: list):
    """INV-PARAGRAFO-380 (Etapa 5.2): parágrafo de conteúdo variável acima
    de 380 caracteres SEM ESPAÇOS aborta antes da geração do DOCX final — nunca gera
    sabendo que a invariante foi violada (CLAUDE.md §17). Etapa 5.3
    acrescenta a densidade por bloco (LIMITES_DENSIDADE_BLOCO) — 380 é
    teto por parágrafo, não meta; um bloco pode respeitar o teto em todo
    parágrafo e ainda ser prolixo por acumulação."""
    schema = carregar_schema(schema_path)
    ok, erros = validar_paragrafos_placeholders(dados, schema)
    if not ok:
        return _abortar(stages, "paragrafo_380",
                         f"parágrafo(s) acima de 380 caracteres sem espaços (INV-PARAGRAFO-380): {erros}")
    ok_densidade, erros_densidade = validar_densidade_blocos(dados)
    if not ok_densidade:
        return _abortar(stages, "densidade_bloco",
                         f"bloco(s) com densidade excessiva (Etapa 5.3): {erros_densidade}")
    stages.append({"name": "paragrafo_380", "status": "ok"})
    return True


def _etapa_zonas(caso: Path, stages: list, catalogo_path: Path, fatos: list = None,
                  contexto_institucional: dict = None):
    """Etapa 5.8-B — INV-ZONA-COMPLEMENTACAO (SPEC-0001 §58, ADR-0010).

    Lê `zonas.json` (opcional — ausente significa TODAS as zonas vazias,
    que é o estado normal da peça) e valida o conteúdo produzido pelo
    Redator/Humanizer ANTES de qualquer composição: tamanho (limites do
    catálogo, nunca hardcode), prefixo de título numerado, sentinela
    textual, travessão e, desde a Etapa 5.8-D.1, continuidade com o texto
    institucional adjacente (INV-CONTINUIDADE-ZONA).

    `contexto_institucional` é o MESMO dicionário que
    `_etapa_contexto_institucional` já produz para alimentar o Redator
    (`contexto_institucional[zona_id]` -> lista de ocorrências com
    `antes`/`depois`) — nenhuma extração nova, nenhum I/O novo; só um
    parâmetro a mais repassando dado já computado nesta mesma execução.

    O que este estágio NÃO faz, deliberadamente:
      - não decide a inclusão da zona (isso é resolver_estados_zonas, a
        partir do bloco-pai + gate fático + presença de conteúdo);
      - não pergunta nada ao advogado (§21 — zona não tem decisão humana);
      - não redige nem apara texto (fail-closed, nunca corrige em silêncio);
      - não aplica o teste de necessidade (§8) — esse é comportamental, do
        Redator, e roda antes de qualquer conteúdo chegar aqui;
      - não altera o texto institucional em hipótese alguma — `antes`/
        `depois` são lidos só para comparação (INV-CONTINUIDADE-ZONA)."""
    caminho = caso / "zonas.json"
    if not caminho.exists():
        stages.append({"name": "zonas", "status": "ok", "conteudo": {},
                        "nota": "zonas.json ausente — todas as zonas vazias (estado normal)"})
        return {}

    try:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return _abortar(stages, "zonas", f"zonas.json malformado: {e}")
    if not isinstance(conteudo, dict):
        return _abortar(stages, "zonas", "zonas.json deve ser um objeto {ZONA_ID: conteúdo}")

    try:
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
    except ComposicaoAbortada as e:
        return _abortar(stages, e.stage, e.motivo)

    # Etapa 5.8-C — proveniência: normaliza o contrato estruturado
    # ({"conteudo": ..., "fatos": [...]}) e confere que nenhum dado
    # numérico do texto existe sem lastro documental declarado. As fontes
    # aceitas são as MESMAS que já sustentam a peça (`fatos.json`) — a
    # zona não abre uma base probatória própria. Etapa 5.8-C.1: `fatos`
    # inteiro (não só os nomes dos documentos), porque a checagem passou a
    # exigir que o dado documental esteja NAQUELE documento.
    zonas_catalogo = {z["id"]: z for z in catalogo.get("zones", [])}
    texto_por_zona, proveniencia, erros_proveniencia = {}, {}, []
    for zid, bruto in sorted(conteudo.items()):
        texto, fatos_zona, erros_forma = normalizar_conteudo_zona(bruto)
        erros_proveniencia.extend(f"{zid}: {e}" for e in erros_forma)
        texto_por_zona[zid] = texto
        if not texto:
            continue
        proveniencia[zid] = fatos_zona
        if zonas_catalogo.get(zid, {}).get("exige_proveniencia", True):
            erros_proveniencia.extend(
                validar_proveniencia_zona(texto, fatos_zona, zid, fatos))
    if erros_proveniencia:
        return _abortar(stages, "zonas",
                         f"proveniência do conteúdo de zona inválida: {erros_proveniencia}")

    ok_densidade, erros_densidade = validar_densidade_zonas(texto_por_zona, catalogo.get("zones", []))
    if not ok_densidade:
        return _abortar(stages, "zonas",
                         f"conteúdo de zona fora dos limites do catálogo: {erros_densidade}")

    ok_semantica, erros_semantica = validar_semantica_zonas(texto_por_zona)
    if not ok_semantica:
        return _abortar(stages, "zonas",
                         f"conteúdo de zona semanticamente inválido: {erros_semantica}")

    # Etapa 5.8-D.1 — INV-CONTINUIDADE-ZONA: a zona precisa ser
    # continuação natural do texto institucional adjacente (TEXTO
    # INSTITUCIONAL ANTERIOR -> ZONA -> TEXTO INSTITUCIONAL POSTERIOR).
    # Fail-closed: nunca exclui a zona nem toca o texto institucional —
    # devolve o motivo para a Skill `contestacao` reformular só o
    # conteúdo da zona (não há mecanismo de retry automático no código:
    # Skills não são chamáveis por este script, mesma limitação de
    # sempre; "nova tentativa" é a orquestração, não um loop em Python).
    ok_continuidade, erros_continuidade = validar_continuidade_zonas(
        texto_por_zona, contexto_institucional or {})
    if not ok_continuidade:
        return _abortar(stages, "zonas",
                         f"zona repete abertura do texto institucional adjacente "
                         f"(INV-CONTINUIDADE-ZONA): {erros_continuidade}")

    preenchidas = sorted(k for k, v in texto_por_zona.items() if v.strip())
    stages.append({"name": "zonas", "status": "ok", "fonte": str(caminho),
                    "zonas_com_conteudo": preenchidas,
                    "fatos_por_zona": {z: len(proveniencia.get(z, [])) for z in preenchidas}})
    return texto_por_zona


def _etapa_pedidos_composicionais(dados: dict, decisoes_blocos: dict, catalogo_path: Path,
                                   fatos_processuais: dict, stages: list):
    """Etapa 5.3 §18: PEDIDOS_FINAIS não pode reintroduzir tese excluída
    pelo motor composicional (ex.: pedido de revogação de gratuidade com
    PRELIMINAR_REVOGACAO_GRATUIDADE=EXCLUIR). Resolve os estados dos
    blocos (mesma função usada por gerar_peca_com_blocos — chamada de novo
    aqui é redundante, mas barata e determinística) só para essa checagem
    de conteúdo, antes de compor o DOCX."""
    try:
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
        estados = validar_e_resolver_decisoes(catalogo, decisoes_blocos, fatos_processuais)
    except ComposicaoAbortada as e:
        # mesmo erro que _etapa_template encontraria mais adiante — reporta
        # aqui primeiro, mesmo stage/motivo, sem duplicar mensagens diferentes.
        return _abortar(stages, "block_composition", f"{e.stage}: {e.motivo}")
    erros = validar_pedidos_composicionais(dados.get("PEDIDOS_FINAIS", ""), estados)
    if erros:
        return _abortar(stages, "pedidos_composicionais",
                         f"PEDIDOS_FINAIS incoerente com blocos excluídos (Etapa 5.3 §18): {erros}")
    stages.append({"name": "pedidos_composicionais", "status": "ok"})
    return True


def _etapa_template(dados: dict, decisoes_blocos: dict, template: Path, schema: Path,
                     catalogo: Path, output: Path, stages: list, fatos_processuais: dict = None,
                     conteudo_zonas: dict = None):
    relatorio = gerar_peca_com_blocos(str(template), str(schema), str(catalogo),
                                       dados, decisoes_blocos, str(output),
                                       fatos_processuais=fatos_processuais,
                                       conteudo_zonas=conteudo_zonas)
    if relatorio["status"] != "OK":
        etapa_engine = relatorio.get("etapa", "")
        # Etapa 5.8-B: falhas de zona são reportadas no stage `zonas`
        # (mesmo nome do estágio que produziu o conteúdo), exceto
        # modelo_institucional_desatualizado, que é condição operacional da
        # INSTALAÇÃO e merece stage próprio para a Skill orientar o
        # advogado a atualizar o modelo (§15).
        if etapa_engine == "modelo_institucional_desatualizado":
            return _abortar(stages, "modelo_institucional_desatualizado",
                             f"{relatorio.get('erros')}")
        if etapa_engine.startswith("zona"):
            return _abortar(stages, "zonas", f"{etapa_engine}: {relatorio.get('erros')}")
        eh_block_composition = etapa_engine.startswith(
            ("catalogo", "decisao", "sdt_", "tag_", "cardinalidade", "estado")
        ) or etapa_engine == "gate_fatico_nao_satisfeito"
        return _abortar(stages, "block_composition" if eh_block_composition else "template_engine",
            f"{relatorio.get('etapa')}: {relatorio.get('erros')}")
    stages.append({"name": "template_engine", "status": "ok",
                    "template_lock": relatorio["template_lock"],
                    "blocos_incluidos": relatorio["blocos_incluidos"],
                    "blocos_excluidos": relatorio["blocos_excluidos"],
                    "containers_derivados": relatorio["containers_derivados"],
                    "zonas": relatorio.get("zonas", {}),
                    "numeracao": relatorio.get("numeracao", {})})
    return relatorio


def gerar(caso_dir, output_path, template=TEMPLATE_PADRAO, schema=SCHEMA_PADRAO,
          catalogo_blocos=CATALOGO_BLOCOS_PADRAO, resolver_juizo_fn=None) -> dict:
    """`resolver_juizo_fn`: injetável para testes (INV-JUIZO-DATAJUD) —
    padrão None usa datajud_client.resolver_juizo (API real)."""
    caso = Path(caso_dir)
    stages = []

    # Etapa 5.7-C — PRIMEIRA etapa, incondicional: sem contexto
    # institucional extraído do modelo real, o pipeline nem chega a olhar
    # os documentos do caso (INV-MODELO-INSTITUCIONAL-FONTE-PRIMARIA).
    contexto_institucional = _etapa_contexto_institucional(
        Path(template), Path(schema), Path(catalogo_blocos), stages)
    if isinstance(contexto_institucional, dict) and contexto_institucional.get("status") == "PIPELINE_ABORTED":
        return contexto_institucional

    fatos = _etapa_fatos(caso, stages)
    if isinstance(fatos, dict) and fatos.get("status") == "PIPELINE_ABORTED":
        return fatos

    tempestividade_valor = _etapa_tempestividade(caso, stages)
    if isinstance(tempestividade_valor, dict) and tempestividade_valor.get("status") == "PIPELINE_ABORTED":
        return tempestividade_valor

    estrategia = _etapa_estrategia(caso, stages)
    if isinstance(estrategia, dict) and estrategia.get("status") == "PIPELINE_ABORTED":
        return estrategia

    resultado_blocos = _etapa_blocos(caso, stages, Path(catalogo_blocos))
    if isinstance(resultado_blocos, dict) and resultado_blocos.get("status") == "PIPELINE_ABORTED":
        return resultado_blocos
    decisoes_blocos, fatos_processuais = resultado_blocos

    validadas, nao_validadas = _etapa_rag_validacao(caso, stages)

    dados = _etapa_placeholders(caso, stages, tempestividade_valor, resolver_juizo_fn)
    if isinstance(dados, dict) and dados.get("status") == "PIPELINE_ABORTED":
        return dados

    paragrafo_ok = _etapa_paragrafo_380(dados, Path(schema), stages)
    if isinstance(paragrafo_ok, dict) and paragrafo_ok.get("status") == "PIPELINE_ABORTED":
        return paragrafo_ok

    pedidos_ok = _etapa_pedidos_composicionais(dados, decisoes_blocos, Path(catalogo_blocos),
                                                fatos_processuais, stages)
    if isinstance(pedidos_ok, dict) and pedidos_ok.get("status") == "PIPELINE_ABORTED":
        return pedidos_ok

    conteudo_zonas = _etapa_zonas(caso, stages, Path(catalogo_blocos), fatos,
                                   contexto_institucional=contexto_institucional)
    if isinstance(conteudo_zonas, dict) and conteudo_zonas.get("status") == "PIPELINE_ABORTED":
        return conteudo_zonas

    relatorio_engine = _etapa_template(dados, decisoes_blocos, Path(template), Path(schema),
                                        Path(catalogo_blocos), Path(output_path), stages,
                                        fatos_processuais=fatos_processuais,
                                        conteudo_zonas=conteudo_zonas)
    if isinstance(relatorio_engine, dict) and relatorio_engine.get("status") == "PIPELINE_ABORTED":
        return relatorio_engine

    return {
        "status": "OK",
        "stages": stages,
        "peca": "Contestação",
        "pipeline": "concluido",
        "estrategia": "OK",
        "tempestividade": tempestividade_valor,
        "rag": "consultado" if (caso / "citacoes.json").exists() else "nao_necessario",
        "fontes_recuperadas": len(validadas) + len(nao_validadas),
        "citacoes_validadas": len(validadas),
        "citacoes_nao_validadas": len(nao_validadas),
        "fatos_com_proveniencia": len(fatos),
        "contexto_institucional": "OK",
        "template_lock": "OK",
        "placeholders": "OK",
        "fotos": "INSERÇÃO MANUAL",
        "blocos_incluidos": relatorio_engine["blocos_incluidos"],
        "blocos_excluidos": relatorio_engine["blocos_excluidos"],
        "containers_derivados": relatorio_engine["containers_derivados"],
        "blocos_indeterminados": relatorio_engine["blocos_indeterminados"],
        "zonas_incluidas": relatorio_engine.get("zonas_incluidas", []),
        "zonas_excluidas": relatorio_engine.get("zonas_excluidas", []),
        "documento_final": relatorio_engine["documento_final"],
    }


def main():
    garantir_utf8()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--caso", required=True, help="diretório com o caso (fatos.json, "
                    "estrategia.md, citacoes.json, tempestividade.json, placeholders.json)")
    ap.add_argument("--output", required=True, help="caminho do DOCX final")
    ap.add_argument("--relatorio", help="se informado, grava o relatório operacional aqui")
    ap.add_argument("--template", default=str(TEMPLATE_PADRAO))
    ap.add_argument("--schema", default=str(SCHEMA_PADRAO))
    ap.add_argument("--catalogo-blocos", default=str(CATALOGO_BLOCOS_PADRAO))
    args = ap.parse_args()

    relatorio = gerar(args.caso, args.output, args.template, args.schema, args.catalogo_blocos)
    saida = json.dumps(relatorio, ensure_ascii=False, indent=2)
    print(saida)
    if args.relatorio:
        Path(args.relatorio).write_text(saida, encoding="utf-8")
    sys.exit(0 if relatorio["status"] == "OK" else 1)


if __name__ == "__main__":
    main()
