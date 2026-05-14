import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Firebase service account JSON file path
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
