# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history and developer talent analytics.

## How to Import Historical PRs (Bootstrap Script)

The `setup.py` script allows you to backfill your database with the historical context of any public or private repository. Because this script relies on local helper modules, you must run it directly from a cloned version of this repository.

### 1. Requirements & Preparation

* You must have Python 3 installed.
* Clone this repository to your local machine:
```bash
git clone https://github.com/Myna-ai-hackaton/Writer.git
cd Writer/scripts
```

* **Firebase Database:** Download your Firebase service account key from your Firebase Console (Project Settings > Service accounts > Generate new private key). Rename the downloaded file to `firebase-key.json` and place it directly inside the `scripts` folder.

### 2. Configure Your Environment

Before running the script, export your necessary API keys directly into your terminal. This bypasses prompts and prevents environment reload issues.

Choose **one** LLM provider and export it, along with your GitHub Personal Access Token (which is required to read PR history without hitting rate limits):

```bash
export GH_PAT="your_github_personal_access_token"

# Export ONE of the following:
export GEMINI_API_KEY="your_gemini_key"
# export OPENROUTER_API_KEY="your_openrouter_key"
# export OPENAI_API_KEY="your_openai_key"
```

### 3. Run the Setup Script

Execute the script from within the `scripts` directory:

```bash
python3 setup.py
```

The script will interactively ask you for:

1. **Repository Name:** The full name of the repository you want to analyze (e.g., `osu-crypto/libOTe`).
2. **PR Limit:** How many PRs to process (useful for testing or staying within API quotas).

The script will automatically detect your keys, connect to Firebase, and begin importing summaries with a built-in rate-limit delay.

---

## Continuous Integration Setup (GitHub Actions)

Once your historical data is imported, you can set the Writer Agent to run automatically every time a new PR is closed.

### 1. Create Workflow File

Create `.github/workflows/writer.yml` in the repository you want to monitor:

```yaml
name: Writer Agent

on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  summarize:
    runs-on: ubuntu-latest
    steps:
      - name: Run Writer Agent
        uses: Myna-ai-hackaton/Writer@main
        with:
          gh_pat: ${{ secrets.GH_PAT }}
          # Provide ONE of the following:
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
          # openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          # gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          firebase_service_account_json: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}
```

### 2. Configure GitHub Secrets

Add these secrets to your repository (**Settings > Secrets and variables > Actions**):

* `GH_PAT`: A Personal Access Token with `repo` scope.
* `OPENROUTER_API_KEY` (or `GEMINI_API_KEY` / `OPENAI_API_KEY`).
* `FIREBASE_SERVICE_ACCOUNT_JSON`: The full JSON content of your Firebase Service Account key.

---

## Architecture: Sensor vs. Brain

The Writer Agent uses a **Sensor vs. Brain** pattern to ensure high-accuracy talent analytics:

1. **The Sensor (LLM):** Uses Gemini 2.5 Flash to extract qualitative engineering signals (complexity, documentation quality, resilience) and generate release notes. It does **not** perform math.
2. **The Brain (Python):** Uses deterministic math to calculate Exponential Moving Averages (EWMA), track skill XP (Junior → Senior), and maintain a temporal quality history for each developer.

## Features

* **Consolidated PR Context:** Automatically fetches full diffs (cleaned of noisy files like `.lock` and `.svg`), test ratios, and human feedback dialogue.
* **Talent Analytics:** Tracks developer growth over time across multiple projects.
* **Closed PR Learning:** Analyzes all closed PRs (both merged and denied) to learn from every code submission.
* **Multi-Provider Support:** Works with OpenRouter, Google Gemini (direct), and OpenAI.

## Local Development

1. **Install dependencies:** `pip install -r requirements.txt`
2. **Env Config:** Create a `.env` with `GH_PAT`, `OPENROUTER_API_KEY`, etc.
3. **Run:** `python scripts/agent_action.py` (requires `GITHUB_EVENT_PATH` set to a mock event JSON).
