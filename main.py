import os
import io
import json
import asyncio
from pypdf import PdfReader
import docx
from google import genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Render.com ga kiritiladigan maxfiy kalitlar
TELEGRAM_TOKEN = os.getenv("9231599712:AAEmseFix58KQPInk6Ja2K4QRNRYNkEKj3o")
GEMINI_KEY = os.getenv("AQ.Ab8RN6KYNSkUl9Xxh4HEbcJRn-hSemkbB0sUOyR275gt01CcFA")

# Gemini mijozi
ai_client = genai.Client(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! Menga test savollari va javoblari bo'lgan PDF yoki DOCX (Word) fayl yuboring.\n\n"
        "Men ulardan avtomatik ravishda Telegram Quiz (viktorina) tuzib beraman."
    )

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def parse_tests_with_gemini(raw_text: str) -> list:
    prompt = f"""
    Quyidagi matnda test savollari, javob variantlari va to'g'ri javoblar mavjud.
    Matn ichidan barcha testlarni aniq ajratib ol va faqat JSON massiv formatida qaytar.

    Telegram Quiz talablari:
    - Har bir savol matni maksimal 290 belgi bo'lsin.
    - Variantlar soni 2 tadan 10 tagacha bo'lsin.
    - Har bir variant matni maksimal 95 belgi bo'lsin.
    - To'g'ri javob indeksi "correct_option_id" (0 dan boshlanadi). Agar matnda qaysi biri to'g'riligi ko'rsatilgan bo'lsa (qalin qilingan, kalitda berilgan, yulduzcha qo'yilgan), shuni tanla; agar belgilanmagan bo'lsa, mantiqan to'g'ri javobni o'zing aniqlab belgilab ket.

    Qaytariladigan JSON strukturasi:
    [
      {{
        "question": "Savol matni...",
        "options": ["A variant", "B variant", "C variant", "D variant"],
        "correct_option_id": 0
      }}
    ]

    Hech qanday qo'shimcha so'z, izoh yoki markdown formatlash belgisisiz (```json siz) toza JSON qaytargin.

    Matn:
    {raw_text[:25000]}
    """
    
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    clean_text = response.text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
        
    return json.loads(clean_text.strip())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_name = doc.file_name.lower()
    
    if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
        await update.message.reply_text("Iltimos, faqat .pdf yoki .docx formatidagi hujjat yuboring.")
        return

    status_msg = await update.message.reply_text("Hujjat yuklab olinmoqda va tahlil qilinmoqda, iltimos kuting...")

    try:
        tg_file = await doc.get_file()
        file_bytes = await tg_file.download_as_bytearray()

        if file_name.endswith(".pdf"):
            text = extract_text_from_pdf(file_bytes)
        else:
            text = extract_text_from_docx(file_bytes)

        if not text.strip():
            await status_msg.edit_text("Hujjatdan matn ajratib bo'lmadi. Fayl bo'sh yoki skanerlangan rasm bo'lishi mumkin.")
            return

        await status_msg.edit_text("Gemini AI savollarni viktorinaga aylantirmoqda (bu biroz vaqt olishi mumkin)...")
        quizzes = parse_tests_with_gemini(text)

        if not quizzes:
            await status_msg.edit_text("Hujjatdan test savollari topilmadi.")
            return

        await status_msg.edit_text(f"{len(quizzes)} ta savol tayyorlandi! Yuborilmoqda...")

        for item in quizzes:
            question = item.get("question", "")[:290]
            options = [opt[:95] for opt in item.get("options", [])][:10]
            correct_id = item.get("correct_option_id", 0)

            if len(options) >= 2 and 0 <= correct_id < len(options):
                await context.bot.send_poll(
                    chat_id=update.effective_chat.id,
                    question=question,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    is_anonymous=False
                )
                await asyncio.sleep(0.6)  # Telegram anti-spam blokka tushmaslik uchun

    except Exception as e:
        await status_msg.edit_text(f"Xatolik yuz berdi: {str(e)}")

def main():
    if not TELEGRAM_TOKEN or not GEMINI_KEY:
        raise ValueError("TELEGRAM_BOT_TOKEN yoki GEMINI_API_KEY o'rnatilmagan. Render muhit o'zgaruvchilarini tekshiring!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
