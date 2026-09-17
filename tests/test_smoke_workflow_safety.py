#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_smoke_workflow_safety.py — testes estruturais estáticos de
`.github/workflows/smoke-mcp-production.yml` (Gate 6.3-D3.3-E §16).

Nunca chama GCP/Descope/GitHub. Só faz parsing YAML do próprio arquivo e
afirma as invariantes de segurança do workflow, para que uma edição
futura que amplie silenciosamente seu escopo (build, deploy, mutação de
IAM, `allUsers`, alvo de staging/descartável, token em input de
`workflow_dispatch`) quebre a suíte em vez de passar despercebida.

Requer PyYAML (dependência leve, só para este teste — nunca importada
por `mcp_server/`; não é dependência de runtime/produção).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML necessário só para este teste estrutural")

BASE = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = BASE / ".github" / "workflows" / "smoke-mcp-production.yml"

PRODUCAO_URL = "https://ede-mcp-269134711029.southamerica-east1.run.app"
SMOKE_SA = "ede-mcp-smoke@ede-legal-mcp-01.iam.gserviceaccount.com"
DEPLOYER_SA = "ede-mcp-deployer@ede-legal-mcp-01.iam.gserviceaccount.com"
RUNTIME_SA = "ede-mcp-runtime@ede-legal-mcp-01.iam.gserviceaccount.com"

PROIBIDOS_EM_COMANDO = (
    "gcloud run deploy",
    "gcloud run services update",
    "gcloud run services delete",
    "gcloud builds submit",
    "docker build",
    "docker push",
    "update-traffic",
    "set-iam-policy",
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "--allow-unauthenticated",
    "allUsers",
)


@pytest.fixture(scope="module")
def workflow_texto() -> str:
    assert WORKFLOW_PATH.exists(), f"workflow não encontrado: {WORKFLOW_PATH}"
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(workflow_texto: str) -> dict:
    dados = yaml.safe_load(workflow_texto)
    assert isinstance(dados, dict)
    return dados


def _todos_os_comandos_run(workflow: dict) -> list[str]:
    comandos: list[str] = []
    for job in workflow.get("jobs", {}).values():
        for passo in job.get("steps", []):
            comando = passo.get("run")
            if comando:
                comandos.append(comando)
    return comandos


def test_gatilho_e_somente_workflow_dispatch(workflow: dict):
    # YAML carrega a chave `on:` como booleano `True` em alguns
    # carregadores por causa da abreviação YAML 1.1 de `on`/`off` — lida
    # com as duas formas possíveis.
    gatilho = workflow.get("on", workflow.get(True))
    assert gatilho is not None, "chave 'on' ausente"
    assert set(gatilho.keys()) == {"workflow_dispatch"}, (
        f"gatilhos inesperados: {sorted(gatilho.keys())} — só workflow_dispatch é permitido "
        f"(sem push/pull_request/schedule)."
    )


def test_permissoes_minimas_exatas(workflow: dict):
    permissoes = workflow.get("permissions")
    assert permissoes == {"contents": "read", "id-token": "write"}, (
        f"permissões inesperadas: {permissoes} — só contents:read e id-token:write são permitidas."
    )


def test_servico_de_producao_fixo_sem_staging_sem_descartavel(workflow_texto: str):
    assert "ede-mcp-staging" not in workflow_texto
    assert "ede-oauth-proof-disposable" not in workflow_texto
    assert "SERVICE: ede-mcp" in workflow_texto
    assert PRODUCAO_URL in workflow_texto


def test_identidade_smoke_fixa_nunca_deployer_nem_runtime_como_service_account(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        for passo in job.get("steps", []):
            usa = passo.get("uses", "")
            if "google-github-actions/auth" in usa:
                sa = passo.get("with", {}).get("service_account", "")
                assert sa == "${{ env.SMOKE_SA }}", (
                    f"step de auth usando service_account={sa!r} — só ede-mcp-smoke "
                    f"(via env.SMOKE_SA) é permitido neste workflow."
                )
    env = workflow.get("env", {})
    assert env.get("SMOKE_SA") == SMOKE_SA
    # DEPLOYER_SA/RUNTIME_SA podem existir só como referência de
    # comparação NEGATIVA na prova de identidade (nunca usados para auth).
    assert env.get("DEPLOYER_SA") == DEPLOYER_SA
    assert env.get("RUNTIME_SA") == RUNTIME_SA


def test_nenhum_comando_de_build_deploy_ou_mutacao_iam(workflow: dict):
    comandos = "\n".join(_todos_os_comandos_run(workflow))
    for proibido in PROIBIDOS_EM_COMANDO:
        assert proibido not in comandos, f"comando proibido encontrado no workflow: {proibido!r}"


def test_sem_input_de_workflow_dispatch_para_token_ou_segredo(workflow: dict):
    gatilho = workflow.get("on", workflow.get(True))
    wd = gatilho.get("workflow_dispatch")
    # `workflow_dispatch: {}` (sem inputs) é a forma exigida — qualquer
    # input futuro que pareça carregar segredo/token quebra este teste;
    # inputs não relacionados a segredo exigiriam atualizar esta lista
    # explicitamente, nunca por omissão.
    assert wd in (None, {}), (
        f"workflow_dispatch com inputs inesperados: {wd} — nenhum input é permitido "
        f"neste workflow (nenhum token/segredo pode trafegar por aqui)."
    )


def test_nenhum_step_de_upload_artifact(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        for passo in job.get("steps", []):
            usa = passo.get("uses", "")
            assert "upload-artifact" not in usa, "upload de artifact não é permitido neste workflow."


def test_mascaramento_do_id_token_presente(workflow_texto: str):
    assert "::add-mask::" in workflow_texto
    assert re.search(r"add-mask::\$\{\{\s*steps\.auth-smoke\.outputs\.id_token\s*\}\}", workflow_texto) or (
        "add-mask::$SMOKE_ID_TOKEN" in workflow_texto
    )


def test_workload_identity_provider_e_o_pool_ja_homologado(workflow: dict):
    env = workflow.get("env", {})
    assert env.get("WORKLOAD_IDENTITY_PROVIDER") == (
        "projects/269134711029/locations/global/workloadIdentityPools/"
        "github-pool/providers/github-provider"
    )


def test_sem_secrets_context_algum(workflow_texto: str):
    assert "secrets." not in workflow_texto, (
        "workflow referencia `secrets.*` — este workflow não deve depender de nenhum "
        "GitHub Secret (nenhuma credencial persistente é necessária)."
    )
