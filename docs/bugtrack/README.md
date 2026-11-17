# Bugtrack — agente-criativos

**Antes de alterar código:** ler esta tabela. Afrouxar guarda = reabrir bug.  
**Rule:** `.cursor/rules/bugtrack.mdc` — todo bug reportado entra aqui (aprender / não repetir).

| ID | Título | Status | Guarda |
|----|--------|--------|--------|
| BUG-001 | Gemini 503/404 + failover (só lite-latest vivo na conta) | corrigido 0.10.8 | `tests/test_gemini_ping_msg.py` · `test_ia_sessao.py` · [doc](./BUG-001-ping-503-traceback.md) |

Ao corrigir: criar `BUG-NNN-slug.md` (sintoma, **por que deu erro**, correção, guarda) e linha nesta tabela. ID = maior NNN + 1.  
Mesmo assunto voltou → seção “Reincidência” no doc existente.
- [BUG-002](./BUG-002-testes-chamavam-openrouter-real.md) — testes chamavam OpenRouter real (corrigido 0.13.0)
