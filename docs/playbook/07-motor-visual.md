# Roteiro 07 — Motor visual (PNG)

**Última revisão:** 2026-03-11

## Quando usar

Implementar ou ajustar templates HTML → Playwright → PNG.

## Pré-requisitos

- Fase texto estável ([04](./04-evoluir-gerador.md) B/C)
- `playwright install chromium` ok
- Cores no `perfil.md` do nicho

## Passos

1. Criar/editar `templates/carrossel_slide.html` (1080×1350 CSS).
2. Testar com JSON/texto **fixo** (sem gastar Gemini).
3. Ligar Jinja2 aos campos do schema do carrossel.
4. Exportar um PNG por slide em `saida/<data>_carrossel/`.
5. Conferir: texto não corta, contraste ok, margem segura.
6. Só então plugar a saída do Gemini.

## Checklist de saída

- [ ] PNG abre e lê no celular (simular zoom)
- [ ] Dimensão 1080×1350 (ou a definida no config)
- [ ] Falha de texto longo tratada (fonte menor ou aviso)

## Armadilhas

- Fonte Google sem checar licença.
- Depender do Canva API na v1.
- Chamar Flux/ComfyUI sem GPU documentada no STACK.

## Links canônicos

- [STACK.md](../STACK.md) seção Visual · [04-evoluir-gerador.md](./04-evoluir-gerador.md)
