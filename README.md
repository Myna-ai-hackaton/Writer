# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history.

## Project Structure

- `scripts/`: Contains the core logic services.
  - `agent_action.py`: The entry point for the GitHub Action.
  - `github_service.py`: Handles GitHub API calls.
  - `llm_service.py`: Processes PR data with OpenRouter AI.
  - `storage_service.py`: Manages the Firebase cloud memory.
  - `config.py`: Configuration and secrets management.
- `requirements.txt`: Python dependencies.
- `Dockerfile`: Docker configuration for the agent.
- `action.yml`: GitHub Action metadata.
- `.env`: Environment variables (API keys).

## Setup

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment Variables:**
    Create a `.env` file in the root directory and fill in your keys:
    - `GH_PAT`: A Personal Access Token with repo scope.
    - `OPENROUTER_API_KEY`: Your OpenRouter API key.
    - `FIREBASE_SERVICE_ACCOUNT_PATH`: Path to your firebase-key.json.

4.  **Wait for PRs:**
    The agent will now run automatically on every merged Pull Request via GitHub Actions.

## How it works

1.  A Pull Request is merged into the `main` branch.
2.  The GitHub Action triggers and runs the `Writer` agent.
3.  The agent fetches the PR metadata and code diff.
4.  OpenRouter AI summarizes the changes into a business-readable format.
5.  The summary is saved to **Firebase Firestore** in real-time.
