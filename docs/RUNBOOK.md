# RUNBOOK — Agente Criativos

Operação do dia a dia (Windows, `C:\projetos\agente-criativos`). Tudo **grátis**: nada aqui liga billing.

## Rodar

| Ação | Comando |
|------|---------|
| Wizard (humano) | `agente-criativos` |
| Teste de API texto | `agente-criativos --ping` |
| Testes (sem rede, sem cota) | `.venv\Scripts\python.exe -m pytest -q` |
| Chromium do Playwright (1ª vez) | `.venv\Scripts\python.exe -m playwright install chromium` |
| Apelido antigo | `gerar` / `gerar.cmd` (continua válido; imprime um aviso) |

## Serviços locais que o projeto usa (NÃO reiniciar daqui)

| Porta | Serviço | Dono |
|------|---------|------|
| 3003 | FreeLLMAPI-criativos (texto) | este projeto consome |

## Post único Instagram (news / ad)

| Quero | Comando |
|------|---------|
| Card de notícia com foto real | `agente-criativos --estilo news --titulo "…" --destaques "a,b" --tag Urgente --handle minhamarca --buscar-fundo` |
| Mesmo card quadrado P&B | `… --formato 1x1 --pb --cor-destaque vermelho --fundo saida\posts\…\fundo.png` |
| Anúncio com cena IA | `agente-criativos --estilo ad --pill "…" --headline "*amarelo* branco" --badge=Grátis --features "zap:…; gift:…; clock:…" --cta "…" --buscar-fundo --prompt-fundo "isometric 3D … no text"` |
| IA escreve tudo (grátis) | `agente-criativos --estilo news --nicho <slug> --tema "…" --buscar-fundo` |
| Story/Reels 9:16 | `… --formato 9x16` (zonas seguras: 250 px topo, 340 px base) |
| Capa de Reels | `… --formato capa-reels` (texto no miolo 3:4 do grid) |
| Carrossel manual | `agente-criativos --estilo news --formato carrossel --titulo "…" --slide "Título *destaque*|texto" --slide "…" --cta "Salve"` |
| Carrossel com IA | `agente-criativos --estilo ad --formato carrossel --nicho minhamarca --tema "…" --slides-n 3 --buscar-fundo` |
| Selo com sinal | `--badge -50%` (funciona direto desde 0.17.0) |

- Destaques têm que ser palavras do título (validado). Ícones: nomes em `assets/icons/lucide/` (desconhecido vira `check`).
- Facebook: use o mesmo PNG (1x1 ou 4x5). Stories/Reels/TikTok: `9x16`. Carrossel: suba `slide_01.png…` na ordem.
- Wizard: `agente-criativos` sem flags → 1) post no estilo novo (news/ad) ou 2) fluxo clássico.
- Revisar sempre antes de postar — o agente não publica.

## Brand kit (desde 0.16.0)

`nichos/<slug>/brand.yaml` define a marca (cores, fontes, logo, @, tom, palavras proibidas, hashtags, CTA). Modelo pronto: `nichos/minhamarca/brand.yaml`.

| Quero | Como |
|------|------|
| Usar o kit | `--marca minhamarca` (ou só `--nicho minhamarca`, se a pasta tiver `brand.yaml`) |
| Nova marca | copie `nichos/minhamarca/brand.yaml` para `nichos/<slug>/` e edite; erro de validação aparece como `ERRO de marca: …` |
| Logo | PNG/SVG transparente na pasta do nicho + `logo: logo.png` |
| Trocar o @ só numa peça | `--handle outro` |

- Fontes aceitas: só as embutidas (Anton, Bebas Neue, Montserrat). Cores: `#RRGGBB`.
- Palavra proibida no texto da IA → o agente pede correção 1×; se insistir, para com erro. No texto manual só avisa.

## Revisão automática (desde 0.15.0)

Todo post único passa por: **pré-checagem local** (texto cortado, zona segura, contraste WCAG) → **IA de visão grátis** (Gemini Flash; reserva GLM-4.6V-Flash se `ZAI_API_KEY` existir).

| Quero | Como |
|------|------|
| Padrão (limiar 7, até 2 refações do fundo) | nada a fazer |
| Mais exigente / mais tentativas | `--revisao-limiar 8 --revisao-tentativas 3` |
| Sem IA de visão (economizar cota) | `--sem-revisao` (a pré-checagem local continua no `post.json`) |
| Ver o porquê da nota | `post.revisao.json` ao lado do PNG (notas, problemas, provedores, tentativas) |

- Nota < limiar → se foi contraste, reforça o véu (e reaproveita o fundo se a IA o aprovou); senão gera outro fundo com o próximo provedor/seed. Depois de N tentativas entrega a melhor com `precisa_revisao: true`.
- Fundo fixo (`--fundo`) ou sem fundo: não há o que refazer; só revisa.
- 429 na visão → cooldown salvo em `.cache/revisao_cooldown.json` (o próximo provedor assume).
- Cloudflare `cota diária grátis esgotada` → zera 00:00 UTC (21:00 BRT); a cadeia segue para os próximos.

## Imagens (cadeia)

`IMAGE_CHAIN` no `.env` (default `cloudflare,openrouter,gemini,hf,aihorde,pollinations,pexels,unsplash`).
Cada cena sai como `01_fases/cenas/cena_XX.png` (PNG limpo, sem EXIF) + `cena_XX.json`:

```json
{"provider": "unsplash", "licenca": "Unsplash License", "fotografo": "…", "fotografo_url": "…?utm_source=…", "foto_url": "…", "atribuicao": "Foto: … / Unsplash"}
```

Ao postar foto de Pexels/Unsplash, use `atribuicao` na legenda ou nos créditos (boa prática; Unsplash pede crédito quando possível).

## TLS

Verificado por padrão. Se a rede tiver antivírus com inspeção HTTPS e der `CERTIFICATE_VERIFY_FAILED`:
1. Prefira instalar o certificado do antivírus no Windows (o Python usa as CAs do sistema).
2. Último recurso: `GEMINI_SSL_VERIFY=false` no `.env` (o log avisa toda vez).

## Problemas comuns

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `No module named 'dotenv'` | Python global | Use `agente-criativos` / `.venv\Scripts\python.exe` |
| Todas as cenas falham | Cotas free esgotadas / sem chaves | `--sem-imagem` ou tente à noite |
| `ImagemInvalida` no log | Provedor devolveu HTML/erro | Normal: a cadeia pula para o próximo |
| 429 / 503 no texto | Free tier saturado | O CLI espera e tenta de novo (Enter/s/q) |

## Release

1. `pytest -q` verde. 2. Atualizar `PROJECT_VERSION`, `CHANGELOG.md`, README/AGENTS se mudou comportamento.
3. Commit pequeno e `git push` .
Nunca commitar `.env`, `saida/`, `.venv/`, logs.
