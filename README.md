# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history.

## How to use in any repository (Easy Setup)

The fastest way to get started is to run our automated setup script.

### 1. Requirements
- You must have the [GitHub CLI (`gh`)](https://cli.github.com/) installed and logged in (`gh auth login`).
- You must have Python installed.

### 2. Run the Setup Script
Open your terminal in the root of the repository you want to monitor and run:

```bash
curl -fsSL https://raw.githubusercontent.com/Myna-ai-hackaton/Writer/main/scripts/setup.py | python
```

This script will:
1.  Ask for your `GH_PAT`, `OPENROUTER_API_KEY`, and Firebase JSON.
2.  **Automatically** set your GitHub Repository Secrets using the `gh` CLI.
3.  **Automatically** create the `.github/workflows/writer.yml` file.

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
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - name: Run Writer Agent
        uses: Myna-ai-hackaton/Writer@main
        with:
          gh_pat: ${{ secrets.GH_PAT }}
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
          firebase_service_account_json: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}
```

### 2. Configure GitHub Secrets
Add these secrets to your repository (**Settings > Secrets and variables > Actions**):

- `GH_PAT`: A Personal Access Token with `repo` scope.
- `OPENROUTER_API_KEY`: Your OpenRouter API key.
- `FIREBASE_SERVICE_ACCOUNT_JSON`: The full JSON content of your Firebase Service Account key.

---

## Local Development & Structure

- `scripts/`: Core logic services.
  - `agent_action.py`: Entry point for the Action.
  - `llm_service.py`: PR summarization (uses Gemini 2.5 Flash).
  - `github_service.py`: GitHub API integration.
  - `storage_service.py`: Firebase Firestore management.
- `action.yml`: Metadata defining the GitHub Action.
- `Dockerfile`: Containerizes the environment for the Action.

### Local Setup
1.  **Install dependencies:** `pip install -r requirements.txt`
2.  **Env Config:** Create a `.env` with `GH_PAT`, `OPENROUTER_API_KEY`, etc.
3.  **Run:** `python scripts/agent_action.py` (requires `GITHUB_EVENT_PATH` set to a mock event JSON).

## How it works
1.  **Trigger:** A PR is merged into `main`.
2.  **Fetch:** The agent pulls the PR description and code diff.
3.  **Analyze:** Gemini 2.5 Flash generates a structured JSON summary (Features, Bugfixes, Risks).
4.  **Store:** The summary is saved to **Firebase Firestore**, creating a permanent, searchable record of your project's evolution.
