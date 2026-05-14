import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") # Optional: to verify GitHub requests

# Firebase service account JSON file path
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
