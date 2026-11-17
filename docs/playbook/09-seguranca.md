# Roteiro 09 — Segurança

**Última revisão:** 2026-03-11

## Quando usar

Setup de chave, dúvida de commit, dados sensíveis em exemplos.

## Pré-requisitos

- Nenhum

## Passos

1. Chave só em `.env` (modelo: `.env.example` sem valor).
2. Confirmar `.env` no `.gitignore`.
3. Nunca colar `GEMINI_API_KEY` no chat do agente de IA.
4. Exemplos sem CPF, e-mail de cliente, contratos.
5. Não habilitar billing Google sem decisão explícita sua.
6. Sem automação de login Meta no repositório.

## Checklist de saída

- [ ] `git status` não mostra `.env`
- [ ] Nenhum secret em `saida/` commitado por engano
- [ ] Política de dados dos exemplos alinhada ao uso free do Gemini

## Armadilhas

- Commitar `.venv` ou prints com chave na barra.
- Copiar `.env` de outro projeto misturando contas.

## Links canônicos

- [STACK.md](../STACK.md) seção Segurança · [10-git.md](./10-git.md)
