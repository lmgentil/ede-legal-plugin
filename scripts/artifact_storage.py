#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
artifact_storage.py — armazenamento efêmero e entrega assinada do DOCX
finalizado (Gate 6.6-E, ADR-0019).

Contexto (não repetido em cada função): o Gate 6.6-D provou, com Claude
e ChatGPT reais, que o `EmbeddedResource`/`BlobResourceContents` inline
(Decisão 5 v1 da ADR-0018) não é usável nativamente por nenhum dos dois
hosts MCP do produto — servidor, validação produção-final e determinismo
do documento estavam corretos; só o TRANSPORTE do artefato falhava. Este
módulo é o mecanismo v2: renderiza (inalterado), envia os bytes exatos
que já passaram por Template Lock/fidelidade/round-trip a um objeto GCS
privado e efêmero, e devolve uma URL HTTPS assinada (V4) de curta
duração — HTTPS comum, consumível por qualquer cliente, sem base64 na
resposta MCP.

Arquitetura de dependência — mesma disciplina de
`scripts/legal_readiness.py` (Gate 6.4-B) e `mcp_server/requirements.txt`:
NENHUM SDK de nuvem completo (`google-cloud-storage` puxaria
google-api-core/google-cloud-core/google-resumable-media). `google-auth`
resolve a identidade da service account de runtime (`google.auth.
default()`, já dependência do projeto); as chamadas REST em si (upload
multipart no GCS JSON API, `signBlob` na API IAM Credentials, exclusão)
usam `httpx2` (já transitivo via `mcp`). A assinatura V4 é construída à
mão, seguindo o algoritmo publicado pelo Google
(`docs.cloud.google.com/storage/docs/access-control/signing-urls-manually`),
NUNCA por biblioteca terceira nova — mesmo princípio de "não adicionar
uma segunda pilha" já aplicado à leitura do Modelo Oficial.

Assinatura SEM ARQUIVO DE CHAVE (Gate 6.6-E §17): a service account de
runtime nunca tem uma chave privada baixada. A assinatura V4 é keyless —
feita via IAM Credentials `signBlob`, que exige que a identidade
chamadora (a própria service account de runtime, em produção) tenha
`roles/iam.serviceAccountTokenCreator` NELA MESMA (auto-impersonation) —
nenhuma chave, nenhum segredo novo, só uma permissão IAM adicional.

Identidade de assinatura EXPLÍCITA, não auto-detectada: `EDE_ARTEFATOS_
SIGNER_SA` nomeia a service account a impersonar para `signBlob`. Em
produção normal, é o mesmo e-mail da própria service account de runtime
(auto-impersonation) — mas como valor de configuração explícito, não
inferido de atributo de credencial (`google.auth.compute_engine.
Credentials.service_account_email` tem comportamento não totalmente
verificado neste ambiente de desenvolvimento — ver ADR-0019/relatório do
Gate 6.6-E, item de risco residual), mesma disciplina de
`EDE_MODELO_OFICIAL_GCS_BUCKET`/`_OBJECT`/`_GENERATION` (Gate 6.4-B):
tudo explícito, nada adivinhado do ambiente.

TTL do link de download é uma CONSTANTE do servidor
(`TTL_DOWNLOAD_SEGUNDOS`), nunca um parâmetro de entrada pública — quem
precisa de TTL diferente para teste chama `TransporteArtefato.
assinar_url()`/`_construir_url_assinada_v4()` diretamente (caminho
interno, nunca alcançável pelo schema Pydantic de
`mcp_server/server.py`).

Object key é sempre opaco (`artifacts/<uuid4 hex>.docx`) — nenhum dado
de caso (nome de parte, número de processo, CPF/CNPJ, conta/contrato)
entra na composição do nome do objeto ou é lido daqui: a função de
entrega recebe só bytes já renderizados, um SHA-256 já calculado pelo
chamador e o nome de arquivo NEUTRO já definido por
`finalizar_peca.FILENAME_POR_CAPACIDADE` — nunca placeholders, nunca
`estado_processual`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Protocol

ENV_ARTEFATOS_GCS_BUCKET = "EDE_ARTEFATOS_GCS_BUCKET"
ENV_ARTEFATOS_SIGNER_SA = "EDE_ARTEFATOS_SIGNER_SA"

CONTENT_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

TTL_DOWNLOAD_SEGUNDOS = 24 * 60 * 60
"""Contrato FIXO de produção — janela de AUTORIZAÇÃO de download, nunca
configurável pelo cliente MCP nem por variável de ambiente: é uma
constante Python, não lida de `os.environ`, para que nenhuma
configuração de implantação possa alongá-la silenciosamente.

Revisado de 15 minutos para 24 horas (decisão explícita do usuário, Gate
6.6-E continuação — "USER DECISION — SIGNED URL LIFETIME CHANGE"). O
valor original de 15 minutos foi a primeira implementação deste gate
(ver `CHANGELOG.md`, entrada original do Gate 6.6-E) — registro
histórico preservado ali, não reescrito; esta é a decisão vigente. A
natureza do mecanismo não muda com o valor: a URL assinada continua
sendo uma CAPACIDADE PORTADORA — quem quer que a possua dentro da
janela de validade pode baixar o artefato, sem segunda verificação de
identidade — nunca "acesso vinculado à identidade"."""

_GCS_ESCOPO_ESCRITA = "https://www.googleapis.com/auth/devstorage.read_write"
_IAM_ESCOPO_ASSINATURA = "https://www.googleapis.com/auth/iam"
_GCS_API_BASE = "https://storage.googleapis.com/storage/v1"
_GCS_UPLOAD_BASE = "https://storage.googleapis.com/upload/storage/v1"
_IAM_CREDENTIALS_BASE = "https://iamcredentials.googleapis.com/v1"


class ErroConfiguracaoArtefato(Exception):
    """`EDE_ARTEFATOS_GCS_BUCKET`/`EDE_ARTEFATOS_SIGNER_SA` ausentes —
    distinto de falha operacional (upload/assinatura): isto é o serviço
    não estar provisionado, mesma disciplina de `ModeloOficialIndisponivel`
    em `legal_readiness.py`."""


class ErroArmazenamentoArtefato(Exception):
    """Falha ao enviar os bytes ao bucket efêmero — rede, autenticação ou
    status HTTP inesperado do GCS. `motivo` é um rótulo estrutural
    fechado, nunca a mensagem bruta da biblioteca (que pode incluir corpo
    de resposta). Upload multipart do GCS é atômico: uma falha aqui nunca
    deixa um objeto parcial — nenhuma limpeza é necessária neste caso."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


class ErroAssinaturaArtefato(Exception):
    """Upload teve sucesso, mas a assinatura V4 (IAM Credentials
    `signBlob`) falhou. Carrega `artefato_id` e `limpeza_ok` para que o
    chamador registre telemetria somente-metadado precisa (Gate 6.6-E
    §22) sem nunca expor o nome do objeto/URL."""

    def __init__(self, motivo: str, artefato_id: str, limpeza_ok: bool | None):
        self.motivo = motivo
        self.artefato_id = artefato_id
        self.limpeza_ok = limpeza_ok
        super().__init__(motivo)


@dataclass(frozen=True)
class ArtefatoEntregue:
    download_url: str
    expires_at: str
    """ISO-8601 UTC com sufixo 'Z' (ex.: '2026-09-22T21:15:00Z') — formato
    inequívoco (Gate 6.6-E §8), nunca époch numérico."""
    artefato_id: str
    """Identificador opaco (uuid4 hex) — nunca exposto na resposta MCP ao
    cliente (`EdeFinalizarPecaResposta` não tem este campo); existe só
    para telemetria somente-metadado e para os testes deste módulo."""


class TransporteArtefato(Protocol):
    """Interface mínima que `entregar_artefato_efemero` precisa. Produção
    usa `TransporteGcsReal`; a suíte de unidade usa um fake em memória —
    nenhum teste de unidade toca rede (Gate 6.6-E §43)."""

    def enviar(self, object_name: str, dados: bytes, content_type: str, metadata: dict) -> None: ...

    def assinar_url(self, object_name: str, ttl_segundos: int, content_disposition: str,
                     momento: "_dt.datetime | None" = None) -> str: ...

    def excluir(self, object_name: str) -> bool:
        """Retorna True se o objeto foi removido (ou já não existia —
        idempotente); False só numa falha real de exclusão."""
        ...

    def listar(self, prefixo: str, limite: int) -> list[tuple[str, dict]]:
        """Lista (nome do objeto, metadado) só sob `prefixo` — usado
        exclusivamente pela limpeza oportunista (Gate 6.6-E, continuação
        §8). Nunca lê conteúdo, nunca lista fora do prefixo de
        artefatos."""
        ...


LIMPEZA_ELEGIVEL_SEGUNDOS = TTL_DOWNLOAD_SEGUNDOS
"""EXATAMENTE `TTL_DOWNLOAD_SEGUNDOS` (24h), sem margem adicional
(decisão explícita do usuário: elegibilidade "imediatamente após a
janela de 24h expirar"). Documenta a relação usada para CALCULAR
`expires_at` no momento do upload (`entregar_artefato_efemero`) — a
DECISÃO de elegibilidade em `limpar_artefatos_elegiveis` não recalcula
isto a partir de `created_at`; ela lê `expires_at` diretamente do
metadado (hardening pós-fechamento do Gate 6.6-E — ver docstring de
`limpar_artefatos_elegiveis` para o motivo: uma comparação baseada só
em `created_at` reabriria a corrida entre a expiração real da URL
assinada e a elegibilidade de limpeza que este valor pretende
fechar).

A retenção NORMAL total (criação -> exclusão de fato) não é este
número sozinho — é este limiar SOMADO à cadência do mecanismo que
executa a varredura (ver `limpar_artefatos_elegiveis`): com cadência de
1h, o alvo de retenção normal é ~24-25h, nunca prometido como exato
(exclusão é sempre um DELETE real de objeto, nunca soft-delete
recuperável — `soft_delete_policy.retentionDurationSeconds: 0` neste
bucket, verificado ao vivo). Este valor substitui dois valores
anteriores deste mesmo gate (15 min de TTL / 30 min de limpeza na
primeira implementação; 24h de TTL / 26h de limpeza numa revisão
intermediária) — histórico preservado no `CHANGELOG.md`, não
reescrito; este é o valor vigente."""

LIMPEZA_MAX_OBJETOS_POR_VARREDURA = 20
"""Teto de objetos processados por chamada — cada finalização bem-
sucedida pode disparar, no máximo, esta quantidade de exclusões, para
que a limpeza nunca infle a latência de uma finalização de forma
descontrolada (Gate 6.6-E, continuação §8). Sobra de objetos elegíveis
além deste teto é varrida na próxima finalização, ou, na ausência de
tráfego, pelo backstop de lifecycle (~1 dia)."""


def _novo_id_artefato() -> str:
    return uuid.uuid4().hex


def _nome_objeto(artefato_id: str) -> str:
    """`artifacts/<uuid4 hex>.docx` — opaco por construção: `artefato_id`
    nunca deriva de nenhum dado de entrada (Gate 6.6-E §11/§26), nem
    mesmo do SHA-256 do documento (dois documentos idênticos, gerados em
    chamadas diferentes, recebem objetos diferentes — identidade do
    documento e identidade de entrega do artefato são conceitos
    deliberadamente separados)."""
    return f"artifacts/{artefato_id}.docx"


# ---------------------------------------------------------- adaptador httpx2/google-auth
# Mesmo padrão de `legal_readiness._RespostaHttpx`/`_RequisicaoHttpx`
# (Gate 6.4-B) — reimplementado aqui, não importado de lá: os dois
# módulos são liberados independentemente na allowlist do Dockerfile
# (Gate 6.6-C), e uma dependência cruzada entre eles exigiria reabrir
# aquela allowlist sem necessidade real.

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
    """`google.auth.default()` com os dois escopos necessários (escrita
    no GCS + IAM para `signBlob`), já atualizado (`.token` pronto para
    uso). Import lazy — nenhum outro caminho deste módulo (testes com
    fake) paga o custo de importar a pilha de credenciais."""
    import google.auth

    try:
        credenciais, _ = google.auth.default(scopes=[_GCS_ESCOPO_ESCRITA, _IAM_ESCOPO_ASSINATURA])
        credenciais.refresh(_RequisicaoHttpx())
    except Exception as e:
        raise ErroArmazenamentoArtefato("autenticacao_falhou") from e
    return credenciais


def _quote(s: str, safe: str = "~") -> str:
    """`urllib.parse.quote` nunca escapa `_.-~` independentemente de
    `safe` (conjunto "sempre seguro" da própria stdlib) — `safe="~"`
    aqui é por clareza de leitura, equivalente a `safe=""` do algoritmo
    publicado pelo Google para chave/valor da query string V4."""
    return urllib.parse.quote(s, safe=safe)


def _construir_url_assinada_v4(bucket: str, object_name: str, signer_sa: str,
                                ttl_segundos: int, content_disposition: str | None,
                                assinar_bytes, momento: "_dt.datetime | None" = None) -> str:
    """Constrói uma URL V4 assinada manualmente, seguindo exatamente o
    algoritmo publicado em
    docs.cloud.google.com/storage/docs/access-control/signing-urls-manually
    (mesma família de `docs.cloud.google.com/storage/docs/authentication/
    signatures` para o formato do string-to-sign) — verificado ponto a
    ponto contra a documentação oficial nesta rodada (Gate 6.6-E),
    incluindo: escapamento de `canonical_uri` com `safe="/~"` (preserva
    barras internas do nome do objeto), escapamento de chave/valor da
    query string com `safe=""` (barras do `X-Goog-Credential`, que
    contém `/`, são percent-encoded), `credential_scope` com o token
    literal `"auto"` (não a região real do bucket — exigência
    documentada, não uma simplificação nossa), linha em branco entre o
    bloco de cabeçalhos canônicos e `signed_headers` (decorrente de
    `canonical_headers` já terminar em `\\n` antes do `\\n` de junção).

    `assinar_bytes` é injetável (produção: `signBlob` real; testes: uma
    assinatura RSA determinística local ou uma função fake) — a
    corretude do ALGORITMO (bytes exatos do `string_to_sign`) já foi
    verificada ao vivo contra o GCS real (Gate 6.6-E, continuação).

    `momento` (Gate 6.6-E, hardening pós-fechamento — corrige uma
    condição de corrida real: sem isto, `X-Goog-Date` usava um
    `datetime.now()` capturado DEPOIS do upload, então a expiração
    criptográfica real da URL (`X-Goog-Date + X-Goog-Expires`) ficava
    sempre um pouco DEPOIS do `expires_at` gravado no metadado do
    objeto — o atraso de rede do próprio upload. Uma varredura de
    limpeza rodando exatamente nessa janela poderia excluir o objeto
    enquanto a URL emitida para ele ainda era, tecnicamente,
    criptograficamente válida). Quando o chamador passa `momento`
    explícito (`entregar_artefato_efemero` sempre passa — o MESMO
    instante já usado para `created_at`/`expires_at`), `X-Goog-Date`
    passa a ser EXATAMENTE esse instante, então a expiração real da URL
    e o `expires_at` do metadado tornam-se o MESMO valor, não uma
    aproximação — a limpeza nunca pode ficar à frente da autorização
    real, por construção, não por margem. `None` (default) preserva o
    comportamento anterior para quem assina sem vínculo com metadado
    (ex.: os testes de expiração deste módulo, que usam TTL curto e não
    gravam objeto algum)."""
    host = "storage.googleapis.com"
    agora = momento if momento is not None else _dt.datetime.now(_dt.timezone.utc)
    datestamp = agora.strftime("%Y%m%d")
    timestamp = agora.strftime("%Y%m%dT%H%M%SZ")
    credential_scope = f"{datestamp}/auto/storage/goog4_request"
    credential = f"{signer_sa}/{credential_scope}"
    canonical_uri = f"/{bucket}/{_quote(object_name, safe='/~')}"

    query_params = {
        "X-Goog-Algorithm": "GOOG4-RSA-SHA256",
        "X-Goog-Credential": credential,
        "X-Goog-Date": timestamp,
        "X-Goog-Expires": str(ttl_segundos),
        "X-Goog-SignedHeaders": "host",
    }
    if content_disposition:
        query_params["response-content-disposition"] = content_disposition

    canonical_query_string = "&".join(
        f"{_quote(k)}={_quote(v)}" for k, v in sorted(query_params.items())
    )
    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    canonical_request = (
        f"GET\n{canonical_uri}\n{canonical_query_string}\n{canonical_headers}\n"
        f"{signed_headers}\nUNSIGNED-PAYLOAD"
    )
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = (
        f"GOOG4-RSA-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"
    ).encode("utf-8")

    assinatura = assinar_bytes(string_to_sign)
    return f"https://{host}{canonical_uri}?{canonical_query_string}&X-Goog-Signature={assinatura.hex()}"


class TransporteGcsReal:
    """Implementação de produção de `TransporteArtefato` — GCS JSON API +
    IAM Credentials `signBlob`, via `httpx2`, sem SDK de nuvem completo
    e sem arquivo de chave de service account (ver docstring do módulo).
    """

    def __init__(self, bucket: str, signer_sa: str):
        if not bucket or not signer_sa:
            raise ErroConfiguracaoArtefato(
                f"{ENV_ARTEFATOS_GCS_BUCKET} e {ENV_ARTEFATOS_SIGNER_SA} são obrigatórios."
            )
        self._bucket = bucket
        self._signer_sa = signer_sa

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

        url = f"{_GCS_UPLOAD_BASE}/b/{self._bucket}/o?uploadType=multipart"
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

    def assinar_url(self, object_name: str, ttl_segundos: int, content_disposition: str,
                     momento: "_dt.datetime | None" = None) -> str:
        import httpx2

        credenciais = _credenciais_e_token()

        def _sign_blob(string_to_sign: bytes) -> bytes:
            import base64

            url = (
                f"{_IAM_CREDENTIALS_BASE}/projects/-/serviceAccounts/"
                f"{self._signer_sa}:signBlob"
            )
            corpo = json.dumps({
                "payload": base64.b64encode(string_to_sign).decode("ascii"),
            }).encode("utf-8")
            cabecalhos = {
                "Authorization": f"Bearer {credenciais.token}",
                "Content-Type": "application/json",
            }
            try:
                resposta = httpx2.post(url, content=corpo, headers=cabecalhos, timeout=30.0)
            except httpx2.HTTPError as e:
                raise ErroAssinaturaArtefato("rede_falhou", artefato_id="", limpeza_ok=None) from e
            if resposta.status_code != 200:
                raise ErroAssinaturaArtefato("iam_signblob_status_inesperado", artefato_id="", limpeza_ok=None)
            return base64.b64decode(resposta.json()["signedBlob"])

        return _construir_url_assinada_v4(
            self._bucket, object_name, self._signer_sa, ttl_segundos, content_disposition, _sign_blob,
            momento=momento,
        )

    def excluir(self, object_name: str) -> bool:
        import httpx2

        try:
            credenciais = _credenciais_e_token()
        except ErroArmazenamentoArtefato:
            return False
        url = f"{_GCS_API_BASE}/b/{self._bucket}/o/{_quote(object_name, safe='')}"
        cabecalhos = {"Authorization": f"Bearer {credenciais.token}"}
        try:
            resposta = httpx2.delete(url, headers=cabecalhos, timeout=30.0)
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
    bucket = (env.get(ENV_ARTEFATOS_GCS_BUCKET) or "").strip()
    signer_sa = (env.get(ENV_ARTEFATOS_SIGNER_SA) or "").strip()
    return TransporteGcsReal(bucket, signer_sa)


def entregar_artefato_efemero(document_bytes: bytes, sha256_hex: str, filename_cliente: str,
                               transporte: TransporteArtefato) -> ArtefatoEntregue:
    """Orquestra upload + assinatura. Nunca reabre/reconstrói
    `document_bytes` (Gate 6.6-E §14) — envia exatamente os bytes que o
    chamador já validou (Template Lock, fidelidade independente,
    round-trip) e cujo SHA-256 já foi calculado sobre eles.

    Falha de upload: nenhuma limpeza necessária (upload multipart do GCS
    é atômico — sem objeto parcial) — propaga `ErroArmazenamentoArtefato`
    tal como veio do transporte.

    Falha de assinatura APÓS upload bem-sucedido: tenta excluir o objeto
    órfão; o resultado da limpeza (`True`/`False`) vai no
    `ErroAssinaturaArtefato.limpeza_ok` para o chamador decidir telemetria
    — a resposta ao cliente MCP é `REFUSED` de qualquer forma (Gate
    6.6-E §22/§24), nunca uma URL inutilizável."""
    artefato_id = _novo_id_artefato()
    object_name = _nome_objeto(artefato_id)
    agora = _dt.datetime.now(_dt.timezone.utc)
    expira_em = agora + _dt.timedelta(seconds=TTL_DOWNLOAD_SEGUNDOS)

    metadata_objeto = {
        "artifact_id": artefato_id,
        "created_at": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expira_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_hex,
    }

    transporte.enviar(object_name, document_bytes, CONTENT_TYPE_DOCX, metadata_objeto)

    disposicao = f'attachment; filename="{filename_cliente}"'
    try:
        # `momento=agora` -- MESMO instante gravado em `created_at`/
        # `expires_at` acima, nunca um novo `datetime.now()` interno
        # capturado depois do upload (ver docstring de
        # `_construir_url_assinada_v4` -- hardening pós-fechamento do
        # Gate 6.6-E: fecha a corrida entre a expiração real da URL e a
        # elegibilidade de limpeza baseada em metadado).
        url = transporte.assinar_url(object_name, TTL_DOWNLOAD_SEGUNDOS, disposicao, momento=agora)
    except ErroAssinaturaArtefato as e:
        limpeza_ok = None
        try:
            limpeza_ok = transporte.excluir(object_name)
        except Exception:
            limpeza_ok = False
        raise ErroAssinaturaArtefato(e.motivo, artefato_id=artefato_id, limpeza_ok=limpeza_ok) from e

    return ArtefatoEntregue(
        download_url=url,
        expires_at=expira_em.strftime("%Y-%m-%dT%H:%M:%SZ"),
        artefato_id=artefato_id,
    )


def limpar_artefatos_elegiveis(transporte: TransporteArtefato,
                                agora: _dt.datetime | None = None) -> dict:
    """Núcleo da exclusão NORMAL do artefato — sempre um DELETE real de
    objeto (nunca soft-delete recuperável: este bucket tem
    `soft_delete_policy.retentionDurationSeconds: 0`, verificado ao
    vivo; sem versionamento; sem retention policy/hold), distinta do
    backstop de lifecycle (~2 dias, assíncrono, sem garantia de prazo
    exato) e da expiração da URL assinada (24h, só access, nunca
    exclusão do objeto).

    Duas formas de chamada, mesma função (Gate 6.6-E continuação —
    "Do not rely only on opportunistic cleanup... could leave the final
    artifact stored indefinitely during periods of no traffic"):
    (1) oportunista, disparada por `finalizar_peca.py` depois de cada
    sucesso — cobre o caso comum, mas sozinha não garante nada sem
    tráfego; (2) `scripts/limpar_artefatos_agendado.py`, um entrypoint
    standalone invocado por um mecanismo de agendamento externo (Cloud
    Scheduler -> Cloud Run Job, provisionado e provado em homologação —
    ver ADR-0019) com cadência horária, que é o que torna a retenção
    normal ~24-25h mesmo sem nenhuma finalização acontecendo. Varre SÓ
    o prefixo `artifacts/`, lê SÓ o metadado seguro já gravado no
    upload — nunca conteúdo, nunca nome de arquivo do cliente, nunca
    dado de caso. Processa no máximo `LIMPEZA_MAX_OBJETOS_POR_VARREDURA`
    por chamada.

    **Elegibilidade é decidida por `expires_at`, nunca recalculada a
    partir de `created_at` (hardening pós-fechamento do Gate 6.6-E).**
    Achado real: `assinar_url()` capturava seu próprio `datetime.now()`
    internamente, DEPOIS do upload já ter terminado — então a expiração
    criptográfica real da URL (`X-Goog-Date + X-Goog-Expires`) ficava
    sempre um pouco DEPOIS do `expires_at` gravado no metadado (o atraso
    de rede do próprio upload). Se a limpeza comparasse `created_at +
    LIMPEZA_ELEGIVEL_SEGUNDOS`, uma varredura rodando exatamente nessa
    janela poderia excluir o objeto enquanto a URL emitida para ele
    ainda era, tecnicamente, válida — violando a invariante "artefato
    nunca fica elegível para limpeza antes de sua autorização de
    download emitida ter expirado". Corrigido na origem, não aqui:
    `entregar_artefato_efemero` agora assina com `momento=` o MESMO
    instante gravado em `created_at`/`expires_at` (ver sua docstring),
    então `expires_at` passa a ser EXATAMENTE a expiração real da URL, e
    esta função só precisa comparar `agora >= expires_at` — sem
    reconstruir esse valor a partir de outro campo, sem introduzir uma
    segunda fonte de verdade. **Metadado ausente ou malformado é
    fail-safe: o objeto é ignorado nesta varredura, nunca excluído por
    incerteza** — o backstop de lifecycle continua sendo a rede de
    segurança para esse caso, não uma exclusão apressada aqui.

    **Best-effort por design, nunca bloqueia a finalização que a
    disparou:** o chamador (`finalizar_peca.py`) invoca isto DEPOIS de
    já ter uma resposta de sucesso pronta para o cliente — qualquer
    exceção aqui é responsabilidade do CHAMADOR capturar (esta função
    não suprime as próprias exceções de rede/autenticação, para que o
    chamador possa decidir telemetria; ela decide, e sempre decide não
    propagar, porque um artefato órfão e não relacionado nunca deve
    degradar uma finalização que já passou por Template Lock/fidelidade/
    round-trip e já tem seu próprio artefato entregue). O backstop de
    lifecycle continua ativo independentemente do resultado.

    Devolve só contadores agregados (`inspecionados`/`excluidos`/
    `falhas`) — nunca nomes de objeto, nunca timestamp individual —
    seguro para telemetria."""
    resultado = {"inspecionados": 0, "excluidos": 0, "falhas": 0}
    if agora is None:
        agora = _dt.datetime.now(_dt.timezone.utc)

    objetos = transporte.listar("artifacts/", LIMPEZA_MAX_OBJETOS_POR_VARREDURA)
    for nome_objeto, metadata in objetos:
        resultado["inspecionados"] += 1
        expira_em_str = (metadata or {}).get("expires_at")
        if not expira_em_str:
            continue  # metadado ausente -- fail-safe, nunca excluído por incerteza
        try:
            expira_em = _dt.datetime.strptime(
                expira_em_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            continue  # metadado malformado -- mesmo fail-safe
        if agora < expira_em:
            continue  # autorização de download ainda não expirou
        if transporte.excluir(nome_objeto):
            resultado["excluidos"] += 1
        else:
            resultado["falhas"] += 1
    return resultado
