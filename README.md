# agente-criativos

Gerador **local** de criativos para redes sociais, com foco em **Instagram**: posts únicos, carrosséis e Stories/Reels **com legenda pronta**. O texto é escrito por **IA gratuita** e as artes saem em **PNG** renderizadas com Python (HTML/CSS + Playwright). Nada é postado automaticamente — você revisa e publica.

> **Release congelada da comunidade (v1.0.0).** Este repositório é uma versão pública e estável, publicada para quem quiser estudar, usar e adaptar. Ele **não recebe novas funcionalidades**. Faça um fork e evolua do seu jeito. Issues e PRs podem não ser respondidos.

## O que ele faz

- **Post único** nos estilos `news` (card de notícia) e `ad` (anúncio), nos formatos `4x5`, `1x1`, `9x16` (Stories/Reels com zonas seguras) e `capa-reels`.
- **Carrossel** (capa + slides internos com numeração e CTA no último slide) e o carrossel clássico de texto.
- **Bio e legenda** de Instagram com hashtags, seguindo as regras de `regras_instagram/`.
- **Brand kit por marca** (`nichos/<slug>/brand.yaml`): cores, fontes, logo, @, tom de voz, palavras proibidas, hashtags e estilo de CTA. Palavra proibida no texto da IA é barrada.
- **Revisão automática** de cada peça: pré-checagem local (texto cortado, zona segura, contraste WCAG) + nota de uma **IA de visão grátis**. Nota baixa → refaz o fundo com outro provedor.
- **Imagens de fundo** por uma cadeia de provedores gratuitos, com licença/atribuição salva ao lado de cada imagem.
- **Vídeo slideshow** simples para Reels/TikTok a partir dos slides (sem IA de vídeo).
- Aprendizado por **exemplos + feedback em disco** (`nichos/<slug>/exemplos/`, `resultados.md`), sem fine-tune.

## Requisitos

- Windows 10/11 (os atalhos `.cmd` são para Windows; em Linux/macOS rode `python agente-criativos.py`)
- Python 3.12
- Pelo menos uma chave gratuita de IA de texto (ex.: Google AI Studio / Gemini)

## Instalação

```bat
git clone https://github.com/orlandoneto/agente-criativos.git
cd agente-criativos
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
copy .env.example .env
```

## Configuração (`.env`)

Copie `.env.example` para `.env` e preencha **só o que for usar**. Nunca faça commit do `.env` (ele já está no `.gitignore`).

| Variável | Para quê | Obrigatória? |
|----------|----------|--------------|
| `GEMINI_API_KEY` | Texto e visão (Google AI Studio, free tier) | Recomendado |
| `FREELLMAPI_BASE_URL` / `FREELLMAPI_API_KEY` | Qualquer endpoint compatível com OpenAI (ex.: um proxy local de modelos grátis) | Opcional |
| `OPENROUTER_API_KEY` | Modelos `:free` do OpenRouter (texto) | Opcional |
| `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` | Imagens via Workers AI (cota diária grátis) | Opcional |
| `HF_TOKEN`, `AIHORDE_API_KEY` | Hugging Face / AI Horde | Opcional |
| `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY` | Fotos de banco (gratuitas, com atribuição) | Opcional |
| `ZAI_API_KEY` | Reserva de IA de visão (GLM-4.6V-Flash, free) | Opcional |
| `IMAGE_CHAIN` | Ordem dos provedores de imagem | Já vem preenchida |

Sem nenhuma chave de imagem você ainda pode gerar peças só com tipografia (`--sem-imagem`) ou usar sua própria foto (`--fundo arquivo.png`).

Teste a conexão: `agente-criativos --ping`

## Uso

Wizard (pergunta tudo passo a passo):

```bat
agente-criativos
```

Exemplos com flags:

```bat
:: manual (não gasta IA)
agente-criativos --estilo news --formato 4x5 --tag Urgente --titulo "Onda de calor extremo deve bater 42 graus" --destaques "calor extremo,42 graus" --handle minhamarca --buscar-fundo
agente-criativos --estilo ad --formato 1x1 --pill "Ebook gratuito" --headline "*Crie posts profissionais* em 10 minutos" --badge=Grátis --features "layout-grid:50 templates; zap:Pronto em minutos; download:Download imediato" --cta "Baixe agora"

:: IA grátis escreve arte + legenda
agente-criativos --estilo news --nicho minhamarca --tema "IA no design gráfico" --buscar-fundo
agente-criativos --estilo ad --formato carrossel --nicho minhamarca --tema "ebook de design" --slides-n 3 --buscar-fundo
agente-criativos --estilo news --formato 9x16 --nicho minhamarca --tema "dicas rápidas"
```

Saída em `saida/posts/<data>_<estilo>_<formato>_<slug>/`: `post.png` (ou `slide_01.png…`), `post.json`, `legenda.md` e `post.revisao.json`.

Nova marca: copie `nichos/minhamarca/` para `nichos/<sua_marca>/` e edite `perfil.md`, `evitar.md` e `brand.yaml`. Há outros nichos prontos em `nichos/` (academia, clínica, restaurante, pet, imobiliário…).

Testes (sem rede, sem gastar cota): `.venv\Scripts\python.exe -m pytest -q`

## Provedores de IA gratuitos

Tudo foi pensado para rodar **no free tier**. Limites reais: dá para algumas boas campanhas por semana, não volume alto diário. Quando um provedor estoura a cota (429/503), a cadeia passa para o próximo.

- **Texto:** Gemini (`gemini-flash-lite-latest`), OpenRouter modelos `:free`, ou qualquer endpoint OpenAI-compatível.
- **Visão (revisão):** Gemini Flash; reserva GLM-4.6V-Flash (Z.ai).
- **Imagem:** Cloudflare Workers AI, OpenRouter, Gemini, Hugging Face, AI Horde, Pollinations, Pexels, Unsplash.

Confira sempre os termos de uso de cada provedor e as licenças das imagens geradas/baixadas. Para fotos de Pexels/Unsplash, use o campo `atribuicao` do `cena_XX.json` nos créditos.

## Documentação

- [docs/ARQUITETURA.md](./docs/ARQUITETURA.md) — mapa do sistema
- [docs/STACK.md](./docs/STACK.md) — libs e tecnologias
- [docs/PLAYBOOK.md](./docs/PLAYBOOK.md) — roteiros operacionais
- [docs/RUNBOOK.md](./docs/RUNBOOK.md) — operação e problemas comuns
- [AGENTS.md](./AGENTS.md) — mapa do repositório para agentes de código
- [CHANGELOG.md](./CHANGELOG.md)

## Licença

Código sob [MIT](./LICENSE) © 2026 Orlando Alves (orlandoneto).

Ativos de terceiros mantêm suas licenças: fontes Anton, Bebas Neue e Montserrat sob **SIL Open Font License 1.1** (`assets/fonts/OFL-*.txt`) e ícones **Lucide** sob **ISC** (`assets/icons/lucide/LICENSE`).
