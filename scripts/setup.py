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
            choice = input(f"🔹 Secret '{name}' already exists. Update it? (y/n): ").lower()
            if choice != 'y':
                return None
        
        val = input(f"Enter {label}: ").strip()
        if not val:
            return None

        if is_file:
            if not os.path.exists(val):
                print(f"   ❌ Error: File not found at {val}")
                return None
            try:
                with open(val, 'r') as f:
                    return f.read()
            except Exception as e:
                print(f"   ❌ Error reading file: {e}")
                return None
        return val

    gh_pat = prompt_for_secret("GH_PAT", "your GitHub PAT (with repo scope)")
    if gh_pat: secrets_to_set["GH_PAT"] = gh_pat

    openrouter_key = prompt_for_secret("OPENROUTER_API_KEY", "your OpenRouter API Key")
    if openrouter_key: secrets_to_set["OPENROUTER_API_KEY"] = openrouter_key

    fb_json = prompt_for_secret("FIREBASE_SERVICE_ACCOUNT_JSON", "the path to your Firebase JSON file", is_file=True)
    if fb_json: secrets_to_set["FIREBASE_SERVICE_ACCOUNT_JSON"] = fb_json

    # 5. Set GitHub Secrets
    if secrets_to_set:
        print("\n🔐 Setting up GitHub Secrets...")
        for name, value in secrets_to_set.items():
            print(f"   Setting {name}...")
            proc = subprocess.Popen(["gh", "secret", "set", name], stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            _, err = proc.communicate(input=value)
            if proc.returncode != 0:
                print(f"   ❌ Failed to set {name}: {err}")
                sys.exit(1)
    else:
        print("\nℹ️ No secrets updated.")

    # 6. Create Workflow File
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
