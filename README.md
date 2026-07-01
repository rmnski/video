# Wideframe CLI

> AI-powered video pre-editing. Point it at footage, search by meaning, get a rough cut.

---

## What it does

1. **Index** — Scans a folder of video files and watches everything for you. Extracts metadata, generates previews, and (if you plug in API keys) has AI describe scenes and transcribe audio.

2. **Search** — Find clips by what's *in* them, not by filename. `"wide shots where people laugh"` → matching results.

3. **Select** — Pick the best clips automatically. Filter by quality, duration, type.

4. **Assemble & Export** — Stitch selected clips into a sequence and export an mp4.

---

## What it does NOT do

- Premiere `.prproj` files — there's no open-source parser for those. Export the rough cut and import it manually.

---

## Install

### 1. You need these on your machine first

- **Python 3.11 or newer**
- **ffmpeg** — `brew install ffmpeg` (Mac) or download from [ffmpeg.org](https://ffmpeg.org)
- **API keys** (optional — skip transcription without them):
  - `GOOGLE_API_KEY` — for AI scene analysis (Gemini)
  - `ASSEMBLYAI_API_KEY` — for transcription
  - `OPENAI_API_KEY` — for Whisper transcription (alternative)

### 2. Install wideframe

```bash
cd wideframe-clone
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Set your API keys (optional)

```bash
export GOOGLE_API_KEY="your-key-here"
export ASSEMBLYAI_API_KEY="your-key-here"
```

Or add them to your shell profile (`~/.zshrc`).

---

## How to use

### Create a workspace

```bash
wideframe init my-project --media-path ~/Videos/footage
```

This creates a folder at `~/Projects/wideframe-clone/workspaces/my-project/` with a database and proxy folder.

### Index your footage

```bash
wideframe index my-project --all
```

This scans every video in the folder. It extracts metadata (duration, resolution, fps), generates low-res proxies for fast preview, and — if API keys are set — runs AI analysis and transcription.

**Skip transcription/AI** (metadata + proxies only):

```bash
wideframe index my-project --all --skip-transcript
```

### Search for clips

```bash
wideframe search "interview moments about pricing" --workspace-name my-project
```

Returns ranked results with timestamps.

### Pick the best clips

```bash
wideframe select --workspace-name my-project --criteria "b-roll, good lighting" --count 20
```

Filter by type, duration, or quality:

```bash
wideframe select --workspace-name my-project --type b-roll --min-duration 3s --max-duration 10s
```

### Assemble a sequence

```bash
wideframe assemble my-project rough-cut
```

Uses all selected clips. To pick specific ones:

```bash
wideframe assemble my-project rough-cut --clips "1,3,5,7,9"
```

### Export

```bash
wideframe export my-project rough-cut --format mp4
```

### Check status

```bash
wideframe status
```

---

## Real example

You come back from a shoot with 200 clips in `~/Videos/shoot/`.

```bash
# 1. Set up
wideframe init client-shoot --media-path ~/Videos/shoot

# 2. Index everything (grab coffee, it'll take a bit)
wideframe index client-shoot --all

# 3. Find the interview gold
wideframe search "client talking about budget concerns" --workspace-name client-shoot

# 4. Pull the best 15
wideframe select --workspace-name client-shoot --criteria "clear audio, good lighting" --count 15

# 5. Assemble and export
wideframe assemble client-shoot rough-cut
wideframe export client-shoot rough-cut
```

Rough cut's in `~/Projects/wideframe-clone/workspaces/client-shoot/exports/`. Drag it into Premiere to finish.

---

## Commands at a glance

| Command | What it does |
|---|---|
| `init <name> --media-path <path>` | Create a new workspace |
| `index <workspace> --all` | Scan and index all footage |
| `search "<query>" --workspace-name <name>` | Find clips by meaning |
| `select --workspace-name <name>` | Pick best clips by criteria |
| `assemble <workspace> <sequence>` | Build a sequence from clips |
| `export <workspace> <sequence>` | Export sequence as video |
| `status` | Show all workspaces and stats |

---

## License

MIT
