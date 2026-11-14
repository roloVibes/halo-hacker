export function mount(el, api) {
    // --- Theme Colors ---
    const colors = {
        bg: '#0d1117',
        text: '#e6edf3',
        border: '#30363d',
        buttonBg: '#21262d',
        green: '#1a7f37', // active/running
        gray: '#8a8f98',  // idle
        red: '#d7263d',   // blocked/error
        blue: '#2f6feb',  // working
        muted: '#666',    // for notes
    };

    let intervalId = null;
    let eventSource = null;
    let rootElement = null;
    let currentToken = null; // To ensure EventSource uses the latest token

    const dataUrl = "/api/pack/halo-hacker/data/live.json"; // Data source path
    const eventUrlBase = "/api/events?t=";

    // --- Helper Functions ---
    function h(tag, props, ...children) {
        const el = document.createElement(tag);
        if (props) {
            for (const [k, v] of Object.entries(props)) {
                if (k === "style") {
                    Object.assign(el.style, v);
                } else {
                    el.setAttribute(k, v);
                }
            }
        }
        for (const c of children) {
            if (c === null || c === undefined) continue;
            if (Array.isArray(c)) {
                c.forEach(child => el.append(child));
            } else {
                el.append(c);
            }
        }
        return el;
    }

    function css(el, styleObj) {
        Object.assign(el.style, styleObj);
    }

    // Badge helper: colored dot + text span
    function badge(status, text) {
        let color = colors.gray; // Default to idle
        if (status === 'running') color = colors.green;
        else if (status === 'working') color = colors.blue;
        else if (status === 'blocked' || status === 'error') color = colors.red;

        return h('span', { class: `badge badge-${status}`, style: { backgroundColor: color, color: colors.text, padding: '2px 8px', borderRadius: '4px', fontSize: '0.8em', marginLeft: '8px', marginRight: '8px', display: 'inline-block', verticalAlign: 'middle' } }, text);
    }

    // fetchJson adapted to parse JSON and use theme colors
    async function fetchJson(path) {
        const headers = {};
        currentToken = sessionStorage.getItem("halo-studio-token"); // Update token
        if (currentToken) headers["Authorization"] = "Bearer " + currentToken;

        try {
            const response = await fetch(path, { headers });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status} for ${path}`);
            }
            return await response.json();
        } catch (error) {
            console.error("Fetch error:", error);
            throw error; // Re-throw to be caught by loadList
        }
    }

    // --- Rendering Functions ---
    function renderHeader(timestamp) {
        return h('div', { class: 'header', style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', borderBottom: `1px solid ${colors.border}` } },
            h('h2', { style: { color: colors.text, margin: 0, fontSize: '1.2em' } }, "Live"),
            h('div', { style: { display: 'flex', alignItems: 'center' } },
                h('button', { id: 'refresh-button', style: { backgroundColor: colors.buttonBg, color: colors.text, border: `1px solid ${colors.border}`, padding: '5px 10px', borderRadius: '4px', cursor: 'pointer', marginRight: '10px' } }, "Refresh"),
                h('span', { id: 'timestamp', style: { fontFamily: 'monospace', color: colors.muted, fontSize: '0.9em' } }, timestamp ? new Date(timestamp).toLocaleString() : "Loading...")
            )
        );
    }

    function renderSessionCard(session) {
        const cwdTail = session.cwd ? session.cwd.split('/').pop() || session.cwd : ''; // Show only the last part of cwd
        const statusColor = session.status === 'running' ? colors.green :
                            session.status === 'working' ? colors.blue :
                            session.status === 'blocked' || session.status === 'error' ? colors.red :
                            colors.gray;

        return h('div', { class: 'session-card', style: { border: `1px solid ${colors.border}`, borderRadius: '6px', padding: '15px', marginBottom: '10px', backgroundColor: colors.buttonBg } },
            h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' } },
                h('h3', { style: { color: colors.text, margin: 0, fontWeight: 'bold', flexGrow: 1, marginRight: '10px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, session.title || 'Untitled Session'),
                badge(session.status, session.status.charAt(0).toUpperCase() + session.status.slice(1)) // Capitalize status
            ),
            h('div', { style: { display: 'flex', alignItems: 'center', fontSize: '0.85em', color: colors.muted } },
                h('span', { style: { marginRight: '10px', fontWeight: 'bold' } }, "cwd:"),
                h('span', { style: { fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, cwdTail || 'N/A')
            ),
            h('div', { style: { marginTop: '8px', display: 'flex', alignItems: 'center' } },
                h('div', { style: { width: '10px', height: '10px', borderRadius: '50%', backgroundColor: statusColor, marginRight: '8px' } }),
                h('span', { style: { color: colors.muted, fontSize: '0.8em' } }, `Status: ${session.status}`)
            )
        );
    }

    function renderSessions(sessions) {
        if (!sessions || sessions.length === 0) {
            return h('div', { class: 'empty-state', style: { padding: '20px', textAlign: 'center', color: colors.muted } }, "No live sessions — start an assessment and agents appear here.");
        }
        return sessions.map(renderSessionCard);
    }

    function renderLines(lines) {
        const lineElements = lines.map(line =>
            h('div', { style: { fontFamily: 'monospace', color: colors.text, fontSize: '0.8em', paddingLeft: '10px', borderLeft: `2px solid ${colors.border}`, marginBottom: '3px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' } }, line)
        );
        return h('div', { id: 'lines-feed', style: { flexGrow: 1, overflowY: 'auto', padding: '10px', borderTop: `1px solid ${colors.border}` } }, lineElements);
    }

    function renderTrafficNote(harnessConnected) {
        if (!harnessConnected) {
            return h('div', { class: 'traffic-note', style: { padding: '10px', textAlign: 'center', color: colors.muted, fontSize: '0.8em', backgroundColor: colors.buttonBg, borderTop: `1px solid ${colors.border}` } }, "Harness not connected — live state unavailable.");
        }
        return null;
    }

    function renderErrorState(errorMessage, retryHandler) {
        return h('div', { style: { padding: '20px', textAlign: 'center', color: colors.red } },
            h('p', errorMessage),
            h('button', { style: { backgroundColor: colors.buttonBg, color: colors.text, border: `1px solid ${colors.border}`, padding: '5px 10px', borderRadius: '4px', cursor: 'pointer' }, onclick: retryHandler }, "Retry")
        );
    }

    function renderLoadingState() {
        return h('div', { style: { padding: '20px', textAlign: 'center', color: colors.muted } }, "Loading...");
    }

    // --- Data Loading and Update Logic ---
    async function loadList() {
        if (!rootElement) return; // Component unmounted

        const headerContainer = rootElement.querySelector('#header-container');
        const sessionsContainer = rootElement.querySelector('#sessions-container');
        const linesFeed = rootElement.querySelector('#lines-feed');
        const trafficNoteEl = rootElement.querySelector('.traffic-note'); // Assuming it gets an ID or class
        const timestampEl = rootElement.querySelector('#timestamp');

        // Show loading state
        if (sessionsContainer) sessionsContainer.innerHTML = ''; // Clear previous content
        if (linesFeed) linesFeed.innerHTML = '';
        if (timestampEl) timestampEl.textContent = "Loading...";
        css(rootElement, { opacity: 0.5 }); // Indicate loading

        try {
            const data = await fetchJson(dataUrl);

            // Update header timestamp
            if (timestampEl) timestampEl.textContent = data.generated ? new Date(data.generated).toLocaleString() : "N/A";
            css(rootElement, { opacity: 1 }); // Restore opacity

            // Render sessions
            if (sessionsContainer) {
                sessionsContainer.innerHTML = ''; // Clear before re-rendering
                const sessionElements = renderSessions(data.sessions);
                if (Array.isArray(sessionElements)) {
                    sessionElements.forEach(el => sessionsContainer.appendChild(el));
                } else {
                    sessionsContainer.appendChild(sessionElements); // For empty state
                }
            }

            // Render lines feed
            if (linesFeed) {
                linesFeed.innerHTML = ''; // Clear before re-rendering
                const linesEl = renderLines(data.lines || []);
                if (linesEl) linesFeed.appendChild(linesEl);
            }

            // Render traffic note
            if (trafficNoteEl) { // It might not exist initially
                const newNote = renderTrafficNote(data.harness);
                if (newNote && !trafficNoteEl.parentNode) {
                    rootElement.appendChild(newNote); // Add if not present
                } else if (!newNote && trafficNoteEl.parentNode) {
                    trafficNoteEl.remove(); // Remove if not needed
                }
            } else {
                 const newNote = renderTrafficNote(data.harness);
                 if (newNote) rootElement.appendChild(newNote);
            }


        } catch (error) {
            console.error("Failed to load data:", error);
            css(rootElement, { opacity: 1 }); // Restore opacity
            // Display error state
            el.innerHTML = ''; // Clear previous content
            el.appendChild(renderErrorState(`Failed to load live data: ${error.message}`, loadList));
            if (intervalId) clearInterval(intervalId);
            if (eventSource) eventSource.close();
        }
    }

    // --- EventSource Setup ---
    function setupEventSource() {
        const token = sessionStorage.getItem("halo-studio-token");
        if (!token || token !== currentToken) {
            // If token changed or is missing, re-setup
            if (eventSource) eventSource.close();
            currentToken = token;
            if (!token) {
                 console.log("No token, EventSource not set up.");
                 return;
            }
        }

        if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
            const url = eventUrlBase + encodeURIComponent(token);
            eventSource = new EventSource(url);

            eventSource.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.event === "pack_event" && msg.data && msg.data.pack === "halo-hacker") {
                        console.log("Received pack_event for halo-hacker, reloading data.");
                        loadList();
                    }
                } catch (e) {
                    console.error("Error parsing EventSource message:", e);
                }
            };

            eventSource.onerror = (error) => {
                console.error("EventSource error:", error);
                eventSource.close(); // Attempt to close and let setupEventSource handle re-opening if needed
                // If loadList fails, it will also try to re-setup things.
            };

            eventSource.onopen = () => {
                console.log("EventSource connected.");
            };
        }
    }

    // --- Initial Render and Setup ---
    function initialize() {
        // Create root element structure
        rootElement = h('div', { id: 'halo-hacker-dashboard', style: { height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: colors.bg, color: colors.text, fontFamily: 'sans-serif' } },
            h('div', { id: 'header-container' }),
            h('div', { id: 'sessions-container', style: { padding: '10px', flexGrow: 1, overflowY: 'auto' } }),
            h('div', { id: 'lines-feed', style: { flexGrow: 1, overflowY: 'auto', padding: '10px', borderTop: `1px solid ${colors.border}` } })
        );
        el.appendChild(rootElement);

        // Render initial loading state
        rootElement.innerHTML = ''; // Clear before adding loading
        rootElement.appendChild(renderLoadingState());

        // Render header placeholder
        const headerContainer = rootElement.querySelector('#header-container');
        if (headerContainer) headerContainer.appendChild(renderHeader("Loading..."));

        // Fetch initial data
        loadList().then(() => {
            // Setup interval and EventSource after initial load success
            intervalId = setInterval(loadList, 15000); // Poll every 15 seconds
            setupEventSource();

            // Add event listener for refresh button
            const refreshButton = rootElement.querySelector('#refresh-button');
            if (refreshButton) {
                refreshButton.onclick = () => {
                    console.log("Refresh button clicked.");
                    loadList(); // Manually refresh
                };
            }
        }).catch(error => {
            console.error("Initial load failed:", error);
            // Error state is already rendered by loadList on failure
        });
    }

    initialize();

    // --- Cleanup Function ---
    return () => {
        console.log("Cleaning up halo-hacker dashboard.");
        if (intervalId) clearInterval(intervalId);
        if (eventSource) eventSource.close();
        if (rootElement && rootElement.parentNode) {
            rootElement.parentNode.removeChild(rootElement);
        }
    };
}
