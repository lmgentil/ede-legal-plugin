#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_placeholder_semantics.py — regressão da validação semântica
de placeholders (Etapa 3, pós-diagnóstico forense do bug real de
paginação).

Mesmo padrão sem framework do resto do projeto: asserts +
`if __name__ == "__main__"`.

Uso:
  python tests/test_validate_placeholder_semantics.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from validate_placeholder_semantics import validar_semantica  # noqa: E402


# --------------------------------------------------------------- AUTOR
def test_autor_com_cpf_rejeitado():
    ok, erros = validar_semantica({"AUTOR": "Fulano de Tal, CPF 011.730.795-56"})
    assert not ok
    assert any("CPF" in e for e in erros)


def test_autor_com_qualificacao_rejeitado_bug_real():
    # Reproduz o padrão exato do bug real confirmado por diagnóstico
    # forense (dados fictícios aqui — nunca dados reais em teste).
    ok, erros = validar_semantica({
        "AUTOR": "Fulana de Tal, já qualificada nos autos, portadora do "
                 "CPF nº 011.730.795-56"})
    assert not ok
    assert any("qualificação" in e for e in erros)


def test_autor_simples_aceito():
    ok, erros = validar_semantica({"AUTOR": "MARIA JOSÉ DA CONCEIÇÃO SANTOS"})
    assert ok, erros


def test_autor_nome_longo_legitimo_nao_e_rejeitado_so_por_tamanho():
    # "Não bloquear apenas por comprimento absoluto — existem nomes
    # legitimamente longos" (instrução do gate).
    ok, erros = validar_semantica({
        "AUTOR": "MARIA DA CONCEIÇÃO DE OLIVEIRA PEREIRA ALMEIDA SANTOS DE JESUS"})
    assert ok, erros


# --------------------------------------------------------------- NUMERO_PROCESSO
def test_numero_processo_formato_cnj_valido_aceito():
    ok, erros = validar_semantica({"NUMERO_PROCESSO": "8000001-11.2026.8.05.0080"})
    assert ok, erros


def test_numero_processo_formato_invalido_rejeitado():
    ok, erros = validar_semantica({"NUMERO_PROCESSO": "processo qualquer sem formato"})
    assert not ok
    assert any("NUMERO_PROCESSO" in e for e in erros)


# --------------------------------------------------------------- VALOR_FRA
def test_valor_fra_monetario_aceito():
    ok, erros = validar_semantica({"VALOR_FRA": "R$ 4.328,17"})
    assert ok, erros


def test_valor_fra_sentinela_ausencia_aceita():
    ok, erros = validar_semantica({"VALOR_FRA": "NÃO INFORMADO NOS ELEMENTOS DISPONIBILIZADOS."})
    assert ok, erros


def test_valor_fra_sem_digito_nem_sentinela_rejeitado():
    ok, erros = validar_semantica({"VALOR_FRA": "valor a ser apurado depois"})
    assert not ok
    assert any("VALOR_FRA" in e for e in erros)


# --------------------------------------------------------------- LOCAL_DATA
def test_local_data_curto_aceito():
    ok, erros = validar_semantica({"LOCAL_DATA": "Salvador/BA, 10 de fevereiro de 2026."})
    assert ok, erros


def test_local_data_narrativo_rejeitado():
    ok, erros = validar_semantica({
        "LOCAL_DATA": "Salvador/BA. Diante do exposto, requer-se o "
                       "acolhimento integral dos pedidos. Termos em que pede "
                       "deferimento."})
    assert not ok
    assert any("LOCAL_DATA" in e for e in erros)


def test_local_data_fora_de_salvador_rejeitado():
    # Etapa 5.3 — regra institucional: local da peça é sempre Salvador,
    # independentemente da comarca do processo.
    ok, erros = validar_semantica({"LOCAL_DATA": "Feira de Santana/BA, 10 de fevereiro de 2026."})
    assert not ok
    assert any("Salvador" in e for e in erros)


# --------------------------------------------------------------- campos livres
def test_campos_narrativos_sem_conteudo_suspeito_nao_bloqueiam():
    # Texto narrativo/técnico livre sem meta-proveniência/marcador de TOI
    # passa normalmente (CLAUDE.md: nunca bloquear texto jurídico legítimo
    # por comprimento).
    ok, erros = validar_semantica({
        "REALIDADE_FATICA": "Texto longo qualquer, sem restrição semântica "
                             "específica " * 20})
    assert ok, erros


def test_dados_com_campo_sem_validador_especifico_passa():
    # FOTOS_DA_IRREGULARIADE é o único campo sem validador dedicado
    # (marcador textual fixo, sobrescrito pelo orquestrador de qualquer forma).
    ok, erros = validar_semantica({"FOTOS_DA_IRREGULARIADE": "qualquer coisa"})
    assert ok, erros


# --------------------------------------------------------------- SINOPSE_FATOS (INV-SINOPSE-ESTRITAMENTE-AUTORAL)
def test_sinopse_puramente_autoral_aceita():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora é titular da unidade consumidora. Em "
                          "14/11/2025 foi lavrado TOI apontando irregularidade "
                          "na medição. A autora nega a irregularidade e pede "
                          "a declaração de inexigibilidade do débito."})
    assert ok, erros


def test_sinopse_com_nao_comprovou_rejeitada():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora alega dano moral, mas não comprovou "
                          "qualquer abalo psicológico."})
    assert not ok
    assert any("SINOPSE_FATOS" in e for e in erros)


def test_sinopse_com_analise_comercial_da_re_rejeitada():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "Os documentos demonstram que a cobrança é legítima "
                          "e decorre de irregularidade real na medição."})
    assert not ok
    assert any("SINOPSE_FATOS" in e for e in erros)


def test_sinopse_com_conclusao_sobre_legitimidade_rejeitada():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora pede a declaração de inexigibilidade, "
                          "mas a cobrança é legítima e regular."})
    assert not ok


def test_sinopse_com_regularidade_da_atuacao_rejeitada():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora questiona o procedimento, sem prejuízo da "
                          "regularidade da atuação da concessionária."})
    assert not ok


def test_sinopse_objetiva_com_pedidos_aceita():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora narra ter recebido fatura de recuperação "
                          "de consumo após TOI. Requer a declaração de "
                          "inexigibilidade do débito e indenização por danos "
                          "morais no valor de R$ 10.000,00."})
    assert ok, erros


# --------------------------------------------------------------- JUIZO (Etapa 5.3)
def test_juizo_padrao_institucional_aceito():
    ok, erros = validar_semantica({
        "JUIZO": "AO JUÍZO DA VARA DOS FEITOS DE RELAÇÕES DE CONSUMO DA COMARCA DE VALENÇA"})
    assert ok, erros


def test_juizo_construcao_improvisada_rejeitada():
    ok, erros = validar_semantica({"JUIZO": "Vara Cível da Comarca de Valença/BA"})
    assert not ok
    assert any("JUIZO" in e for e in erros)


def test_juizo_sem_comarca_rejeitado():
    ok, erros = validar_semantica({"JUIZO": "AO JUÍZO DA VARA DOS FEITOS DE RELAÇÕES DE CONSUMO"})
    assert not ok


def test_juizo_minuscula_rejeitado():
    ok, erros = validar_semantica({
        "JUIZO": "Ao Juízo da Vara dos Feitos de Relações de Consumo da Comarca de Valença"})
    assert not ok


# INV-JUIZO-DATAJUD (correção pontual, achado real): órgão julgador real
# retornado pelo DataJud frequentemente traz número ordinal ("2ª Vara...")
# e nem sempre a palavra "Vara" — o indicador ordinal "ª"/"º" não deve
# disparar falso positivo de "não está em caixa alta", e a exigência
# rígida da palavra "VARA" foi removida (unidade real vem do DataJud).
def test_juizo_com_vara_numerada_do_datajud_aceito():
    ok, erros = validar_semantica({
        "JUIZO": "AO JUÍZO DA 2ª VARA DE FEITOS DE REL DE CONS. CÍVEL E COMERCIAIS DA COMARCA DE VALENÇA"})
    assert ok, erros


def test_juizo_unidade_sem_a_palavra_vara_aceito():
    ok, erros = validar_semantica({
        "JUIZO": "AO JUÍZO DA TURMA RECURSAL DA COMARCA DE SALVADOR"})
    assert ok, erros


# --------------------------------------------------------------- AUTOR caixa alta (Etapa 5.3)
def test_autor_minusculo_rejeitado():
    ok, erros = validar_semantica({"AUTOR": "Maria José da Conceição Santos"})
    assert not ok
    assert any("CAIXA ALTA" in e for e in erros)


def test_autor_caixa_alta_aceito():
    ok, erros = validar_semantica({"AUTOR": "MARIA JOSÉ DA CONCEIÇÃO SANTOS"})
    assert ok, erros


# --------------------------------------------------------------- meta-proveniência (Etapa 5.3, achado grave)
def test_tempestividade_com_meta_proveniencia_rejeitada():
    ok, erros = validar_semantica({
        "TEMPESTIVIDADE_CASO": "A citação da Ré nestes autos foi realizada em "
                                "29/07/2026, conforme informação processual "
                                "fornecida pelo advogado subscritor desta peça."})
    assert not ok
    assert any("TEMPESTIVIDADE_CASO" in e for e in erros)


def test_tempestividade_redigida_naturalmente_aceita():
    ok, erros = validar_semantica({
        "TEMPESTIVIDADE_CASO": "A Ré foi citada em 29/07/2026. Considerando o "
                                "prazo legal aplicável e a contagem em dias "
                                "úteis, a presente defesa é tempestiva."})
    assert ok, erros


def test_desenvolvimento_tecnico_com_meta_proveniencia_rejeitado():
    ok, erros = validar_semantica({
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "Conforme dados fornecidos, "
                                                    "a irregularidade consiste em..."})
    assert not ok


def test_pedidos_finais_com_referencia_ao_rag_rejeitado():
    ok, erros = validar_semantica({"PEDIDOS_FINAIS": "Conforme RAG, requer-se a improcedência."})
    assert not ok


# --------------------------------------------------------------- assinatura do TOI (Etapa 5.3 §11)
def test_irregularidade_com_mencao_a_assinatura_do_toi_rejeitada():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "A autora assinou o TOI no ato da inspeção."})
    assert not ok
    assert any("IRREGULARIDADE_ENCONTRADA" in e for e in erros)


def test_irregularidade_sem_mencao_a_assinatura_aceita():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "Ligação direta no ramal de entrada, "
                                      "constatada pelo TOI nº 12345."})
    assert ok, erros


# --------------------------------------------------------------- contrato atômico (Etapa 5.3-B §15-§18, §26)
def test_irregularidade_atomica_valida_aceita():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**"})
    assert ok, erros


def test_irregularidade_repetindo_prefixo_fixo_rejeitada():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "Na ocasião, foi constatada irregularidade do tipo "
                                      "desvio de energia antes do sistema de medição"})
    assert not ok
    assert any("IRREGULARIDADE_ENCONTRADA" in e for e in erros)


def test_irregularidade_repetindo_sufixo_fixo_rejeitada():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "desvio de energia antes do sistema de medição, "
                                      "circunstância que impedia o registro integral"})
    assert not ok
    assert any("IRREGULARIDADE_ENCONTRADA" in e for e in erros)


def test_irregularidade_caixa_alta_forcada_rejeitada():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**DESVIO DE ENERGIA ANTES DO SISTEMA DE MEDIÇÃO**"})
    assert not ok
    assert any("CAIXA ALTA" in e for e in erros)


def test_irregularidade_com_sigla_isolada_nao_e_bloqueada_pela_regra_de_caixa_alta():
    # sigla curta (ex.: "TOI") sozinha teria toda letra maiúscula, mas não
    # é o cenário real do achado (tipo inteiro em caixa alta) — o valor
    # típico mistura minúsculas com a sigla, o que já basta para não
    # disparar o "all(upper)" (regra deliberadamente simples, sem
    # heurística de reconhecimento de sigla — ver docstring do módulo).
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**fraude no TOI de inspeção**"})
    assert ok, erros


# --------------------------------------------------------------- INV-NAO-REPETICAO-FATICA (Etapa 5.5 §9-13, §26)
# Cenário do achado real: "desvio de energia antes do medidor" reaparecia
# quase palavra por palavra em REALIDADE_FATICA, IRREGULARIDADE_ENCONTRADA
# e DESENVOLVIMENTO_TECNICO. O backstop determinístico só cobre a
# repetição VERBATIM do rótulo atômico dentro de REALIDADE_FATICA — a
# paráfrase (palavras diferentes, mesmo fato) é comportamental (Skills),
# não bloqueada por código (§13/§26: vedado bloqueador de similaridade
# genérico, geraria falso positivo).
def test_redundancia_realidade_fatica_repetindo_rotulo_atomico_e_rejeitada():
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**",
        "REALIDADE_FATICA": "Os elementos técnicos confirmam desvio de energia "
                             "antes do sistema de medição na unidade consumidora.",
    })
    assert not ok
    assert any("INV-NAO-REPETICAO-FATICA" in e for e in erros)


def test_redundancia_realidade_fatica_abstrata_sem_rotulo_e_aceita():
    # Exemplo corrigido (Etapa 5.5 §9): REALIDADE_FATICA global/objetiva,
    # sem antecipar o tipo/detalhe técnico da irregularidade.
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**",
        "REALIDADE_FATICA": "A inspeção identificou irregularidade no sistema de "
                             "medição, dando origem ao procedimento de recuperação "
                             "de consumo documentado nos autos.",
    })
    assert ok, erros


def test_redundancia_realidade_fatica_com_palavras_diferentes_nao_e_bloqueada_por_codigo():
    # Paráfrase (mesmo fato, palavras diferentes) — fora do escopo do
    # backstop determinístico por decisão explícita (§13); controle real é
    # comportamental (Redator/Humanizer, skills/contestacao/SKILL.md).
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**desvio de energia antes do sistema de medição**",
        "REALIDADE_FATICA": "A perícia constatou captação irregular de energia "
                             "elétrica em ponto anterior ao equipamento de aferição "
                             "de consumo instalado na unidade.",
    })
    assert ok, erros


def test_redundancia_sem_irregularidade_encontrada_nao_bloqueia_realidade_fatica():
    ok, erros = validar_semantica({
        "REALIDADE_FATICA": "A inspeção identificou irregularidade no sistema de "
                             "medição, dando origem ao procedimento de recuperação "
                             "de consumo documentado nos autos."})
    assert ok, erros


def test_redundancia_irregularidade_curta_nao_gera_falso_positivo_generico():
    # rótulo curto (< 12 chars normalizados) fica de fora do backstop —
    # evita falso positivo em substrings triviais/curtas demais.
    ok, erros = validar_semantica({
        "IRREGULARIDADE_ENCONTRADA": "**fraude**",
        "REALIDADE_FATICA": "A Ré nega a fraude alegada pela autora e apresenta "
                             "os elementos técnicos que amparam a cobrança.",
    })
    assert ok, erros


# --------------------------------------------------------------- INV-CONTESTACAO-SEM-TRAVESSAO
# A. texto gerado contendo "—" é rejeitado.
def test_A_texto_com_travessao_e_rejeitado():
    ok, erros = validar_semantica({"SINOPSE_FATOS": "A autora alega dano — sem provas."})
    assert not ok
    assert any("SINOPSE_FATOS" in e and "travessão" in e for e in erros)


# B. travessão produzido pelo Redator é rejeitado (qualquer campo textual).
def test_B_travessao_estilo_redator_e_rejeitado():
    ok, erros = validar_semantica({
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE":
            "A irregularidade caracteriza-se por derivação anterior ao medidor — circunstância técnica objetiva."})
    assert not ok
    assert any("DESENVOLVIMENTO_TECNICO_IRREGULARIDADE" in e for e in erros)


# C. travessão introduzido pelo Humanizer (ex.: "para dar ritmo" a uma frase) é rejeitado.
def test_C_travessao_estilo_humanizer_e_rejeitado():
    ok, erros = validar_semantica({
        "PEDIDOS_FINAIS": "Requer a improcedência dos pedidos — e a condenação em custas."})
    assert not ok
    assert any("PEDIDOS_FINAIS" in e for e in erros)


# D/E/F. pontuação convencional passa.
def test_D_E_F_pontuacao_convencional_passa():
    ok, erros = validar_semantica({
        "SINOPSE_FATOS": "A autora alega dano, sem provas.",
        "REALIDADE_FATICA": "A irregularidade foi apurada; o TOI está nos autos.",
        "DESENVOLVIMENTO_TECNICO_IRREGULARIDADE": "A metodologia observa o seguinte: art. 595, III.",
    })
    assert ok, erros


# G. hífen legítimo (U+002D) não é confundido com travessão (U+2014).
def test_G_hifen_legitimo_nao_e_confundido_com_travessao():
    ok, erros = validar_semantica({
        "NUMERO_PROCESSO": "8000001-11.2026.8.05.0080",
        "SINOPSE_FATOS": "A ligação direta no ramal, tipo by-pass, foi constatada em campo.",
    })
    assert ok, erros


# H. conteúdo válido sem travessão continua gerando resultado positivo (sem abortar por esta regra).
def test_H_conteudo_valido_sem_travessao_nao_bloqueia():
    ok, erros = validar_semantica({
        "JUIZO": "AO JUÍZO DA VARA DOS FEITOS DE RELAÇÕES DE CONSUMO DA COMARCA DE SALVADOR",
        "AUTOR": "FULANO DE TAL",
        "LOCAL_DATA": "Salvador/BA, 1 de janeiro de 2026.",
    })
    assert ok, erros


def main():
    testes = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in testes:
        t()
        print(f"OK — {t.__name__}")
    print(f"\n{len(testes)}/{len(testes)} testes passaram.")


if __name__ == "__main__":
    main()
