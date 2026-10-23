# /short — вертикальные ролики о проектах для Claude Code

Даёшь ссылку на GitHub-репозиторий, сайт или название инструмента — получаешь готовый ролик 9:16 на 30–40 секунд для Reels, YouTube Shorts и TikTok: с озвучкой, субтитрами, обложкой и текстами постов.

```
/short https://github.com/owner/repo
```

## Что делает

1. **Ресерч** — README, GitHub API, сайт, обзоры, Hacker News, Threads. Каждый факт со ссылкой.
2. **Стиль под проект** — цвета, шрифт (с кириллицей), логотип и настоящие скриншоты проекта.
3. **Сценарий** — 3 хука «через боль» с оценкой из 10, надпись для обложки, повторный крючок, финал-петля, проверки качества, вычитка от «ИИ-шности». **Стоп: ждёт твоего «ок».**
4. **Черновое видео** на бесплатном голосе — смотришь картинку, не тратя кредиты.
5. **Озвучка ElevenLabs** — анимации, субтитры и звуки привязаны к словам и подстраиваются сами.
6. **Пакет** — `video.mp4`, `cover.png`, `captions.srt`, `POSTS.md` (заголовок и описание YouTube, подписи Reels и TikTok).

Флаги: `--auto` — без остановки на сценарии; `--like <ролик>` — подстроить ритм под вирусный ролик-образец.

Видео собирается на [HyperFrames](https://github.com/heygen-com/hyperframes) (HTML → MP4).

## Установка

```bash
npx skills add <owner>/<repo>          # или: git clone … ~/.claude/skills/short
npx hyperframes skills update          # навыки HyperFrames (+ media-use)
npx skills add ilyautov/humanizer-ru   # вычитка русского текста
python3 -m pip install --user pymorphy3==2.0.6 razdel==0.5.0   # сканер humanizer-ru
```

Требования: Node.js 22+, FFmpeg (с rubberband не обязательно), Python 3.10+, Claude Code.

### Голос (ElevenLabs)

1. Создай аккаунт на elevenlabs.io и API-ключ с правами **Text to Speech**, **Voices (read/write)**, **Models (read)**, **User (read)**.
2. Сохрани ключ в окружение (не вставляй в чат):
   ```bash
   read -s "K?ElevenLabs API key: " && echo "export ELEVENLABS_API_KEY=\"$K\"" >> ~/.zshrc && unset K
   ```
3. Впиши `voice_id` в `channel.json → voice`. На бесплатном тарифе через API работают только встроенные голоса и созданные тобой (Voices → Voice Design); голоса из библиотеки — только на платном.

Бесплатный черновой голос для предпросмотра — Edge TTS: `python3 -m venv ~/.short-venv && ~/.short-venv/bin/pip install edge-tts`, затем `voice.py <проект> --provider edge --python ~/.short-venv/bin/python`.

### Одно правило для humanizer-ru

Тире в тексте озвучки — паузы голоса. Добавь в `~/.claude/skills/humanizer-ru/edit-log.md`:

```
## тире в сценариях для озвучки
Правило: в тексте озвучки (поля `say` в script.json и колонка «Текст озвучки» в SCRIPT.md навыка /short) длинное тире «—» не снимать. В подписях к постам — снимать как обычно.
Область: сценарии для озвучки навыка /short
```

## Настройка канала — `channel.json`

- `videos_root` — куда складывать проекты (по умолчанию `~/Movies/shorts`);
- `voice` — провайдер, `voice_id`, скорость (`speed` 1.2 через atempo), пауза между сценами;
- `pronounce` — словарь произношения для англоязычных названий;
- `handle` — ник канала для финальной карточки.

## Состав

- `SKILL.md` — процесс по шагам; `references/` — ресерч, стиль, сценарий, сборка;
- `tools/` — `new_project.sh`, `fonts.py` (шрифты с кириллицей), `voice.py` (озвучка по сценам), `captions.py` (субтитры + .srt), `scenes.py` (раскладка сцен по словам), `reference.py` (разбор ролика-образца);
- `templates/` — каркас композиции и субтитров.

## Лицензия

MIT — см. `LICENSE`. Правила хуков и сценария адаптированы из [Melvynx/video-agent-skills](https://github.com/Melvynx/video-agent-skills) (MIT) — см. `NOTICE.md`.
