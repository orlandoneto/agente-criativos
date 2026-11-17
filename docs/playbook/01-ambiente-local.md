# Roteiro 01 — Ambiente local

**Última revisão:** 2026-11-05

## Quando usar

PC novo, clone fresco, ou “não roda nada”.

## Pré-requisitos

- Windows 11
- Python 3.12 (`py -3.12 --version`)
- Cursor aberto em `C:\projetos\agente-criativos`
- Conta Google AI Studio (chave Gemini)

## Passos

1. Terminal no projeto (Cmder ou PowerShell).
2. Criar venv:
   ```bat
   py -3.12 -m venv .venv
   ```
3. Atualizar pip / deps **pelo Python do venv** (Cmder não usa `Activate.ps1`):
   ```bat
   .venv\Scripts\python.exe -m pip install --upgrade pip
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
4. No dia a dia: `gerar` / `gerar --ping` (`gerar.cmd` já aponta pro `.venv`).
5. Browsers do Playwright: `.venv\Scripts\python.exe -m playwright install chromium`  
   Se der erro de certificado SSL no Windows:  
   `set NODE_TLS_REJECT_UNAUTHORIZED=0` e rode o install de novo.
6. Copiar env: `Copy-Item .env.example .env` → colar `GEMINI_API_KEY` (só no arquivo).
7. Conferir modelo em `.env` / futuro `app/config.py` com o nome atual no AI Studio.

## Checklist de saída

- [ ] `gerar --ping` abre a marca e responde (ou erro claro de chave)
- [ ] `.venv\Scripts\python.exe -m pip show google-genai pydantic jinja2 playwright python-dotenv` listam versões
- [ ] `.env` existe e **não** está staged no Git

## Armadilhas

- No Cmder, `Activate.ps1` **não** troca o `python` → use `gerar` ou `.venv\Scripts\python.exe …`.
- Usar `python` global em vez do venv → `No module named 'dotenv'`.
- Nome do modelo Gemini desatualizado → 404/400; ajustar em config.
- Esquecer `playwright install chromium` → render PNG quebra na fase visual.

## Links canônicos

- [STACK.md](../STACK.md) · [VISAO.md](../VISAO.md) · [09-seguranca.md](./09-seguranca.md)
