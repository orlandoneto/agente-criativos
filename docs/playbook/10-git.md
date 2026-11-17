# Roteiro 10 — Git

**Última revisão:** 2026-03-11

## Quando usar

Commit, push, primeiro remote.

## Pré-requisitos

- [09](./09-seguranca.md) ok

## Passos

1. `git status` / `git diff` — revisar.
2. Não stage: `.env`, `.venv`, PNGs enormes de teste (ou use Git LFS depois se precisar).
3. Conventional Commits: `docs:`, `feat:`, `fix:`, `chore:`.
4. Commit só com pedido explícito do dono do repo, se estiver em modo assistido.
5. Remote: o seu fork (ex.: `git@github.com:<voce>/agente-criativos.git`).

## Checklist de saída

- [ ] Diff limpo de secrets
- [ ] `STACK.md` / playbook atualizados se a mudança for de processo ou deps

## Armadilhas

- Primeiro commit com `saida/` cheia de lixo binário.

## Links canônicos

- [09-seguranca.md](./09-seguranca.md)
