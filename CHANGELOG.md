# Changelog — agente-criativos

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · versão em `app/config.py` (`PROJECT_VERSION`).

## [1.0.0] — 2026-11-17 — Release pública da comunidade

Primeira (e única planejada) versão pública. Este repositório é uma **release congelada**: não recebe novas funcionalidades; forks são bem-vindos.

### Incluído
- CLI `agente-criativos` (wizard para humanos + flags para automação); `gerar` continua como apelido.
- Instagram: bio, legenda, carrossel clássico e post único nos estilos `news` (card de notícia) e `ad` (anúncio).
- Formatos `4x5`, `1x1`, `9x16` (Stories/Reels com zonas seguras), `capa-reels` e `carrossel` (capa + slides).
- Brand kit por marca em `nichos/<slug>/brand.yaml` (cores, fontes, logo, @, tom de voz, palavras proibidas, hashtags, CTA), com exemplo em `nichos/minhamarca/`.
- Revisão automática: pré-checagem local (texto cortado, zona segura, contraste WCAG) + IA de visão gratuita (Gemini Flash; reserva GLM-4.6V-Flash) com refação do fundo.
- Texto com IA gratuita (FreeLLMAPI/OpenAI-compatível, OpenRouter free, Gemini) e cadeia de imagens `IMAGE_CHAIN` (Cloudflare Workers AI, OpenRouter, Gemini, Hugging Face, AI Horde, Pollinations, Pexels, Unsplash).
- Vídeo slideshow simples para Reels/TikTok a partir dos slides.
- Fontes OFL e ícones Lucide (ISC) embutidos com as licenças.
- Licença MIT.
