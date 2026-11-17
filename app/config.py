"""Configuração central — paths e env. Sem lógica de geração."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_REGRAS = ROOT_DIR / "regras_instagram"
NICHOS_DIR = ROOT_DIR / "nichos"
TEMPLATES_DIR = ROOT_DIR / "templates"
SAIDA_DIR = ROOT_DIR / "saida"
CAMPANHAS_DIR = ROOT_DIR / "campanhas"
ASSETS_DIR = ROOT_DIR / "assets"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Free: flash-lite-latest (2.0/2.5-flash costumam 404 nesta conta)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
# Abordagem A: cena fotográfica (sem texto na arte)
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
_img = os.getenv("GEMINI_IMAGE_ENABLED", "true").strip().lower()
GEMINI_IMAGE_ENABLED = _img in {"1", "true", "yes", "on"}

# Chaveador de imagem (melhor → fallback)
# cloudflare | openrouter | gemini | hf | aihorde | pollinations | pexels | unsplash
IMAGE_CHAIN = [
    p.strip().lower()
    for p in os.getenv(
        "IMAGE_CHAIN",
        "cloudflare,openrouter,gemini,hf,aihorde,pollinations,pexels,unsplash",
    ).split(",")
    if p.strip()
]
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"
)

# FreeLLMAPI dedicado do Criativos (WSL 127.0.0.1:3003; no Windows use o relay local).
FREELLMAPI_BASE_URL = os.getenv("FREELLMAPI_BASE_URL", "http://127.0.0.1:3003/v1").rstrip("/")
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "")
FREELLMAPI_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")
FREELLMAPI_TIMEOUT = float(os.getenv("FREELLMAPI_TIMEOUT", "240"))
FREELLMAPI_CONNECT_TIMEOUT = float(os.getenv("FREELLMAPI_CONNECT_TIMEOUT", "3"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Image slot stays empty until a currently available zero-price model is verified.
OPENROUTER_IMAGE_MODELS = tuple(
    m.strip() for m in os.getenv("OPENROUTER_IMAGE_MODELS", "").split(",") if m.strip()
)
OPENROUTER_TEXT_MODELS = tuple(
    m.strip() for m in os.getenv("OPENROUTER_TEXT_MODELS", "").split(",") if m.strip()
)

AIHORDE_API_KEY = os.getenv("AIHORDE_API_KEY", "")
AIHORDE_CLIENT_AGENT = os.getenv(
    "AIHORDE_CLIENT_AGENT", "agente-criativos:1.0:anonymous"
)

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")

# TLS verificado por padrão (CAs do sistema). Opt-out só se o .env disser
# GEMINI_SSL_VERIFY=false explicitamente (rede com antivírus/MITM conhecido).
_ssl = os.getenv("GEMINI_SSL_VERIFY", "true").strip().lower()
GEMINI_SSL_VERIFY = _ssl in {"1", "true", "yes", "on"}

PROJECT_NAME = "Agente Criativos"
PROJECT_VERSION = "1.0.0"

# Limites Instagram
BIO_MAX_CHARS = 150
LEGENDA_MAX_CHARS = 2200
GANCHO_VISIBLE_CHARS = 125
HASHTAGS_MAX = 30
HASHTAGS_RECOMENDADAS = (3, 5)
CARROSSEL_SLIDES_MAX = 20
CARROSSEL_SLIDES_DEFAULT = (7, 10)
FEED_WIDTH = 1080
FEED_HEIGHT = 1350
# Reels / TikTok (9:16) — slideshow sem IA de vídeo
REELS_WIDTH = 1080
REELS_HEIGHT = 1920
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_SEGUNDOS_POR_SLIDE = float(os.getenv("VIDEO_SEGUNDOS_POR_SLIDE", "2.5"))
