#!/usr/bin/env python3
"""Режим «как в этом ролике»: разбирает эталонный вирусный ролик и пишет research/reference/REFERENCE.md.

  python3 reference.py <project_dir> <video.mp4 | URL>

URL скачивается через yt-dlp, если он установлен (Instagram часто требует вход — тогда попроси
у пользователя сам файл). Что измеряется, без нейросетей и без сети:
  - длина, формат кадра;
  - склейки (ffmpeg scene detection): число, средняя длина плана, склейки в первые 3 с, темп по третям;
  - речь: доля звучания и паузы (silencedetect), громкость;
  - контакт-лист: кадр 0 (обложка/хук) и кадры сразу после склеек — по нему смотришь глазами,
    где стоит текст, какой стиль субтитров, что в хуке.
"""
import json, math, os, re, shutil, subprocess, sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    proj, src = os.path.abspath(sys.argv[1]), sys.argv[2]
    out = os.path.join(proj, "research", "reference")
    os.makedirs(out, exist_ok=True)

    video = src
    if re.match(r"https?://", src):
        if not shutil.which("yt-dlp"):
            sys.exit("Нет yt-dlp. Попроси пользователя прислать файл ролика или разрешить `brew install yt-dlp`.")
        r = run(["yt-dlp", "-q", "-f", "mp4/best", "-o", os.path.join(out, "reference.%(ext)s"), src])
        files = [f for f in os.listdir(out) if f.startswith("reference.")]
        if r.returncode != 0 or not files:
            sys.exit("yt-dlp не скачал ролик (часто — нужен вход в Instagram). Попроси файл.\n" + r.stderr[-600:])
        video = os.path.join(out, files[0])

    probe = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", video]).stdout)
    dur = float(probe["format"]["duration"])
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    w, h = int(vs["width"]), int(vs["height"])

    # Склейки
    r = run(["ffmpeg", "-hide_banner", "-i", video, "-vf", "select='gt(scene,0.25)',showinfo", "-an", "-f", "null", "-"])
    cuts = [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    cuts = [c for i, c in enumerate(cuts) if i == 0 or c - cuts[i - 1] > 0.25]
    bounds = [0.0] + cuts + [dur]
    shots = [round(b - a, 2) for a, b in zip(bounds, bounds[1:])]
    thirds = [sum(1 for c in cuts if dur * k / 3 <= c < dur * (k + 1) / 3) for k in range(3)]

    # Речь и паузы
    r = run(["ffmpeg", "-hide_banner", "-i", video, "-af", "silencedetect=noise=-32dB:d=0.25", "-vn", "-f", "null", "-"])
    sil = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", r.stderr)]
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-af", "ebur128", "-f", "null", "-"]) if has_audio else None
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr) if r else []

    # Контакт-лист: кадр 0.1 с + первые 11 планов (кадр через 0.15 с после склейки)
    times = [0.1] + [min(dur - 0.05, c + 0.15) for c in cuts][:11]
    if len(cuts) < 3:  # плавные переходы, а не склейки — берём кадры равномерно
        times = [0.1] + [round(dur * k / 12, 2) for k in range(1, 12)]
    frames = []
    for i, t in enumerate(times):
        f = os.path.join(out, f"f{i:02d}.jpg")
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
             "-vf", f"scale=270:-2,drawtext=text='{t:.1f}s':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6", f])
        if os.path.exists(f):
            frames.append(f)
    sheet = os.path.join(out, "sheet.jpg")
    if frames:
        cols = 4
        rows = math.ceil(len(frames) / cols)
        inputs = sum((["-i", f] for f in frames), [])
        layout = "|".join(("0" if i % cols == 0 else "+".join(["w0"] * (i % cols))) + "_" +
                          ("0" if i // cols == 0 else "+".join(["h0"] * (i // cols))) for i in range(len(frames)))
        r = run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
                 f"xstack=inputs={len(frames)}:layout={layout}:fill=black" if len(frames) > 1 else "null", sheet])
        if len(frames) == 1:
            shutil.copy(frames[0], sheet)
        for f in frames:
            os.remove(f)

    avg = round(sum(shots) / len(shots), 2) if shots else dur
    md = f"""# Эталон: разбор ритма

Источник: {src}
Длина: **{dur:.1f} с** · кадр {w}×{h}
Склеек: **{len(cuts)}** · средний план **{avg} с** · склеек в первые 3 с: **{sum(1 for c in cuts if c < 3)}**
Склейки по третям ролика: {thirds[0]} / {thirds[1]} / {thirds[2]}
Планы, с: {', '.join(str(s) for s in shots[:30])}{' …' if len(shots) > 30 else ''}
Паузы ≥ 0,25 с: {len(sil)} шт., всего {sum(sil):.1f} с ({(sum(sil) / dur * 100 if dur else 0):.0f}% ролика) · громкость {lufs[-1] + ' LUFS' if lufs else 'нет звука'}

Контакт-лист: `research/reference/sheet.jpg` — кадр 0 и кадры после склеек.

## Что перенести в наш ролик (заполняешь ты, глядя на лист)
- Длина: целиться в ±15% от эталона, но в рамках 30–40 с.
- Темп: новый визуальный бит каждые ~{avg} с (у нас бит = смена внутри сцены или новая сцена).
- Кадр 0: что в нём (лицо, результат, крупная надпись?), где текст, сколько слов.
- Субтитры: позиция, слов в группе, регистр, подсветка слова, обводка/плашка.
- Чего нет у нас и стоит взять: …
"""
    open(os.path.join(out, "REFERENCE.md"), "w", encoding="utf-8").write(md)
    print(md)


if __name__ == "__main__":
    main()
