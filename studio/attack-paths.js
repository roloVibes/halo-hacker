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

function fetchJson(path) {
    const headers = {};
    const token = sessionStorage.getItem("halo-studio-token");
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch(path, { headers }).then(r => {
        if (!r.ok) {
            return r.text().then(errorText => {
                throw new Error(`${path} -> HTTP ${r.status} ${r.statusText}. Response: ${errorText}`);
            });
        }
        return r.text();
    }).then(text => {
        try {
            return JSON.parse(text);
        } catch (e) {
            throw new Error(`Failed to parse JSON from ${path}. Content: "${text.substring(0, 200)}..." Error: ${e.message}`);
        }
    });
}

export function mount(el, api) {
    const DATA_PATH = "/api/pack/halo-hacker/data/attack-paths.json";
    // const EVENTS_PATH = "/api/events?t=" + sessionStorage.getItem("halo-studio-token"); // EventSource setup is commented out for now
    const UPDATE_INTERVAL = 15000; // 15 seconds

    let updateTimer = null;
    let currentData = null;
    let loading = false;
    let error = null;

    const styles = {
        container: {
            fontFamily: 'sans-serif',
            backgroundColor: '#0d1117',
            color: '#e6edf3',
            padding: '20px',
            height: '100%',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '20px',
            borderBottom: '1px solid #30363d',
        },
        headerButton: {
            padding: '8px 12px',
            backgroundColor: '#30363d',
            color: '#e6edf3',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
            fontSize: '14px',
        },
        legend: {
            display: 'flex',
            gap: '20px',
            marginBottom: '20px',
            fontSize: '14px',
            flexWrap: 'wrap',
        },
        legendItem: {
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
        },
        severityBadge: {
            width: '15px',
            height: '15px',
            borderRadius: '3px',
            display: 'inline-block',
        },
        graphContainer: {
            flexGrow: 1,
            overflow: 'auto',
            position: 'relative',
            backgroundColor: '#0d1117',
        },
        techniqueListContainer: {
            marginTop: '20px',
            maxHeight: '400px',
            overflowY: 'auto',
            backgroundColor: '#161b22',
            padding: '15px',
            borderRadius: '5px',
        },
        table: {
            width: '100%',
            borderCollapse: 'collapse',
        },
        th: {
            textAlign: 'left',
            padding: '10px',
            backgroundColor: '#30363d',
            color: '#e6edf3',
            borderBottom: '1px solid #444',
        },
        td: {
            padding: '10px',
            borderBottom: '1px solid #444',
        },
        monospace: {
            fontFamily: 'monospace',
            fontSize: '12px',
        },
        muted: {
            color: '#8b949e',
        },
        findingId: {
            fontFamily: 'monospace',
            fontSize: '12px',
            fontWeight: 'bold',
            color: '#8b949e',
            marginRight: '8px',
        },
        findingTitle: {
            flexGrow: 1,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
        },
        node: {
            borderRadius: '5px',
            padding: '8px 12px',
            marginBottom: '10px',
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        },
        confirmedDot: {
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'green',
            marginLeft: '8px',
        },
        candidateDot: {
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: '#8b949e',
            marginLeft: '8px',
        },
        edge: {
            position: 'absolute',
            backgroundColor: '#8b949e',
            opacity: '0.7',
            zIndex: '1',
        },
        solidEdge: {
            backgroundColor: '#58a6ff',
            height: '2px',
        },
        dashedEdge: {
            height: '1px',
            borderStyle: 'dashed',
        },
        edgeLabel: {
            fontFamily: 'monospace',
            fontSize: '10px',
            backgroundColor: '#161b22',
            padding: '2px 4px',
            borderRadius: '3px',
            position: 'absolute',
            transform: 'translate(-50%, -50%)',
            zIndex: '2',
        },
        techniqueId: {
            fontFamily: 'monospace',
            padding: '4px 8px',
            backgroundColor: '#30363d',
            borderRadius: '5px',
            color: '#e6edf3',
            marginRight: '10px',
        },
        techniqueFindingId: {
            fontFamily: 'monospace',
            fontSize: '12px',
            color: '#8b949e',
            marginRight: '10px',
        },
        confirmedBadge: {
            padding: '3px 6px',
            backgroundColor: 'green',
            color: 'white',
            borderRadius: '3px',
            fontSize: '12px',
        },
        loadingIndicator: {
            textAlign: 'center',
            padding: '50px',
            fontSize: '18px',
            color: '#8b949e',
        },
        errorDisplay: {
            textAlign: 'center',
            padding: '50px',
            fontSize: '18px',
            color: '#d7263d',
        },
        emptyState: {
            textAlign: 'center',
            padding: '50px',
            fontSize: '18px',
            color: '#8b949e',
        },
    };

    const severityColors = {
        critical: '#d7263d',
        high: '#f4711f',
        medium: '#e6a817',
        low: '#4a7ba6',
        info: '#8a8f98',
    };

    function renderLegend() {
        const legendEl = h('div', { style: styles.legend });
        legendEl.append(
            h('div', { style: styles.legendItem }, [h('div', { style: {...styles.severityBadge, backgroundColor: severityColors.critical} }), 'Critical']),
            h('div', { style: styles.legendItem }, [h('div', { style: {...styles.severityBadge, backgroundColor: severityColors.high} }), 'High']),
            h('div', { style: styles.legendItem }, [h('div', { style: {...styles.severityBadge, backgroundColor: severityColors.medium} }), 'Medium']),
            h('div', { style: styles.legendItem }, [h('div', { style: {...styles.severityBadge, backgroundColor: severityColors.low} }), 'Low']),
            h('div', { style: styles.legendItem }, [h('div', { style: {...styles.severityBadge, backgroundColor: severityColors.info} }), 'Info']),
            h('div', { style: styles.legendItem }, [h('div', { style: { ...styles.severityBadge, backgroundColor: 'green', width: '10px', height: '10px', borderRadius: '50%' } }), 'Demonstrated Path']),
            h('div', { style: styles.legendItem }, [h('div', { style: { ...styles.severityBadge, backgroundColor: '#8b949e', width: '10px', height: '10px', borderRadius: '0px', border: '1px dashed #8b949e' } }), 'Projected Path']),
            h('div', { style: styles.legendItem }, [h('div', { style: styles.confirmedDot }), 'Confirmed']),
            h('div', { style: styles.legendItem }, [h('div', { style: styles.candidateDot }), 'Candidate']),
        );
        return legendEl;
    }

    function renderNode(nodeData) {
        const nodeEl = h('div', { style: { ...styles.node, borderLeft: `4px solid ${severityColors[nodeData.severity] || severityColors.info}` } });
        const idEl = h('span', { style: styles.findingId }, nodeData.id);
        const titleEl = h('span', { style: styles.findingTitle }, nodeData.title);
        nodeEl.append(idEl, titleEl);

        if (nodeData.confirmed) {
            nodeEl.append(h('div', { style: styles.confirmedDot }));
        } else {
            nodeEl.append(h('div', { style: styles.candidateDot }));
        }
        
        nodeEl.onclick = () => {
            if (api.focusNode) api.focusNode(nodeData.id);
        };
        return nodeEl;
    }

    function renderEdgeLabel(edgeData) {
        const labelEl = h('div', { style: styles.edgeLabel }, edgeData.token);
        return labelEl;
    }

    function renderTechniqueRow(technique) {
        const row = h('tr', {},
            h('td', { style: {...styles.td, ...styles.monospace} }, technique.technique_id),
            h('td', { style: {...styles.td, ...styles.muted, ...styles.monospace} }, technique.finding_id),
        );
        if (technique.confirmed) {
            row.append(h('td', { style: styles.td }, h('span', { style: styles.confirmedBadge }, 'Confirmed')));
        }
        return row;
    }

    function renderTechniqueList(techniques) {
        const container = h('div', { style: styles.techniqueListContainer });
        container.innerHTML = '<h2>MITRE ATT&CK / ATLAS Techniques</h2>';
        
        if (!techniques || techniques.length === 0) {
            container.append(h('div', { style: styles.emptyState }, 'No techniques mapped.'));
            return container;
        }

        const table = h('table', { style: styles.table });
        const thead = h('thead', {},
            h('tr', {},
                h('th', { style: styles.th }, 'Technique ID'),
                h('th', { style: styles.th }, 'Finding ID'),
                h('th', { style: styles.th }, 'Status')
            )
        );
        const tbody = h('tbody', {});
        techniques.forEach(tech => tbody.append(renderTechniqueRow(tech)));
        table.append(thead, tbody);
        container.append(table);
        return container;
    }

    function updateGraphLayout(nodes, edges, graphContainer) {
        const depthMap = new Map();
        const adj = new Map(); // Adjacency list for BFS

        nodes.forEach(node => {
            depthMap.set(node.id, -1); // Initialize depth to -1 (unvisited)
            adj.set(node.id, { incoming: [], outgoing: [] });
        });

        edges.forEach(edge => {
            adj.get(edge.from).outgoing.push(edge);
            adj.get(edge.to).incoming.push(edge);
        });

        const queue = [];
        // Find nodes with no incoming edges (depth 0)
        nodes.filter(node => adj.get(node.id).incoming.length === 0).forEach(node => {
            queue.push(node.id);
            depthMap.set(node.id, 0);
        });

        let head = 0;
        while (head < queue.length) {
            const u = queue[head++];
            const currentDepth = depthMap.get(u);

            adj.get(u).outgoing.forEach(edge => {
                const v = edge.to;
                if (depthMap.get(v) === -1) { // If not visited
                    depthMap.set(v, currentDepth + 1);
                    queue.push(v);
                }
            });
        }

        const maxDepth = Math.max(-1, ...Array.from(depthMap.values()).filter(d => d !== -1));
        
        const nodesByDepth = Array.from({ length: maxDepth + 1 }, () => []);
        nodes.forEach(node => {
            const depth = depthMap.get(node.id);
            if (depth !== -1) {
                nodesByDepth[depth].push(node);
            } else {
                // Handle nodes with no incoming edges that weren't roots (disconnected or cycles)
                // Push them to the last column for visualization
                nodesByDepth[maxDepth].push(node);
            }
        });

        const nodeWidth = 200; // Approximate width of a node element
        const nodeHeight = 50; // Approximate height of a node element
        const columnSpacing = 100; // Space between columns
        const rowSpacing = 15; // Space between nodes in a column
        const svgHeight = nodesByDepth.reduce((sum, col) => sum + col.length * (nodeHeight + rowSpacing), 0);
        const svgWidth = (maxDepth + 1) * (nodeWidth + columnSpacing);
        
        const svg = h('svg', { style: { width: `${svgWidth}px`, height: `${svgHeight}px`, position: 'absolute', top: '0', left: '0', zIndex: '1' } });
        const nodePositions = new Map(); // Store { nodeId: { x, y } }

        let currentX = columnSpacing / 2;
        nodesByDepth.forEach((column, depth) => {
            let currentY = rowSpacing / 2;
            column.forEach(node => {
                nodePositions.set(node.id, { x: currentX, y: currentY });
                currentY += nodeHeight + rowSpacing;
            });
            currentX += nodeWidth + columnSpacing;
        });

        // Draw edges
        edges.forEach(edge => {
            const fromPos = nodePositions.get(edge.from);
            const toPos = nodePositions.get(edge.to);

            if (!fromPos || !toPos) return;

            const line = h('line', {
                x1: fromPos.x + nodeWidth, // Right side of 'from' node
                y1: fromPos.y + nodeHeight / 2,
                x2: toPos.x, // Left side of 'to' node
                y2: toPos.y + nodeHeight / 2,
                style: {
                    ...styles.edge,
                    ...(edge.demonstrated ? styles.solidEdge : styles.dashedEdge),
                    strokeWidth: edge.demonstrated ? '2px' : '1px',
                    stroke: edge.demonstrated ? '#58a6ff' : '#8b949e',
                }
            });
            svg.append(line);
            
            // Add edge label
            const label = renderEdgeLabel(edge);
            // Position label in the middle of the line
            const labelX = (fromPos.x + nodeWidth + toPos.x) / 2;
            const labelY = fromPos.y + nodeHeight / 2;
            css(label, { left: `${labelX}px`, top: `${labelY}px` });
            svg.append(label);
        });

        // Render nodes on top of edges
        nodesByDepth.forEach((column, depth) => {
            let currentY = rowSpacing / 2;
            column.forEach(node => {
                const nodeEl = renderNode(node);
                const xPos = columnSpacing / 2 + depth * (nodeWidth + columnSpacing);
                const yPos = currentY;
                css(nodeEl, { position: 'absolute', left: `${xPos}px`, top: `${yPos}px`, width: `${nodeWidth}px` });
                
                nodeEl.onclick = () => {
                    if (api.focusNode) api.focusNode(node.id);
                };

                svg.append(nodeEl); // Append node element to SVG
                currentY += nodeHeight + rowSpacing;
            });
        });

        return svg;
    }


    function renderGraph(nodes, edges) {
        const graphContainer = h('div', { style: styles.graphContainer });
        
        if (nodes.length === 0) {
            graphContainer.append(h('div', { style: styles.emptyState }, 'No findings to map — run an assessment first.'));
            return graphContainer;
        }

        const svgContainer = h('div', { style: { position: 'relative', width: '100%', height: '100%' } }); 
        graphContainer.append(svgContainer);

        const svgElement = updateGraphLayout(nodes, edges, graphContainer);
        svgContainer.appendChild(svgElement);

        return graphContainer;
    }

    function renderLoading() {
        const loadingEl = h('div', { style: styles.loadingIndicator });
        loadingEl.textContent = 'Loading attack paths...';
        return loadingEl;
    }

    function renderError(err) {
        const errorEl = h('div', { style: styles.errorDisplay });
        errorEl.textContent = `Error loading data: ${err.message}`;
        const retryButton = h('button', { style: styles.headerButton }, 'Retry');
        retryButton.onclick = fetchData;
        errorEl.append(h('div', {}, retryButton));
        return errorEl;
    }

    function renderContent(data) {
        const contentWrapper = h('div', { style: styles.container });

        const header = h('div', { style: styles.header });
        header.append(h('h1', {}, 'Attack Paths'));
        const refreshButton = h('button', { style: styles.headerButton }, 'Refresh');
        refreshButton.onclick = fetchData;
        header.append(refreshButton);
        contentWrapper.append(header);

        contentWrapper.append(renderLegend());

        const graph = renderGraph(data.nodes || [], data.edges || []);
        contentWrapper.append(graph);

        if (data.techniques && data.techniques.length > 0) {
            contentWrapper.append(renderTechniqueList(data.techniques));
        }
        
        if (data.generated) {
            const timestampEl = h('div', { style: { ...styles.muted, fontSize: '12px', marginTop: '10px', textAlign: 'right' }});
            timestampEl.textContent = `Generated: ${new Date(data.generated).toLocaleString()}`;
            contentWrapper.append(timestampEl);
        }

        return contentWrapper;
    }

    function fetchData() {
        if (loading) return;
        loading = true;
        error = null;
        currentData = null;
        el.innerHTML = ''; 
        el.append(renderLoading());

        fetchJson(DATA_PATH)
            .then(data => {
                currentData = data;
                loading = false;
                el.innerHTML = ''; 
                el.append(renderContent(data));
                if (updateTimer) clearInterval(updateTimer);
                updateTimer = setInterval(fetchData, UPDATE_INTERVAL);
            })
            .catch(err => {
                error = err;
                loading = false;
                el.innerHTML = ''; 
                el.append(renderError(err));
            });
    }

    fetchData();

    return () => {
        if (updateTimer) clearInterval(updateTimer);
    };
}
