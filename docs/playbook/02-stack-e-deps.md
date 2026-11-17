# Roteiro 02 — Stack e dependências

**Última revisão:** 2026-03-11

## Quando usar

Vai adicionar/remover lib, trocar SDK do Gemini, ou alguém perguntou “por que essa tecnologia?”.

## Pré-requisitos

- Ter lido [STACK.md](../STACK.md)
- Ambiente local ok ([01](./01-ambiente-local.md))

## Passos

1. Decidir se a lib é **v1** ou “depois” (ver tabela “fora da v1” no STACK).
2. Se entrar: adicionar pin em `requirements.txt` (`pacote>=x,<y`).
3. Atualizar seção correspondente em `docs/STACK.md` (data no topo).
4. `pip install -r requirements.txt` no venv.
5. Se for Playwright/browser: rodar o install específico de novo.
6. Anotar no PR/commit: *por que* entrou (uma frase).

## Checklist de saída

- [ ] `requirements.txt` e `STACK.md` coerentes
- [ ] Nada de chave ou URL secreta no doc
- [ ] CrewAI / Flux / Streamlit só entram com decisão explícita no STACK

## Armadilhas

- Instalar “só no pip” sem documentar → próximo agente reinventa a roda.
- Duas libs Gemini ao mesmo tempo (`google-genai` + legado).

## Links canônicos

- [STACK.md](../STACK.md) · [requirements.txt](../../requirements.txt)
