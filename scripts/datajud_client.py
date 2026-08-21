#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datajud_client.py — resolução determinística de {{JUIZO}} via API Pública
DataJud/CNJ (INV-JUIZO-DATAJUD, correção pontual).

{{JUIZO}} deixa de ser conteúdo gerativo do redator: a unidade judiciária
real do processo é identificada por consulta estruturada, nunca inventada
ou inferida livremente pela IA.

Fluxo:
    NUMERO_PROCESSO -> normalizar (20 dígitos) -> identificar_alias (segmento
    + tribunal do número CNJ) -> consultar DataJud -> extrair orgaoJulgador
    -> resolver comarca (IBGE, a partir de codigoMunicipioIBGE) -> montar
    JUIZO no padrão institucional "AO JUÍZO DA ... DA COMARCA DE ...".

Documentação consultada (não presumida) antes de implementar o mapeamento
de campos, em 2026-08 — ver relatório da correção para os links:
  - https://datajud-wiki.cnj.jus.br/api-publica/endpoints/ (lista real de
    aliases por tribunal — usada para derivar o padrão "api_publica_tj<uf>",
    com "api_publica_tjdft" como única exceção).
  - https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/ (exemplo
    real de request/response — confirma request `{"query": {"match":
    {"numeroProcesso": "<20 dígitos>"}}}` e os campos
    `_source.tribunal`, `_source.orgaoJulgador.{nome,codigo,
    codigoMunicipioIBGE}`).
  - https://datajud-wiki.cnj.jus.br/api-publica/acesso/ (autenticação via
    header `Authorization: APIKey <chave pública>` — a chave em si NUNCA é
    gravada neste código; ver DATAJUD_API_KEY abaixo).
  - Consulta real ao TJBA (processo 8000099-11.2026.8.05.0080, mesmo caso
    usado nos testes reais deste projeto) confirmou o formato acima em
    produção e que `orgaoJulgador.nome` do nível superior da resposta
    ("2ª VARA DE FEITOS DE REL DE CONS. CÍVEL E COMERCIAIS") não inclui a
    comarca — daí a necessidade da resolução separada via IBGE
    (codigoMunicipioIBGE 2932903 -> "Valença", confirmado contra
    https://servicodados.ibge.gov.br/api/v1/localidades/municipios/2932903,
    API pública do IBGE, sem autenticação).
  - Números de tribunal (TR) do segmento 8 (Justiça Estadual): Resolução
    CNJ nº 65/2008 — "as unidades federativas e o Distrito Federal, na
    ordem alfabética dos nomes dos Estados, recebem os códigos 01 a 27" —
    tabela abaixo construída a partir dessa regra e cruzada com os 27
    aliases reais listados na página de endpoints.

Escopo suportado (não adivinhado além disto — falha explícita, nunca
"chuta" um alias): segmento 8 (Justiça Estadual, 27 UFs), segmento 4
(Justiça Federal, TRF1-TRF6), segmento 3 (STJ). Demais segmentos
(Trabalho, Eleitoral, Militar) não têm o mapeamento TR->alias
verificado nesta implementação — falha explícita (fail closed) em vez de
supor a convenção.

API key: NUNCA gravada em código/Skill/fixture/teste (CLAUDE.md §18 +
instrução expressa desta correção) — mesmo a chave pública documentada
pelo DPJ/CNJ é tratada como configuração externa. Lida exclusivamente de
DATAJUD_API_KEY (variável de ambiente) ou passada explicitamente pelo
chamador. Obtenha a chave vigente em
https://datajud-wiki.cnj.jus.br/api-publica/acesso/.

Cache local simples (numero_processo -> resolução), para uso em massa —
nunca versionado (dados de processo, mesmo tratamento de CLAUDE.md §18-19
dado a outros dados sensíveis de caso deste projeto).

Uso programático:
    from datajud_client import resolver_juizo, JuizoResolutionError
    try:
        r = resolver_juizo("8000099-11.2026.8.05.0080")
    except JuizoResolutionError as e:
        ...  # fail-closed — e.motivo é a mensagem para o advogado

Uso via CLI (teste real isolado, sem gerar peça):
    python scripts/datajud_client.py --numero-processo 8000099-11.2026.8.05.0080
"""
import argparse
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"
IBGE_MUNICIPIO_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{codigo}"

_TIMEOUT_PADRAO = 10  # segundos, por requisição
_TENTATIVAS_PADRAO = 3  # 1 tentativa inicial + até 2 retries em falha transitória
_CACHE_PADRAO = Path(__file__).parent.parent / ".cache" / "datajud" / "juizo_cache.json"

# CNJ Resolução 65/2008: segmento 8 (Justiça Estadual), TR 01-27 na ordem
# alfabética do nome do Estado/Distrito Federal. Alias real confirmado
# contra datajud-wiki.cnj.jus.br/api-publica/endpoints/ (todos seguem
# "api_publica_tj<uf minúscula>", exceto o Distrito Federal).
_UF_POR_TR_ESTADUAL = {
    "01": "AC", "02": "AL", "03": "AP", "04": "AM", "05": "BA", "06": "CE",
    "07": "DF", "08": "ES", "09": "GO", "10": "MA", "11": "MT", "12": "MS",
    "13": "MG", "14": "PA", "15": "PB", "16": "PR", "17": "PE", "18": "PI",
    "19": "RJ", "20": "RN", "21": "RS", "22": "RO", "23": "RR", "24": "SC",
    "25": "SP", "26": "SE", "27": "TO",
}
_ALIAS_UF_ESPECIAL = {"DF": "tjdft"}  # demais: "tj" + uf.lower()

_ALIAS_SEGMENTO_3 = "api_publica_stj"  # segmento 3 = STJ, sem TR (único tribunal)
_TR_TRF_VALIDOS = {"01", "02", "03", "04", "05", "06"}  # segmento 4: TR = região do TRF


class JuizoResolutionError(Exception):
    """Fail-closed único desta camada — nunca presume JUIZO. `motivo` é a
    mensagem destinada ao advogado/operador (stage=juizo_datajud)."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


# --------------------------------------------------------------- normalização/alias
def normalizar_numero_processo(numero) -> str:
    """NNNNNNN-DD.AAAA.J.TR.OOOO -> 20 dígitos, sem pontuação. Aceita com
    ou sem pontuação (dígitos crus são só filtrados)."""
    digitos = re.sub(r"\D", "", str(numero))
    if len(digitos) != 20:
        raise JuizoResolutionError(
            f"NUMERO_PROCESSO não tem 20 dígitos após normalização (formato "
            f"CNJ esperado: NNNNNNN-DD.AAAA.J.TR.OOOO): {numero!r} -> "
            f"{digitos!r} ({len(digitos)} dígitos)")
    return digitos


def identificar_alias(numero_normalizado: str) -> str:
    """Deriva o alias DataJud a partir do segmento (posição 13) e do
    tribunal/TR (posições 14-15) do número CNJ normalizado. Fail-closed
    para qualquer combinação fora do escopo verificado (ver docstring do
    módulo) — nunca "chuta" um alias plausível."""
    segmento = numero_normalizado[13]
    tr = numero_normalizado[14:16]
    if segmento == "8":
        uf = _UF_POR_TR_ESTADUAL.get(tr)
        if uf is None:
            raise JuizoResolutionError(
                f"segmento 8 (Justiça Estadual) com código de tribunal (TR) "
                f"não reconhecido: {tr!r} — não é seguro derivar o alias "
                f"DataJud automaticamente.")
        return f"api_publica_{_ALIAS_UF_ESPECIAL.get(uf, f'tj{uf.lower()}')}"
    if segmento == "3":
        return _ALIAS_SEGMENTO_3
    if segmento == "4":
        if tr not in _TR_TRF_VALIDOS:
            raise JuizoResolutionError(
                f"segmento 4 (Justiça Federal) com código de região (TR) "
                f"não reconhecido: {tr!r}.")
        return f"api_publica_trf{int(tr)}"
    raise JuizoResolutionError(
        f"segmento de justiça {segmento!r} não suportado por esta "
        f"implementação (suportados: 3=STJ, 4=Justiça Federal, "
        f"8=Justiça Estadual) — identificação automática de {{JUIZO}} não "
        f"pode prosseguir para este processo; confirme manualmente com o "
        f"advogado.")


# --------------------------------------------------------------- cache local
def _carregar_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------- HTTP (stdlib só)
def _fazer_requisicao(req: urllib.request.Request, timeout: int, tentativas: int, nome_servico: str) -> dict:
    """POST/GET com retry limitado só para falha transitória (timeout,
    erro de conexão, HTTP 5xx) — erro 4xx (auth, not found, bad request)
    nunca é retentado, pois retry não resolve."""
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                bruto = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    bruto = gzip.decompress(bruto)
                return json.loads(bruto.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise JuizoResolutionError(f"{nome_servico} retornou HTTP {e.code}: {e.reason}")
            ultimo_erro = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            ultimo_erro = e
        if tentativa < tentativas:
            time.sleep(min(2 ** (tentativa - 1), 4))
    raise JuizoResolutionError(f"{nome_servico} indisponível após {tentativas} tentativa(s): {ultimo_erro}")


def _post_json(url: str, body: dict, headers: dict, timeout: int, tentativas: int, nome_servico: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    return _fazer_requisicao(req, timeout, tentativas, nome_servico)


def _get_json(url: str, timeout: int, tentativas: int, nome_servico: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    return _fazer_requisicao(req, timeout, tentativas, nome_servico)


# --------------------------------------------------------------- DataJud (órgão julgador)
def resolver_orgao_julgador(numero_processo, api_key: str = None, timeout: int = _TIMEOUT_PADRAO,
                             tentativas: int = _TENTATIVAS_PADRAO, cache_path=None) -> dict:
    """Consulta DataJud e retorna {numero_processo, tribunal,
    orgao_julgador_nome, orgao_julgador_codigo, codigo_municipio_ibge,
    data_consulta}. Fail-closed (JuizoResolutionError) se indisponível,
    processo não encontrado, múltiplos resultados incompatíveis, ou
    órgão julgador ausente na resposta. Nunca busca por texto/heurística
    — só o campo estruturado `_source.orgaoJulgador`."""
    numero_normalizado = normalizar_numero_processo(numero_processo)
    cache_path = Path(cache_path) if cache_path else _CACHE_PADRAO
    cache = _carregar_cache(cache_path)
    if numero_normalizado in cache and "orgao_julgador_nome" in cache[numero_normalizado]:
        return cache[numero_normalizado]

    api_key = api_key or os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        raise JuizoResolutionError(
            "DATAJUD_API_KEY não configurada (variável de ambiente) — "
            "obtenha a chave pública vigente em "
            "https://datajud-wiki.cnj.jus.br/api-publica/acesso/ e "
            "configure-a externamente; nunca grave a chave em código, "
            "Skill, fixture ou arquivo versionado.")

    alias = identificar_alias(numero_normalizado)
    url = f"{DATAJUD_BASE_URL}/{alias}/_search"
    headers = {"Authorization": f"APIKey {api_key}", "Content-Type": "application/json"}
    body = {
        "query": {"match": {"numeroProcesso": numero_normalizado}},
        "_source": ["numeroProcesso", "tribunal", "orgaoJulgador"],
    }
    resposta = _post_json(url, body, headers, timeout, tentativas, "DataJud")

    hits_wrap = resposta.get("hits", {}) if isinstance(resposta, dict) else {}
    hits = hits_wrap.get("hits", []) or []
    total = (hits_wrap.get("total") or {}).get("value", len(hits))
    if not total or not hits:
        raise JuizoResolutionError(
            f"processo {numero_normalizado} não encontrado no DataJud "
            f"({alias}) — não é seguro presumir a vara; confirme com o "
            f"advogado.")

    fontes = [h.get("_source", {}) or {} for h in hits]
    assinaturas = {json.dumps(f.get("orgaoJulgador"), sort_keys=True, ensure_ascii=False) for f in fontes}
    if len(assinaturas) > 1:
        raise JuizoResolutionError(
            f"processo {numero_normalizado} retornou múltiplos resultados "
            f"com órgãos julgadores incompatíveis no DataJud ({alias}) — "
            f"não é seguro identificar o juízo automaticamente; confirme "
            f"manualmente com o advogado.")

    fonte = fontes[0]
    orgao = fonte.get("orgaoJulgador") or {}
    nome = str(orgao.get("nome") or "").strip()
    if not nome:
        raise JuizoResolutionError(
            f"processo {numero_normalizado}: resposta do DataJud ({alias}) "
            f"não trouxe o nome do órgão julgador — não é seguro presumir "
            f"a vara; confirme manualmente com o advogado.")

    resultado = {
        "numero_processo": numero_normalizado,
        "tribunal": fonte.get("tribunal"),
        "orgao_julgador_nome": nome,
        "orgao_julgador_codigo": orgao.get("codigo"),
        "codigo_municipio_ibge": orgao.get("codigoMunicipioIBGE"),
        "data_consulta": datetime.now(timezone.utc).isoformat(),
    }
    cache[numero_normalizado] = resultado
    _salvar_cache(cache_path, cache)
    return resultado


# --------------------------------------------------------------- IBGE (comarca/município)
def resolver_municipio(codigo_ibge, timeout: int = _TIMEOUT_PADRAO,
                        tentativas: int = _TENTATIVAS_PADRAO, cache_path=None) -> str:
    """codigoMunicipioIBGE -> nome do município (API pública do IBGE, sem
    autenticação). Usado como comarca — correto para a grande maioria dos
    casos (comarca = nome do município-sede); limitação conhecida e
    documentada: não distingue comarcas que abrangem mais de um
    município. Fail-closed se o código estiver ausente ou o IBGE não
    retornar nome."""
    if not codigo_ibge:
        raise JuizoResolutionError(
            "código de município IBGE ausente na resposta do DataJud — "
            "comarca não pode ser confirmada automaticamente.")
    cache_path = Path(cache_path) if cache_path else _CACHE_PADRAO
    cache = _carregar_cache(cache_path)
    chave = f"ibge:{codigo_ibge}"
    if chave in cache:
        return cache[chave]["nome"]

    url = IBGE_MUNICIPIO_URL.format(codigo=codigo_ibge)
    resposta = _get_json(url, timeout, tentativas, "IBGE Localidades")
    nome = str((resposta or {}).get("nome") or "").strip()
    if not nome:
        raise JuizoResolutionError(f"IBGE não retornou nome para o código de município {codigo_ibge!r}.")
    cache[chave] = {"nome": nome, "codigo": codigo_ibge}
    _salvar_cache(cache_path, cache)
    return nome


# --------------------------------------------------------------- ponto de entrada único
def resolver_juizo(numero_processo, api_key: str = None, timeout: int = _TIMEOUT_PADRAO,
                    tentativas: int = _TENTATIVAS_PADRAO, cache_path=None) -> dict:
    """DataJud (órgão julgador) + IBGE (comarca) -> string institucional
    pronta para {{JUIZO}}: "AO JUÍZO DA <órgão julgador> DA COMARCA DE
    <comarca>", tudo em caixa alta. Fail-closed em qualquer etapa —
    nunca retorna um valor parcial/adivinhado.

    Regra documental (gate de aprovação da INV-JUIZO-DATAJUD): o campo
    `orgaoJulgador.nome` retornado pelo DataJud constitui a fonte de
    verdade da denominação da unidade judiciária. Este módulo não
    expande, corrige, reinterpreta ou substitui automaticamente
    abreviações ou a nomenclatura oficial retornada pela fonte — o único
    tratamento aplicado é `.upper()`, exigido pelo padrão institucional
    de caixa alta já vigente para todo o endereçamento da peça (mesma
    convenção de AUTOR/JUIZO desde a Etapa 5.3), nunca uma reescrita de
    conteúdo."""
    dados = resolver_orgao_julgador(numero_processo, api_key, timeout, tentativas, cache_path)
    comarca = resolver_municipio(dados.get("codigo_municipio_ibge"), timeout, tentativas, cache_path)
    resultado = dict(dados)
    resultado["comarca"] = comarca
    resultado["juizo"] = (
        f"AO JUÍZO DA {dados['orgao_julgador_nome'].strip().upper()} "
        f"DA COMARCA DE {comarca.upper()}"
    )
    return resultado


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numero-processo", required=True)
    ap.add_argument("--api-key", default=None, help="Se omitido, lê DATAJUD_API_KEY do ambiente.")
    args = ap.parse_args()

    try:
        numero_normalizado = normalizar_numero_processo(args.numero_processo)
        alias = identificar_alias(numero_normalizado)
        resultado = resolver_juizo(args.numero_processo, api_key=args.api_key)
    except JuizoResolutionError as e:
        print(f"FALHOU (fail-closed, stage=juizo_datajud): {e.motivo}")
        raise SystemExit(1)

    print(f"NUMERO_PROCESSO: {resultado['numero_processo']}")
    print(f"TRIBUNAL: {resultado['tribunal']}")
    print(f"ALIAS DATAJUD: {alias}")
    print(f"ORGAO_JULGADOR: {resultado['orgao_julgador_nome']}")
    print(f"COMARCA: {resultado['comarca']}")
    print(f"JUIZO FINAL: {resultado['juizo']}")


if __name__ == "__main__":
    main()
