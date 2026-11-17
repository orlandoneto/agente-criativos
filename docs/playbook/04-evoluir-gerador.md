# Roteiro 04 — Evoluir o gerador (por fases)

**Última revisão:** 2026-11-05 (wizard + flags obrigatórios por feature — rule `wizard-cli-api`)

## Quando usar

Implementar ou alterar `gerar.py` / `app/*`.

## Pré-requisitos

- [01](./01-ambiente-local.md) ok
- Nicho de teste ([03](./03-novo-nicho.md))
- Escopo = **uma** fase abaixo

## Ordem obrigatória das fases

| Fase | Entrega | Não faça ainda |
|------|---------|----------------|
| A | `app/config.py` + ping Gemini | render, multiagente |
| B | `bio` + `legenda` + schemas Pydantic + validador | carrossel PNG |
| C | Salvar `saida/*.md` | autopost |
| D | Template HTML + Playwright PNG com texto fixo | Gemini no visual |
| E | Carrossel: Gemini JSON → valida → PNG | painel Streamlit |
| F | `--aprovar` + leitura de `exemplos/` no prompt | fine-tune |

## Passos (toda mudança de código)

1. Abrir [ARQUITETURA.md](../ARQUITETURA.md) + [STACK.md](../STACK.md) + a fase.
2. Feature de produto: **wizard** + **flag CLI** + mesmo `Brief`/pipeline ([wizard-cli-api](../../.cursor/rules/wizard-cli-api.mdc)).
3. Implementar só o necessário da fase.
4. Escrever/atualizar testes em `tests/` ([feature-testes-qualidade](../../.cursor/rules/feature-testes-qualidade.mdc)).
5. Rodar: `.venv\Scripts\python.exe -m pytest -q` — só seguir se verde.
6. Smoke opcional: `gerar` (humano) e um comando com flags.
7. Se mudou pastas/fluxo/módulo → atualizar ARQUITETURA. Contrato JSON → schema.
8. Bug → bugtrack. Fechar com **resumo simples** ao usuário.

## Checklist de saída

- [ ] `pytest` verde
- [ ] Comando/docs atualizados se necessário
- [ ] ARQUITETURA tocada se a estrutura mudou
- [ ] Sem chave no código
- [ ] Fase seguinte **não** antecipada
- [ ] Resumo simples no fim da resposta

## Armadilhas

- Pedir “sistema completo” ao Cursor numa tacada → código quebrado.
- CrewAI “só um pouquinho” sem decisão no STACK.

## Links canônicos

- [STACK.md](../STACK.md) · [05-gerar-criativo.md](./05-gerar-criativo.md) · [07-motor-visual.md](./07-motor-visual.md)
