# clone_repos.py
import json
import subprocess
import pathlib
import sys

REPOS_FILE = "repos_full.json"
CLONE_DIR = "cloned_repos"

def clone_repos():
    repos_path = pathlib.Path(REPOS_FILE)
    if not repos_path.exists():
        print(f"❌ {REPOS_FILE} not found.")
        sys.exit(1)

    try:
        repos = json.loads(repos_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"❌ Failed to parse {REPOS_FILE} as JSON.")
        sys.exit(1)

    clone_dir = pathlib.Path(CLONE_DIR)
    clone_dir.mkdir(exist_ok=True)

    for repo in repos:
        url = repo.get("url")
        if not url:
            print("⚠️  Skipping repo without URL.")
            continue

        repo_name = url.rstrip("/").split("/")[-1]
        target_path = clone_dir / repo_name

        if target_path.exists():
            print(f"✅ Already cloned: {repo_name}")
            continue

        print(f"📥 Cloning {repo_name}...")
        try:
            subprocess.run(
                ["git", "clone", url, str(target_path)],
                check=True
            )
            print(f"✅ Cloned {repo_name}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to clone {repo_name}")



def clone_single_repo(url: str):
    """Clone a single repository from a given URL."""
    if not url:
        print("❌ No URL provided.")
        return

    repo_name = url.rstrip("/").split("/")[-1]
    clone_dir = pathlib.Path(CLONE_DIR)
    clone_dir.mkdir(exist_ok=True)
    target_path = clone_dir / repo_name

    if target_path.exists():
        print(f"✅ Already cloned: {repo_name}")
        return

    print(f"📥 Cloning {repo_name}...")
    try:
        subprocess.run(
            ["git", "clone", url, str(target_path)],
            check=True
        )
        print(f"✅ Cloned {repo_name}")
    except subprocess.CalledProcessError:
        print(f"❌ Failed to clone {repo_name}")


if __name__ == "__main__":
    clone_repos()
