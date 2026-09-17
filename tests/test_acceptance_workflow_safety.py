#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_acceptance_workflow_safety.py — testes estruturais estáticos
de `.github/workflows/acceptance-self-hosted-temp.yml` (Gate 6.3-D3.3-G).

Nunca chama GCP/Descope/GitHub. Só faz parsing YAML do próprio arquivo e
afirma as invariantes de segurança do workflow TEMPORÁRIO de aceitação
via runner self-hosted — em particular, que o rótulo do runner nunca é
`self-hosted` sozinho (o que aceitaria QUALQUER máquina self-hosted, não
só a temporária deste gate) e que nenhum segredo/token pode vazar por
`workflow_dispatch`, artifact, summary ou `secrets.*`.

Este arquivo e o workflow que ele testa são ambos DESCARTÁVEIS — serão
removidos do repositório ao final do Gate 6.3-D3.3-G. Enquanto existirem,
continuam sujeitos à mesma disciplina de teste dos demais workflows.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML necessário só para este teste estrutural")

BASE = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = BASE / ".github" / "workflows" / "acceptance-self-hosted-temp.yml"

PRODUCAO_URL = "https://ede-mcp-269134711029.southamerica-east1.run.app"
SMOKE_SA = "ede-mcp-smoke@ede-legal-mcp-01.iam.gserviceaccount.com"
RUNNER_LABEL_TEMP = "ede-production-acceptance-temp"

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
    "runners/registration-token",
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


def test_gatilho_e_somente_workflow_dispatch_sem_inputs(workflow: dict):
    gatilho = workflow.get("on", workflow.get(True))
    assert gatilho is not None, "chave 'on' ausente"
    assert set(gatilho.keys()) == {"workflow_dispatch"}
    assert gatilho.get("workflow_dispatch") in (None, {}), (
        "workflow_dispatch não pode ter inputs — nenhum token/segredo pode "
        "trafegar por aqui."
    )


def test_permissoes_minimas_exatas(workflow: dict):
    assert workflow.get("permissions") == {"contents": "read", "id-token": "write"}


def test_runs_on_e_o_rotulo_triplo_exato_nunca_self_hosted_sozinho(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        runs_on = job.get("runs-on")
        assert isinstance(runs_on, list), (
            f"runs-on precisa ser uma lista explícita de rótulos, obtido: {runs_on!r}"
        )
        assert set(runs_on) == {"self-hosted", "Windows", RUNNER_LABEL_TEMP}, (
            f"runs-on inesperado: {runs_on} — só o trio exato "
            f"[self-hosted, Windows, {RUNNER_LABEL_TEMP}] é permitido, nunca "
            f"'self-hosted' isolado nem outro rótulo."
        )


def test_timeout_finito_no_job(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        assert isinstance(job.get("timeout-minutes"), int) and job["timeout-minutes"] > 0, (
            "job precisa de timeout-minutes finito — o runner temporário não pode "
            "ficar ocupado indefinidamente."
        )


def test_concurrency_declarada(workflow: dict):
    conc = workflow.get("concurrency")
    assert isinstance(conc, dict) and conc.get("group"), "concurrency.group ausente"
    assert conc.get("cancel-in-progress") is False


def test_servico_de_producao_fixo(workflow_texto: str):
    assert PRODUCAO_URL in workflow_texto
    assert "ede-mcp-staging" not in workflow_texto


def test_identidade_smoke_fixa(workflow: dict, workflow_texto: str):
    for job in workflow.get("jobs", {}).values():
        for passo in job.get("steps", []):
            if "google-github-actions/auth" in passo.get("uses", ""):
                sa = passo.get("with", {}).get("service_account", "")
                assert sa == "${{ env.SMOKE_SA }}"
    env = workflow.get("env", {})
    assert env.get("SMOKE_SA") == SMOKE_SA


def test_nenhum_comando_de_build_deploy_mutacao_iam_ou_criacao_de_runner(workflow: dict):
    comandos = "\n".join(_todos_os_comandos_run(workflow))
    for proibido in PROIBIDOS_EM_COMANDO:
        assert proibido not in comandos, f"comando proibido encontrado no workflow: {proibido!r}"


def test_sem_secrets_context_algum(workflow_texto: str):
    # Distingue o contexto `${{ secrets.* }}` do GitHub Actions do módulo
    # `secrets` da stdlib do Python (usado dentro do script embutido para
    # `secrets.token_bytes`/`secrets.token_urlsafe`, sem relação alguma
    # com GitHub Secrets).
    assert "${{ secrets." not in workflow_texto
    assert "secrets.GITHUB_TOKEN" not in workflow_texto


def test_sem_upload_de_artifact(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        for passo in job.get("steps", []):
            assert "upload-artifact" not in passo.get("uses", "")


def test_token_do_google_mascarado_antes_do_passo_de_aceitacao(workflow_texto: str):
    assert "::add-mask::${{ steps.auth-smoke.outputs.id_token }}" in workflow_texto
    assert "::add-mask::$GOOGLE_ID_TOKEN" in workflow_texto


def test_token_descope_nunca_escrito_em_canal_entre_steps(workflow_texto: str):
    # O token Descope (`descope_token`, dentro do script Python embutido)
    # nunca pode aparecer atribuído a GITHUB_ENV/GITHUB_OUTPUT/GITHUB_STEP_SUMMARY.
    for canal in ("GITHUB_ENV", "GITHUB_OUTPUT"):
        for linha in workflow_texto.splitlines():
            if canal in linha:
                assert "descope_token" not in linha.lower()
                assert "access_token" not in linha.lower()


def test_workload_identity_provider_e_o_pool_ja_homologado(workflow: dict):
    env = workflow.get("env", {})
    assert env.get("WORKLOAD_IDENTITY_PROVIDER") == (
        "projects/269134711029/locations/global/workloadIdentityPools/"
        "github-pool/providers/github-provider"
    )
