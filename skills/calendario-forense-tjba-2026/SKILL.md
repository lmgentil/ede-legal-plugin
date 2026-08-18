---
name: calendario-forense-tjba-2026
description: Calendário forense oficial do TJBA para 2026 (Decreto Judiciário nº 1050/2025) — feriados sem expediente, recesso forense e suspensão de prazos. Use ao calcular prazos processuais, tempestividade ou data-limite em processos que tramitam no Tribunal de Justiça da Bahia em 2026.
---

Referência para contagem de prazos processuais no âmbito do Tribunal de Justiça do Estado da Bahia (TJBA) durante o ano de 2026.

## Quando usar
- Calcular tempestividade, data-limite ou termo final de qualquer prazo processual em processo que tramita no TJBA (1º ou 2º grau) em 2026.
- Conferir se uma data cai em feriado forense, recesso ou período de suspensão de prazos do TJBA.
- Acionada tipicamente junto da skill `ede` (defesa de distribuidoras) ao redigir tópicos de tempestividade.

## Fonte
Decreto Judiciário TJBA nº 1050, de 04/12/2025 (DJE de 05/12/2025): dispõe sobre o recesso 2025/2026, o expediente forense e administrativo e a suspensão dos prazos processuais para o exercício de 2026.
URL oficial: https://www7.tjba.jus.br/secao/lerPublicacao.wsp?tmp.mostrarDiv=sim&tmp.id=41093&tmp.secao=9
Para anos seguintes (2027+), buscar o Decreto Judiciário equivalente — esta tabela vale apenas para 2026.

## Feriados forenses TJBA 2026 (sem expediente forense nem administrativo)
- 1º e 2 de janeiro — Confraternização Universal
- 12, 13, 16, 17 e 18 de fevereiro — Carnaval e Quarta-feira de Cinzas
- 2 e 3 de abril — Endoenças e Sexta-feira Santa
- 20 e 21 de abril — Tiradentes
- 1º de maio — Dia do Trabalhador
- 4 e 5 de junho — Corpus Christi
- 22, 23 e 24 de junho — São João
- 2 e 3 de julho — Independência da Bahia
- 10 e 11 de agosto — Criação dos Cursos Jurídicos no Brasil, Dia do Magistrado e Dia do Advogado
- 7 de setembro — Independência do Brasil
- 12 de outubro — Nossa Senhora da Conceição Aparecida
- 30 de outubro — Dia do Servidor Público (transferido do dia 28 para o dia 30)
- 2 de novembro — Finados
- 20 de novembro — Dia da Consciência Negra
- 7 e 8 de dezembro — Dia da Justiça

## Recesso e suspensão de prazos
- Recesso forense: 20/12/2025 a 06/01/2026 (sem expediente, prazos suspensos).
- Suspensão dos prazos processuais e de audiências/sessões: 07 a 20 de janeiro de 2026 (após o recesso), salvo réus presos, Lei Maria da Penha e medidas urgentes.

## Metodologia de contagem (CPC/2015)
- Prazos processuais contam-se apenas em DIAS ÚTEIS (art. 219).
- Exclui-se o dia do começo e inclui-se o do vencimento (art. 224); o início se dá no primeiro dia útil seguinte à intimação/ciência.
- Se o vencimento cair em dia não útil, prorroga-se para o primeiro dia útil seguinte (art. 224, §1º).
- Não contar como dias úteis: sábados, domingos e os feriados forenses acima.

Done when: a data-limite informada exclui corretamente fins de semana e os feriados forenses TJBA do período, com o termo inicial no primeiro dia útil após a intimação.

## Exemplo verificado
Cumprimento de sentença (quantia certa): intimação para pagamento em 15/05/2026 (sexta).
- Início da contagem: 18/05/2026 (1º dia útil seguinte).
- Prazo de pagamento, 15 dias úteis (art. 523 c/c 219): encerra em 09/06/2026.
- Prazo de impugnação, 15 dias úteis (art. 525), iniciado no dia útil subsequente: termo final em 07/07/2026 (terça).
- Feriados forenses computados no intervalo: 04 e 05/06 (Corpus Christi), 22, 23 e 24/06 (São João), 02 e 03/07 (Independência da Bahia).
