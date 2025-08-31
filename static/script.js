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
        // (This function remains as it was in the previous update)
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
            zipInputs.remove('hidden');
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
        
        const options = { method: 'POST', body: formData };
        if (endpoint === '/process-github') {
            options.headers = { 'Authorization': `Bearer ${localStorage.getItem(GITHUB_TOKEN_KEY)}` };
        }

        fetch(endpoint, options).then(response => {
            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            function push() {
                reader.read().then(({ done, value }) => {
                    if (done) return;
                    decoder.decode(value, { stream: true }).split('\n\n').forEach(eventData => {
                        if (!eventData.trim()) return;
                        const eventLine = eventData.split('\n').find(l => l.startsWith('event: '));
                        const dataLine = eventData.split('\n').find(l => l.startsWith('data: '));
                        if (eventLine && dataLine) {
                            handleStreamEvent(eventLine.substring(7), JSON.parse(dataLine.substring(6)));
                        }
                    });
                    push();
                });
            }
            push();
        }).catch(err => handleStreamEvent('error', `Connection failed: ${err.message}`));
    };

    const handleStreamEvent = (type, data) => {
        switch (type) {
            case 'phase':
                const phaseEl = document.getElementById(`phase-${data.id}`);
                if (phaseEl) phaseEl.dataset.status = data.status;
                break;
            case 'subtask':
                const subtaskId = sanitizeForId(data.id);
                let subtaskEl = document.getElementById(subtaskId);
                const listEl = document.getElementById(data.listId);
                if (!subtaskEl && listEl) {
                    subtaskEl = document.createElement('li');
                    subtaskEl.id = subtaskId;
                    subtaskEl.textContent = data.name;
                    listEl.appendChild(subtaskEl);
                }
                if (subtaskEl) subtaskEl.dataset.status = data.status;
                break;
            case 'log':
                logOutput.textContent += data.message.replace(/\\n/g, '\n') + '\n';
                logOutput.scrollTop = logOutput.scrollHeight;
                break;
            case 'error':
                document.querySelectorAll('.phase-item[data-status="in-progress"]').forEach(el => el.dataset.status = 'error');
                logOutput.textContent += `\n\n--- ERROR ---\n${data}\n`;
                submitBtn.disabled = false;
                break;
            case 'done':
                showView('result-section');
                resultLink.innerHTML = `<p>${data.message}</p>`;
                if (data.type === 'zip') {
                    resultLink.innerHTML += `<a href="/download/${data.download_path}" class="button-link" download>Download ZIP</a>`;
                } else if (data.url) {
                    const linkText = data.url.includes('/pull/new/') ? 'Create Pull Request' : 'View Repository';
                    resultLink.innerHTML += `<a href="${data.url}" target="_blank" class="button-link">${linkText}</a>`;
                }
                submitBtn.disabled = false;
                break;
        }
    };

    // --- Event Listeners ---
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

    // --- Initial Load ---
    handleAuth();
});