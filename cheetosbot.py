# bot.py
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters
from telegram.ext import (Application,CommandHandler,MessageHandler,ConversationHandler,ContextTypes,filters,CallbackQueryHandler)
import os 
from dotenv import load_dotenv
import db 
from db import get_pool, is_user_registered, get_user, add_user 
from pathlib import Path
import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import logging
load_dotenv(Path(__file__).resolve().parent / ".env")

WEBAPP_URL =os.getenv("WEBAPP_URL")    
TOKEN =os.getenv("BOT_TOKEN")

ASK_NAME, ASK_PHONE = range(2)
# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    db_user = await db.get_user(user.id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Запустить игру", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("Удалить регистрацию", callback_data="delete_registration")]   
    ])

    if db_user:
        await update.message.reply_text(
            f"С возвращением, {db_user['name']} 👋",
            reply_markup=keyboard
        )
        return ConversationHandler.END

    await update.message.reply_text("Как вас зовут?")
    return ASK_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await update.message.reply_text(
        "Напишите номер телефона или нажмите кнопку ниже:",
        reply_markup=keyboard,
    )
    return ASK_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    user = update.effective_user

    await db.add_user(
        user_id=user.id,
        name=context.user_data.get("name"),
        username=user.username,
        number=phone,
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Запустить игру", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("Удалить регистрацию", callback_data="delete_registration")]
    ])

    await update.message.reply_text(
        "Готово!\nТеперь ты можешь лайкать призы и участвовать в розыгрышах!",
        reply_markup=keyboard,
    )
    return ConversationHandler.END

async def on_startup(app: Application):
    await db.init_db()

async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.message.web_app_data.data  # строка JSON
    await update.message.reply_text(f"Получил данные из мини-игры:\n{data}")    

async def delete_registration_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="delete_registration_yes"),
            InlineKeyboardButton("❌ Отмена", callback_data="delete_registration_no"),
        ]
    ])

    await query.edit_message_text(
        "⚠️ Удалить регистрацию?\n\n"
        "Профиль будет скрыт (soft delete). При необходимости можно восстановить.",
        reply_markup=keyboard
    )

async def delete_registration_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    await db.soft_delete_user(user.id)
    context.user_data.clear()

    await query.edit_message_text(
        "✅ Регистрация удалена (профиль скрыт).\n\n"
        "Чтобы зарегистрироваться заново — /start"
    )

async def delete_registration_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Ок, не удаляю.")

def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(on_startup)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
        },
        fallbacks=[],
    )
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))
    app.add_handler(CallbackQueryHandler(delete_registration_confirm, pattern="^delete_registration$"))
    app.add_handler(CallbackQueryHandler(delete_registration_yes, pattern="^delete_registration_yes$"))
    app.add_handler(CallbackQueryHandler(delete_registration_no, pattern="^delete_registration_no$"))


    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
