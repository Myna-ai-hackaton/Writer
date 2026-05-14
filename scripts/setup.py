import os
import sys
import subprocess
import shutil


def check_command(cmd):
    return shutil.which(cmd) is not None


def run_command(cmd_list):
    try:
        result = subprocess.run(cmd_list, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd_list)}: {e.stderr}")
        return None


def check_gh_auth():
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def setup():
    print("🚀 Welcome to the Writer Agent Setup!")
    print(
        "This script will configure your repository to use the AI Talent Analytics pipeline.\n"
    )

    # 1. Check for GitHub CLI and Auth
    if not check_command("gh"):
        print("❌ Error: GitHub CLI ('gh') is not installed.")
        print("Please install it from https://cli.github.com/")
        sys.exit(1)

    if not check_gh_auth():
        print("❌ Error: GitHub CLI is not logged in.")
        print(
            "Please run 'gh auth login' first to authenticate with your GitHub account."
        )
        sys.exit(1)

    # 2. Check if we are in a Git repo
    if not os.path.exists(".git"):
        print("❌ Error: This script must be run from the root of a Git repository.")
        sys.exit(1)

    # 3. Get existing secrets
    print("🔍 Checking existing secrets...")
    existing_secrets_raw = run_command(["gh", "secret", "list"])
    existing_secrets = []
    if existing_secrets_raw:
        for line in existing_secrets_raw.splitlines():
            if line.strip():
                existing_secrets.append(line.split()[0])

    # 4. Collect API Keys
    secrets_to_set = {}

    print("\n--- Configuration ---")

    # Helper to check and prompt
    def prompt_for_secret(name, label, is_file=False):
        if name in existing_secrets:
            choice = input(
                f"🔹 Secret '{name}' already exists. Update it? (y/n): "
            ).lower()
            if choice != "y":
                return None

        val = input(f"Enter {label}: ").strip()
        if not val:
            return None

        if is_file:
            if not os.path.exists(val):
                print(f"   ❌ Error: File not found at {val}")
                return None
            try:
                with open(val, "r") as f:
                    content = f.read()
                    # Basic Firebase JSON Validation
                    if "project_id" not in content or "private_key" not in content:
                        print(
                            "   ⚠️ Warning: This doesn't look like a valid Firebase Service Account JSON."
                        )
                    return content
            except Exception as e:
                print(f"   ❌ Error reading file: {e}")
                return None
        return val

    gh_pat = prompt_for_secret("GH_PAT", "your GitHub PAT (with repo scope)")
    if gh_pat:
        secrets_to_set["GH_PAT"] = gh_pat

    # LLM Provider Choice
    print("\nSelect your AI Provider:")
    print("1. OpenRouter (Supports Gemini 2.0 Flash)")
    print("2. Google Gemini (Direct API)")
    print("3. OpenAI (ChatGPT)")
    provider_choice = input("Choice (1-3): ").strip()

    if provider_choice == "1":
        key = prompt_for_secret("OPENROUTER_API_KEY", "your OpenRouter API Key")
        if key:
            secrets_to_set["OPENROUTER_API_KEY"] = key
    elif provider_choice == "2":
        key = prompt_for_secret("GEMINI_API_KEY", "your Google Gemini API Key")
        if key:
            secrets_to_set["GEMINI_API_KEY"] = key
    elif provider_choice == "3":
        key = prompt_for_secret("OPENAI_API_KEY", "your OpenAI API Key")
        if key:
            secrets_to_set["OPENAI_API_KEY"] = key

    fb_json = prompt_for_secret(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "the path to your Firebase JSON file",
        is_file=True,
    )
    if fb_json:
        secrets_to_set["FIREBASE_SERVICE_ACCOUNT_JSON"] = fb_json

    # 5. Set GitHub Secrets
    if secrets_to_set:
        print("\n🔐 Setting up GitHub Secrets...")
        for name, value in secrets_to_set.items():
            print(f"   Setting {name}...")
            proc = subprocess.Popen(
                ["gh", "secret", "set", name],
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            _, err = proc.communicate(input=value)
            if proc.returncode != 0:
                print(f"   ❌ Failed to set {name}: {err}")
                sys.exit(1)
    else:
        print("\nℹ️ No secrets updated.")

    # 6. Create Workflow File
    workflow_dir = ".github/workflows"
    workflow_path = os.path.join(workflow_dir, "writer.yml")

    should_create_workflow = True
    if os.path.exists(workflow_path):
        choice = input(
            f"\n🔹 Workflow file '{workflow_path}' already exists. Overwrite it? (y/n): "
        ).lower()
        if choice != "y":
            should_create_workflow = False

    if should_create_workflow:
        print("\n📄 Creating GitHub Workflow file...")
        os.makedirs(workflow_dir, exist_ok=True)

        workflow_content = """name: Writer Agent

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
          openrouter_api_key: ${{ secrets.OPENROUTER_API_KEY }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          firebase_service_account_json: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}
"""

        with open(workflow_path, "w") as f:
            f.write(workflow_content)
        print(f"✅ Created {workflow_path}")
    else:
        print(f"\nℹ️ Skipped creating {workflow_path}")

    print("\n✨ Setup Complete!")
    print(
        "1. Commit the new workflow file: 'git add .github/workflows/writer.yml && git commit -m \"Add Writer Agent\"'"
    )
    print("2. Push to GitHub.")
    print("The Writer Agent will now analyze every closed PR in this repo!")


if __name__ == "__main__":
    setup()
