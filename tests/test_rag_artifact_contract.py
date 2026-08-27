"""Contrato de compatibilidade dos artefatos persistidos do RAG LSA.

Cada teste cobre uma falha operacional que não pode ser tratada como mero
warning: manifesto legado sem proveniência, runtime incompatível e artefato
alterado depois da geração. O build também precisa produzir tudo o que o
loader exige, para que os dois lados do contrato não possam divergir.
"""

import hashlib
import importlib.metadata
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "rag"))
sys.path.insert(0, str(BASE / "rag" / "embeddings"))

import build_embeddings as builder  # noqa: E402
import artifact_contract as contract  # noqa: E402
import search_hybrid as sh  # noqa: E402

pytestmark = pytest.mark.rag


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_instalado() -> dict:
    return {
        "python": ".".join(map(str, sys.version_info[:3])),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "joblib": importlib.metadata.version("joblib"),
        "pandas": importlib.metadata.version("pandas"),
        "pyarrow": importlib.metadata.version("pyarrow"),
    }


def _corpus_minimo() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"corpus": "TESTE", "file_name": "a.md", "text": "energia elétrica consumo"},
            {"corpus": "TESTE", "file_name": "b.md", "text": "energia medição faturamento"},
            {"corpus": "TESTE", "file_name": "c.md", "text": "cobrança consumo medição"},
            {"corpus": "TESTE", "file_name": "d.md", "text": "faturamento elétrica cobrança"},
        ]
    )


def test_loader_rejeita_manifesto_legado_sem_contrato_de_runtime(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"total_chunks": 434, "arquivos": {}}), encoding="utf-8"
    )
    monkeypatch.setattr(sh, "EMB", tmp_path)

    with pytest.raises(RuntimeError, match="contrato de runtime"):
        sh.HybridSearcher()


def test_loader_rejeita_sklearn_diferente_do_usado_no_build(tmp_path, monkeypatch):
    manifest = {
        "runtime": {
            "python": "3.12.10",
            "scikit_learn": "0.0.0-incompativel",
            "numpy": "0.0.0-incompativel",
            "scipy": "0.0.0-incompativel",
            "joblib": "0.0.0-incompativel",
            "pandas": "0.0.0-incompativel",
            "pyarrow": "0.0.0-incompativel",
        },
        "sha256": {},
        "arquivos": {},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sh, "EMB", tmp_path)

    with pytest.raises(RuntimeError, match="scikit_learn"):
        sh.HybridSearcher()


def test_loader_rejeita_hash_divergente_antes_de_desserializar(tmp_path, monkeypatch):
    for nome in ("embeddings_all.parquet", "vectorizer.joblib", "svd.joblib"):
        (tmp_path / nome).write_bytes(b"artefato-alterado")
    manifest = {
        "runtime": _runtime_instalado(),
        "armazenamento": contract.formato_armazenamento_lsa(),
        "sha256": {
            "embeddings_all.parquet": "0" * 64,
            "vectorizer.joblib": "0" * 64,
            "svd.joblib": "0" * 64,
        },
        "arquivos": {
            "combinado": "embeddings_all.parquet",
            "vectorizer": "vectorizer.joblib",
            "svd": "svd.joblib",
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sh, "EMB", tmp_path)

    with pytest.raises(RuntimeError, match="hash SHA-256 divergente"):
        sh.HybridSearcher()


def test_loader_rejeita_manifesto_sem_contrato_de_armazenamento(tmp_path):
    manifest = {
        "runtime": _runtime_instalado(),
        "sha256": {},
        "arquivos": {},
    }

    with pytest.raises(RuntimeError, match="contrato de armazenamento"):
        contract.validar_contrato_lsa(manifest, tmp_path)


def test_loader_rejeita_svd_com_dtype_divergente_do_manifesto(tmp_path, monkeypatch):
    pd.DataFrame(
        [{"text": "energia", "file_name": "chunk.md", "embedding": [1.0]}]
    ).to_parquet(tmp_path / "embeddings_all.parquet", index=False)
    joblib.dump(SimpleNamespace(), tmp_path / "vectorizer.joblib")
    joblib.dump(
        SimpleNamespace(components_=np.ones((1, 1), dtype=np.float64)),
        tmp_path / "svd.joblib",
    )
    arquivos = {
        "combinado": "embeddings_all.parquet",
        "vectorizer": "vectorizer.joblib",
        "svd": "svd.joblib",
    }
    manifest = {
        "runtime": _runtime_instalado(),
        "armazenamento": contract.formato_armazenamento_lsa(),
        "arquivos": arquivos,
        "sha256": {nome: _sha256(tmp_path / nome) for nome in arquivos.values()},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sh, "EMB", tmp_path)

    with pytest.raises(RuntimeError, match="dtype incompatível"):
        sh.HybridSearcher()


def test_build_grava_runtime_e_hashes_dos_artefatos(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "OUT_DIR", tmp_path)
    monkeypatch.setattr(builder, "load_all_chunks", lambda: _corpus_minimo().copy())

    builder.main()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["runtime"] == builder.runtime_atual()
    for nome in ("embeddings_all.parquet", "vectorizer.joblib", "svd.joblib"):
        assert manifest["sha256"][nome] == _sha256(tmp_path / nome)


def test_build_grava_svd_float32_compressao_zlib(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "OUT_DIR", tmp_path)
    monkeypatch.setattr(builder, "load_all_chunks", lambda: _corpus_minimo().copy())

    builder.main()

    svd_path = tmp_path / "svd.joblib"
    svd = joblib.load(svd_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    uncompressed_path = tmp_path / "svd-uncompressed.joblib"
    joblib.dump(svd, uncompressed_path, compress=0)

    assert svd.components_.dtype == np.dtype("float32")
    assert manifest["armazenamento"] == {
        "svd_components_dtype": "float32",
        "joblib_compress": "zlib",
        "joblib_compress_level": 3,
    }
    assert svd_path.stat().st_size < uncompressed_path.stat().st_size
