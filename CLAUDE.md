# CLAUDE.md — EDE Legal Plugin

## 1. Projeto

Este repositório contém o **EDE Legal Plugin**, plugin jurídico para Claude Code destinado à elaboração assistida de peças processuais.

A primeira peça suportada é a **Contestação**, mas a arquitetura deve permanecer extensível para outros tipos de peças.

A especificação arquitetural vigente está em:

`docs/specs/SPEC-0001.md`

Antes de realizar alterações estruturais, leia a SPEC e os ADRs aplicáveis.

---

## 2. Hierarquia documental

Para decisões de implementação, observe:

1. `CLAUDE.md` — regras operacionais permanentes;
2. SPEC vigente — requisitos do sistema;
3. ADRs aceitos — decisões arquiteturais;
4. `SKILL.md` — comportamento especializado;
5. código e testes existentes.

Se houver conflito relevante entre esses documentos, não escolha silenciosamente uma interpretação.

Identifique e reporte a divergência.

---

## 3. Regra fundamental

Não transforme o projeto em um gerador monolítico de Contestação.

A arquitetura deve permanecer:

```text
Core
├── Skills processuais
├── Skills transversais
├── Templates
├── RAG jurídico
├── Validação
├── Renderização
└── Atualização
```

Contestação é apenas o primeiro módulo processual.

---

## 4. Desenvolvimento por fases

A implementação da `SPEC-0001` é controlada por gates.

Não avance automaticamente entre fases.

Quando autorizado a executar determinada fase:

1. implemente somente aquela fase;
2. execute os testes aplicáveis;
3. valide os critérios de aceite;
4. documente alterações relevantes;
5. informe pendências;
6. pare ao concluir.

Não inicie a fase seguinte sem autorização explícita.

---

## 5. Antes de modificar código

Antes de qualquer alteração relevante:

1. inspecione os arquivos relacionados;
2. identifique implementação existente;
3. verifique testes existentes;
4. consulte SPEC e ADRs relacionados;
5. preserve comportamento funcional não relacionado.

Não sobrescreva implementação funcional sem compreender sua finalidade.

---

## 6. Alterações arquiteturais

Não introduza silenciosamente decisões arquiteturais novas.

Quando uma alteração representar decisão arquitetural relevante:

* identifique a necessidade;
* verifique ADR existente;
* proponha atualização ou novo ADR;
* registre consequências.

Código não deve se tornar arquitetura por acidente.

---

## 7. Skills obrigatórias

Toda elaboração de peça processual deverá utilizar:

`redator-peca-processual-elite`

e:

`humanizer-pt-br`

Para Contestação, essas dependências são obrigatórias.

---

## 8. Tempestividade

Toda análise de tempestividade relativa ao TJBA em 2026 deverá utilizar:

`calendario-forense-tjba-2026`

Não declare tempestividade sem dados suficientes.

Não invente:

* data de publicação;
* data de ciência;
* feriado;
* suspensão;
* termo inicial;
* termo final.

Quando os dados forem insuficientes, sinalize a pendência.

---

## 9. Integridade jurídica

Nunca invente:

* dispositivo legal;
* artigo;
* resolução;
* súmula;
* enunciado;
* precedente;
* número processual;
* ementa;
* tese jurisprudencial;
* conteúdo de decisão.

Sempre que houver fonte disponível no RAG, prefira o conteúdo recuperado e verificável à memória do modelo.

---

## 10. RAG jurídico

O RAG é a camada de conhecimento jurídico do projeto.

As Skills não devem conter cópias extensas da legislação.

Fluxo esperado:

```text
Skill
  ↓
consulta jurídica
  ↓
RAG
  ↓
busca lexical + vetorial
  ↓
reranking
  ↓
fontes recuperadas
  ↓
validação
  ↓
redação
```

Mantenha o RAG desacoplado das Skills.

---

## 11. Separação fato × direito

Nunca misture:

`FATOS DO PROCESSO`

com:

`CONHECIMENTO JURÍDICO`

Fatos devem derivar dos documentos ou de informação expressamente fornecida pelo advogado.

Conhecimento jurídico deve derivar das fontes jurídicas disponíveis.

O RAG não é fonte de fatos processuais.

---

## 12. Regra anti-hallucination

Uma afirmação jurídica específica que dependa de fonte deve ser verificável.

Para citações:

```text
citação proposta
      ↓
fonte encontrada?
      ↓
SIM → validar
NÃO → pesquisar novamente
      ↓
continua sem fonte?
      ↓
não utilizar como citação confirmada
```

Nunca complete uma referência jurídica por plausibilidade.

---

## 13. Template oficial

O template institucional da Contestação é protegido.

Arquivo esperado:

`templates/contestacao/modelo-oficial.docx`

Todo conteúdo que não seja placeholder autorizado ou seção condicional mapeada deve permanecer intocado.

---

## 14. Placeholders autorizados

Lista real, auditada diretamente em `templates/contestacao/modelo-oficial.docx`
(Fase 3) — substitui a lista hipotética original desta seção; ver
`docs/specs/SPEC-0001.md REQ-014` para a justificativa da divergência:

```text
{{JUIZO}}
{{NUMERO_PROCESSO}}
{{AUTOR}}
{{TEMPESTIVIDADE_CASO}}
{{SINOPSE_FATOS}}
{{REALIDADE_FATICA}}
{{IRREGULARIDADE_ENCONTRADA}}
{{DESENVOLVIMENTO_TECNICO_IRREGULARIDADE}}
{{FOTOS_DA_IRREGULARIADE}}
{{ARGUMENTACAO_EVOLUCAO_DE_CONSUMO_FIXA}}
{{VALOR_FRA}}
{{PEDIDOS_FINAIS}}
{{LOCAL_DATA}}
```

Não crie novos placeholders silenciosamente.

Alteração do contrato de placeholders exige atualização do schema e, quando aplicável, da SPEC.

---

## 15. Template Lock

Nunca contorne o Template Lock para fazer uma geração "funcionar".

Se a validação estrutural falhar:

**a geração deve falhar.**

Não liberar DOCX final como válido quando houver alteração não autorizada.

---

## 16. Manipulação de DOCX

Não reconstruir o documento inteiro quando o objetivo for preencher o template.

Preserve, sempre que tecnicamente aplicável:

* estilos;
* runs;
* fontes;
* cabeçalhos;
* rodapés;
* tabelas;
* imagens;
* hyperlinks;
* margens;
* espaçamento;
* elementos institucionais.

Sempre trabalhar sobre cópia.

Nunca sobrescrever o template mestre durante a geração de uma peça.

---

## 17. Fail Closed

Em matéria jurídica ou documental, prefira falhar explicitamente a gerar resultado silenciosamente incorreto.

Exemplos:

```text
fonte jurídica não validada
→ não inventar

tempestividade inconclusiva
→ sinalizar

placeholder ausente
→ falhar

template alterado indevidamente
→ falhar

documento processual ilegível
→ sinalizar
```

---

## 18. Segurança

Este projeto poderá possuir repositório público.

Nunca versionar:

* `.env`;
* API keys;
* tokens;
* senhas;
* credenciais;
* documentos reais de clientes;
* processos sigilosos;
* dados pessoais desnecessários;
* secrets;
* arquivos locais de trabalho.

Use `.env.example` apenas com nomes de variáveis e valores fictícios.

---

## 19. Workspace

Documentos processuais utilizados durante elaboração de peças devem permanecer fora do versionamento.

Diretórios locais de trabalho devem constar no `.gitignore`.

---

## 20. Dependências

Não adicione biblioteca sem necessidade concreta.

Antes de adicionar dependência, considere:

* necessidade;
* manutenção;
* licença;
* segurança;
* estabilidade;
* peso;
* alternativa já disponível.

---

## 21. Testes

Não considere uma implementação concluída apenas porque o código foi escrito.

Execute os testes aplicáveis.

Nunca:

* esconda teste falhando;
* remova teste apenas para obter verde;
* enfraqueça assertion sem justificativa;
* altere fixture para mascarar regressão.

Corrija a causa da falha.

---

## 22. Regressões

Antes de concluir uma fase:

1. execute os testes novos;
2. execute testes relacionados;
3. execute a suíte completa quando razoável;
4. informe qualquer falha preexistente separadamente.

---

## 23. Commits

Prefira commits pequenos e semanticamente coerentes.

Um commit deve representar uma unidade lógica de mudança.

Evite misturar:

* feature;
* refatoração não relacionada;
* documentação não relacionada;
* correções oportunistas.

---

## 24. Git

Não execute operações destrutivas sem autorização explícita.

Evite especialmente:

```text
git reset --hard
git clean -fd
git push --force
```

Não descarte alterações locais desconhecidas.

Antes de operações relevantes, consulte `git status`.

---

## 25. Atualização

O mecanismo de atualização deverá preservar configurações locais.

A experiência desejada é equivalente a:

`/updateEde`

O advogado usuário do plugin não deverá precisar conhecer Git para atualizar a instalação.

---

## 26. Compatibilidade com Claude Code

Não invente:

* comandos;
* hooks;
* propriedades de manifest;
* APIs;
* mecanismos de plugin;
* comportamento de marketplace;
* sintaxe MCP.

Quando a implementação depender do comportamento atual do Claude Code, consulte a documentação oficial vigente.

---

## 27. Expansão futura

Novos tipos de peça deverão reutilizar os componentes transversais.

Exemplo esperado:

```text
skills/
├── contestacao/
├── recurso-inominado/
├── embargos-de-declaracao/
└── ...
```

e:

```text
templates/
├── contestacao/
├── recurso-inominado/
├── embargos-de-declaracao/
└── ...
```

Não duplique o Core para implementar nova peça.

---

## 28. Critério de conclusão de tarefa

Antes de declarar uma tarefa concluída, informe:

1. o que foi implementado;
2. arquivos criados;
3. arquivos modificados;
4. testes executados;
5. resultado dos testes;
6. requisitos da SPEC atendidos;
7. pendências conhecidas;
8. riscos remanescentes.

Não declare "concluído" quando houver erro conhecido relevante.

---

## 29. Regra de escopo

Quando receber:

`Implemente a Fase N`

isso significa:

**implementar somente a Fase N.**

Não utilizar a autorização como permissão genérica para implementar fases subsequentes.

---

## 30. Fonte normativa do projeto

A SPEC vigente define os requisitos.

Os ADRs registram decisões arquiteturais.

As Skills definem comportamentos especializados.

O `CLAUDE.md` estabelece as regras permanentes de trabalho do agente.

Preserve essa separação durante toda a evolução do projeto.
