"""
Pipeline de mascota por reuso de microclips — reemplaza tools/lipsync.py (Rhubarb)
para el niche `mascota_tutorial`.

Importante: este módulo SOLO genera el video silencioso concatenado
(output/clips/raw_concat.mp4). El audio, la música, el color grade y los
subtítulos ya los pone tools/video.py::assemble_video, que soporta este caso
exacto (num_images=0 + raw_concat.mp4 ya existente -> skip_render) — es el
mismo mecanismo que ya usa el niche `differences`. No hay que reimplementar
esa parte.

Flujo:
    build_library()              -> corta el master en microclips + library.json
    detect_speech_segments()     -> habla/pausa del audio (silencedetect, sin Rhubarb)
    match_clips()                -> empareja segmentos con clips por duración
    build_raw_video()            -> concatena la secuencia -> raw_concat.mp4
    generate_mascota_raw_video() -> orquesta las 4 anteriores (esto es lo que
                                     llama flows/generate_short.py)

CAMBIOS (fix corrupción de librería al cambiar de master_video):
    - build_library() ahora recorta usable_range/exclude_ranges a la duración
      REAL del master (sea más largo o más corto que el anterior), en vez de
      confiar ciegamente en los valores pasados por el caller.
    - Cada clip cortado se valida con _probe_duration() antes de entrar al
      manifest. Si ffmpeg escribió un archivo sin stream de video (corte más
      allá del contenido real — típico al cambiar de master), se descarta en
      vez de quedar en el manifest con motion=0.0, que lo volvía "el clip más
      quieto" y candidato automático a idle_clip para TODAS las pausas.
"""

import os
import json
import random
import subprocess
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageStat

from tools.tts import get_segment_duration
from tools.video import FORMAT_CONFIG


# ---------------------------------------------------------------------------
# 1. Librería de microclips
# ---------------------------------------------------------------------------

def build_library(
    master_video: str,
    out_dir: str,
    manifest_path: str,
    video_format: str = "short",
    usable_range: Tuple[float, Optional[float]] = (0.0, None),
    exclude_ranges: Optional[List[Tuple[float, float]]] = None,
    clip_min_sec: float = 1.0,
    clip_max_sec: float = 2.0,
    fps: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, float]:
    """
    Corta `master_video` en microclips de clip_min_sec-clip_max_sec, saltando
    exclude_ranges (glitches, ej. el frame con dientes) y limitando a usable_range
    (antes del fade a blanco). Cada clip se recorta/escala centrado a la
    resolución del niche (el master es horizontal 1920x1080; para 'short'
    -1080x1920- se hace crop vertical centrado, igual que un recorte de retrato
    normal). Guarda manifest_path con {clip_name: duracion}.

    usable_range/exclude_ranges se recortan a la duración REAL del master
    (ver total_dur más abajo), así que si cambiás de video por uno más largo
    o más corto, no hace falta tocar estos valores a mano — y si igual quedan
    mal calculados, cualquier clip que salga sin contenido real se descarta
    en vez de romper el pipeline más adelante.
    """
    if seed is not None:
        random.seed(seed)

    exclude_ranges = exclude_ranges or []
    os.makedirs(out_dir, exist_ok=True)
    fmt = FORMAT_CONFIG.get(video_format, FORMAT_CONFIG["short"])

    src_w, src_h = _probe_resolution(master_video)
    vf = _crop_scale_filter(src_w, src_h, fmt["width"], fmt["height"])

    total_dur = get_segment_duration(master_video)
    if not total_dur or total_dur <= 0:
        raise RuntimeError(
            f"No se pudo leer la duración de '{master_video}' "
            f"(¿archivo corrupto, vacío, o ruta incorrecta?)."
        )

    start, end = usable_range
    start = max(0.0, start)
    end = total_dur if end is None else min(end, total_dur)
    if start >= end:
        raise ValueError(
            f"usable_range={usable_range} queda fuera de la duración real del "
            f"master ({total_dur:.2f}s) — revisá el rango, sobre todo si "
            f"acabás de cambiar de video."
        )

    # recortamos también exclude_ranges a la duración real, por las dudas
    exclude_ranges = [
        (max(0.0, s), min(e, total_dur)) for s, e in exclude_ranges if s < total_dur
    ]

    segments = _subtract_ranges(start, end, exclude_ranges)

    manifest: Dict[str, float] = {}
    clip_idx = 1
    skipped = 0
    for seg_start, seg_end in segments:
        t = seg_start
        while t < seg_end - 0.05:
            dur = min(random.uniform(clip_min_sec, clip_max_sec), seg_end - t)
            if dur < 0.4:
                break
            clip_name = f"clip_{clip_idx:03d}.mp4"
            clip_path = os.path.join(out_dir, clip_name)
            _cut_clip(master_video, t, dur, clip_path, vf, fps=fps)

            real_dur = _probe_duration(clip_path)
            if real_dur is None or real_dur < 0.35:
                # El corte cayó fuera del contenido real del video (típico al
                # cambiar a un master más corto que el anterior). Descartamos
                # el archivo en vez de dejarlo en el manifest: si queda, su
                # motion sale 0.0 y termina elegido como idle_clip para TODAS
                # las pausas -> el crash que viste.
                if os.path.exists(clip_path):
                    os.remove(clip_path)
                skipped += 1
                t += dur
                continue

            motion = _mouth_activity_score(clip_path)
            manifest[clip_name] = {"duration": round(real_dur, 3), "motion": round(motion, 3)}
            clip_idx += 1
            t += dur

    if not manifest:
        raise RuntimeError(
            "build_library() no generó ningún clip válido a partir de "
            f"'{master_video}'. Revisá master_video, usable_range y "
            "exclude_ranges — probablemente no coinciden con el contenido real."
        )
    if skipped:
        print(
            f"[mascota_clips] Aviso: se descartaron {skipped} recorte(s) "
            f"inválido(s) (fuera del contenido real del video)."
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Marca de qué master_video generó esta biblioteca, para poder detectar
    # más adelante si cambió y hay que reconstruir (ver _library_is_stale).
    with open(_source_marker_path(manifest_path), "w", encoding="utf-8") as f:
        f.write(f"{os.path.abspath(master_video)}|{os.path.getmtime(master_video)}")

    return manifest


def _source_marker_path(manifest_path: str) -> str:
    return manifest_path + ".source"


def _library_is_stale(manifest_path: str, master_video: str) -> bool:
    """
    True si no hay marca de origen todavía, o si el master_video cambió
    (ruta distinta, o mismo nombre pero contenido/fecha de modificación
    distintos). Así, si cambias de video pero reusas el mismo nombre de
    archivo, igual se detecta el cambio.
    """
    marker = _source_marker_path(manifest_path)
    if not os.path.exists(marker):
        return True
    with open(marker, "r", encoding="utf-8") as f:
        saved = f.read().strip()
    current = f"{os.path.abspath(master_video)}|{os.path.getmtime(master_video)}"
    return saved != current


def _probe_resolution(video_path: str) -> Tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        video_path,
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error obteniendo resolución de '{video_path}':\n{r.stderr.decode('utf-8')}")
    w, h = r.stdout.decode("utf-8").strip().split(",")
    return int(w), int(h)


def _probe_duration(path: str) -> Optional[float]:
    """
    Duración real (en segundos) del archivo vía ffprobe, o None si no tiene
    stream de video válido / está vacío (mismo síntoma que 'duration=N/A' al
    correr ffprobe a mano).
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path,
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None
    out = r.stdout.decode("utf-8").strip()
    if not out or out.upper() == "N/A":
        return None
    try:
        val = float(out)
    except ValueError:
        return None
    return val if val > 0 else None


def _crop_scale_filter(src_w: int, src_h: int, target_w: int, target_h: int) -> str:
    """Crop centrado al aspect ratio del target y luego escala exacto (sin deformar)."""
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if abs(src_ratio - target_ratio) < 1e-3:
        return f"scale={target_w}:{target_h}"

    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = int(round(src_h * target_ratio))
    else:
        crop_w = src_w
        crop_h = int(round(src_w / target_ratio))

    x = (src_w - crop_w) // 2
    y = (src_h - crop_h) // 2
    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={target_w}:{target_h}"


def _subtract_ranges(start: float, end: float, exclude: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Sub-intervalos de [start, end] que no caen dentro de ningún rango excluido."""
    exclude = sorted(exclude)
    segments = []
    cursor = start
    for ex_start, ex_end in exclude:
        if ex_end <= cursor or ex_start >= end:
            continue
        if ex_start > cursor:
            segments.append((cursor, min(ex_start, end)))
        cursor = max(cursor, ex_end)
    if cursor < end:
        segments.append((cursor, end))
    return segments


def _mouth_activity_score(clip_path: str, n_samples: int = 6) -> float:
    """
    Puntaje de 'actividad de boca': diferencia promedio entre frames consecutivos
    en la región central del rostro (donde cae la boca). Clips con boca moviéndose
    (hablando) dan un puntaje alto; clips con boca cerrada/quieta dan uno bajo.
    Sin IA — solo diff de píxeles con PIL.
    """
    tmp_dir = clip_path + ".frames_tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        cmd = [
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", "scale=200:-1",
            "-vsync", "vfr",
            "-frames:v", str(n_samples),
            os.path.join(tmp_dir, "s_%02d.png"),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        frames = sorted(os.listdir(tmp_dir))
        if len(frames) < 2:
            return 0.0

        imgs = [Image.open(os.path.join(tmp_dir, f)).convert("L") for f in frames]
        w, h = imgs[0].size
        # región central: donde cae la cara/boca en el crop vertical ya normalizado
        box = (int(w * 0.25), int(h * 0.15), int(w * 0.75), int(h * 0.55))
        crops = [im.crop(box) for im in imgs]

        diffs = [ImageStat.Stat(ImageChops.difference(a, b)).mean[0] for a, b in zip(crops, crops[1:])]
        return sum(diffs) / len(diffs) if diffs else 0.0
    finally:
        for fn in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, fn))
        os.rmdir(tmp_dir)


def _cut_clip(master_video: str, start: float, duration: float, out_path: str, vf: str, fps: int = 30) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", master_video,
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an",
        out_path,
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error cortando clip en {start:.2f}s:\n{r.stderr.decode('utf-8')}")


# ---------------------------------------------------------------------------
# 2. Análisis del audio (habla / pausa) — sin Rhubarb, sin visemas
# ---------------------------------------------------------------------------

def detect_speech_segments(
    audio_path: str,
    noise_db: str = "-30dB",
    min_silence_sec: float = 0.3,
) -> List[Dict[str, float]]:
    """
    Usa ffmpeg silencedetect para partir el audio (el mismo output/audio.mp3
    que ya genera tts.py, sea edge-tts hoy o ElevenLabs cuando se integre en
    M6) en tramos "speech"/"pause" con su duración. No necesita fonemas.
    """
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={noise_db}:d={min_silence_sec}",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log = r.stderr.decode("utf-8")

    total_dur = get_segment_duration(audio_path)
    silences: List[Tuple[float, float]] = []
    silence_start = None
    for line in log.splitlines():
        if "silence_start" in line:
            silence_start = float(line.split("silence_start:")[1].strip())
        elif "silence_end" in line and silence_start is not None:
            silence_end = float(line.split("silence_end:")[1].split("|")[0].strip())
            silences.append((silence_start, silence_end))
            silence_start = None

    segments: List[Dict[str, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start > cursor:
            segments.append({"type": "speech", "duration": round(s_start - cursor, 3)})
        segments.append({"type": "pause", "duration": round(s_end - s_start, 3)})
        cursor = s_end
    if cursor < total_dur:
        segments.append({"type": "speech", "duration": round(total_dur - cursor, 3)})

    return segments


# ---------------------------------------------------------------------------
# 3. Selección de clips por duración
# ---------------------------------------------------------------------------

def match_clips(
    segments: List[Dict[str, float]],
    manifest: Dict[str, Dict[str, float]],
    pause_freeze_min: float = 0.3,
    duration_pool: int = 5,
    motion_pref: int = 2,
) -> List[Tuple[str, str, float]]:
    """
    Devuelve una secuencia de (tipo, clip_o_fuente, duracion):
      - ("clip", nombre_clip, duracion)      -> usar ese microclip tal cual
      - ("freeze", nombre_clip_fuente, dur)  -> congelar el último frame de ese clip

    Habla: junta los `duration_pool` clips más cercanos en duración al segmento,
    y entre esos elige al azar entre los `motion_pref` con MÁS actividad de boca
    (evita el "mudo" — un clip de boca cerrada quedando en un tramo hablado).
    Pausa: usa el clip con MENOS actividad de boca de toda la librería (el más
    "quieto" disponible) — no el último que se usó para hablar, y no un frame
    congelado (eso se ve trabado, no como una pausa natural).
    """
    if not manifest:
        raise ValueError("La librería de microclips está vacía — corré build_library primero.")

    idle_clip = min(manifest.items(), key=lambda kv: kv[1]["motion"])[0]
    sequence: List[Tuple[str, str, float]] = []

    for seg in segments:
        if seg["type"] == "pause":
            if seg["duration"] >= pause_freeze_min:
                sequence.append(("pause", idle_clip, seg["duration"]))
            continue

        remaining = seg["duration"]
        while remaining > 0.2:
            by_duration = sorted(manifest.items(), key=lambda kv: abs(kv[1]["duration"] - remaining))[:duration_pool]
            by_duration.sort(key=lambda kv: kv[1]["motion"], reverse=True)
            name, info = random.choice(by_duration[:motion_pref])
            sequence.append(("clip", name, info["duration"]))
            remaining -= info["duration"]

    return sequence


# ---------------------------------------------------------------------------
# 4. Montaje del silencioso — esto reemplaza el raw_concat.mp4 de lipsync.py
# ---------------------------------------------------------------------------

def build_raw_video(
    sequence: List[Tuple[str, str, float]],
    library_dir: str,
    manifest: Dict[str, Dict[str, float]],
    output_path: str,
    fps: int = 30,
) -> None:
    """
    Concatena la secuencia en un video SIN audio (output/clips/raw_concat.mp4).
    tools/video.py::assemble_video toma esto desde ahí y le pega audio/música/
    subtítulos/color — no se repite esa lógica acá.
    """
    tmp_dir = output_path + ".tmp_pause"
    os.makedirs(tmp_dir, exist_ok=True)
    concat_file = output_path + ".concat_list.txt"

    try:
        with open(concat_file, "w", encoding="utf-8") as f:
            for i, (kind, name, dur) in enumerate(sequence):
                if kind == "clip":
                    clip_path = os.path.abspath(os.path.join(library_dir, name))
                else:  # "pause"
                    source_path = os.path.abspath(os.path.join(library_dir, name))
                    clip_path = os.path.abspath(os.path.join(tmp_dir, f"pause_{i:03d}.mp4"))
                    idle_duration = manifest[name]["duration"]
                    _make_pause_clip(source_path, idle_duration, dur, clip_path, fps=fps)
                f.write(f"file '{clip_path.replace(chr(92), '/')}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-vsync", "cfr",
            output_path,
        ]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError(f"Error concatenando clips:\n{r.stderr.decode('utf-8')}")
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)
        for fn in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, fn))
        os.rmdir(tmp_dir)


def _make_pause_clip(idle_clip_path: str, idle_duration: float, hold_sec: float, out_path: str, fps: int = 30) -> None:
    """
    Rellena una pausa con metraje REAL e inmóvil (no un frame congelado) —
    recorta los primeros `hold_sec` del clip más quieto de la librería, así
    conserva su movimiento sutil (respiración, parpadeo) en vez de verse
    como un video trabado.
    Si la pausa dura más que el propio clip quieto (caso raro), se completa
    el resto congelando su último frame.
    """
    if hold_sec <= idle_duration:
        cmd = [
            "ffmpeg", "-y",
            "-i", idle_clip_path,
            "-t", f"{hold_sec:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            out_path,
        ]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError(f"Error recortando clip de pausa:\n{r.stderr.decode('utf-8')}")
        return

    # pausa más larga que el clip más quieto disponible: usar el clip completo
    # y congelar solo el remanente
    extra = hold_sec - idle_duration
    tail_path = out_path + ".tail.mp4"
    _make_freeze_clip(idle_clip_path, extra, tail_path, fps=fps)

    concat_list = out_path + ".concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(idle_clip_path).replace(chr(92), '/')}'\n")
        f.write(f"file '{os.path.abspath(tail_path).replace(chr(92), '/')}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        out_path,
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    os.remove(concat_list)
    os.remove(tail_path)
    if r.returncode != 0:
        raise RuntimeError(f"Error armando clip de pausa extendido:\n{r.stderr.decode('utf-8')}")


def _make_freeze_clip(source_clip: str, hold_sec: float, out_path: str, fps: int = 30) -> None:
    """Congela el último frame de source_clip durante hold_sec (fallback para pausas largas)."""
    frame_path = out_path + ".png"
    cmd_frame = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", source_clip, "-vframes", "1", frame_path]
    r = subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error extrayendo último frame de '{source_clip}':\n{r.stderr.decode('utf-8')}")

    cmd_loop = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", frame_path,
        "-t", f"{hold_sec:.3f}", "-r", str(fps),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ]
    r = subprocess.run(cmd_loop, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if os.path.exists(frame_path):
        os.remove(frame_path)
    if r.returncode != 0:
        raise RuntimeError(f"Error generando freeze de pausa:\n{r.stderr.decode('utf-8')}")


# ---------------------------------------------------------------------------
# 5. Orquestador — esto es lo que llama flows/generate_short.py en vez de
#    generate_lipsync_video()
# ---------------------------------------------------------------------------

def generate_mascota_raw_video(
    audio_path: str,
    output_path: str,
    master_video: str,
    library_dir: str,
    manifest_path: str,
    video_format: str = "short",
    usable_range: Tuple[float, Optional[float]] = (0.0, None),
    exclude_ranges: Optional[List[Tuple[float, float]]] = None,
    clip_min_sec: float = 1.0,
    clip_max_sec: float = 2.0,
    fps: int = 30,
) -> None:
    """
    Reemplaza generate_lipsync_video(). Genera SOLO raw_concat.mp4 (silencioso);
    el resto (audio, música, subs, color grade) lo pone assemble_video() como ya
    hace con `differences`.
    """
    if not os.path.exists(manifest_path) or _library_is_stale(manifest_path, master_video):
        manifest = build_library(
            master_video, library_dir, manifest_path,
            video_format=video_format, usable_range=usable_range,
            exclude_ranges=exclude_ranges, clip_min_sec=clip_min_sec,
            clip_max_sec=clip_max_sec, fps=fps,
        )
    else:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    segments = detect_speech_segments(audio_path)
    sequence = match_clips(segments, manifest)
    build_raw_video(sequence, library_dir, manifest, output_path, fps=fps)