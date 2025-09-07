from __future__ import annotations

import os
import re
import difflib
import logging
from urllib.parse import urljoin
from typing import List, Tuple, Dict, Any

import aiohttp
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import StateFilter
from aiogram.types.input_file import BufferedInputFile

from utils.mohir import stt
from utils.check_audio import check_audio

# ===================== Logging =====================
LOG_LEVEL = os.getenv("DIAG_LOG_LEVEL", "INFO").upper()
log = logging.getLogger("diagnostika")
if not log.handlers:
    # Agar umumiy logging main.py da sozlanmagan bo'lsa, hech bo'lmasa konsolga yozib tursin
    handler = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(fmt)
    log.addHandler(handler)
log.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# ===================== Konfiguratsiya =====================
# Eslatma: Admin API public GET endpointlari:
#   /                 -> {"name":"Bot Admin API","ok":true}
#   /export/diagnostika
#   /export/hayvon
#   /darslik (GET) , /export/darslik/{code}
# Bular admin_app.py da aniq ko'rsatilgan.  :contentReference[oaicite:4]{index=4}
ADMIN_BASE = os.getenv("ADMIN_BASE", "http://185.217.131.39").rstrip("/")
EXPECTED_REPEATS = int(os.getenv("EXPECTED_REPEATS", "2"))

# ===================== FSM =====================
class Diagnostika(StatesGroup):
    running = State()

diagnostika = Router(name="diagnostika")

# ===================== Admin API dan ma'lumot olish =====================
async def _admin_healthcheck(base: str) -> tuple[bool, int, str]:
    """ADMIN_BASE / ni tekshiradi va natijani logga yozadi."""
    url = f"{base}/"
    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"User-Agent": "diag-bot/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.get(url) as r:
                status = r.status
                text = await r.text()
                ok = 200 <= status < 300
                log.info("DIAG health: GET %s -> %s | %s", url, status, text[:200].replace("\n", " "))
                return ok, status, text
    except Exception as e:
        log.exception("DIAG health: FAILED %s: %s", url, e)
        return False, 0, str(e)

async def fetch_diagnostika_items() -> List[Tuple[str, str]]:
    """
    Admin API'dan diagnostika setlarini olamiz.
    Natija: [(phrase, image_full_url), ...]
    """
    url = f"{ADMIN_BASE}/export/diagnostika"
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"User-Agent": "diag-bot/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            async with sess.get(url) as r:
                status = r.status
                if status != 200:
                    body = await r.text()
                    log.error("DIAG items: GET %s -> %s | %s", url, status, body[:200])
                r.raise_for_status()
                data = await r.json()
                items: List[Tuple[str, str]] = []
                for d in data:
                    phrase = (d.get("phrase") or "").strip()
                    img_rel = (d.get("image_url") or "").strip()
                    if not phrase or not img_rel:
                        continue
                    items.append((phrase, urljoin(ADMIN_BASE + "/", img_rel)))
                log.info("DIAG items: received %d item(s)", len(items))
                return items
    except Exception as e:
        log.exception("DIAG items: FAILED GET %s: %s", url, e)
        raise

# ===================== Matn tahlil yordamchi funksiyalar =====================
def _normalize(t: str) -> str:
    t = (t or "").lower()
    t = t.replace("’", "'").replace("`", "'").replace("ʻ", "'").replace("ʼ", "'")
    t = re.sub(r"[^a-zа-яёҳқғў0-9'\s]", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _count_word_occurrences(text: str, word: str) -> int:
    return len(re.findall(rf"\b{re.escape(word)}\b", text))

def _lev_distance(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    dp = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        dp[i][0] = i
    for j in range(lb + 1):
        dp[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[la][lb]

def _closest_token(target: str, tokens: List[str]) -> tuple[str, int]:
    best = ("", 10 ** 9)
    for tok in tokens:
        d = _lev_distance(target, tok)
        if d < best[1]:
            best = (tok, d)
    return best

def _char_diff(a: str, b: str) -> str:
    diff = []
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            diff.append(a[i1:i2])
        elif tag == "replace":
            diff.append(f"[{a[i1:i2]}→{b[j1:j2]}]")
        elif tag == "delete":
            diff.append(f"[{a[i1:i2]}→ ]")
        elif tag == "insert":
            diff.append(f"[→{b[j1:j2]}]")
    return "".join(diff)

def _format_instruction(title: str) -> str:
    parts = title.split()
    w1 = parts[0] if len(parts) > 0 else ""
    w2 = parts[1] if len(parts) > 1 else ""
    w3 = parts[2] if len(parts) > 2 else ""
    return (
        "<blockquote>"
        "Ushbu rasmlar nomini 2 martadan, mikrofonni to‘xtatmagan holda quyidagi shakllardan birini tanlab talaffuz qiling.\n"
        f"{w1}, {w1}.\n"
        f"{w2}, {w2}.\n"
        f"{w3}, {w3}.\n"
        "<b>YOKI</b>\n"
        f"{w1}, {w2}, {w3}.\n"
        f"{w1}, {w2}, {w3}.\n\n"
        "Talaffuz vaqtida tekshiriluvchi mustaqil talaffuzni amalga oshirishi zarur. Boshqa shovqinlar aralashishi taqiqlanadi."
        "</blockquote>"
    )

def _evaluate(expected_phrase: str, stt_text: str) -> Dict[str, Any]:
    try:
        check_ok = check_audio(expected_phrase, stt_text)
    except Exception as e:
        log.exception("DIAG check_audio failed: %s", e)
        check_ok = False

    norm_expected = _normalize(expected_phrase)
    norm_rec = _normalize(stt_text)
    rec_tokens = norm_rec.split()

    exp_words = norm_expected.split()
    per_word_counts = {w: _count_word_occurrences(norm_rec, w) for w in exp_words}

    none_matched = all(c == 0 for c in per_word_counts.values())
    all_good = all(c >= EXPECTED_REPEATS for c in per_word_counts.values())
    pass_ok = all_good or (str(check_ok) == "True")

    diffs_info = []
    if rec_tokens:
        for w in exp_words:
            c = per_word_counts[w]
            if c < EXPECTED_REPEATS:
                closest, dist = _closest_token(w, rec_tokens)
                diff = _char_diff(w, closest)
                diffs_info.append((w, closest, dist, diff))

    return {
        "pass_ok": pass_ok,
        "none_matched": none_matched,
        "all_good": all_good,
        "per_word_counts": per_word_counts,
        "diffs_info": diffs_info,
        "stt_text": stt_text.strip(),
        "exp_words": exp_words,
    }

def _format_step_report(result: Dict[str, Any], expected_phrase: str) -> str:
    if result["none_matched"]:
        return (
            "<blockquote>Umuman mos kelmadi: kutilgan so‘zlardan birortasi topilmadi.\n"
            f"Kutilgan: {expected_phrase}</blockquote>\n\n"
            f"🔎 Sizning talaffuzingiz:\n<code>{result['stt_text']}</code>"
        )

    lines = []
    for w in result["exp_words"]:
        c = result["per_word_counts"].get(w, 0)
        mark = "✅" if c >= EXPECTED_REPEATS else "❌"
        lines.append(f"{mark} {w}: {c}/{EXPECTED_REPEATS}")
    counts_block = "\n".join(lines)

    if result["pass_ok"] and not result["diffs_info"]:
        diffs_block = "100% moslik"
    elif result["diffs_info"]:
        diffs_block = "\n".join([
            f"• {w} ↔ {closest}  (lev={dist})\n  harf-farqlar: {diff}"
            for (w, closest, dist, diff) in result["diffs_info"]
        ])
    else:
        diffs_block = "—"

    status = "✅ To‘g‘ri" if result["pass_ok"] else "❌ Xatolik bor"
    return (
        "<blockquote>"
        f"Natija (shu rasm bo‘yicha): {status}\n\n"
        f"{counts_block}\n\n"
        f"🔎 Sizning talaffuzingiz:\n<code>{result['stt_text']}</code>\n\n"
        f"📉 Tovush/harf darajasidagi farqlar:\n{diffs_block}</blockquote>"
    )

def _format_final_summary(stats: Dict[str, Any]) -> str:
    total = stats.get("total", 0)
    ok = len(stats.get("passed", []))
    agg: Dict[str, int] = {}
    for _, wc in stats.get("failed_words_per_step", {}).items():
        for w, c in wc.items():
            if w not in agg:
                agg[w] = c
            else:
                agg[w] = min(agg[w], c)

    lines = [f"📊 Umumiy natija: {ok}/{total} bosqich muvaffaqiyatli."]
    if agg:
        lines.append("\n❌ Muammo bo‘lgan so‘z(tovush)lar:")
        for w in sorted(agg.keys()):
            c = agg[w]
            lines.append(f"  • {w}: {c}/{EXPECTED_REPEATS}")
    else:
        lines.append("\nA’lo! Hech qanday xatolik topilmadi.")

    return "<blockquote>" + "\n".join(lines) + "</blockquote>"

# ===================== Rasmni yuklab, fayl sifatida jo'natish =====================
async def _download_bytes(url: str) -> tuple[bytes, str]:
    timeout = aiohttp.ClientTimeout(total=25)
    headers = {"User-Agent": "diag-bot/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
        async with s.get(url) as r:
            log.info("DIAG photo: GET %s -> %s", url, r.status)
            r.raise_for_status()
            return await r.read(), r.headers.get("Content-Type", "")

async def _send_step_photo(message: types.Message, step_index: int, items: List[Tuple[str, str]]):
    title, img_url = items[step_index]
    try:
        data, ct = await _download_bytes(img_url)
        ct_l = (ct or "").lower()
        if "png" in ct_l:
            ext = ".png"
        elif "webp" in ct_l:
            ext = ".webp"
        elif "gif" in ct_l:
            ext = ".gif"
        else:
            ext = ".jpg"

        photo = BufferedInputFile(data, filename=f"diagnostika_{step_index}{ext}")
        await message.answer_photo(
            photo,
            caption=_format_instruction(title),
            parse_mode=ParseMode.HTML,
        )
        log.info("DIAG photo: sent step=%d title=%s", step_index, title)
    except Exception as e:
        log.exception("DIAG photo: FAILED step=%d url=%s: %s", step_index, img_url, e)
        await message.answer(_format_instruction(title), parse_mode=ParseMode.HTML)

# ===================== Boshlash =====================
# Eslatma: Reply-menyu tugmasi "📋 Diagnostika qilish" — ana shu matn bilan bog'lash kerak.  :contentReference[oaicite:5]{index=5}
@diagnostika.message(F.text == "📋 Diagnostika qilish")
async def diagnostika_start(message: types.Message, state: FSMContext):
    # Avval healthcheck
    ok, status, _ = await _admin_healthcheck(ADMIN_BASE)
    if not ok:
        await message.answer(f"Admin API bilan bog‘lanib bo‘lmadi (status={status}). Iltimos, qayta urinib ko‘ring.")
        return

    try:
        items = await fetch_diagnostika_items()
    except Exception as e:
        await message.answer(f"Konfiguratsiyani olishda xatolik: {e}")
        return

    if not items:
        await message.answer("Diagnostika setlari topilmadi. Admin paneldan qo‘shing.")
        log.warning("DIAG start: empty items")
        return

    await state.update_data(_items=items, _idx=0, _passed=[], _failed=[], _failed_words_per_step={})
    await state.set_state(Diagnostika.running)

    await state.update_data(test_current=items[0][0])  # phrase
    log.info("DIAG start: total=%d first_title=%s", len(items), items[0][0])
    await _send_step_photo(message, 0, items)

# ===================== AUDIO handler (dinamik) =====================
@diagnostika.message(StateFilter(Diagnostika.running), F.audio | F.voice)
async def handle_step_audio(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")

    data = await state.get_data()
    items: List[Tuple[str, str]] = data.get("_items", [])
    idx: int = int(data.get("_idx", 0))

    if not items:
        await message.answer("Sozlamalar topilmadi. /start dan qayta boshlang.")
        log.warning("DIAG audio: items missing in state")
        await state.clear()
        return

    # 1) Audio faylni yuklab olish
    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await message.bot.get_file(file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        raw = file_bytes.getvalue()
        log.info("DIAG audio: downloaded bytes=%d", len(raw) if raw else 0)
    except Exception as e:
        log.exception("DIAG audio: download failed: %s", e)
        await message.answer("Faylni yuklab olishda xatolik. Qayta urinib ko‘ring.")
        return

    expected_phrase = data.get("test_current", items[idx][0])

    # 2) STT
    try:
        res = stt(raw)
        stt_text = res["result"]["text"]
        log.info("DIAG stt: len=%d text='%s'", len(stt_text or ""), (stt_text or "")[:120])
    except Exception as e:
        log.exception("DIAG stt: failed: %s", e)
        await message.answer("Audio matnga aylantirishda xatolik. Yana urinib ko‘ring.")
        return

    if not stt_text or not stt_text.strip():
        await message.answer("Ovozdan matn aniqlanmadi. Iltimos, so‘zlarni aniqroq takrorlang.")
        log.warning("DIAG stt: empty text")
        return

    # 3) Baholash va hisobot
    result = _evaluate(expected_phrase, stt_text)
    log.info("DIAG eval: idx=%d pass_ok=%s all_good=%s none_matched=%s counts=%s",
             idx, result["pass_ok"], result["all_good"], result["none_matched"], result["per_word_counts"])
    await message.answer(_format_step_report(result, expected_phrase), parse_mode=ParseMode.HTML)

    # 4) Umumiy statistikani yangilash
    passed = data.get("_passed", [])
    failed = data.get("_failed", [])
    failed_words_per_step = data.get("_failed_words_per_step", {})

    if result["pass_ok"]:
        passed.append(idx)
    else:
        failed.append(idx)
        word_counts = {}
        for w in result["exp_words"]:
            c = result["per_word_counts"].get(w, 0)
            if c < EXPECTED_REPEATS:
                word_counts[w] = c
        if word_counts:
            failed_words_per_step[idx] = word_counts

    # 5) Keyingi bosqichga o'tish yoki yakunlash
    idx += 1
    if idx < len(items):
        await state.update_data(
            _passed=passed,
            _failed=failed,
            _failed_words_per_step=failed_words_per_step,
            _idx=idx,
            test_current=items[idx][0]
        )
        log.info("DIAG next: move to idx=%d title='%s'", idx, items[idx][0])
        await _send_step_photo(message, idx, items)
    else:
        final_stats = {
            "total": len(items),
            "passed": passed,
            "failed": failed,
            "failed_words_per_step": failed_words_per_step,
        }
        log.info("DIAG done: total=%d passed=%d failed=%d", len(items), len(passed), len(failed))
        await message.answer(_format_final_summary(final_stats), parse_mode=ParseMode.HTML)
        await state.clear()

# ===================== No-audio holatda ogohlantirish =====================
@diagnostika.message(StateFilter(Diagnostika.running))
async def only_audio_warning(message: types.Message):
    await message.answer("Iltimos, voice yoki audio yuboring 🎙️")

# ===================== /reload qo'mondasi =====================
@diagnostika.message(F.text == "/reload")
async def reload_cfg(message: types.Message, state: FSMContext):
    try:
        items = await fetch_diagnostika_items()
    except Exception as e:
        await message.answer(f"Yuklashda xatolik: {e}")
        return

    if not items:
        await message.answer("Diagnostika setlari topilmadi.")
        log.warning("DIAG reload: empty items")
        return

    await state.update_data(
        _items=items, _idx=0, _passed=[], _failed=[],
        _failed_words_per_step={}, test_current=items[0][0]
    )
    await state.set_state(Diagnostika.running)
    log.info("DIAG reload: total=%d", len(items))
    await message.answer("♻️ Diagnostika konfiguratsiyasi yangilandi. Qayta boshlaymiz.")
    await _send_step_photo(message, 0, items)
