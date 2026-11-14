// Live — real-time agent dashboard
// Loaded as ES module: import(url) → { mount(el, api) }
// STUB — Phase 6 implementation replaces this

export function mount(el, api) {
    const div = document.createElement("div");
    div.style.cssText = "color:#8b949e;padding:32px;text-align:center;font-size:14px";
    div.textContent = "Live agent dashboard — coming in halo-hacker 1.0.0. See every agent working in real time with status, current task, and traffic watch.";
    el.appendChild(div);
}