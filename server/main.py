
import os
import tempfile
import zipfile
import shutil
from pathlib import Path
import requests

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
# NEW: Import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from typing import List
from git import Repo

from github import Github, GithubException

from .tasks import process_project

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

app = FastAPI()

# NEW: Add CORS middleware configuration
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers, including Authorization
)


# Mount the static directory to serve HTML, CSS, JS
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

@app.get("/login/github")
async def login_github():
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo",
        status_code=302
    )

@app.get("/auth/github/callback")
async def auth_github_callback(code: str, request: Request): # Add request parameter
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers = {"Accept": "application/json"}
    
    # Base URL for redirects, defaulting to root.
    base_url = str(request.base_url)

    try:
        response = requests.post("https://github.com/login/oauth/access_token", params=params, headers=headers)
        response.raise_for_status() # This will raise an exception for 4xx/5xx responses
        
        response_json = response.json()
        
        # Check for errors from GitHub, like a used code
        if "error" in response_json:
            error_description = response_json.get("error_description", "Unknown error.")
            # Redirect to the home page with an error message
            # The frontend can optionally display this to the user.
            return RedirectResponse(f"{base_url}?error={error_description}")

        token = response_json.get("access_token")

        # Explicitly check if the token is valid before redirecting
        if not token:
            # If for some reason we didn't get a token and no error, handle it.
            return RedirectResponse(f"{base_url}?error=Authentication failed, no token received.")

        # Success! Redirect user back to the frontend with the real token.
        return RedirectResponse(f"{base_url}?token={token}")

    except requests.exceptions.RequestException as e:
        # Handle network errors or non-200 responses
        return RedirectResponse(f"{base_url}?error=Failed to connect to GitHub: {e}")

@app.get("/api/github/repos")
async def get_github_repos(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]
    
    try:
        g = Github(token)
        user = g.get_user()
        repos = [{"full_name": repo.full_name, "default_branch": repo.default_branch} for repo in user.get_repos(type='owner')]
        return repos
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch repos: {e}")


@app.get("/api/github/tree")
async def get_github_repo_tree(request: Request, repo_full_name: str, branch: str):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]

    temp_dir = tempfile.mkdtemp(prefix="codescribe-tree-")
    try:
        repo_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
        # We only need the metadata, so a shallow clone is much faster.
        Repo.clone_from(repo_url, temp_dir, branch=branch, depth=1)
        
        repo_path = Path(temp_dir)
        tree = []
        for root, dirs, files in os.walk(repo_path):
            # Ignore .git directory
            if '.git' in dirs:
                dirs.remove('.git')

            # Create a nested structure
            current_level = tree
            rel_path = Path(root).relative_to(repo_path)
            
            if str(rel_path) != ".":
                for part in rel_path.parts:
                    # Find the parent node
                    parent = next((item for item in current_level if item['name'] == part), None)
                    if not parent: # Should not happen if os.walk works as expected
                        break
                    current_level = parent.get('children', [])
            
            # Add directories
            for d in sorted(dirs):
                current_level.append({'name': d, 'children': []})
            
            # Add files
            for f in sorted(files):
                current_level.append({'name': f})
        
        return tree

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone or process repo tree: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/process-zip")
async def process_zip_endpoint(
    description: str = Form(...),
    readme_note: str = Form(""),
    zip_file: UploadFile = File(...),
    exclude_patterns: str = Form("")
):
    # The zip workflow can't use a file tree, so it only gets regex.
    exclude_list = [p.strip() for p in exclude_patterns.splitlines() if p.strip()]
    temp_dir = tempfile.mkdtemp(prefix="codescribe-zip-")
    project_path = Path(temp_dir)
    zip_location = project_path / zip_file.filename

    with open(zip_location, "wb+") as f:
        shutil.copyfileobj(zip_file.file, f)

    with zipfile.ZipFile(zip_location, 'r') as zip_ref:
        zip_ref.extractall(project_path)
    
    os.remove(zip_location)

    # Now we stream the processing
    return EventSourceResponse(
        process_project(
            project_path=project_path,
            description=description,
            readme_note=readme_note,
            is_temp=True,
            exclude_list=exclude_list
        )
    )

@app.post("/process-github")
async def process_github_endpoint(request: Request,
    repo_full_name: str = Form(...),
    base_branch: str = Form(...),
    new_branch_name: str = Form(...),
    description: str = Form(...),
    readme_note: str = Form(""),
    exclude_patterns: str = Form(""),
    exclude_paths: List[str] = Form([]) # This captures the checkboxes
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]

    regex_list = [p.strip() for p in exclude_patterns.splitlines() if p.strip()]
    exclude_list = regex_list + exclude_paths

    # Clone the repo
    temp_dir = tempfile.mkdtemp(prefix="codescribe-git-")
    project_path = Path(temp_dir)
    repo_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    
    from git import Repo
    Repo.clone_from(repo_url, project_path, branch=base_branch)

    # Stream the processing
    return EventSourceResponse(
        process_project(
            project_path=project_path,
            description=description,
            readme_note=readme_note,
            is_temp=True,
            new_branch_name=new_branch_name,
            repo_full_name=repo_full_name,
            github_token=token,
            exclude_list=exclude_list,
        )
    )

@app.get("/download/{file_path}")
async def download_file(file_path: str):
    temp_dir = tempfile.gettempdir()
    full_path = Path(temp_dir) / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")
    return FileResponse(path=full_path, filename=file_path, media_type='application/zip')