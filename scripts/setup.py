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

def setup():
    print("🚀 Welcome to the Writer Agent Setup!")
    print("This script will configure your repository to use the AI Talent Analytics pipeline.\n")

    # 1. Check for GitHub CLI
    if not check_command("gh"):
        print("❌ Error: GitHub CLI ('gh') is not installed.")
        print("Please install it from https://cli.github.com/ and login with 'gh auth login'.")
        sys.exit(1)

    # 2. Check if we are in a Git repo
    if not os.path.exists(".git"):
        print("❌ Error: This script must be run from the root of a Git repository.")
        sys.exit(1)

    # 3. Collect API Keys
    print("--- Configuration ---")
    gh_pat = input("Enter your GitHub PAT (with repo scope): ").strip()
    openrouter_key = input("Enter your OpenRouter API Key: ").strip()
    
    fb_key_path = input("Enter the path to your Firebase service account JSON file: ").strip()
    if not os.path.exists(fb_key_path):
        print(f"❌ Error: File not found at {fb_key_path}")
        sys.exit(1)

    with open(fb_key_path, 'r') as f:
        fb_json = f.read()

    # 4. Set GitHub Secrets
    print("\n🔐 Setting up GitHub Secrets...")
    
    secrets = {
        "GH_PAT": gh_pat,
        "OPENROUTER_API_KEY": openrouter_key,
        "FIREBASE_SERVICE_ACCOUNT_JSON": fb_json
    }

    for name, value in secrets.items():
        print(f"   Setting {name}...")
        # Use subprocess.Popen to feed the secret value via stdin to avoid it appearing in process lists
        proc = subprocess.Popen(["gh", "secret", "set", name], stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, err = proc.communicate(input=value)
        if proc.returncode != 0:
            print(f"   ❌ Failed to set {name}: {err}")
            sys.exit(1)

    # 5. Create Workflow File
    print("\n📄 Creating GitHub Workflow file...")
    workflow_dir = ".github/workflows"
    os.makedirs(workflow_dir, exist_ok=True)
    
    workflow_path = os.path.join(workflow_dir, "writer.yml")
    
    workflow_content = """name: Writer Agent

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
"""
    
    with open(workflow_path, "w") as f:
        f.write(workflow_content)

    print(f"✅ Created {workflow_path}")

    print("\n✨ Setup Complete!")
    print("1. Commit the new workflow file: 'git add .github/workflows/writer.yml && git commit -m \"Add Writer Agent\"'")
    print("2. Push to GitHub.")
    print("The Writer Agent will now analyze every merged PR in this repo!")

if __name__ == "__main__":
    setup()
