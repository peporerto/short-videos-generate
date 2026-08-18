# Differences Niche (`differences`)

Short-form video pipeline for comparison content (e.g. *desert vs dessert*), starring the mascot **Mr. Worm** (`@Mrworm-b6k`).

---

## Key Features

- **Format & Resolution**: Vertical 9:16 (`720x1280`).
- **Visual Style**: Fixed crumpled-paper background (`assets/differences/background.gif`), fixed `@Mrworm-b6k` watermark, and identical dual image containers.
- **Mascot Poses**: Uses three Mr. Worm poses across 4 distinct beats:
  - `presenter`: Top hat, bow tie, pointer stick.
  - `confused`: Puzzled look with question marks.
  - `professor`: Glasses and open book.
- **Image Container Guardrail**: Strict "cover" crop mode with mandatory validation. Prevents stretching, empty bars, upscaling, or excessive cropping.

---

## 4-Beat Dynamics per Comparison

For each comparison block (`diffN`) in the script, the video renders 4 beats:

| Beat | Name | Duration | Description | Mr. Worm Pose | Images Shown |
|------|------|----------|-------------|---------------|--------------|
| 1 | **Hook** | ~3.0s | Image A (left) & B (right) blur in progressively. Word-by-word caption hook. | `presenter` | A + B |
| 2 | **Question** | ~1.0s | Images disappear. Caption: *"What's the difference?"*. | `confused` | None |
| 3 | **Definition 1** | ~3.0s | Image A reappears centered. Definition A caption builds. | `professor` | A |
| 4 | **Definition 2** | ~3.0s | Image B reappears alongside A. Definition B caption builds. | `professor` | A + B |

If multiple `diff` blocks exist in the script, all 4 beats loop sequentially for each comparison within a single generated video.

---

## Input Structure

Scripts and images must follow this exact layout:

```text
input/differences/
├── script.txt
├── diff1/
│   ├── imageA.png (or .jpg/.jpeg/.webp)
│   └── imageB.png (or .jpg/.jpeg/.webp)
└── diff2/ (optional)
    ├── imageA.png
    └── imageB.png
```

### Script Format (`input/differences/script.txt`)

```text
diff1:
Desert vs Dessert — do you know the difference?
What's the difference?
A desert is a dry, barren landscape that receives very little rainfall.
A dessert is a sweet course eaten at the end of a meal. Don't mix them up!
```

---

## Image Guardrail Rules

Before rendering any frame, `tools/image_container.py` checks two critical guardrails:

1. **No Upscaling**: If the source image resolution is smaller than the target container at the container's aspect ratio, execution halts with a detailed error.
2. **Crop Limit (`crop_threshold_pct`)**: If cropping to fit the container removes more than `35%` (default, configurable) of the source image area, execution halts.

---

## Configuration (`config.yaml`)

Edit the `differences` entry under `nichos:` in `config.yaml`:

```yaml
nichos:
  differences:
    format: "short"
    voice: "en-US-GuyNeural"
    canvas_width: 720
    canvas_height: 1280
    background: "assets/differences/background.gif"
    watermark_text: "@Mrworm-b6k"
    container_width: 300
    container_height: 220
    container_radius: 18
    crop_threshold_pct: 35
    worm_presenter: "assets/worm/presenter.png"
    worm_confused: "assets/worm/confused.png"
    worm_professor: "assets/worm/professor.png"
```

---

## Usage Command

```bash
make run NICHE=differences
```

Or using Poetry directly:

```bash
poetry run python flows/generate_short.py --niche differences
```
