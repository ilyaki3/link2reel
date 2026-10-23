#!/usr/bin/env bash
# Проверка окружения навыка /short. Ничего не устанавливает и не тратит символы ElevenLabs.
#   bash tools/doctor.sh
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
ok=0; bad=0
pass() { printf "  \033[32m✓\033[0m %s\n" "$1"; ok=$((ok+1)); }
fail() { printf "  \033[31m✗\033[0m %s\n    → %s\n" "$1" "$2"; bad=$((bad+1)); }
warn() { printf "  \033[33m!\033[0m %s\n    → %s\n" "$1" "$2"; }

find_skill() {  # глобально или в текущем проекте
  for d in "$HOME/.claude/skills/$1" "./.claude/skills/$1" "$HOME/.agents/skills/$1"; do
    [ -f "$d/SKILL.md" ] && { echo "$d"; return 0; }
  done
  return 1
}

echo "Программы"
if command -v node >/dev/null; then
  v=$(node -p 'process.versions.node.split(".")[0]')
  [ "$v" -ge 22 ] && pass "Node.js $(node -v)" || fail "Node.js $(node -v) — нужен 22+" "brew install node"
else fail "Node.js не найден" "brew install node"; fi
command -v ffmpeg >/dev/null && pass "FFmpeg $(ffmpeg -version | head -1 | awk '{print $3}')" || fail "FFmpeg не найден" "brew install ffmpeg"
if command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
  pass "Python $(python3 -V | awk '{print $2}')"
else fail "Python 3.10+ не найден" "brew install python"; fi
command -v gh >/dev/null && pass "GitHub CLI (для ресерча репозиториев)" || warn "GitHub CLI не найден" "brew install gh && gh auth login"
command -v yt-dlp >/dev/null && pass "yt-dlp (режим --like по ссылке)" || warn "yt-dlp не найден — для --like присылайте файл ролика" "brew install yt-dlp"

echo "Навыки"
find_skill hyperframes >/dev/null && pass "hyperframes" || fail "hyperframes не установлен" "npx hyperframes skills update"
MU=$(find_skill media-use) && pass "media-use" || warn "media-use не найден (нужен только для --provider heygen)" "npx hyperframes skills update"
HR=$(find_skill humanizer-ru)
if [ -n "$HR" ]; then
  pass "humanizer-ru"
  grep -q "тире в сценариях для озвучки" "$HR/edit-log.md" 2>/dev/null && pass "правило про тире в edit-log humanizer-ru" \
    || fail "нет правила про тире в humanizer-ru (иначе он вычистит паузы из озвучки)" "bash $SKILL/tools/doctor.sh --fix-dash-rule"
else fail "humanizer-ru не установлен" "npx skills add ilyautov/humanizer-ru -g -a claude-code"; fi
python3 -c 'import pymorphy3, razdel' 2>/dev/null && pass "pymorphy3 + razdel (сканер humanizer-ru)" \
  || fail "нет pymorphy3/razdel" "python3 -m pip install --user pymorphy3==2.0.6 razdel==0.5.0"

echo "Голос"
if [ -z "$ELEVENLABS_API_KEY" ]; then
  fail "ELEVENLABS_API_KEY не задан" "read -s \"K?ElevenLabs API key: \" && echo \"export ELEVENLABS_API_KEY=\\\"\$K\\\"\" >> ~/.zshrc && unset K && source ~/.zshrc"
else
  code=$(curl -s -o /tmp/short-doctor-sub.json -w "%{http_code}" https://api.elevenlabs.io/v1/user/subscription -H "xi-api-key: $ELEVENLABS_API_KEY")
  if [ "$code" = "200" ]; then
    left=$(python3 -c 'import json;d=json.load(open("/tmp/short-doctor-sub.json"));print(d["character_limit"]-d["character_count"], "из", d["character_limit"], "·", d["tier"])')
    pass "ключ ElevenLabs работает · осталось символов: $left"
  else fail "ключ ElevenLabs отвечает $code" "проверь ключ и права: Text to Speech, Voices read/write, Models read, User read"; fi
  rm -f /tmp/short-doctor-sub.json
fi
vid=$(python3 -c "import json;print(json.load(open('$SKILL/channel.json'))['voice'].get('voice_id') or '')")
[ -n "$vid" ] && pass "voice_id в channel.json: $vid" || fail "voice_id не задан в channel.json" "python3 $SKILL/tools/voices.py — выбери голос и впиши его id"

echo "Ресурсы"
free=$(df -g "$HOME" | awk 'NR==2{print $4}')
[ "${free:-0}" -ge 3 ] && pass "свободно на диске: ${free} ГБ" || warn "мало места: ${free} ГБ" "рендер и проекты занимают ~50–100 МБ на ролик"

echo
[ $bad -eq 0 ] && echo "Готово: всё на месте ($ok проверок)." || echo "Есть что исправить: $bad. Команды — под каждым ✗."

if [ "$1" = "--fix-dash-rule" ] && [ -n "$HR" ]; then
  cat >> "$HR/edit-log.md" <<'EOF'

## тире в сценариях для озвучки

Фидбек: в сценариях роликов тире — это пауза для голоса ElevenLabs. Без тире диктор читает фразу слитно.

Правило: в тексте озвучки (поля `say` в script.json и колонка «Текст озвучки» в SCRIPT.md навыка /short) длинное тире «—» не снимать и не заменять. Остальные правки действуют. В подписях к постам (POSTS.md) тире снимаются как обычно.

Область: сценарии для озвучки навыка /short
EOF
  echo "Правило про тире добавлено в $HR/edit-log.md"
fi
