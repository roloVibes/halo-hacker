"""Adapters: turn a source (file tree, PDF, GitHub repo, YouTube video) into Documents.

A Document is the only shape the pipeline understands:
  {source_type, source_ref, content, sha256, fetched_at, trust_tier}

trust_tier: "first-party" (user's own notes) | "third-party" (web/github/youtube —
a LEAD requiring corroboration, never filed as authoritative).
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import subprocess
import urllib.request

TEXT_EXTS = {".md", ".markdown", ".txt", ".org", ".rst"}


def _doc(source_type: str, source_ref: str, content: str, trust_tier: str) -> dict:
    return {
        "source_type": source_type,
        "source_ref": source_ref,
        "content": content,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trust_tier": trust_tier,
    }


# ---------------------------------------------------------------- text trees

def scan_tree(root: str, max_bytes: int = 2_000_000) -> list[dict]:
    """Walk a directory of the user's notes. First-party by definition.

    Skips dot-directories, anything over max_bytes (a note that big is a paste of
    raw output, not a note), and non-text extensions. Returns Documents.
    """
    docs, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext not in TEXT_EXTS:
                skipped.append((p, "non-text ext"))
                continue
            try:
                if os.path.getsize(p) > max_bytes:
                    skipped.append((p, "over size cap"))
                    continue
                with open(p, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError as e:
                skipped.append((p, f"unreadable: {e}"))
                continue
            if not content.strip():
                skipped.append((p, "empty"))
                continue
            docs.append(_doc("notes", os.path.abspath(p), content, "first-party"))
    return docs, skipped


# ---------------------------------------------------------------- pdf

def read_pdf(path: str) -> dict:
    """PDF -> text via PyMuPDF. Raises on encrypted/unreadable — the caller refuses,
    never files a partial document silently."""
    import pymupdf  # local import: only needed when PDFs are actually ingested

    with pymupdf.open(path) as pdf:
        if pdf.is_encrypted:
            raise ValueError(f"encrypted PDF: {path}")
        pages = [page.get_text("text") for page in pdf]
    content = "\n\f\n".join(pages).strip()
    if not content:
        raise ValueError(
            f"PDF has no extractable text (likely scanned): {path} — "
            "run OCR (ocrmypdf) first or use the OCR adapter"
        )
    return _doc("pdf", os.path.abspath(path), content, "first-party")


# ---------------------------------------------------------------- github

def fetch_github(url: str, timeout: int = 30) -> dict:
    """Fetch ONE file from a public GitHub repo (raw). Accepts blob URLs or raw URLs.
    Repo-wide crawling is deliberately NOT here (v0) — one URL, one document,
    explicit and auditable."""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", url)
    if not m:
        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)
    if not m:
        raise ValueError(f"not a GitHub file URL: {url}")
    owner, repo, ref, path = m.groups()
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    with urllib.request.urlopen(raw, timeout=timeout) as r:
        content = r.read().decode("utf-8", errors="replace")
    return _doc("github", url, content, "third-party")


# ---------------------------------------------------------------- youtube

def fetch_youtube(url: str, timeout: int = 120) -> dict:
    """YouTube -> subtitle text via yt-dlp (already on ~/.local/bin for the /watch
    skill). Auto-subs when no manual ones exist. Fails loudly if no subtitles."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        cmd = [
            os.path.expanduser("~/.local/bin/yt-dlp"),
            "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", "en.*", "--convert-subs", "vtt",
            "-o", os.path.join(td, "sub"),
            "--no-warnings", "--quiet",
            url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        vtt = [f for f in os.listdir(td) if f.endswith(".vtt")]
        if proc.returncode != 0 or not vtt:
            raise ValueError(f"yt-dlp failed or no subtitles: {proc.stderr.strip()[:300]}")
        with open(os.path.join(td, vtt[0]), encoding="utf-8", errors="replace") as f:
            raw = f.read()
    content = _vtt_to_text(raw)
    if not content:
        raise ValueError(f"subtitles extracted but empty after cleanup: {url}")
    return _doc("youtube", url, content, "third-party")


def _vtt_to_text(vtt: str) -> str:
    """Strip VTT timing/header/cue markup and collapse the rolling-repeat lines
    auto-subs are full of: each cue repeats the previous text plus a few new
    words, so a line that STARTS WITH the previous kept line replaces it."""
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))
                or "-->" in line or re.fullmatch(r"[\d:.]+", line)):
            continue
        if lines and line.startswith(lines[-1]):
            lines[-1] = line  # cumulative growth: the new cue extends the old one
        elif lines:
            merged = _overlap_merge(lines[-1], line)
            if merged is not None:
                lines[-1] = merged  # rolling window reset: share a suffix/prefix
            elif line != lines[-1]:
                lines.append(line)
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _overlap_merge(a: str, b: str, min_words: int = 2) -> str | None:
    """If a's suffix equals b's prefix (>= min_words), merge: a + b[len(overlap):].
    Returns None when there is no meaningful overlap."""
    aw, bw = a.split(), b.split()
    for k in range(min(len(aw), len(bw)), min_words - 1, -1):
        if aw[-k:] == bw[:k]:
            return " ".join(aw + bw[k:])
    return None
