# Roteiro 08 — Rotina diária

**Última revisão:** 2026-03-11

## Quando usar

Fábrica estável; quer 1 pacote por dia sem pensar no comando.

## Pré-requisitos

- [05](./05-gerar-criativo.md) funciona na mão
- Cota Gemini conhecida (AI Studio)

## Passos

1. Definir: 1 nicho/dia no início (vários nichos esgotam cota).
2. Criar `.ps1` simples que ativa venv e chama `gerar.py` com tema do dia (ou lê `temas_fila.md`).
3. Agendador de Tarefas do Windows → 1×/dia em horário fixo (PC ligado).
4. Revisar `saida/` (5 min) → aprovar ([06](./06-aprendizado-feedback.md)).
5. Postar **manual** (Business Suite / app).

## Checklist de saída

- [ ] Pasta do dia criada sem erro
- [ ] Você revisou antes de publicar
- [ ] Feedback registrado

## Armadilhas

- Agendar 10 carrosséis/dia no free → 429.
- Autopost com Selenium “para facilitar”.

## Links canônicos

- [05-gerar-criativo.md](./05-gerar-criativo.md) · [09-seguranca.md](./09-seguranca.md)
