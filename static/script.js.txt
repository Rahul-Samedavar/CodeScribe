// This is the complete content for static/script.js

document.addEventListener("DOMContentLoaded", () => {
    // --- Constants ---
    const GITHUB_TOKEN_KEY = 'github_access_token';

    // --- DOM Element Cache ---
    const docForm = document.getElementById('doc-form');
    const submitBtn = document.getElementById('submit-btn');
    const authSection = document.getElementById('auth-section');
    const mainContent = document.getElementById('main-content');
    const githubLoginBtn = document.getElementById('github-login-btn');
    const selectZipBtn = document.getElementById('select-zip-btn');
    const selectGithubBtn = document.getElementById('select-github-btn');
    const zipInputs = document.getElementById('zip-inputs');
    const githubInputs = document.getElementById('github-inputs');
    const zipFileInput = document.getElementById('zip-file');
    const repoSelect = document.getElementById('repo-select');
    const baseBranchInput = document.getElementById('base-branch-input');
    const fileTreeContainer = document.getElementById('file-tree-container');
    const fileTree = document.getElementById('file-tree');
    const liveProgressView = document.getElementById('live-progress-view');
    const resultSection = document.getElementById('result-section');
    const resultLink = document.getElementById('result-link');
    const logOutput = document.getElementById('log-output');

    // --- Helper Functions ---
    const showView = (viewId) => {
        [authSection, mainContent, liveProgressView, resultSection].forEach(el => {
            el.classList.add('hidden');
        });
        document.getElementById(viewId).classList.remove('hidden');
    };
    
    const sanitizeForId = (str) => `subtask-${str.replace(/[^a-zA-Z0-9-]/g, '-')}`;

    const resetProgressView = () => {
        document.querySelectorAll('.phase-item').forEach(item => item.dataset.status = 'pending');
        document.querySelectorAll('.subtask-list').forEach(list => list.innerHTML = '');
        logOutput.textContent = '';
    };

    const createTreeHtml = (nodes, pathPrefix = '') => {
        let html = '<ul>';
        nodes.forEach(node => {
            const fullPath = pathPrefix ? `${pathPrefix}/${node.name}` : node.name;
            const isDir = !!node.children;
            html += `<li><input type="checkbox" name="exclude_paths" value="${fullPath}" id="cb-${fullPath}"> <label for="cb-${fullPath}"><strong>${node.name}${isDir ? '/' : ''}</strong></label>`;
            if (isDir) {
                html += createTreeHtml(node.children, fullPath);
            }
            html += '</li>';
        });
        html += '</ul>';
        return html;
    };

    // --- Core Logic ---
    const handleAuth = () => {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        const error = urlParams.get('error');

        if (error) {
            alert(`Authentication failed: ${error}`);
        }
        if (token && token !== "None") {
            localStorage.setItem(GITHUB_TOKEN_KEY, token);
        }
        window.history.replaceState({}, document.title, "/");

        if (localStorage.getItem(GITHUB_TOKEN_KEY)) {
            showView('main-content');
            fetchGithubRepos();
            switchMode('github');
        } else {
            showView('auth-section');
            switchMode('zip');
        }
    };

    const fetchGithubRepos = async () => {
        const token = localStorage.getItem(GITHUB_TOKEN_KEY);
        if (!token) return;

        try {
            const response = await fetch('/api/github/repos', { headers: { 'Authorization': `Bearer ${token}` } });
            if (response.status === 401) {
                localStorage.removeItem(GITHUB_TOKEN_KEY);
                alert('GitHub session expired. Please log in again.');
                handleAuth();
                return;
            }
            if (!response.ok) throw new Error('Failed to fetch repos');
            
            const repos = await response.json();
            repoSelect.innerHTML = '<option value="">-- Select a repository --</option>';
            repos.forEach(repo => {
                const option = document.createElement('option');
                option.value = repo.full_name;
                option.textContent = repo.full_name;
                option.dataset.defaultBranch = repo.default_branch;
                repoSelect.appendChild(option);
            });
        } catch (error) {
            console.error(error);
        }
    };

    const fetchAndBuildTree = async (repoFullName, branch) => {
        fileTreeContainer.classList.remove('hidden');
        fileTree.innerHTML = '<em>Loading repository file tree...</em>';
        const token = localStorage.getItem(GITHUB_TOKEN_KEY);
        if (!token || !repoFullName || !branch) return;
        
        try {
            const response = await fetch(`/api/github/tree?repo_full_name=${repoFullName}&branch=${branch}`, { headers: { 'Authorization': `Bearer ${token}` } });
            if (!response.ok) throw new Error(`Failed to fetch file tree (status: ${response.status})`);
            const treeData = await response.json();
            fileTree.innerHTML = createTreeHtml(treeData);
        } catch (error) {
            console.error(error);
            fileTree.innerHTML = `<em style="color: red;">${error.message}</em>`;
        }
    };

    const switchMode = (mode) => {
        fileTreeContainer.classList.add('hidden');
        if (mode === 'github') {
            selectGithubBtn.classList.add('active');
            selectZipBtn.classList.remove('active');
            githubInputs.classList.remove('hidden');
            zipInputs.classList.add('hidden');
            zipFileInput.required = false;
            repoSelect.required = true;
            if (repoSelect.value) fetchAndBuildTree(repoSelect.value, baseBranchInput.value);
        } else {
            selectZipBtn.classList.add('active');
            selectGithubBtn.classList.remove('active');
            zipInputs.classList.remove('hidden');
            githubInputs.classList.add('hidden');
            zipFileInput.required = true;
            repoSelect.required = false;
        }
    };
    
    const handleFormSubmit = (e) => {
        e.preventDefault();
        resetProgressView();
        showView('live-progress-view');
        submitBtn.disabled = true;

        const formData = new FormData(docForm);
        const endpoint = selectGithubBtn.classList.contains('active') ? '/process-github' : '/process-zip';
        
        const headers = new Headers();
        if (endpoint === '/process-github') {
            headers.append('Authorization', `Bearer ${localStorage.getItem(GITHUB_TOKEN_KEY)}`);
        }
        
        const options = { method: 'POST', body: formData, headers: headers };

        fetch(endpoint, options).then(response => {
            if (!response.ok) {
                return response.json().then(errData => {
                    throw new Error(`Server error: ${response.status} - ${errData.detail || 'Unknown error'}`);
                });
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = ''; // Buffer for incomplete lines

            function push() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        // Process any remaining text in the buffer when the stream is done
                        if (buffer) {
                           try {
                                const json = JSON.parse(buffer);
                                handleStreamEvent(json.type, json.payload);
                            } catch (e) {
                                console.error("Error parsing final buffer chunk:", buffer, e);
                            }
                        }
                        return;
                    }

                    // Append new data to buffer and process complete lines
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    
                    // The last item in lines might be an incomplete line, so we keep it in the buffer
                    buffer = lines.pop(); 
                    
                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        try {
                            const json = JSON.parse(line);
                            handleStreamEvent(json.type, json.payload);
                        } catch (e) {
                            console.error("Failed to parse JSON line:", line, e);
                        }
                    }
                    
                    push();
                }).catch(err => {
                    console.error("Stream reading error:", err);
                    handleStreamEvent('error', `Stream error: ${err.message}`);
                });
            }
            push();
        }).catch(err => handleStreamEvent('error', `${err.message}`));
    };

    const handleStreamEvent = (type, payload) => {
        // The data is now in 'payload'
        switch (type) {
            case 'phase':
                const phaseEl = document.getElementById(`phase-${payload.id}`);
                if (phaseEl) phaseEl.dataset.status = payload.status;
                break;
            case 'subtask':
                const subtaskId = sanitizeForId(payload.id);
                let subtaskEl = document.getElementById(subtaskId);
                const listEl = document.getElementById(payload.listId);
                if (!subtaskEl && listEl) {
                    subtaskEl = document.createElement('li');
                    subtaskEl.id = subtaskId;
                    subtaskEl.textContent = payload.name;
                    listEl.appendChild(subtaskEl);
                }
                if (subtaskEl) subtaskEl.dataset.status = payload.status;
                break;
            case 'log':
                logOutput.textContent += payload.message.replace(/\\n/g, '\n') + '\n';
                logOutput.scrollTop = logOutput.scrollHeight;
                break;
            case 'error':
                document.querySelectorAll('.phase-item[data-status="in-progress"]').forEach(el => el.dataset.status = 'error');
                logOutput.textContent += `\n\n--- ERROR ---\n${payload}\n`;
                submitBtn.disabled = false;
                break;
            case 'done':
                showView('result-section');
                resultLink.innerHTML = `<p>${payload.message}</p>`;
                if (payload.type === 'zip') {
                    resultLink.innerHTML += `<a href="/download/${payload.download_path}" class="button-link" download>Download ZIP</a>`;
                } else if (payload.url) {
                    const linkText = payload.url.includes('/pull/new/') ? 'Create Pull Request' : 'View Repository';
                    resultLink.innerHTML += `<a href="${payload.url}" target="_blank" class="button-link">${linkText}</a>`;
                }
                submitBtn.disabled = false;
                break;
        }
    };

    // --- Event Listeners and Initial Load ---
    githubLoginBtn.addEventListener('click', () => window.location.href = '/login/github');
    selectZipBtn.addEventListener('click', () => switchMode('zip'));
    selectGithubBtn.addEventListener('click', () => switchMode('github'));
    docForm.addEventListener('submit', handleFormSubmit);

    const updateTreeOnInputChange = () => {
        const repoFullName = repoSelect.value;
        const branch = baseBranchInput.value;
        if (repoFullName && branch) fetchAndBuildTree(repoFullName, branch);
    };

    repoSelect.addEventListener('change', (e) => {
        const selectedOption = e.target.options[e.target.selectedIndex];
        baseBranchInput.value = selectedOption.dataset.defaultBranch || '';
        updateTreeOnInputChange();
    });
    baseBranchInput.addEventListener('change', updateTreeOnInputChange);

    handleAuth();
});