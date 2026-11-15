// Projects — multi-program switcher for bug bounty workflows
// Loaded as ES module: import(url) → { mount(el, api) }

// Local DOM helpers (no imports: CSP forbids external code).
function h(tag, props, ...children) {
    const el = document.createElement(tag);
    if (props) {
        for (const [k, v] of Object.entries(props)) {
            if (k === "style") Object.assign(el.style, v);
            else el.setAttribute(k, v);
        }
    }
    for (const c of children) {
        if (c === null || c === undefined) continue;
        el.append(c);
    }
    return el;
}

function css(el, styleObj) {
    Object.assign(el.style, styleObj);
}

function badge(color, text) {
    const wrap = h("span", null);
    css(wrap, { whiteSpace: "nowrap", marginRight: "10px" });
    const dot = h("span", null);
    css(dot, { display: "inline-block", width: "8px", height: "8px",
               borderRadius: "999px", background: color, marginRight: "6px" });
    wrap.append(dot, text);
    return wrap;
}

// A 404 on a pack data file is NOT an error for this panel: projects.json is
// only written once the first project is created, so a fresh install (zero
// projects) is the normal state. Treat it as an empty project list.
function fetchJson(path) {
    const headers = {};
    const token = sessionStorage.getItem("halo-studio-token");
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch(path, { headers }).then(r => {
        if (r.status === 404) return JSON.stringify({ projects: [], active_project: null, generated: null });
        if (!r.ok) throw new Error(path + " -> HTTP " + r.status);
        return r.text();
    });
}

const PLATFORM_COLORS = {
    H1: "#f4711f",
    BC: "#2f6feb",
    IG: "#1a7f37"
};
const CUSTOM_PLATFORM_COLOR = "#8a8f98";

const PROJECT_STATE_COLORS = {
    active: "#1a7f37",
    paused: "#9a6700",
    archived: "#6e7681"
};

const LIST_URL = "api/pack/halo-hacker/data/projects.json";

export function mount(el, api) {
    const state = {
        projects: [],
        activeProject: null,
        generated: null,
        lastJson: null,
        showNewForm: false,
        timer: null,
        errored: false
    };

    // Root container
    const root = h("div", null);
    css(root, {
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: "0",
        color: "#e6edf3",
        fontSize: "14px",
        lineHeight: "1.5"
    });
    el.appendChild(root);

    // Header strip
    const header = h("div", null);
    css(header, {
        padding: "12px 16px",
        borderBottom: "1px solid #30363d",
        display: "flex",
        alignItems: "center",
        gap: "16px",
        flexWrap: "wrap"
    });
    root.appendChild(header);

    const headerTitle = h("span", null);
    css(headerTitle, { fontWeight: "bold", fontSize: "16px" });
    header.appendChild(headerTitle);

    const headerCounts = h("span", null);
    css(headerCounts, { color: "#8b949e", fontSize: "13px" });
    header.appendChild(headerCounts);

    const newBtn = h("button", null, "+ New Project");
    css(newBtn, {
        background: "#21262d",
        border: "1px solid #30363d",
        color: "#e6edf3",
        borderRadius: "6px",
        padding: "4px 10px",
        cursor: "pointer",
        fontSize: "13px",
        fontWeight: "bold"
    });
    header.appendChild(newBtn);

    const refreshBtn = h("button", null, "Refresh");
    css(refreshBtn, {
        background: "#21262d",
        border: "1px solid #30363d",
        color: "#e6edf3",
        borderRadius: "6px",
        padding: "4px 10px",
        cursor: "pointer",
        fontSize: "13px"
    });
    header.appendChild(refreshBtn);

    // Content area
    const content = h("div", null);
    css(content, {
        flex: "1",
        overflow: "auto",
        padding: "16px"
    });
    root.appendChild(content);

    // ─── Helpers ───────────────────────────────────────────────────

    function getToken() {
        return sessionStorage.getItem("halo-studio-token");
    }

    function platformColor(platform) {
        if (!platform) return CUSTOM_PLATFORM_COLOR;
        return PLATFORM_COLORS[platform] || CUSTOM_PLATFORM_COLOR;
    }

    function stateColor(st) {
        return PROJECT_STATE_COLORS[st] || "#6e7681";
    }

    function formatDate(dateStr) {
        if (!dateStr) return "";
        // Try to show a relative-ish short date
        try {
            const d = new Date(dateStr);
            if (d.toString() === "Invalid Date") return dateStr;
            const now = new Date();
            const diffMs = now - d;
            const diffDays = Math.floor(diffMs / 86400000);
            if (diffDays < 0) return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
            if (diffDays === 0) return "Today";
            if (diffDays === 1) return "Yesterday";
            if (diffDays < 7) return `${diffDays}d ago`;
            if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
            return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        } catch (_) {
            return dateStr;
        }
    }

    // ─── Data loading ──────────────────────────────────────────────

    async function loadList() {
        if (state.errored) return; // a failing endpoint is retried by Refresh/Retry, not by every poll/SSE tick
        try {
            const json = await fetchJson(LIST_URL);
            if (json === state.lastJson) return;
            state.lastJson = json;
            const data = JSON.parse(json);
            state.projects = data.projects || [];
            state.activeProject = data.active_project || null;
            state.generated = data.generated || null;
            state.errored = false;
            updateHeader();
            renderList();
        } catch (e) {
            renderError(e.message);
        }
    }

    function updateHeader() {
        const count = state.projects.length;
        headerTitle.textContent = `Projects (${count})`;

        const active = state.projects.find(p => {
            const id = p.program_id || p.id;
            return id === state.activeProject;
        });
        if (active) {
            const name = active.program_name || active.name || active.program_id || active.id || "";
            headerCounts.textContent = `Active: ${name}`;
        } else if (state.activeProject) {
            headerCounts.textContent = `Active: ${state.activeProject}`;
        } else {
            headerCounts.textContent = `No active project`;
        }
    }

    // ─── New project form ──────────────────────────────────────────

    function toggleNewForm() {
        state.showNewForm = !state.showNewForm;
        renderList();
    }

    function renderNewForm() {
        const formContainer = h("div", null);
        css(formContainer, {
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: "6px",
            padding: "16px",
            marginBottom: "16px"
        });
        content.appendChild(formContainer);

        const formTitle = h("h3", null, "New project");
        css(formTitle, {
            color: "#e6edf3",
            fontSize: "15px",
            fontWeight: "bold",
            margin: "0 0 12px 0"
        });
        formContainer.appendChild(formTitle);

        // Fields
        const fields = [
            { label: "Program name", id: "np-name", type: "text", placeholder: "e.g. Acme Corp VDP" },
            { label: "Platform", id: "np-platform", type: "select", options: ["H1", "BC", "IG", "custom"] },
            { label: "Engagement ID", id: "np-eng", type: "text", placeholder: "e.g. ENG-2026-001" }
        ];

        for (const field of fields) {
            const row = h("div", null);
            css(row, { marginBottom: "10px" });
            formContainer.appendChild(row);

            const label = h("label", null, field.label);
            css(label, {
                display: "block",
                color: "#8b949e",
                fontSize: "12px",
                marginBottom: "4px"
            });
            row.appendChild(label);

            if (field.type === "select") {
                const sel = h("select", null);
                css(sel, {
                    background: "#0d1117",
                    border: "1px solid #30363d",
                    color: "#e6edf3",
                    borderRadius: "6px",
                    padding: "6px 8px",
                    fontSize: "13px",
                    width: "100%"
                });
                sel.id = field.id;
                for (const opt of field.options) {
                    const o = h("option", null, opt);
                    o.value = opt === "custom" ? "" : opt;
                    sel.appendChild(o);
                }
                row.appendChild(sel);
            } else {
                const inp = h("input", null);
                inp.type = field.type;
                inp.placeholder = field.placeholder;
                inp.id = field.id;
                css(inp, {
                    background: "#0d1117",
                    border: "1px solid #30363d",
                    color: "#e6edf3",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    fontSize: "13px",
                    width: "100%"
                });
                row.appendChild(inp);
            }
        }

        // Buttons
        const btnRow = h("div", null);
        css(btnRow, {
            display: "flex",
            gap: "8px",
            marginTop: "12px"
        });
        formContainer.appendChild(btnRow);

        const submitBtn = h("button", null, "Create");
        css(submitBtn, {
            background: "#1a7f37",
            border: "none",
            color: "#ffffff",
            borderRadius: "6px",
            padding: "6px 16px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: "bold"
        });
        btnRow.appendChild(submitBtn);

        const cancelBtn = h("button", null, "Cancel");
        css(cancelBtn, {
            background: "#21262d",
            border: "1px solid #30363d",
            color: "#e6edf3",
            borderRadius: "6px",
            padding: "6px 16px",
            cursor: "pointer",
            fontSize: "13px"
        });
        btnRow.appendChild(cancelBtn);

        cancelBtn.addEventListener("click", toggleNewForm);

        // Feedback area
        const feedback = h("div", null);
        css(feedback, { color: "#8b949e", fontSize: "12px", marginTop: "8px" });
        formContainer.appendChild(feedback);

        submitBtn.addEventListener("click", async () => {
            const nameEl = document.getElementById("np-name");
            const platformEl = document.getElementById("np-platform");
            const engEl = document.getElementById("np-eng");
            const name = nameEl ? nameEl.value.trim() : "";
            const platform = platformEl ? platformEl.value : "";
            const engagementId = engEl ? engEl.value.trim() : "";

            if (!name) {
                feedback.textContent = "Program name is required.";
                feedback.style.color = "#d7263d";
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = "Creating...";
            feedback.textContent = "";
            feedback.style.color = "#8b949e";

            try {
                await createProject({
                    program_name: name,
                    platform: platform || "custom",
                    engagement_id: engagementId
                });
                feedback.textContent = "Project created.";
                feedback.style.color = "#1a7f37";
                state.showNewForm = false;
                await loadList();
            } catch (e) {
                feedback.textContent = `Error: ${e.message}`;
                feedback.style.color = "#d7263d";
                submitBtn.disabled = false;
                submitBtn.textContent = "Create";
            }
        });
    }

    async function createProject(data) {
        const token = getToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = "Bearer " + token;
        const resp = await fetch("api/pack/halo-hacker/projects", {
            method: "POST",
            headers,
            body: JSON.stringify(data)
        });
        if (!resp.ok) {
            let detail = "";
            try { const j = await resp.json(); detail = j.error || j.detail || ""; } catch (_) {}
            throw new Error(`HTTP ${resp.status}${detail ? " — " + detail : ""}`);
        }
    }

    // ─── Switch / archive actions ──────────────────────────────────

    async function switchProject(programId) {
        if (!programId || programId === state.activeProject) return;

        // Try api object first (provided by Studio host)
        if (api && typeof api.setConfig === "function") {
            try {
                await api.setConfig({ active_project: programId });
                state.activeProject = programId;
                updateHeader();
                renderList();
                return;
            } catch (_) {
                // Fall through to direct fetch
            }
        }

        const token = getToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = "Bearer " + token;
        const resp = await fetch("api/pack/halo-hacker/config", {
            method: "POST",
            headers,
            body: JSON.stringify({ active_project: programId })
        });
        if (!resp.ok) {
            let detail = "";
            try { const j = await resp.json(); detail = j.error || j.detail || ""; } catch (_) {}
            throw new Error(`Failed to switch: HTTP ${resp.status}${detail ? " — " + detail : ""}`);
        }
        state.activeProject = programId;
        updateHeader();
        renderList();
    }

    async function archiveProject(programId) {
        const token = getToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = "Bearer " + token;
        const resp = await fetch(`api/pack/halo-hacker/projects/${encodeURIComponent(programId)}/archive`, {
            method: "POST",
            headers
        });
        if (!resp.ok) {
            let detail = "";
            try { const j = await resp.json(); detail = j.error || j.detail || ""; } catch (_) {}
            throw new Error(`Failed to archive: HTTP ${resp.status}${detail ? " — " + detail : ""}`);
        }
        await loadList();
    }

    // ─── Renderers ─────────────────────────────────────────────────

    function renderList() {
        content.replaceChildren();

        if (state.showNewForm) {
            renderNewForm();
        }

        // Loading state
        if (state.lastJson === null) {
            const spinner = h("div", null, "Loading projects...");
            css(spinner, {
                color: "#8b949e",
                padding: "32px",
                textAlign: "center",
                fontSize: "14px"
            });
            content.appendChild(spinner);
            return;
        }

        // Empty state
        if (state.projects.length === 0) {
            const empty = h("div", null);
            css(empty, {
                color: "#8b949e",
                padding: "32px",
                textAlign: "center",
                fontSize: "14px"
            });
            empty.textContent = "No projects yet. Click \"+ New Project\" to create one.";
            content.appendChild(empty);
            return;
        }

        // Table
        const table = h("table", null);
        css(table, {
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "13px"
        });
        content.appendChild(table);

        // Header row
        const thead = h("thead", null);
        table.appendChild(thead);
        const headerRow = h("tr", null);
        thead.appendChild(headerRow);
        const headerCells = ["Program", "Platform", "Engagement", "Findings", "State", "Last activity", ""];
        for (const text of headerCells) {
            const th = h("th", null, text);
            css(th, {
                padding: "8px",
                textAlign: "left",
                borderBottom: "1px solid #30363d",
                position: "sticky",
                top: "0",
                background: "#0d1117",
                color: "#8b949e",
                fontWeight: "bold",
                fontSize: "12px",
                textTransform: "uppercase",
                letterSpacing: "0.05em"
            });
            headerRow.appendChild(th);
        }

        // Body
        const tbody = h("tbody", null);
        table.appendChild(tbody);

        for (let i = 0; i < state.projects.length; i++) {
            const p = state.projects[i];
            const programId = p.program_id || p.id;
            const isActive = programId === state.activeProject;
            const tr = h("tr", null);
            tr.dataset.index = i;
            tr.dataset.id = programId || "";
            css(tr, {
                cursor: "pointer",
                padding: "4px 8px"
            });

            // Active project highlight
            if (isActive) {
                css(tr, { background: "rgba(88,166,255,0.16)" });
            }

            tr.addEventListener("mouseenter", () => {
                if (!isActive) {
                    css(tr, { background: "rgba(88,166,255,0.08)" });
                }
            });
            tr.addEventListener("mouseleave", () => {
                if (!isActive) {
                    css(tr, { background: "transparent" });
                }
            });
            tr.addEventListener("click", async () => {
                if (!isActive && programId) {
                    try {
                        await switchProject(programId);
                    } catch (e) {
                        renderError(e.message);
                    }
                }
            });
            tbody.appendChild(tr);

            // Program name cell
            const nameCell = h("td", null, p.program_name || p.name || programId || "");
            css(nameCell, {
                padding: "4px 8px",
                borderBottom: "1px solid #30363d",
                fontWeight: isActive ? "bold" : "normal"
            });
            if (isActive) {
                // Add an accent marker for the active project
                const activeMarker = h("span", null, " ●");
                css(activeMarker, { color: "#58a6ff", fontWeight: "bold" });
                nameCell.appendChild(activeMarker);
            }
            tr.appendChild(nameCell);

            // Platform cell
            const platformCell = h("td", null);
            css(platformCell, { padding: "4px 8px", borderBottom: "1px solid #30363d" });
            const plat = p.platform || "";
            if (plat) {
                const color = platformColor(plat);
                const displayName = plat === "H1" ? "HackerOne"
                                   : plat === "BC" ? "Bugcrowd"
                                   : plat === "IG" ? "Intigriti"
                                   : plat === "custom" || !plat ? "Custom" : plat;
                platformCell.appendChild(badge(color, displayName));
            }
            tr.appendChild(platformCell);

            // Engagement ID cell
            const engCell = h("td", null, p.engagement_id || "");
            css(engCell, {
                padding: "4px 8px",
                borderBottom: "1px solid #30363d",
                fontFamily: "ui-monospace, monospace",
                fontSize: "12px",
                color: "#8b949e"
            });
            tr.appendChild(engCell);

            // Finding count cell
            const countCell = h("td", null);
            css(countCell, { padding: "4px 8px", borderBottom: "1px solid #30363d" });
            if (p.finding_count != null) {
                countCell.textContent = String(p.finding_count);
            } else if (p.finding_count === undefined && p.findings_count != null) {
                countCell.textContent = String(p.findings_count);
            } else {
                countCell.textContent = "—";
            }
            tr.appendChild(countCell);

            // State cell
            const stateCell = h("td", null);
            css(stateCell, { padding: "4px 8px", borderBottom: "1px solid #30363d" });
            const st = p.state || "active";
            stateCell.appendChild(badge(stateColor(st), st));
            tr.appendChild(stateCell);

            // Last activity cell
            const activityCell = h("td", null, formatDate(p.last_activity || p.updated_at || p.created_at || ""));
            css(activityCell, {
                padding: "4px 8px",
                borderBottom: "1px solid #30363d",
                fontFamily: "ui-monospace, monospace",
                fontSize: "12px",
                color: "#8b949e"
            });
            tr.appendChild(activityCell);

            // Actions cell
            const actionsCell = h("td", null);
            css(actionsCell, { padding: "4px 8px", borderBottom: "1px solid #30363d" });

            // Archive button (not on active project)
            if (!isActive && st !== "archived") {
                const archiveBtn = h("button", null, "Archive");
                css(archiveBtn, {
                    background: "#21262d",
                    border: "1px solid #30363d",
                    color: "#e6edf3",
                    borderRadius: "6px",
                    padding: "2px 8px",
                    cursor: "pointer",
                    fontSize: "12px"
                });
                archiveBtn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    if (programId) {
                        try {
                            await archiveProject(programId);
                        } catch (e) {
                            renderError(e.message);
                        }
                    }
                });
                actionsCell.appendChild(archiveBtn);
            } else if (st === "archived") {
                const archivedLabel = h("span", null, "Archived");
                css(archivedLabel, { color: "#6e7681", fontSize: "12px", fontStyle: "italic" });
                actionsCell.appendChild(archivedLabel);
            } else if (isActive) {
                const activeLabel = h("span", null, "Active");
                css(activeLabel, { color: "#1a7f37", fontSize: "12px", fontWeight: "bold" });
                actionsCell.appendChild(activeLabel);
            }

            tr.appendChild(actionsCell);
        }
    }

    function renderError(msg) {
        state.errored = true; // SSE / poll must not hammer a failing endpoint
        content.replaceChildren();
        const div = h("div", null);
        css(div, {
            color: "#d7263d",
            padding: "32px",
            textAlign: "center"
        });
        const msgSpan = h("span", null, `Error loading projects: ${msg}`);
        div.appendChild(msgSpan);
        const retryBtn = h("button", null, "Retry");
        css(retryBtn, {
            background: "#21262d",
            border: "1px solid #30363d",
            color: "#e6edf3",
            borderRadius: "6px",
            padding: "4px 10px",
            cursor: "pointer",
            marginTop: "12px"
        });
        retryBtn.addEventListener("click", loadList);
        div.appendChild(retryBtn);
        content.appendChild(div);
    }

    // ─── Event wiring + initial load ───────────────────────────────

    newBtn.addEventListener("click", toggleNewForm);
    refreshBtn.addEventListener("click", loadList);

    // Live updates every 15 s
    function startLiveUpdates() {
        state.timer = setInterval(loadList, 15000);

        const token = getToken();
        if (token) {
            try {
                const es = new EventSource(`/api/events?t=${encodeURIComponent(token)}`);
                es.addEventListener("message", (e) => {
                    try {
                        const msg = JSON.parse(e.data);
                        if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") {
                            loadList();
                        }
                    } catch (_) {
                        // Ignore parse errors
                    }
                });
            } catch (_) {
                // EventSource not available or failed
            }
        }
    }

    loadList();
    startLiveUpdates();

    // Cleanup
    return () => {
        if (state.timer) clearInterval(state.timer);
        el.removeChild(root);
    };
}