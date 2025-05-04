import sys
import subprocess
import time
from collections import defaultdict

# Check and install missing dependencies
try:
    import requests
except ImportError:
    print("Installing missing dependency: requests")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

def show_help():
    """Display help information and examples"""
    help_text = """
This file is created by Kishore DVR, for more details about him please visit 
https://kishoredvr.github.io/Exploring/

Following are the example usage of this file:

1. Basic usage (public repo):
   python github_tree.py owner/repo_name
   Example: python github_tree.py digitalreliability/Sharing for https://github.com/digitalreliability/Sharing

2. With GitHub token (for private repos or higher rate limits):
   python github_tree.py owner/repo_name your_github_token
   Example: python github_tree.py digitalreliability/Sharing ghp_your_token_here

3. Help command:
   python github_tree.py help

4. Using full GitHub URL:
   python github_tree.py https://github.com/owner/repo_name
   Example: python github_tree.py https://github.com/digitalreliability/Sharing

Note: For private repositories, you must provide a GitHub personal access token.
Create one at: https://github.com/settings/tokens (scope: repo)
"""
    print(help_text)
    sys.exit(0)

def get_rate_limit_info(headers):
    """Get current rate limit information"""
    try:
        response = requests.get("https://api.github.com/rate_limit", headers=headers)
        if response.status_code == 200:
            data = response.json()
            core = data['resources']['core']
            remaining = core['remaining']
            reset_time = core['reset']
            reset_datetime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time))
            return remaining, reset_time, reset_datetime
    except Exception:
        pass
    return None, None, None

def get_repo_tree(repo, token=None, branch="main"):
    """Fetch the entire repository tree structure in one request"""
    headers = {'Authorization': f'token {token}'} if token else {}
    remaining, reset_time, reset_datetime = get_rate_limit_info(headers)
    
    # First get the latest commit SHA of the default branch
    repo_info = requests.get(f"https://api.github.com/repos/{repo}", headers=headers)
    if repo_info.status_code != 200:
        raise Exception(f"Failed to fetch repo info: {repo_info.json().get('message', 'Unknown error')}")
    
    branch = repo_info.json().get('default_branch', branch)
    branch_info = requests.get(f"https://api.github.com/repos/{repo}/branches/{branch}", headers=headers)
    if branch_info.status_code != 200:
        raise Exception(f"Failed to fetch branch info: {branch_info.json().get('message', 'Unknown error')}")
    
    tree_sha = branch_info.json()['commit']['commit']['tree']['sha']
    
    # Get the full recursive tree
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{tree_sha}?recursive=1"
    tree_response = requests.get(tree_url, headers=headers)
    
    if tree_response.status_code != 200:
        raise Exception(f"Failed to fetch tree: {tree_response.json().get('message', 'Unknown error')}")
    
    return tree_response.json()['tree'], remaining, reset_time, reset_datetime

def build_directory_structure(tree):
    """Convert flat tree into hierarchical directory structure"""
    structure = defaultdict(dict)
    
    for item in tree:
        if item['type'] != 'blob' and item['type'] != 'tree':
            continue
            
        path_parts = item['path'].split('/')
        current_level = structure
        
        for part in path_parts[:-1]:
            if part not in current_level:
                current_level[part] = defaultdict(dict)
            current_level = current_level[part]
            
        if item['type'] == 'blob':
            current_level[path_parts[-1]] = None  # Files are marked as None
        else:
            current_level[path_parts[-1]] = defaultdict(dict)
    
    return structure

def print_structure(structure, indent=""):
    """Print the directory structure with proper formatting"""
    items = sorted(structure.items())
    for i, (name, contents) in enumerate(items):
        is_last = i == len(items) - 1
        branch = "└── " if is_last else "├── "
        
        if contents is None:  # It's a file
            print(f"{indent}{branch}{name}")
        else:  # It's a directory
            print(f"{indent}{branch}{name}/")
            new_indent = indent + ("    " if is_last else "│   ")
            print_structure(contents, new_indent)

def main():
    if len(sys.argv) < 2:
        show_help()
    
    # Check for help command
    if sys.argv[1].lower() == 'help':
        show_help()
    
    repo = sys.argv[1].replace("https://github.com/", "").strip("/")
    token = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print(f"Fetching repository structure for {repo}...")
        tree, remaining, reset_time, reset_datetime = get_repo_tree(repo, token)
        structure = build_directory_structure(tree)
        
        print(f"\n{repo.split('/')[-1]}/")
        print_structure(structure)
        
        # Display rate limit information
        if remaining is not None:
            current_time = time.time()
            time_until_reset = max(0, reset_time - current_time)
            minutes, seconds = divmod(time_until_reset, 60)
            
            print("\nRate Limit Info:")
            print(f"Remaining requests: {remaining}")
            print(f"Limit resets at: {reset_datetime} (in {int(minutes)}m {int(seconds)}s)")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        if "API rate limit exceeded" in str(e):
            print("\nTip: Add a GitHub personal access token to increase your rate limit")
            print("Create one at: https://github.com/settings/tokens (scope: repo)")
        sys.exit(1)

if __name__ == "__main__":
    main()