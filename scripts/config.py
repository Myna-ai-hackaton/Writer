import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

GH_PAT = os.getenv("GH_PAT")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Firebase service account JSON file path
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
