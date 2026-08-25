# -*- coding: utf-8 -*-
"""
conftest.py — ponto de entrada da sessão pytest para garantir_utf8().

Achado real: mover garantir_utf8() para dentro de main()/`__main__` (a
correção que torna o `import` de módulos de teste seguro, sem sys.exit
como efeito colateral) removia, para quem roda a suíte via `pytest`
(nunca via `python arquivo.py`), a garantia funcional de UTF-8 que a
própria função existe para prover — e testes que exercitam de verdade o
toolkit externo do skill "docx" (unpack/pack/validate) contra o template
real voltavam a falhar com UnicodeDecodeError ('charmap' codec).

conftest.py é o ponto certo para isso: pytest o importa uma única vez, no
início da sessão, antes de coletar qualquer módulo de teste — é o
"entrypoint" real da execução via `pytest`, equivalente a main()/
`__main__` para os CLIs deste projeto. Chamar aqui (nunca dentro de um
módulo de teste individual) preserva a separação biblioteca/CLI: só um
entrypoint de processo decide sys.exit(), nunca o import de um módulo de
teste comum.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from docx_template_engine import garantir_utf8  # noqa: E402

garantir_utf8()
