#!/usr/bin/env python3
"""Раскладывает сцены по таймлайну озвучки.

Читает timeline.json и assets/words.json, затем:
  - вписывает в index.html хосты сцен (<!--SCENES-->), длительность ролика и свуши на склейках (<!--SFX-->);
  - создаёт compositions/<id>.html-заготовки для сцен, у которых файла ещё нет.
    В заготовке — T0, длительность и таблица слов сцены с локальным временем: анимации вешаются на слова.

  python3 scenes.py <project_dir>

Повторный запуск после переозвучки обновляет время в index.html, `T0`/`DUR` и блок слов `W`
в существующих сценах. Анимации, привязанные через w(i)/we(i), сдвигаются вместе со словами сами.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SFX_DUR = {"pop": 0.72, "click-soft": 0.37, "sparkle": 1.8, "typing": 1.5, "whoosh": 0.57, "whoosh-short": 0.57}

STUB = """<template>
  <style>
    #root {{ position: absolute; inset: 0; }}
    #{id}-stage {{ position: absolute; inset: 0; }}
  </style>
  <div id="root" data-composition-id="{id}" data-width="1080" data-height="1920">
    <div id="{id}-stage">
      <div id="{id}-kicker" class="kicker" style="position: absolute; left: 90px; top: 250px">✱ {id}</div>
    </div>
  </div>
  <script>
    (function () {{
      const T0 = {t0}; // начало сцены в ролике, с (справочно)
      const DUR = {dur}; // длина слота, с
      /*WORDS*/
{words}
      /*/WORDS*/
      // w(i) — локальное время начала i-го слова сцены, we(i) — его конца. Привязывай анимации к словам,
      // а не к секундам: после переозвучки scenes.py перепишет блок WORDS, и всё сдвинется само.
      const w = (i) => W[Math.max(0, Math.min(i, W.length - 1))].s;
      const we = (i) => W[Math.max(0, Math.min(i, W.length - 1))].e;
      const tl = gsap.timeline({{ paused: true }});
      {enter}
      // TODO: анимации на слова: tl.fromTo(sel, {{...}}, {{...}}, w(<номер слова>));
      tl.to("#{id}-stage", {{ opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power3.in" }}, DUR - 0.2);
      window.__timelines["{id}"] = tl;
    }})();
  </script>
</template>
"""


def main():
    proj = os.path.abspath(sys.argv[1])
    tlj = json.load(open(os.path.join(proj, "timeline.json"), encoding="utf-8"))
    words = json.load(open(os.path.join(proj, "assets", "words.json"), encoding="utf-8"))
    script = json.load(open(os.path.join(proj, "script.json"), encoding="utf-8"))
    sfx_by_scene = {sc["id"]: sc.get("sfx", []) for sc in script["scenes"]}
    dur = round(tlj["duration"], 3)
    hosts, sfx = [], []
    whooshes = ["whoosh-short", "whoosh"]
    for i, s in enumerate(tlj["scenes"]):
        sid = s["id"]
        hosts.append(
            f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html"\n'
            f'        data-start="{s["start"]}" data-duration="{s["duration"]}" data-track-index="1" data-track-kind="graphics"\n'
            f'        data-width="1080" data-height="1920"></div>')
        if i > 0:
            sfx.append(f'      <audio id="sfx-cut-{i}" class="clip" src="assets/sfx/{whooshes[i % 2]}.mp3" '
                       f'data-start="{max(0, round(s["start"] - 0.12, 3))}" data-duration="0.57" data-track-index="4" data-volume="0.28"></audio>')
        sw = [w for w in words if w["scene"] == sid]
        # Звуки на слова: script.json → scenes[].sfx = [{"file": "pop", "word": 3, "vol": 0.35, "offset": 0}]
        for k, fx in enumerate(sfx_by_scene.get(sid, [])):
            if not sw:
                break
            wi = max(0, min(fx.get("word", 0), len(sw) - 1))
            t = max(0, round(sw[wi]["start"] + fx.get("offset", 0) - 0.02, 3))
            fd = SFX_DUR.get(fx["file"], 0.6)
            sfx.append(f'      <audio id="sfx-{sid}-{k}" class="clip" src="assets/sfx/{fx["file"]}.mp3" data-start="{t}" '
                       f'data-duration="{fd}" data-track-index="{5 + k % 2}" data-volume="{fx.get("vol", 0.35)}"></audio>')
        path = os.path.join(proj, "compositions", f"{sid}.html")
        wl = ("      const W = [\n" + "\n".join(
            f'        {{ s: {round(w["start"] - s["start"], 3)}, e: {round(w["end"] - s["start"], 3)} }}, // {i} {w["text"]}'
            for i, w in enumerate(sw)) + "\n      ];")
        if not os.path.exists(path):
            enter = ("// Первая сцена: кадр 0 — обложка, хук уже на экране, без входа из пустоты."
                     if i == 0 else
                     f'tl.fromTo("#{sid}-stage", {{ opacity: 0, filter: "blur(10px)" }}, '
                     f'{{ opacity: 1, filter: "blur(0px)", duration: 0.25, ease: "power3.out" }}, 0);')
            open(path, "w", encoding="utf-8").write(STUB.format(id=sid, t0=s["start"], dur=s["duration"], words=wl, enter=enter))
        else:
            src = open(path, encoding="utf-8").read()
            src = re.sub(r"const T0 = [\d.]+;", f"const T0 = {s['start']};", src, count=1)
            src = re.sub(r"const DUR = [\d.]+;", f"const DUR = {s['duration']};", src, count=1)
            src = re.sub(r"/\*WORDS\*/.*?/\*/WORDS\*/", lambda m: "/*WORDS*/\n" + wl + "\n      /*/WORDS*/", src, count=1, flags=re.S)
            open(path, "w", encoding="utf-8").write(src)

    index = os.path.join(proj, "index.html")
    html = open(index, encoding="utf-8").read()
    html = re.sub(r'(id="root"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{dur}\g<2>", html, count=1, flags=re.S)
    html = re.sub(r'(id="captions"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{dur}\g<2>", html, count=1, flags=re.S)
    html = html.replace("__DURATION__", str(dur))
    html = re.sub(r"<!--SCENES-->.*?<!--/SCENES-->|<!--SCENES-->",
                  lambda m: "<!--SCENES-->\n" + "\n".join(hosts) + "\n      <!--/SCENES-->", html, count=1, flags=re.S)
    html = re.sub(r"<!--SFX-->.*?<!--/SFX-->|<!--SFX-->",
                  lambda m: "<!--SFX-->\n" + "\n".join(sfx) + "\n      <!--/SFX-->", html, count=1, flags=re.S)
    open(index, "w", encoding="utf-8").write(html)
    print(f"длительность {dur} с, сцен {len(hosts)}")


if __name__ == "__main__":
    main()
