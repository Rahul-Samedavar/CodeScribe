# START OF FILE main.py

import os
import tempfile
import zipfile
import shutil
from pathlib import Path
import requests

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from typing import List
from git import Repo

from github import Github, GithubException # Github is already imported

from .tasks import process_project

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

app = FastAPI()

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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ... (all GET endpoints remain the same, no changes needed there) ...
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
async def auth_github_callback(code: str, request: Request):
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }
    headers = {"Accept": "application/json"}
    base_url = str(request.base_url)
    try:
        response = requests.post("https://github.com/login/oauth/access_token", params=params, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        if "error" in response_json:
            error_description = response_json.get("error_description", "Unknown error.")
            return RedirectResponse(f"{base_url}?error={error_description}")
        token = response_json.get("access_token")
        if not token:
            return RedirectResponse(f"{base_url}?error=Authentication failed, no token received.")
        return RedirectResponse(f"{base_url}?token={token}")
    except requests.exceptions.RequestException as e:
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
        Repo.clone_from(repo_url, temp_dir, branch=branch, depth=1)
        repo_path = Path(temp_dir)
        tree = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            current_level = tree
            rel_path = Path(root).relative_to(repo_path)
            if str(rel_path) != ".":
                for part in rel_path.parts:
                    parent = next((item for item in current_level if item['name'] == part), None)
                    if not parent: break
                    current_level = parent.get('children', [])
            for d in sorted(dirs):
                current_level.append({'name': d, 'children': []})
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
    exclude_list = [p.strip() for p in exclude_patterns.splitlines() if p.strip()]
    temp_dir = tempfile.mkdtemp(prefix="codescribe-zip-")
    project_path = Path(temp_dir)
    zip_location = project_path / zip_file.filename

    with open(zip_location, "wb+") as f:
        shutil.copyfileobj(zip_file.file, f)
    with zipfile.ZipFile(zip_location, 'r') as zip_ref:
        zip_ref.extractall(project_path)
    os.remove(zip_location)
    
    stream_headers = {
        "Content-Type": "text/plain",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(
        process_project(
            project_path=project_path,
            description=description,
            readme_note=readme_note,
            is_temp=True,
            exclude_list=exclude_list,
        ),
        headers=stream_headers,
        media_type="text/plain"
    )

@app.post("/process-github")
async def process_github_endpoint(request: Request,
    repo_full_name: str = Form(...),
    base_branch: str = Form(...),
    new_branch_name: str = Form(...),
    description: str = Form(...),
    readme_note: str = Form(""),
    exclude_patterns: str = Form(""),
    exclude_paths: List[str] = Form([])
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]

    # --- NEW: Branch Existence Check ---
    try:
        g = Github(token)
        repo = g.get_repo(repo_full_name)
        existing_branches = [b.name for b in repo.get_branches()]
        if new_branch_name in existing_branches:
            raise HTTPException(
                status_code=409, # 409 Conflict is appropriate here
                detail=f"Branch '{new_branch_name}' already exists. Please use a different name."
            )
    except GithubException as e:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_full_name}' not found or token lacks permissions: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while checking branches: {e}")
    # --- END of new check ---

    regex_list = [p.strip() for p in exclude_patterns.splitlines() if p.strip()]
    exclude_list = regex_list + exclude_paths

    temp_dir = tempfile.mkdtemp(prefix="codescribe-git-")
    project_path = Path(temp_dir)
    repo_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    
    Repo.clone_from(repo_url, project_path, branch=base_branch)

    stream_headers = {
        "Content-Type": "text/plain",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(
        process_project(
            project_path=project_path,
            description=description,
            readme_note=readme_note,
            is_temp=True,
            new_branch_name=new_branch_name,
            repo_full_name=repo_full_name,
            github_token=token,
            exclude_list=exclude_list,
        ),
        headers=stream_headers,
        media_type="text/plain"
    )

@app.get("/download/{file_path}")
async def download_file(file_path: str):
    temp_dir = tempfile.gettempdir()
    full_path = Path(temp_dir) / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")
    return FileResponse(path=full_path, filename=file_path, media_type='application/zip')