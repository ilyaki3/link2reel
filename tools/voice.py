#!/usr/bin/env python3
"""Озвучка по сценам: script.json -> assets/voice.wav + assets/voice_words.json + timeline.json.

Каждая сцена озвучивается отдельно, тишина по краям срезается по таймингам слов,
сцены склеиваются с паузой `gap`. Так темп плотный, а сцена знает свой точный старт.

  python3 voice.py <project_dir> [--provider heygen|edge] [--voice ID] [--speed 1.15] [--only scene_id]

Провайдеры:
  elevenlabs — ElevenLabs API (ключ в $ELEVENLABS_API_KEY), модель из channel.json, тайминги по символам из API.
               Скорость — ускорение atempo после синтеза, тон не меняется (у eleven_v4 нет параметра speed).
  heygen — media-use/audio/scripts/heygen-tts.mjs (нужен `npx hyperframes auth login`), тайминги слов из API.
  edge   — бесплатный Edge TTS, только для черновиков (нужен python с пакетом edge-tts: --python путь).
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
HEYGEN_TTS = os.path.expanduser("~/.claude/skills/media-use/audio/scripts/heygen-tts.mjs")
EDGE_VOICE = {"ru": "ru-RU-DmitryNeural", "en": "en-US-AndrewNeural"}


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def spoken_text(text, pronounce):
    # Длинные ключи первыми, чтобы «Claude Code» заменился раньше «Claude».
    for key in sorted(pronounce, key=len, reverse=True):
        text = re.sub(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", pronounce[key], text)
    return text


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"Команда упала: {' '.join(cmd[:3])}…\n{r.stderr[-1500:]}")
    return r.stdout


def tts_heygen(text, wav, words_path, lang, voice, speed):
    if not os.path.exists(HEYGEN_TTS):
        sys.exit("Нет heygen-tts.mjs: выполните `npx hyperframes skills update`.")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as t:
        t.write(text)
    cmd = ["node", HEYGEN_TTS, t.name, "-o", wav, "--words", words_path, "--lang", lang, "--speed", str(speed)]
    if voice:
        cmd += ["--voice", voice]
    run(cmd)
    os.unlink(t.name)
    return load_json(words_path)


def tts_elevenlabs(text, wav, words_path, lang, voice, speed, vcfg):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("Нет ELEVENLABS_API_KEY в окружении (~/.zshrc).")
    if not voice:
        sys.exit("Не задан voice_id для ElevenLabs (channel.json → voice.voice_id).")
    body = {"text": text, "model_id": vcfg.get("model", "eleven_v4"), "language_code": lang,
            "voice_settings": {"stability": vcfg.get("stability", 0.45), "similarity_boost": vcfg.get("similarity", 0.8)}}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps(body).encode(), method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs {e.code}: {e.read().decode()[:400]}")
    mp3 = wav[:-4] + ".src.mp3"
    open(mp3, "wb").write(base64.b64decode(res["audio_base64"]))
    al = res.get("alignment") or {}
    words, cur, t0, t1 = [], "", None, None
    for ch, s, e in zip(al.get("characters", []), al.get("character_start_times_seconds", []),
                        al.get("character_end_times_seconds", [])):
        if ch.isspace():
            if cur:
                words.append({"text": cur, "start": t0, "end": t1})
            cur, t0 = "", None
            continue
        if t0 is None:
            t0 = s
        cur, t1 = cur + ch, e
    if cur:
        words.append({"text": cur, "start": t0, "end": t1})
    # Ускорение без смены тона через atempo (склейка кусочков записи, на речи звучит естественно;
    # rubberband давал «электронный» призвук на низком голосе). Тайминги делим на ту же скорость.
    af = f"atempo={speed}" if abs(speed - 1) > 1e-3 else "anull"
    run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-af", af, "-ar", "44100", "-ac", "1", wav])
    os.unlink(mp3)
    words = [{"text": w["text"], "start": round(w["start"] / speed, 3), "end": round(w["end"] / speed, 3)} for w in words]
    json.dump(words, open(words_path, "w", encoding="utf-8"), ensure_ascii=False)
    return words


def tts_edge(text, wav, words_path, lang, voice, speed, python):
    code = r'''
import asyncio, json, sys, edge_tts
text, mp3, words_path, voice, rate = sys.argv[1:6]
async def main():
    c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"text": ch["text"], "start": round(s, 3), "end": round(s + ch["duration"] / 1e7, 3)})
    json.dump(words, open(words_path, "w"), ensure_ascii=False)
asyncio.run(main())
'''
    mp3 = wav[:-4] + ".mp3"
    rate = f"{round((speed - 1) * 100):+d}%"
    run([python, "-I", "-c", code, text, mp3, words_path, voice or EDGE_VOICE.get(lang, EDGE_VOICE["en"]), rate])
    run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "44100", "-ac", "1", wav])
    os.unlink(mp3)
    return load_json(words_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--provider", help="elevenlabs | heygen | edge (по умолчанию из channel.json)")
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--gap", type=float)
    ap.add_argument("--only", help="переозвучить одну сцену, остальные взять из кэша")
    ap.add_argument("--python", default=sys.executable, help="python с edge-tts для --provider edge")
    a = ap.parse_args()

    channel = load_json(os.path.join(SKILL, "channel.json"), {})
    vcfg = channel.get("voice", {})
    proj = os.path.abspath(a.project)
    script = load_json(os.path.join(proj, "script.json"))
    if not script:
        sys.exit("Нет script.json в проекте.")
    lang = script.get("language", channel.get("language", "ru"))
    provider = a.provider or vcfg.get("provider", "heygen")
    same = provider == vcfg.get("provider", "heygen")  # id голоса из channel.json — только для его провайдера
    voice = a.voice or (script.get("voice_id") if same else None) or (vcfg.get("voice_id") if same else None)
    speed = a.speed or script.get("speed") or vcfg.get("speed", 1.15)
    gap = a.gap if a.gap is not None else vcfg.get("gap", 0.22)
    pronounce = {**channel.get("pronounce", {}), **script.get("pronounce", {})}

    vdir = os.path.join(proj, "assets", "voice")
    os.makedirs(vdir, exist_ok=True)
    pieces, all_words, scenes, cursor = [], [], [], 0.12
    for sc in script["scenes"]:
        sid, say = sc["id"], sc["say"].strip()
        wav = os.path.join(vdir, f"{sid}.raw.wav")
        wpath = os.path.join(vdir, f"{sid}.words.json")
        cached = a.only and a.only != sid and os.path.exists(wav) and os.path.exists(wpath)
        if cached:
            words = load_json(wpath)
        else:
            text = spoken_text(say, pronounce)
            print(f"[{sid}] {text}", file=sys.stderr)
            if provider == "elevenlabs":
                words = tts_elevenlabs(text, wav, wpath, lang, voice, speed, vcfg)
            elif provider == "heygen":
                words = tts_heygen(text, wav, wpath, lang, voice, speed)
            elif provider == "edge":
                words = tts_edge(text, wav, wpath, lang, voice, speed, a.python)
            else:
                sys.exit(f"Неизвестный провайдер {provider}")
        words = [w for w in words if re.search(r"\w", w.get("text", "")) and not w["text"].startswith("<")]
        if not words:
            sys.exit(f"[{sid}] провайдер не вернул тайминги слов")
        t0 = max(0.0, words[0]["start"] - 0.04)
        t1 = words[-1]["end"] + 0.1
        cut = os.path.join(vdir, f"{sid}.wav")
        run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
             "-ar", "44100", "-ac", "1", "-af", "afade=t=in:d=0.02,areverse,afade=t=in:d=0.04,areverse", cut])
        dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", cut]).strip())
        for w in words:
            all_words.append({"scene": sid, "text": w["text"],
                              "start": round(cursor + w["start"] - t0, 3), "end": round(cursor + w["end"] - t0, 3)})
        scenes.append({"id": sid, "voice_start": round(cursor, 3), "voice_end": round(cursor + dur, 3)})
        pieces.append((cut, dur))
        cursor += dur + gap

    # Склейка: тишина 0.12 с в начале, между сценами gap.
    lst = os.path.join(vdir, "concat.txt")
    sil = os.path.join(vdir, "gap.wav")
    lead = os.path.join(vdir, "lead.wav")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(gap), sil])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.12", lead])
    with open(lst, "w") as f:
        f.write(f"file '{lead}'\n")
        for i, (p, _) in enumerate(pieces):
            f.write(f"file '{p}'\n")
            if i < len(pieces) - 1:
                f.write(f"file '{sil}'\n")
    out = os.path.join(proj, "assets", "voice.wav")
    # Голоса HeyGen отличаются по громкости на 3–5 дБ: выравниваем к −16 LUFS, пик −1.5 dBTP.
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "pcm_s16le", out])

    # Слоты сцен: сцена начинается чуть раньше своего голоса и длится до начала следующей.
    hold = script.get("end_hold", 1.4)
    for i, s in enumerate(scenes):
        s["start"] = 0.0 if i == 0 else round(s["voice_start"] - gap / 2, 3)
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else round(s["voice_end"] + hold, 3)
        s["duration"] = round(s["end"] - s["start"], 3)
    total = scenes[-1]["end"]
    json.dump(all_words, open(os.path.join(proj, "assets", "voice_words.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"duration": total, "scenes": scenes}, open(os.path.join(proj, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"duration": total, "scenes": [(s["id"], s["start"], s["duration"]) for s in scenes]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
