from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import FSInputFile
from aiogram.enums.parse_mode import ParseMode

from pathlib import Path
import re
import difflib

from utils.mohir import stt
from utils.check_audio import check_audio

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "bot" / "assets" / "img"

# Faqat bitta set
sozlar = [
    ("Savat Asal Gilos", "savat.png"),
]

EXPECTED_REPEATS = 2  # har bir so‘z kamida 2 marta aytilishi kerak

class Diagnostika(StatesGroup):
    test1 = State()

diagnostika = Router(name="diagnostika")


def _normalize(t: str) -> str:
    """So‘zlarni tekshiruv uchun soddalashtirish (punktuatsiyasiz, kichik harf)."""
    t = (t or "").lower()
    t = t.replace("’", "'").replace("`", "'").replace("ʻ", "'").replace("ʼ", "'")
    # faqat harf va raqam qoldiramiz
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
                dp[i - 1][j - 1] + cost
            )
    return dp[la][lb]


def _closest_token(target: str, tokens: list[str]) -> tuple[str, int]:
    best = ("", 10**9)
    for tok in tokens:
        d = _lev_distance(target, tok)
        if d < best[1]:
            best = (tok, d)
    return best


def _char_diff(a: str, b: str) -> str:
    diff = []
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            diff.append(a[i1:i2])
        elif tag == 'replace':
            diff.append(f"[{a[i1:i2]}→{b[j1:j2]}]")
        elif tag == 'delete':
            diff.append(f"[{a[i1:i2]}→ ]")
        elif tag == 'insert':
            diff.append(f"[→{b[j1:j2]}]")
    return "".join(diff)


@diagnostika.message(F.text == "Diagnostika qilish")
async def diagnostika_start(message: types.Message, state: FSMContext):
    await state.set_state(Diagnostika.test1)
    await state.update_data(test1=sozlar[0][0])  # "Savat Asal Gilos"

    await message.answer_photo(
        FSInputFile(IMG_DIR / sozlar[0][1]),
        caption=(
            "<blockquote>Ushbu rasmlar nomini 2 martadan, mikrofonni to‘xtatmagan holda takrorlang.\n"
            "(Savat, savat ,Asal, asal ,Gilos, gilos  yoki Savat asal gilos Savat asal gilos shaklida aytishingiz mumkin)</blockquote>"
        ),
        parse_mode=ParseMode.HTML,
    )


@diagnostika.message(Diagnostika.test1, F.audio | F.voice)
async def echo_audio(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await message.bot.get_file(file_id)
        file_bytes = await message.bot.download_file(file.file_path)
    except Exception:
        await message.answer("Faylni yuklab olishda xatolik. Qayta urinib ko‘ring.")
        return

    data = await state.get_data()
    expected_phrase = data.get("test1", sozlar[0][0])

    try:
        stt_text = stt(file_bytes.getvalue())["result"]["text"]
    except Exception:
        await message.answer("Audio matnga aylantirishda xatolik. Yana urinib ko‘ring.")
        return

    if not stt_text or not stt_text.strip():
        await message.answer("Ovozdan matn aniqlanmadi. Iltimos, so‘zlarni aniqroq takrorlang.")
        return

    try:
        check_ok = check_audio(expected_phrase, stt_text)
    except Exception:
        check_ok = False

    norm_expected = _normalize(expected_phrase)
    norm_rec = _normalize(stt_text)
    rec_tokens = norm_rec.split()

    exp_words = norm_expected.split()
    per_word_counts = {w: _count_word_occurrences(norm_rec, w) for w in exp_words}

    none_matched = all(c == 0 for c in per_word_counts.values())
    all_good = all(c >= EXPECTED_REPEATS for c in per_word_counts.values())

    await state.clear()

    if all_good or str(check_ok) == "True":
        await message.answer("✅ Tabriklaymiz! Siz so‘zlarni to‘g‘ri takrorladingiz.")
        return

    if none_matched:
        await message.answer(
            "<blockquote>Umuman mos kelmadi: kutilgan so‘zlardan birortasi topilmadi.\n"
            f"Kutilgan: {expected_phrase}</blockquote>\n\n"
            f"🔎 Sizning talaffuzingiz :\n<code>{stt_text.strip()}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Har bir so‘zga hisobot
    counts_info = []
    diffs_info = []
    for w in exp_words:
        c = per_word_counts[w]
        mark = "✅" if c >= EXPECTED_REPEATS else "❌"
        counts_info.append(f"{mark} {w}: {c}/{EXPECTED_REPEATS}")
        if c < EXPECTED_REPEATS and rec_tokens:
            closest, dist = _closest_token(w, rec_tokens)
            diff = _char_diff(w, closest)
            diffs_info.append(f"• {w} ↔ {closest}  (lev={dist})\n  harf-farqlar: {diff}")

    counts_block = "\n".join(counts_info)
    diffs_block = "\n".join(diffs_info)

    # ✅ Endi STT matn + farqlar bitta xabarda chiroyli chiqadi
    await message.answer(
        "<blockquote>Sizda xatoliklar bor:\n\n"
        f"{counts_block}\n\n"
        f"🔎 STT matn:\n<code>{stt_text.strip()}</code>\n\n"
        f"📉 Tovush/harf darajasidagi farqlar:\n{diffs_block}</blockquote>",
        parse_mode=ParseMode.HTML,
    )
