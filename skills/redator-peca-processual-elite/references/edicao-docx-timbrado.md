# Edição de .docx em timbrado oficial — procedimento validado

Este procedimento serve para REVISAR TEXTO de um .docx existente sem quebrar a formatação. O caso mais sensível é o timbrado oficial EDE (TIMBRADO OFICIAL - APELAÇÃO.docx e derivados), que tem cabeçalhos com watermark, caixas de título em shapes duplicados e estrutura XML validada. Mas as regras valem para qualquer .docx.

## Princípio central

Na lapidação de texto, a única coisa que muda é o conteúdo dos elementos `<w:t>`. Não crie nem remova parágrafos, não altere `<w:pPr>`, estilos, shapes, cabeçalhos ou rodapés. Se a revisão exigir dividir um período longo em dois, faça a divisão DENTRO do mesmo `<w:t>` (o ponto final e a nova frase continuam no mesmo parágrafo visual) — dividir em dois `<w:p>` novos só quando inevitável, e nesse caso clonando o parágrafo original inteiro e trocando apenas o texto.

## Passo a passo

### 1. Detectar os scripts do plugin docx (nunca hardcodar caminhos)

```python
import glob, os, sys
_m = glob.glob('/sessions/*/mnt/.claude/skills/docx/scripts/office/unpack.py')
if not _m: sys.exit("ERRO: unpack.py não encontrado — plugin docx não instalado?")
UNPACK_PY = _m[0]; PACK_PY = os.path.join(os.path.dirname(_m[0]), 'pack.py')
```

### 2. Desempacotar

```bash
python3 $UNPACK_PY "PEÇA.docx" peca_unpacked/
```

Editar APENAS `peca_unpacked/word/document.xml`. Preservar intactos: `header1.xml` (watermark), `header2.xml`, `header3.xml`, `word/media/`.

### 3. Editar o texto

- Extraia os textos dos `<w:t>`, revise, e substitua de volta run a run.
- Escape XML obrigatório: `html.escape(texto)` antes de reinserir (`&`, `<`, `>`).
- Atenção a frases divididas entre múltiplos runs do mesmo parágrafo (formatação inline com negrito seletivo): reconstitua a frase completa, revise, e redistribua respeitando os limites de negrito originais.
- Use `xml:space="preserve"` quando o texto começar ou terminar com espaço.

### 4. Armadilha das caixas de título (shapes)

As caixas "APELAÇÃO" / "RAZÕES DE RECURSO" existem duplicadas em `mc:AlternateContent` (`mc:Choice` + `mc:Fallback`), gerando 2 ocorrências de texto por caixa. Se precisar tocar nelas:

- Nunca localize a posição por `doc.rfind("<w:p ", 0, pos_do_texto)` a partir do texto da caixa — isso pega o `<w:p>` INTERNO do shape e corrompe o conteúdo (a caixa renderiza vazia, e o pack.py NÃO acusa erro).
- Localize pelo início do bloco `<mc:AlternateContent` (existem exatamente 2 no documento).
- Na revisão de texto pura, o mais seguro é não tocar nas caixas de título.

### 5. Se precisar criar parágrafo novo (evitar; só quando inevitável)

- Ordem obrigatória em `<w:pPr>`: `pStyle → spacing → ind → jc → rPr`.
- `w14:paraId` deve ser < 0x80000000: gere IDs com primeiro dígito hex 1–7 (ex.: `1A000001`), nunca 8–F.
- Fonte do timbrado EDE: Segoe UI; corpo sz=24, citação recuada sz=20-22 com `ind left=2268` (ou 720 conforme o template), títulos em negrito no formato `1.` `2.` `3.1.` (nunca travessão).

### 6. Reempacotar e validar

```bash
python3 $PACK_PY peca_unpacked/ "PEÇA.docx" --original "PEÇA_BACKUP.docx"
```

Deve mostrar "All validations PASSED!". Antes de editar, faça backup do original para servir de `--original` e de rede de segurança.

### 7. Conferência visual obrigatória

```bash
soffice --headless --convert-to pdf "PEÇA.docx"
```

Abra as páginas como imagem com PyMuPDF (`pip install pymupdf --break-system-packages`) e confira ao menos a capa e a primeira página do corpo. A extração de texto (pdfplumber) não basta: texto dentro de shapes pode não aparecer no `extract_text()` mesmo renderizando bem, e vice-versa. Só considere o trabalho concluído após a checagem visual.

## Regra do projeto EDE

Edite sempre o arquivo existente, no lugar (após backup temporário). Nunca entregue uma cópia "REVISADA.docx" ao lado do original — o usuário trabalha sobre um arquivo único.
