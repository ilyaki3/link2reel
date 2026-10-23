#!/usr/bin/env python3
"""Субтитры: сводит экранный текст сцен (script.json) с таймингами озвучки (assets/voice_words.json).

Пишет compositions/captions.html, assets/words.json и deliver/captions.srt.

  python3 captions.py <project_dir> [--max-words 3]

Экранный текст может отличаться от озвученного (HyperFrames vs «Хайперфреймс», 450 vs
«четыреста пятьдесят»): слова сопоставляются по совпадениям, а расхождения делят время
своего промежутка пропорционально длине слов.
"""
import argparse, difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PUNCT_END = re.compile(r"[.,:;!?…]+$")
DASHES = {"—", "–", "-"}
# Служебные слова не оставляем висеть в конце группы субтитров.
WEAK = {"и", "а", "но", "в", "во", "на", "с", "со", "к", "ко", "от", "до", "за", "по", "из", "о", "об", "у",
        "для", "около", "не", "ни", "же", "что", "как", "это", "the", "a", "an", "of", "to", "and", "in", "on"}


def norm(s):
    return re.sub(r"[^\w]", "", s.lower().replace("ё", "е"))


def spoken_text(text, pronounce):
    for key in sorted(pronounce, key=len, reverse=True):
        text = re.sub(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", pronounce[key], text)
    return text


def display_tokens(say, pronounce):
    # Многословные ключи словаря («Claude Code») склеиваем неразрывным пробелом в один токен.
    for key in sorted(pronounce, key=len, reverse=True):
        if " " in key:
            say = re.sub(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", key.replace(" ", " "), say)
    return [t for t in re.split(r"[ \t\n]+", say.strip()) if t and t not in DASHES]


def align(tokens, spoken_words, pronounce):
    """tokens: экранные слова сцены; spoken_words: [{text,start,end}] из TTS."""
    expected, owner = [], []
    for i, tok in enumerate(tokens):
        sp = spoken_text(tok.replace(" ", " "), pronounce)
        for part in sp.split():
            if norm(part):
                expected.append(norm(part))
                owner.append(i)
    actual = [norm(w["text"]) for w in spoken_words]
    times = [None] * len(tokens)

    def put(i, s, e):
        if times[i] is None:
            times[i] = [s, e]
        else:
            times[i] = [min(times[i][0], s), max(times[i][1], e)]

    sm = difflib.SequenceMatcher(a=expected, b=actual, autojunk=False)
    prev_a = prev_b = 0
    blocks = sm.get_matching_blocks()
    for blk in blocks:
        # Промежуток без совпадений: expected[prev_a:blk.a] ↔ actual[prev_b:blk.b]
        gap_tok = sorted(set(owner[prev_a:blk.a]) - {i for i in range(len(tokens)) if times[i]})
        if gap_tok:
            if blk.b > prev_b:
                s, e = spoken_words[prev_b]["start"], spoken_words[blk.b - 1]["end"]
            else:  # нечего прочитать — узкое окно у соседнего слова
                s = spoken_words[prev_b - 1]["end"] if prev_b > 0 else spoken_words[0]["start"]
                e = s + 0.15
            lens = [max(1, len(tokens[i])) for i in gap_tok]
            acc, total = s, sum(lens)
            for i, ln in zip(gap_tok, lens):
                step = (e - s) * ln / total
                put(i, acc, acc + step)
                acc += step
        for k in range(blk.size):
            w = spoken_words[blk.b + k]
            put(owner[blk.a + k], w["start"], w["end"])
        prev_a, prev_b = blk.a + blk.size, blk.b + blk.size
    # Подстраховка: токены без времени берут время соседа.
    for i in range(len(tokens)):
        if times[i] is None:
            j = next((k for k in range(i - 1, -1, -1) if times[k]), None)
            base = times[j][1] if j is not None else spoken_words[0]["start"]
            times[i] = [base, base + 0.15]
    return times


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--max-words", type=int, default=3)
    ap.add_argument("--pause", type=float, default=0.15)
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    channel = json.load(open(os.path.join(SKILL, "channel.json"), encoding="utf-8"))
    script = json.load(open(os.path.join(proj, "script.json"), encoding="utf-8"))
    vw = json.load(open(os.path.join(proj, "assets", "voice_words.json"), encoding="utf-8"))
    pronounce = {**channel.get("pronounce", {}), **script.get("pronounce", {})}

    words = []
    for sc in script["scenes"]:
        toks = display_tokens(sc["say"], pronounce)
        sw = [w for w in vw if w["scene"] == sc["id"]]
        for tok, (s, e) in zip(toks, align(toks, sw, pronounce)):
            words.append({"id": f"w{len(words)}", "scene": sc["id"], "text": tok.replace(" ", " "),
                          "start": round(s, 3), "end": round(e, 3)})

    groups, cur = [], []
    for k, w in enumerate(words):
        cur.append(k)
        nxt = words[k + 1] if k + 1 < len(words) else None
        ends = bool(PUNCT_END.search(w["text"]))
        short_tail = not ends and w["text"].lower() in WEAK
        if (nxt is None or ends or nxt["scene"] != w["scene"] or nxt["start"] - w["end"] >= (0.4 if short_tail else a.pause)
                or (len(cur) >= a.max_words and not short_tail) or len(cur) > a.max_words):
            groups.append(cur)
            cur = []

    # Висящие служебные слова («и около») переносим в начало следующей группы той же сцены.
    for gi in range(len(groups) - 1):
        g, nx = groups[gi], groups[gi + 1]
        while (len(g) > 1 and words[g[-1]]["text"].lower() in WEAK
               and words[g[-1]]["scene"] == words[nx[0]]["scene"] and len(nx) <= a.max_words):
            nx.insert(0, g.pop())
    out = []
    for gi, g in enumerate(groups):
        start = max(0.1, words[g[0]]["start"] - 0.05)
        limit = words[groups[gi + 1][0]]["start"] - 0.05 if gi + 1 < len(groups) else words[-1]["end"] + 0.6
        out.append({"start": round(start, 3), "end": round(min(words[g[-1]]["end"] + 0.35, limit), 3),
                    "words": [{"id": words[k]["id"], "text": words[k]["text"], "start": words[k]["start"],
                               "end": words[k]["end"]} for k in g]})

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;")

    markup = []
    for gi, g in enumerate(out):
        spans = "".join(
            f'<span class="cap-w" id="cap-w{w["id"][1:]}"><span class="cap-bg" id="cap-bg{w["id"][1:]}"></span>'
            f'<span class="cap-t">{esc(PUNCT_END.sub("", w["text"]))}</span></span>' for w in g["words"])
        markup.append(f'    <div class="cap-g" id="cap-g{gi}">{spans}</div>')
    tpl = open(os.path.join(SKILL, "templates", "captions.template.html"), encoding="utf-8").read()
    html = tpl.replace("<!--GROUPS-->", "\n".join(markup)).replace("/*DATA*/", json.dumps(out, ensure_ascii=False))
    os.makedirs(os.path.join(proj, "compositions"), exist_ok=True)
    open(os.path.join(proj, "compositions", "captions.html"), "w", encoding="utf-8").write(html)
    json.dump(words, open(os.path.join(proj, "assets", "words.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # SRT для YouTube: строки по фразам (до 7 слов или до знака препинания).
    os.makedirs(os.path.join(proj, "deliver"), exist_ok=True)
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if PUNCT_END.search(w["text"]) or len(cur) >= 7:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    with open(os.path.join(proj, "deliver", "captions.srt"), "w", encoding="utf-8") as f:
        for i, ln in enumerate(lines, 1):
            end = ln[-1]["end"] + 0.2
            if i < len(lines):
                end = min(end, lines[i][0]["start"] - 0.02)
            f.write(f"{i}\n{srt_time(ln[0]['start'])} --> {srt_time(end)}\n{' '.join(x['text'] for x in ln)}\n\n")

    for g in out:
        print(f"{g['start']:6.2f}–{g['end']:6.2f}  " + " ".join(w["text"] for w in g["words"]))
    print(f"{len(words)} слов, {len(out)} групп", file=sys.stderr)


if __name__ == "__main__":
    main()
