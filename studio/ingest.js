// Ingest — knowledge-ingestion visualization
// ES module with mount(el, api) — CSP-safe, DOM APIs only

/* ---- helpers ---- */
function h(tag, props, ...children) {
    const el = document.createElement(tag);
    if (props) { for (const [k,v] of Object.entries(props)) { if (k === "style") Object.assign(el.style, v); else el.setAttribute(k, v); } }
    for (const c of children) { if (c === null || c === undefined) continue; el.append(c); }
    return el;
}
function css(el, styleObj) { Object.assign(el.style, styleObj); }
function fetchJson(path) {
    const headers = {};
    const token = sessionStorage.getItem("halo-studio-token");
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch(path, { headers }).then(r => { if (!r.ok) throw new Error(path + " -> HTTP " + r.status); return r.text(); });
}

/* ---- constants ---- */
const SOURCE_COLORS = { pdf: "#d7263d", notes: "#4a7ba6", github: "#1a7f37", youtube: "#e6a817" };
const TIER_COLORS = { "first-party": "#1a7f37", "third-party": "#e6a817" };
const ROUTE_COLORS = { recon: "#4a7ba6", web: "#2f6feb", api: "#1a7f37", ai: "#e6a817", infra: "#8a8f98" };
const OTHER_COLOR = "#8a8f98";
const UNCLASSIFIED_COLOR = "#8a8f98";
const DARK_BG = "#0d1117";
const TEXT_COLOR = "#e6edf3";
const BORDER_COLOR = "#30363d";
const BUTTON_BG = "#21262d";

/* ---- stat-card factories ---- */
function statCard(value, label) {
    const valEl = h("div", { style: { fontSize: "28px", fontWeight: "700", color: TEXT_COLOR } });
    valEl.textContent = String(value);
    const lblEl = h("div", { style: { fontSize: "12px", color: "#8b949e", marginTop: "6px" } });
    lblEl.textContent = label;
    return h("div", { style: { background: "#161b22", borderRadius: "8px", padding: "18px 22px", textAlign: "center", minWidth: "80px" } }, valEl, lblEl);
}

/* ---- bar-row builder ---- */
function barRow(label, count, maxCount, color) {
    const pct = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0;
    const labelEl = h("div", { style: { fontSize: "13px", color: TEXT_COLOR, whiteSpace: "nowrap" } });
    labelEl.textContent = label;

    const bar = h("div", { style: { height: "18px", borderRadius: "4px", background: color, width: pct + "%", transition: "width 0.3s" } });
    const barTrack = h("div", { style: { background: "#21262d", borderRadius: "4px", height: "18px", flex: "1" } }, bar);

    const countEl = h("div", { style: { fontSize: "13px", fontWeight: "600", color: TEXT_COLOR, textAlign: "right", minWidth: "32px" } });
    countEl.textContent = String(count);

    return h("div", { style: { display: "flex", alignItems: "center", gap: "10px", padding: "6px 0" } }, labelEl, barTrack, countEl);
}

/* ---- section header builder ---- */
function sectionHeader(text) {
    const el = h("div", { style: { fontSize: "15px", fontWeight: "600", color: TEXT_COLOR, borderBottom: "1px solid " + BORDER_COLOR, paddingBottom: "6px", marginTop: "20px", marginBottom: "12px" } });
    el.textContent = text;
    return el;
}

/* ---- source-type badge ---- */
function sourceBadge(type) {
    const color = SOURCE_COLORS[type] || OTHER_COLOR;
    const el = h("span", { style: { display: "inline-block", fontSize: "11px", fontWeight: "600", padding: "1px 8px", borderRadius: "10px", background: color, color: "#fff", lineHeight: "1.6" } });
    el.textContent = type;
    return el;
}

/* ---- main render ---- */
function renderRoot(data) {
    const root = h("div", { style: { background: DARK_BG, color: TEXT_COLOR, fontFamily: "'Segoe UI','Helvetica Neue',Arial,sans-serif", fontSize: "14px", lineHeight: "1.5", padding: "24px", borderRadius: "8px", border: "1px solid " + BORDER_COLOR } });

    /* -------- HEADER -------- */
    const titleRow = h("div", { style: { display: "flex", alignItems: "center", gap: "12px", marginBottom: "6px" } });
    const title = h("div", { style: { fontSize: "20px", fontWeight: "700", color: TEXT_COLOR } });
    title.textContent = "Ingest";
    const ts = h("div", { style: { fontSize: "11px", color: "#8b949e" } });
    if (data.generated) {
        let d = data.generated;
        if (typeof d === "string") {
            try { d = new Date(d); } catch (_) { /* keep as-is */ }
        }
        if (d instanceof Date && !isNaN(d.getTime())) {
            ts.textContent = d.toLocaleString();
        } else {
            ts.textContent = String(data.generated);
        }
    }
    const headerRight = h("div", { style: { display: "flex", alignItems: "center", gap: "8px", fontSize: "11px", color: "#8b949e" } }, ts);
    titleRow.append(title, headerRight);

    root.append(titleRow);

    /* -------- EMPTY / ERROR STATES -------- */
    if (data.total_items === 0 || (data.total_items === undefined && data.ledger_exists === false)) {
        if (data.ledger_exists === false) {
            const msg = h("div", { style: { padding: "24px", textAlign: "center", color: "#8b949e", fontSize: "14px", marginTop: "16px" } });
            msg.textContent = "No ledger found — configure a vault and ingest something first.";
            root.append(msg);
        } else {
            const msg = h("div", { style: { padding: "24px", textAlign: "center", color: "#8b949e", fontSize: "14px", marginTop: "16px" } });
            msg.textContent = "Nothing ingested yet.";
            root.append(msg);
        }
        return root;
    }

    /* -------- STAT CARDS -------- */
    const distinctSources = data.source_types ? Object.keys(data.source_types).length : 0;
    const cardContainer = h("div", { style: { display: "flex", gap: "14px", marginTop: "14px", flexWrap: "wrap" } });
    cardContainer.append(
        statCard(data.total_items ?? 0, "Total items"),
        statCard(distinctSources, "Source types"),
        statCard(data.ledger_exists ? "Yes" : "No", "Ledger")
    );
    root.append(cardContainer);

    /* -------- SOURCE BREAKDOWN -------- */
    if (data.source_types) {
        root.append(sectionHeader("By source type"));
        const entries = Object.entries(data.source_types);
        const maxSrc = entries.length > 0 ? Math.max(...entries.map(([,c]) => c)) : 1;
        for (const [type, count] of entries) {
            const color = SOURCE_COLORS[type] || OTHER_COLOR;
            root.append(barRow(type, count, maxSrc, color));
        }
    }

    /* -------- TRUST TIERS -------- */
    if (data.trust_tiers) {
        root.append(sectionHeader("By trust tier"));
        const entries = Object.entries(data.trust_tiers);
        const maxTier = entries.length > 0 ? Math.max(...entries.map(([,c]) => c)) : 1;
        for (const [tier, count] of entries) {
            const color = TIER_COLORS[tier] || UNCLASSIFIED_COLOR;
            root.append(barRow(tier, count, maxTier, color));
        }
    }

    /* -------- TOPIC ROUTING -------- */
    if (data.routing) {
        root.append(sectionHeader("Topic routing"));
        const entries = Object.entries(data.routing);
        const maxRoute = entries.length > 0 ? Math.max(...entries.map(([,c]) => c)) : 1;
        for (const [lane, count] of entries) {
            const color = ROUTE_COLORS[lane] || "#6e7681";
            root.append(barRow(lane, count, maxRoute, color));
        }
    }

    /* -------- RECENT INGEST LOG -------- */
    if (data.recent && data.recent.length > 0) {
        root.append(sectionHeader("Recent ingest log"));
        const table = h("div", { style: { display: "table", width: "100%", borderCollapse: "collapse", fontSize: "12px" } });

        const recent = data.recent.slice(0, 15);
        for (const entry of recent) {
            const refEl = h("span", { style: { fontFamily: "'SF Mono','Consolas','Liberation Mono',monospace", fontSize: "12px", color: TEXT_COLOR } });
            refEl.textContent = entry.source_ref || entry.id || "(no ref)";

            const badge = sourceBadge(entry.source_type || "other");

            const idEl = h("span", { style: { fontSize: "10px", color: "#8b949e" } });
            const shortId = entry.id && entry.id.length > 12 ? entry.id.slice(0, 12) + "…" : (entry.id || "");
            idEl.textContent = shortId;

            const row = h("div", { style: { display: "table-row" } });
            const cells = h("div", { style: { display: "flex", alignItems: "center", gap: "8px", padding: "5px 8px", borderBottom: "1px solid " + BORDER_COLOR } }, refEl, badge, idEl);
            row.append(cells);
            table.append(row);
        }
        root.append(table);
    }

    return root;
}

/* ---- mount entry point ---- */
export function mount(el, api) {
    let pollTimer = null;
    let eventSource = null;
    let rootEl = null;
    let destroyed = false;

    function buildRoot(data) {
        const frag = document.createDocumentFragment();
        const r = renderRoot(data);
        frag.append(r);
        return r;
    }

    function refresh() {
        if (destroyed) return;
        fetchJson("api/pack/halo-hacker/data/ingest/summary.json").then(raw => {
            if (destroyed) return;
            let data;
            try { data = JSON.parse(raw); } catch (e) {
                data = { total_items: 0, ledger_exists: false, error: "parse failed" };
            }
            if (rootEl) {
                const replacement = buildRoot(data);
                rootEl.replaceWith(replacement);
                rootEl = replacement;
            }
        }).catch(() => {
            /* poll will retry */
        });
    }

    /* initial load */
    fetchJson("api/pack/halo-hacker/data/ingest/summary.json").then(raw => {
        if (destroyed) return;
        let data;
        try { data = JSON.parse(raw); } catch (e) {
            data = { total_items: 0, ledger_exists: false };
        }
        rootEl = buildRoot(data);
        el.append(rootEl);
    }).catch(() => {
        if (destroyed) return;
        /* render error state */
        const errRoot = h("div", { style: { background: DARK_BG, color: TEXT_COLOR, padding: "24px", borderRadius: "8px", border: "1px solid " + BORDER_COLOR, textAlign: "center" } });
        const errMsg = h("div", { style: { fontSize: "14px", color: "#8b949e" } });
        errMsg.textContent = "Failed to load ingest data — is halo-hacker running?";
        errRoot.append(errMsg);
        rootEl = errRoot;
        el.append(rootEl);
    });

    /* poll timer — 15 s */
    pollTimer = setInterval(refresh, 15000);

    /* event source — reload on pack events */
    try {
        const token = sessionStorage.getItem("halo-studio-token");
        const esUrl = "api/events" + (token ? "?t=" + encodeURIComponent(token) : "");
        eventSource = new EventSource(esUrl);
        eventSource.addEventListener("message", function handler(ev) {
            if (destroyed) return;
            try {
                const msg = JSON.parse(ev.data);
                if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") {
                    refresh();
                }
            } catch (_) { /* ignore malformed events */ }
        });
    } catch (_) { /* EventSource not available in all CSP contexts — poll-only fallback */ }

    /* return cleanup */
    return function cleanup() {
        destroyed = true;
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        if (eventSource) { try { eventSource.close(); } catch (_) {} eventSource = null; }
        if (rootEl && rootEl.parentNode) { rootEl.parentNode.removeChild(rootEl); rootEl = null; }
    };
}