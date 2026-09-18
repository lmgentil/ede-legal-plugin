#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.github/ci/homologar_container_mcp.py — cliente MCP real usado SOMENTE
pelo workflow .github/workflows/homologar-mcp-container.yml (Etapa
6.2-B, laboratório efêmero em GitHub Actions) para provar, de FORA do
container, o caminho completo pedido no gate:

    CLIENTE MCP -> HTTP real -> container -> Streamable HTTP -> ede_health

Não é um teste da suíte pytest do projeto (não fica em tests/, não usa
fixtures/conftest do projeto, não é coletado por `pytest tests/`) — é um
script de CI mínimo, específico da homologação do container publicado
via `docker run -p`. Réplica deliberadamente enxuta da mesma lógica já
provada em tests/test_mcp_streamable_http.py (mesma API do SDK oficial,
mesmo padrão `async with Client(...)`), mas apontando para a URL HTTP
publicada pelo container real, nunca para um subprocess local — é
exatamente essa diferença (processo dentro de um container Linux
efêmero, alcançado só via rede publicada) que este script existe para
provar.

Uso:
    python .github/ci/homologar_container_mcp.py http://127.0.0.1:9123/mcp

Saída: exit(0) e resumo não sensível em stdout se todas as asserções
baterem; exit(1) com a asserção que falhou, caso contrário. Nunca
imprime segredo, credencial ou conteúdo jurídico — só os campos
estruturais de EdeHealthResponse (mcp_server/server.py), todos
deterministicos/institucionais, nenhum dado de caso real.

Atualizado no Gate 6.4-B: o container do candidato SEMPRE sobe aqui SEM
nenhuma variável `EDE_MODELO_OFICIAL_*` no ambiente (nenhum segredo/
config de produção chega a este runner efêmero) — por isso
`checks.modelo_oficial` continua NOT_CONFIGURED, exatamente como antes.
`checks.rag`, porém, deixou de ser NOT_CONFIGURED fixo desde o Gate
6.4-A (ADR-0017 §6: o corpus RAG é asset público já embutido na imagem)
— o valor esperado agora é READY, refletindo o corpus real que o
Dockerfile copiou. `contestacao_status` continua NOT_READY (só
`modelo_oficial` falta) — nunca READY neste gate, que não autoriza
provisionar o Modelo Oficial dentro da imagem candidata (ADR-0009).
"""
import asyncio
import sys


async def _homologar(url: str) -> int:
    from mcp import Client

    async with Client(url, raise_exceptions=True) as client:
        tools = await client.list_tools()
        nomes = {t.name for t in tools.tools}
        if "ede_health" not in nomes:
            print(f"FALHA: ede_health não anunciada pelo servidor. Tools: {sorted(nomes)}")
            return 1
        # Gate 6.5-A: este container sobe SEM camada OAuth de aplicação
        # (config=None) — não há filtragem de escopo por ferramenta neste
        # modo, então `ede_preparar_contestacao` (escopo ede:legal em
        # produção) aparece aqui também; isso é esperado e correto para
        # este smoke test específico, nunca para produção real (OAuth
        # obrigatória, ver mcp_server/auth_config.py).
        if "ede_preparar_contestacao" not in nomes:
            print(f"FALHA: ede_preparar_contestacao não anunciada pelo servidor. Tools: {sorted(nomes)}")
            return 1

        resultado = await client.call_tool("ede_health", {})
        if resultado.is_error:
            print(f"FALHA: call_tool(ede_health) retornou erro: {resultado}")
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
        esperado_checks = {"rag": "READY", "modelo_oficial": "NOT_CONFIGURED"}
        for chave, valor_esperado in esperado_checks.items():
            status = checks.get(chave, {}).get("status")
            if status != valor_esperado:
                print(f"FALHA: checks.{chave}.status = {status!r}, esperado {valor_esperado!r}")
                return 1

        resumo = (
            "OK — cliente MCP real, HTTP real, container real, Streamable HTTP real:\n"
            f"  service_status        = {dados['service_status']}\n"
            f"  contestacao_status    = {dados['contestacao_status']}\n"
            f"  checks.rag            = {checks['rag']['status']}\n"
            f"  checks.modelo_oficial = {checks['modelo_oficial']['status']}\n"
            f"  version               = {dados.get('version')}\n"
            f"  runtime               = {dados.get('runtime')}"
        )
        print(resumo)
        return 0


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: homologar_container_mcp.py <url-streamable-http>")
        sys.exit(2)
    sys.exit(asyncio.run(_homologar(sys.argv[1])))


if __name__ == "__main__":
    main()
