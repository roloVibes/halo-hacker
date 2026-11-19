// Bug Bounty — merged HackerOne Studio bundle panel.
// Tab structure: one Studio panel titled "Bug Bounty" with in-panel tabs
// [ Overview | Reports | Intents | Programs ]. The tab buttons only switch pane
// visibility; the four pane roots stay mounted so Studio does not create extra pack
// tabs. Overview contains bounty stats/state/attention, Reports contains grouped
// report timelines, Intents contains the submission queue, and Programs contains
// the former bounty-programs browser.
// CSP/data rules: DOM nodes only, untrusted strings via textContent, CSSOM via
// css(), data from /api/pack/halo-hacker/data/ with the Studio Bearer token,
// 404 data files treated as empty, one 30s poll plus one pack-event SSE listener.

function h(tag, props, ...children) {
    const el = document.createElement(tag);
    if (props) for (const [k, v] of Object.entries(props)) {
        if (k === "className") el.className = v;
        else if (k !== "style") el.setAttribute(k, v);
    }
    for (const c of children) if (c !== null && c !== undefined) el.append(c);
    return el;
}

function css(el, styleObj) { Object.assign(el.style, styleObj); }

const DATA_ROOT = "/api/pack/halo-hacker/data/";
const DISMISS_KEY = "halo-hacker-bounty-pending-dismissed";
const PROGRAMS_PATH = "h1/programs.json";
const TAB_DEFS = [
    ["overview", "Overview"],
    ["reports", "Reports"],
    ["intents", "Intents"],
    ["programs", "Programs"]
];
const STATE_COLORS = {
    new: "#8b949e", triaged: "#58a6ff", "needs-more-info": "#d29922",
    resolved: "#3fb950", duplicate: "#6e7681", informative: "#6e7681",
    "not-applicable": "#6e7681", spam: "#f85149", draft: "#8b949e",
    pending: "#d29922", running: "#58a6ff", failed: "#f85149",
    ready_to_submit: "#3fb950", submitted: "#a371f7", open: "#3fb950",
    closed: "#6e7681", paused: "#d29922", enabled: "#3fb950",
    disabled: "#6e7681", public: "#58a6ff", private: "#a371f7"
};
const SEVERITY_COLORS = { critical: "#f85149", high: "#db6d28", medium: "#d29922", low: "#58a6ff", none: "#6e7681", unknown: "#6e7681" };

function dataUrl(path) { return DATA_ROOT + path.split("/").map(encodeURIComponent).join("/"); }

function fetchJson(path, emptyValue) {
    const headers = {};
    const token = sessionStorage.getItem("halo-studio-token");
    if (token) headers.Authorization = "Bearer " + token;
    return fetch(path, { headers }).then(r => {
        if (r.status === 404) return JSON.stringify(emptyValue);
        if (!r.ok) throw new Error(path + " -> HTTP " + r.status);
        return r.text();
    });
}

function stripMd(value) {
    let s = String(value || "").replace(/\r/g, "\n");
    s = s.replace(/```[a-zA-Z0-9_-]*\n?/g, " ").replace(/```/g, " ");
    s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
    s = s.replace(/^\s{0,3}#{1,6}\s*/gm, "").replace(/^\s{0,3}>\s?/gm, "");
    s = s.replace(/^\s{0,3}[-*+]\s+/gm, "").replace(/^\s{0,3}\d+[.)]\s+/gm, "");
    s = s.replace(/^\s*[-*_]{3,}\s*$/gm, " ");
    s = s.replace(/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/gm, " ");
    s = s.replace(/[\\#*_`~]/g, "").replace(/\s*\|\s*/g, " | ").replace(/\s+/g, " ").trim();
    return s;
}

function truncateText(value, max) {
    const s = stripMd(value);
    return s.length <= max ? s : s.slice(0, Math.max(0, max - 1)).trimEnd() + "…";
}

function formatMoney(value, wholeDollars) {
    const n = Number(value || 0);
    try {
        const options = { style: "currency", currency: "USD" };
        if (wholeDollars) options.maximumFractionDigits = 0;
        return n.toLocaleString("en-US", options);
    } catch (_) {
        return "$" + (wholeDollars ? Math.round(n).toLocaleString("en-US") : n.toFixed(2));
    }
}

function formatDate(value) {
    if (!value) return "—";
    try {
        const d = new Date(value);
        if (d.toString() === "Invalid Date") return String(value);
        return d.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (_) { return String(value); }
}

function lastActivity(report) {
    return report.last_program_activity_at || report.last_reporter_activity_at || report.bounty_awarded_at ||
        report.closed_at || report.triaged_at || report.created_at || "";
}

function countBy(items, field) {
    const counts = new Map();
    for (const item of items || []) {
        const key = item && item[field] ? String(item[field]) : "unknown";
        counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function asNumber(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n : 0;
}

function stateColor(state) { return STATE_COLORS[state] || "#6e7681"; }
function severityColor(sev) { return SEVERITY_COLORS[String(sev || "unknown").toLowerCase()] || "#6e7681"; }
function programKey(program) { return String(program.handle || program.name || "unknown"); }
function programName(program) { return String(program.name || program.handle || "Unnamed program"); }
function programHandle(program) { return String(program.handle || program.name || "unknown"); }
function isMyProgram(program) { return program.last_invitation_accepted_at_for_user != null || asNumber(program.number_of_reports_for_user) > 0; }
function sortByName(a, b) { return programName(a).localeCompare(programName(b)); }
function sortByEarnedThenName(a, b) {
    const earned = asNumber(b.bounty_earned_for_user) - asNumber(a.bounty_earned_for_user);
    return earned || sortByName(a, b);
}
function matchesQuery(program, query) {
    if (!query) return true;
    const haystack = [program.handle, program.name].map(v => String(v || "").toLowerCase()).join(" ");
    return haystack.includes(query);
}

function button(text) {
    const btn = h("button", { type: "button" }, text);
    css(btn, { background: "#21262d", border: "1px solid #30363d", color: "#e6edf3", borderRadius: "6px", padding: "5px 10px", cursor: "pointer", fontSize: "12px", lineHeight: "1.2", fontWeight: "600" });
    return btn;
}

function badge(text, color) {
    const wrap = h("span", null);
    css(wrap, { display: "inline-flex", alignItems: "center", gap: "6px", border: "1px solid #30363d", borderRadius: "999px", padding: "2px 8px", whiteSpace: "nowrap", fontSize: "12px", color: "#e6edf3", background: "#161b22", minWidth: "0", lineHeight: "1.5" });
    const dot = h("span", null);
    css(dot, { width: "8px", height: "8px", borderRadius: "999px", background: color || "#6e7681", display: "inline-block", flex: "0 0 auto" });
    const label = h("span", null, text || "unknown");
    css(label, { overflow: "hidden", textOverflow: "ellipsis" });
    wrap.append(dot, label);
    return wrap;
}

function card() {
    const div = h("div", null);
    css(div, { background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px", marginBottom: "14px" });
    return div;
}

function panel() {
    const box = h("section", null);
    css(box, { background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "14px", marginBottom: "14px" });
    return box;
}

function sectionTitle(text) {
    const title = h("h2", null, text);
    css(title, { margin: "0 0 10px 0", fontSize: "15px", lineHeight: "1.4", color: "#e6edf3" });
    return title;
}

function empty(text) {
    const div = h("div", null, text);
    css(div, { color: "#8b949e", padding: "16px", textAlign: "center", border: "1px dashed #30363d", borderRadius: "8px", background: "#0d1117" });
    return div;
}

function clampLines(el, lines) {
    css(el, { display: "-webkit-box", WebkitLineClamp: String(lines), WebkitBoxOrient: "vertical", overflow: "hidden" });
}

function small(text) {
    const span = h("span", null, stripMd(text));
    css(span, { color: "#8b949e", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: "0" });
    return span;
}

function muted(text) {
    const span = h("span", null, text);
    css(span, { color: "#8b949e" });
    return span;
}

function mono(text) {
    const span = h("span", null, text);
    css(span, { color: "#8b949e", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "12px" });
    return span;
}

function retestChecklist(report) {
    return [
        `Retest checklist for HackerOne report #${report.id || ""}`,
        `Title: ${stripMd(report.title || "")}`,
        `Program: ${report.program_handle || ""}`,
        "",
        "1. Reproduce the original issue from a clean session.",
        "2. Verify the patched path no longer triggers the vulnerability.",
        "3. Check adjacent variants and the original affected asset scope.",
        "4. Capture evidence: request, response, timestamp, account, and environment.",
        "5. Update the HackerOne report with the retest result and remaining risk."
    ].join("\n");
}

export function mount(el, api) {
    const state = {
        activeTab: "overview",
        reports: [], details: new Map(), earnings: { balance: 0, total_earned: 0, earnings: [], payouts: [] },
        intents: [], syncState: null, pendingEvents: [], programs: [], programsGenerated: null,
        collapsedPrograms: new Set(), expandedReports: new Set(), expandedIntents: new Set(), expandedTimeline: new Set(),
        expandedPrograms: new Set(), expandedTexts: new Set(), showAll: false, programFilter: "",
        loadingDetails: new Set(), lastJson: "", loading: true, error: "", timer: null, eventSource: null
    };

    const root = h("div", null);
    css(root, { display: "flex", flexDirection: "column", height: "100%", minHeight: "0", color: "#e6edf3", background: "#0d1117", fontSize: "14px", lineHeight: "1.45" });
    el.appendChild(root);

    const header = h("div", null);
    css(header, { position: "sticky", top: "0", zIndex: "5", padding: "12px 16px", borderBottom: "1px solid #30363d", background: "#0d1117", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" });
    root.appendChild(header);

    const headerLeft = h("div", null);
    css(headerLeft, { display: "flex", flexDirection: "column", gap: "2px", minWidth: "0" });
    const title = h("div", null, "Bug Bounty");
    css(title, { fontWeight: "700", fontSize: "17px" });
    const lastSync = h("div", null, "Last sync: loading…");
    css(lastSync, { color: "#8b949e", fontSize: "12px" });
    headerLeft.append(title, lastSync);
    const refreshBtn = button("Refresh");
    header.append(headerLeft, refreshBtn);

    const shell = h("div", null);
    css(shell, { flex: "1", minHeight: "0", display: "flex", flexDirection: "column", overflow: "hidden" });
    root.appendChild(shell);

    const tabBar = h("div", { role: "tablist", "aria-label": "Bug Bounty sections" });
    css(tabBar, { display: "flex", gap: "8px", overflowX: "auto", whiteSpace: "nowrap", borderBottom: "1px solid #30363d", padding: "8px 16px 0 16px", background: "#0d1117", flex: "0 0 auto" });
    shell.appendChild(tabBar);

    const content = h("div", null);
    css(content, { flex: "1", minHeight: "0", overflow: "auto", padding: "16px" });
    shell.appendChild(content);

    const tabButtons = new Map();
    const panes = new Map();
    for (const [key, label] of TAB_DEFS) {
        const tab = h("button", { type: "button", role: "tab", "aria-controls": `bounty-pane-${key}`, id: `bounty-tab-${key}` }, label);
        css(tab, { flex: "0 0 auto", background: "transparent", border: "0", borderBottom: "2px solid transparent", color: "#8b949e", cursor: "pointer", padding: "8px 2px 10px 2px", fontSize: "13px", fontWeight: "700" });
        tab.addEventListener("click", () => {
            if (state.activeTab === key) return;
            state.activeTab = key;
            updateTabVisibility();
        });
        tabBar.appendChild(tab);
        tabButtons.set(key, tab);

        const pane = h("div", { role: "tabpanel", id: `bounty-pane-${key}`, "aria-labelledby": `bounty-tab-${key}` });
        css(pane, { minHeight: "0" });
        content.appendChild(pane);
        panes.set(key, pane);
    }

    async function load() {
        try {
            const [reportsText, earningsText, intentsText, syncText, pendingText, programsText] = await Promise.all([
                fetchJson(dataUrl("h1/reports.json"), { generated: null, reports: [] }),
                fetchJson(dataUrl("h1/earnings.json"), { generated: null, balance: 0, earnings: [], payouts: [], total_earned: 0 }),
                fetchJson(dataUrl("h1/intents.json"), { generated: null, intents: [] }),
                fetchJson(dataUrl("h1/sync_state.json"), { last_sync: null, counts: {}, previous: null }),
                fetchJson(dataUrl("h1/pending_events.json"), []),
                fetchJson(dataUrl(PROGRAMS_PATH), { generated: null, programs: [] })
            ]);
            const combined = [reportsText, earningsText, intentsText, syncText, pendingText, programsText].join("\n---\n");
            if (combined === state.lastJson && !state.loading && !state.error) return;
            state.lastJson = combined;
            const reportsData = JSON.parse(reportsText || "{}");
            const earningsData = JSON.parse(earningsText || "{}");
            const intentsData = JSON.parse(intentsText || "{}");
            const programsData = JSON.parse(programsText || "{}");
            state.reports = Array.isArray(reportsData.reports) ? reportsData.reports : [];
            state.earnings = earningsData || state.earnings;
            state.intents = Array.isArray(intentsData.intents) ? intentsData.intents : [];
            state.syncState = JSON.parse(syncText || "{}");
            state.pendingEvents = JSON.parse(pendingText || "[]") || [];
            state.programs = Array.isArray(programsData.programs) ? programsData.programs : [];
            state.programsGenerated = programsData.generated || null;
            state.loading = false;
            state.error = "";
            render();
        } catch (e) {
            state.loading = false;
            state.error = e.message || String(e);
            render();
        }
    }

    async function loadDetail(reportId) {
        const key = String(reportId || "");
        if (!key || state.details.has(key) || state.loadingDetails.has(key)) return;
        state.loadingDetails.add(key);
        try {
            const text = await fetchJson(dataUrl(`h1/report_details/${key}.json`), { id: key, timeline: [], bounties: [] });
            state.details.set(key, JSON.parse(text || "{}"));
        } catch (e) {
            state.details.set(key, { id: key, timeline: [], bounties: [], error: e.message || String(e) });
        } finally {
            state.loadingDetails.delete(key);
            render();
        }
    }

    function updateTabVisibility() {
        for (const [key, buttonEl] of tabButtons.entries()) {
            const active = state.activeTab === key;
            buttonEl.setAttribute("aria-selected", active ? "true" : "false");
            buttonEl.setAttribute("tabindex", active ? "0" : "-1");
            css(buttonEl, { color: active ? "#e6edf3" : "#8b949e", borderBottomColor: active ? "#58a6ff" : "transparent" });
        }
        for (const [key, pane] of panes.entries()) {
            const active = state.activeTab === key;
            pane.hidden = !active;
            css(pane, { display: active ? "block" : "none" });
        }
    }

    function render() {
        updateHeader();
        for (const pane of panes.values()) pane.replaceChildren();
        if (state.loading) {
            for (const pane of panes.values()) {
                const div = h("div", null, "Loading bounty data…");
                css(div, { color: "#8b949e", padding: "32px", textAlign: "center" });
                pane.appendChild(div);
            }
            updateTabVisibility();
            return;
        }
        if (state.error) renderError(panes.get("overview"));
        renderOverview(panes.get("overview"));
        renderReports(panes.get("reports"));
        renderIntents(panes.get("intents"));
        renderPrograms(panes.get("programs"));
        renderFooter(panes.get("overview"), "Polling every 30s; live updates via Studio pack events.");
        renderFooter(panes.get("reports"), "Polling every 30s; live updates via Studio pack events.");
        renderFooter(panes.get("intents"), "Polling every 30s; live updates via Studio pack events.");
        renderFooter(panes.get("programs"), `Generated: ${state.programsGenerated || "never"} · data: ${PROGRAMS_PATH} · run a sync to refresh`);
        updateTabVisibility();
    }

    function updateHeader() {
        const last = state.syncState && state.syncState.last_sync ? formatDate(state.syncState.last_sync) : "never";
        const programCount = state.programs.length;
        lastSync.textContent = `Last sync: ${last} · ${programCount} programs synced`;
    }

    function renderError(parent) {
        const div = card();
        css(div, { borderColor: "#f85149", color: "#f85149" });
        div.append("Error loading bounty data: " + state.error + " ");
        const retry = button("Retry");
        retry.addEventListener("click", load);
        div.appendChild(retry);
        parent.appendChild(div);
    }

    function renderOverview(parent) {
        renderStats(parent);
        renderAttention(parent);
    }

    function renderStats(parent) {
        const wrap = card();
        css(wrap, { padding: "14px" });
        const grid = h("div", null);
        css(grid, { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "10px", marginBottom: "14px" });
        grid.appendChild(statCard("Current balance", formatMoney(state.earnings.balance)));
        grid.appendChild(statCard("Total earned", formatMoney(state.earnings.total_earned)));
        grid.appendChild(statCard("Reports", String(state.reports.length)));
        grid.appendChild(statCard("Ready intents", String(state.intents.filter(i => i && i.state === "ready_to_submit").length)));
        wrap.append(grid, renderStateSummary());
        parent.appendChild(wrap);
    }

    function statCard(label, value) {
        const div = h("div", null);
        css(div, { background: "#0d1117", border: "1px solid #30363d", borderRadius: "10px", padding: "14px", minHeight: "74px", display: "flex", flexDirection: "column", justifyContent: "center" });
        const big = h("div", null, value);
        css(big, { fontSize: "24px", fontWeight: "800", letterSpacing: "-0.02em" });
        const smallLabel = h("div", null, label);
        css(smallLabel, { color: "#8b949e", fontSize: "12px", marginTop: "2px" });
        div.append(big, smallLabel);
        return div;
    }

    function renderStateSummary() {
        const box = h("div", null);
        const counts = countBy(state.reports, "state");
        const total = counts.reduce((sum, item) => sum + item[1], 0);
        if (!total) {
            box.appendChild(empty("No reports synced yet — run /hh-bounty sync to populate this panel."));
            return box;
        }
        const bar = h("div", null);
        css(bar, { display: "flex", width: "100%", height: "14px", overflow: "hidden", borderRadius: "999px", border: "1px solid #30363d", background: "#0d1117", marginBottom: "10px" });
        for (const [st, count] of counts) {
            const seg = h("div", { title: `${st}: ${count}` });
            css(seg, { flexGrow: String(count), flexBasis: "0", background: stateColor(st), minWidth: count ? "4px" : "0" });
            bar.appendChild(seg);
        }
        const legend = h("div", null);
        css(legend, { display: "flex", gap: "8px", flexWrap: "wrap" });
        for (const [st, count] of counts) legend.appendChild(badge(`${count} ${st}`, stateColor(st)));
        box.append(bar, legend);
        return box;
    }

    function renderAttention(parent) {
        const key = JSON.stringify(state.pendingEvents || []);
        if (!state.pendingEvents.length || sessionStorage.getItem(DISMISS_KEY) === key) return;
        const wrap = card();
        css(wrap, { borderColor: "#d29922", background: "#1f1a0d" });
        const top = h("div", null);
        css(top, { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", marginBottom: "6px" });
        const dismiss = button("Dismiss");
        dismiss.addEventListener("click", () => { sessionStorage.setItem(DISMISS_KEY, key); render(); });
        top.append(h("strong", null, "Attention: changes since last sync"), dismiss);
        wrap.appendChild(top);
        for (const ev of state.pendingEvents) {
            const row = h("div", null);
            css(row, { color: "#e6edf3", padding: "3px 0", fontSize: "13px" });
            row.textContent = `Report #${ev.report_id || "?"} (${ev.program_handle || "unknown"}): ${ev.kind || "change"} ${ev.from || "—"} → ${ev.to || "—"}`;
            wrap.appendChild(row);
        }
        parent.appendChild(wrap);
    }

    function renderIntents(parent) {
        const wrap = card();
        wrap.appendChild(sectionTitle("Report intents queue"));
        if (!state.intents.length) {
            wrap.appendChild(empty("No report intents yet — run a sync or create an intent to start the submission queue."));
            parent.appendChild(wrap);
            return;
        }
        const grid = h("div", null);
        css(grid, { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "12px" });
        state.intents.forEach((intent, index) => grid.appendChild(renderIntentCard(intent, index)));
        wrap.appendChild(grid);
        parent.appendChild(wrap);
    }

    function renderIntentCard(intent, index) {
        const key = String(intent.id || intent.title || index);
        const open = state.expandedIntents.has(key);
        const div = h("div", { tabindex: "0" });
        css(div, { background: "#0d1117", border: "1px solid #30363d", borderRadius: "10px", padding: "12px", cursor: "pointer", minHeight: "164px", display: "flex", flexDirection: "column", gap: "9px" });
        if (intent.state === "ready_to_submit") css(div, { borderColor: "rgba(63,185,80,0.75)", background: "rgba(63,185,80,0.08)" });
        div.addEventListener("click", () => toggleIntent(key));
        div.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleIntent(key); } });
        div.appendChild(badge(intent.state || "unknown", stateColor(intent.state)));
        const name = h("div", null, stripMd(intent.title || intent.id || "Untitled intent"));
        css(name, { fontWeight: "700", color: "#e6edf3", minHeight: "38px" });
        clampLines(name, 2);
        div.appendChild(name);
        const descText = open ? stripMd(intent.description || "No description synced.") : truncateText(intent.description || "No description synced.", 160);
        const desc = h("div", null, descText);
        css(desc, { color: "#8b949e", fontSize: "12px" });
        if (!open) clampLines(desc, 3);
        else css(desc, { maxHeight: "200px", overflowY: "auto", whiteSpace: "pre-wrap", borderTop: "1px solid #30363d", paddingTop: "8px" });
        div.appendChild(desc);
        renderIntentFailures(div, intent);
        renderIntentFooter(div, intent);
        return div;
    }

    // HackerOne's own Hai pipeline job types, humanized. Anything unknown
    // falls back to a prettified snake_case -> words transform.
    const H1_JOB_LABELS = {
        analyze_asset_type: "Asset type analysis",
        analyze_bug_class_completeness: "Bug-class completeness check",
        analyze_bug_type: "Bug type classification",
        analyze_cif: "Customer impact (CIF) analysis",
        analyze_custom_fields: "Custom field extraction",
        analyze_vulnerability_presence: "Vulnerability presence check",
        assistant_response: "Assistant response draft",
        assistant_summary: "Report summary draft",
        determine_asset: "Asset detection",
        revise_intent: "Intent revision"
    };

    function jobLabel(name) {
        const key = String(name || "");
        if (H1_JOB_LABELS[key]) return H1_JOB_LABELS[key];
        const words = key.replace(/[_-]+/g, " ").trim();
        return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Unknown check";
    }

    function renderIntentFailures(div, intent) {
        const failed = Array.isArray(intent.failed_jobs) ? intent.failed_jobs : [];
        if (!failed.length) return;
        const names = failed.map(jobLabel);
        const fail = h("div", null,
            "HackerOne AI review — needs attention: " + names.join(", ") + ".");
        css(fail, { color: "#d29922", fontSize: "12px", fontWeight: "600" });
        div.appendChild(fail);
        const why = h("div", null,
            "These are HackerOne's own pipeline checks on the intent (not halo-hacker jobs). " +
            "They usually fail on a thin draft or a platform hiccup — edit and re-save the intent on H1 to re-run them.");
        css(why, { color: "#8b949e", fontSize: "11px" });
        div.appendChild(why);
    }

    function renderIntentFooter(div, intent) {
        const footer = h("div", null);
        css(footer, { marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" });
        const link = h("a", { href: intent.hackerone_url || intent.url || "https://hackerone.com/reports/new", target: "_blank", rel: "noopener noreferrer" }, "Open in H1");
        css(link, { color: "#58a6ff", fontSize: "12px", whiteSpace: "nowrap" });
        link.addEventListener("click", e => e.stopPropagation());
        footer.appendChild(link);
        if (intent.state === "ready_to_submit") {
            const hint = h("span", null, "Submit via agent");
            css(hint, { color: "#8b949e", fontSize: "12px" });
            footer.appendChild(hint);
        }
        div.appendChild(footer);
    }

    function toggleIntent(key) {
        if (state.expandedIntents.has(key)) state.expandedIntents.delete(key);
        else state.expandedIntents.add(key);
        render();
    }

    function renderReports(parent) {
        const wrap = h("div", null);
        wrap.appendChild(sectionTitle("Reports grouped by program"));
        if (!state.reports.length) {
            wrap.appendChild(empty("No reports yet — run /hh-bounty sync, then refresh this panel."));
            parent.appendChild(wrap);
            return;
        }
        const groups = new Map();
        for (const report of state.reports) {
            const key = report.program_handle || "unknown";
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(report);
        }
        for (const [program, reports] of Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {
            renderProgramGroup(wrap, program, reports);
        }
        parent.appendChild(wrap);
    }

    function earnedByProgram(program) {
        let total = 0;
        for (const item of state.earnings.earnings || []) {
            if ((item.program_handle || "unknown") === program) total += Number(item.amount || item.bounty_amount || 0);
        }
        return total;
    }

    function programRollup(program, reports) {
        const parts = [`${reports.length} ${reports.length === 1 ? "report" : "reports"}`];
        for (const [st, count] of countBy(reports, "state")) parts.push(`${count} ${st}`);
        const earned = earnedByProgram(program);
        if (earned > 0) parts.push(`${formatMoney(earned)} earned`);
        return parts.join(" · ");
    }

    function renderProgramGroup(parent, program, reports) {
        const open = !state.collapsedPrograms.has(program);
        const group = card();
        css(group, { padding: "0", overflow: "hidden" });
        const head = h("button", { type: "button" }, null);
        css(head, { background: "#161b22", border: "0", color: "#e6edf3", cursor: "pointer", padding: "12px", textAlign: "left", width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" });
        const name = h("div", null, `${open ? "▾" : "▸"} ${program}`);
        css(name, { fontWeight: "700", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        const roll = h("div", null, programRollup(program, reports));
        css(roll, { color: "#8b949e", fontSize: "12px", marginTop: "2px" });
        clampLines(roll, 1);
        const left = h("div", null);
        css(left, { minWidth: "0" });
        left.append(name, roll);
        head.appendChild(left);
        head.addEventListener("click", () => { if (open) state.collapsedPrograms.add(program); else state.collapsedPrograms.delete(program); render(); });
        group.appendChild(head);
        if (open) renderProgramRows(group, reports);
        parent.appendChild(group);
    }

    function renderProgramRows(group, reports) {
        const rows = h("div", null);
        css(rows, { borderTop: "1px solid #30363d" });
        const sorted = reports.slice().sort((a, b) => String(lastActivity(b)).localeCompare(String(lastActivity(a))));
        for (const report of sorted) renderReport(rows, report);
        group.appendChild(rows);
    }

    function renderReport(parent, report) {
        const reportId = String(report.id || "");
        const open = state.expandedReports.has(reportId);
        const row = h("div", { tabindex: "0" });
        css(row, { display: "grid", gridTemplateColumns: "116px minmax(160px, 1fr) minmax(100px, 160px) 92px 112px", gap: "8px", alignItems: "center", padding: "9px 12px", cursor: "pointer", borderBottom: "1px solid #30363d" });
        row.addEventListener("click", () => toggleReport(reportId));
        row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleReport(reportId); } });
        row.appendChild(badge(report.state || "unknown", stateColor(report.state)));
        const titleEl = h("div", null, stripMd(report.title || "Untitled report"));
        css(titleEl, { fontWeight: open ? "700" : "500", minWidth: "0" });
        clampLines(titleEl, 1);
        row.append(titleEl, small(report.weakness_name || report.weakness || "—"), badge(report.severity_rating || "—", severityColor(report.severity_rating)), small(formatDate(lastActivity(report))));
        parent.appendChild(row);
        if (open) renderDetail(parent, report);
    }

    function toggleReport(reportId) {
        if (!reportId) return;
        if (state.expandedReports.has(reportId)) state.expandedReports.delete(reportId);
        else { state.expandedReports.add(reportId); loadDetail(reportId); }
        render();
    }

    function renderDetail(parent, report) {
        const reportId = String(report.id || "");
        const detail = state.details.get(reportId) || { timeline: [], bounties: [] };
        const box = h("div", null);
        css(box, { padding: "12px", borderBottom: "1px solid #30363d", background: "#0d1117" });
        const actions = h("div", null);
        css(actions, { display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap", marginBottom: "10px" });
        const link = h("a", { href: `https://hackerone.com/reports/${reportId}`, target: "_blank", rel: "noopener noreferrer" }, "Open on HackerOne");
        css(link, { color: "#58a6ff", fontSize: "12px" });
        actions.appendChild(link);
        if (report.state === "resolved") actions.appendChild(renderRetestButton(report));
        box.appendChild(actions);
        if (state.loadingDetails.has(reportId)) box.appendChild(empty("Loading activity timeline…"));
        else if (detail.error) box.appendChild(empty("Detail load error: " + detail.error));
        else renderTimeline(box, reportId, detail.timeline || []);
        parent.appendChild(box);
    }

    function renderRetestButton(report) {
        const wrap = h("span", null);
        css(wrap, { display: "inline-flex", alignItems: "center", gap: "8px" });
        const retest = button("Retest");
        const status = h("span", null);
        css(status, { color: "#8b949e", fontSize: "12px" });
        retest.addEventListener("click", async e => {
            e.stopPropagation();
            try { await navigator.clipboard.writeText(retestChecklist(report)); status.textContent = "Checklist copied."; }
            catch (_) { status.textContent = "Clipboard unavailable."; }
        });
        wrap.append(retest, status);
        return wrap;
    }

    function renderTimeline(box, reportId, timeline) {
        if (!timeline.length) {
            box.appendChild(empty("No timeline entries synced for this report."));
            return;
        }
        const title = h("div", null, "Activity timeline");
        css(title, { color: "#8b949e", fontSize: "12px", fontWeight: "700", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.04em" });
        box.appendChild(title);
        timeline.forEach((item, index) => box.appendChild(renderTimelineEntry(reportId, item, index)));
    }

    function renderTimelineEntry(reportId, item, index) {
        const internal = Boolean(item.internal);
        const key = `${reportId}:${index}`;
        const expanded = state.expandedTimeline.has(key);
        const clean = stripMd(item.message || item.type || "Timeline event");
        const entry = h("div", null);
        css(entry, { borderTop: "1px solid #30363d", padding: "9px 0", color: internal ? "#6e7681" : "#e6edf3", opacity: internal ? "0.78" : "1" });
        const meta = h("div", null);
        css(meta, { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", marginBottom: "5px" });
        const when = h("span", null, formatDate(item.created_at));
        const actor = h("span", null, stripMd(item.actor_username || "unknown"));
        css(when, { color: internal ? "#6e7681" : "#8b949e", fontSize: "12px" });
        css(actor, { color: internal ? "#6e7681" : "#8b949e", fontSize: "12px" });
        meta.append(when, actor, badge(item.type || "activity", "#6e7681"));
        if (internal) meta.appendChild(badge("internal", "#6e7681"));
        entry.appendChild(meta);
        const msg = h("div", null, clean || "Timeline event");
        css(msg, { fontSize: "13px", color: internal ? "#8b949e" : "#e6edf3" });
        if (!expanded) clampLines(msg, 3);
        entry.appendChild(msg);
        if (clean.length > 260) entry.appendChild(timelineToggle(key, expanded));
        if (item.bounty_amount != null) {
            const bounty = h("div", null, "Bounty: " + formatMoney(item.bounty_amount));
            css(bounty, { color: "#3fb950", fontSize: "12px", marginTop: "5px", fontWeight: "700" });
            entry.appendChild(bounty);
        }
        return entry;
    }

    function timelineToggle(key, expanded) {
        const toggle = button(expanded ? "show less" : "show more");
        css(toggle, { marginTop: "6px", padding: "3px 8px", color: "#58a6ff" });
        toggle.addEventListener("click", () => { if (expanded) state.expandedTimeline.delete(key); else state.expandedTimeline.add(key); render(); });
        return toggle;
    }

    function filteredPrograms() { return state.programs.filter(program => matchesQuery(program, state.programFilter)); }
    function myPrograms() { return filteredPrograms().filter(isMyProgram).sort(sortByEarnedThenName); }
    function directoryPrograms() { return filteredPrograms().filter(program => !isMyProgram(program)).sort(sortByName); }

    function renderPrograms(parent) {
        renderProgramControls(parent);
        renderMyPrograms(parent);
        renderAllPrograms(parent);
    }

    function renderProgramControls(parent) {
        const controls = panel();
        css(controls, { display: "grid", gridTemplateColumns: "minmax(220px, 380px) 1fr", gap: "12px", alignItems: "center" });
        const search = h("input", { type: "search", placeholder: "Filter by handle or name", autocomplete: "off", "aria-label": "Filter programs by handle or name", value: state.programFilter });
        css(search, { width: "100%", minWidth: "220px", background: "#0d1117", border: "1px solid #30363d", color: "#e6edf3", borderRadius: "6px", padding: "7px 10px", fontSize: "13px", outline: "none" });
        search.addEventListener("input", () => { state.programFilter = search.value.trim().toLowerCase(); render(); });
        const total = state.programs.length;
        const shown = filteredPrograms().length;
        const meta = h("div", null, state.programFilter ? `${shown} of ${total} shown` : `${total} synced`);
        css(meta, { color: "#8b949e", fontSize: "12px", textAlign: "right", minWidth: "140px" });
        controls.append(search, meta);
        parent.appendChild(controls);
    }

    function renderMyPrograms(parent) {
        const mine = myPrograms();
        const wrap = panel();
        const top = h("div", null);
        css(top, { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "12px", marginBottom: "12px", flexWrap: "wrap" });
        top.appendChild(sectionTitle(`My programs (${mine.length})`));
        top.appendChild(muted("accepted invitations or past reports"));
        wrap.appendChild(top);

        if (!state.programs.length) {
            wrap.appendChild(empty("No HackerOne programs synced yet — run a sync."));
        } else if (!mine.length) {
            wrap.appendChild(empty(state.programFilter ? "No matching my-programs. Try a different handle or name." : "No accepted or previously reported programs in the synced data."));
        } else {
            const grid = h("div", null);
            css(grid, { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "12px" });
            for (const program of mine) grid.appendChild(programCard(program));
            wrap.appendChild(grid);
        }
        parent.appendChild(wrap);
    }

    function programCard(program) {
        const key = programKey(program);
        const open = state.expandedPrograms.has(key);
        const cardEl = h("article", null);
        css(cardEl, { border: "1px solid " + (open ? "#58a6ff" : "#30363d"), borderRadius: "10px", background: open ? "#101923" : "#161b22", padding: "12px", cursor: "pointer", boxShadow: open ? "0 0 0 1px rgba(88,166,255,0.18)" : "none" });
        cardEl.addEventListener("click", () => {
            if (state.expandedPrograms.has(key)) state.expandedPrograms.delete(key);
            else state.expandedPrograms.add(key);
            render();
        });
        cardEl.addEventListener("mouseenter", () => css(cardEl, { borderColor: open ? "#58a6ff" : "#8b949e" }));
        cardEl.addEventListener("mouseleave", () => css(cardEl, { borderColor: open ? "#58a6ff" : "#30363d" }));

        const head = h("div", null);
        css(head, { display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "flex-start" });
        const names = h("div", null);
        css(names, { minWidth: "0" });
        const name = h("div", null, programName(program));
        css(name, { fontWeight: "700", fontSize: "15px", color: "#e6edf3", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        names.append(name, mono(programHandle(program)));
        head.append(names, submissionBadge(program));
        cardEl.appendChild(head);

        const stats = h("div", null);
        css(stats, { marginTop: "10px", color: "#8b949e", fontSize: "13px", display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" });
        stats.append("Reports " + asNumber(program.number_of_reports_for_user), "·", "Valid " + asNumber(program.number_of_valid_reports_for_user), "·");
        const earned = h("strong", null, "Earned " + formatMoney(program.bounty_earned_for_user, true));
        css(earned, { color: "#3fb950", fontWeight: "700" });
        stats.appendChild(earned);
        cardEl.appendChild(stats);

        const hint = h("div", null, open ? "Click to collapse" : "Click for policy and scope");
        css(hint, { color: "#8b949e", fontSize: "12px", marginTop: "8px" });
        cardEl.appendChild(hint);
        if (open) cardEl.appendChild(programDetail(program));
        return cardEl;
    }

    function submissionBadge(program) {
        const st = String(program.submission_state || "unknown").toLowerCase();
        return badge(st, STATE_COLORS[st] || "#6e7681");
    }

    function programDetail(program) {
        const detail = h("div", null);
        css(detail, { marginTop: "12px", paddingTop: "12px", borderTop: "1px solid #30363d", cursor: "default" });
        detail.addEventListener("click", event => event.stopPropagation());

        const chips = h("div", null);
        css(chips, { display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "12px" });
        chips.append(infoChip("Weaknesses", String(asNumber(program.weaknesses_count))), infoChip("Offers bounties", program.offers_bounties ? "yes" : "no"), infoChip("State", program.state || "unknown"));
        detail.appendChild(chips);

        detail.append(blockTitle("Policy"), clampedText({ key: programKey(program) + ":policy", text: stripMd(program.policy) || "No policy text synced.", lines: 4, shortLimit: 520, expandedMaxHeight: "260px" }));
        const scopeHead = blockTitle("Scope");
        css(scopeHead, { marginTop: "12px" });
        detail.appendChild(scopeHead);

        const scopes = Array.isArray(program.scopes) ? program.scopes : [];
        if (!scopes.length) detail.appendChild(empty("No scope entries synced for this program."));
        else {
            const list = h("div", null);
            css(list, { display: "grid", gap: "8px" });
            scopes.forEach((scope, index) => list.appendChild(scopeRow(program, scope, index)));
            detail.appendChild(list);
        }
        return detail;
    }

    function infoChip(label, value) {
        const chip = h("div", null);
        css(chip, { display: "inline-flex", alignItems: "center", gap: "6px", border: "1px solid #30363d", borderRadius: "999px", padding: "4px 8px", background: "#0d1117", fontSize: "12px" });
        const strong = h("strong", null, value);
        css(strong, { color: "#e6edf3" });
        chip.append(strong, muted(label));
        return chip;
    }

    function blockTitle(text) {
        const title = h("div", null, text);
        css(title, { fontWeight: "700", color: "#e6edf3", marginBottom: "6px", fontSize: "13px" });
        return title;
    }

    function clampedText(options) {
        const full = options.text || "";
        const key = options.key;
        const expanded = state.expandedTexts.has(key);
        const limit = options.shortLimit || 240;
        const needsToggle = full.length > limit;
        const shown = !expanded && needsToggle ? full.slice(0, limit).trimEnd() + "…" : full;
        const wrap = h("div", null);
        css(wrap, { color: "#8b949e", fontSize: "13px" });
        const body = h("div", null, shown);
        css(body, { display: expanded ? "block" : "-webkit-box", WebkitLineClamp: expanded ? "unset" : String(options.lines || 2), WebkitBoxOrient: "vertical", overflow: expanded ? "auto" : "hidden", maxHeight: expanded ? (options.expandedMaxHeight || "180px") : "none", whiteSpace: "normal" });
        wrap.appendChild(body);
        if (needsToggle) wrap.appendChild(toggleTextButton(key, expanded));
        return wrap;
    }

    function toggleTextButton(key, expanded) {
        const more = h("button", { type: "button" }, expanded ? "Show less" : "Show more");
        css(more, { marginTop: "6px", padding: "0", background: "transparent", border: "0", color: "#58a6ff", cursor: "pointer", fontSize: "12px", fontWeight: "600" });
        more.addEventListener("click", event => {
            event.stopPropagation();
            if (state.expandedTexts.has(key)) state.expandedTexts.delete(key);
            else state.expandedTexts.add(key);
            render();
        });
        return more;
    }

    function scopeRow(program, scope, index) {
        const row = h("div", null);
        css(row, { border: "1px solid #30363d", borderRadius: "8px", background: "#0d1117", padding: "9px" });
        const top = h("div", null);
        css(top, { display: "grid", gridTemplateColumns: "minmax(150px, 1fr) auto auto", gap: "8px", alignItems: "center" });
        const ident = h("div", null, String(scope.asset_identifier || "unnamed asset"));
        css(ident, { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "12px", color: "#e6edf3", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        top.append(ident, badge(scope.eligible_for_bounty ? "bounty" : "no bounty", scope.eligible_for_bounty ? "#3fb950" : "#6e7681"), badge(scope.max_severity || "severity —", "#58a6ff"));
        row.appendChild(top);

        const facts = [];
        if (scope.asset_type) facts.push("Type: " + scope.asset_type);
        if (scope.eligible_for_submission === false) facts.push("Not eligible for submission");
        const instruction = stripMd(scope.instruction || scope.instructions || "");
        const detailText = [facts.join(" · "), instruction].filter(Boolean).join(" · ");
        if (detailText) {
            const detail = clampedText({ key: programKey(program) + ":scope:" + index, text: detailText, lines: 2, shortLimit: 190, expandedMaxHeight: "140px" });
            css(detail, { marginTop: "7px" });
            row.appendChild(detail);
        }
        return row;
    }

    function renderAllPrograms(parent) {
        const rest = directoryPrograms();
        const wrap = panel();
        const head = h("button", { type: "button" }, `${state.showAll ? "▾" : "▸"} All programs directory (${rest.length})`);
        css(head, { background: "transparent", border: "0", color: "#e6edf3", cursor: "pointer", fontWeight: "700", fontSize: "15px", padding: "0", textAlign: "left" });
        head.addEventListener("click", () => { state.showAll = !state.showAll; render(); });
        wrap.appendChild(head);
        if (state.showAll) {
            if (!rest.length) wrap.appendChild(empty(state.programFilter ? "No matching directory programs." : "No additional programs outside My programs."));
            else {
                const list = h("div", null);
                css(list, { marginTop: "10px", maxHeight: "400px", overflowY: "auto", borderTop: "1px solid #30363d" });
                for (const program of rest) list.appendChild(directoryRow(program));
                wrap.appendChild(list);
            }
        }
        parent.appendChild(wrap);
    }

    function directoryRow(program) {
        const row = h("div", null);
        css(row, { display: "grid", gridTemplateColumns: "minmax(160px, 1fr) auto", gap: "10px", alignItems: "center", padding: "8px 4px", borderBottom: "1px solid #30363d" });
        const names = h("div", null);
        css(names, { minWidth: "0" });
        const name = h("div", null, programName(program));
        css(name, { color: "#e6edf3", fontWeight: "600", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        names.append(name, mono(programHandle(program)));
        row.append(names, submissionBadge(program));
        return row;
    }

    function renderFooter(parent, text) {
        const footer = h("div", null);
        css(footer, { color: "#8b949e", fontSize: "12px", padding: "2px 0 12px 0" });
        footer.textContent = text;
        parent.appendChild(footer);
    }

    function startLiveUpdates() {
        state.timer = setInterval(load, 30000);
        const token = sessionStorage.getItem("halo-studio-token");
        if (token && typeof EventSource !== "undefined") {
            try {
                state.eventSource = new EventSource(`/api/events?t=${encodeURIComponent(token)}`);
                state.eventSource.addEventListener("message", e => {
                    try {
                        const msg = JSON.parse(e.data);
                        if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") load();
                    } catch (_) {}
                });
            } catch (_) {}
        }
    }

    refreshBtn.addEventListener("click", load);
    updateTabVisibility();
    load();
    startLiveUpdates();

    return () => {
        if (state.timer) clearInterval(state.timer);
        if (state.eventSource) state.eventSource.close();
        if (root.parentNode === el) el.removeChild(root);
    };
}
