# Стиль под проект

Два слоя:
- **Канал (неизменно):** субтитры по 2–3 слова с подсветкой слова (`compositions/captions.html`), кикер `.kicker` (моно, капс, акцент, «✱»), safe-зоны 9:16, финальная сцена «ссылка в описании + сохрани», плотный ритм. Ник канала — из `channel.json → handle`, если задан.
- **Проект (каждый раз свой):** цвета, тема (светлая/тёмная), шрифты, логотип, реальные скриншоты и демо, характер движения.

## Откуда брать

1. **Сайт:** `npx hyperframes capture <url> --json -o research/capture` → `screenshots/` (full-page, scroll-*), извлечённые цвета/шрифты, ассеты (логотипы, svg). Правила чтения токенов — `/hyperframes` → `references/film.md` («Brand tokens»): акцент — цвет, повторяющийся в большинстве ролей; ссылочный синий и статусные цвета не акцент.
2. **GitHub без сайта:** логотип из README (`<img>` в начале), аватар организации `https://github.com/<owner>.png`, OG-картинка `https://opengraph.githubassets.com/1/<owner>/<repo>`, GIF/скриншоты из README. Палитру — по логотипу: `python3 -c` с Pillow не нужен, достаточно `ffmpeg -i logo.png -vf "scale=64:64,palettegen=max_colors=6" pal.png` и посмотреть.
3. **Ничего нет:** нейтральная тёмная тема шаблона, акцент — по смыслу категории (dev-tool — электрический синий/лайм, AI — фиолетовый/коралл, финансы — зелёный).

## STYLE.md (в проекте)

```
Тема: dark | light
--ground / --panel / --panel-2 / --line / --ink / --muted / --accent / --on-accent: #...
Шрифты: display "<Family>" 800 · body "<Family>" 400/700 · mono "<Family>" 400/700
Логотип: assets/logo.(svg|png) · Скриншоты: assets/shots/*.png · Демо: assets/demo.mp4
Характер движения: строгий (expo.out, без отскоков) | игривый (back.out) | технический (steps, печать)
```

Затем:
- Пропиши цвета в `:root` `index.html`. Для светлой темы: `--cap-shadow: none` и проверь, что субтитры читаются (контраст ≥ 4.5).
- Шрифты: `python3 <навык>/tools/fonts.py <проект> "<Display>:800" "<Body>:400,700" "<Mono>:400,700"` и поменяй `--font-*` на `"<Family> RU"`. Шрифт проекта без кириллицы → ближайший с кириллицей: гротеск — Inter, Manrope, Onest, Golos Text; геометрический — Montserrat, Unbounded, Rubik; узкий — Oswald, Roboto Condensed; антиква — Playfair Display, Lora, PT Serif; моно — JetBrains Mono, IBM Plex Mono, Fira Code. Встроенные шрифты HyperFrames **без кириллицы** — не использовать их имена для русского текста.
- Реальный продукт: минимум две сцены со скриншотом/демо проекта. Скриншот в рамке устройства или окна, с наездом на важную часть (`scale`/`x`/`y` обёртки), а не мелко на весь экран.
