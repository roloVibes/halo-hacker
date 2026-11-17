// HackerOne programs browser — renders h1/programs.json from halo-hacker's pack-data directory.
// Data flow: sync mount creates the shell, async fetch reads data through the Studio HTTP data API,
// then interval polling and SSE pack_event frames refresh the view; untrusted fields only hit textContent.

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

const DATA_ROOT = "/api/pack/halo-hacker/data/";
const STATE_COLORS = {
    open: "#3fb950",
    closed: "#6e7681",
    paused: "#d29922",
    enabled: "#3fb950",
    disabled: "#6e7681",
    public: "#58a6ff",
    private: "#a371f7"
};

function dataUrl(path) {
    return DATA_ROOT + path.split("/").map(encodeURIComponent).join("/");
}

function fetchJson(path, emptyValue) {
    const headers = {};
    const token = sessionStorage.getItem("halo-studio-token");
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch(path, { headers }).then(r => {
        if (r.status === 404) return JSON.stringify(emptyValue);
        if (!r.ok) throw new Error(path + " -> HTTP " + r.status);
        return r.text();
    });
}

function badge(text, color) {
    const wrap = h("span", null);
    css(wrap, {
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        border: "1px solid #30363d",
        borderRadius: "999px",
        padding: "2px 8px",
        whiteSpace: "nowrap",
        fontSize: "12px",
        color: "#e6edf3",
        background: "#161b22"
    });
    const dot = h("span", null);
    css(dot, { display: "inline-block", width: "8px", height: "8px", borderRadius: "999px", background: color || "#6e7681" });
    wrap.append(dot, text || "unknown");
    return wrap;
}

function button(text) {
    const btn = h("button", null, text);
    css(btn, {
        background: "#21262d",
        border: "1px solid #30363d",
        color: "#e6edf3",
        borderRadius: "6px",
        padding: "5px 10px",
        cursor: "pointer",
        fontSize: "12px"
    });
    return btn;
}

function card() {
    const div = h("div", null);
    css(div, { background: "#161b22", border: "1px solid #30363d", borderRadius: "8px", padding: "12px", marginBottom: "14px" });
    return div;
}

function sectionTitle(text) {
    const title = h("h2", null, text);
    css(title, { margin: "0 0 10px 0", fontSize: "15px", color: "#e6edf3" });
    return title;
}

function muted(text) {
    const span = h("span", null, text);
    css(span, { color: "#8b949e" });
    return span;
}

function formatMoney(value) {
    const n = Number(value || 0);
    try { return n.toLocaleString("en-US", { style: "currency", currency: "USD" }); }
    catch (_) { return "$" + n.toFixed(2); }
}

function isMyProgram(program) {
    return program.last_invitation_accepted_at_for_user != null || Number(program.number_of_reports_for_user || 0) > 0;
}

function submissionColor(state) {
    return STATE_COLORS[state] || "#6e7681";
}

export function mount(el, api) {
    const state = {
        programs: [],
        generated: null,
        expandedPrograms: new Set(),
        showAll: false,
        lastJson: null,
        loading: true,
        error: "",
        timer: null,
        eventSource: null
    };

    const root = h("div", null);
    css(root, { display: "flex", flexDirection: "column", height: "100%", minHeight: "0", color: "#e6edf3", fontSize: "14px", lineHeight: "1.45" });
    el.appendChild(root);

    const header = h("div", null);
    css(header, { padding: "12px 16px", borderBottom: "1px solid #30363d", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" });
    root.appendChild(header);

    const title = h("div", null, "HackerOne programs");
    css(title, { fontWeight: "bold", fontSize: "16px" });
    header.appendChild(title);

    const refreshBtn = button("Refresh");
    header.appendChild(refreshBtn);

    const content = h("div", null);
    css(content, { flex: "1", overflow: "auto", padding: "16px" });
    root.appendChild(content);

    async function load() {
        try {
            const text = await fetchJson(dataUrl("h1/programs.json"), { generated: null, programs: [] });
            if (text === state.lastJson && !state.loading) return;
            state.lastJson = text;
            const data = JSON.parse(text || "{}");
            state.programs = data.programs || [];
            state.generated = data.generated || null;
            state.loading = false;
            state.error = "";
            render();
        } catch (e) {
            state.loading = false;
            state.error = e.message || String(e);
            render();
        }
    }

    function render() {
        content.replaceChildren();
        if (state.loading) {
            const div = h("div", null, "Loading programs...");
            css(div, { color: "#8b949e", padding: "32px", textAlign: "center" });
            content.appendChild(div);
            return;
        }
        if (state.error) renderError();
        renderMyPrograms();
        renderAllPrograms();
        renderFooter();
    }

    function renderError() {
        const div = card();
        css(div, { borderColor: "#f85149", color: "#f85149" });
        div.append("Error loading programs: " + state.error + " ");
        const retry = button("Retry");
        retry.addEventListener("click", load);
        div.appendChild(retry);
        content.appendChild(div);
    }

    function renderMyPrograms() {
        const my = state.programs.filter(isMyProgram).sort((a, b) => Number(b.bounty_earned_for_user || 0) - Number(a.bounty_earned_for_user || 0));
        const wrap = card();
        wrap.appendChild(sectionTitle(`My programs (${my.length})`));
        if (!state.programs.length) {
            wrap.appendChild(empty("No data yet — run a sync."));
            content.appendChild(wrap);
            return;
        }
        if (!my.length) {
            wrap.appendChild(empty("No accepted or previously reported programs in the synced data."));
            content.appendChild(wrap);
            return;
        }
        const table = h("table", null);
        css(table, { width: "100%", borderCollapse: "collapse", fontSize: "13px" });
        const thead = h("thead", null);
        const headRow = h("tr", null);
        for (const label of ["Handle", "Name", "Submission", "Reports", "Valid", "Earned"]) {
            const th = h("th", null, label);
            css(th, { textAlign: "left", padding: "8px", borderBottom: "1px solid #30363d", color: "#8b949e", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.05em" });
            headRow.appendChild(th);
        }
        thead.appendChild(headRow);
        table.appendChild(thead);
        const tbody = h("tbody", null);
        table.appendChild(tbody);
        for (const program of my) renderProgramRows(tbody, program, true);
        wrap.appendChild(table);
        content.appendChild(wrap);
    }

    function renderProgramRows(tbody, program, detailedTable) {
        const handle = program.handle || program.name || "unknown";
        const open = state.expandedPrograms.has(handle);
        const tr = h("tr", null);
        css(tr, { cursor: "pointer" });
        tr.addEventListener("click", () => {
            if (open) state.expandedPrograms.delete(handle);
            else state.expandedPrograms.add(handle);
            render();
        });
        const cells = detailedTable ? [
            `${open ? "▾" : "▸"} ${handle}`,
            program.name || "—",
            null,
            String(program.number_of_reports_for_user || 0),
            String(program.number_of_valid_reports_for_user || 0),
            formatMoney(program.bounty_earned_for_user)
        ] : [`${open ? "▾" : "▸"} ${program.name || handle}`, null];
        for (let i = 0; i < cells.length; i++) {
            const td = h("td", null);
            css(td, { padding: "7px 8px", borderBottom: "1px solid #30363d", verticalAlign: "top" });
            if ((detailedTable && i === 2) || (!detailedTable && i === 1)) td.appendChild(badge(program.submission_state || "unknown", submissionColor(program.submission_state)));
            else td.append(cells[i] || "");
            tr.appendChild(td);
        }
        tbody.appendChild(tr);
        if (open) renderDetailRow(tbody, program, detailedTable ? 6 : 2);
    }

    function renderDetailRow(tbody, program, colspan) {
        const tr = h("tr", null);
        const td = h("td", { colspan: String(colspan) });
        css(td, { padding: "0 8px 10px 8px", borderBottom: "1px solid #30363d" });
        const box = h("div", null);
        css(box, { background: "#0d1117", border: "1px solid #30363d", borderRadius: "6px", padding: "10px" });

        const policyTitle = h("div", null, "Policy preview");
        css(policyTitle, { fontWeight: "bold", marginBottom: "4px" });
        box.appendChild(policyTitle);
        const policyText = String(program.policy || "No policy text synced.").slice(0, 500);
        const policy = h("div", null, policyText + (String(program.policy || "").length > 500 ? "…" : ""));
        css(policy, { color: "#8b949e", whiteSpace: "pre-wrap", marginBottom: "10px" });
        box.appendChild(policy);

        const meta = h("div", null);
        css(meta, { display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" });
        meta.appendChild(infoChip("Weaknesses", String(program.weaknesses_count || 0)));
        meta.appendChild(infoChip("State", program.state || "unknown"));
        meta.appendChild(infoChip("Offers bounties", program.offers_bounties ? "yes" : "no"));
        box.appendChild(meta);

        const scopeTitle = h("div", null, "Scopes");
        css(scopeTitle, { fontWeight: "bold", marginBottom: "6px" });
        box.appendChild(scopeTitle);
        const scopes = Array.isArray(program.scopes) ? program.scopes : [];
        if (!scopes.length) {
            box.appendChild(empty("No scope entries synced."));
        } else {
            for (const scope of scopes) box.appendChild(scopeRow(scope));
        }
        td.appendChild(box);
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    function infoChip(label, value) {
        const chip = h("div", null);
        css(chip, { border: "1px solid #30363d", borderRadius: "999px", padding: "4px 8px", background: "#161b22", display: "flex", gap: "6px" });
        const v = h("strong", null, value);
        chip.append(v, muted(label));
        return chip;
    }

    function scopeRow(scope) {
        const row = h("div", null);
        css(row, { borderTop: "1px solid #30363d", padding: "8px 0" });
        const top = h("div", null);
        css(top, { display: "grid", gridTemplateColumns: "minmax(180px, 1fr) 120px 110px", gap: "8px", alignItems: "center" });
        const asset = h("div", null, `${scope.asset_identifier || "unnamed asset"}`);
        css(asset, { fontFamily: "ui-monospace, monospace", fontSize: "12px" });
        top.appendChild(asset);
        top.appendChild(badge(scope.eligible_for_bounty ? "bounty" : "no bounty", scope.eligible_for_bounty ? "#3fb950" : "#6e7681"));
        top.appendChild(muted(scope.max_severity || "severity —"));
        row.appendChild(top);
        const details = [];
        if (scope.asset_type) details.push("Type: " + scope.asset_type);
        if (scope.eligible_for_submission === false) details.push("Not eligible for submission");
        if (scope.instruction) details.push(scope.instruction);
        if (details.length) {
            const instruction = h("div", null, details.join(" · "));
            css(instruction, { color: "#8b949e", fontSize: "12px", marginTop: "4px", whiteSpace: "pre-wrap" });
            row.appendChild(instruction);
        }
        return row;
    }

    function renderAllPrograms() {
        const rest = state.programs.filter(p => !isMyProgram(p)).sort((a, b) => String(a.name || a.handle || "").localeCompare(String(b.name || b.handle || "")));
        const wrap = card();
        const head = h("button", null, `${state.showAll ? "▾" : "▸"} All programs directory (${rest.length})`);
        css(head, { background: "transparent", border: "0", color: "#e6edf3", cursor: "pointer", fontWeight: "bold", fontSize: "15px", padding: "0", textAlign: "left" });
        head.addEventListener("click", () => {
            state.showAll = !state.showAll;
            render();
        });
        wrap.appendChild(head);
        if (state.showAll) {
            if (!rest.length) wrap.appendChild(empty("No additional programs in the synced data."));
            else {
                const table = h("table", null);
                css(table, { width: "100%", borderCollapse: "collapse", fontSize: "13px", marginTop: "10px" });
                const tbody = h("tbody", null);
                table.appendChild(tbody);
                for (const program of rest) renderProgramRows(tbody, program, false);
                wrap.appendChild(table);
            }
        }
        content.appendChild(wrap);
    }

    function renderFooter() {
        const footer = h("div", null);
        css(footer, { color: "#8b949e", fontSize: "12px", padding: "2px 0 12px 0" });
        footer.textContent = `Generated: ${state.generated || "never"} · syncing via /hh-bounty sync`;
        content.appendChild(footer);
    }

    function empty(text) {
        const div = h("div", null, text);
        css(div, { color: "#8b949e", padding: "12px", textAlign: "center" });
        return div;
    }

    function startLiveUpdates() {
        state.timer = setInterval(load, 30000);
        const token = sessionStorage.getItem("halo-studio-token");
        if (token && typeof EventSource !== "undefined") {
            try {
                state.eventSource = new EventSource(`/api/events?t=${encodeURIComponent(token)}`);
                state.eventSource.addEventListener("message", (e) => {
                    try {
                        const msg = JSON.parse(e.data);
                        if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") load();
                    } catch (_) {}
                });
            } catch (_) {}
        }
    }

    refreshBtn.addEventListener("click", load);
    load();
    startLiveUpdates();

    return () => {
        if (state.timer) clearInterval(state.timer);
        if (state.eventSource) state.eventSource.close();
        el.removeChild(root);
    };
}
