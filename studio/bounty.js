// HackerOne bounty dashboard — renders h1/* pack-data files from ~/.halo/packs/.data/halo-hacker/.
// Data flow: sync mount builds a static shell, async loaders fetch JSON through Studio's data API,
// then polling/SSE pack_event frames reload and re-render without using inline HTML or external assets.

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
const DISMISS_KEY = "halo-hacker-bounty-pending-dismissed";

const STATE_COLORS = {
    new: "#8b949e",
    triaged: "#58a6ff",
    "needs-more-info": "#d29922",
    resolved: "#3fb950",
    duplicate: "#6e7681",
    informative: "#6e7681",
    "not-applicable": "#6e7681",
    spam: "#f85149",
    draft: "#8b949e",
    running: "#58a6ff",
    failed: "#f85149",
    ready_to_submit: "#3fb950",
    submitted: "#a371f7"
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
    css(dot, { width: "8px", height: "8px", borderRadius: "999px", background: color || "#6e7681", display: "inline-block" });
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

function formatDate(value) {
    if (!value) return "—";
    try {
        const d = new Date(value);
        if (d.toString() === "Invalid Date") return value;
        return d.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (_) {
        return value;
    }
}

function lastActivity(report) {
    return report.last_program_activity_at || report.last_reporter_activity_at || report.bounty_awarded_at || report.closed_at || report.triaged_at || report.created_at || "";
}

function countBy(items, field) {
    const counts = new Map();
    for (const item of items || []) {
        const key = item && item[field] ? String(item[field]) : "unknown";
        counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function retestChecklist(report) {
    return [
        `Retest checklist for HackerOne report #${report.id || ""}`,
        `Title: ${report.title || ""}`,
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
        reports: [],
        details: new Map(),
        earnings: { balance: 0, total_earned: 0, earnings: [], payouts: [] },
        intents: [],
        syncState: null,
        pendingEvents: [],
        expandedPrograms: new Set(),
        expandedReports: new Set(),
        lastJson: "",
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

    const title = h("div", null, "HackerOne bounty dashboard");
    css(title, { fontWeight: "bold", fontSize: "16px" });
    header.appendChild(title);

    const refreshBtn = button("Refresh");
    header.appendChild(refreshBtn);

    const content = h("div", null);
    css(content, { flex: "1", overflow: "auto", padding: "16px" });
    root.appendChild(content);

    async function load() {
        try {
            const [reportsText, earningsText, intentsText, syncText, pendingText] = await Promise.all([
                fetchJson(dataUrl("h1/reports.json"), { generated: null, reports: [] }),
                fetchJson(dataUrl("h1/earnings.json"), { generated: null, balance: 0, earnings: [], payouts: [], total_earned: 0 }),
                fetchJson(dataUrl("h1/intents.json"), { generated: null, intents: [] }),
                fetchJson(dataUrl("h1/sync_state.json"), { last_sync: null, counts: {}, previous: null }),
                fetchJson(dataUrl("h1/pending_events.json"), [])
            ]);
            const combined = [reportsText, earningsText, intentsText, syncText, pendingText].join("\n---\n");
            if (combined === state.lastJson && !state.loading) return;
            state.lastJson = combined;
            const reportsData = JSON.parse(reportsText || "{}");
            const earningsData = JSON.parse(earningsText || "{}");
            const intentsData = JSON.parse(intentsText || "{}");
            state.reports = reportsData.reports || [];
            state.earnings = earningsData || state.earnings;
            state.intents = intentsData.intents || [];
            state.syncState = JSON.parse(syncText || "{}");
            state.pendingEvents = JSON.parse(pendingText || "[]") || [];
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
        if (!reportId || state.details.has(String(reportId))) return;
        try {
            const text = await fetchJson(dataUrl(`h1/report_details/${reportId}.json`), { id: reportId, timeline: [], bounties: [] });
            state.details.set(String(reportId), JSON.parse(text || "{}"));
        } catch (e) {
            state.details.set(String(reportId), { id: reportId, timeline: [], bounties: [], error: e.message || String(e) });
        }
    }

    function render() {
        content.replaceChildren();
        if (state.loading) {
            const div = h("div", null, "Loading bounty data...");
            css(div, { color: "#8b949e", padding: "32px", textAlign: "center" });
            content.appendChild(div);
            return;
        }
        if (state.error) renderError();
        renderStats();
        renderAttention();
        renderIntents();
        renderReports();
        renderFooter();
    }

    function renderError() {
        const div = card();
        css(div, { borderColor: "#f85149", color: "#f85149" });
        div.append("Error loading bounty data: " + state.error + " ");
        const retry = button("Retry");
        retry.addEventListener("click", load);
        div.appendChild(retry);
        content.appendChild(div);
    }

    function renderStats() {
        const wrap = card();
        css(wrap, { display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" });
        wrap.appendChild(statChip("Current balance", formatMoney(state.earnings.balance)));
        wrap.appendChild(statChip("Total earned", formatMoney(state.earnings.total_earned)));
        for (const [st, count] of countBy(state.reports, "state")) wrap.appendChild(statChip(st, String(count), STATE_COLORS[st]));
        for (const [st, count] of countBy(state.intents, "state")) wrap.appendChild(statChip("intents " + st, String(count), STATE_COLORS[st]));
        content.appendChild(wrap);
    }

    function statChip(label, value, color) {
        const chip = h("div", null);
        css(chip, { border: "1px solid #30363d", borderRadius: "999px", padding: "5px 10px", background: "#0d1117", display: "flex", gap: "6px", alignItems: "center" });
        if (color) {
            const dot = h("span", null);
            css(dot, { width: "8px", height: "8px", borderRadius: "999px", background: color, display: "inline-block" });
            chip.appendChild(dot);
        }
        const strong = h("strong", null, value);
        css(strong, { color: "#e6edf3" });
        chip.append(strong, muted(label));
        return chip;
    }

    function renderAttention() {
        const key = JSON.stringify(state.pendingEvents || []);
        if (!state.pendingEvents.length || sessionStorage.getItem(DISMISS_KEY) === key) return;
        const wrap = card();
        css(wrap, { borderColor: "#d29922", background: "#1f1a0d" });
        const top = h("div", null);
        css(top, { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", marginBottom: "8px" });
        const heading = h("strong", null, "Attention: changes since last sync");
        const dismiss = button("Dismiss");
        dismiss.addEventListener("click", () => {
            sessionStorage.setItem(DISMISS_KEY, key);
            render();
        });
        top.append(heading, dismiss);
        wrap.appendChild(top);
        for (const ev of state.pendingEvents) {
            const row = h("div", null);
            css(row, { color: "#e6edf3", padding: "3px 0" });
            row.textContent = `Report #${ev.report_id || "?"} (${ev.program_handle || "unknown"}): ${ev.kind || "change"} ${ev.from || "—"} → ${ev.to || "—"}`;
            wrap.appendChild(row);
        }
        content.appendChild(wrap);
    }

    function renderIntents() {
        const wrap = card();
        wrap.appendChild(sectionTitle("Report Intents queue"));
        if (!state.intents.length) {
            wrap.appendChild(empty("No report intents yet — run a sync or create an intent."));
            content.appendChild(wrap);
            return;
        }
        for (const intent of state.intents) {
            const row = h("div", null);
            css(row, { display: "grid", gridTemplateColumns: "minmax(110px, auto) 1fr auto", gap: "10px", alignItems: "center", padding: "8px 0", borderTop: "1px solid #30363d" });
            if (intent.state === "ready_to_submit") css(row, { background: "rgba(63,185,80,0.10)", marginLeft: "-8px", marginRight: "-8px", paddingLeft: "8px", paddingRight: "8px", borderRadius: "6px" });
            row.appendChild(badge(intent.state || "unknown", STATE_COLORS[intent.state]));
            const mid = h("div", null);
            const name = h("div", null, intent.title || intent.id || "Untitled intent");
            css(name, { fontWeight: intent.state === "ready_to_submit" ? "bold" : "normal" });
            mid.appendChild(name);
            if (intent.description) {
                const desc = h("div", null, intent.description);
                css(desc, { color: "#8b949e", fontSize: "12px", marginTop: "2px" });
                mid.appendChild(desc);
            }
            const failed = Array.isArray(intent.failed_jobs) ? intent.failed_jobs : [];
            if (failed.length) {
                const fail = h("div", null, "Failed AI jobs: " + failed.join(", "));
                css(fail, { color: "#f85149", fontSize: "12px", marginTop: "2px" });
                mid.appendChild(fail);
            }
            row.appendChild(mid);
            const link = h("a", { href: "https://hackerone.com/reports/", target: "_blank", rel: "noopener noreferrer" }, "Open submit");
            css(link, { color: "#58a6ff", whiteSpace: "nowrap" });
            row.appendChild(link);
            wrap.appendChild(row);
        }
        content.appendChild(wrap);
    }

    function renderReports() {
        const wrap = card();
        wrap.appendChild(sectionTitle("Reports grouped by program"));
        if (!state.reports.length) {
            wrap.appendChild(empty("No data yet — run a sync."));
            content.appendChild(wrap);
            return;
        }
        const groups = new Map();
        for (const report of state.reports) {
            const key = report.program_handle || "unknown";
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(report);
        }
        const sortedGroups = Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
        for (const [program, reports] of sortedGroups) renderProgramGroup(wrap, program, reports);
        content.appendChild(wrap);
    }

    function renderProgramGroup(wrap, program, reports) {
        const open = state.expandedPrograms.has(program);
        const group = h("div", null);
        css(group, { borderTop: "1px solid #30363d", padding: "8px 0" });
        const head = h("button", null, `${open ? "▾" : "▸"} ${program} (${reports.length})`);
        css(head, { background: "transparent", border: "0", color: "#e6edf3", cursor: "pointer", fontWeight: "bold", padding: "4px 0", textAlign: "left", width: "100%" });
        head.addEventListener("click", () => {
            if (open) state.expandedPrograms.delete(program);
            else state.expandedPrograms.add(program);
            render();
        });
        group.appendChild(head);
        if (open) {
            reports.sort((a, b) => String(lastActivity(b)).localeCompare(String(lastActivity(a))));
            for (const report of reports) renderReport(group, report);
        }
        wrap.appendChild(group);
    }

    function renderReport(group, report) {
        const reportId = String(report.id || "");
        const open = state.expandedReports.has(reportId);
        const row = h("div", null);
        css(row, { display: "grid", gridTemplateColumns: "90px minmax(180px, 1fr) 130px 120px 120px", gap: "8px", alignItems: "center", padding: "7px 8px", cursor: "pointer", borderRadius: "6px" });
        row.addEventListener("click", async () => {
            if (open) state.expandedReports.delete(reportId);
            else {
                state.expandedReports.add(reportId);
                await loadDetail(reportId);
            }
            render();
        });
        const id = h("span", null, "#" + reportId);
        css(id, { fontFamily: "ui-monospace, monospace", color: "#8b949e" });
        row.appendChild(id);
        row.appendChild(h("span", null, report.title || "Untitled report"));
        row.appendChild(badge(report.state || "unknown", STATE_COLORS[report.state]));
        row.appendChild(small(report.weakness_name || "—"));
        row.appendChild(small((report.severity_rating || "—") + " · " + formatDate(lastActivity(report))));
        group.appendChild(row);
        if (open) renderDetail(group, report);
    }

    function renderDetail(group, report) {
        const reportId = String(report.id || "");
        const detail = state.details.get(reportId) || { timeline: [], bounties: [] };
        const box = h("div", null);
        css(box, { margin: "0 0 8px 98px", padding: "10px", border: "1px solid #30363d", borderRadius: "6px", background: "#0d1117" });
        const actions = h("div", null);
        css(actions, { display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap", marginBottom: "8px" });
        const link = h("a", { href: `https://hackerone.com/reports/${reportId}`, target: "_blank", rel: "noopener noreferrer" }, "Open on HackerOne");
        css(link, { color: "#58a6ff" });
        actions.appendChild(link);
        if (report.state === "resolved") {
            const retest = button("Retest");
            const status = h("span", null);
            css(status, { color: "#8b949e", fontSize: "12px" });
            retest.addEventListener("click", async (e) => {
                e.stopPropagation();
                try {
                    await navigator.clipboard.writeText(retestChecklist(report));
                    status.textContent = "Checklist copied.";
                } catch (_) {
                    status.textContent = "Clipboard unavailable.";
                }
            });
            actions.append(retest, status);
        }
        box.appendChild(actions);
        if (detail.error) box.appendChild(small("Detail load error: " + detail.error));
        const timeline = detail.timeline || [];
        if (!timeline.length) box.appendChild(empty("No timeline entries synced for this report."));
        for (const item of timeline) {
            const entry = h("div", null);
            css(entry, { borderTop: "1px solid #30363d", padding: "8px 0", color: item.internal ? "#6e7681" : "#e6edf3" });
            const meta = h("div", null, `${formatDate(item.created_at)} · ${item.actor_username || item.type || "unknown"}`);
            css(meta, { color: item.internal ? "#6e7681" : "#8b949e", fontSize: "12px", marginBottom: "4px" });
            entry.appendChild(meta);
            const msg = h("div", null, item.message || item.type || "Timeline event");
            entry.appendChild(msg);
            if (item.bounty_amount != null) {
                const bounty = h("div", null, "Bounty: " + formatMoney(item.bounty_amount));
                css(bounty, { color: "#3fb950", fontSize: "12px", marginTop: "4px" });
                entry.appendChild(bounty);
            }
            box.appendChild(entry);
        }
        group.appendChild(box);
    }

    function renderFooter() {
        const footer = h("div", null);
        css(footer, { color: "#8b949e", fontSize: "12px", padding: "2px 0 12px 0" });
        const last = state.syncState && state.syncState.last_sync ? formatDate(state.syncState.last_sync) : "never";
        footer.textContent = `Last sync: ${last} · syncing via /hh-bounty sync`;
        content.appendChild(footer);
    }

    function small(text) {
        const span = h("span", null, text);
        css(span, { color: "#8b949e", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        return span;
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
