"""
Translator on Drawings — Thai → English construction-drawing PDF translator.

Pipeline:
  1. Extract Thai text spans from a vector PDF (pdfplumber + custom rotation grouping).
  2. For each Thai phrase: glossary lookup → transliterate (names) → Argos Translate (fallback).
  3. Build a redaction overlay PDF (reportlab) with white rectangles + English text.
  4. Merge overlay onto the original PDF (pypdf).
  5. Return translated PDF bytes.

This module is self-contained: it owns its own SQLite database, its own background
job table, and lazy-loads heavy dependencies (Argos, pythainlp).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import socket
import sqlite3
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    """Print + flush so output appears in Render logs without buffering.

    Render's Python runtime sometimes buffers stdout/stderr unless `flush=True`
    is set. logger.info() also goes through buffered handlers in some configs.
    Using print(..., flush=True) is the most reliable way to surface
    diagnostic output from a background thread to Render's log panel.
    """
    print(f"[translator] {msg}", flush=True)

# --------------------------------------------------------------------------------------
# Paths and DB setup
# --------------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# On Render the persistent disk is mounted at /var/data — put translator state
# there so the Argos model, glossary DB, and job files all survive restarts.
# Locally keep everything under <project>/data for easy inspection.
if os.getenv("RENDER"):
    DATA_DIR = "/var/data/translator"
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "translator.db")
JOBS_DIR = os.path.join(DATA_DIR, "translator_jobs")
ARGOS_MODELS_DIR = os.path.join(DATA_DIR, "argos_models")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(ARGOS_MODELS_DIR, exist_ok=True)

# macOS Pythons from python.org ship without a populated SSL trust store, so HTTPS
# downloads (e.g. the Argos model index) fail with CERTIFICATE_VERIFY_FAILED.
# Point urllib/requests at the certifi bundle if SSL_CERT_FILE is not already set.
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _certifi.where())
except ImportError:
    pass

THAI_RE = re.compile(r"[฀-๿]")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS translation_dictionary (
    id           INTEGER PRIMARY KEY,
    source_lang  TEXT NOT NULL DEFAULT 'th',
    target_lang  TEXT NOT NULL DEFAULT 'en',
    source_text  TEXT NOT NULL,
    target_text  TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'phrase',     -- 'phrase' | 'abbrev' | 'name'
    source_kind  TEXT NOT NULL DEFAULT 'manual',     -- 'manual' | 'api' | 'verified'
    domain       TEXT DEFAULT 'construction',
    notes        TEXT,
    use_count    INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_lang, target_lang, source_text)
);

CREATE INDEX IF NOT EXISTS idx_dict_lookup
    ON translation_dictionary (source_lang, target_lang, source_text);

CREATE TABLE IF NOT EXISTS translation_jobs (
    id                TEXT PRIMARY KEY,
    user_id           INTEGER,
    filename          TEXT,
    status            TEXT NOT NULL DEFAULT 'queued',  -- queued | processing | done | error
    page_count        INTEGER,
    text_count        INTEGER DEFAULT 0,
    api_calls         INTEGER DEFAULT 0,
    cache_hits        INTEGER DEFAULT 0,
    progress_percent  INTEGER DEFAULT 0,
    progress_message  TEXT,
    error_message     TEXT,
    duration_ms       INTEGER,
    output_path       TEXT,
    mappings_json     TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# A small seed of common Thai construction terms. Users can refine via the glossary
# UI later. Personal-name and abbreviation rows are added lazily as we encounter them.
SEED_DICTIONARY = [
    ("ระดับ", "Level", "phrase"),
    ("ระดับชั้น", "Floor Level", "phrase"),
    ("ระดับดิน", "Ground Level", "phrase"),
    ("ระดับดินเดิม", "Existing Ground Level", "phrase"),
    ("ระดับน้ำ", "Water Level", "phrase"),
    ("ระดับพื้น", "Floor Level", "phrase"),
    ("แปลน", "Plan", "phrase"),
    ("รูปด้าน", "Elevation", "phrase"),
    ("รูปตัด", "Section", "phrase"),
    ("รายละเอียด", "Detail", "phrase"),
    ("เสา", "Column", "phrase"),
    ("คาน", "Beam", "phrase"),
    ("พื้น", "Slab", "phrase"),
    ("ฐานราก", "Foundation", "phrase"),
    ("ผนัง", "Wall", "phrase"),
    ("ประตู", "Door", "phrase"),
    ("หน้าต่าง", "Window", "phrase"),
    ("บันได", "Stairs", "phrase"),
    ("หลังคา", "Roof", "phrase"),
    ("ห้องน้ำ", "Toilet", "phrase"),
    ("ห้องนอน", "Bedroom", "phrase"),
    ("ห้องครัว", "Kitchen", "phrase"),
    ("ห้องนั่งเล่น", "Living Room", "phrase"),
    ("ห้องอาหาร", "Dining Room", "phrase"),
    ("โครงการ", "Project", "phrase"),
    ("เจ้าของ", "Owner", "phrase"),
    ("ผู้ออกแบบ", "Designer", "phrase"),
    ("วิศวกร", "Engineer", "phrase"),
    ("สถาปนิก", "Architect", "phrase"),
    ("มาตราส่วน", "Scale", "phrase"),
    ("วันที่", "Date", "phrase"),
    ("แบบเลขที่", "Drawing No.", "phrase"),
    # Common Thai professional license abbreviations (placeholder targets — user
    # should refine these via the glossary UI when one exists).
    ("วสถ", "[Architect license: VSTH]", "abbrev"),
    ("สสถ", "[Architect license: SSTH]", "abbrev"),
    ("ภสถ", "[Architect license: PHASTH]", "abbrev"),
    ("วฟก", "[Engineer license: VFK]", "abbrev"),
    ("สฟก", "[Engineer license: SFK]", "abbrev"),
    ("ภฟก", "[Engineer license: PHAFK]", "abbrev"),
]

_INIT_LOCK = threading.Lock()
_INITIALIZED = False


def _connect() -> sqlite3.Connection:
    # isolation_level=None puts the connection in autocommit mode: every statement
    # is its own atomic transaction, so no write lock outlives a single SQL call.
    # That's what we want for this pipeline — many small writes, never a long
    # multi-statement transaction. Combined with WAL + a 30s busy timeout, this
    # eliminates the "database is locked" races between the background thread
    # and the status poller.
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db() -> None:
    """Idempotent DB initialization. Creates tables and seeds the dictionary."""
    global _INITIALIZED
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        with _connect() as conn:
            conn.executescript(SCHEMA_SQL)
            n = conn.execute("SELECT COUNT(*) FROM translation_dictionary").fetchone()[0]
            if n == 0:
                conn.executemany(
                    "INSERT OR IGNORE INTO translation_dictionary "
                    "(source_lang, target_lang, source_text, target_text, kind, source_kind) "
                    "VALUES ('th', 'en', ?, ?, ?, 'manual')",
                    SEED_DICTIONARY,
                )
            conn.commit()
        _INITIALIZED = True


# --------------------------------------------------------------------------------------
# Text-extraction core
# --------------------------------------------------------------------------------------
@dataclass
class TextSpan:
    """A run of Thai-containing characters that share a rotation matrix and a baseline."""
    text: str
    page_index: int
    matrix_sig: tuple
    x0: float
    y0: float
    x1: float
    y1: float
    fontname: str
    size: float
    # Original characters (kept for debugging / advanced redraw)
    chars: list = field(default_factory=list, repr=False)


def _matrix_sig(matrix) -> tuple:
    a, b, c, d = matrix[0], matrix[1], matrix[2], matrix[3]
    return (round(a, 1), round(b, 1), round(c, 1), round(d, 1))


def _is_thai(s: str) -> bool:
    return bool(THAI_RE.search(s))


# Map matrix signature → (page-axis along which text writes, sign)
# Only handles the 4 cardinal orientations seen in CAD-exported PDFs.
_WRITING_DIR = {
    (1.0, 0.0, 0.0, 1.0):   ("x", +1),  # horizontal
    (0.0, 1.0, -1.0, 0.0):  ("y", +1),  # 90° CCW (text reads upward)
    (-1.0, 0.0, 0.0, -1.0): ("x", -1),  # 180° (upside-down)
    (0.0, -1.0, 1.0, 0.0):  ("y", -1),  # 270° (text reads downward)
}


def _extract_thai_spans(page) -> list[TextSpan]:
    """Group Thai chars into phrase-level spans, respecting rotation."""
    thai_chars = [c for c in page.chars if _is_thai(c.get("text", ""))]
    if not thai_chars:
        return []

    spans: list[TextSpan] = []
    by_sig: dict[tuple, list] = {}
    for c in thai_chars:
        by_sig.setdefault(_matrix_sig(c["matrix"]), []).append(c)

    for sig, chars in by_sig.items():
        if sig not in _WRITING_DIR:
            # Unknown rotation — emit each char as its own span (best-effort).
            for c in chars:
                spans.append(_span_from_chars([c], sig, page.page_number - 1))
            continue
        axis, sign = _WRITING_DIR[sig]
        perp = "y" if axis == "x" else "x"

        # Bucket by perpendicular position (rounded), so a "row" of text is one bucket.
        buckets: dict[int, list] = {}
        for c in chars:
            perp_val = c["x0"] if perp == "x" else c["y0"]
            key = round(perp_val / 2.0)  # ~2 pt tolerance
            buckets.setdefault(key, []).append(c)

        for bucket_chars in buckets.values():
            # Sort along writing direction
            if axis == "x":
                bucket_chars.sort(key=lambda c: c["x0"] * sign)
            else:
                bucket_chars.sort(key=lambda c: c["y0"] * sign)

            # Walk and split when gap exceeds ~1.5x the typical char advance
            current: list = []
            last_end: Optional[float] = None
            for c in bucket_chars:
                start = c["x0"] if axis == "x" else c["y0"]
                end = c["x1"] if axis == "x" else c["y1"]
                if sign < 0:
                    start, end = -end, -start  # work in writing-direction coords
                advance = abs(c.get("adv") or c.get("width") or c["x1"] - c["x0"]) or 6.0
                gap_threshold = advance * 1.5
                if current and last_end is not None and (start - last_end) > gap_threshold:
                    spans.append(_span_from_chars(current, sig, page.page_number - 1))
                    current = []
                current.append(c)
                last_end = max(last_end, end) if last_end is not None else end
            if current:
                spans.append(_span_from_chars(current, sig, page.page_number - 1))

    return spans


def _span_from_chars(chars: list, sig: tuple, page_index: int) -> TextSpan:
    text = "".join(c["text"] for c in chars)
    x0 = min(c["x0"] for c in chars)
    y0 = min(c["y0"] for c in chars)
    x1 = max(c["x1"] for c in chars)
    y1 = max(c["y1"] for c in chars)
    fontname = chars[0].get("fontname", "")
    size = max((c.get("size") or 0) for c in chars) or 8.0
    return TextSpan(
        text=text, page_index=page_index, matrix_sig=sig,
        x0=x0, y0=y0, x1=x1, y1=y1, fontname=fontname, size=size, chars=chars,
    )


# --------------------------------------------------------------------------------------
# Translation backends (lazy-loaded)
# --------------------------------------------------------------------------------------
_ARGOS_LOCK = threading.Lock()
_ARGOS_READY = False


def _ensure_argos() -> None:
    """Install the Thai → English Argos model if not already present, then load it."""
    global _ARGOS_READY
    with _ARGOS_LOCK:
        if _ARGOS_READY:
            return
        _log("_ensure_argos: entered")
        os.environ.setdefault("ARGOS_PACKAGES_DIR", ARGOS_MODELS_DIR)
        _log(f"_ensure_argos: ARGOS_PACKAGES_DIR={ARGOS_MODELS_DIR}")
        import argostranslate.package as ap
        import argostranslate.translate as at
        _log("_ensure_argos: argostranslate imported")
        installed = at.get_installed_languages()
        have_th_en = any(
            src.code == "th" and any(t.to_lang.code == "en" for t in src.translations_from)
            for src in installed
        )
        _log(f"_ensure_argos: have_th_en_already_installed={have_th_en}")
        if not have_th_en:
            # Cap every HTTP call at 60 s so a hanging socket can't freeze the
            # background thread indefinitely. Restored in `finally`.
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(60)
            try:
                _log("_ensure_argos: calling update_package_index()…")
                ap.update_package_index()
                _log("_ensure_argos: update_package_index() returned")
                available = ap.get_available_packages()
                _log(f"_ensure_argos: {len(available)} packages available in index")
                pkg = next((p for p in available if p.from_code == "th" and p.to_code == "en"), None)
                if pkg is None:
                    raise RuntimeError("Argos package index has no th→en pair available.")
                _log(f"_ensure_argos: downloading th→en package (~150 MB)…")
                path = pkg.download()
                _log(f"_ensure_argos: download complete → {path}")
                ap.install_from_path(path)
                _log("_ensure_argos: install_from_path() returned — model installed")
            finally:
                socket.setdefaulttimeout(old_timeout)
        _ARGOS_READY = True
        _log("_ensure_argos: ready")


def _argos_translate(text: str) -> str:
    _ensure_argos()
    import argostranslate.translate as at
    _log(f"_argos_translate: translating {len(text)} chars: {text[:40]!r}…")
    out = at.translate(text, "th", "en")
    _log(f"_argos_translate: → {out[:60]!r}…")
    return out


# --------------------------------------------------------------------------------------
# Claude API translation engine (default — high-quality, paid)
# --------------------------------------------------------------------------------------
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 256


def _build_claude_system_prompt() -> str:
    """Domain prompt for Claude. Sized > 2048 tokens to qualify for prompt caching
    on Sonnet 4.6 (anything shorter silently won't cache)."""
    glossary_lines = "\n".join(
        f"  {src}  →  {tgt}" for (src, tgt, _kind) in SEED_DICTIONARY
    )
    return f"""You are a professional Thai-to-English translator specializing in architectural and engineering construction drawings exported from AutoCAD or similar CAD tools to PDF. Your translations are pasted back onto the original drawing in the exact same position as the Thai source text, so they must be precise, concise, and follow the conventional English wording used by Thai construction professionals.

# Translation rules

1. **Domain phrases**: use the precise English construction term, not a literal word-by-word translation. Match the standard English wording a Thai engineer or architect would expect to read on a drawing.
   - "ระดับชั้น" → "Floor Level"  (NOT "level class" or "class level")
   - "เสาเข็ม" → "Pile Foundation"  (NOT "pillar pile" or "needle column")
   - "รูปตัด" → "Section"  (NOT "cut figure")
   - "แปลน" → "Plan"  (NOT "blueprint" or "diagram")

2. **Personal names** (Thai given names, family names, prefixes like นาย/นาง/น.ส./ดร.): transliterate using the **Royal Thai General System (RTGS)**. Do not translate. Capitalize as a proper name.
   - "พิชัยวงศ์" → "Phichaiwong"
   - "จารุวัลลภ" → "Charuwanlop"
   - "ทนงศักดิ์" → "Thanongsak"
   - "ดร.สมชาย" → "Dr. Somchai"
   Use the standard RTGS romanization; don't invent novel spellings.

3. **Professional license abbreviations** (Thai 2-3 letter abbreviations used by the Council of Engineers / Architects of Thailand — e.g. วสถ, สสถ, ภสถ, วฟก, สฟก, ภฟก, วย, สย, ภย, วก, สก, ภก, วฟ, สฟ, ภฟ, วโยธา, สโยธา, ภโยธา): preserve the abbreviation Romanized in brackets, then a short English gloss.
   - "วสถ" → "[VSTH] Architect license"
   - "สสถ" → "[SSTH] Senior Architect license"
   - "ภสถ" → "[PHASTH] Associate Architect license"
   - "ภฟก" → "[PHAFK] Associate Engineer license (M&E)"

4. **Numeric / dimensional labels**: translate only the Thai words; preserve numbers and units (mm, cm, m, %, +, −, x, @) verbatim.
   - "ระดับ +1.250" → "Level +1.250"
   - "ขนาด 3000x4000 มม." → "Size 3000x4000 mm"
   - "ความลึก 1.50 ม." → "Depth 1.50 m"

5. **Conciseness**: drawings have very little space, and English of equivalent meaning is usually 1.5–2× longer than Thai. Prefer the standard short English term over a long literal translation.
   - "ห้องน้ำ" → "Toilet"  (preferred over "Bathroom" / "Water Room")
   - "ห้องน้ำ-ห้องส้วม" → "Toilet"  (combined)
   - "ห้องเก็บของ" → "Storage"  (preferred over "Storage Room")

6. **Compound words and stems**: Thai construction terms are often compounds without spaces. Recognize the stem.
   - Anything starting with "ระดับ" relates to a level/elevation.
   - Anything starting with "ห้อง" is a room — use the standard English room name.
   - Anything starting with "รูป" is a drawing view (plan, section, elevation, detail).
   - Anything starting with "ขนาด" relates to size/dimension.

7. **Project / drawing metadata**: standard one-word English equivalents.
   - "โครงการ" → "Project"
   - "เจ้าของ" → "Owner"
   - "แบบเลขที่" → "Drawing No."
   - "มาตราส่วน" → "Scale"
   - "วันที่" → "Date"
   - "ผู้ออกแบบ" → "Designer"
   - "ผู้ควบคุม" → "Supervisor"

8. **Building elements**: use standard structural / architectural English terms.
   - "เสา" → "Column" (vertical structural)
   - "คาน" → "Beam"
   - "พื้น" → "Slab" (structural) or "Floor" (architectural — context-dependent; default to "Slab" if uncertain)
   - "ผนัง" → "Wall"
   - "ฐานราก" → "Foundation"
   - "หลังคา" → "Roof"
   - "บันได" → "Stairs"

# Output format

Return exactly one line in the form:

`<kind>|<english>`

where `<kind>` is exactly one of these three lowercase tokens:
- `phrase` — a general construction term, label, or descriptor
- `name` — a personal/proper name (transliterated, not translated)
- `abbrev` — a Thai professional license abbreviation

No quotes, no commentary, no leading/trailing whitespace, no markdown, no code fences. Just the single pipe-separated line. Do not echo the input.

# Reference glossary (use these standard translations consistently)

{glossary_lines}

# Few-shot examples

Input: ระดับชั้น
Output: phrase|Floor Level

Input: ระดับดินเดิม
Output: phrase|Existing Ground Level

Input: ระดับพื้นสำเร็จ
Output: phrase|Finished Floor Level

Input: เสาเข็ม
Output: phrase|Pile Foundation

Input: เสาเข็มเจาะ
Output: phrase|Bored Pile

Input: คานคอดิน
Output: phrase|Ground Beam

Input: พื้นคอนกรีตเสริมเหล็ก
Output: phrase|Reinforced Concrete Slab

Input: พิชัยวงศ์
Output: name|Phichaiwong

Input: ทนงศักดิ์
Output: name|Thanongsak

Input: ฟารุงสาง
Output: name|Farungsang

Input: นายสมชาย ใจดี
Output: name|Mr. Somchai Jaidee

Input: วสถ
Output: abbrev|[VSTH] Architect license

Input: ภฟก
Output: abbrev|[PHAFK] Associate Engineer license (M&E)

Input: ห้องน้ำ
Output: phrase|Toilet

Input: ห้องนอนใหญ่
Output: phrase|Master Bedroom

Input: ขนาด 3000x4000
Output: phrase|Size 3000x4000

Input: ความลึก 1.50 ม.
Output: phrase|Depth 1.50 m

Input: มาตราส่วน 1:100
Output: phrase|Scale 1:100

Input: รายละเอียดเสา
Output: phrase|Column Detail

Input: รูปด้านหน้า
Output: phrase|Front Elevation

Now translate the user's input. Output only the single `<kind>|<english>` line.
"""


CLAUDE_SYSTEM_PROMPT = _build_claude_system_prompt()

_CLAUDE_CLIENT = None
_CLAUDE_LOCK = threading.Lock()


def _get_anthropic_client():
    """Lazy-initialize the Anthropic client. Raises if ANTHROPIC_API_KEY is unset
    so the user gets an actionable error rather than a silent failure."""
    global _CLAUDE_CLIENT
    if _CLAUDE_CLIENT is not None:
        return _CLAUDE_CLIENT
    with _CLAUDE_LOCK:
        if _CLAUDE_CLIENT is None:
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Set it in .env (local) "
                    "or in the Render dashboard (production), or set "
                    "TRANSLATOR_ENGINE=argos to use the offline engine."
                )
            import anthropic
            _CLAUDE_CLIENT = anthropic.Anthropic(api_key=key)
            _log("_claude: Anthropic client initialised")
    return _CLAUDE_CLIENT


def _claude_translate(text: str) -> tuple[str, str]:
    """Translate Thai text to English via Claude Sonnet 4.6.

    Returns (english_target, kind) where kind is 'phrase' | 'name' | 'abbrev'.
    Uses prompt caching on the system prompt — the first call in each ~5-minute
    window pays the full input cost; subsequent calls cost ~10× less per input
    token because the system prompt is served from the ephemeral cache.
    """
    _log(f"_claude_translate: input={text[:40]!r} ({len(text)} chars)")
    client = _get_anthropic_client()
    t0 = time.time()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=[{
            "type": "text",
            "text": CLAUDE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Translate: {text}",
        }],
    )

    dt_ms = int((time.time() - t0) * 1000)
    raw = next((b.text for b in response.content if b.type == "text"), "").strip()

    # Parse "<kind>|<english>" — fall back to treating the whole response as a
    # phrase translation if Claude didn't follow the format.
    if "|" in raw:
        kind_raw, target = raw.split("|", 1)
        kind = kind_raw.strip().lower()
        target = target.strip()
        if kind not in ("phrase", "name", "abbrev"):
            kind = "phrase"
    else:
        kind = "phrase"
        target = raw.strip()

    # Cache-hit telemetry. cache_read_input_tokens > 0 confirms the prompt cache
    # is working; if it's 0 across multiple calls there's a silent invalidator.
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    _log(
        f"_claude_translate: → {target[:60]!r} kind={kind} ({dt_ms} ms, "
        f"in:{usage.input_tokens}/out:{usage.output_tokens}/"
        f"cache_read:{cache_read}/cache_write:{cache_write})"
    )

    return target, kind


_PYTHAINLP_LOCK = threading.Lock()
_PYTHAINLP_READY = False


def _transliterate_thai_name(text: str) -> str:
    """Romanise a Thai personal name using the Royal Thai General System."""
    global _PYTHAINLP_READY
    with _PYTHAINLP_LOCK:
        if not _PYTHAINLP_READY:
            from pythainlp.transliterate import romanize  # noqa: F401 (warm import)
            _PYTHAINLP_READY = True
    from pythainlp.transliterate import romanize
    return romanize(text, engine="royin").title()


# --------------------------------------------------------------------------------------
# Translation lookup with caching
# --------------------------------------------------------------------------------------
def _looks_like_personal_name(text: str) -> bool:
    """Heuristic: a long Thai run with no spaces and no obvious 'function' words."""
    # Personal names in our sample run 8+ chars and are pure Thai consonant/vowel runs.
    # Common construction phrases are usually shorter and contain known stems.
    if len(text) < 8:
        return False
    if any(text.startswith(stem) for stem in (
        "ระดับ", "ห้อง", "รูป", "แบบ", "โครง", "วิศว", "สถาป", "ผู้",
        "เจ้า", "ตำแหน่ง", "มาตรา", "วัน", "ขนาด"
    )):
        return False
    return True


@dataclass
class TranslationResult:
    source: str
    target: str
    kind: str           # 'phrase' | 'abbrev' | 'name'
    via: str            # 'cache' | 'transliterate' | 'argos'


def _lookup_or_translate(text: str) -> TranslationResult:
    """Glossary first; fall back to transliteration for names; else Argos.

    Opens its own short-lived connection so no DB lock ever spans an Argos call
    (which can take seconds, especially during the first-run model download).
    """
    text = text.strip()
    if not text:
        return TranslationResult(text, text, "phrase", "cache")

    # 1) Glossary cache (read + bookkeeping update, both autocommit)
    with _connect() as conn:
        row = conn.execute(
            "SELECT target_text, kind FROM translation_dictionary "
            "WHERE source_lang='th' AND target_lang='en' AND source_text=?",
            (text,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE translation_dictionary SET use_count = use_count + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE source_text=?",
                (text,),
            )
            return TranslationResult(text, row["target_text"], row["kind"], "cache")

    # 2) Translation-engine dispatch (no DB lock held during this).
    #    TRANSLATOR_ENGINE=claude (default) — high-quality paid Anthropic API.
    #    TRANSLATOR_ENGINE=argos          — free offline fallback (heavy memory).
    engine = os.getenv("TRANSLATOR_ENGINE", "claude").strip().lower()

    if engine == "claude":
        target, kind = _claude_translate(text)
        via = "claude"
    elif engine == "argos":
        # Personal-name heuristic → transliterate; otherwise Argos.
        if _looks_like_personal_name(text):
            try:
                target = _transliterate_thai_name(text)
                kind, via = "name", "transliterate"
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Transliterate failed for %r: %s", text, e)
                target = _argos_translate(text)
                kind, via = "phrase", "argos"
        else:
            target = _argos_translate(text)
            kind, via = "phrase", "argos"
    else:
        raise RuntimeError(
            f"Unknown TRANSLATOR_ENGINE={engine!r} — expected 'claude' or 'argos'."
        )

    # Cache result in a fresh, short-lived connection. source_kind = the engine
    # that produced it, so the user can later filter / wipe / re-translate by
    # provenance (e.g. wipe Argos rows when switching to Claude).
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO translation_dictionary "
            "(source_lang, target_lang, source_text, target_text, kind, source_kind) "
            "VALUES ('th', 'en', ?, ?, ?, ?)",
            (text, target, kind, via),
        )
    return TranslationResult(text, target, kind, via)


# --------------------------------------------------------------------------------------
# Overlay rendering (reportlab → pypdf merge)
# --------------------------------------------------------------------------------------
def _build_overlay_pdf(
    page_size: tuple[float, float],
    spans_with_translations: list[tuple[TextSpan, TranslationResult]],
) -> bytes:
    """Build a single-page PDF containing white redaction rects and English text."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page_size)

    for span, tr in spans_with_translations:
        w = max(span.x1 - span.x0, 1.0)
        h = max(span.y1 - span.y0, 1.0)

        # White redaction rectangle (in PDF page coords; pdfplumber and reportlab
        # both use bottom-left origin, so x0/y0 maps directly).
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(1, 1, 1)
        c.rect(span.x0, span.y0, w, h, stroke=0, fill=1)

        # English overlay
        en = tr.target or ""
        if not en.strip():
            continue
        c.setFillColorRGB(0, 0, 0)

        axis, sign = _WRITING_DIR.get(span.matrix_sig, ("x", +1))
        # Pick a font size that fits along the writing direction.
        if axis == "x":
            fit_extent = w
        else:
            fit_extent = h
        font_size = _fit_font_size("Helvetica", en, fit_extent, max_size=span.size or 8.0)
        c.setFont("Helvetica", font_size)

        # Translate to the start of the original span and rotate.
        c.saveState()
        if span.matrix_sig == (1.0, 0.0, 0.0, 1.0):
            c.translate(span.x0, span.y0)
            c.drawString(0, 0, en)
        elif span.matrix_sig == (0.0, 1.0, -1.0, 0.0):
            # Original Thai writes upward (text +x → page +y). Rotate 90° CCW.
            c.translate(span.x1, span.y0)
            c.rotate(90)
            c.drawString(0, 0, en)
        elif span.matrix_sig == (-1.0, 0.0, 0.0, -1.0):
            c.translate(span.x1, span.y1)
            c.rotate(180)
            c.drawString(0, 0, en)
        elif span.matrix_sig == (0.0, -1.0, 1.0, 0.0):
            c.translate(span.x0, span.y1)
            c.rotate(270)
            c.drawString(0, 0, en)
        else:
            # Unknown matrix — draw horizontally as a fallback.
            c.translate(span.x0, span.y0)
            c.drawString(0, 0, en)
        c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()


def _fit_font_size(font: str, text: str, max_extent: float, max_size: float) -> float:
    """Largest font size such that drawString(text) fits within max_extent points."""
    if not text:
        return max_size
    size = min(max_size, 14.0)
    while size > 3.0:
        width = pdfmetrics.stringWidth(text, font, size)
        if width <= max_extent:
            return size
        size -= 0.5
    return 3.0


# --------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------
def translate_pdf(input_path: str, output_path: str, progress_cb=None) -> dict:
    """Run the full pipeline. Returns a stats dict including per-mapping list."""
    init_db()
    t0 = time.time()
    stats = {
        "page_count": 0, "text_count": 0,
        "api_calls": 0, "cache_hits": 0, "transliterations": 0,
        "mappings": [],  # list of {source, target, kind, via, page}
    }

    with pdfplumber.open(input_path) as pdf:
        stats["page_count"] = len(pdf.pages)
        overlay_pages: list[bytes] = []

        for page_index, page in enumerate(pdf.pages):
            if progress_cb:
                progress_cb(
                    int(100 * page_index / max(1, stats["page_count"])),
                    f"Processing page {page_index + 1}/{stats['page_count']}",
                )

            spans = _extract_thai_spans(page)
            stats["text_count"] += len(spans)

            spans_with_tr: list[tuple[TextSpan, TranslationResult]] = []
            for span in spans:
                tr = _lookup_or_translate(span.text)
                if tr.via == "cache":
                    stats["cache_hits"] += 1
                elif tr.via == "argos":
                    stats["api_calls"] += 1
                elif tr.via == "transliterate":
                    stats["transliterations"] += 1
                spans_with_tr.append((span, tr))
                stats["mappings"].append({
                    "source": tr.source, "target": tr.target,
                    "kind": tr.kind, "via": tr.via,
                    "page": page_index + 1,
                })

            overlay_pdf = _build_overlay_pdf((page.width, page.height), spans_with_tr)
            overlay_pages.append(overlay_pdf)

        if progress_cb:
            progress_cb(95, "Merging overlays into output PDF")

        # Merge each overlay onto the matching original page.
        original = PdfReader(input_path)
        writer = PdfWriter()
        for i, page in enumerate(original.pages):
            overlay_reader = PdfReader(io.BytesIO(overlay_pages[i]))
            page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)

    stats["duration_ms"] = int((time.time() - t0) * 1000)
    if progress_cb:
        progress_cb(100, "Done")
    return stats


# --------------------------------------------------------------------------------------
# Background-job orchestration
# --------------------------------------------------------------------------------------
def create_job(filename: str, user_id: Optional[int]) -> str:
    init_db()
    job_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            "INSERT INTO translation_jobs (id, user_id, filename, status) "
            "VALUES (?, ?, ?, 'queued')",
            (job_id, user_id, filename),
        )
        conn.commit()
    return job_id


def _update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    cols += ", updated_at = CURRENT_TIMESTAMP"
    with _connect() as conn:
        conn.execute(f"UPDATE translation_jobs SET {cols} WHERE id = ?",
                     (*fields.values(), job_id))
        conn.commit()


def get_job(job_id: str) -> Optional[dict]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM translation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("mappings_json"):
        try:
            d["mappings"] = json.loads(d["mappings_json"])
        except Exception:
            d["mappings"] = []
    else:
        d["mappings"] = []
    d.pop("mappings_json", None)
    return d


def run_job_in_background(job_id: str, input_path: str) -> None:
    """Kick off a background thread that runs the pipeline and updates the job row."""

    # Opportunistic sweep — keeps the JOBS_DIR bounded over time without a cron.
    _cleanup_stale_job_files()

    def _runner():
        _log(f"_runner: thread started for job {job_id}")
        try:
            _log("_runner: calling _update_job(status=processing)…")
            _update_job(job_id, status="processing", progress_percent=1,
                        progress_message="Starting…")
            _log("_runner: status set to 'processing'")
            output_path = os.path.join(JOBS_DIR, f"{job_id}.translated.pdf")

            def cb(pct: int, msg: str):
                _log(f"_runner: progress {pct}% — {msg}")
                _update_job(job_id, progress_percent=pct, progress_message=msg)

            _log(f"_runner: calling translate_pdf({input_path!r})…")
            stats = translate_pdf(input_path, output_path, progress_cb=cb)
            _log(f"_runner: translate_pdf returned. stats={stats}")
            _update_job(
                job_id,
                status="done",
                page_count=stats["page_count"],
                text_count=stats["text_count"],
                api_calls=stats["api_calls"],
                cache_hits=stats["cache_hits"],
                duration_ms=stats["duration_ms"],
                output_path=output_path,
                mappings_json=json.dumps(stats["mappings"], ensure_ascii=False),
                progress_percent=100,
                progress_message="Done",
            )
            _log(f"_runner: job {job_id} marked done")
            # Input PDF is no longer needed once the translated output exists.
            if _safe_remove(input_path):
                _log(f"_runner: deleted input PDF {input_path}")
        except Exception as e:
            _log(f"_runner: EXCEPTION {type(e).__name__}: {e}")
            logger.exception("Translation job failed")
            _update_job(
                job_id, status="error", error_message=f"{type(e).__name__}: {e}",
                progress_percent=100, progress_message="Error",
            )
            # On failure, also drop the input PDF — nothing is going to read it.
            _safe_remove(input_path)

    _log(f"run_job_in_background: starting thread for job {job_id}")
    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    _log(f"run_job_in_background: thread.start() returned")


def save_uploaded_pdf(job_id: str, file_bytes: bytes) -> str:
    path = os.path.join(JOBS_DIR, f"{job_id}.input.pdf")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


# --------------------------------------------------------------------------------------
# PDF cleanup — translation results live in the DB; the PDFs themselves are transient.
# --------------------------------------------------------------------------------------
PDF_RETENTION_SECONDS = 3600  # 1 hour — generous window for download retries


def _safe_remove(path: str) -> bool:
    """Delete a file if it exists. Return True if anything was removed."""
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        _log(f"_safe_remove: could not remove {path}: {e}")
        return False


def remove_output_after_download(job_id: str, output_path: str) -> None:
    """BackgroundTask callback: drop the translated PDF after FastAPI streams it
    back to the user, and null out the DB pointer so a re-download cleanly 404s."""
    if _safe_remove(output_path):
        _log(f"remove_output_after_download: deleted {output_path}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE translation_jobs SET output_path = NULL WHERE id = ?",
                (job_id,),
            )
    except Exception as e:  # pragma: no cover - defensive
        _log(f"remove_output_after_download: DB update failed: {e}")


def _cleanup_stale_job_files(max_age_seconds: int = PDF_RETENTION_SECONDS) -> int:
    """Sweep JOBS_DIR for files older than max_age_seconds and delete them.
    Also clear output_path on any DB row whose file we just removed."""
    now = time.time()
    removed: list[str] = []
    try:
        names = os.listdir(JOBS_DIR)
    except OSError as e:
        _log(f"_cleanup_stale_job_files: cannot list {JOBS_DIR}: {e}")
        return 0

    for fname in names:
        path = os.path.join(JOBS_DIR, fname)
        try:
            if not os.path.isfile(path):
                continue
            if (now - os.path.getmtime(path)) <= max_age_seconds:
                continue
            if _safe_remove(path):
                removed.append(path)
        except OSError as e:
            _log(f"_cleanup_stale_job_files: error on {fname}: {e}")

    if removed:
        try:
            with _connect() as conn:
                placeholders = ",".join("?" * len(removed))
                conn.execute(
                    f"UPDATE translation_jobs SET output_path = NULL "
                    f"WHERE output_path IN ({placeholders})",
                    removed,
                )
        except Exception as e:  # pragma: no cover - defensive
            _log(f"_cleanup_stale_job_files: DB update failed: {e}")
        _log(f"_cleanup_stale_job_files: removed {len(removed)} stale file(s) "
             f"older than {max_age_seconds}s")
    return len(removed)
