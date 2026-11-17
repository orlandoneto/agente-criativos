# agente-criativos

Gerador local de criativos para Instagram (bio, legenda, carrossel, post único, Stories/Reels) com IA gratuita + templates Python.
Comando: `agente-criativos` (o antigo `gerar` continua como apelido). Pacote interno: `app`.
Aprendizado = exemplos + feedback em disco. **Não** há fine-tune nem autopost.

> Release pública congelada (v1.0.0). Veja o [README](./README.md).

## Mapa

| Pasta / arquivo | Papel |
|-----------------|--------|
| `agente-criativos.py` / `agente-criativos.cmd` | Entrada preferida: **wizard** para humano; **flags** para dev/robô |
| `gerar.py` / `gerar.cmd` | Apelido do mesmo CLI; imprime um aviso e chama o mesmo núcleo |
| `app/wizard.py` | Entrevista → `Brief` (mesmo contrato das flags) |
| `campanhas/` | Por nicho/campanha: `skill/` (ideia+imagens, opcional) + `saida/<plataforma>/<formato>/` |
| `app/` | Código Python (config, clientes de IA, validação, render, pipeline, campanha) |
| `regras_instagram/` | Limites e formatos por tipo de criativo |
| `nichos/<slug>/` | Perfil, exemplos, evitar — memória por marca |
| `templates/` | HTML/CSS: `carrossel_slide.html`, `news_card.html`, `ad_promo.html`, `slide_carrossel.html` |
| `assets/fonts/`, `assets/icons/lucide/` | Fontes OFL e ícones ISC embutidos (com licenças) |
| `app/post_render.py` / `app/post_pipeline.py` | Post news/ad: 4x5, 1x1, 9x16, capa-reels, carrossel |
| `app/wizard_post.py` | Wizard do estilo news/ad → mesmas flags do CLI |
| `app/brand_kit.py` + `nichos/<slug>/brand.yaml` | Brand kit validado usado por templates e prompts |
| `app/revisao.py` | Revisão automática: pré-checagem (DOM + contraste WCAG) + IA de visão grátis |
| `saida/` | Outputs gerados (conteúdo no `.gitignore`) |
| `docs/` | ARQUITETURA, STACK, PLAYBOOK + roteiros, VISAO, RUNBOOK, bugtrack |

## Regras duras

- Só free tier — nada que gere custo/billing.
- Nunca imprimir `.env` nem commitar segredos; `.env`, `.venv/`, `saida/*`, `*.log` estão no `.gitignore`.
- TLS sempre verificado (opt-out só via `.env` explícito).
- Sem postagem automática em rede social.
- Toda mudança: `pytest` verde → CHANGELOG + README/AGENTS/RUNBOOK.

## Princípio

Código = implementação · Docs = verdade · Playbook = como executar.

**Regra de negócio** (limites do Instagram, tom do nicho) fica em `regras_instagram/` e `nichos/`.

**Interfaces:** toda feature nova no wizard + flags; núcleo único.

**Qualidade:** toda implementação com testes + `pytest` verde.

**Bugs:** registrar em `docs/bugtrack/` (aprender; não repetir).
