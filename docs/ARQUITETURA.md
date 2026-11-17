# Arquitetura — Agente Criativos

**Última revisão:** 2026-11-05 (v0.10.6: sessão sticky de IAs + continuar de onde parou) · **Versão:** `app/config.py` → `PROJECT_VERSION`  
**Para quem:** você (leitura) e o agente Cursor (evoluir sem reinventar).

Este doc é o **mapa estrutural**. Detalhes de libs → [STACK.md](./STACK.md). Escopo produto → [VISAO.md](./VISAO.md). Como executar tarefas → [PLAYBOOK.md](./PLAYBOOK.md).

---

## 1. Em uma frase

CLI local que transforma **nicho + tema (+ skill opcional)** em **criativos** (bio, legenda, carrossel PNG, vídeo slideshow), com Gemini no texto/cena e Python no resto.

---

## 2. Diagrama do sistema

```text
┌─────────────────────────────────────────────────────────────────┐
│  HUMANO: `gerar`          DEV/ROBÔ: `gerar --nicho …`           │
│  (wizard perguntas)       (flags; sem pergunta)                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Brief (contrato)   │  app/wizard.py
                    │  nicho, plataforma, │
                    │  formatos/jobs,     │
                    │  tema, campanha,    │
                    │  skill?             │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   nichos/<slug>/      campanhas/.../skill/    regras_instagram/
   perfil exemplos     ideia.md referencias/   bio.md legenda.md…
   evitar              (opcional)              carrossel.md
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  app/pipeline.py    │
                    │  bio | legenda |    │
                    │  carrossel          │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        prompt_builder   gemini_client    validator
        + nicho_loader   (JSON Pydantic)  (limites IG)
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Motor visual       │
                    │  image_gen (cenas)  │
                    │  renderer (PNG)     │
                    │  video (MP4 9:16)   │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  app/saver.py       │
                    │  01_fases/          │
                    │  02_resultado/      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   campanhas/<n>/<c>/saida/              saida/ (legado)
   <plataforma>/<formato>/<job>/
```

---

## 3. Camadas (o que vive onde)

| Camada | Pasta / arquivo | Responsabilidade |
|--------|-----------------|------------------|
| Entrada CLI | `gerar.py`, `gerar.cmd` | Parse flags, ping, orquestra jobs |
| UX humano | `app/wizard.py` | Entrevista → `Brief` |
| Estilo terminal | `app/cli_style.py`, `app/banner.py` | Cores / marca |
| Domínio campanha | `app/campanha.py` | Pastas, skill de **conteúdo**, saída |
| Domínio redes | `app/plataformas.py` | Instagram/TikTok/… → jobs |
| Memória de marca | `nichos/<slug>/` | Perfil, exemplos, evitar, resultados |
| Limites da rede | `regras_instagram/` | Regras por tipo (não copiar para `.mdc`) |
| Skill de conteúdo | `campanhas/.../skill/` | Ideia + imagens da **campanha** (≠ Cursor skill) |
| Prompts | `app/prompt_builder.py` | Monta texto para o Gemini |
| LLM texto | `app/gemini_client.py` + `app/freellmapi_client.py` | 3003/auto primeiro; OpenRouter e Gemini diretos como reserva |
| Sessão de IAs | `app/ia_sessao.py` | Sticky texto/imagem na corrida; continua de onde parou |
| Contratos | `app/schemas.py` | Pydantic bio/legenda/carrossel |
| Qualidade | `app/validator.py` | Limites IG (chars, slides, tags) |
| Identidade visual | `app/brand.py` | Cores/nome do `perfil.md` |
| Imagem | `app/image_gen.py` | Cadeia Gemini → HF → … |
| PNG | `app/renderer.py` + `templates/` | Tipografia sobre cena |
| Vídeo | `app/video.py` | Slideshow 9:16 sem IA de vídeo |
| Persistência | `app/saver.py` | Pastas fase/resultado |
| Orquestração | `app/pipeline.py` | Liga tudo sem UI |
| Config | `app/config.py` | Paths, env, `PROJECT_VERSION` |
| Testes | `tests/` | pytest — sem gastar cota Gemini |
| Docs | `docs/` | Verdade operacional + arquitetura |
| Rules | `.cursor/rules/` | Comportamento do agente Cursor |

---

## 4. Fluxo de um job (carrossel)

1. `Brief` define nicho, tema, campanha, formatos (ex.: `post_feed` → arte + legenda).
2. Se há campanha + skill → `_tema_com_skill` anexa ideia/refs ao tema.
3. `carregar_nicho` + `prompt_carrossel` → Gemini → `CarrosselResult`.
4. `validar_carrossel`; se falhar → uma correção Gemini; se ainda falhar → erro.
5. `image_gen` gera cenas (ou pula com `--sem-imagem`).
6. `renderer` monta PNG 1080×1350.
7. Opcional: `video` → `reels_tiktok.mp4`.
8. `saver` grava `01_fases/` + `02_resultado/` + `LEIA-ME.md`.

Bio/legenda: mesmo pipeline, sem PNG/vídeo.

---

## 5. Interfaces (contrato estável)

Toda feature de produto entra nos **três** pontos (API HTTP só no futuro):

| Canal | Entrada | Núcleo |
|-------|---------|--------|
| Wizard | perguntas | `Brief` → `pipeline` |
| Flags CLI | `--nicho --tema --campanha --ideia --imagens …` | mesmo |
| API futura | JSON ≈ `Brief` | mesmo `app/pipeline.py` |

Rule: `.cursor/rules/wizard-cli-api.mdc`.

---

## 6. Dados em disco (não é banco)

```text
nichos/<slug>/
  perfil.md
  evitar.md
  exemplos/*.md
  resultados.md          ← métricas humanas pós-post

campanhas/<nicho>/<campanha>/
  campanha.md
  skill/                 ← OPCIONAL (conteúdo, não Cursor)
    ideia.md
    referencias/*        ← gitignored
    evitar.md
  saida/<plataforma>/<formato>/<job>/
    01_fases/
    02_resultado/

saida/                   ← legado sem campanha (gitignored)
regras_instagram/*.md
templates/               ← HTML dos slides
```

Aprendizado = **ler** esses arquivos no próximo prompt. Não fine-tune.

---

## 7. Dependências externas

| Serviço | Uso | Nos testes |
|---------|-----|------------|
| Gemini (texto) | JSON dos criativos | **não** chamar |
| Gemini Image / HF / … | Cenas do carrossel | **não** chamar |
| Playwright Chromium | PNG | só se teste visual dedicado |
| `.env` | chaves | nunca no Git |

---

## 8. Qualidade e evolução

1. Feature → testes em `tests/` → `pytest` verde → resumo simples ao usuário.  
   Rule: `.cursor/rules/feature-testes-qualidade.mdc`.
2. Mudou estrutura de pastas / fluxo / módulo → **atualizar este ARQUITETURA.md** (data + seção).
3. Mudou lib → [STACK.md](./STACK.md) + `requirements.txt`.
4. Mudou escopo “o que é / não é” → [VISAO.md](./VISAO.md).
5. Bug → `docs/bugtrack/` + guarda de teste.

### Módulos × cobertura de teste (alvo)

| Módulo | Teste | Status |
|--------|-------|--------|
| `validator` / `schemas` | `test_validator`, `test_schemas`, `test_carrossel_validator` | ok |
| `wizard` | `test_wizard` | ok |
| `plataformas` | `test_plataformas` | ok |
| `campanha` / skill | `test_campanha` | ok |
| `pipeline` (skill no tema) | `test_pipeline_skill` | ok |
| `nicho_loader` | `test_nicho_loader` | ok |
| `prompt_builder` | `test_prompt_builder` | ok |
| `saver` | `test_saver` | ok |
| `brand` | `test_brand` | ok |
| `cli_style` / `banner` | `test_cli_style`, `test_banner` | ok |
| `video` | `test_video` | ok |
| `gemini_client` / `ia_sessao` | `test_gemini_ping_msg`, `test_ia_sessao` | ok |
| `image_gen` / `renderer` | — | só manual / futuro (caro) |

---

## 9. Anti-padrões (não fazer)

- Fine-tune, JEPA, autopost Meta, CrewAI sem decisão no STACK + playbook.
- Feature só na flag ou só no wizard.
- Skill do **Cursor** misturada com skill de **conteúdo** da campanha.
- Negócio (limites IG, tom do nicho) dentro de `.mdc`.
- Entregar feature sem pytest.
- Gravar chave no código ou no Git.

---

## 10. Como o agente deve usar este doc

```text
Pedido novo
  → ler esta seção relevante
  → implementar no módulo certo
  → espelhar wizard + flag se for produto
  → teste + pytest
  → se mudou “onde as coisas vivem”, editar este arquivo
  → resumo simples ao usuário
```


## Cloudflare image adapter - 2026-11-11
image_gen -> cloudflare_image: Workers AI REST, strict system CA TLS, 60s wall-clock HTTP deadline; JSON base64/binary decoded and normalized to PNG. No same-provider retry; 429 cooldown honors Retry-After.
Config: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_IMAGE_MODEL. Unset model defaults to tested flux-1-schnell (prompt-only); FLUX.2 uses multipart.
Existing IMAGE_CHAIN/sticky behavior and all other provider adapters remain unchanged. Tests: tests/test_cloudflare_image.py; no credentials in source/backups.


## OpenRouter free-only - 2026-11-11
openrouter_client: verified :free text/image catalog + zero prices; no paid models or automatic paid/provider fallback. 60s per attempt, 180s OpenRouter text budget, provider-wide 429 cooldown, strict TLS. Gemini public ping/JSON functions use OpenRouter first unless sticky Gemini; legacy Gemini logic unchanged. IMAGE_CHAIN has an inactive OpenRouter slot after Cloudflare: no free image model/endpoints in current catalog. OPENROUTER_IMAGE_MODELS is intentionally empty. Text model order and keys live only in .env. Tests: test_openrouter_client.py. Both wizard and flags use the same unchanged public functions.


## AI Horde image adapter - 2026-11-11
aihorde_image: official async REST (POST /api/v2/generate/async, poll /generate/check/{id}, GET /generate/status/{id}, DELETE cancel on timeout/error). Modest 512x640, 16 steps, nsfw=false, censor_nsfw=true, r2=true. Hard 60s wall-clock deadline; no same-provider retry; 429 cooldown honors Retry-After. Strict system CA TLS; Client-Agent agente-criativos:1.0:anonymous. IMAGE_CHAIN places aihorde after Cloudflare/OpenRouter(inactive)/Gemini/HF (faster dedicated APIs) and before Pollinations/stock, because it is real generation but 0-kudos queues can exceed 60s. Tests: tests/test_aihorde_image.py. No credentials in source.

## FreeLLMAPI-criativos (porta 3003) — 2026-11-11
Optional OpenAI-compatible text gateway (e.g. a self-hosted FreeLLMAPI instance) at FREELLMAPI_BASE_URL (default loopback 127.0.0.1:3003). On Windows the client can start a small 127.0.0.1:3003 stdio relay to a WSL loopback service if the port is closed. Client timeout 240s; hang/error/429 skip to the next model, and a 429 at the gateway puts the client in a 120s cooldown before falling back to OpenRouter then Gemini. IMAGE_CHAIN is unchanged. Keys live only in `.env`, never in source. Tests: `tests/test_freellmapi_client.py`.
