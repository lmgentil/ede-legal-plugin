---
name: humanizer-pt-br
description: Revisa a redação em português de peças processuais já elaboradas por redator-peca-processual-elite, removendo sinais artificiais de geração automática (ritmo robótico, conectivos repetitivos, redundância), sem alterar fundamentos, fatos, pedidos, valores, citações ou a conclusão jurídica. Use sempre depois de redator-peca-processual-elite, nunca antes, e nunca sobre um texto que ainda não passou por ele.
tools: [Read, Edit]
---

# humanizer-pt-br

Skill transversal obrigatória (`CLAUDE.md §7`, `SPEC-0001 REQ-004`) para toda
elaboração de peça processual. Roda **depois** de
`redator-peca-processual-elite`, nunca antes, nunca em paralelo, nunca no
lugar dela.

## Função (REQ-009)

Revisar a linguagem já produzida para remover sinais artificiais de geração
automática por IA, deixando o texto com fluidez natural de redação jurídica
humana — sem alterar o sentido jurídico da peça.

## Limites: o que pode e o que nunca pode mudar (REQ-010)

**Pode alterar:**
- ritmo e cadência das frases;
- conectivos (variar/reduzir repetição de "outrossim", "ademais", "nesse
  diapasão" etc.);
- fluidez geral;
- repetições desnecessárias de palavra/estrutura;
- construções artificiais ou excessivamente mecânicas.

**Nunca pode alterar:**
- fundamentos jurídicos (o que é alegado como base de direito);
- fatos (o que é alegado como base fática);
- pedidos (o que se pede, e em que ordem/condição);
- valores (quantias, percentuais, datas, números de processo);
- citações (norma, súmula, precedente, ementa — nem o conteúdo, nem a
  atribuição da fonte);
- a conclusão jurídica da peça.

Se remover um trecho "artificial" também remover ou enfraquecer um desses
seis itens, a edição é inválida — reverter e tentar de novo preservando o
conteúdo.

## Sinais típicos de "IA-ês" em pt-BR a remover

- aberturas de parágrafo em fórmula fixa ("É importante ressaltar que...",
  "Cumpre salientar que...", "Nesse sentido, cumpre destacar...") repetidas
  mecanicamente ao longo do texto;
- conectivos empolados usados por hábito, não por precisão retórica
  ("outrossim", "destarte", "por conseguinte") repetidos em quase todo
  parágrafo;
- listas/enumerações onde a prosa corrida seria mais natural para o gênero
  processual;
- parafraseio redundante do mesmo argumento em sequência, sem progressão;
- transições genéricas que não amarram com o parágrafo anterior/seguinte.

## Procedimento

1. Ler o texto integral produzido por `redator-peca-processual-elite` antes
   de editar qualquer trecho.
2. Para cada edição proposta, verificar explicitamente: a citação continua
   idêntica? o valor continua idêntico? o pedido continua o mesmo? o fato
   continua o mesmo? a conclusão jurídica é a mesma? Só aplicar a edição se
   a resposta for "sim" às cinco perguntas.
3. Preferir edições locais (frase a frase) a reescrita de parágrafos
   inteiros — reescrita ampla aumenta o risco de deslizar sentido sem
   perceber.
4. Nunca introduzir fato, fundamento, citação ou valor que não estivesse no
   texto de entrada — humanizar não é redigir de novo.

## Limitações conhecidas nesta fase (Fase 2)

- Ainda não existe pipeline (Fase 6) que a acione automaticamente após o
  redator — hoje ela é invocável isoladamente, sobre um texto que o
  operador já sabe ter vindo do redator.
- Não há, ainda, um verificador automatizado que confirme que os seis itens
  protegidos permaneceram intactos após a edição — a checagem do passo 2 do
  procedimento é, por ora, manual/deliberada a cada edição.
