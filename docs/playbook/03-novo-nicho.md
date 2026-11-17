# Roteiro 03 — Novo nicho / marca

**Última revisão:** 2026-03-11

## Quando usar

Nova empresa, novo site, ou calibrar o primeiro nicho real.

## Pré-requisitos

- Pasta `nichos/` existe
- Você sabe: público, oferta, tom, o que não pode dizer

## Passos

1. Criar `nichos/<slug>/` (slug curto, sem espaço: `minhamarca`, `empresa_tech`).
2. Copiar de `nichos/exemplo_tech/` os arquivos base.
3. Preencher `perfil.md`: público, dores, promessa, tom, CTA padrão, cores hex.
4. Preencher `evitar.md`: clichês, claims proibidos, concorrentes a não citar.
5. Colar **≥ 10** exemplos bons em `exemplos/` (bios, legendas, outlines de carrossel).
6. (Opcional) Criar `resultados.md` vazio com cabeçalho de colunas.
7. Testar geração só nesse slug quando o `gerar.py` existir.

## Checklist de saída

- [ ] `perfil.md` legível por humano em &lt; 2 min
- [ ] ≥ 10 exemplos reais (não lorem ipsum)
- [ ] Cores definidas se for usar motor visual
- [ ] Slug estável (não renomear depois sem atualizar scripts)

## Armadilhas

- Nicho vazio → Gemini genérico.
- Misturar duas marcas no mesmo `perfil.md`.
- Exemplos com dados de cliente / PII ([09](./09-seguranca.md)).

## Links canônicos

- [VISAO.md](../VISAO.md) · [06-aprendizado-feedback.md](./06-aprendizado-feedback.md)
