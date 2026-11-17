# Roteiro 11 — Trabalhar com o agente (Cursor)

**Última revisão:** 2026-03-11

## Quando usar

Antes de pedir implementação ao seu agente de código no projeto.

## Pré-requisitos

- Este playbook indexado em [PLAYBOOK.md](../PLAYBOOK.md)

## Passos

1. Abrir a pasta `agente-criativos` no Cursor (workspace).
2. Dizer **uma fase** do [04](./04-evoluir-gerador.md) (ex.: “implemente só Fase A — config + ping Gemini”).
3. Exigir: ler `AGENTS.md` + roteiro + `STACK.md` antes de codar.
4. Proibir: CrewAI, autopost, commit de `.env`, pular validador.
5. Ao fim: pedir o comando de teste e o checklist do roteiro.

## Prompt modelo

```text
Projeto: C:\projetos\agente-criativos
Leia AGENTS.md, docs/PLAYBOOK.md e o roteiro 04 (fase X apenas).
Stack canônica: docs/STACK.md. Não invente libs.
Implemente só a fase X. Windows + PowerShell.
Chave só via .env. Mostre o comando de teste ao final.
```

## Checklist de saída

- [ ] Diff limitado à fase pedida
- [ ] Docs tocados se mudou comportamento
- [ ] Teste manual descrito

## Armadilhas

- “Monta tudo CrewAI + Flux + painel” numa mensagem.
- Misturar este repo com outro projeto no mesmo pedido sem necessidade.

## Links canônicos

- [AGENTS.md](../../AGENTS.md) · [PLAYBOOK.md](../PLAYBOOK.md)
