// Original behavior from static/script.js (script-RhPfZ.js) with minimal structural adjustments:
document.addEventListener("DOMContentLoaded", () => {
  // --- Constants ---
  const GITHUB_TOKEN_KEY = "github_access_token"

  // --- DOM Element Cache ---
  const docForm = document.getElementById("doc-form")
  const submitBtn = document.getElementById("submit-btn")
  const authSection = document.getElementById("auth-section")
  const mainContent = document.getElementById("main-content")
  const githubLoginBtn = document.getElementById("github-login-btn")
  const selectZipBtn = document.getElementById("select-zip-btn")
  const selectGithubBtn = document.getElementById("select-github-btn")
  const zipInputs = document.getElementById("zip-inputs")
  const githubInputs = document.getElementById("github-inputs")
  const zipFileInput = document.getElementById("zip-file")
  const repoSelect = document.getElementById("repo-select")
  const baseBranchSelect = document.getElementById("base-branch-select")
  const newBranchInput = document.getElementById("new-branch-input")
  const branchNameError = document.getElementById("branch-name-error")
  const fileTreeContainer = document.getElementById("file-tree-container")
  const fileTree = document.getElementById("file-tree")
  const liveProgressView = document.getElementById("live-progress-view")
  const resultSection = document.getElementById("result-section")
  const resultLink = document.getElementById("result-link")
  const logOutput = document.getElementById("log-output")

  // --- Helper Functions ---
  const showView = (viewId) => {
    ;[authSection, mainContent, liveProgressView, resultSection].forEach((el) => el.classList.add("hidden"))
    document.getElementById(viewId).classList.remove("hidden")
  }
  const sanitizeForId = (str) => `subtask-${str.replace(/[^a-zA-Z0-9-]/g, "-")}`
  const resetProgressView = () => {
    document.querySelectorAll(".phase-item").forEach((item) => (item.dataset.status = "pending"))
    document.querySelectorAll(".subtask-list").forEach((list) => (list.innerHTML = ""))
    logOutput.textContent = ""
  }
  const createTreeHtml = (nodes, pathPrefix = "") => {
    let html = "<ul>"
    nodes.forEach((node) => {
      const fullPath = pathPrefix ? `${pathPrefix}/${node.name}` : node.name
      const isDir = !!node.children
      html += `<li><input type="checkbox" name="exclude_paths" value="${fullPath}" id="cb-${fullPath}"> <label for="cb-${fullPath}"><strong>${node.name}${isDir ? "/" : ""}</strong></label>`
      if (isDir) html += createTreeHtml(node.children, fullPath)
      html += "</li>"
    })
    html += "</ul>"
    return html
  }

  // --- Core Logic (unchanged app behavior) ---
  const checkBranchName = async () => {
    const repoFullName = repoSelect.value
    const branchName = newBranchInput.value.trim()
    const token = localStorage.getItem(GITHUB_TOKEN_KEY)

    branchNameError.textContent = ""
    branchNameError.style.display = "none"

    if (!repoFullName || !branchName || !token || !selectGithubBtn.classList.contains("active")) {
      submitBtn.disabled = false
      return
    }

    submitBtn.disabled = true
    submitBtn.querySelector(".btn-inner span:last-child")?.replaceWith(document.createTextNode("Checking branch..."))

    try {
      const response = await fetch(
        `/api/github/branch-exists?repo_full_name=${encodeURIComponent(repoFullName)}&branch_name=${encodeURIComponent(branchName)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      )

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || `Server error: ${response.status}`)
      }

      const data = await response.json()
      if (data.exists) {
        branchNameError.textContent = `Branch '${branchName}' already exists. Please choose another name.`
        branchNameError.style.display = "block"
        submitBtn.disabled = true
      } else {
        submitBtn.disabled = false
      }
    } catch (error) {
      console.error("Error checking branch name:", error)
      branchNameError.textContent = `Could not verify branch name. ${error.message}`
      branchNameError.style.display = "block"
      submitBtn.disabled = false // Allow submission, server will catch it if it's a real issue.
    } finally {
      // Restore button text
      const inner = submitBtn.querySelector(".btn-inner")
      if (inner) {
        inner.innerHTML = '<span class="loader" aria-hidden="true"></span><span>Generate Documentation</span>'
      }
    }
  }

  const handleAuth = () => {
    const urlParams = new URLSearchParams(window.location.search)
    const token = urlParams.get("token")
    const error = urlParams.get("error")

    if (error) alert(`Authentication failed: ${error}`)
    if (token && token !== "None") localStorage.setItem(GITHUB_TOKEN_KEY, token)
    window.history.replaceState({}, document.title, "/")

    if (localStorage.getItem(GITHUB_TOKEN_KEY)) {
      showView("main-content")
      fetchGithubRepos()
      switchMode("github")
    } else {
      showView("auth-section")
      switchMode("zip")
    }
  }

  const fetchGithubRepos = async () => {
    const token = localStorage.getItem(GITHUB_TOKEN_KEY)
    if (!token) return

    try {
      const response = await fetch("/api/github/repos", { headers: { Authorization: `Bearer ${token}` } })
      if (response.status === 401) {
        localStorage.removeItem(GITHUB_TOKEN_KEY)
        alert("GitHub session expired. Please log in again.")
        handleAuth()
        return
      }
      if (!response.ok) throw new Error("Failed to fetch repos")

      const repos = await response.json()
      repoSelect.innerHTML = '<option value="">-- Select a repository --</option>'
      repos.forEach((repo) => {
        const option = document.createElement("option")
        option.value = repo.full_name
        option.textContent = repo.full_name
        option.dataset.defaultBranch = repo.default_branch
        repoSelect.appendChild(option)
      })
    } catch (error) {
      console.error(error)
    }
  }

  const fetchRepoBranches = async (repoFullName, defaultBranch) => {
    const token = localStorage.getItem(GITHUB_TOKEN_KEY)
    if (!token || !repoFullName) return

    baseBranchSelect.innerHTML = "<option>Loading branches...</option>"
    baseBranchSelect.disabled = true

    try {
      const response = await fetch(`/api/github/branches?repo_full_name=${repoFullName}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) throw new Error("Failed to fetch branches")
      const branches = await response.json()

      baseBranchSelect.innerHTML = ""
      branches.forEach((branchName) => {
        const option = document.createElement("option")
        option.value = branchName
        option.textContent = branchName
        if (branchName === defaultBranch) option.selected = true
        baseBranchSelect.appendChild(option)
      })
    } catch (error) {
      console.error(error)
      baseBranchSelect.innerHTML = `<option>Error loading branches</option>`
    } finally {
      baseBranchSelect.disabled = false
    }
  }

  const fetchAndBuildTree = async (repoFullName, branch) => {
    fileTreeContainer.classList.remove("hidden")
    fileTree.innerHTML = "<em>Loading repository file tree...</em>"
    const token = localStorage.getItem(GITHUB_TOKEN_KEY)
    if (!token || !repoFullName || !branch) return

    try {
      const response = await fetch(`/api/github/tree?repo_full_name=${repoFullName}&branch=${branch}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) throw new Error(`Failed to fetch file tree (status: ${response.status})`)
      const treeData = await response.json()
      fileTree.innerHTML = createTreeHtml(treeData)
    } catch (error) {
      console.error(error)
      fileTree.innerHTML = `<em style="color: #ef4444;">${error.message}</em>`
    }
  }

  const switchMode = (mode) => {
    fileTreeContainer.classList.add("hidden")
    if (mode === "github") {
      selectGithubBtn.classList.add("active")
      selectZipBtn.classList.remove("active")
      githubInputs.classList.remove("hidden")
      zipInputs.classList.add("hidden")
      zipFileInput.required = false
      repoSelect.required = true
      if (repoSelect.value) fetchAndBuildTree(repoSelect.value, baseBranchSelect.value)
    } else {
      selectZipBtn.classList.add("active")
      selectGithubBtn.classList.remove("active")
      zipInputs.classList.remove("hidden")
      githubInputs.classList.add("hidden")
      zipFileInput.required = true
      repoSelect.required = false
    }
  }

  const handleFormSubmit = (e) => {
    e.preventDefault()
    resetProgressView()
    showView("live-progress-view")
    submitBtn.disabled = true

    const formData = new FormData(docForm)
    const endpoint = selectGithubBtn.classList.contains("active") ? "/process-github" : "/process-zip"

    const headers = new Headers()
    if (endpoint === "/process-github") {
      headers.append("Authorization", `Bearer ${localStorage.getItem(GITHUB_TOKEN_KEY)}`)
    }

    const options = { method: "POST", body: formData, headers: headers }

    fetch(endpoint, options)
      .then((response) => {
        if (!response.ok) {
          return response.json().then((errData) => {
            throw new Error(`Server error: ${response.status} - ${errData.detail || "Unknown error"}`)
          })
        }
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        function push() {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                if (buffer) {
                  try {
                    const json = JSON.parse(buffer)
                    handleStreamEvent(json.type, json.payload)
                  } catch (e) {
                    console.error("Error parsing final buffer chunk:", buffer, e)
                  }
                }
                return
              }
              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split("\n")
              buffer = lines.pop()
              for (const line of lines) {
                if (line.trim() === "") continue
                try {
                  const json = JSON.parse(line)
                  handleStreamEvent(json.type, json.payload)
                } catch (e) {
                  console.error("Failed to parse JSON line:", line, e)
                }
              }
              push()
            })
            .catch((err) => {
              console.error("Stream reading error:", err)
              handleStreamEvent("error", `Stream error: ${err.message}`)
            })
        }
        push()
      })
      .catch((err) => handleStreamEvent("error", `${err.message}`))
  }

  const handleStreamEvent = (type, payload) => {
    switch (type) {
      case "phase": {
        const phaseEl = document.getElementById(`phase-${payload.id}`)
        if (phaseEl) phaseEl.dataset.status = payload.status
        break
      }
      case "subtask": {
        const subtaskId = sanitizeForId(payload.id)
        let subtaskEl = document.getElementById(subtaskId)
        const listEl = document.getElementById(payload.listId)
        if (!subtaskEl && listEl) {
          subtaskEl = document.createElement("li")
          subtaskEl.id = subtaskId
          subtaskEl.textContent = payload.name
          listEl.appendChild(subtaskEl)
        }
        if (subtaskEl) subtaskEl.dataset.status = payload.status
        break
      }
      case "log": {
        logOutput.textContent += payload.message.replace(/\\n/g, "\n") + "\n"
        logOutput.scrollTop = logOutput.scrollHeight
        break
      }
      case "error": {
        document
          .querySelectorAll('.phase-item[data-status="in-progress"]')
          .forEach((el) => (el.dataset.status = "error"))
        logOutput.textContent += `\n\n--- ERROR ---\n${payload}\n`
        submitBtn.disabled = false
        break
      }
      case "done": {
        showView("result-section")
        resultLink.innerHTML = `<p>${payload.message}</p>`
        if (payload.type === "zip") {
          resultLink.innerHTML += `<a href="/download/${payload.download_path}" class="button-link" download>Download ZIP</a>`
        } else if (payload.url) {
          const linkText = payload.url.includes("/pull/new/") ? "Create Pull Request" : "View Repository"
          resultLink.innerHTML += `<a href="${payload.url}" target="_blank" rel="noopener noreferrer" class="button-link">${linkText}</a>`
        }
        submitBtn.disabled = false
        break
      }
    }
  }

  // --- Events ---
  githubLoginBtn.addEventListener("click", () => (window.location.href = "/login/github"))
  selectZipBtn.addEventListener("click", () => switchMode("zip"))
  selectGithubBtn.addEventListener("click", () => switchMode("github"))
  docForm.addEventListener("submit", handleFormSubmit)

  repoSelect.addEventListener("change", async (e) => {
    const selectedOption = e.target.options[e.target.selectedIndex]
    const repoFullName = selectedOption.value
    const defaultBranch = selectedOption.dataset.defaultBranch || ""

    if (repoFullName) {
      await fetchRepoBranches(repoFullName, defaultBranch)
      fetchAndBuildTree(repoFullName, baseBranchSelect.value)
      checkBranchName()
    } else {
      baseBranchSelect.innerHTML = ""
      fileTreeContainer.classList.add("hidden")
    }
  })

  baseBranchSelect.addEventListener("change", () => {
    fetchAndBuildTree(repoSelect.value, baseBranchSelect.value)
  })

  newBranchInput.addEventListener("blur", checkBranchName)

  // Initialize
  handleAuth()

  // --- UI Enhancements: glow cursor on buttons ---
  document.querySelectorAll(".btn-glow").forEach((btn) => {
    btn.addEventListener("pointermove", (e) => {
      const rect = btn.getBoundingClientRect()
      const x = ((e.clientX - rect.left) / rect.width) * 100
      const y = ((e.clientY - rect.top) / rect.height) * 100
      btn.style.setProperty("--x", x + "%")
      btn.style.setProperty("--y", y + "%")
    })
  })

  // --- Ripple effect for buttons and links ---
  function addRipple(e) {
    const el = e.currentTarget
    const rect = el.getBoundingClientRect()
    const circle = document.createElement("span")
    circle.className = "ripple"
    circle.style.left = `${e.clientX - rect.left}px`
    circle.style.top = `${e.clientY - rect.top}px`
    el.appendChild(circle)
    setTimeout(() => circle.remove(), 600)
  }
  document.querySelectorAll("button.btn, .button-link").forEach((el) => {
    el.addEventListener("click", addRipple)
  })

  // --- Subtle parallax tilt on hover for panels and phase items ---
  const tiltEls = document.querySelectorAll(".panel, .phase-item, .terminal, .glass-card")
  tiltEls.forEach((el) => {
    let enter = false
    el.addEventListener("pointerenter", () => {
      enter = true
    })
    el.addEventListener("pointerleave", () => {
      enter = false
      el.style.transform = ""
    })
    el.addEventListener("pointermove", (e) => {
      if (!enter) return
      const rect = el.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const dx = (e.clientX - cx) / rect.width
      const dy = (e.clientY - cy) / rect.height
      const max = 6
      el.style.transform = `rotateX(${(-dy * max).toFixed(2)}deg) rotateY(${(dx * max).toFixed(2)}deg) translateZ(0)`
    })
  })

  // --- Optional: lightweight animated background canvas (respects reduced motion) ---
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const canvas = document.getElementById("bg-canvas")
  if (canvas && !prefersReduced) {
    const ctx = canvas.getContext("2d", { alpha: true })
    let w, h, dots
    function resize() {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
      dots = Array.from({ length: Math.min(90, Math.floor((w * h) / 60000)) }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
      }))
    }
    function step() {
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = "rgba(34, 211, 238, 0.6)"
      const threshold = 120
      for (let i = 0; i < dots.length; i++) {
        const a = dots[i]
        a.x += a.vx
        a.y += a.vy
        if (a.x < 0 || a.x > w) a.vx *= -1
        if (a.y < 0 || a.y > h) a.vy *= -1
        ctx.beginPath()
        ctx.arc(a.x, a.y, 1.2, 0, Math.PI * 2)
        ctx.fill()
        for (let j = i + 1; j < dots.length; j++) {
          const b = dots[j]
          const dx = a.x - b.x,
            dy = a.y - b.y
          const dist = Math.hypot(dx, dy)
          if (dist < threshold) {
            const alpha = (1 - dist / threshold) * 0.2
            ctx.strokeStyle = `rgba(96,165,250,${alpha})`
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
      }
      requestAnimationFrame(step)
    }
    window.addEventListener("resize", resize)
    resize()
    step()
  }
})
