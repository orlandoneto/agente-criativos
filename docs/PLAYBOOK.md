# Playbook operacional — Agente Criativos

**Última revisão:** 2026-11-05 · **Vale para:** `C:\projetos\agente-criativos`

Roteiro: “vou fazer X → sigo estes passos, nesta ordem, e confiro isto no fim”.  
O playbook **aponta** para a verdade; arquitetura em [ARQUITETURA.md](./ARQUITETURA.md); stack em [STACK.md](./STACK.md); visão em [VISAO.md](./VISAO.md).

| Camada | Onde | Papel |
|--------|------|--------|
| Playbook (este) | `docs/playbook/` | Passo a passo operacional |
| Arquitetura | `docs/ARQUITETURA.md` | Mapa estrutural (módulos, pastas, fluxo) |
| Stack | `docs/STACK.md` | Libs e tecnologias |
| Visão | `docs/VISAO.md` | Escopo do produto |
| Rules | `.cursor/rules/` | Comportamento do agente Cursor |
| Bugtrack | `docs/bugtrack/` | Bugs + guardas |
| Memória de nicho | `nichos/`, `regras_instagram/` | Regras de conteúdo (não copiar para cá) |

Conflito playbook × doc canônico → **vale o canônico**; corrija o roteiro e a data.

## Cartão de 1 página

| Vou… | Roteiro | Confiro no fim |
|------|---------|----------------|
| Subir o ambiente no PC | [01](./playbook/01-ambiente-local.md) | venv ativo, deps ok, Gemini responde |
| Entender / mudar stack | [STACK.md](./STACK.md) + [02](./playbook/02-stack-e-deps.md) | `requirements.txt` = STACK |
| Cadastrar ou calibrar um nicho | [03](./playbook/03-novo-nicho.md) | `perfil.md` + ≥10 exemplos |
| Implementar / evoluir o gerador | [04](./playbook/04-evoluir-gerador.md) | fase verde + **pytest** + ARQUITETURA se mudou estrutura |
| Gerar um criativo | [05](./playbook/05-gerar-criativo.md) | arquivo válido em `saida/` |
| Aprovar e “ensinar” o agente | [06](./playbook/06-aprendizado-feedback.md) | exemplo em `exemplos/` ou linha em `evitar.md` |
| Motor visual (PNG) | [07](./playbook/07-motor-visual.md) | PNG 1080×1350 legível |
| Rotina diária / agendar | [08](./playbook/08-rotina-diaria.md) | 1 ciclo/dia sem estourar cota |
| Segurança (chave, dados) | [09](./playbook/09-seguranca.md) | nada sensível no Git |
| Commit / Git | [10](./playbook/10-git.md) | `.env` fora; mensagem clara |
| Pedir tarefa ao agente Cursor | [11](./playbook/11-trabalhar-com-agente.md) | escopo de **uma** fase |

**Interfaces:** feature nova = wizard + flags + núcleo — `wizard-cli-api.mdc`.  
**Qualidade:** toda implementação = testes + `pytest` verde + resumo simples — `feature-testes-qualidade.mdc`. API HTTP só no futuro.

## Ordem de construção (roadmap)

```
01 ambiente → 03 nicho exemplo → ping Gemini
→ gerador texto (bio/legenda) + validador
→ motor visual → juntar carrossel
→ feedback/aprendizado → rotina diária
```

Não pule validação de caracteres. Não introduza CrewAI/autopost sem roteiro novo neste índice.

## Esqueleto de cada roteiro

`Quando usar` → `Pré-requisitos` → `Passos` → `Checklist de saída` → `Armadilhas` → `Links canônicos`.

## Manutenção

Mudou fluxo ou dependência? Atualize o roteiro **e** a data “Última revisão” aqui e no arquivo tocado.
