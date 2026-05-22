# AI Shorts Generator

Automated pipeline for generating narrative videos in Spanish using AI tools.
Creates videos from a script + images, with Ken Burns camera effects, dynamic transitions, and AI-generated voiceover.

---

## Stack

- **Python 3.11+** with Poetry
- **Gemini API** — script generation
- **edge-tts** — text-to-speech (Spanish voices)
- **Pollinations.ai** — free image generation (no account needed)
- **Whisper** — subtitle generation (optional)
- **FFmpeg** — video assembly, effects, transitions

---

## Project Structure

```text
ai-shorts-generator/
├── flows/
│   └── generate_short.py     ← main pipeline
├── tools/
│   ├── script.py             ← Gemini script generation
│   ├── tts.py                ← edge-tts voiceover
│   ├── srt.py                ← Whisper subtitle generation
│   ├── images.py             ← Pollinations image generation
│   ├── video.py              ← FFmpeg assembly + effects
│   ├── sprites.py            ← avatar/background processing
│   └── compositor.py         ← avatar + background compositing
├── assets/
│   ├── avatares/             ← processed avatar PNGs (transparent)
│   ├── escenarios/           ← processed background PNGs
│   └── music/                ← background music files
├── input/
│   ├── script.txt            ← manual script (optional)
│   ├── prompts.txt           ← manual image prompts with effects (optional)
│   ├── images/               ← manual images for Mode A
│   └── audio/                ← manual audio fragments for Mode C
├── output/                   ← generated video and assets
├── config.yaml               ← niche configuration
└── Makefile
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/peporerto/ai-shorts-generator
cd ai-shorts-generator

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Install dependencies
poetry install --no-root

# Install rembg for avatar background removal
poetry run pip install "rembg[cpu]"

# Copy environment file and add your API keys
cp .env.example .env
```

`.env` file:
GEMINI_API_KEY=your_gemini_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_key

Get Gemini API key free at [aistudio.google.com](https://aistudio.google.com)

---

## Pipeline Modes

### Mode A — Manual images + manual script
You provide everything. The pipeline assembles the video.
input/script.txt     ← your script
input/images/        ← your images (numbered: escena_01.png, escena_02.png...)

```bash
make run NICHE=geopolitica
```

---

### Mode B — Manual prompts + manual script
You write the script and define the image prompts with camera effects.
input/script.txt     ← your script
input/prompts.txt    ← one prompt per line with effect

Format of `prompts.txt`:
empty airport corridor at night, cold light, cinematic 2D illustration | pan_right
close up of hands on a table, tense atmosphere | zoom_in
aerial view of Latin American city, warm lights | pan_up

```bash
make run NICHE=geopolitica
```

---

### Mode B Auto — Prompt only
You provide just a topic. Gemini generates the script and image prompts automatically.

```bash
make run NICHE=finanzas PROMPT="por que el 90 por ciento de la gente pierde dinero en bolsa"
```

---

## Available Niches

| Niche | Format | Duration | Voice | Style |
|-------|--------|----------|-------|-------|
| `finanzas` | Short 9:16 | 60s | GonzaloNeural CO | Editorial cinematic |
| `ai_tech` | Short 9:16 | 60s | GonzaloNeural CO | Cyberpunk neon |
| `terror` | Short 9:16 | 5min | AlvaroNeural ES | Dark horror |
| `geopolitica` | Long 16:9 | 5min | LuisNeural EC | Documentary |
| `caricatura` | Short 9:16 | 60s | GonzaloNeural CO | Animated film |
| `esqueletos` | Short 9:16 | 5min | GonzaloNeural CO | Dark editorial |
| `motivacional` | Short 9:16 | 5min | GonzaloNeural CO | Epic landscape |

---

## Camera Effects

Available effects per image in `prompts.txt`:

| Effect | Description |
|--------|-------------|
| `zoom_in` | Slow cinematic zoom in |
| `zoom_out` | Slow zoom out revealing context |
| `zoom_in_out` | Zoom in then reverse, dramatic |
| `pan_right` | Camera travels right |
| `pan_left` | Camera travels left |
| `pan_up` | Camera travels upward |
| `pan_down` | Camera travels downward |

---

## Niche Configuration

Edit `config.yaml` to customize each niche:

```yaml
nichos:
  geopolitica:
    image_style: "cinematic 2D illustration, editorial storytelling style..."
    camera_effect: "pan_left"
    music: "assets/music/dramatic.mp3"
    voice: "es-EC-LuisNeural"
    duration: "medium"
    format: "long"
    narrative_mode: "second_person"
```

Add a new niche by adding a new entry following the same structure.

---

## Script Writing

For best results write your script with Claude using this prompt:
You are an immersive narrative writer for YouTube in Spanish.
Write in SECOND PERSON. The viewer IS the protagonist.
No moral filter. No compassion. Only facts described with surgical precision.
Sensory details in every paragraph: exact temperature, specific smells,
weight of objects, texture of surfaces, sounds that are not forgotten.
Cruelty is not named. It is described.
The viewer must feel pity without being asked to.
Nothing generic. No moralizing. The facts speak for themselves.
Do not use apostrophes or special characters.

---

## Image Generation Workflow

For best quality and consistency:

1. **Characters** — Generate character sheets in Meta AI or ChatGPT with consistent style
2. **Backgrounds** — Generate backgrounds with Pollinations (automatic in Mode B) or Meta AI
3. **Scenes** — Use character reference images + scene description for consistency

Recommended image style prompt for Meta AI:
GTA-style 2D illustration, semi-realistic, big head proportions,
full body character, white background, clean bold lines,
vibrant colors, expressive face, Latin American urban style

---

## Avatar System

Process avatar grids into individual transparent PNGs:

1. Add raw avatar images to `assets/avatares_raw/`
2. Configure `assets/avatares/config.yaml`
3. Run:

```bash
poetry run python tools/sprites.py
```

Test compositing:

```bash
poetry run python tools/compositor.py
```

---

## Video Output

| Format | Resolution | Use case |
|--------|------------|----------|
| `short` | 1080x1920 | YouTube Shorts, TikTok, Reels |
| `long` | 1920x1080 | YouTube long form |

Output file: `output/final_video.mp4`

---

## Makefile Commands

```bash
make install    # Install dependencies
make run        # Run pipeline
make clean      # Clear output folder
```

Run examples:

```bash
# Auto mode — Gemini generates everything
make run NICHE=finanzas PROMPT="el precio del bitcoin hoy"

# Manual mode — your script and images
make run NICHE=geopolitica

# Force format override
make run NICHE=geopolitica FORMAT=short

# Force duration override
make run NICHE=terror PROMPT="la leyenda de la llorona" DURATION=short
```

---

## Monetization Notes

This pipeline is designed to produce original content that meets YouTube monetization requirements:

- Scripts are written by a human with a specific narrative voice
- AI tools assist but do not replace creative decisions
- Each video has an original story, real data, and human editorial judgment
- Image prompts are crafted per video, not templated

---

## Roadmap

- [x] M0 — Project setup and dependency validation
- [x] M1 — Full pipeline Mode A (manual images + script)
- [x] M2 — Mode B with AI image generation
- [x] M3 — Niche config, camera effects, dynamic prompts
- [x] M4 — Documentation and README
- [ ] M5 — Avatar compositing system (sprites + compositor)
- [ ] M6 — ElevenLabs voice integration
- [ ] M7 — YouTube API autopublish
- [ ] M8 — FastAPI server + agent integration

---

## Author

Santiago — [github.com/peporerto](https://github.com/peporerto)

Backend developer building automated content systems.
Stack: TypeScript/NestJS/Python · AWS · PostgreSQL · Redis
