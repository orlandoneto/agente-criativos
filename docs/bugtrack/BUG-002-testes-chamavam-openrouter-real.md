# BUG-002 — Testes chamavam OpenRouter real

- **Sintoma**: `test_gerar_json_esgota_modelos_mensagem_amiga` passava sozinho e falhava na suíte completa ("devia falhar").
- **Causa**: `_com_provedores` tenta OpenRouter quando `OPENROUTER_API_KEY` existe. Com a chave real no `.env`, o teste caía num modelo `:free` de verdade e recebia resposta.
- **Correção (0.13.0)**: `tests/conftest.py` zera `OPENROUTER_API_KEY`, `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY` e `HF_TOKEN` por padrão. Testes de provedor re-setam chave fictícia + MockTransport.
- **Guarda**: nenhum teste pode depender de rede. Chave nova em provedor → zerar no conftest.
