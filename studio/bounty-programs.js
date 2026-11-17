// HackerOne Programs — scannable Studio bundle panel for h1/programs.json.
// Layout: header actions/search; “My programs” as earned-sorted expandable cards;
// collapsed “All programs” directory for the rest. Long policy/scope text is stripped,
// clamped, and only expanded on demand. Styling is CSSOM-only through css().

function h(tag, props, ...children) {
    const el = document.createElement(tag);
    if (props) for (const [k, v] of Object.entries(props)) el.setAttribute(k, v);
    for (const child of children) if (child !== null && child !== undefined) el.append(child);
    return el;
}

function css(el, styleObj) {
    Object.assign(el.style, styleObj);
}

const DATA_ROOT = "/api/pack/halo-hacker/data/";
const PROGRAMS_PATH = "h1/programs.json";
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
    if (token) headers.Authorization = "Bearer " + token;
    return fetch(path, { headers }).then(r => {
        if (r.status === 404) return JSON.stringify(emptyValue);
        if (!r.ok) throw new Error(path + " -> HTTP " + r.status);
        return r.text();
    });
}

function stripMd(value) {
    return String(value || "")
        .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
        .replace(/`{1,3}([^`]*)`{1,3}/g, "$1")
        .replace(/^\s{0,3}#{1,6}\s*/gm, "")
        .replace(/^\s{0,3}>\s?/gm, "")
        .replace(/^\s{0,3}[-*+]\s+/gm, "")
        .replace(/^\s{0,3}\d+[.)]\s+/gm, "")
        .replace(/[\\#*_`~]/g, "")
        .replace(/\s+/g, " ")
        .trim();
}

function button(text) {
    const btn = h("button", { type: "button" }, text);
    css(btn, { background: "#21262d", border: "1px solid #30363d", color: "#e6edf3", borderRadius: "6px", padding: "6px 11px", cursor: "pointer", fontSize: "12px", fontWeight: "600" });
    return btn;
}

function badge(text, color) {
    const wrap = h("span", null);
    css(wrap, { display: "inline-flex", alignItems: "center", gap: "6px", border: "1px solid #30363d", borderRadius: "999px", padding: "2px 8px", whiteSpace: "nowrap", fontSize: "12px", color: "#e6edf3", background: "#161b22", lineHeight: "1.5" });
    const dot = h("span", null);
    css(dot, { display: "inline-block", width: "8px", height: "8px", borderRadius: "999px", background: color || "#6e7681", flex: "0 0 auto" });
    wrap.append(dot, text || "unknown");
    return wrap;
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

function sectionTitle(text) {
    const title = h("h2", null, text);
    css(title, { margin: "0", fontSize: "15px", lineHeight: "1.4", color: "#e6edf3" });
    return title;
}

function formatMoney(value) {
    const n = Number(value || 0);
    try { return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }); }
    catch (_) { return "$" + Math.round(n).toLocaleString("en-US"); }
}

function asNumber(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n : 0;
}

function programKey(program) { return String(program.handle || program.name || "unknown"); }
function programName(program) { return String(program.name || program.handle || "Unnamed program"); }
function programHandle(program) { return String(program.handle || program.name || "unknown"); }
function isMyProgram(program) { return program.last_invitation_accepted_at_for_user != null || asNumber(program.number_of_reports_for_user) > 0; }
function sortByName(a, b) { return programName(a).localeCompare(programName(b)); }
function sortByEarnedThenName(a, b) {
    const earned = asNumber(b.bounty_earned_for_user) - asNumber(a.bounty_earned_for_user);
    return earned || sortByName(a, b);
}

function submissionBadge(program) {
    const st = String(program.submission_state || "unknown").toLowerCase();
    return badge(st, STATE_COLORS[st] || "#6e7681");
}

function matchesQuery(program, query) {
    if (!query) return true;
    const haystack = [program.handle, program.name].map(v => String(v || "").toLowerCase()).join(" ");
    return haystack.includes(query);
}

export function mount(el, api) {
    const state = {
        programs: [],
        generated: null,
        query: "",
        expandedPrograms: new Set(),
        expandedTexts: new Set(),
        showAll: false,
        lastJson: null,
        loading: true,
        error: "",
        timer: null,
        eventSource: null
    };

    const root = h("div", null);
    css(root, { display: "flex", flexDirection: "column", height: "100%", minHeight: "0", color: "#e6edf3", fontSize: "14px", lineHeight: "1.45", background: "#0d1117" });
    el.appendChild(root);

    const header = h("div", null);
    css(header, { padding: "12px 16px", borderBottom: "1px solid #30363d", display: "grid", gridTemplateColumns: "auto auto minmax(220px, 380px) 1fr", gap: "12px", alignItems: "center" });
    root.appendChild(header);

    const title = h("div", null, "Programs");
    css(title, { fontWeight: "700", fontSize: "17px", whiteSpace: "nowrap" });
    header.appendChild(title);

    const refreshBtn = button("Refresh");
    header.appendChild(refreshBtn);

    const search = h("input", { type: "search", placeholder: "Filter by handle or name", autocomplete: "off", "aria-label": "Filter programs by handle or name" });
    css(search, { width: "100%", minWidth: "220px", background: "#0d1117", border: "1px solid #30363d", color: "#e6edf3", borderRadius: "6px", padding: "7px 10px", fontSize: "13px", outline: "none" });
    header.appendChild(search);

    const headerMeta = h("div", null);
    css(headerMeta, { color: "#8b949e", fontSize: "12px", textAlign: "right", minWidth: "140px" });
    header.appendChild(headerMeta);

    const content = h("div", null);
    css(content, { flex: "1", minHeight: "0", overflow: "auto", padding: "16px" });
    root.appendChild(content);

    async function load() {
        try {
            const text = await fetchJson(dataUrl(PROGRAMS_PATH), { generated: null, programs: [] });
            if (text === state.lastJson && !state.loading && !state.error) return;
            state.lastJson = text;
            const data = JSON.parse(text || "{}");
            state.programs = Array.isArray(data.programs) ? data.programs : [];
            state.generated = data.generated || null;
            state.loading = false;
            state.error = "";
            render();
        } catch (e) {
            state.loading = false;
            state.error = e && e.message ? e.message : String(e);
            render();
        }
    }

    function filteredPrograms() { return state.programs.filter(program => matchesQuery(program, state.query)); }
    function myPrograms() { return filteredPrograms().filter(isMyProgram).sort(sortByEarnedThenName); }
    function directoryPrograms() { return filteredPrograms().filter(program => !isMyProgram(program)).sort(sortByName); }

    function updateHeaderMeta() {
        const total = state.programs.length;
        const shown = filteredPrograms().length;
        if (state.loading) headerMeta.textContent = "Loading…";
        else if (state.query) headerMeta.textContent = `${shown} of ${total} shown`;
        else headerMeta.textContent = `${total} synced`;
    }

    function render() {
        updateHeaderMeta();
        content.replaceChildren();
        if (state.loading) {
            content.appendChild(emptyState("Loading HackerOne programs…"));
            return;
        }
        if (state.error) renderError();
        renderMyPrograms();
        renderAllPrograms();
        renderFooter();
    }

    function renderError() {
        const box = panel();
        css(box, { borderColor: "#f85149", background: "#180d0f" });
        const line = h("div", null, "Error loading programs: " + state.error);
        css(line, { color: "#ff7b72", marginBottom: "10px" });
        const retry = button("Retry");
        retry.addEventListener("click", load);
        box.append(line, retry);
        content.appendChild(box);
    }

    function renderMyPrograms() {
        const mine = myPrograms();
        const wrap = panel();
        const top = h("div", null);
        css(top, { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "12px", marginBottom: "12px" });
        top.appendChild(sectionTitle(`My programs (${mine.length})`));
        top.appendChild(muted("accepted invitations or past reports"));
        wrap.appendChild(top);

        if (!state.programs.length) {
            wrap.appendChild(emptyState("No HackerOne programs synced yet — run a sync."));
        } else if (!mine.length) {
            wrap.appendChild(emptyState(state.query ? "No matching my-programs. Try a different handle or name." : "No accepted or previously reported programs in the synced data."));
        } else {
            const grid = h("div", null);
            css(grid, { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "12px" });
            for (const program of mine) grid.appendChild(programCard(program));
            wrap.appendChild(grid);
        }
        content.appendChild(wrap);
    }

    function programCard(program) {
        const key = programKey(program);
        const open = state.expandedPrograms.has(key);
        const card = h("article", null);
        css(card, { border: "1px solid " + (open ? "#58a6ff" : "#30363d"), borderRadius: "10px", background: open ? "#101923" : "#161b22", padding: "12px", cursor: "pointer", boxShadow: open ? "0 0 0 1px rgba(88,166,255,0.18)" : "none" });
        card.addEventListener("click", () => {
            if (state.expandedPrograms.has(key)) state.expandedPrograms.delete(key);
            else state.expandedPrograms.add(key);
            render();
        });
        card.addEventListener("mouseenter", () => css(card, { borderColor: open ? "#58a6ff" : "#8b949e" }));
        card.addEventListener("mouseleave", () => css(card, { borderColor: open ? "#58a6ff" : "#30363d" }));

        const head = h("div", null);
        css(head, { display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "flex-start" });
        const names = h("div", null);
        css(names, { minWidth: "0" });
        const name = h("div", null, programName(program));
        css(name, { fontWeight: "700", fontSize: "15px", color: "#e6edf3", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        names.append(name, mono(programHandle(program)));
        head.append(names, submissionBadge(program));
        card.appendChild(head);

        const stats = h("div", null);
        css(stats, { marginTop: "10px", color: "#8b949e", fontSize: "13px", display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" });
        stats.append("Reports " + asNumber(program.number_of_reports_for_user), "·", "Valid " + asNumber(program.number_of_valid_reports_for_user), "·");
        const earned = h("strong", null, "Earned " + formatMoney(program.bounty_earned_for_user));
        css(earned, { color: "#3fb950", fontWeight: "700" });
        stats.appendChild(earned);
        card.appendChild(stats);

        const hint = h("div", null, open ? "Click to collapse" : "Click for policy and scope");
        css(hint, { color: "#8b949e", fontSize: "12px", marginTop: "8px" });
        card.appendChild(hint);
        if (open) card.appendChild(programDetail(program));
        return card;
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
        if (!scopes.length) detail.appendChild(emptyState("No scope entries synced for this program."));
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

    function renderAllPrograms() {
        const rest = directoryPrograms();
        const wrap = panel();
        const head = h("button", { type: "button" }, `${state.showAll ? "▾" : "▸"} All programs directory (${rest.length})`);
        css(head, { background: "transparent", border: "0", color: "#e6edf3", cursor: "pointer", fontWeight: "700", fontSize: "15px", padding: "0", textAlign: "left" });
        head.addEventListener("click", () => { state.showAll = !state.showAll; render(); });
        wrap.appendChild(head);
        if (state.showAll) {
            if (!rest.length) wrap.appendChild(emptyState(state.query ? "No matching directory programs." : "No additional programs outside My programs."));
            else {
                const list = h("div", null);
                css(list, { marginTop: "10px", maxHeight: "400px", overflowY: "auto", borderTop: "1px solid #30363d" });
                for (const program of rest) list.appendChild(directoryRow(program));
                wrap.appendChild(list);
            }
        }
        content.appendChild(wrap);
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

    function panel() {
        const box = h("section", null);
        css(box, { background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "14px", marginBottom: "14px" });
        return box;
    }

    function emptyState(text) {
        const div = h("div", null, text);
        css(div, { color: "#8b949e", padding: "16px", textAlign: "center", border: "1px dashed #30363d", borderRadius: "8px", background: "#0d1117" });
        return div;
    }

    function renderFooter() {
        const footer = h("div", null);
        css(footer, { color: "#8b949e", fontSize: "12px", padding: "0 2px 12px 2px" });
        footer.textContent = `Generated: ${state.generated || "never"} · data: ${PROGRAMS_PATH} · run a sync to refresh`;
        content.appendChild(footer);
    }

    function startLiveUpdates() {
        state.timer = setInterval(load, 30000);
        const token = sessionStorage.getItem("halo-studio-token");
        if (token && typeof EventSource !== "undefined") {
            try {
                state.eventSource = new EventSource(`/api/events?t=${encodeURIComponent(token)}`);
                state.eventSource.addEventListener("message", event => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") load();
                    } catch (_) {}
                });
            } catch (_) {}
        }
    }

    search.addEventListener("input", () => { state.query = search.value.trim().toLowerCase(); render(); });
    refreshBtn.addEventListener("click", load);
    load();
    startLiveUpdates();

    return () => {
        if (state.timer) clearInterval(state.timer);
        if (state.eventSource) state.eventSource.close();
        if (root.parentNode === el) el.removeChild(root);
    };
}
