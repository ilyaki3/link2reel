#!/usr/bin/env python3
"""Голоса ElevenLabs, доступные твоему ключу через API (символы не тратит).

  python3 voices.py            # список: id, имя, тип
  python3 voices.py <voice_id> # записать голос в channel.json

На бесплатном тарифе через API работают встроенные голоса (premade) и созданные тобой
(generated — Voice Design, cloned — клон). Голоса из библиотеки — только на платном.
"""
import json, os, sys, urllib.request

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
key = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("Нет ELEVENLABS_API_KEY в окружении.")


def get(path):
    req = urllib.request.Request("https://api.elevenlabs.io" + path, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


if len(sys.argv) > 1:
    vid = sys.argv[1]
    v = get(f"/v1/voices/{vid}")
    p = os.path.join(SKILL, "channel.json")
    c = json.load(open(p, encoding="utf-8"))
    c["voice"].update({"provider": "elevenlabs", "voice_id": vid, "voice_name": v.get("name", "")})
    json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"channel.json: голос «{v.get('name')}» ({vid})")
    sys.exit(0)

data = get("/v2/voices?page_size=100")
rows = sorted(data.get("voices", []), key=lambda v: (v.get("category") != "generated", v.get("category") != "cloned", v["name"]))
print(f"{'voice_id':24} {'тип':12} имя")
for v in rows:
    lab = v.get("labels") or {}
    extra = " · ".join(x for x in (lab.get("gender"), lab.get("accent"), lab.get("age")) if x)
    cat = v.get("category", "")
    note = "  (через API — только платный тариф)" if cat == "professional" else ""
    print(f"{v['voice_id']:24} {cat:12} {v['name']}  {extra}{note}")
print("\nЗапиши выбранный: python3 voices.py <voice_id>")
