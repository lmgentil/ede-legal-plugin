#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legal_readiness.py — checagens determinísticas de prontidão jurídica do
Core (Gate 6.4-A/6.4-B, ADR-0015, ADR-0017).

Objetivo do gate: permitir que `mcp_server/server.py` (`ede_health`)
reporte verdade sobre dois pré-requisitos da Contestação — Modelo Oficial
e corpus RAG — em vez dos estados `NOT_CONFIGURED` fixos da Etapa 6.1.
Este módulo é CORE (reutilizável por qualquer host, nunca importa nada de
`mcp_server/`) — o servidor MCP só chama as duas funções públicas abaixo
e traduz o resultado para `HealthCheck`; nenhuma lógica de validação vive
duplicada no adapter (ADR-0015, "MCP fica fino").

Fail-closed (CLAUDE.md §17): as duas funções nunca levantam exceção por
condição de runtime esperada (arquivo ausente, hash divergente, corpus
incompleto, objeto GCS ausente/geração divergente) — sempre devolvem
`ResultadoReadiness` com `status` explícito. Uma exceção genuína (bug de
programação, schema/catálogo do próprio plugin corrompido) propaga sem
mascaramento, como no restante do Core.

Nenhum conteúdo sensível (texto de documento, caminho absoluto de posse
do advogado, corpo de exceção, token de acesso) entra em `detail` — só
fatos estruturais (contagens, nomes de diploma/bloco, motivo de rejeição
já catalogado alhures). Mesma disciplina de `mcp_server/server.py`
(CLAUDE.md §12/§18).

Gate 6.4-B — Arquitetura A′ (ADR-0017 §6): `avaliar_modelo_oficial()`
adquire o Modelo Oficial de um bucket GCS privado, pinado por
bucket+objeto+geração (nunca "latest"), com o SHA-256 verificado
localmente contra o valor configurado — nunca o hash remoto (MD5/CRC32C)
reportado pela API, que é só metadado de auditoria (§5 do gate). O modo
GCS ativa quando QUALQUER uma das três variáveis
`EDE_MODELO_OFICIAL_GCS_{BUCKET,OBJECT,GENERATION}` está presente — nesse
caso as três MAIS `EDE_MODELO_OFICIAL_SHA256` são exigidas juntas
(configuração parcial é `NOT_CONFIGURED`, nunca uma tentativa de baixar
mesmo assim). Sem NENHUMA das três, o módulo cai para o modo local
(`EDE_MODELO_OFICIAL_PATH`, Gate 6.4-A) — mecanismo de
desenvolvimento/teste; a produção real nunca define
`EDE_MODELO_OFICIAL_PATH` (só as variáveis GCS), então os dois modos
nunca colidem em runtime real. Autenticação via `google.auth.default()`
(metadata server do Cloud Run em produção; ADC do titular fora dele) —
nenhuma chave de service account é lida de arquivo por este módulo.
`google-auth` + `requests` são as dependências novas (ver
mcp_server/requirements.txt para a análise de footprint e para o achado
real do Gate 6.4-C que tornou `requests` necessária — não opcional —
para a detecção de ambiente Cloud Run/GCE do próprio `google-auth`).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_block_engine import (  # noqa: E402
    ComposicaoAbortada,
    carregar_catalogo,
    validar_catalogo,
)
from docx_package import PacoteDocxAbortada, extrair_pacote_docx  # noqa: E402
from docx_template_engine import carregar_schema  # noqa: E402
from instalar_modelo_oficial import validar_contrato_modelo  # noqa: E402

Status = Literal["READY", "NOT_READY", "NOT_CONFIGURED", "ERROR"]

SCHEMA_PADRAO = BASE / "templates" / "contestacao" / "schema.json"
CATALOGO_PADRAO = BASE / "templates" / "contestacao" / "blocos.json"

RAG_DIR_PADRAO = BASE / "rag"
MANIFESTO_CORPUS_PADRAO = RAG_DIR_PADRAO / "corpus_manifest.json"

# Modo local (Gate 6.4-A) — desenvolvimento/teste; nunca definido em
# produção (produção define só as três variáveis GCS abaixo).
ENV_MODELO_PATH = "EDE_MODELO_OFICIAL_PATH"
# Compartilhada pelos dois modos — o pin de integridade é sempre o mesmo
# nome, independentemente de onde o arquivo é lido.
ENV_MODELO_SHA256 = "EDE_MODELO_OFICIAL_SHA256"

# Modo GCS (Gate 6.4-B, Arquitetura A′, ADR-0017 §6) — produção real.
# "MODELO_OFICIAL" é o termo canônico já em uso desde a Etapa 5.10
# (instalar_modelo_oficial.py) e o Gate 6.4-A — nomes ingleses como
# "OFFICIAL_MODEL" não são introduzidos para não fragmentar a convenção
# já committada.
ENV_GCS_BUCKET = "EDE_MODELO_OFICIAL_GCS_BUCKET"
ENV_GCS_OBJECT = "EDE_MODELO_OFICIAL_GCS_OBJECT"
ENV_GCS_GENERATION = "EDE_MODELO_OFICIAL_GCS_GENERATION"

_GCS_ESCOPO_LEITURA = "https://www.googleapis.com/auth/devstorage.read_only"
_GCS_API_BASE = "https://storage.googleapis.com/storage/v1"


class ErroAquisicaoGCS(Exception):
    """Fail-closed: qualquer falha ao adquirir o objeto do GCS (rede,
    autenticação, objeto/geração não encontrados, geração servida
    divergente da pinada) vira este erro tipado — nunca uma exceção crua
    de `httpx2`/`google-auth` propagando até `avaliar_modelo_oficial`.
    `motivo` é um rótulo estrutural fechado, nunca a mensagem bruta da
    biblioteca (que pode incluir corpo de resposta HTTP)."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


class _RespostaHttpx:
    """Adapta `httpx2.Response` à interface `google.auth.transport.
    Response` (status/headers/data) — as três únicas propriedades que
    `Credentials.refresh()` lê."""

    def __init__(self, resposta):
        self._resposta = resposta

    @property
    def status(self):
        return self._resposta.status_code

    @property
    def headers(self):
        return self._resposta.headers

    @property
    def data(self):
        return self._resposta.content


class _RequisicaoHttpx:
    """Adapta `httpx2` à interface `google.auth.transport.Request`
    (callable), usada só para `Credentials.refresh()` (a chamada
    EXPLÍCITA que busca o token de acesso) — a leitura do objeto GCS em
    si usa `httpx2` diretamente em `_baixar_modelo_oficial_gcs`.

    Gate 6.4-C1 (achado do Gate 6.4-C, rollback de produção real):
    `requests` passou a ser dependência do projeto de qualquer forma —
    `google.auth.compute_engine._metadata` (a DETECÇÃO do ambiente
    Cloud Run/GCE, interna ao `google.auth.default()`, que roda ANTES
    desta classe ser chamada) tem `import requests` incondicional,
    nunca opcional. Esta classe continua existindo porque evita que a
    chamada explícita de refresh do token dependa de `requests`/
    `urllib3` também — não elimina `requests` da árvore de dependências
    do processo, só limita onde ele é efetivamente exercitado pelo
    código do EDE (nenhuma linha própria importa `requests`
    diretamente; ver mcp_server/requirements.txt)."""

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        import httpx2

        resposta = httpx2.request(method, url, content=body, headers=headers, timeout=timeout)
        return _RespostaHttpx(resposta)


def _baixar_modelo_oficial_gcs(bucket: str, objeto: str, generation: str) -> bytes:
    """Baixa exatamente `generation` de `objeto` em `bucket` — nunca
    "latest", nunca outra geração, nunca reconstrução (CLAUDE.md §13).
    Import de `google.auth`/`httpx2` só aqui dentro (lazy): o modo local
    (Gate 6.4-A) e a checagem do corpus RAG nunca pagam o custo de
    importar a pilha GCS."""
    import google.auth

    try:
        credenciais, _ = google.auth.default(scopes=[_GCS_ESCOPO_LEITURA])
        credenciais.refresh(_RequisicaoHttpx())
    except Exception as e:
        raise ErroAquisicaoGCS("autenticacao_falhou") from e

    import httpx2

    objeto_codificado = urllib.parse.quote(objeto, safe="")
    url = (
        f"{_GCS_API_BASE}/b/{bucket}/o/{objeto_codificado}"
        f"?alt=media&generation={generation}"
    )
    cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}

    try:
        resposta = httpx2.get(url, headers=cabecalhos, timeout=30.0)
    except httpx2.HTTPError as e:
        raise ErroAquisicaoGCS("rede_falhou") from e

    if resposta.status_code == 404:
        raise ErroAquisicaoGCS("objeto_ou_geracao_nao_encontrado")
    if resposta.status_code != 200:
        raise ErroAquisicaoGCS("gcs_status_inesperado")

    # Defesa em profundidade: a própria query string já pina a geração
    # (a API deveria recusar servir outra), mas os bytes só são aceitos
    # se o cabeçalho de resposta confirmar EXATAMENTE a geração pedida —
    # nunca avaliamos bytes de uma geração diferente da configurada.
    generation_servida = resposta.headers.get("x-goog-generation")
    if generation_servida is not None and str(generation_servida) != str(generation):
        raise ErroAquisicaoGCS("geracao_servida_diverge_da_pinada")

    return resposta.content


@dataclass(frozen=True)
class ResultadoReadiness:
    status: Status
    detail: str


def _normalizar_quebras_de_linha(conteudo: bytes) -> bytes:
    """Normaliza CRLF/CR isolado para LF antes do hash — achado real do
    Gate 6.4-B: `core.autocrlf=true` no ambiente de desenvolvimento
    Windows expande as quebras de linha LF do blob Git (canônico) para
    CRLF na árvore de trabalho local; um manifesto gerado a partir dessa
    árvore de trabalho local diverge do checkout Linux real (CI, Cloud
    Run em produção — sempre LF), fazendo `avaliar_corpus_rag` reportar
    `NOT_READY` para um corpus estruturalmente idêntico. A integridade
    que interessa aqui é a do CONTEÚDO do corpus legislativo, nunca a
    convenção de quebra de linha de um checkout específico — normalizar
    torna o fingerprint invariante ao sistema operacional/configuração
    Git de quem gerou o manifesto ou de quem roda a checagem."""
    return conteudo.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _fingerprint_diretorio(diretorio: Path, base: Path | None = None) -> tuple[str, int]:
    """SHA-256 determinístico sobre (caminho relativo, bytes normalizados)
    de todo arquivo em `diretorio`, ordenado por caminho — mesmo
    mecanismo usado para gerar `rag/corpus_manifest.json`. Não é um
    índice de busca, só um fingerprint estrutural: existência +
    integridade do CONTEÚDO do corpus declarado (quebra de linha
    normalizada, ver `_normalizar_quebras_de_linha`), nada de
    tokenização/embeddings (aquilo é `rag/search_hybrid.py`, fora do
    escopo de uma checagem de saúde).

    `base` é o diretório contra o qual o caminho relativo de cada arquivo
    é calculado (default: o pai de `diretorio` — o mesmo `rag_dir` que o
    chamador já resolveu); nunca a constante `RAG_DIR_PADRAO` fixa, para
    que a função funcione igual em produção e em corpus sintético de
    teste apontando para outro diretório.

    A ordenação usa EXPLICITAMENTE a string `as_posix()` (a mesma que
    entra no hash) como chave — nunca `sorted(caminhos)` puro. Achado
    real do Gate 6.4-B: `pathlib.Path.__lt__` compara `WindowsPath` por
    `os.path.normcase` (minúsculas, case-INsensitive) mas `PosixPath`
    por igualdade de string exata (case-SENSITIVE); para nomes como
    "TII_C01_P01.md" vs "TIII_P01.md", isso INVERTE a ordem relativa
    entre Windows e Linux (posição 4: `_` vs `I` maiúsculo ordena
    `TIII` antes; `_` vs `i` minúsculo ordena `TII_` antes) — mesmo
    conteúdo, mesmo hash por arquivo, HASH AGREGADO DIFERENTE, porque a
    ordem de concatenação divergia. Corrigido ordenando pela chave
    string explícita, que usa comparação de codepoint Unicode pura,
    idêntica em qualquer SO — o manifesto gerado no Windows agora bate
    byte a byte com a checagem rodando em produção (Linux)."""
    if base is None:
        base = diretorio.parent
    arquivos = sorted(
        (p for p in diretorio.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(base).as_posix(),
    )
    h = hashlib.sha256()
    for f in arquivos:
        rel = f.relative_to(base).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(_normalizar_quebras_de_linha(f.read_bytes()))
        h.update(b"\x00")
    return h.hexdigest(), len(arquivos)


def avaliar_corpus_rag(
    rag_dir: Path = RAG_DIR_PADRAO,
    manifesto_path: Path = MANIFESTO_CORPUS_PADRAO,
) -> ResultadoReadiness:
    """Corpus jurídico institucional (legislação — CPC/CC/CDC/L8987/L9427/
    REN1000; nunca jurisprudência, INV-CONTESTACAO-SEM-PESQUISA-
    JURISPRUDENCIAL, CLAUDE.md §10) está presente e íntegro conforme o
    manifesto versionado (`rag/corpus_manifest.json`, gerado a partir do
    mesmo corpus já público/rastreado no repositório — nenhum asset
    privado é lido aqui).

    READY          — todo diploma do manifesto presente, contagem de
                      arquivos e fingerprint SHA-256 batendo exatamente.
    NOT_READY       — manifesto presente mas corpus ausente/incompleto/
                      divergente (nunca recorta silenciosamente).
    NOT_CONFIGURED  — manifesto ausente (corpus nunca foi versionado
                      nesta instalação)."""
    if not manifesto_path.is_file():
        return ResultadoReadiness(
            "NOT_CONFIGURED",
            "Manifesto do corpus RAG (rag/corpus_manifest.json) ausente.",
        )

    try:
        manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ResultadoReadiness(
            "ERROR", "Manifesto do corpus RAG ilegível ou corrompido."
        )

    diplomas = manifesto.get("diplomas", {})
    if not diplomas:
        return ResultadoReadiness(
            "NOT_CONFIGURED", "Manifesto do corpus RAG não declara diplomas."
        )

    for nome, esperado in sorted(diplomas.items()):
        dirp = rag_dir / f"chunks_{nome}"
        if not dirp.is_dir():
            return ResultadoReadiness(
                "NOT_READY", f"Corpus do diploma {nome} ausente (chunks_{nome}/)."
            )
        fingerprint, contagem = _fingerprint_diretorio(dirp, base=rag_dir)
        if contagem != esperado.get("arquivos"):
            return ResultadoReadiness(
                "NOT_READY",
                f"Corpus do diploma {nome} incompleto: "
                f"{contagem} arquivo(s) presente(s), "
                f"{esperado.get('arquivos')} esperado(s) pelo manifesto.",
            )
        if fingerprint != esperado.get("sha256"):
            return ResultadoReadiness(
                "NOT_READY",
                f"Corpus do diploma {nome} divergente do manifesto "
                f"(SHA-256 não bate) — possível corrupção ou alteração "
                f"não versionada.",
            )

    total_esperado = manifesto.get("total_chunks")
    total_real = sum(v.get("arquivos", 0) for v in diplomas.values())
    if total_esperado is not None and total_real != total_esperado:
        return ResultadoReadiness(
            "NOT_READY",
            "Total de chunks do corpus RAG diverge do manifesto.",
        )

    return ResultadoReadiness(
        "READY",
        f"Corpus RAG íntegro: {len(diplomas)} diploma(s), "
        f"{total_real} chunk(s) verificado(s) contra o manifesto "
        f"(versão {manifesto.get('versao', 'sem versão declarada')}).",
    )


def _validar_conteudo_modelo_oficial(
    conteudo: bytes,
    sha_esperado: str,
    schema_path: Path,
    catalogo_path: Path,
) -> ResultadoReadiness:
    """Validação COMPARTILHADA pelos dois modos de aquisição (local e
    GCS) — SHA-256 pinado, depois estrutura OOXML, depois contrato
    institucional. Nenhuma lógica de aquisição (de onde vieram os bytes)
    entra aqui; só o que se faz com bytes já em mãos. `conteudo` nunca é
    logado nem aparece em nenhum `detail` devolvido."""
    sha_real = hashlib.sha256(conteudo).hexdigest()
    if sha_real.lower() != sha_esperado.strip().lower():
        return ResultadoReadiness(
            "NOT_READY",
            "Modelo Oficial provisionado não bate com o SHA-256 pinado "
            "na configuração — arquivo rejeitado (fail-closed).",
        )

    try:
        schema = carregar_schema(schema_path)
        catalogo = carregar_catalogo(catalogo_path)
        validar_catalogo(catalogo)
    except (OSError, ValueError, ComposicaoAbortada):
        return ResultadoReadiness(
            "ERROR",
            "Schema/catálogo institucional do próprio plugin inválido "
            "ou ilegível — instalação do plugin comprometida.",
        )

    with tempfile.TemporaryDirectory() as tmp:
        # Diretório temporário isolado, sempre removido pelo `with`
        # (sucesso ou exceção) — `extrair_pacote_docx` exige um caminho
        # de arquivo real (não aceita bytes em memória), então os bytes
        # do modo GCS também passam por um arquivo efêmero aqui, nunca
        # persistido além deste bloco (Gate 6.4-B §8, itens 8/10/M/N).
        caminho_efemero = Path(tmp) / "modelo-oficial.docx"
        caminho_efemero.write_bytes(conteudo)
        pacote_dir = Path(tmp) / "unpacked"
        try:
            extrair_pacote_docx(caminho_efemero, pacote_dir)
        except PacoteDocxAbortada:
            return ResultadoReadiness(
                "NOT_READY",
                "Modelo Oficial provisionado não é um pacote OOXML "
                "válido (arquivo corrompido ou não é .docx).",
            )

        divergencias = validar_contrato_modelo(pacote_dir, schema, catalogo)

    if divergencias:
        return ResultadoReadiness(
            "NOT_READY",
            f"Modelo Oficial provisionado diverge do contrato "
            f"institucional vigente ({len(divergencias)} divergência(s) "
            f"— schema/catálogo desatualizados em relação ao arquivo, "
            f"ou vice-versa).",
        )

    return ResultadoReadiness(
        "READY",
        "Modelo Oficial provisionado, íntegro (SHA-256 pinado conforme) "
        "e conforme o contrato institucional (placeholders e SDTs de "
        "blocos/zonas).",
    )


class ModeloOficialIndisponivel(Exception):
    """Levantada por `adquirir_bytes_modelo_oficial()` — `status` é um dos
    valores de `Status` (nunca `READY`, que exige validação de conteúdo,
    fora do escopo desta função) e `detail` é sempre seguro para aparecer
    num `ResultadoReadiness`/log de auditoria (nunca inclui caminho local,
    bytes, ou motivo interno de `ErroAquisicaoGCS`)."""

    def __init__(self, status: Status, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def adquirir_bytes_modelo_oficial() -> bytes:
    """Aquisição PURA do Modelo Oficial (GCS ou local) — sem validar
    SHA-256/estrutura/contrato (isso é `_validar_conteudo_modelo_oficial`,
    chamada por `avaliar_modelo_oficial` logo abaixo). Extraída para que
    outro consumidor Core (`scripts/preparar_contestacao.py`, Gate 6.5-A)
    obtenha os MESMOS bytes que a checagem de saúde já validou, sem
    duplicar a lógica de despacho GCS-vs-local. Levanta
    `ModeloOficialIndisponivel` em toda condição não-READY — nunca
    devolve bytes parciais/de outra geração."""
    gcs_bucket = os.environ.get(ENV_GCS_BUCKET)
    gcs_objeto = os.environ.get(ENV_GCS_OBJECT)
    gcs_generation = os.environ.get(ENV_GCS_GENERATION)
    sha_esperado = os.environ.get(ENV_MODELO_SHA256)

    modo_gcs_sinalizado = any((gcs_bucket, gcs_objeto, gcs_generation))

    if modo_gcs_sinalizado:
        if not (gcs_bucket and gcs_objeto and gcs_generation and sha_esperado):
            raise ModeloOficialIndisponivel(
                "NOT_CONFIGURED",
                f"Configuração GCS do Modelo Oficial incompleta — "
                f"{ENV_GCS_BUCKET}/{ENV_GCS_OBJECT}/{ENV_GCS_GENERATION}/"
                f"{ENV_MODELO_SHA256} devem estar todos presentes juntos; "
                f"nunca tenta adquirir com configuração parcial.",
            )
        try:
            return _baixar_modelo_oficial_gcs(gcs_bucket, gcs_objeto, gcs_generation)
        except ErroAquisicaoGCS:
            raise ModeloOficialIndisponivel(
                "NOT_READY",
                "Modelo Oficial não pôde ser adquirido do armazenamento "
                "privado configurado (objeto/geração ausente, falha de "
                "autenticação/rede, ou geração servida divergente da "
                "pinada) — nenhuma outra geração é tentada.",
            )

    caminho_env = os.environ.get(ENV_MODELO_PATH)
    if not caminho_env or not sha_esperado:
        raise ModeloOficialIndisponivel(
            "NOT_CONFIGURED",
            f"Nem {ENV_GCS_BUCKET}/{ENV_GCS_OBJECT}/{ENV_GCS_GENERATION} "
            f"(produção) nem {ENV_MODELO_PATH}/{ENV_MODELO_SHA256} "
            f"(local/teste) configurados — Modelo Oficial permanece fora "
            f"deste runtime (ADR-0009).",
        )

    caminho = Path(caminho_env)
    if not caminho.is_file():
        raise ModeloOficialIndisponivel(
            "NOT_READY",
            "Modelo Oficial configurado (modo local), mas o arquivo não "
            "foi encontrado no caminho provisionado.",
        )
    return caminho.read_bytes()


def avaliar_modelo_oficial(
    schema_path: Path = SCHEMA_PADRAO,
    catalogo_path: Path = CATALOGO_PADRAO,
) -> ResultadoReadiness:
    """Modelo Oficial da Contestação (asset privado externo, ADR-0009)
    está provisionado, íntegro (SHA-256 pinado) e estruturalmente
    conforme o contrato institucional. Aquisição delegada a
    `adquirir_bytes_modelo_oficial()` (dois modos, mutuamente exclusivos
    — GCS em produção, local em desenvolvimento/teste; ver docstring
    dela); esta função só cuida de SHA-256 + estrutura + contrato.

    READY          — bytes adquiridos (de onde for), SHA-256 bate,
                      contrato válido.
    NOT_READY       — configurado mas aquisição falhou, hash divergente,
                      pacote OOXML corrompido ou contrato desatualizado.
    NOT_CONFIGURED  — nem GCS nem local configurados, ou GCS
                      parcialmente configurado (nenhuma tentativa de
                      adivinhar/descobrir o arquivo — CLAUDE.md §13)."""
    sha_esperado = os.environ.get(ENV_MODELO_SHA256)
    try:
        conteudo = adquirir_bytes_modelo_oficial()
    except ModeloOficialIndisponivel as e:
        return ResultadoReadiness(e.status, e.detail)

    return _validar_conteudo_modelo_oficial(
        conteudo, sha_esperado, schema_path, catalogo_path
    )
