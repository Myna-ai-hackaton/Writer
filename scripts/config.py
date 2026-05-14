import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

GH_PAT = os.getenv("GH_PAT")

# LLM Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Firebase service account JSON file path
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    "firebase-key.json",
)
