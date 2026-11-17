# Visão do produto — Agente Criativos

**Última revisão:** 2026-11-05 (v0.10.0: skill de conteúdo opcional por campanha)

## O que é

Sistema **local** (seu PC) que, a partir de um nicho + tema (+ contexto opcional), gera criativos de qualidade:

1. Carrega regras da rede + perfil + exemplos do nicho
2. Pede ao **Gemini** o conteúdo em JSON estruturado
3. **Valida** limites (bio, legenda, hashtags, slides) em Python
4. (Fase visual) Renderiza **PNG** 1080×1350 via HTML/CSS + Playwright
5. Salva em `saida/`; você aprova os bons → viram `exemplos/` (aprendizado)

## O que não é (v1)

| Fora de escopo | Motivo |
|----------------|--------|
| Autopost Instagram/Facebook | Risco de ban; fica manual / Business Suite |
| Treinar rede / JEPA / fine-tune | Desnecessário; Gemini + memória local basta |
| CrewAI multiagente | Cota e complexidade; 1 fluxo `gerar.py` primeiro |
| Canva API / login Canva | Acabamento opcional **manual** no Canva Free |
| Flux/ComfyUI local | Só se houver GPU forte; arte tipográfica cobre v1 |
| Servidor / SaaS hospedado | Tudo no PC; custo ~zero |
| API HTTP pública (venda) | Fase futura: mesmo `Brief`/pipeline; não na v1 local |

## Interfaces (produto)

| Canal | Quem | Como |
|-------|------|------|
| Wizard (`gerar`) | Humano | Nicho → plataforma → formatos → tema → campanha → **skill?** (ideia + imagens, opcional) |
| CLI flags | Dev / robô / CI | + `--campanha` `--ideia` `--imagens` (todos opcionais além do brief) |
| API HTTP | Cliente pago (futuro) | Mesmo núcleo `app/pipeline.py` — ainda não expor |

Saída: `campanhas/<nicho>/<campanha>/saida/<plataforma>/<formato>/`.  
Skill de conteúdo (opcional): `.../skill/{ideia.md,referencias/,evitar.md}` — **não** é skill do Cursor.  
Sem skill → só perfil do nicho + tema.

Nicho = pasta `nichos/<slug>/`. Contexto/tema = texto livre da campanha. Rule: `.cursor/rules/wizard-cli-api.mdc`.

## Aprendizado (definição operacional)

Não é treinar pesos nem fine-tune. É:

- **Skill de campanha** — ideia central + imagens exemplo (few-shot no prompt)
- `nichos/.../exemplos/` — o que você aprovou no nicho
- `evitar.md` (nicho ou `skill/evitar.md`) — o que não repetir
- `resultados.md` — métricas que você anotou após postar
- Próximo `gerar.py` **lê** isso no prompt do Gemini

## Entregáveis por tipo

| Tipo | Saída |
|------|--------|
| `bio` | 3 versões ≤ 150 caracteres + contagem |
| `legenda` | Gancho nos 125, corpo, CTA, 3–5 hashtags |
| `headline` | Título/subtítulo para Canva + alternativas |
| `cta` | Variações por objetivo |
| `carrossel` | 7–10 slides (texto + nota visual) + legenda + PNGs |
| `prompt_imagem` | Prompt EN (opcional, se for usar gerador externo) |

## Stack canônica

Ver [STACK.md](./STACK.md).
