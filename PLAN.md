# Wideframe Clone — Feasibility Plan

> **Status:** Planning (not started)
> **Created:** 2026-06-30
> **Source:** Analysis of Wideframe (wideframe.com) + CAL copy folder (Claude's Wideframe setup)

---

## Executive Summary

Wideframe is an AI-powered video pre-editing tool that indexes footage, performs agentic search, and assembles Premiere Pro-ready sequences. This plan outlines building an open-source CLI clone that captures ~80% of Wideframe's value — **media analysis, semantic search, clip selection, and sequence assembly** — while dropping the `.prproj`/Premiere project manipulation (no open-source equivalent exists at that depth).

---

## What Wideframe Actually Does

### Core Capabilities (from wideframe.com)

1. **Media Analysis** — Watches terabytes of footage at "superhuman speed": transcripts, scene detection, semantic understanding. All indexed, all searchable. No manual scrubbing or tagging.
2. **Agentic Search** — Find footage by meaning (e.g., "wide shots where people laugh"). Wideframe knows the entire library like a trusted Assistant Editor.
3. **Sequence Assembly** — Describe what you want. Wideframe handles research, pulls selects, builds bins, assembles rough cuts, and delivers Premiere Pro ready sequences. Days of pre-edit work in minutes.
4. **Contextual Generation** — AI-generated content (briefs, copy, b-roll, music, images, video) grounded in the context of your existing work.
5. **Systems Integration** — Reads and writes `.prproj` files natively. Works across filesystem and codecs.

### How It Works (from the site)

- **Non-destructive** — Source files untouched. Wideframe generates its own index.
- **Local-first** — Lives on your machine, works with local files, but accesses cloud-based AI models.
- **M1+ Mac required** — Optimized for Apple Silicon.

---

## What CAL Was (Reference from CAL copy folder)

CAL was **Claude Opus + a custom CLI tool (`caltools`) + a structured knowledge base** configured to run as an "Agent" for Wideframe.

### CAL Architecture

| Layer | What It Does | Open Source Equivalent |
|---|---|---|
| **Media analysis** | Gemini vision describes scenes, key moments, quality | `media-analyze-content-batch` (uses Gemini), CLIP, BLIP, or any vision model |
| **Transcription** | Word-level timestamps | AssemblyAI, Deepgram, Whisper |
| **Proxy generation** | ffmpeg encoding | Pure ffmpeg |
| **.prproj manipulation** | Read/write Premiere projects | **DROPPED** — no open-source equivalent at this depth |
| **DaVinci .drp reading** | Parse Resolve projects | Not prioritized |
| **Cloud/Frame.io/Dropbox** | API integrations | All have public APIs — doable |
| **Workspace management** | Project structure, symlinks, indexing | Custom CLI |

### CAL Knowledge Base (from `kb/` folder)

The CAL copy folder contained a comprehensive knowledge base:
- `kb/tools.md` — Full tool reference (media analysis, transcription, sequences, rendering)
- `kb/video-editing.md` — Timeline management, B-roll techniques, framing, captions
- `kb/selects-workflow.md` — Finding selects, pulling moments, subclips
- `kb/sequences.md` — Sequence data model, tracks, clips
- `kb/workspaces.md` — Workspace structure, directory conventions
- `kb/premiere-pro.md` — .prproj manipulation (dropped from this plan)
- `kb/image-organization.md` — Photo culling, sorting, deduplication

### CAL Session Data

The `projects/` folder contained actual session logs (JSONL files) showing CAL's workflow:
- Workspace initialization
- Media analysis submission
- Transcription jobs
- Sequence assembly
- Clip selection and trimming

This gives us a **real blueprint** for the exact tool specs and workflows we need to replicate.

---

## What We're Building (The 80% Plan)

### Scope: Keep vs Drop

**KEEP (buildable ~80%):**
- Media indexing (analysis + transcription)
- Semantic search across indexed footage
- Clip selection and quality scoring
- Sequence assembly (timeline export)
- Proxy generation (ffmpeg encoding)
- Workspace management (project structure, symlinks)
- Searchable index (SQLite + vector embeddings)

**DROP (~20%):**
- `.prproj` / Premiere project file manipulation
  - No open-source Rust parser exists at this depth
  - Wideframe's custom `caltools` has a dedicated parser
  - Workaround: export as FFmpeg commands or simple XML instead
- DaVinci Resolve `.drp` reading
- Cloud API integrations (Frame.io, etc.) — lower priority

---

## Architecture

### Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ (or Rust + Python bindings) |
| **CLI** | `click` or `argparse` |
| **Media Analysis** | Gemini API (vision), CLIP, or BLIP |
| **Transcription** | AssemblyAI, Deepgram, or Whisper |
| **Video Processing** | ffmpeg (proxy generation, encoding) |
| **Vector Search** | SQLite FTS5 + FAISS / chromadb for embeddings |
| **Storage** | SQLite for metadata, filesystem for media |
| **Proxy** | ffmpeg with configurable presets |

### Directory Structure

```
wideframe/
├── wideframe/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (click/argparse)
│   ├── index.py            # Media indexing (analysis + transcription)
│   ├── search.py           # Semantic search across indexed footage
│   ├── select.py           # Clip selection and quality scoring
│   ├── sequence.py         # Sequence assembly and timeline export
│   ├── proxy.py            # Proxy generation (ffmpeg wrapper)
│   ├── workspace.py        # Workspace management, symlinks
│   ├── models.py           # Data models (Clip, Sequence, Workspace)
│   └── utils.py            # Helpers (ffmpeg, file ops)
├── tests/
├── pyproject.toml
├── README.md
└── PLAN.md                 # This file
```

### Data Model

```python
class Clip:
    path: str                  # Absolute path to source file
    duration: float            # Duration in seconds
    resolution: tuple          # (width, height)
    fps: float
    analysis: dict             # Gemini/CLIP scene description
    transcript: dict           # Word-level timestamps (AssemblyAI/Whisper)
    quality_score: float       # 0-100, based on focus, lighting, stability
    key_moments: list          # Timestamps of key visual moments
    embeddings: list           # Vector embedding for semantic search

class Sequence:
    name: str
    clips: list[Clip]          # Ordered list of selected clips
    trim_points: dict          # {clip_index: (start, end) offsets}
    transitions: list          # Crossfade, dissolve, cut
    export_format: str         # mp4, prores, etc.

class Workspace:
    name: str
    media_path: str            # Path to source media folder
    index_path: str            # Path to SQLite index
    proxy_path: str            # Path to proxy folder
    sequences: list[Sequence]  # All sequences in workspace
```

---

## Implementation Phases

### Phase 1: Media Indexing (Core)

**Goal:** Index a folder of video files — extract metadata, analyze content, transcribe audio, build searchable index.

**Commands:**
```bash
wideframe init --name "project-name" --media-path /path/to/footage
wideframe index --workspace "project-name" --all
```

**Steps:**
1. Scan media folder for video files (mp4, mov, mxf, etc.)
2. For each file:
   - Extract metadata (resolution, fps, duration) via ffprobe
   - Generate proxy (low-res h.264) via ffmpeg for fast preview
   - Run content analysis (Gemini vision / CLIP) — describe scenes, key moments
   - Run transcription (AssemblyAI / Whisper) — word-level timestamps
   - Compute quality score (focus, lighting, stability)
   - Store all data in SQLite index
3. Build vector embeddings for semantic search

**Output:** SQLite database with clip metadata, analysis, transcripts, embeddings.

---

### Phase 2: Semantic Search

**Goal:** Search indexed footage by meaning, not filenames.

**Commands:**
```bash
wideframe search --workspace "project-name" "wide shots of people laughing"
wideframe search --workspace "project-name" --type b-roll --quality 80+
```

**Steps:**
1. Convert search query to vector embedding (same model as indexing)
2. Perform vector similarity search against indexed clips
3. Rank results by relevance + quality score
4. Return top N clips with timestamps and thumbnails

**Output:** Ranked list of clips matching the search query.

---

### Phase 3: Clip Selection

**Goal:** Automatically pick the best clips from indexed footage based on criteria.

**Commands:**
```bash
wideframe select --workspace "project-name" --criteria "interview, clear audio, good lighting" --count 50
wideframe select --workspace "project-name" --type b-roll --min-duration 3s --max-duration 10s
```

**Steps:**
1. Filter indexed clips by criteria (type, quality, duration, content)
2. Rank by quality score + relevance to query
3. Deduplicate (avoid selecting same moment from multiple angles)
4. Return selected clips with timecodes

**Output:** List of selected clips ready for sequence assembly.

---

### Phase 4: Sequence Assembly

**Goal:** Assemble selected clips into a timeline and export.

**Commands:**
```bash
wideframe assemble --workspace "project-name" --sequence "rough-cut" --clips 50
wideframe export --workspace "project-name" --sequence "rough-cut" --format mp4
```

**Steps:**
1. Create sequence from selected clips (ordered list)
2. Apply trim points (start/end offsets per clip)
3. Add transitions (cuts, crossfades)
4. Export as:
   - **Primary:** FFmpeg command / script (since we're dropping .prproj)
   - **Alternative:** Simple XML timeline format
   - **Future:** .prproj via manual parsing (low priority)

**Output:** Exported video file or FFmpeg command for rendering.

---

### Phase 5: Workspace Management & Polish

**Goal:** Project structure, symlinks, batch operations, CLI UX.

**Features:**
- Workspace initialization (media path, proxy path, index path)
- Symlink-based media linking (never copy source files)
- Batch operations (index all, search all, select all)
- Progress tracking (long-running jobs)
- Error handling and retry logic

---

## Key Technical Decisions

### 1. Media Analysis: Gemini vs CLIP vs BLIP

| Option | Pros | Cons |
|---|---|---|
| **Gemini API** | Rich descriptions, scene understanding, word-level accuracy | API cost, requires internet |
| **CLIP (local)** | No API cost, fast, open source | Less detailed descriptions, no transcripts |
| **BLIP (local)** | Good balance of speed/quality | Less proven at scale |

**Recommendation:** Start with Gemini API (matches Wideframe's approach), add CLIP/BLIP as local fallback.

### 2. Transcription: AssemblyAI vs Whisper

| Option | Pros | Cons |
|---|---|---|
| **AssemblyAI** | Word-level timestamps, speaker diarization, high accuracy | API cost, requires internet |
| **Whisper (local)** | No API cost, offline, open source | Slower, less accurate on accents/noise |

**Recommendation:** Start with AssemblyAI (matches Wideframe), add Whisper as local fallback.

### 3. Vector Search: SQLite FTS5 + FAISS

- **SQLite FTS5** for keyword/text search (fast, simple)
- **FAISS** or **chromadb** for vector similarity search (semantic)
- Store embeddings as BLOB in SQLite or separate FAISS index

### 4. Proxy Generation

- ffmpeg encoding to low-res h.264 (e.g., 720p, 15fps)
- Store in `proxies/` subfolder
- Use proxies for preview/search, originals for export

---

## What We Know From CAL (Blueprint)

The CAL copy folder gave us exact tool specs from Wideframe's actual implementation. Key takeaways:

### Media Analysis (`media-analyze-content-batch`)
- Uses Gemini vision to describe scenes, key moments, quality
- Runs on proxy files (not originals) for speed
- Results stored as JSON with scene descriptions, timestamps, quality scores

### Transcription (`media-transcript-get-batch`)
- Word-level timestamps (precision: ±50-100ms)
- Speaker diarization (labeled A, B, C...)
- Providers: AssemblyAI (default), Gemini (fallback)
- Duration limits: 10h per file (AssemblyAI), 30min per file (Gemini)

### Sequence System (`sequence-*` commands)
- Data model: sequences → tracks → clips
- Clips have: source_path, trim_start, trim_end, scale, position
- Supports V1 (base), V2+ (overlays) tracks
- Caption system (CEA-708 for Premiere export)

### Workspace Management
- Symlinks to source media (never copy)
- Project structure: `projects/<name>/` with index, proxies, sequences
- Subagent support (parallel processing)

### Video Editing Guidelines (from `kb/video-editing.md`)
- A-roll (talking head) on V1, B-roll on V2+
- No gaps within sections, dead space between sections
- Speech cut padding: tight (15-25ms start, 5-10ms end)
- Caption defaults: zone 7 (bottom-center), 48-60pt for 16:9
- Quality scoring: focus, lighting, stability, framing

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| API costs (Gemini, AssemblyAI) | Ongoing expense | Add local fallbacks (CLIP, Whisper) |
| Large video libraries (1000+ files) | Slow indexing | Batch processing, parallel jobs, proxy-first |
| No .prproj support | Can't hand off to Premiere directly | Export as FFmpeg commands or XML; document manual import steps |
| No open-source .prproj parser | Cannot match Wideframe's Premiere integration | Accept this limitation; focus on what's buildable |
| GPU requirements for local models | May need cloud API | Default to cloud APIs, offer local as opt-in |

---

## Estimated Effort

| Phase | Complexity | Time (solo) | Time (pair) |
|---|---|---|---|
| Phase 1: Media Indexing | Medium | 2-3 weeks | 1-2 weeks |
| Phase 2: Semantic Search | Medium | 1-2 weeks | 1 week |
| Phase 3: Clip Selection | Medium | 1-2 weeks | 1 week |
| Phase 4: Sequence Assembly | Medium-Hard | 2-3 weeks | 1-2 weeks |
| Phase 5: Polish | Low | 1 week | 3-5 days |

**Total estimate:** 7-11 weeks (solo) / 4-6 weeks (pair)

---

## Why This Is Viable

1. **Wideframe's value is mostly in the pipeline, not magic** — analysis + transcription + search + assembly. All have open-source/affordable equivalents.
2. **CAL copy gives us the exact blueprint** — we know the tool specs, data models, and workflows from a real implementation.
3. **The hard part (.prproj) is dropped** — removing the ~20% that's not replicable makes the remaining 80% very achievable.
4. **CLI-first approach** — no UI to build, just a powerful command-line tool. Can add a simple web UI later if needed.
5. **Python ecosystem has everything** — ffmpeg, AssemblyAI, Gemini, Whisper, FAISS, SQLite. No custom parsers needed.

---

## Next Steps (When We Fire This Up)

1. **Set up the project** — `mkdir wideframe && cd wideframe && python -m venv .venv`
2. **Build Phase 1** — Media indexing CLI (scan, analyze, transcribe, index)
3. **Test with real footage** — Point it at a folder of video, verify indexing works
4. **Build Phase 2** — Semantic search (vector similarity)
5. **Build Phase 3** — Clip selection (filtering + ranking)
6. **Build Phase 4** — Sequence assembly (timeline export)
7. **Polish** — CLI UX, error handling, documentation

---

*This plan was derived from analysis of wideframe.com and the CAL copy folder (Claude's Wideframe configuration). The CAL knowledge base provided exact tool specs and workflows that serve as our implementation blueprint.*
