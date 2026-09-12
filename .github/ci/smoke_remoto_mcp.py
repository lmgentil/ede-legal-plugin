#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.github/ci/smoke_remoto_mcp.py — cliente MCP real usado SOMENTE pelo
workflow .github/workflows/deploy-mcp-staging.yml (Etapa 6.2-C.4B.2) para
provar, de FORA do Cloud Run, o caminho remoto completo pedido no gate:

    GitHub Actions -> WIF -> ede-mcp-smoke -> ID token -> Cloud Run IAM
    -> MCP SDK 2.2.0 -> Streamable HTTP -> ede_health

Réplica deliberadamente enxuta de .github/ci/homologar_container_mcp.py
(Etapa 6.2-B, mesma disciplina de nunca imprimir dado sensível e de só
asserir os campos estruturais de EdeHealthResponse) — script próprio, não
uma generalização daquele, por duas diferenças estruturais reais:

  1. alvo remoto real (Cloud Run via HTTPS), nunca loopback/subprocess
     local — não há container nem processo para subir/derrubar aqui;
  2. autenticação: o serviço remoto exige
     "Authorization: Bearer <ID token do Cloud Run>", inexistente no
     laboratório efêmero sem GCP da Etapa 6.2-B. O SDK oficial (mcp
     2.2.0) não expõe um parâmetro de headers na fachada `Client`/
     `StreamableHTTPTransport` para uma URL simples — o mecanismo
     documentado (docstring de
     mcp.client.streamable_http.streamable_http_client) é construir um
     httpx2.AsyncClient próprio (via create_mcp_http_client, que aplica
     os mesmos timeouts recomendados do SDK) com o header desejado e
     passá-lo como `http_client=`; o objeto resultante de
     streamable_http_client(...) já satisfaz o protocolo `Transport`
     esperado por `Client(server=...)`, dispensando qualquer acesso a
     API privada do SDK.

O token NUNCA é aceito como argumento de linha de comando (apareceria em
listagem de processo do SO e em histórico de shell) — este script só o lê
de uma variável de ambiente (nome configurável via --token-env, default
EDE_MCP_SMOKE_TOKEN) e nunca o imprime, loga, inclui em mensagem de erro
ou grava em arquivo.

Uso:
    EDE_MCP_SMOKE_TOKEN=<id-token-do-cloud-run> \
      python .github/ci/smoke_remoto_mcp.py \
        https://<servico>.run.app/mcp \
        --expected-version 0.11.1

Saída: exit(0) e resumo não sensível em stdout se todas as asserções
baterem (service_status=READY, contestacao_status=NOT_READY,
checks.rag.status=NOT_CONFIGURED, checks.modelo_oficial.status=
NOT_CONFIGURED, version=<--expected-version>); exit(1) com a asserção que
falhou, caso contrário; exit(2) se o token não estiver disponível na
variável de ambiente esperada. Nunca imprime segredo, credencial, token
ou conteúdo jurídico — só os campos estruturais de EdeHealthResponse
(mcp_server/server.py), todos deterministicos/institucionais, nenhum
dado de caso real.
"""
import argparse
import asyncio
import os
import sys


async def _homologar(url: str, token: str, expected_version: str) -> int:
    from mcp import Client
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    # create_mcp_http_client aplica os timeouts recomendados do SDK
    # (30s connect/write/pool, 300s read) — nunca o default genérico do
    # httpx2.AsyncClient, curto demais para uma conexão Streamable HTTP.
    http_client = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
    transport = streamable_http_client(url, http_client=http_client)

    async with Client(transport, raise_exceptions=True) as client:
        tools = await client.list_tools()
        nomes = {t.name for t in tools.tools}
        if "ede_health" not in nomes:
            print(f"FALHA: ede_health não anunciada pelo servidor remoto. Tools: {sorted(nomes)}")
            return 1

        resultado = await client.call_tool("ede_health", {})
        if resultado.is_error:
            print("FALHA: call_tool(ede_health) retornou erro.")
            return 1

        dados = resultado.structured_content
        if dados is None:
            print("FALHA: structured_content ausente na resposta de ede_health.")
            return 1

        esperado = {
            "service_status": "READY",
            "contestacao_status": "NOT_READY",
        }
        for campo, valor in esperado.items():
            if dados.get(campo) != valor:
                print(f"FALHA: {campo} = {dados.get(campo)!r}, esperado {valor!r}")
                return 1

        checks = dados.get("checks", {})
        for chave in ("rag", "modelo_oficial"):
            status = checks.get(chave, {}).get("status")
            if status != "NOT_CONFIGURED":
                print(f"FALHA: checks.{chave}.status = {status!r}, esperado 'NOT_CONFIGURED'")
                return 1

        versao = dados.get("version")
        if versao != expected_version:
            print(f"FALHA: version = {versao!r}, esperado {expected_version!r}")
            return 1

        resumo = (
            "OK — cliente MCP real, HTTP real, Cloud Run REMOTO, Streamable HTTP real, "
            "autenticado via WIF (ede-mcp-smoke):\n"
            f"  service_status        = {dados['service_status']}\n"
            f"  contestacao_status    = {dados['contestacao_status']}\n"
            f"  checks.rag            = {checks['rag']['status']}\n"
            f"  checks.modelo_oficial = {checks['modelo_oficial']['status']}\n"
            f"  version               = {versao}\n"
            f"  runtime               = {dados.get('runtime')}"
        )
        print(resumo)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke test MCP remoto (Cloud Run) via Streamable HTTP autenticado "
            "(Authorization: Bearer <ID token>). Nunca aceita o token por argumento."
        )
    )
    parser.add_argument("url", help="URL Streamable HTTP do serviço remoto (ex.: https://.../mcp)")
    parser.add_argument(
        "--token-env",
        default="EDE_MCP_SMOKE_TOKEN",
        help="Nome da variável de ambiente que contém o ID token (default: EDE_MCP_SMOKE_TOKEN).",
    )
    parser.add_argument(
        "--expected-version",
        required=True,
        help="Valor esperado de EdeHealthResponse.version (ex.: conteúdo do arquivo VERSION).",
    )
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    if not token:
        print(
            f"FALHA: variável de ambiente {args.token_env} ausente/vazia "
            "(o token nunca é aceito por argumento de linha de comando)."
        )
        sys.exit(2)

    sys.exit(asyncio.run(_homologar(args.url, token, args.expected_version)))


if __name__ == "__main__":
    main()
