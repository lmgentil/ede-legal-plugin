#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
artifact_storage.py — armazenamento efêmero e entrega por URL opaca do
DOCX finalizado (Gate 6.6-E, ADR-0019; revisado no Gate 6.6-F/G).

Contexto (não repetido em cada função): o Gate 6.6-D provou, com Claude
e ChatGPT reais, que o `EmbeddedResource`/`BlobResourceContents` inline
(Decisão 5 v1 da ADR-0018) não é usável nativamente por nenhum dos dois
hosts MCP do produto. O Gate 6.6-E implementou o mecanismo v2 como URL
V4 assinada do GCS entregue diretamente ao cliente — homologada, mas
rejeitada como solução cross-client no Gate 6.6-F Fase 2
(DELIVERY-CLIENT-01: o ChatGPT acrescenta `utm_source=chatgpt.com` ao
link renderizado, o parâmetro extra altera a query string canônica
assinada e o GCS devolve `SignatureDoesNotMatch`). Histórico preservado
no `CHANGELOG.md` e na ADR-0019; este módulo implementa a substituição
aprovada ("Opção 1"):

    ede_finalizar_peca
      -> bytes validados (Template Lock/fidelidade/round-trip)
      -> objeto GCS privado `artifacts/<sha256(token)>.docx`
      -> https://<host canônico do EDE>/download/<token>
    GET /download/<token>
      -> o PRÓPRIO EDE lê o objeto privado, confere SHA-256 e entrega

A URL pública não depende de nenhuma query string assinada: a
autorização está INTEIRA no caminho (`/download/<token>`), e a query
string nunca é lida — parâmetros acrescentados pelo cliente não têm
efeito algum.

TOKEN (capacidade portadora opaca): `secrets.token_urlsafe(32)` — 256
bits do gerador criptográfico do sistema, 43 caracteres base64url, sem
nenhum dado de caso, nome de arquivo ou processo. O servidor NUNCA
persiste o token em claro: o objeto é identificado por `sha256(token)`
(hex, 64 caracteres), então quem lê o bucket, a listagem ou a telemetria
(`artefato_id` é esse hash) não consegue reconstruir o link. Sem banco
de dados, sem segredo de servidor: a busca é o próprio hash.

Sem assinatura: esta arquitetura não usa V4 signed URL, `signBlob`,
auto-impersonation nem `EDE_ARTEFATOS_SIGNER_SA` (variável ignorada se
ainda presente no ambiente — só existia para o mecanismo substituído).
A service account de runtime precisa apenas de permissão de objeto no
bucket de artefatos.

Arquitetura de dependência — mesma disciplina de
`scripts/legal_readiness.py` (Gate 6.4-B): NENHUM SDK de nuvem completo.
`google-auth` resolve a identidade de runtime; as chamadas REST (upload
multipart, leitura de metadado, leitura de conteúdo por geração,
exclusão, listagem) usam `httpx2` (já transitivo via `mcp`).

TTL é uma CONSTANTE do servidor (`TTL_DOWNLOAD_SEGUNDOS`), nunca
parâmetro de entrada pública.

Object key opaco por construção — nenhum dado de caso (nome de parte,
número de processo, CPF/CNPJ, conta/contrato) entra no nome do objeto
nem na URL: a função de entrega recebe só bytes já renderizados, um
SHA-256 já calculado e o nome de arquivo NEUTRO já definido por
`finalizar_peca.FILENAME_POR_CAPACIDADE` (gravado só no metadado do
objeto, para o `Content-Disposition` da entrega).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Protocol

ENV_ARTEFATOS_GCS_BUCKET = "EDE_ARTEFATOS_GCS_BUCKET"
ENV_ARTEFATOS_DOWNLOAD_BASE_URL = "EDE_ARTEFATOS_DOWNLOAD_BASE_URL"
"""Origem pública do EDE (`https://<host canônico>`) usada para compor
`https://<host>/download/<token>` — valor explícito de configuração,
nunca inferido do cabeçalho `Host` de uma requisição. `mcp_server/
server.py` recusa subir se o host desta variável divergir do host
canônico OAuth (`EDE_MCP_CANONICAL_HOST`)."""

CONTENT_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

PREFIXO_ROTA_DOWNLOAD = "/download/"
"""Única rota pública de download. Mantida aqui (Core) porque o Core
compõe a URL e o adapter HTTP serve a rota — os dois precisam do mesmo
valor, nunca duas cópias."""

TTL_DOWNLOAD_SEGUNDOS = 24 * 60 * 60
"""Contrato FIXO — janela de AUTORIZAÇÃO de download, nunca configurável
pelo cliente MCP nem por variável de ambiente (constante Python).
Revisado de 15 minutos para 24 horas no Gate 6.6-E (decisão explícita do
usuário; histórico no `CHANGELOG.md`). O token é uma CAPACIDADE
PORTADORA: quem o possuir dentro da janela baixa o artefato, sem segunda
verificação de identidade. Downloads múltiplos dentro da janela são
permitidos (decisão explícita: pré-visualizadores de link dos hosts
consumiriam um token de uso único antes do advogado)."""

_TOKEN_BYTES = 32
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
"""`token_urlsafe(32)` produz exatamente 43 caracteres base64url sem
padding. Qualquer outra forma é rejeitada ANTES de qualquer I/O."""

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.docx$")
"""Nome de arquivo aceitável no `Content-Disposition` — ASCII restrito,
sem aspas, barras, espaços ou `;`, portanto nunca injeta parâmetro no
cabeçalho. Metadado fora disso é tratado como metadado inválido."""

_FORMATO_DATA = "%Y-%m-%dT%H:%M:%SZ"

_GCS_ESCOPO = "https://www.googleapis.com/auth/devstorage.read_write"
_GCS_API_BASE = "https://storage.googleapis.com/storage/v1"
_GCS_UPLOAD_BASE = "https://storage.googleapis.com/upload/storage/v1"


class ErroConfiguracaoArtefato(Exception):
    """`EDE_ARTEFATOS_GCS_BUCKET`/`EDE_ARTEFATOS_DOWNLOAD_BASE_URL`
    ausentes ou malformadas — distinto de falha operacional: isto é o
    serviço não estar provisionado, mesma disciplina de
    `ModeloOficialIndisponivel` em `legal_readiness.py`."""


class ErroArmazenamentoArtefato(Exception):
    """Falha de I/O com o bucket efêmero — rede, autenticação ou status
    HTTP inesperado do GCS. `motivo` é um rótulo estrutural fechado,
    nunca a mensagem bruta da biblioteca (que pode incluir corpo de
    resposta). Upload multipart do GCS é atômico: uma falha de envio
    nunca deixa objeto parcial."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


@dataclass(frozen=True)
class ArtefatoEntregue:
    download_url: str = field(repr=False)
    """`https://<host>/download/<token>` — contém a capacidade portadora;
    `repr=False` para que nunca apareça num traceback/log por `repr()`.
    Nunca repassada à telemetria (`mcp_server/auth_logging.py`)."""
    expires_at: str
    """ISO-8601 UTC com sufixo 'Z' (ex.: '2026-09-22T21:15:00Z')."""
    artefato_id: str
    """`sha256(token)` em hex — identifica o objeto sem permitir
    reconstruir o link. Seguro para telemetria somente-metadado; nunca
    exposto na resposta MCP ao cliente."""


class TransporteArtefato(Protocol):
    """Interface mínima de armazenamento. Produção usa
    `TransporteGcsReal`; a suíte de unidade usa um fake em memória —
    nenhum teste de unidade toca rede."""

    def enviar(self, object_name: str, dados: bytes, content_type: str, metadata: dict) -> None: ...

    def obter_metadado(self, object_name: str) -> "tuple[dict, str, str] | None":
        """(metadado customizado, generation, content_type) do objeto, ou
        `None` se o objeto não existe. Falha operacional levanta
        `ErroArmazenamentoArtefato` — nunca confundida com inexistência."""
        ...

    def baixar(self, object_name: str, generation: str) -> "bytes | None":
        """Conteúdo DAQUELA geração, ou `None` se ela não existe mais
        (hard delete entre a leitura do metadado e a do conteúdo)."""
        ...

    def excluir(self, object_name: str) -> bool:
        """True se o objeto foi removido (ou já não existia —
        idempotente); False só numa falha real de exclusão."""
        ...

    def listar(self, prefixo: str, limite: int) -> list[tuple[str, dict]]:
        """Lista (nome do objeto, metadado) só sob `prefixo` — usado
        exclusivamente pela limpeza. Nunca lê conteúdo."""
        ...


LIMPEZA_ELEGIVEL_SEGUNDOS = TTL_DOWNLOAD_SEGUNDOS
"""EXATAMENTE `TTL_DOWNLOAD_SEGUNDOS` (24h), sem margem adicional
(decisão explícita do usuário: elegibilidade "imediatamente após a
janela de 24h expirar"). Documenta a relação usada para CALCULAR
`expires_at` no upload — a decisão de elegibilidade em
`limpar_artefatos_elegiveis` lê `expires_at` diretamente do metadado,
a MESMA fonte de verdade usada pela rota de download, então a limpeza
nunca fica à frente da autorização (e a rota nunca entrega depois
dela). Retenção normal total = este limiar + cadência da varredura
agendada (~24-25h), exclusão sempre real (hard delete)."""

LIMPEZA_MAX_OBJETOS_POR_VARREDURA = 20
"""Teto de objetos processados por chamada — cada finalização bem-
sucedida pode disparar, no máximo, esta quantidade de exclusões."""


# ------------------------------------------------------------- token/objeto

def _novo_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def token_bem_formado(token: str) -> bool:
    return isinstance(token, str) and _TOKEN_RE.fullmatch(token) is not None


def id_artefato_do_token(token: str) -> str:
    """`sha256(token)` em hex. Único vínculo entre a URL e o objeto; o
    token em si nunca é gravado em lugar nenhum."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _nome_objeto(artefato_id: str) -> str:
    """`artifacts/<sha256(token)>.docx` — opaco por construção: deriva só
    do token aleatório, nunca de dado de entrada, nem do SHA-256 do
    documento (dois documentos idênticos recebem objetos e links
    diferentes)."""
    return f"artifacts/{artefato_id}.docx"


def validar_base_url_download(valor: str | None) -> str:
    """Normaliza `EDE_ARTEFATOS_DOWNLOAD_BASE_URL` para `https://<host>`.
    Aceita só origem HTTPS pura: sem caminho, query, fragmento, usuário
    ou porta. Qualquer outra forma é erro de configuração (fail-closed),
    nunca "corrigida"."""
    bruto = (valor or "").strip()
    if not bruto:
        raise ErroConfiguracaoArtefato(f"{ENV_ARTEFATOS_DOWNLOAD_BASE_URL} é obrigatória.")
    partes = urllib.parse.urlsplit(bruto)
    if (
        partes.scheme != "https"
        or not partes.hostname
        or partes.path not in ("", "/")
        or partes.query
        or partes.fragment
        or partes.username is not None
        or partes.password is not None
        or partes.port is not None
        or partes.netloc.lower() != partes.hostname
    ):
        raise ErroConfiguracaoArtefato(
            f"{ENV_ARTEFATOS_DOWNLOAD_BASE_URL} deve ser uma origem HTTPS pura (https://<host>)."
        )
    return f"https://{partes.hostname}"


def obter_base_url_download_do_ambiente(env: dict) -> str:
    return validar_base_url_download(env.get(ENV_ARTEFATOS_DOWNLOAD_BASE_URL))


# ---------------------------------------------------------- adaptador httpx2/google-auth
# Mesmo padrão de `legal_readiness._RespostaHttpx`/`_RequisicaoHttpx`
# (Gate 6.4-B) — reimplementado aqui, não importado de lá: os dois
# módulos são liberados independentemente na allowlist do Dockerfile.

class _RespostaHttpx:
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
    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        import httpx2

        resposta = httpx2.request(method, url, content=body, headers=headers, timeout=timeout)
        return _RespostaHttpx(resposta)


def _credenciais_e_token():
    """`google.auth.default()` com escopo de leitura/escrita no GCS, já
    atualizado. Import lazy — os testes com fake nunca pagam o custo."""
    import google.auth

    try:
        credenciais, _ = google.auth.default(scopes=[_GCS_ESCOPO])
        credenciais.refresh(_RequisicaoHttpx())
    except Exception as e:
        raise ErroArmazenamentoArtefato("autenticacao_falhou") from e
    return credenciais


def _quote(s: str, safe: str = "") -> str:
    return urllib.parse.quote(s, safe=safe)


class TransporteGcsReal:
    """Implementação de produção de `TransporteArtefato` — GCS JSON API
    via `httpx2`, sem SDK de nuvem completo e sem arquivo de chave."""

    def __init__(self, bucket: str):
        if not bucket:
            raise ErroConfiguracaoArtefato(f"{ENV_ARTEFATOS_GCS_BUCKET} é obrigatória.")
        self._bucket = bucket

    def _url_objeto(self, object_name: str) -> str:
        return f"{_GCS_API_BASE}/b/{self._bucket}/o/{_quote(object_name)}"

    def enviar(self, object_name: str, dados: bytes, content_type: str, metadata: dict) -> None:
        import httpx2

        credenciais = _credenciais_e_token()
        boundary = f"ede-artifact-{uuid.uuid4().hex}"
        metadado_json = json.dumps({
            "name": object_name,
            "contentType": content_type,
            "metadata": metadata,
        })
        corpo = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadado_json}\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + dados + f"\r\n--{boundary}--\r\n".encode("utf-8")

        # `ifGenerationMatch=0`: o upload só cria, nunca sobrescreve um
        # objeto existente — colisão de sha256(token) é impossível na
        # prática, e se ocorresse falharia fechado em vez de trocar o
        # conteúdo de um link já emitido.
        url = f"{_GCS_UPLOAD_BASE}/b/{self._bucket}/o?uploadType=multipart&ifGenerationMatch=0"
        cabecalhos = {
            "Authorization": f"Bearer {credenciais.token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        }
        try:
            resposta = httpx2.post(url, content=corpo, headers=cabecalhos, timeout=60.0)
        except httpx2.HTTPError as e:
            raise ErroArmazenamentoArtefato("rede_falhou") from e
        if resposta.status_code not in (200, 201):
            raise ErroArmazenamentoArtefato("gcs_status_inesperado")

    def obter_metadado(self, object_name: str) -> "tuple[dict, str, str] | None":
        import httpx2

        credenciais = _credenciais_e_token()
        cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}
        try:
            resposta = httpx2.get(self._url_objeto(object_name), headers=cabecalhos, timeout=30.0)
        except httpx2.HTTPError as e:
            raise ErroArmazenamentoArtefato("rede_falhou") from e
        if resposta.status_code == 404:
            return None
        if resposta.status_code != 200:
            raise ErroArmazenamentoArtefato("gcs_status_inesperado")
        try:
            dados = resposta.json()
            return (dados.get("metadata") or {}, str(dados["generation"]), str(dados.get("contentType") or ""))
        except (ValueError, KeyError, TypeError) as e:
            raise ErroArmazenamentoArtefato("gcs_resposta_malformada") from e

    def baixar(self, object_name: str, generation: str) -> "bytes | None":
        import httpx2

        credenciais = _credenciais_e_token()
        cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}
        url = f"{self._url_objeto(object_name)}?alt=media&generation={_quote(generation)}"
        try:
            resposta = httpx2.get(url, headers=cabecalhos, timeout=60.0)
        except httpx2.HTTPError as e:
            raise ErroArmazenamentoArtefato("rede_falhou") from e
        if resposta.status_code == 404:
            return None
        if resposta.status_code != 200:
            raise ErroArmazenamentoArtefato("gcs_status_inesperado")
        return resposta.content

    def excluir(self, object_name: str) -> bool:
        import httpx2

        try:
            credenciais = _credenciais_e_token()
        except ErroArmazenamentoArtefato:
            return False
        cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}
        try:
            resposta = httpx2.delete(self._url_objeto(object_name), headers=cabecalhos, timeout=30.0)
        except httpx2.HTTPError:
            return False
        return resposta.status_code in (200, 204, 404)

    def listar(self, prefixo: str, limite: int) -> list[tuple[str, dict]]:
        import httpx2

        try:
            credenciais = _credenciais_e_token()
        except ErroArmazenamentoArtefato:
            return []
        url = (
            f"{_GCS_API_BASE}/b/{self._bucket}/o"
            f"?prefix={_quote(prefixo, safe='/')}&maxResults={int(limite)}"
        )
        cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}
        try:
            resposta = httpx2.get(url, headers=cabecalhos, timeout=30.0)
        except httpx2.HTTPError:
            return []
        if resposta.status_code != 200:
            return []
        dados = resposta.json()
        return [(item["name"], item.get("metadata") or {}) for item in dados.get("items", [])]


def obter_transporte_do_ambiente(env: dict) -> TransporteGcsReal:
    return TransporteGcsReal((env.get(ENV_ARTEFATOS_GCS_BUCKET) or "").strip())


# ------------------------------------------------------------------ entrega

def entregar_artefato_efemero(document_bytes: bytes, sha256_hex: str, filename_cliente: str,
                               transporte: TransporteArtefato, base_url: str) -> ArtefatoEntregue:
    """Grava o artefato e devolve a URL opaca. Nunca reabre/reconstrói
    `document_bytes` — envia exatamente os bytes que o chamador já
    validou (Template Lock, fidelidade independente, round-trip) e cujo
    SHA-256 já foi calculado sobre eles.

    Configuração é validada ANTES do upload (base URL e nome de arquivo)
    — nenhum objeto é criado para um link que não poderia funcionar.
    Falha de upload propaga `ErroArmazenamentoArtefato` (sem objeto
    parcial). Não há etapa posterior ao upload que possa falhar: sem
    assinatura, não existe mais objeto órfão por falha de entrega."""
    origem = validar_base_url_download(base_url)
    if not _FILENAME_RE.fullmatch(filename_cliente or ""):
        raise ErroConfiguracaoArtefato("nome de arquivo institucional fora do formato seguro.")

    token = _novo_token()
    artefato_id = id_artefato_do_token(token)
    agora = _dt.datetime.now(_dt.timezone.utc)
    expira_em = agora + _dt.timedelta(seconds=TTL_DOWNLOAD_SEGUNDOS)

    metadata_objeto = {
        "artifact_id": artefato_id,
        "created_at": agora.strftime(_FORMATO_DATA),
        "expires_at": expira_em.strftime(_FORMATO_DATA),
        "sha256": sha256_hex,
        "filename": filename_cliente,
    }
    transporte.enviar(_nome_objeto(artefato_id), document_bytes, CONTENT_TYPE_DOCX, metadata_objeto)

    return ArtefatoEntregue(
        download_url=f"{origem}{PREFIXO_ROTA_DOWNLOAD}{token}",
        expires_at=metadata_objeto["expires_at"],
        artefato_id=artefato_id,
    )


# ------------------------------------------------------------------ download

DOWNLOAD_ENTREGUE = "entregue"
DOWNLOAD_NAO_ENCONTRADO = "nao_encontrado"
DOWNLOAD_INTEGRIDADE_DIVERGENTE = "integridade_divergente"
DOWNLOAD_INDISPONIVEL = "indisponivel"

MOTIVO_TOKEN_MALFORMADO = "token_malformado"
MOTIVO_OBJETO_INEXISTENTE = "objeto_inexistente"
MOTIVO_METADADO_INVALIDO = "metadado_invalido"
MOTIVO_EXPIRADO = "expirado"


@dataclass(frozen=True)
class ResultadoDownload:
    """Resultado da resolução de um token. `status`/`motivo` são rótulos
    fechados (seguros para telemetria); o adapter HTTP decide o código de
    resposta e NUNCA expõe `motivo` ao cliente — todo `nao_encontrado` é
    o mesmo 404 uniforme."""

    status: str
    motivo: str | None = None
    artefato_id: str | None = None
    dados: bytes | None = field(default=None, repr=False)
    filename: str | None = None
    sha256: str | None = None


def _ler_data(valor) -> "_dt.datetime | None":
    if not isinstance(valor, str):
        return None
    try:
        return _dt.datetime.strptime(valor, _FORMATO_DATA).replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def resolver_download(token: str, transporte: TransporteArtefato,
                      agora: "_dt.datetime | None" = None) -> ResultadoDownload:
    """Resolve `/download/<token>` em bytes entregáveis — ou em recusa.
    Ordem fixa, e nenhum byte do documento sai daqui sem TODAS as
    etapas terem passado:

    1. formato do token (antes de qualquer I/O);
    2. objeto localizado por `sha256(token)`;
    3. metadado íntegro (id, datas, SHA, nome de arquivo, content type);
    4. `expires_at` ainda no futuro (mesma fonte de verdade da limpeza);
    5. conteúdo lido DA GERAÇÃO observada no passo 2;
    6. SHA-256 do conteúdo calculado;
    7. SHA-256 comparado ao registrado no metadado.

    Token inválido/inexistente, metadado ausente/malformado, expirado ou
    objeto já excluído -> `nao_encontrado` (404 uniforme no adapter).
    SHA divergente -> `integridade_divergente` (5xx, nenhum byte).
    Falha operacional do armazenamento -> `indisponivel` (5xx)."""
    if not token_bem_formado(token):
        return ResultadoDownload(DOWNLOAD_NAO_ENCONTRADO, MOTIVO_TOKEN_MALFORMADO)

    artefato_id = id_artefato_do_token(token)
    nome = _nome_objeto(artefato_id)
    if agora is None:
        agora = _dt.datetime.now(_dt.timezone.utc)

    try:
        observado = transporte.obter_metadado(nome)
    except ErroArmazenamentoArtefato:
        return ResultadoDownload(DOWNLOAD_INDISPONIVEL, artefato_id=artefato_id)
    if observado is None:
        return ResultadoDownload(DOWNLOAD_NAO_ENCONTRADO, MOTIVO_OBJETO_INEXISTENTE, artefato_id)
    metadata, generation, content_type = observado
    metadata = metadata or {}

    criado_em = _ler_data(metadata.get("created_at"))
    expira_em = _ler_data(metadata.get("expires_at"))
    sha_registrado = metadata.get("sha256")
    filename = metadata.get("filename")
    if (
        metadata.get("artifact_id") != artefato_id
        or criado_em is None
        or expira_em is None
        or expira_em <= criado_em
        # janela nunca maior que o contrato — metadado adulterado ou
        # corrompido não alonga a autorização
        or (expira_em - criado_em).total_seconds() > TTL_DOWNLOAD_SEGUNDOS
        or not isinstance(sha_registrado, str) or not _SHA256_RE.fullmatch(sha_registrado)
        or not isinstance(filename, str) or not _FILENAME_RE.fullmatch(filename)
        or content_type != CONTENT_TYPE_DOCX
        or not generation
    ):
        return ResultadoDownload(DOWNLOAD_NAO_ENCONTRADO, MOTIVO_METADADO_INVALIDO, artefato_id)

    if agora >= expira_em:
        return ResultadoDownload(DOWNLOAD_NAO_ENCONTRADO, MOTIVO_EXPIRADO, artefato_id)

    try:
        dados = transporte.baixar(nome, generation)
    except ErroArmazenamentoArtefato:
        return ResultadoDownload(DOWNLOAD_INDISPONIVEL, artefato_id=artefato_id)
    if dados is None:
        return ResultadoDownload(DOWNLOAD_NAO_ENCONTRADO, MOTIVO_OBJETO_INEXISTENTE, artefato_id)

    if not secrets.compare_digest(hashlib.sha256(dados).hexdigest(), sha_registrado):
        return ResultadoDownload(DOWNLOAD_INTEGRIDADE_DIVERGENTE, artefato_id=artefato_id)

    return ResultadoDownload(
        DOWNLOAD_ENTREGUE, artefato_id=artefato_id, dados=dados, filename=filename, sha256=sha_registrado,
    )


# ------------------------------------------------------------------ limpeza

def limpar_artefatos_elegiveis(transporte: TransporteArtefato,
                                agora: _dt.datetime | None = None) -> dict:
    """Núcleo da exclusão NORMAL do artefato — sempre um DELETE real de
    objeto (este bucket tem soft-delete desligado, sem versionamento, sem
    retention policy/hold — verificado ao vivo no Gate 6.6-E), distinta
    do backstop de lifecycle (`age: 2`, assíncrono, sem prazo garantido).

    Duas formas de chamada, mesma função: (1) oportunista, disparada por
    `finalizar_peca.py` depois de cada sucesso; (2) `scripts/limpar_
    artefatos_agendado.py`, invocado por Cloud Scheduler -> Cloud Run Job
    com cadência horária (provado em homologação, ADR-0019) — é o que
    garante retenção normal ~24-25h mesmo sem tráfego. Varre SÓ o
    prefixo `artifacts/`, lê SÓ o metadado — nunca conteúdo. Processa no
    máximo `LIMPEZA_MAX_OBJETOS_POR_VARREDURA` por chamada.

    **Elegibilidade é decidida por `expires_at`**, nunca recalculada a
    partir de `created_at` (hardening pós-fechamento do Gate 6.6-E): é o
    MESMO campo que a rota de download usa para recusar, então um objeto
    nunca é excluído enquanto seu link ainda autoriza download.
    **Metadado ausente ou malformado é fail-safe**: o objeto é ignorado,
    nunca excluído por incerteza — o backstop de lifecycle cobre esse
    caso (e a rota de download já o recusa com 404).

    Best-effort: exceções de rede/autenticação propagam para o chamador,
    que decide (a finalização sempre engole; o script agendado sai com
    código de erro). Devolve só contadores agregados."""
    resultado = {"inspecionados": 0, "excluidos": 0, "falhas": 0}
    if agora is None:
        agora = _dt.datetime.now(_dt.timezone.utc)

    objetos = transporte.listar("artifacts/", LIMPEZA_MAX_OBJETOS_POR_VARREDURA)
    for nome_objeto, metadata in objetos:
        resultado["inspecionados"] += 1
        expira_em = _ler_data((metadata or {}).get("expires_at"))
        if expira_em is None:
            continue  # metadado ausente/malformado -- fail-safe
        if agora < expira_em:
            continue  # autorização de download ainda não expirou
        if transporte.excluir(nome_objeto):
            resultado["excluidos"] += 1
        else:
            resultado["falhas"] += 1
    return resultado
