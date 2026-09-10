#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_package.py — manipulação própria (EDE) do pacote OOXML/ZIP de um
`.docx`: extração segura para diretório, reempacotamento e validação
estrutural mínima (Etapa 5.10, ADR-0014).

Substitui a dependência histórica do skill "docx" de terceiro (Anthropic;
`skills/docx/` — NUNCA consultado, lido, copiado, adaptado ou traduzido
na implementação deste módulo; ver ADR-0014 e PEND-007 para o diagnóstico
completo). Fundamentado exclusivamente em:
  - biblioteca padrão Python (`zipfile`, `pathlib`, `shutil`, `os`,
    `stat`, `re`);
  - `lxml.etree`, já dependência direta do projeto (usada por
    `docx_template_engine.py`, `docx_numeracao_engine.py`,
    `docx_block_engine.py`), configurada para processamento seguro (sem
    resolução de entidade externa, sem rede, sem DTD — ver decisão
    lxml × defusedxml abaixo);
  - conhecimento público do formato ZIP (APPNOTE.TXT) e do OOXML/OPC
    (ECMA-376 / ISO-IEC 29500).

Host-agnostic (ADR-0014, regra de portabilidade da Etapa 5.10): este
módulo não importa, não lê e não consulta nada específico do Claude Code
(`CLAUDE_PLUGIN_ROOT`, `SKILL.md`, `~/.claude`, `~/.agents`) nem de
OpenAI SDK, Apps SDK ou MCP. Toda entrada é um `Path` explícito recebido
do chamador — quem resolve "onde estão os arquivos" é a camada que
importa este módulo, nunca ele mesmo.

API própria do EDE — deliberadamente NÃO espelha a assinatura do toolkit
substituído. Em particular, não há parâmetro `original_file`: a garantia
"nada fora de `word/document.xml` mudou" já é 100% responsabilidade de
`docx_template_engine.verificar_template_lock()` (código próprio,
inalterado por este módulo), que roda antes do reempacotamento — este
módulo não duplica essa checagem nem depende dela para operar.

Decisão lxml × defusedxml (Etapa 5.10, antes de escrever este módulo):
`defusedxml` está listada em `scripts/requirements.txt` desde a Etapa 5.9,
mas nunca foi de fato importada por nenhum código do EDE — era descrita
como "transitiva do toolkit de terceiro". Comparação objetiva:
  - `lxml.etree.XMLParser(resolve_entities=False, no_network=True,
    load_dtd=False, dtd_validation=False, huge_tree=False)` — padrão de
    hardening publicamente documentado para lxml (OWASP XXE Prevention
    Cheat Sheet) — bloqueia expansão de entidade (XXE e bombas de
    entidade tipo "billion laughs", já que entidades não resolvidas não
    são expandidas), acesso de rede e carregamento de DTD; `huge_tree`
    mantém os limites de robustez padrão do libxml2 contra árvores
    degeneradas.
  - `defusedxml` endurece os parsers da biblioteca padrão
    (`xml.etree.ElementTree`, `minidom`, `sax`, `xmlrpc`) contra as
    mesmas classes de ataque — mas o próprio projeto `defusedxml`
    documenta que seu wrapper para lxml (`defusedxml.lxml`) NÃO oferece
    a mesma garantia de proteção contra XXE que os wrappers da biblioteca
    padrão, precisamente por causa de como o lxml trata entidades por
    baixo. Ou seja: para proteger lxml, a orientação pública é configurar
    o parser do próprio lxml (acima), não envolvê-lo em `defusedxml`.
  - Decisão: usar só `lxml.etree` com parser configurado para
    processamento seguro. Não adicionar `defusedxml` como dependência —
    manteria uma segunda pilha de XML em paralelo só para uma função,
    sem ganho de proteção real sobre a configuração direta do lxml, que
    já é dependência direta e já é o único motor XML usado em todo o
    resto do pipeline de Contestação. `defusedxml` é removida de
    `scripts/requirements.txt` neste commit.

Decisão de reempacotamento determinístico (ADR-0014, Fase 3): o CONTEÚDO
de cada parte é preservado byte a byte (lido de disco, gravado sem
transformação alguma — nenhum parser XML é usado em `extrair_pacote_docx`
nem em `empacotar_pacote_docx`, só em `validar_estrutura_minima`, que é
estritamente leitura). O metadado de CONTÊINER (timestamp, ordem original
de compressão por entrada) NÃO é herdado do `ZipInfo` original — todo
arquivo é escrito com `ZIP_DEFLATED` e uma data-hora fixa
(`_DATA_ZIP_FIXA`), o que não afeta a compatibilidade OOXML/Word e torna
a saída determinística (mesmo diretório de entrada produz sempre o mesmo
`.docx`, byte a byte) — valioso para os testes de round-trip deste
módulo. Preservar o `ZipInfo` original por entrada seria possível, mas
foi avaliado como complexidade sem benefício real: o requisito nuclear é
o conteúdo das partes não alteradas permanecer idêntico, não o contêiner
ZIP inteiro.

Taxonomia de `PacoteDocxAbortada.stage` (Etapa 5.10, Commit 4 — padronização
do fail-closed do runtime DOCX):
  - `docx_package_invalido`: arquivo ausente/ilegível, ZIP corrompido ou
    inválido, pacote vazio, `[Content_Types].xml` ausente, ou qualquer
    entrada de caminho perigosa rejeitada por `_resolver_entrada_segura`/
    `_eh_symlink` (Zip Slip, path absoluto, prefixo de unidade Windows,
    separador ambíguo, symlink) — todos os casos em que o ZIP em si não
    pode ser confiavelmente tratado como um pacote OPC.
  - `docx_package_estrutura_incompleta`: o diretório de origem de
    `empacotar_pacote_docx` está ausente ou vazio — condição estrutural,
    não de conteúdo malicioso.
  Consumidores (`docx_template_engine.gerar_peca`,
  `docx_block_engine.gerar_peca_com_blocos`) propagam `e.stage`
  diretamente para o campo `"etapa"` do relatório de falha — nunca um
  rótulo genérico próprio (`"unpack"`/`"pack"`) que descartaria a
  informação, mesmo padrão já usado para `ComposicaoAbortada`/
  `NumeracaoAbortada` nesses arquivos.

  `template_ausente` (checado ANTES deste módulo ser chamado, pelos
  próprios consumidores — `docx_context_engine.py`/`docx_block_engine.py`/
  `docx_template_engine.py` — e por `dependencia_python_ausente`/
  `erro_interno`, abaixo) não é produzido por este módulo.

`dependencia_python_ausente` — DELIBERADAMENTE NÃO implementado neste
módulo nem em seus consumidores (Commit 4, item 6 do pedido). `lxml` é
importada no nível de módulo aqui e em todo consumidor
(`docx_template_engine.py`/`docx_context_engine.py`/`docx_block_engine.py`
já importam este módulo no próprio topo do arquivo) — se `lxml` não
estiver instalada, o `ImportError` ocorre ANTES de qualquer código do
pipeline poder envolvê-lo num `try/except`, e criar um import artificial
tardio só para tornar esse erro "capturável" adicionaria complexidade sem
benefício real (import dinâmico não é o padrão do projeto em nenhum outro
lugar). Verificação preventiva de dependências fica para
`scripts/ede_doctor.py` (Commit 6, ainda não implementado) — checar antes
da primeira geração, não durante.

`erro_interno` — reservado a pontos defensivos específicos e nomeados
onde uma inconsistência interna seria, por construção, impossível em
operação normal (ex.: `empacotar_pacote_docx` retornar sem levantar
exceção mas o arquivo de saída não existir) — nunca um
`except Exception` genérico envolvendo o pipeline inteiro. Uma exceção
verdadeiramente inesperada (bug de programação, não um destes casos
nomeados) continua se propagando com traceback completo — não é
convertida em `PacoteDocxAbortada` nem em `PIPELINE_ABORTED` por nenhum
`except` deste módulo ou de seus consumidores diretos.

Uso programático:
    from docx_package import extrair_pacote_docx, empacotar_pacote_docx, validar_estrutura_minima
    extrair_pacote_docx(Path("modelo.docx"), Path("/tmp/unpacked"))
    # ... document.xml já reescrito pelos motores do EDE (fora deste módulo) ...
    empacotar_pacote_docx(Path("/tmp/unpacked"), Path("saida.docx"))
"""
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

import lxml.etree as LET

# Data ZIP fixa (época ZIP, 1980-01-01, a mais antiga aceita pelo
# formato) usada em toda entrada escrita por empacotar_pacote_docx —
# reempacotamento determinístico, não depende do relógio do sistema no
# momento da geração (ver decisão no docstring do módulo).
_DATA_ZIP_FIXA = (1980, 1, 1, 0, 0, 0)

# Partes OPC/OOXML mínimas que este pipeline exige para considerar um
# pacote estruturalmente utilizável. Escopo deliberadamente estreito —
# só o que a Contestação de fato usa (WordprocessingML), não uma
# validação genérica de todo tipo de pacote OPC (planilha, apresentação).
_PARTES_OBRIGATORIAS = (
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
)

# Padrão de hardening publicamente documentado para lxml (OWASP XXE
# Prevention Cheat Sheet) — ver decisão lxml × defusedxml no docstring
# do módulo. Usado só para leitura (validar_estrutura_minima); nunca
# para escrita/serialização.
_PARSER_XML_SEGURO = LET.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    dtd_validation=False,
    huge_tree=False,
)

_PADRAO_DRIVE_WINDOWS = re.compile(r"^[A-Za-z]:")


class PacoteDocxAbortada(Exception):
    """Fail-closed deste módulo — mesmo contrato (stage, motivo) de
    ContextoAbortada/ComposicaoAbortada/NumeracaoAbortada
    (docx_context_engine.py, docx_block_engine.py,
    docx_numeracao_engine.py): plugável nos mesmos pontos de captura já
    existentes no pipeline sem mudar a forma do relatório de erro."""

    def __init__(self, stage, motivo):
        self.stage = stage
        self.motivo = motivo
        super().__init__(f"stage={stage} — {motivo}")


def _eh_symlink(info: zipfile.ZipInfo) -> bool:
    """True se a entrada codifica um link simbólico nos bits Unix altos
    de `external_attr` (convenção de ferramentas ZIP criadas em POSIX;
    ausente/zero em pacotes gerados no Windows/Word — não gera falso
    positivo nesses casos)."""
    modo_unix = info.external_attr >> 16
    return bool(modo_unix) and stat.S_ISLNK(modo_unix)


def _resolver_entrada_segura(nome: str, destino_dir: Path) -> Path:
    """Valida uma entrada de ZIP antes de extraí-la; devolve o Path de
    destino se segura. Levanta PacoteDocxAbortada (stage="docx_package_invalido")
    para path traversal, path absoluto (POSIX ou Windows) ou separador de
    diretório ambíguo entre Windows/POSIX.

    Nomes de entrada de ZIP são sempre separados por "/", por convenção
    do próprio formato (APPNOTE.TXT) — um "\\" dentro do nome nunca é
    separador legítimo. Em Windows, porém, pathlib trata "\\" como
    separador de diretório: sem esta rejeição explícita, uma entrada
    maliciosa com "\\" poderia atravessar diretório só nesse SO, mesmo
    passando incólume por uma checagem baseada só em PurePosixPath.
    Rejeitar sempre, independentemente do SO em que o módulo roda,
    elimina essa assimetria em vez de depender dela. Prefixo de unidade
    Windows ("C:...") é rejeitado à parte, porque PurePosixPath não o
    reconhece como caminho absoluto."""
    if not nome:
        raise PacoteDocxAbortada("docx_package_invalido", "entrada de ZIP com nome vazio rejeitada")
    if "\\" in nome:
        raise PacoteDocxAbortada(
            "docx_package_invalido",
            f"entrada de ZIP com separador de diretório ambíguo (Windows) rejeitada: {nome!r}",
        )
    if _PADRAO_DRIVE_WINDOWS.match(nome):
        raise PacoteDocxAbortada("docx_package_invalido", f"entrada com prefixo de unidade Windows rejeitada: {nome!r}")

    caminho_puro = PurePosixPath(nome)
    if caminho_puro.is_absolute():
        raise PacoteDocxAbortada("docx_package_invalido", f"entrada de caminho absoluto rejeitada: {nome!r}")
    if ".." in caminho_puro.parts:
        raise PacoteDocxAbortada("docx_package_invalido", f"entrada com travessia de diretório ('..') rejeitada: {nome!r}")

    destino_resolvido = destino_dir.resolve()
    alvo = (destino_dir / nome).resolve()
    if alvo != destino_resolvido and not alvo.is_relative_to(destino_resolvido):
        raise PacoteDocxAbortada("docx_package_invalido", f"entrada resolvida fora do diretório de destino (zip slip): {nome!r}")
    return alvo


def extrair_pacote_docx(docx_path: Path, destino_dir: Path) -> None:
    """Extrai o conteúdo ZIP de `docx_path` para `destino_dir` (criado se
    necessário), preservando os bytes de cada parte exatamente como estão
    no arquivo original — nenhuma reformatação, nenhum parsing XML nesta
    função (o que ainda não foi tocado pelos motores do EDE nunca é
    reescrito por este módulo).

    Fail-closed: levanta PacoteDocxAbortada("docx_package_invalido", ...) para
    arquivo ausente, ZIP corrompido/ilegível, pacote vazio, qualquer
    entrada de caminho perigosa (Zip Slip, path absoluto, prefixo de
    unidade Windows, separador ambíguo, link simbólico) ou pacote sem
    "[Content_Types].xml" (não é um pacote OPC válido — mínimo exigido
    pela norma, independente de ser especificamente um `.docx`)."""
    docx_path = Path(docx_path)
    destino_dir = Path(destino_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)

    try:
        zf = zipfile.ZipFile(docx_path, "r")
    except FileNotFoundError:
        raise PacoteDocxAbortada("docx_package_invalido", f"arquivo não encontrado: {docx_path}")
    except (zipfile.BadZipFile, OSError) as e:
        raise PacoteDocxAbortada("docx_package_invalido", f"não é um pacote ZIP válido: {docx_path} ({e})")

    with zf:
        try:
            infos = zf.infolist()
            if not infos:
                raise PacoteDocxAbortada("docx_package_invalido", f"pacote ZIP vazio: {docx_path}")

            alvos = []
            for info in infos:
                if _eh_symlink(info):
                    raise PacoteDocxAbortada("docx_package_invalido", f"entrada de link simbólico rejeitada: {info.filename!r}")
                alvos.append((info, _resolver_entrada_segura(info.filename, destino_dir)))

            nomes = {info.filename for info, _ in alvos}
            if "[Content_Types].xml" not in nomes:
                raise PacoteDocxAbortada(
                    "docx_package_invalido",
                    f"pacote sem [Content_Types].xml — não é um pacote OPC válido: {docx_path}",
                )

            for info, alvo in alvos:
                if info.filename.endswith("/"):
                    alvo.mkdir(parents=True, exist_ok=True)
                    continue
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as origem, open(alvo, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
        except (zipfile.BadZipFile, OSError) as e:
            raise PacoteDocxAbortada("docx_package_invalido", f"pacote ZIP corrompido ou ilegível: {docx_path} ({e})")


def empacotar_pacote_docx(origem_dir: Path, docx_saida: Path) -> None:
    """Reempacota o diretório `origem_dir` (produzido por
    extrair_pacote_docx, com `word/document.xml` já reescrito pelos
    motores do EDE) num arquivo `.docx` em `docx_saida`.

    Escreve primeiro num arquivo temporário no mesmo diretório de
    `docx_saida` e só então o promove com `os.replace` (rename atômico no
    mesmo sistema de arquivos) — nunca deixa um `.docx` parcialmente
    escrito no caminho final em caso de falha no meio da escrita.

    Ver decisão de reempacotamento determinístico no docstring do
    módulo: conteúdo de cada parte é preservado byte a byte; metadado de
    contêiner (timestamp, compressão original por entrada) não é."""
    origem_dir = Path(origem_dir)
    docx_saida = Path(docx_saida)
    if not origem_dir.is_dir():
        raise PacoteDocxAbortada("docx_package_estrutura_incompleta", f"diretório de origem inexistente: {origem_dir}")

    arquivos = [
        (p.relative_to(origem_dir).as_posix(), p)
        for p in origem_dir.rglob("*")
        if p.is_file()
    ]
    if not arquivos:
        raise PacoteDocxAbortada("docx_package_estrutura_incompleta", f"diretório de origem vazio: {origem_dir}")

    # "[Content_Types].xml" primeiro (convenção OPC observada na prática,
    # não estritamente exigida pela norma); demais entradas em ordem
    # alfabética — determinístico, não depende de ordem de travessia do
    # sistema de arquivos.
    arquivos.sort(key=lambda par: (par[0] != "[Content_Types].xml", par[0]))

    docx_saida.parent.mkdir(parents=True, exist_ok=True)
    tmp_saida = docx_saida.with_name(docx_saida.name + ".tmp")

    try:
        with zipfile.ZipFile(tmp_saida, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome_zip, caminho_real in arquivos:
                info = zipfile.ZipInfo(filename=nome_zip, date_time=_DATA_ZIP_FIXA)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, caminho_real.read_bytes())
    except OSError:
        tmp_saida.unlink(missing_ok=True)
        raise

    os.replace(tmp_saida, docx_saida)


def validar_estrutura_minima(pacote_dir: Path) -> list:
    """Confere, sobre um diretório já extraído por extrair_pacote_docx:
    (1) presença das partes OPC/OOXML mínimas exigidas por este pipeline
    (_PARTES_OBRIGATORIAS); (2) boa-formação XML de toda parte `.xml`/
    `.rels` encontrada, usando um parser lxml configurado para
    processamento seguro (ver decisão lxml × defusedxml no docstring do
    módulo).

    Não levanta exceção — devolve lista de problemas (vazia = OK); quem
    chama decide se/como transformar isso em PacoteDocxAbortada, seguindo
    o mesmo padrão dos demais motores do EDE (validar_placeholders,
    validar_catalogo etc., que também só relatam, não abortam sozinhos)."""
    pacote_dir = Path(pacote_dir)
    problemas = []

    for parte in _PARTES_OBRIGATORIAS:
        if not (pacote_dir / parte).is_file():
            problemas.append(f"parte obrigatória ausente: {parte}")

    for caminho in sorted(pacote_dir.rglob("*")):
        if not caminho.is_file() or caminho.suffix.lower() not in (".xml", ".rels"):
            continue
        try:
            LET.parse(str(caminho), parser=_PARSER_XML_SEGURO)
        except LET.XMLSyntaxError as e:
            problemas.append(f"XML malformado em {caminho.relative_to(pacote_dir).as_posix()}: {e}")

    return problemas
