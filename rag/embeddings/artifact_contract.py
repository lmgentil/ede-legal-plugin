"""Contrato reproduzível e fail-closed dos artefatos LSA do RAG.

O builder registra o runtime e os hashes; o loader valida ambos antes de
abrir parquet ou desserializar estimadores joblib. Artefato persistido não é
compatível por presunção: o contrato precisa provar essa compatibilidade.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import sys
from pathlib import Path


PACOTES_RUNTIME = (
    ("scikit_learn", "scikit-learn"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("joblib", "joblib"),
    ("pandas", "pandas"),
    ("pyarrow", "pyarrow"),
)
ARTEFATOS_OBRIGATORIOS = ("combinado", "vectorizer", "svd")
FORMATO_ARMAZENAMENTO_LSA = {
    "svd_components_dtype": "float32",
    "joblib_compress": "zlib",
    "joblib_compress_level": 3,
}


class RagArtifactCompatibilityError(RuntimeError):
    """O índice LSA não pode ser usado com segurança neste runtime."""


def formato_armazenamento_lsa() -> dict:
    """Retorna o formato canônico e compacto dos artefatos LSA."""
    return FORMATO_ARMAZENAMENTO_LSA.copy()


def runtime_atual() -> dict:
    """Retorna as versões que determinam a compatibilidade do índice LSA."""
    runtime = {"python": ".".join(map(str, sys.version_info[:3]))}
    for chave, distribuicao in PACOTES_RUNTIME:
        runtime[chave] = importlib.metadata.version(distribuicao)
    return runtime


def sha256_arquivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def hashes_dos_artefatos(diretorio: Path, arquivos: dict) -> dict:
    hashes = {}
    for chave in ARTEFATOS_OBRIGATORIOS:
        nome = arquivos.get(chave)
        if not isinstance(nome, str) or not nome:
            raise RagArtifactCompatibilityError(
                f"manifesto LSA sem arquivo obrigatório: arquivos.{chave}"
            )
        if Path(nome).name != nome:
            raise RagArtifactCompatibilityError(
                f"caminho de artefato LSA inválido no manifesto: {nome!r}"
            )
        path = diretorio / nome
        if not path.is_file():
            raise RagArtifactCompatibilityError(f"artefato LSA ausente: {path}")
        hashes[nome] = sha256_arquivo(path)
    return hashes


def validar_contrato_lsa(manifesto: dict, diretorio: Path) -> None:
    """Valida runtime e integridade antes de qualquer desserialização."""
    esperado = manifesto.get("runtime")
    if not isinstance(esperado, dict):
        raise RagArtifactCompatibilityError(
            "manifesto LSA legado sem contrato de runtime; regenere os artefatos "
            "com rag/embeddings/build_embeddings.py"
        )

    atual = runtime_atual()
    campos = ("python",) + tuple(chave for chave, _ in PACOTES_RUNTIME)
    ausentes = [campo for campo in campos if not esperado.get(campo)]
    if ausentes:
        raise RagArtifactCompatibilityError(
            f"contrato de runtime LSA incompleto; campos ausentes: {ausentes}"
        )

    divergencias = [
        f"{campo}: build={esperado[campo]!r}, runtime={atual[campo]!r}"
        for campo in campos
        if esperado[campo] != atual[campo]
    ]
    if divergencias:
        raise RagArtifactCompatibilityError(
            "runtime incompatível com os artefatos LSA: " + "; ".join(divergencias)
        )

    armazenamento = manifesto.get("armazenamento")
    esperado_armazenamento = formato_armazenamento_lsa()
    if armazenamento != esperado_armazenamento:
        raise RagArtifactCompatibilityError(
            "contrato de armazenamento LSA ausente ou incompatível: "
            f"manifesto={armazenamento!r}, esperado={esperado_armazenamento!r}"
        )

    arquivos = manifesto.get("arquivos")
    if not isinstance(arquivos, dict):
        raise RagArtifactCompatibilityError("manifesto LSA sem catálogo de arquivos")
    hashes_esperados = manifesto.get("sha256")
    if not isinstance(hashes_esperados, dict):
        raise RagArtifactCompatibilityError("manifesto LSA sem hashes SHA-256")

    hashes_atuais = hashes_dos_artefatos(diretorio, arquivos)
    for nome, hash_atual in hashes_atuais.items():
        hash_esperado = hashes_esperados.get(nome)
        if hash_esperado != hash_atual:
            raise RagArtifactCompatibilityError(
                f"hash SHA-256 divergente para {nome}: "
                f"manifesto={hash_esperado!r}, atual={hash_atual!r}"
            )


def validar_svd_lsa(svd: object, manifesto: dict) -> None:
    """Confirma que o estimador carregado corresponde ao formato declarado."""
    armazenamento = manifesto["armazenamento"]
    components = getattr(svd, "components_", None)
    dtype_atual = str(getattr(components, "dtype", "ausente"))
    dtype_esperado = armazenamento["svd_components_dtype"]
    if dtype_atual != dtype_esperado:
        raise RagArtifactCompatibilityError(
            "dtype incompatível em svd.components_: "
            f"manifesto={dtype_esperado!r}, artefato={dtype_atual!r}"
        )
