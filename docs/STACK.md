# Stack — libs e tecnologias

**Última revisão:** 2026-03-11 (v0.2.0: `google-genai` + Pydantic em uso no `gerar.py`)  
**Para quem:** você entender **o que** cada peça faz e **por que** está (ou não) no projeto.

Documento canônico de tecnologias. Se uma lib entrar/sair, atualize esta página **e** o `requirements.txt`.

---

## Visão em uma figura

```
Você (tema + exemplos + feedback)
        │
        ▼
┌───────────────────┐
│  gerar.py (CLI)   │  Python 3.12
└─────────┬─────────┘
          │
    ┌─────┴──────┐
    ▼            ▼
 Gemini Flash   Validador
 (texto JSON)   (limites IG)
    │            │
    └─────┬──────┘
          ▼
   Jinja2 + HTML/CSS
          │
          ▼
   Playwright → PNG
          │
          ▼
   saida/ + (opcional) Obsidian / Canva manual
```

---

## 1. Ambiente e oficina

| Tecnologia | Papel | Grátis? | Obrigatório v1? |
|------------|-------|---------|-----------------|
| **Windows 11** | SO onde o agente roda | — | Sim (alvo atual) |
| **Cursor Pro** | Editor + agente de código | Pago (você já tem) | Sim para desenvolver |
| **Python 3.12** | Linguagem do motor | Sim | Sim |
| **venv (`.venv`)** | Isola dependências do projeto | Sim (stdlib) | Sim |
| **pip** | Instala pacotes | Sim | Sim |
| **Git** | Versionar código (sem `.env`) | Sim | Recomendado |
| **Obsidian** | Abrir/organizar notas de `saida/` e nichos | Sim | Opcional (pode usar só pastas) |
| **Canva Free** | Acabamento visual humano | Sim (limites) | Opcional |
| **Google AI Studio** | Emite chave Gemini / cota free | Sim (limites diários) | Sim |

---

## 2. Bibliotecas Python (runtime)

Fonte de instalação: `requirements.txt` na raiz.

| Pacote | Para que serve neste projeto | Alternativa rejeitada |
|--------|------------------------------|------------------------|
| **`google-genai`** | SDK oficial atual do Gemini: enviar prompt, receber texto/JSON | `google-generativeai` legado; não misturar |
| **`python-dotenv`** | Carrega `GEMINI_API_KEY` do `.env` sem hardcode | Variável manual no PowerShell (pior DX) |
| **`pydantic`** (v2) | Define o formato do criativo (slides, bio, hashtags) e valida tipos | JSON “solto” sem schema → mais erro silencioso |
| **`jinja2`** | Preenche template HTML com os textos do JSON | Concatenar HTML na mão |
| **`playwright`** | Abre Chromium headless e captura PNG 1080×1350 | Selenium (mais pesado); só Pillow (layout mais difícil) |
| **Pillow** | Encaixa slide 4:5 no canvas 9:16 (Reels/TikTok) | — |
| **imageio** + **imageio-ffmpeg** | Slideshow MP4 sem IA de vídeo (`--video`) | moviepy (mais pesado) |
| **pytest** *(dev)* | Testes do validador e parsers | — |

### Por que **não** na v1

| Lib / ferramenta | Motivo de ficar de fora |
|------------------|-------------------------|
| **CrewAI / LangGraph / AutoGen** | Multiagente gasta cota e complica debug; um pipeline linear basta |
| **langchain-google-genai** | Indireção; preferimos SDK `google-genai` direto |
| **duckduckgo-search** | Pesquisa web = fase futura; v1 usa seus exemplos |
| **streamlit** | Painel depois que a CLI funciona |
| **moviepy** | Preferimos `imageio` + `imageio-ffmpeg` (mais leve) |
| **torch / diffusers / ComfyUI** | Imagem local tipo Flux exige GPU; fora do escopo v1 |

---

## 3. Serviços externos (API)

| Serviço | Uso | Custo | Onde a chave fica |
|---------|-----|-------|-------------------|
| **Gemini API** (padrão: `gemini-flash-lite-latest`) | Gerar texto inteligente (bios, legendas, carrossel em JSON) | Cota gratuita; `flash-latest` pode 503 — preferir lite | `.env` → `GEMINI_API_KEY` (**nunca** no Git nem no chat) |
| **Chaveador de imagem** (`IMAGE_CHAIN`) | gemini → hf → pollinations → pexels | Free em cascata; 429 não mata o job | `app/image_gen.py` |
| **Gemini Image** | 1º da cadeia | Cota free apertada; billing OFF | — |
| **Hugging Face** (`HF_TOKEN` + FLUX) | 2º | Inference Providers: free sem crédito → **402**; precisa PRO/pre-paid | — |
| **Pollinations** | 3º | Sem chave | — |
| **Pexels** (`PEXELS_API_KEY`) | 4º stock | API free | — |
| **Unsplash** (`UNSPLASH_ACCESS_KEY`) | 5º stock | Access Key (sem Secret) | — |
| **SSL no Windows** | `GEMINI_SSL_VERIFY=false` + `httpx` no cliente | Contorna `CERTIFICATE_VERIFY_FAILED` (antivírus/MITM) | Só desktop local; em rede limpa use `true` |


---

## 4. Camadas do nosso código (pastas)

| Caminho | Tecnologia / formato | Função |
|---------|----------------------|--------|
| `gerar.py` | Python CLI | Orquestra: ler nicho → Gemini → validar → salvar → (render) |
| `app/config.py` | Python + dotenv | Paths, nome do modelo, limites numéricos |
| `app/gemini_client.py` | `google-genai` | Uma função: prompt in → texto/JSON out |
| `app/schemas.py` | Pydantic | Contratos: `BioResult`, `LegendaResult`, `CarrosselResult` |
| `app/validator.py` | Python puro | Conta caracteres, hashtags, slides — **sem IA** |
| `app/renderer.py` | Jinja2 + Playwright | HTML → PNG |
| `regras_instagram/*.md` | Markdown | Regras de produto por tipo (bio, legenda…) |
| `nichos/<slug>/perfil.md` | Markdown | Público, tom, oferta, cores |
| `nichos/<slug>/exemplos/` | Markdown | Memória do que é “bom” |
| `nichos/<slug>/evitar.md` | Markdown | Anticlichê / rejeições |
| `templates/*.html` | HTML + CSS | Design do slide (Google Fonts via link, se licença ok) |
| `saida/` | `.md` + `.png` | Entrega do dia |

---

## 5. Aprendizado (sem rede neural nova)

| Mecanismo | Tecnologia | Como melhora a qualidade |
|-----------|------------|---------------------------|
| Few-shot | Arquivos em `exemplos/` no prompt | Gemini imita estilo aprovado |
| Negativo | `evitar.md` | Reduz spam/clichê |
| Feedback de performance | `resultados.md` (você anota) | Prompt futuro prioriza o que performou |
| (Futuro) RAG leve | embeddings locais + busca | Só se o volume de exemplos explodir |

**Não usamos:** fine-tune, JEPA, treino PyTorch, “rede neural própria”.

---

## 6. Visual: decisão técnica

| Opção | Quando usar |
|-------|-------------|
| **Jinja2 + Playwright → PNG** | Padrão v1 — carrossel/feed tipográfico com identidade do nicho |
| **Canva Free (manual)** | Polir logo, foto stock, variante rápida |
| **Gerador de imagem cloud (Ideogram etc.)** | Se o prompt_imagem for necessário; cota externa |
| **Flux / SD / ComfyUI local** | Só com GPU Nvidia ~8–12 GB+; fase opcional documentada depois |

---

## 7. Segurança e custo

| Tema | Regra |
|------|--------|
| Chaves | Só `.env`; listado no `.gitignore` |
| Dados de cliente | Não colocar PII nos exemplos (plano free do Gemini pode usar dados para treino — política Google) |
| Postagem | Manual; sem Selenium na conta Meta |
| Cota | 2–3 chamadas Gemini por criativo (gerar + corrigir se validação falhar) |

---

## 8. Como atualizar este doc

1. Adicionou pacote no `requirements.txt`? → nova linha na seção 2.  
2. Trocou modelo Gemini? → seção 3 + `app/config.py`.  
3. Entrou CrewAI / Streamlit / Flux? → seção 2 “fora da v1” vira “em uso” + data de revisão no topo.

---

## 9. Referências oficiais (externas)

- [Google Gen AI SDK (Python)](https://googleapis.github.io/python-genai/)
- [Google AI Studio](https://aistudio.google.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [Jinja2](https://jinja.palletsprojects.com/)
- [Playwright for Python](https://playwright.dev/python/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

Playbook operacional: [PLAYBOOK.md](./PLAYBOOK.md).
