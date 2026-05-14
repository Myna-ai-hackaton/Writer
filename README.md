# Writer Agent

An AI-powered Git Project Manager that summarizes Pull Requests and provides a queryable memory for project history.

## Project Structure

- `scripts/`: Contains the core logic services.
  - `main.py`: The FastAPI webhook listener.
  - `github_service.py`: Handles GitHub API calls.
  - `llm_service.py`: Processes PR data with Gemini AI.
  - `storage_service.py`: Manages the local JSON memory index.
  - `config.py`: Configuration and secrets management.
- `requirements.txt`: Python dependencies.
- `Dockerfile`: Docker configuration for the agent.
- `.env`: Environment variables (API keys).

## Setup

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment Variables:**
    Create a `.env` file in the root directory and fill in your keys:
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