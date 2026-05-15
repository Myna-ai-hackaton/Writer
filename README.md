# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history and developer talent analytics.

## How to use in any repository (Easy Setup)

The fastest way to get started is to run our automated setup script.

### 1. Requirements
- You must have the [GitHub CLI (`gh`)](https://cli.github.com/) installed and logged in (`gh auth login`).
- You must have Python installed.

### 2. Run the Setup Script
Open your terminal in the root of the repository you want to monitor and run:

```bash
python scripts/setup.py
```

If you want to run the latest remote version directly, you can also use:

```bash
python -c "$(curl -fsSL https://raw.githubusercontent.com/Myna-ai-hackaton/Writer/main/scripts/setup.py)"
```

The script will:
1.  Use any existing environment variables for `GH_PAT`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, and `FIREBASE_SERVICE_ACCOUNT_PATH`.
2.  Prompt for any missing keys or Firebase JSON content interactively.
3.  Fetch closed PR history from GitHub and import summaries into Firebase.

> Note: A `.env` file is optional. The script reads from environment variables first, and only prompts you when values are missing.

---

## Manual Setup (Alternative)

If you prefer to set up manually, follow these steps:

### 1. Create Workflow File
Create `.github/workflows/writer.yml`:

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

- `GH_PAT`: A Personal Access Token with `repo` scope.
- `OPENROUTER_API_KEY` (or `GEMINI_API_KEY` / `OPENAI_API_KEY`).
- `FIREBASE_SERVICE_ACCOUNT_JSON`: The full JSON content of your Firebase Service Account key.

---

## Architecture: Sensor vs. Brain

The Writer Agent uses a **Sensor vs. Brain** pattern to ensure high-accuracy talent analytics:

1.  **The Sensor (LLM):** Uses Gemini 2.0 Flash to extract qualitative engineering signals (complexity, documentation quality, resilience) and generate release notes. It does **not** perform math.
2.  **The Brain (Python):** Uses deterministic math to calculate Exponential Moving Averages (EWMA), track skill XP (Junior → Senior), and maintain a temporal quality history for each developer.

## Features

-   **Consolidated PR Context:** Automatically fetches full diffs (cleaned of noisy files like `.lock` and `.svg`), test ratios, and human feedback dialogue.
-   **Talent Analytics:** Tracks developer growth over time across multiple projects.
-   **Closed PR Learning:** Analyzes all closed PRs (both merged and denied) to learn from every code submission.
-   **Multi-Provider Support:** Works with OpenRouter, Google Gemini (direct), and OpenAI.

## Local Development

1.  **Install dependencies:** `pip install -r requirements.txt`
2.  **Env Config:** Create a `.env` with `GH_PAT`, `OPENROUTER_API_KEY`, etc.
3.  **Run:** `python scripts/agent_action.py` (requires `GITHUB_EVENT_PATH` set to a mock event JSON).
