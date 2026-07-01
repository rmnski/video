# Wideframe CLI

A command-line tool that watches your video footage for you, finds clips by what's happening in them, and stitches together a rough cut.

---

## What it does (plain English)

You dump a folder of video clips into this thing and it:

1. **Watches every clip** — figures out how long each one is, what resolution, what framerate. If you give it AI access, it'll actually describe what's happening in each scene and transcribe every word spoken.

2. **Lets you search like Google** — type `"person laughing at their phone"` and it finds the clips where that happens. No filenames, no tags, no scrubbing through timelines.

3. **Picks the best stuff** — tell it "give me 20 clips with good lighting" and it ranks them by quality.

4. **Makes you a rough cut** — stitches the selected clips together and exports an mp4 file you can drag into Premiere.

---

## What it does NOT do

- Make Premiere project files (`.prproj`). Nothing open-source can do that. Export the mp4 and import it.

---

## Before you start: what you need on your computer

**You must have these two things:**

- **Python 3.11 or newer**
  - Open Terminal (press Cmd+Space, type "Terminal", hit Enter)
  - Type: `python3 --version`
  - If it says 3.11 or higher, you're good. If not, download from [python.org](https://www.python.org/downloads/).

- **ffmpeg** (the video processing engine)
  - If you have Homebrew: `brew install ffmpeg`
  - If you don't have Homebrew: go to [ffmpeg.org](https://ffmpeg.org/download.html), download the macOS build, follow their instructions.
  - To check if it's installed: `ffmpeg -version`

**Optional — only if you want AI analysis and transcription:**

- **A Google API key** (for AI scene descriptions) — free tier available at [aistudio.google.com](https://aistudio.google.com)
- **An AssemblyAI API key** (for speech-to-text) — free tier at [assemblyai.com](https://www.assemblyai.com)
- These are NOT required. Without them, the tool still works for metadata, proxies, search by filename, and assembly. It just won't describe your scenes or transcribe audio.

---

## Installation

Open Terminal and type these commands one at a time. **Copy and paste them.**

### Step 1: Go into the wideframe folder

```bash
cd ~/path/to/wideframe
```

(Replace `~/path/to/wideframe` with wherever you downloaded or cloned this project.)

### Step 2: Create a virtual environment

This keeps wideframe's dependencies separate from the rest of your system.

```bash
python3 -m venv .venv
```

### Step 3: Activate the virtual environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` appear at the start of your terminal prompt. That means it worked.

### Step 4: Install wideframe

```bash
pip install -e .
```

Wait for it to finish downloading. This might take a minute.

### Step 5: (Optional) Add your API keys

If you got API keys, paste your actual keys in place of the placeholder text:

```bash
export GOOGLE_API_KEY="paste-your-google-key-here"
export ASSEMBLYAI_API_KEY="paste-your-assemblyai-key-here"
```

**Important:** Every time you open a NEW terminal window, you need to do Steps 3 and 5 again (activate the venv + set the keys). Or add those export lines to your `~/.zshrc` file so they stick permanently.

---

## How to use it

Every command starts with `wideframe`. Here's the full workflow, in order.

---

### 1. Create a workspace

A workspace is just a folder that holds everything — your index, proxies, sequences.

```bash
wideframe init my-project --media-path /path/to/your/video/folder
```

**Replace `/path/to/your/video/folder` with the actual folder where your video files live.**

Example:
```bash
wideframe init wedding-footage --media-path ~/Videos/wedding-shoot
```

What happens:
- Creates a folder at `~/Projects/wideframe-clone/workspaces/my-project/`
- Inside that: a database file, a proxies folder, a sequences folder
- Links to your footage (doesn't copy files — saves disk space)

---

### 2. Index your footage

This is the big one. It scans every video in your folder and extracts everything it can.

**With AI (if you set API keys):**
```bash
wideframe index my-project --all
```

**Without AI (metadata + preview files only):**
```bash
wideframe index my-project --all --skip-transcript
```

What happens:
- Scans for `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.mxf`, `.ts` files
- For each file: grabs duration, resolution, framerate
- Makes a small low-quality preview version (proxy) for quick searching
- If API keys are set: sends frames to Google Gemini to describe scenes
- If API keys are set: sends audio to AssemblyAI to transcribe speech
- Stores everything in a searchable database

**This can take a while if you have a lot of footage.** Go grab a coffee.

---

### 3. Search for clips

Once indexing is done, you can search by what's actually IN the footage.

```bash
wideframe search "person giving a speech at a podium" --workspace-name my-project
```

What you get back:
- A numbered list of matching clips
- Duration and quality score for each
- AI description of what's in the clip
- Key moments with timestamps

To get more results:
```bash
wideframe search "crowd cheering" --workspace-name my-project --top-k 50
```

To only see high-quality clips:
```bash
wideframe search "drone shot of beach" --workspace-name my-project --min-quality 80
```

---

### 4. Pick the best clips

Now filter and rank your footage automatically.

```bash
wideframe select --workspace-name my-project --count 20
```

Add filters to narrow it down:

```bash
# Only b-roll, 3 to 10 seconds long, good quality
wideframe select \
  --workspace-name my-project \
  --type b-roll \
  --min-duration 3 \
  --max-duration 10 \
  --min-quality 70 \
  --count 15
```

---

### 5. Build a sequence

Take the selected clips and put them in order.

**Use all selected clips:**
```bash
wideframe assemble my-project rough-cut
```

**Use specific clips** (by their number from the search/select list):
```bash
wideframe assemble my-project highlights --clips "1,3,5,7,9,12"
```

---

### 6. Export as video

Turn your sequence into an actual mp4 file.

```bash
wideframe export my-project rough-cut --format mp4
```

The file will be saved in your workspace folder under `exports/`.

---

### 7. Check what's going on

See all your workspaces and how many clips are indexed:

```bash
wideframe status
```

---

## Full example: from footage to rough cut

Say you have 200 clips from a corporate shoot in `~/Videos/client-shoot/`.

```bash
# 1. Make sure the venv is active
source .venv/bin/activate

# 2. Create the workspace
wideframe init client --media-path ~/Videos/client-shoot

# 3. Index everything (takes a while)
wideframe index client --all

# 4. Find the interview gold
wideframe search "ceo talking about company values" --workspace-name client

# 5. Grab the top 15
wideframe select --workspace-name client --criteria "clear audio, well lit" --count 15

# 6. Build the rough cut
wideframe assemble client rough-cut

# 7. Export
wideframe export client rough-cut
```

Your rough cut is at: `~/Projects/wideframe-clone/workspaces/client/exports/rough-cut.mp4`

Drag it into Premiere, DaVinci, Final Cut — whatever you use — and finish the edit.

---

## Every command at a glance

| Command | What it does |
|---|---|
| `wideframe init <name> --media-path <folder>` | Start a new project |
| `wideframe index <name> --all` | Scan and analyze all footage |
| `wideframe search "<words>" --workspace-name <name>` | Find clips by what's in them |
| `wideframe select --workspace-name <name> --count <number>` | Pick the best clips |
| `wideframe assemble <name> <sequence-name>` | Build a timeline |
| `wideframe export <name> <sequence-name>` | Save as mp4 |
| `wideframe status` | See all projects and stats |

---

## Troubleshooting

**"command not found: wideframe"**
- You forgot to activate the virtual environment. Run `source .venv/bin/activate` first.

**"Error: No such file or directory"**
- The media folder path you typed doesn't exist. Check for typos.

**"GOOGLE_API_KEY not set"**
- You didn't export your API keys, OR you opened a new terminal and forgot. Rerun the `export` commands from Step 5 of Installation.

**"ffmpeg: command not found"**
- ffmpeg isn't installed or isn't in your PATH. Install it — see the "Before you start" section.

**"ModuleNotFoundError: No module named 'wideframe'"**
- You're not in the right folder, or you didn't run `pip install -e .`. Make sure you're `cd`'d into the wideframe project folder and the venv is active.

---

## License

MIT
