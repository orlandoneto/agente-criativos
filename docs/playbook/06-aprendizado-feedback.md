# Roteiro 06 — Aprendizado e feedback

**Última revisão:** 2026-11-05

## Quando usar

Depois de gerar (e, se possível, depois de postar). É o que faz o agente “melhorar”.

## Pré-requisitos

- Entender: **não** treina rede neural; alimenta contexto ([VISAO.md](../VISAO.md))
- Skill de campanha = pacote de **conteúdo** (ideia + imagens), não skill do Cursor

## Passos

1. **Skill da campanha (opcional, antes/durante gerar)**  
   - `campanhas/<nicho>/<campanha>/skill/ideia.md` + `skill/referencias/`  
   - Wizard pergunta s/n; CLI: `--ideia` / `--imagens`
2. **Aprovar texto/arte bons**  
   - Copiar/mover o `.md` (e PNG se houver) para `nichos/<slug>/exemplos/`  
   - Ou: `python gerar.py --aprovar caminho` (quando implementado)
3. **Rejeitar padrão ruim**  
   - Nicho: linha em `nichos/<slug>/evitar.md`  
   - Só desta campanha: `skill/evitar.md`
4. **Se postou**, anotar em `nichos/<slug>/resultados.md`:
   - data, tipo, tema, salvamentos, comentários, nota 1–5, observação
5. Próxima geração: o prompt lê nicho (`exemplos/` + `evitar.md`) **e**, se houver, a skill da campanha

## Checklist de saída

- [ ] Pelo menos 1 exemplo novo ou 1 linha em evitar após sessão de uso
- [ ] Exemplos sem PII
- [ ] Resultados com números reais (não inventados)

## Armadilhas

- Só gerar e nunca aprovar → qualidade estagna.
- Encher exemplos com mediocre → modelo “aprende” mediocridade.

## Links canônicos

- [VISAO.md](../VISAO.md) · [STACK.md](../STACK.md) seção Aprendizado
