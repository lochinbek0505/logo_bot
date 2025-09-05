#!/usr/bin/env python3
"""
Seed script: assets/hayvon_imgs/* + assets/hayvon_audio/* -> Admin API (hayvon_top)

- Rasm va audio fayllarni /upload/image va /upload/audio orqali yuklaydi
- So'ng /hayvon ga item yaratadi (agar key allaqachon mavjud bo'lsa - o'tkazib yuboradi)
- Title uchun ixtiyoriy mapping (UZbekcha nomlar); bo'lmasa filestem Capitalized
- Group default = "animal" (xohlasangiz filename prefiksi bo'yicha aniqlashni kengaytirishingiz mumkin)

Ishga tushirish:
  export ADMIN_BASE=http://127.0.0.1:8099
  export ADMIN_API_KEY=changeme
  python seed_hayvon_from_assets.py
"""

import os
import sys
from pathlib import Path
import re
import requests

ADMIN_BASE = os.getenv("ADMIN_BASE", "http://127.0.0.1:8099")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "changeme")

# Loyihadagi mavjud papkalar (sizning strukturangizga mos)
IMG_DIR = Path("bot/assets/hayvon_imgs")
AUD_DIR = Path("bot/assets/hayvon_audio")

HEADERS = {"X-API-Key": ADMIN_API_KEY}

# ixtiyoriy: kalit -> ko'rinadigan nom
TITLE_MAP = {
    "ayiq": "Ayiq",
    "bori": "Bo'ri",
    "echki": "Echki",
    "eshak": "Eshak",
    "goz": "G'oz",
    "ilon": "Ilon",
    "kuchuk": "Kuchuk",
    "maymun": "Maymun",
    "mushuk": "Mushuk",
    "ot": "Ot",
    "sher": "Sher",
    "sigir": "Sigir",
    "tovuq": "Tovuq",
    "tulki": "Tulki",
    "xoroz": "Xo'roz",
    "yolbars": "Yo'lbars",
    "ari": "Ari",
    "chigirtka": "Chigirtka",
    "basketbol": "Basketbol",
    "kulish": "Kulish",
    "kuylash": "Kuylash",
    "opish": "O'pish",
    "tish_yuvish": "Tish yuvish",
    "yugurish": "Yugurish",
    "yurmoq": "Yurish",
    "mashina": "Mashina",
    "metro": "Metro",
    "poyezd": "Poyezd",
    "vertalyot": "Vertolyot",
    "chaqmoq": "Chaqmoq",
    "shamol": "Shamol",
    "yomgir": "Yomg'ir",
    "aksirish": "Aksirish",
    "chivin": "Chivin",
    "hurrak": "Hurrak",
    "kema": "Kema",
    "ninachi": "Ninachi",
    "pasha": "Pasha",
    "qarsak": "Qarsak",
    "sharshara": "Sharshara",
    "shuttak": "Shuttak",
    "suv_oynash": "Suv o'ynash",
    "tishlash": "Tishlash",
    "tolqin": "Tolqin",
    "yiglamoq": "Yig'lash",
    "yotalmoq": "Yo'talish",
}

# ixtiyoriy: fayl nomi/kalitga ko'ra guruh aniqlash (default animal)
def infer_group(key: str) -> str:
    # aniq ro'yxatlar bo'yicha misollar:
    actions = {"basketbol", "kulish", "kuylash", "opish", "tish_yuvish", "yugurish", "yurmoq",
               "aksirish", "qarsak", "tishlash", "yiglamoq", "yotalmoq", "suv_oynash"}
    transport = {"mashina", "metro", "poyezd", "vertalyot"}
    nature = {"chaqmoq", "shamol", "yomgir", "sharshara", "tolqin"}
    insects = {"ari", "chigirtka", "ninachi", "chivin", "pasha"}  # bularni ham "animal"ga qoldirsak bo'ladi

    if key in actions:
        return "action"
    if key in transport:
        return "transport"
    if key in nature:
        return "nature"
    return "animal"  # default

def to_key(stem: str) -> str:
    # fayl nomi -> kalit (kichik, faqat [a-z0-9_])
    s = stem.lower()
    s = s.replace("’", "'").replace("`", "'").replace("ʻ", "'").replace("ʼ", "'")
    s = s.strip()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = s.strip("_")
    return s

def pick_audio_for_key(key: str, audios: dict) -> Path | None:
    # aniq mos tushsa
    if key in audios:
        return audios[key]
    # ba'zi fayllar 'o''/ 'g\'' kabi translit bo'lishi mumkin – sodda fallback
    # (kerak bo'lsa o'zingiz qoidalarga boyitib oling)
    return None

def upload_file(kind: str, path: Path) -> dict:
    """
    kind: 'image' yoki 'audio'
    """
    url = f"{ADMIN_BASE}/upload/{kind}"
    with path.open("rb") as f:
        files = {"file": (path.name, f)}
        r = requests.post(url, headers=HEADERS, files=files, timeout=60)
    r.raise_for_status()
    return r.json()  # {'url': '/static/...', 'path': '/abs/...'} yoki shunga yaqin

def create_hayvon(item: dict) -> dict:
    """
    item: {'key','title','group','image_path','audio_path','enabled','sort_order'}
    """
    url = f"{ADMIN_BASE}/hayvon"
    r = requests.post(url, headers=HEADERS, json=item, timeout=30)
    if r.status_code == 409:
        print(f"[SKIP] key already exists: {item['key']}")
        return {"ok": False, "skipped": True}
    r.raise_for_status()
    return r.json()

def main():
    if not IMG_DIR.exists():
        print(f"Image dir not found: {IMG_DIR}")
        sys.exit(1)
    if not AUD_DIR.exists():
        print(f"Audio dir not found: {AUD_DIR}")
        sys.exit(1)

    # rasm va audio fayllar ro'yxati
    img_files = {to_key(p.stem): p for p in IMG_DIR.glob("*") if p.is_file()}
    aud_files = {to_key(p.stem): p for p in AUD_DIR.glob("*") if p.is_file()}

    if not img_files:
        print("No images found.")
        sys.exit(1)

    print(f"Found {len(img_files)} images, {len(aud_files)} audios.")
    created = 0
    skipped = 0
    failed = 0

    # sort-order uchun oddiy inkrement
    sort_order = 0

    for key, img_path in sorted(img_files.items()):
        audio_path = pick_audio_for_key(key, aud_files)
        if not audio_path:
            print(f"[WARN] Audio not found for key={key} (image={img_path.name}) — item is skipped.")
            skipped += 1
            continue

        title = TITLE_MAP.get(key) or key.replace("_", " ").capitalize()
        group = infer_group(key)

        try:
            up_img = upload_file("image", img_path)   # -> {'url': '/static/images/...'}
            up_aud = upload_file("audio", audio_path) # -> {'url': '/static/audios/...'}
            payload = {
                "key": key,
                "title": title,
                "group": group,
                "image_path": up_img.get("url") or up_img.get("path"),
                "audio_path": up_aud.get("url") or up_aud.get("path"),
                "enabled": True,
                "sort_order": sort_order,
            }
            res = create_hayvon(payload)
            if res.get("skipped"):
                skipped += 1
            else:
                created += 1
                sort_order += 1
                print(f"[OK] {key} -> group={group} title={title}")
        except requests.HTTPError as e:
            failed += 1
            print(f"[ERR] key={key}: HTTP {e.response.status_code} {e.response.text}")
        except Exception as e:
            failed += 1
            print(f"[ERR] key={key}: {e}")

    print(f"Done. created={created}, skipped={skipped}, failed={failed}")

if __name__ == "__main__":
    main()
