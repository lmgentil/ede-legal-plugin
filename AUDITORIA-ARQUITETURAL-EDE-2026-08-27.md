# AUDITORIA ARQUITETURAL EDE — ESTADO ATUAL

**Data da auditoria:** 27/08/2026  
**Modo:** somente leitura / auditoria profunda

## 1. Executive Summary

1. A arquitetura documental da Contestação está tecnicamente sólida, modular e fortemente fail-closed.
2. O pipeline real executa contexto institucional → fatos → tempestividade → estratégia → blocos → RAG/validação → placeholders/DataJud → zonas → renumeração → Template Lock → DOCX.
3. A suíte principal passou integralmente: **568 testes aprovados**, sem falhas, em 7m16s.
4. O template privado local foi efetivamente exercitado; existe fora do Git, com SHA-256 `10FAB6F59A937390B28B66C053892086B7F464D2AD21AB34A1C15AB5825A46C6`.
5. A proteção do texto institucional é real, não apenas documental: escrita generativa fica confinada a 13 placeholders e uma zona catalogada.
6. A arquitetura de zonas é genérica o suficiente para múltiplas zonas; a primeira zona não está hardcoded no motor.
7. A numeração dinâmica está implementada e testada. A `PEND-005` continua válida apenas quanto à migração futura para lista multinível nativa do Word.
8. `PEND-006` está contraditória: a tabela a marca aberta, mas a seção detalhada a declara resolvida.
9. A portabilidade da Contestação depende fortemente de `CLAUDE_PLUGIN_ROOT`, apesar de evidência prática de que essa variável não chega de forma confiável ao Bash disparado pela Skill.
10. A compatibilidade com Claude Code é forte; com Cowork continua **não homologada E2E**.
11. `/atualizar-ede` foi corretamente reduzida a verificador puro de versão, mas ainda contém uma afirmação histórica desatualizada de que não existe Release.
12. Git, tag, Release e versão estão sincronizados em `0.10.1`.
13. O maior risco técnico atual é o RAG: `svd.joblib` tem aproximadamente 81 MB e os artefatos foram gerados com scikit-learn 1.7.2, mas carregados com 1.9.0.
14. O projeto EDE MCP existe e implementa as três tools MCP-1, mas ainda é um protótipo não versionado, não implantável e com manifesto fictício.
15. A integração MCP deve começar apenas por metadados públicos de baixa sensibilidade; DataJud e RAG vêm depois, com controles próprios.

## 2. Estado Git/Release

| Item | Estado comprovado |
|---|---|
| Branch | `main` |
| HEAD | `69d8a4381c23154cc7efcbee4e2afa1f2951b1e2` |
| `origin/main` após fetch | Mesmo commit |
| Commits locais não publicados | Nenhum |
| Commits remotos não incorporados | Nenhum |
| Working tree | Não literalmente limpa: `.claude/` e `AGENTS.md` não rastreados |
| Versão | `0.10.1` em `VERSION` e `.claude-plugin/plugin.json` |
| Tag | `v0.10.1`, apontando para o HEAD |
| Release | `v0.10.1`, publicada, não draft e não prerelease |
| Release atual | [EDE Legal Plugin 0.10.1](https://github.com/lmgentil/ede-legal-plugin/releases/tag/v0.10.1) |
| Código posterior ao bump `0.10.0` | Sim: transformação de `/atualizar-ede`; corretamente absorvida pelo bump `0.10.1` |
| Código funcional posterior ao bump `0.10.1` | Não |
| Mesmo SemVer representando releases diferentes | Não comprovado |
| Classificação | **OK**, sem dívida de release no HEAD |

Há 30 commits recentes inspecionados; aproximadamente 14 alteram materialmente a arquitetura atual da Contestação, distribuição ou atualização.

## 3. Mapa arquitetural atual

| Subsistema | Status | Evidência/síntese |
|---|---|---|
| A. Orquestração | **PARCIAL** | Fluxo completo documentado em `skills/contestacao/SKILL.md`, mas Skills são coordenadas pelo agente, não por runtime transacional |
| B. Estrategista | **ESTÁVEL** | Obrigatório e anterior à redação; presença validada por `estrategia.md` em `scripts/gerar_contestacao.py` |
| C. Redator | **PARCIAL** | Contrato robusto, porém cumprimento é majoritariamente comportamental |
| D. Humanizer | **PARCIAL** | Limites claros; não há runtime que prove semanticamente que não alterou estratégia |
| E. Tempestividade | **ESTÁVEL** | Cálculo determinístico, prosa separada da memória técnica e fail-closed |
| F. DataJud/JUIZO | **ESTÁVEL localmente** | Alias, cache, IBGE, autenticação e falhas cobertos por 23 testes |
| G. Blocos | **ESTÁVEL** | Catálogo único e motor determinístico |
| H. Gates humanos | **PARCIAL** | Semântica correta; interação depende de `AskUserQuestion` do host |
| I. Zonas | **ESTÁVEL** | Uma zona, catálogo genérico, proveniência e aritmética fortes |
| J. Modelo como fonte primária | **ESTÁVEL** | Contexto extraído do DOCX real como primeira etapa |
| K. Placeholders | **ESTÁVEL** | 13 oficiais, schema/template testados |
| L. Dano moral pretendido | **ESTÁVEL** | Obrigatoriedade condicional e validação monetária |
| M. Contexto institucional | **ESTÁVEL** | Extração somente leitura e hash da execução |
| N. Numeração dinâmica | **ESTÁVEL** | Níveis 2/3 recalculados; nível 1 preservado |
| O. Template Engine | **ESTÁVEL** | Substituição confinada e cor `FF0000` |
| P. Block Engine | **ESTÁVEL** | Blocos, zonas, estados e catálogo validados bidirecionalmente |
| Q. Template Lock | **ESTÁVEL** | Comparação byte a byte, com transformação autorizada recomposta |
| R. RAG | **PARCIAL** | Funciona, mas pesado e com incompatibilidade de versões serializadas |
| S. Atualização | **ESTÁVEL** | Verificador puro via GitHub Releases |
| T. Marketplace | **PARCIAL** | Code funciona; sincronização pessoal Cowork é não confiável |
| U. Testes | **ESTÁVEL/PARCIAL** | 568 aprovados; ainda há garantias textuais de Skill sem E2E do host |
| V. Segurança | **PARCIAL** | Nenhum secret privado detectado; dados processuais exigem disciplina |
| W. Versionamento | **ESTÁVEL** | `0.10.1`, tag e Release sincronizados |
| X. Runtime | **PARCIAL** | Python/toolkit/RAG pesados e sensíveis a versões |
| Y. Claude Code | **ESTÁVEL COM RESTRIÇÕES** | Melhor ambiente atual; fragilidade residual de root/toolkit |
| Z. Cowork | **EXPERIMENTAL** | Sem E2E real e marketplace pessoal stale |

## 4. Invariantes

### Invariantes-base

| ID | Descrição | Implementação/teste | Vigência |
|---|---|---|---|
| INV-001 | Modularidade | Estrutura separada em skills, RAG, validação e engines | Vigente |
| INV-002 | Integridade documental | Template Lock e motores DOCX | Vigente |
| INV-003 | Fonte jurídica verificável | RAG + validação de citações | Vigente |
| INV-004 | Não invenção jurídica | Validação e contratos comportamentais | Vigente |
| INV-005 | Separação fatos/direito | `fatos.json`, estratégia e RAG separados | Vigente |
| INV-006 | Fail-closed | Amplamente implementada e testada | Vigente |
| INV-007 | Extensibilidade | Core não está fundido à Contestação | Vigente |
| INV-008 | Conteúdo protegido | Schema e Template Lock | Vigente |
| INV-009 | Alteração restrita | Apenas placeholders/zonas | Vigente |
| INV-010 | Corpus fora das Skills | RAG separado | Vigente |
| INV-011 | Norma revogada | Camada de estado temporal | Vigente |
| INV-012 | Template como base | Cópia de trabalho; mestre somente leitura | Vigente |
| INV-013 | Configuração local | Parcial; root do plugin continua frágil | Vigente, implementação incompleta |
| INV-014 | Componentes compartilhados | Redator/Humanizer transversais | Vigente |
| INV-015 | Ausência do template afeta só geração | Instalação aceita asset externo ausente | Vigente |

### Invariantes especializadas

| ID | Implementada? | Testada? | Avaliação |
|---|---:|---:|---|
| INV-CONTESTACAO-ESTRATEGIA | Sim | Estrutural + pipeline | Sólida |
| INV-TEMPESTIVIDADE-MARCO | Sim | Comportamental | Sólida |
| INV-COMPOSICAO-BLOCOS | Sim | Comportamental/E2E | Sólida |
| INV-CONTESTACAO-ENTREGA-DOCX | Parcial | Majoritariamente textual | Depende do agente não encerrar cedo |
| INV-GATE-CONTESTACAO | Sim | Estrutural | Vigente |
| INV-PARAGRAFO-380 | Sim | Limites exatos | Sólida |
| INV-NAO-REDUNDANCIA | Comportamental | Backstop parcial | Não automatizável integralmente |
| INV-SINOPSE-ESTRITAMENTE-AUTORAL | Sim/parcial | Backstop lexical | Vigente |
| INV-RECONVENCAO-AUTORIZACAO | Sim | Motor + teste textual de interação | Host-dependent |
| INV-BLOCO-SUPORTE-FATICO | Parcial | Gates específicos | Controle semântico permanece na Skill |
| INV-GRATUIDADE-LINKED | Sim | Comportamental | Sólida |
| INV-CORTE-GATE-HUMANO | Sim | Motor + estrutural | Host-dependent |
| INV-NAO-REDUNDANCIA-NORMATIVA | Comportamental | Parcial | Vigente |
| INV-SEM-PESQUISA-JURISPRUDENCIAL | Sim | Textual/estrutural | Vigente |
| INV-PARAGRAFO-HERDA-TEMPLATE | Sim | DOCX real | Sólida |
| INV-SEM-TRAVESSAO | Sim | Backstop lexical | Sólida |
| INV-JUIZO-DATAJUD | Sim | 23 testes | Sólida localmente |
| INV-TEMPESTIVIDADE-PROCEDIMENTO-COMUM | Sim | Comportamental | Sólida |
| INV-NAO-REPETICAO-FATICA | Parcial | Sintoma grave apenas | Corretamente não tenta resolver semântica em Python |
| INV-VALOR-DANO-MORAL-DOCUMENTAL | Sim | Comportamental | Sólida |
| INV-NUMERACAO-DINAMICA | Sim | Unidade + template real | Sólida |
| INV-MODELO-FONTE-PRIMARIA | Sim | Integração/template real | Sólida |
| INV-ZONA-COMPLEMENTACAO | Sim | 95 testes relacionados | Sólida |
| INV-CONTINUIDADE-ZONA | Sim | Template real | Sólida |

Os `REQ-001` a `REQ-047` estão formalmente presentes. A lacuna material continua sendo `REQ-018` na parte de jurisprudência, registrada como `PEND-002`.

## 5. Pendências reconciliadas

### Resolvidas

| Pendência | Estado real | Ação |
|---|---|---|
| PEND-004 — licença/distribuição | Resolvida | Nenhuma |
| PEND-006 — fronteira de `EVOLUCAO_CONSUMO` | Resolvida por eliminação do placeholder variável | Corrigir a tabela inicial |
| Template Lock | Implementado/testado | Remover menções históricas de abertura |
| Renumeração dinâmica | Implementada | Não confundir com PEND-005 |
| Entrega contínua até DOCX | Implementada no contrato; runtime de host ainda não E2E | Manter ressalva |
| Modelo institucional fonte primária | Implementado | Nenhuma |
| Zonas | Implementadas | Nenhuma |
| DataJud | Implementado localmente | Avaliar futura migração |
| `validate_placeholders.py` | Continua útil como validador standalone | Não remover agora |

### Ainda abertas

| Pendência | Estado |
|---|---|
| PEND-001 — fotos embutidas | `DEFERRED`; marcador manual é decisão vigente |
| PEND-002 — jurisprudência no RAG | Aberta, mas não deve afetar a Contestação atual |
| PEND-003 — `svd.joblib` aproximadamente 81 MB | Aberta e confirmada |
| PEND-005 — lista multinível nativa Word | Aberta, cosmética; numeração literal já é recalculada |
| Cowork E2E | Aberta e não formalizada como PEND |
| Compatibilidade dos artefatos sklearn | Aberta e não formalizada |
| MCP deployment/integrador real | Aberta |

### Superadas

- Self-update via `/plugin update`.
- Marketplace como fonte de verdade da versão instalada.
- Gate universal por `CLAUDE_PLUGIN_ROOT` para `/atualizar-ede`.
- Exigência de ZIP anexado para uma Release ser considerada válida.
- Inclusão automática do bloco de corte somente porque houve corte.
- Reconvenção decidida pelo estrategista.
- Zona como bloco ou placeholder.
- Pesquisa jurisprudencial condicionada ao futuro fechamento de `PEND-002`.

### Documentação desatualizada

- `docs/PENDENCIAS.md` marca `PEND-006` como aberta na tabela, mas sua seção detalhada a declara resolvida.
- `skills/atualizar-ede/SKILL.md` ainda diz que `releases/latest` responde 404 “hoje”; hoje há Release `v0.10.1`.
- O CHANGELOG preserva corretamente história, mas não deve ser lido como arquitetura vigente sem contexto temporal.
- README ainda pode sugerir que atualizar o marketplace pessoal resolve sincronização no Cowork.

## 6. Contradições encontradas

1. `PEND-006`: aberta na tabela, resolvida no corpo.
2. `/atualizar-ede`: contrato atual correto, exemplo factual sobre inexistência de Release já envelheceu.
3. `CLAUDE_PLUGIN_ROOT`: Contestação exige a variável em `skills/contestacao/SKILL.md`, enquanto a experiência real indica que o Bash disparado pela Skill pode não recebê-la.
4. `tests/test_contestacao_skill_caminhos.py` valida textualmente a arquitetura de `CLAUDE_PLUGIN_ROOT`; não prova que o host a fornece.
5. A descrição pública do plugin destaca Claude Code; README oferece Cowork, mas não há homologação E2E equivalente.
6. O RAG passa nos testes, mas a própria execução emite `InconsistentVersionWarning`; testes verdes não eliminam risco de persistência incompatível.

## 7. Dívida técnica

| Item | Classificação | Risco |
|---|---|---|
| `svd.joblib` aproximadamente 81 MB | REAVALIAR/MIGRAR | Clone, instalação e Cowork |
| Artefatos sklearn 1.7.2 carregados em 1.9.0 | P0 técnico | Resultado potencialmente incorreto |
| Dependência de `CLAUDE_PLUGIN_ROOT` na Skill | REAVALIAR | Falha em host/camada |
| Toolkit DOCX descoberto por busca de caminhos | REAVALIAR | Portabilidade |
| `validate_template.py` e `validate_placeholders.py` standalone | MANTER | Diagnóstico independente útil |
| `render_docx.py` | MANTER/REAVALIAR | Papel auxiliar; não é o pipeline principal |
| Documentação histórica muito extensa | REAVALIAR | Dificulta distinguir vigente de superado |
| Fixtures históricas | MANTER | Cobrem regressões reais |
| Cache DataJud local | MANTER localmente | Evita rede, mas requer política de retenção |
| `.egg-info` e `__pycache__` no EDE MCP | REMOVER do futuro Git | Artefatos de build/runtime |
| MCP sem Git | BLOQUEADOR de governança | Sem histórico, rollback ou release auditável |

## 8. Qualidade da suíte de testes

Resultado principal:

```text
568 passed, 32 warnings, 436.21s
```

Distribuição aproximada por tema:

- 95 testes de zonas;
- 61 com foco DOCX;
- 56 de template;
- 51 relacionados a Skills;
- 48 de RAG;
- 31 E2E;
- 24 de validação jurídica;
- 23 DataJud;
- 23 tempestividade;
- 22 contexto institucional.

Pontos fortes:

- Template real exercitado.
- Gates, blocos, zonas, aritmética, proveniência e Template Lock têm testes comportamentais.
- RAG, DataJud e E2E possuem testes reais com dependências controladas.
- Gold set é local e determinístico.

Limitações:

- Muitos testes de Skills verificam strings e presença de instruções, não execução pelo Claude.
- Não existe E2E real do Cowork.
- DataJud de produção não é chamado pela suíte, corretamente evitando flaky/network.
- A suíte inteira leva mais de sete minutos e não está segmentada.
- Os avisos de incompatibilidade sklearn são materialmente relevantes.
- Há falsa sensação de cobertura apenas onde “Skill escrita corretamente” é tratada como equivalente a “host executou corretamente”.

CI recomendada:

1. `unit/structural` rápido;
2. `DOCX real local/private`;
3. `RAG pesado`;
4. `network smoke` opt-in;
5. `Code E2E`;
6. `Cowork homologation` manual/versionada.

## 9. Compatibilidade Claude Code

**Status: SIM COM RESTRIÇÕES.**

Funciona bem:

- Skills;
- Bash/Python;
- filesystem local;
- RAG;
- DataJud;
- toolkit DOCX;
- template privado;
- gates humanos;
- entrega DOCX.

Fragilidades:

- `CLAUDE_PLUGIN_ROOT` não deve ser presumido em todas as camadas;
- descoberta do toolkit DOCX depende do ambiente;
- instalação precisa do template privado local;
- artefatos pesados do RAG;
- não há teste do harness real garantindo o encadeamento das três Skills.

## 10. Compatibilidade Cowork

**Status: EXPERIMENTAL / NÃO HOMOLOGADA.**

| Capacidade | Situação |
|---|---|
| Skills | Provável |
| Bash/Python | Dependente do ambiente disponibilizado |
| Filesystem | Diferente e menos previsível |
| `CLAUDE_PLUGIN_ROOT` | Não garantido |
| Marketplace pessoal | Confirmadamente pode permanecer stale |
| DOCX | Não provado E2E |
| DataJud | Não provado E2E |
| RAG pesado | Alto risco |
| Gates humanos | Semântica possível, execução não homologada |
| Entrega final | Não comprovada |
| MCP remoto | Caminho promissor, ainda não integrado |

Não deve ser anunciada compatibilidade plena antes de um caso real completo: upload/instalação → intake → gates → DataJud/RAG → DOCX final → validação visual.

## 11. Marketplace/distribuição

O marketplace pessoal stale é uma **limitação/bug de plataforma com risco operacional para o EDE**, não um bug do motor jurídico.

Estado:

- GitHub avançou;
- plugin sincronizado no Cowork permaneceu antigo;
- botão atualizar não resolveu;
- CLI informou sincronização via conta sem backing de marketplace.

Consequência: colaboradores podem acreditar que estão em `0.10.1` quando executam conteúdo antigo.

Recomendação:

- Release GitHub permanece fonte oficial.
- Cowork pessoal deve usar upload explícito do artefato versionado até haver mecanismo confiável.
- Mostrar versão instalada no início de operações críticas.
- Nunca usar “marketplace atualizado” como prova de conteúdo instalado.

## 12. Versionamento/releases

O fluxo atual está consistente:

```text
VERSION 0.10.1
      =
plugin.json 0.10.1
      =
Skill /atualizar-ede 0.10.1
      =
tag v0.10.1
      =
GitHub Release v0.10.1
      =
commit 69d8a43
```

Política futura recomendada:

1. Alteração funcional primeiro.
2. Suíte completa e teste real do template.
3. Bump único no final.
4. Tag imutável.
5. Release apontando exatamente para a tag.
6. Manifesto MCP atualizado no mesmo gate.
7. Nunca reutilizar SemVer.
8. Registrar hashes do plugin e template.
9. Publicar matriz de compatibilidade Code/Cowork.

## 13. Segurança

### Estado atual

- Nenhum secret privado conhecido foi detectado nos arquivos rastreados.
- `DATAJUD_API_KEY_PADRAO` é chave pública disponibilizada pelo CNJ, não credencial privada.
- Embuti-la permanece risco operacional de rotação/disponibilidade, não vazamento.
- O template privado está corretamente fora do Git.
- Testes verificam ausência de outras credenciais e DOCX rastreados.

### Dados por sensibilidade

| Classe | Dados | MCP v1 |
|---|---|---|
| Baixa | versão, Release, hash, template version | Permitido |
| Média | número CNJ | Somente após política LGPD/logs |
| Alta | fatos, documentos, CPF, dados de clientes | Não enviar no MCP v1 |

Controles futuros:

- TLS obrigatório;
- logs sem payload;
- retenção mínima;
- revogação de usuários;
- tokens individuais ou OAuth para múltiplos colaboradores;
- rate limit;
- trilha de versão das políticas;
- segregação entre telemetria operacional e conteúdo jurídico.

## 14. Arquitetura MCP atual

Projeto: `C:\Users\lmgen\Desktop\EDE MCP`.

Estado real:

- não é repositório Git;
- usa Python `>=3.11`;
- SDK `mcp[cli]>=2.1,<3`;
- transporte Streamable HTTP;
- Starlette/Uvicorn;
- bearer token estático;
- manifesto JSON carregado fail-closed;
- implementa exatamente:

```text
get_latest_plugin_version
get_latest_template_version
verify_template_hash
```

Problemas:

- manifesto informa plugin `0.1.0`, enquanto o EDE real é `0.10.1`;
- URLs são `example.invalid`;
- hash do template no manifesto não coincide com o template local auditado;
- não há deploy;
- não há integração do plugin;
- não há Git;
- testes não puderam ser coletados porque `starlette`/dependências não estão instaladas;
- não foram instaladas dependências, conforme proibição da auditoria.

Classificação: **protótipo MCP-1 tecnicamente coerente, ainda não operacional**.

## 15. Fronteira Plugin × MCP

| Componente | Destino recomendado |
|---|---|
| Versão/release do plugin | MCP |
| Versão/hash/download autorizado do template | Híbrido |
| Arquivo DOCX | Repositório de artefatos autenticado; não payload comum de tool |
| DataJud | Híbrido; migrar após controles LGPD |
| RAG normativo | MCP futuro |
| Estrategista | Local |
| Redator | Local |
| Humanizer | Local |
| Políticas institucionais críticas | Local versionada + manifesto remoto |
| Regras jurídicas/invariantes | Local, com versão/hash remoto |
| Composição DOCX | Local |
| Template Lock | Local |
| Numeração | Local |
| Blocos/zonas | Local |
| Gates humanos | Local |
| Documentos/fatos do processo | Local |
| Métricas anônimas de versão/saúde | MCP, se necessárias |

## 16. Skills × MCP

### Comparação

| Modelo | Avaliação |
|---|---|
| A. Skills integralmente locais | Mais auditável e resiliente; atualização mais lenta |
| B. Skills mínimas locais + políticas remotas | Risco elevado de mudança silenciosa e indisponibilidade |
| C. MCP retorna perfis versionados | Útil como complemento, desde que pinado e arquivado |

Recomendação: **A + elementos controlados de C**.

A Skill executável e as invariantes críticas devem continuar no plugin local. O MCP pode informar que existe uma versão nova e retornar metadados/perfis versionados, mas nunca substituir silenciosamente as instruções durante a elaboração.

Toda peça deveria registrar:

```text
plugin_version
skill_profile_version
template_version
template_sha256
rag_corpus_version
```

Isso permite reprodução, rollback e auditoria posterior.

## 17. Modelo Word × MCP

Arquitetura segura:

1. MCP informa `template_version`, `sha256`, assinatura e URL.
2. Arquivo fica em storage/release separado, não necessariamente servido pelo processo MCP.
3. Download é explícito e autenticado.
4. Verificação de hash e assinatura antes da instalação.
5. Atualização em arquivo temporário.
6. Validação estrutural completa.
7. Substituição atômica.
8. Backup da versão anterior.
9. Rollback disponível.
10. Nunca atualizar o template durante uma geração em andamento.

O Template Lock permanece local e obrigatório. O MCP não deve validar estrutura apenas por hash remoto.

## 18. DataJud × MCP

Recomendação: **migrar para MCP numa fase posterior, não na MCP-1**.

Benefícios:

- chave pública e endpoint atualizados centralmente;
- retry/cache centralizados;
- correções sem redistribuir plugin;
- menor dependência de runtime local.

Riscos:

- número CNJ deixa o ambiente local;
- logs podem revelar processos consultados;
- disponibilidade e latência passam a bloquear geração;
- necessidade de base legal, minimização e retenção.

Pré-condições:

- logs sem número CNJ;
- TLS;
- autenticação por usuário;
- cache com retenção definida;
- contrato de indisponibilidade fail-closed;
- DPIA/threat model;
- proibição de enviar documentos ou fatos junto da consulta.

## 19. RAG × MCP

### RAG local

Vantagens:

- confidencialidade;
- disponibilidade offline;
- corpus e resultado reproduzíveis.

Desvantagens:

- pacote pesado;
- sklearn/pyarrow/joblib;
- incompatibilidade de versões;
- baixa portabilidade Cowork;
- atualização exige redistribuição.

### RAG remoto

Vantagens:

- corpus central;
- plugin menor;
- atualização rápida;
- elimina dependências pesadas locais.

Desvantagens:

- latência/rede;
- versionamento obrigatório;
- risco de consultas revelarem estratégia;
- indisponibilidade;
- necessidade de auditabilidade dos resultados.

Recomendação: **RAG normativo remoto híbrido**, enviando apenas consultas jurídicas abstratas. Fatos do processo e documentos permanecem locais. Cada resultado deve trazer corpus version, source ID, hash e data de vigência.

## 20. Arquitetura-alvo recomendada

```text
┌─────────────────────────────────────────────────────────┐
│ EDE PLUGIN LOCAL                                        │
│                                                         │
│ Intake e documentos processuais                         │
│ Estratégia → gates humanos → Redator → Humanizer         │
│ Blocos → zonas → numeração → placeholders               │
│ Template Lock → renderização DOCX                       │
│ Registro das versões usadas                             │
└───────────────┬───────────────────────────┬─────────────┘
                │ metadados públicos        │ consultas abstratas
                ▼                           ▼
┌───────────────────────────┐   ┌─────────────────────────┐
│ EDE MCP — núcleo mínimo   │   │ EDE MCP — fases futuras│
│                           │   │                         │
│ plugin version/release    │   │ DataJud com controles  │
│ template version/hash     │   │ RAG normativo versionado│
│ manifests assinados       │   │ políticas/perfis pinados│
└───────────────┬───────────┘   └─────────────┬───────────┘
                │                             │
                ▼                             ▼
┌─────────────────────────────────────────────────────────┐
│ GITHUB + STORAGE DE ARTEFATOS                           │
│ código, tags, releases, manifestos, DOCX assinado       │
└─────────────────────────────────────────────────────────┘
```

Princípio central: **conteúdo processual e geração ficam locais; metadados públicos e corpus normativo podem ser centralizados progressivamente**.

## 21. Roadmap P0/P1/P2/P3

| Prioridade | Problema/ação | Esforço | Antes do MCP? | Decisão humana |
|---|---|---:|---:|---:|
| P0 | Regerar/pinar artefatos RAG com versão compatível de sklearn | Médio | Sim | Não |
| P0 | Colocar EDE MCP sob Git e substituir manifesto fictício | Baixo | Sim | Sim |
| P0 | Corrigir `PEND-006` e afirmação 404 de `/atualizar-ede` | Baixo | Sim | Não |
| P0 | Definir resolução de root independente de `CLAUDE_PLUGIN_ROOT` universal | Médio | Sim | Sim |
| P1 | Criar CI segmentada | Médio | Sim | Não |
| P1 | Homologar E2E real no Claude Code | Médio | Sim | Não |
| P1 | Homologar ou limitar formalmente Cowork | Alto | Sim | Sim |
| P1 | Sincronizar Release → manifesto MCP automaticamente | Médio | Sim | Sim |
| P1 | Assinar manifesto/template e definir rollback | Médio | Sim | Sim |
| P2 | Migrar metadados de versão/hash para MCP | Médio | Depois das P0 | Sim |
| P2 | Definir storage seguro do template | Médio | Durante MCP-1 | Sim |
| P2 | Reduzir pacote RAG ou externalizá-lo | Alto | Depois do MCP-1 | Sim |
| P2 | Instrumentar registro de versões em cada peça | Médio | Depois do MCP-1 | Sim |
| P3 | DataJud remoto | Alto | Depois | Sim/LGPD |
| P3 | RAG normativo remoto | Alto | Depois | Sim |
| P3 | Perfis de Skill versionados via MCP | Alto | Depois | Sim |
| P3 | Fotos embutidas | Médio | Independente | Sim |

## 22. Decisões que exigem aprovação do usuário

1. Se `CLAUDE_PLUGIN_ROOT` será substituído por mecanismo explícito de localização do pacote.
2. Se Cowork continuará sendo declarado suportado antes da homologação.
3. Onde hospedar o DOCX institucional.
4. Se o manifesto será assinado e com qual infraestrutura.
5. Se DataJud será local, remoto ou híbrido.
6. Se o RAG será retirado do pacote local.
7. Política de retenção/logs do futuro MCP.
8. Autenticação: bearer único interno ou OAuth por usuário.
9. Se perfis jurídicos remotos poderão participar da geração.
10. Política formal de rollback de Skill/template/corpus.

## 23. Coisas que NÃO devem ser alteradas

- Separação entre estrategista, redator e humanizer.
- Estratégia obrigatória antes da redação.
- Gates humanos de Reconvenção e corte.
- Template institucional como fonte primária.
- Regra “sem placeholder/zona, sem escrita generativa”.
- Template Lock local.
- Composição determinística de blocos e zonas.
- Numeração estrutural fora das Skills.
- Proveniência factual e jurídica.
- Fail-closed para estados indeterminados.
- Ausência do template privado no Git.
- Proibição de jurisprudência na Contestação atual.
- Documentos e fatos processuais locais no MCP-1.
- Preservação do valor documental, sem recálculo autônomo pela IA.

## 24. Veredito final

| Pergunta | Veredito |
|---|---|
| **ARQUITETURA ATUAL** | **AMARELA** |
| **PRONTA PARA INTEGRAÇÃO MCP** | **SIM COM PRÉ-CONDIÇÕES** |
| **PRONTA PARA DISTRIBUIÇÃO A COLABORADORES** | **SIM COM RESTRIÇÕES** |
| **PRONTA PARA PRODUÇÃO** | **SIM COM RESTRIÇÕES** |

A arquitetura jurídica e documental da Contestação é a parte mais madura do sistema. O amarelo decorre da camada operacional: portabilidade por `CLAUDE_PLUGIN_ROOT`, RAG serializado com versões divergentes, Cowork não homologado e MCP ainda sem Git, manifesto real ou deploy.

Durante a auditoria original, nenhum arquivo foi alterado. O estado da árvore ao encerramento daquela auditoria continha apenas os itens preexistentes não rastreados `.claude/` e `AGENTS.md`.
