#!/usr/bin/env python3
"""Шрифты с кириллицей: качает латиницу + кириллицу из Fontsource в assets/fonts
и вписывает @font-face в index.html между /*FONTS*/ и /*/FONTS*/.

  python3 fonts.py <project_dir> "Montserrat:800" "Inter:400,700" "JetBrains Mono:400,700"

Семейство в CSS получает суффикс " RU" (например "Montserrat RU"), чтобы не путаться
со встроенными шрифтами HyperFrames, где кириллицы нет.
Если у шрифта нет кириллицы, скрипт скажет об этом — выберите другой.
"""
import os, re, sys, time, urllib.request

RANGES = {
    "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, "
             "U+2000-206F, U+20AC, U+2122, U+2190-21FF, U+2212, U+2215, U+2605, U+FEFF, U+FFFD",
    "cyrillic": "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
}


def fetch(url, dest):
    for attempt in range(3):  # CDN иногда отвечает ошибкой — пробуем ещё раз
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except Exception:
            time.sleep(1 + attempt)
    return False


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    proj = os.path.abspath(sys.argv[1])
    fdir = os.path.join(proj, "assets", "fonts")
    os.makedirs(fdir, exist_ok=True)
    css, missing = [], []
    for spec in sys.argv[2:]:
        family, _, weights = spec.partition(":")
        slug = re.sub(r"\s+", "-", family.strip().lower())
        for w in (weights or "400").split(","):
            for sub, rng in RANGES.items():
                name = f"{slug}-{sub}-{w}.woff2"
                url = f"https://cdn.jsdelivr.net/fontsource/fonts/{slug}@latest/{sub}-{w}-normal.woff2"
                if not os.path.exists(os.path.join(fdir, name)) and not fetch(url, os.path.join(fdir, name)):
                    missing.append(f"{family} {w} ({sub})")
                    continue
                css.append(f'      @font-face {{ font-family: "{family} RU"; font-weight: {w}; font-style: normal; '
                           f'font-display: block; src: url("assets/fonts/{name}") format("woff2"); unicode-range: {rng}; }}')
    index = os.path.join(proj, "index.html")
    html = open(index, encoding="utf-8").read()
    block = "/*FONTS*/\n" + "\n".join(css) + "\n      /*/FONTS*/"
    if "/*FONTS*/" not in html:
        sys.exit("В index.html нет маркера /*FONTS*/")
    html = re.sub(r"/\*FONTS\*/.*?/\*/FONTS\*/", lambda m: block, html, flags=re.S)
    open(index, "w", encoding="utf-8").write(html)
    print(f"@font-face: {len(css)}")
    if missing:
        print("НЕ НАЙДЕНО (нет такого начертания или кириллицы): " + "; ".join(missing), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
