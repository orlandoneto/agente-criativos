# Roteiro 05 — Gerar um criativo

**Última revisão:** 2026-11-05

## Quando usar

Rodar o produto no dia a dia (depois do gerador existir).

## Pré-requisitos

- `.venv` instalado, `.env` com chave
- Nicho preenchido
- `gerar.py` na fase B+ implementado

## Passos

1. Ir à pasta do projeto (`cd C:\projetos\agente-criativos`).
2. Humano — rodar só:
   ```bat
   gerar
   ```
   Wizard: nicho → plataforma → formatos → tema/contexto → **campanha** → **skill de conteúdo?** (opcional: ideia + imagens).  
   Saída em `campanhas/<nicho>/<campanha>/saida/<plataforma>/<formato>/`.  
   Sem skill → gera só com o nicho escolhido.
3. Ping / marca: `gerar --ping`  
4. Dev/robô (flags, sem pergunta):
   ```bat
   gerar --nicho exemplo_tech --tipo bio --tema "erro ao contratar freela" --contexto "tom direto" --campanha freela_nov --ideia "Tom direto, sem hype"
   ```
   Flags de skill: `--ideia` → `skill/ideia.md` · `--imagens` → `skill/referencias/` (ambas opcionais).
5. Abrir o arquivo em `saida/` (ou na pasta da campanha).
6. Conferir contadores (bio ≤150, gancho, hashtags).
7. Se for carrossel visual: abrir PNGs.
8. Reels/TikTok (opcional): `--video` no carrossel, ou `--video-de <pasta_do_job>` nos PNGs já gerados → `02_resultado/reels_tiktok.mp4` (9:16 slideshow, sem IA de vídeo).
9. Decidir: aprovar ([06](./06-aprendizado-feedback.md)) ou regenerar com tema mais específico.

## Checklist de saída

- [ ] Arquivo novo em `campanhas/.../saida/` (ou `saida/` legado)
- [ ] Limites respeitados (ou erro claro do validador)
- [ ] Tom alinhado ao `perfil.md` (e à skill, se houver)
- [ ] Skill = conteúdo da campanha, **não** skill do Cursor

## Armadilhas

- Tema vago (“marketing”) → conteúdo genérico.
- Estourar cota (429) → esperar / trocar modelo Flash; não ligar billing sem querer.
- Publicar sem ler → risco de claim falso.
- Confundir skill de conteúdo com skill do agente Cursor.

## Links canônicos

- [campanhas/README.md](../../campanhas/README.md) · [regras_instagram/](../../regras_instagram/) · [06-aprendizado-feedback.md](./06-aprendizado-feedback.md)
