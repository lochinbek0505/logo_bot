from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import FSInputFile
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import StateFilter

from pathlib import Path
import re
import difflib

from utils.mohir import stt
from utils.check_audio import check_audio

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMG_DIR = BASE_DIR / "bot" / "assets" / "img"

# 10 ta set (matn, rasm)
sozlar = [
    ("Savat Asal Gilos", "savat.png"),
    ("Zina Uzum Xo'roz", "zina.png"),
    ("Shaftoli Qoshiq Quyosh", "shaftoli.png"),
    ("Choynak Arg'imchoq uch", "choynak.png"),
    ("Jo'ja Zanjir Toj", "joja.png"),
    ("Likop Bulut Stol", "likopcha.png"),
    ("Ruchka Arra Bir", "ruchka.png"),
    ("Kitob Ukki Chelak", "kitob.png"),
    ("Gilos Sigir Barg", "gilos.png"),
    ("Qovun Baqlajon Tovuq", "qovun.png"),
]

EXPECTED_REPEATS = 2  # har bir so‘z kamida 2 marta aytilishi kerak

class Diagnostika(StatesGroup):
    test1 = State()
    test2 = State()
    test3 = State()
    test4 = State()
    test5 = State()
    test6 = State()
    test7 = State()
    test8 = State()
    test9 = State()
    test10 = State()

diagnostika = Router(name="diagnostika")

# -------------------- YORDAMCHI FUNKSIYALAR --------------------

def _normalize(t: str) -> str:
    """So‘zlarni tekshiruv uchun soddalashtirish (punktuatsiyasiz, kichik harf)."""
    t = (t or "").lower()
    t = t.replace("’", "'").replace("`", "'").replace("ʻ", "'").replace("ʼ", "'")
    # faqat harf/raqam va bo'shliq qoldiramiz
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

def _state_to_index(state_str: str) -> int:
    # "Diagnostika:test3" -> 2 (0-based)
    name = state_str.split(":")[-1]  # "test3"
    n = int(name[4:])
    return n - 1

def _format_instruction(title: str) -> str:
    """
    Ko‘rsatma matnini rasmga mos uchta so‘z bilan quradi:
    - W1, W1.
    - W2, W2.
    - W3, W3.
      YOKI
    - W1, W2, W3.
    - W1, W2, W3.
    """
    parts = title.split()
    # ehtiyot chorasi: agar >=3 bo'lmasa ham ishlashi uchun
    w1 = parts[0] if len(parts) > 0 else ""
    w2 = parts[1] if len(parts) > 1 else ""
    w3 = parts[2] if len(parts) > 2 else ""

    return (
        "<blockquote>"
        "Ushbu rasmlar nomini 2 martadan, mikrofonni to‘xtatmagan holda quyidagi shaklardan birini tanlab talaffuz qiling.\n"
        f"{w1}, {w1}.\n"
        f"{w2}, {w2}.\n"
        f"{w3}, {w3}.\n"
        "<b>YOKI</b>\n"
        f"{w1}, {w2}, {w3}.\n"
        f"{w1}, {w2}, {w3}.\n\n"
        "Talaffuz vaqtida tekshiriluvchi mustaqil talaffuzni amalga oshirishi zarur. Boshqa shovqinlar aralashishi taqiqlanadi."
        "</blockquote>"
    )

async def _send_step_photo(message: types.Message, step_index: int):
    title, img = sozlar[step_index]
    await message.answer_photo(
        FSInputFile(IMG_DIR / img),
        caption=_format_instruction(title),
        parse_mode=ParseMode.HTML,
    )

def _evaluate(expected_phrase: str, stt_text: str):
    """Bitta bosqich (rasm) bo‘yicha natijani hisoblaydi."""
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

def _format_step_report(result: dict, expected_phrase: str) -> str:
    """Bir bosqich uchun chiroyli matnli hisobot."""
    if result["none_matched"]:
        return (
            "<blockquote>Umuman mos kelmadi: kutilgan so‘zlardan birortasi topilmadi.\n"
            f"Kutilgan: {expected_phrase}</blockquote>\n\n"
            f"🔎 Sizning talaffuzingiz:\n<code>{result['stt_text']}</code>"
        )

    # so‘zlar bo‘yicha sanash
    lines = []
    for w in result["exp_words"]:
        c = result["per_word_counts"].get(w, 0)
        mark = "✅" if c >= EXPECTED_REPEATS else "❌"
        lines.append(f"{mark} {w}: {c}/{EXPECTED_REPEATS}")
    counts_block = "\n".join(lines)

    # harf/tovush farqlari
    if result["pass_ok"] and not result["diffs_info"]:
        diffs_block = "100% moslik"
    elif result["diffs_info"]:
        diffs_block = "\n".join(
            [f"• {w} ↔ {closest}  (lev={dist})\n  harf-farqlar: {diff}"
             for (w, closest, dist, diff) in result["diffs_info"]]
        )
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

def _format_final_summary(stats: dict) -> str:
    """
    Umumiy yakuniy hisobot:
    - Bosqich raqamlari o‘rniga muammo bo‘lgan so‘z(lar) aggregatsiyasi (min count) ko‘rsatiladi.
    """
    total = len(sozlar)
    ok = len(stats["passed"])
    bad = len(stats["failed"])

    agg: dict[str, int] = {}
    for _, wc in stats["failed_words_per_step"].items():
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

# -------------------- BOSHLASH --------------------

@diagnostika.message(F.text == "Diagnostika qilish")
async def diagnostika_start(message: types.Message, state: FSMContext):
    # Step1 holatini o‘rnatamiz va kutilayotgan matnni saqlaymiz
    await state.set_state(Diagnostika.test1)
    await state.update_data(test1=sozlar[0][0])

    # Umumiy statistika konteynerlari
    await state.update_data(_passed=[], _failed=[], _failed_words_per_step={})

    # 1-rasmni yuboramiz
    await _send_step_photo(message, 0)

# -------------------- AUDIO HANDLER (barcha 10 holatga umumiy) --------------------

@diagnostika.message(
    StateFilter(
        Diagnostika.test1, Diagnostika.test2, Diagnostika.test3, Diagnostika.test4, Diagnostika.test5,
        Diagnostika.test6, Diagnostika.test7, Diagnostika.test8, Diagnostika.test9, Diagnostika.test10
    ),
    F.audio | F.voice
)
async def handle_step_audio(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")

    # Audio/voice faylni olib kelamiz
    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await message.bot.get_file(file_id)
        file_bytes = await message.bot.download_file(file.file_path)
    except Exception:
        await message.answer("Faylni yuklab olishda xatolik. Qayta urinib ko‘ring.")
        return

    # Hozirgi step indeksini topamiz
    cur_state = await state.get_state()
    idx = _state_to_index(cur_state)  # 0..9

    data = await state.get_data()
    expected_key = f"test{idx+1}"
    expected_phrase = data.get(expected_key, sozlar[idx][0])

    # STT
    try:
        stt_text = stt(file_bytes.getvalue())["result"]["text"]
    except Exception:
        await message.answer("Audio matnga aylantirishda xatolik. Yana urinib ko‘ring.")
        return

    if not stt_text or not stt_text.strip():
        await message.answer("Ovozdan matn aniqlanmadi. Iltimos, so‘zlarni aniqroq takrorlang.")
        return

    # Baholash
    result = _evaluate(expected_phrase, stt_text)

    # Hisobotni chiqaramiz (shu rasm bo‘yicha)
    await message.answer(_format_step_report(result, expected_phrase), parse_mode=ParseMode.HTML)

    # Umumiy statistikaga yozib boramiz
    passed = data.get("_passed", [])
    failed = data.get("_failed", [])
    failed_words_per_step = data.get("_failed_words_per_step", {})

    if result["pass_ok"]:
        passed.append(idx)
    else:
        failed.append(idx)
        # qaysi so‘z(lar) kam bo‘lgan — ularning faktik sanog‘ini saqlaymiz
        word_counts = {}
        for w in result["exp_words"]:
            c = result["per_word_counts"].get(w, 0)
            if c < EXPECTED_REPEATS:
                word_counts[w] = c
        if word_counts:
            failed_words_per_step[idx] = word_counts

    await state.update_data(_passed=passed, _failed=failed, _failed_words_per_step=failed_words_per_step)

    # Keyingisiga o'tamiz yoki yakunlaymiz
    if idx < 9:
        # Keyingi stepga o'tish
        next_index = idx + 1
        next_state = getattr(Diagnostika, f"test{next_index+1}")
        await state.set_state(next_state)
        await state.update_data(**{f"test{next_index+1}": sozlar[next_index][0]})
        await _send_step_photo(message, next_index)
    else:
        # Yakuniy hisobot (tovush/so'zlar kesimida)
        summary_data = await state.get_data()
        final_stats = {
            "passed": summary_data.get("_passed", []),
            "failed": summary_data.get("_failed", []),
            "failed_words_per_step": summary_data.get("_failed_words_per_step", {}),
        }
        await message.answer(_format_final_summary(final_stats), parse_mode=ParseMode.HTML)
        await state.clear()

# -------------------- No-audio holatda ogohlantirish --------------------

@diagnostika.message(
    StateFilter(
        Diagnostika.test1, Diagnostika.test2, Diagnostika.test3, Diagnostika.test4, Diagnostika.test5,
        Diagnostika.test6, Diagnostika.test7, Diagnostika.test8, Diagnostika.test9, Diagnostika.test10
    )
)
async def only_audio_warning(message: types.Message):
    await message.answer("Iltimos, voice yoki audio yuboring 🎙️")
