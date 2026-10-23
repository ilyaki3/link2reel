#!/usr/bin/env bash
# Новый проект ролика: <videos_root>/<YYYY-MM-DD>-<slug>/ с HyperFrames, шаблоном канала и шрифтами.
#   bash new_project.sh <slug>
# Печатает путь к проекту последней строкой.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:?usage: new_project.sh <slug>}"
HF="hyperframes@0.8.188"
ROOT="${SHORT_VIDEOS_ROOT:-$(python3 -c "import json,os;print(os.path.expanduser(json.load(open('$SKILL/channel.json'))['videos_root']))")}"
DIR="$ROOT/$(date +%Y-%m-%d)-$SLUG"
mkdir -p "$ROOT"
if [ -e "$DIR" ]; then echo "Уже есть: $DIR" >&2; echo "$DIR"; exit 0; fi
(cd "$ROOT" && npx -y "$HF" init "$(basename "$DIR")" --example blank --resolution portrait --non-interactive >/dev/null)
cp "$SKILL/templates/index.html" "$DIR/index.html"
mkdir -p "$DIR/compositions" "$DIR/assets/sfx" "$DIR/deliver" "$DIR/research"
cp ~/.claude/skills/media-use/audio/assets/sfx/{whoosh,whoosh-short,pop,click-soft,sparkle,typing}.mp3 "$DIR/assets/sfx/"
python3 "$SKILL/tools/fonts.py" "$DIR" "Montserrat:800" "Inter:400,700" "JetBrains Mono:400,500,700" >/dev/null
echo "$DIR"
