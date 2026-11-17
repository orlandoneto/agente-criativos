# Campanhas + skill de conteúdo

Cada campanha fica separada por **nicho** e **nome**. A **skill** aqui é de **conteúdo** (ideia + imagens para acertar o criativo) — **não** é skill do Cursor/agente de código.

```text
campanhas/
  <nicho>/
    <campanha>/
      campanha.md
      skill/                    ← opcional
        ideia.md                ← ideia central (texto)
        referencias/            ← imagens exemplo de estilo
        evitar.md               ← erros só desta campanha
      saida/
        <plataforma>/           ← instagram, tiktok, …
          <formato>/            ← bio, post_feed, carrossel_feed, reels, …
            <job>/
              01_fases/
              02_resultado/
```

**Sem skill** → o motor usa só o perfil do nicho + tema/formatos que você escolheu.

## Como usar a skill (opcional)

Não é fine-tune. O agente **lê** `ideia.md` + lista de arquivos em `skill/referencias/` e pede ao Gemini para alinhar tom/estilo.

**Wizard:** depois da campanha, pergunta se quer fornecer skill (s/n). Se sim → ideia + caminhos de imagens.  
**CLI:**

```bat
gerar --nicho cobras_br --plataforma instagram --tipo bio --tema "educacao" --campanha cobras_marco --ideia "Serpentes brasileiras sem alarmismo" --imagens "C:\refs\a.png;C:\refs\b.jpg"
gerar ... --imagens "C:\pasta\com\varias\imagens"
```

Ou edite/copie manualmente em `campanhas/<nicho>/<campanha>/skill/`.
