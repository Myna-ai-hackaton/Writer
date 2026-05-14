# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history.

## Project Structure

- `scripts/main.py`: The FastAPI webhook listener.
- `scripts/github_service.py`: Handles GitHub API calls.
- `scripts/llm_service.py`: Processes PR data with Gemini AI.
- `scripts/storage_service.py`: Manages the local JSON memory index.
- `scripts/config.py`: Configuration and secrets management.
- `scripts/requirements.txt`: Python dependencies.
- `scripts/Dockerfile`: Docker configuration for the agent.

## Setup

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r scripts/requirements.txt
    ```
3.  **Configure Environment Variables:**
    Copy `scripts/.env.example` to `scripts/.env` and fill in your keys:
    - `GITHUB_TOKEN`: A Personal Access Token with repo scope.
    - `GEMINI_API_KEY`: Your Google AI API key.
4.  **Run the Agent:**
    ```bash
    python scripts/main.py
    ```
5.  **Expose the Webhook:**
    Use a tool like `ngrok` to expose port 8000 and configure the URL in your GitHub repository's webhook settings.

## How it works

1.  GitHub sends a webhook when a PR is merged.
2.  The `Writer` agent fetches the PR metadata and code diff.
3.  Gemini AI summarizes the changes into a business-readable format.
4.  The summary is saved to `memory_index.json`.