# BUG-001 — Gemini 503 (alta demanda) no ping e no gerar

**Data:** 2026-11-05 · **Versões:** 0.6.3 → 0.10.5 → **0.10.6** (todas as IAs + continua de onde parou)

## Por que deu erro? (causa raiz)

Não foi bug do nicho, tema, skill nem do Feed.  
O **Google Gemini (plano free)** respondeu `503 UNAVAILABLE` / *high demand*: muitos usuários batendo no mesmo modelo ao mesmo tempo. A API pede para tentar de novo depois.

O que **era** bug nosso:

1. Mostrar dump inglês/JSON cru no terminal
2. Desistir no primeiro 503 sem esperar nem trocar de modelo

## Sintoma

- `gerar --ping` ou `Feed — 1 imagem + texto` → `FALHA … 503 UNAVAILABLE {'error': …}`

## Correção

| Versão | O que fez |
|--------|-----------|
| 0.6.3 | Ping: mensagem amigável + fallback de modelos |
| 0.10.3 | `gerar_json` com fallback; mensagem sem dump; caminho no sucesso |
| **0.10.4** | Detecta 503 pelo texto; backoff + retry |
| **0.10.5** | Failover inteligente no texto (classifica erro; 503 troca na hora) |
| **0.10.6** | **Todas as IAs** (texto + imagem): sticky na corrida; job que falhou não aborta os outros; cenas já feitas são reaproveitadas |

## Guarda

`tests/test_gemini_ping_msg.py`  
- mensagem amigável · detecta 503 pelo texto  
- classifica erro · reordena lite em sobrecarga  
- 503 → troca de modelo na hora (não martela o mesmo)  
- esgota modelos → RuntimeError amigável  

## Como conferir

```bat
gerar --ping
gerar
```

Se a API ainda estiver saturada: mensagem em PT pedindo 1–2 min — **sem** Traceback e **sem** JSON inglês.  
Muitas vezes o retry resolve sozinho.

## Reincidência / atualização 2026-11-05

Feed mostrou dump 503 → 0.10.3–0.10.6 failover.

### 2026-11-05 (404 modelo morto) — 0.10.7 → 0.10.8

**Sintoma:** vários 404 (`2.0-flash`, `2.0-flash-lite`, `2.5-flash-lite`) e 503 no carrossel; legenda ok em `gemini-flash-lite-latest`.

**Causa:** conta free só responde bem no `*-lite-latest`; demais ids 404; carrossel ia primeiro e falhava antes do sticky.

**Correção 0.10.8:**
- Padrão `GEMINI_MODEL=gemini-flash-lite-latest`
- Blacklist dos 404 observados + cache `.cache/modelos_texto_bloqueados.txt`
- Pacote Feed: **legenda antes** da arte (aquece sticky)
- Último modelo vivo: até 5 retries em 503

### 2026-11-05 — espera + salvar campanha (0.11.0)

**Pedido:** esperar e ficar tentando; sugerir tipografia / ping / horário; após 5 esperas **salvar** a campanha.

**Correção:** `app/resiliencia_ia.py` — esperas 60…180s (5×), `gerar --ping` entre tentativas, sugestões no terminal, `campanhas/.../pendente.md` + mantém entregas parciais.
