
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)
from geopy.geocoders import Nominatim
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8966021539:AAF5HWasJALEYYVhpFbQZjqI6K0PjY5ZauQ"
ADMIN_PASSWORD = "today a reader tomorrow a leader".lower()

# Yagona Konversiya uchun holatlar
MENU_SELECTION, TYPING_NAME, REGISTERING_LOCATION, ADMIN_AUTH = range(4)


def start(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Ro'yxatdan o'tish 📝", callback_data="register_start"),
            InlineKeyboardButton("Admin Panel 🔒", callback_data="admin_start")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg_text = "Salom! Quyidagi variantlardan birini tanlang:"

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=msg_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(text=msg_text, reply_markup=reply_markup)

    return MENU_SELECTION


def inline_button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == "register_start":
        user_id = update.effective_user.id
        user = database.get_user(user_id)
        if user:
            query.edit_message_text(
                f"Salom {user['name']}! Siz allaqachon ro'yxatdan o'tgansiz.\n"
                "Joylashuvingizni yangilash uchun qaytadan /start bosing va joylashuv yuboring."
            )
            return ConversationHandler.END

        query.edit_message_text("Iltimos, ism va familiyangizni kiriting:")
        return TYPING_NAME

    elif query.data == "admin_start":
        query.edit_message_text("Admin panelga kirish uchun parolni kiriting:")
        return ADMIN_AUTH


def save_name(update: Update, context: CallbackContext) -> int:
    user_name = update.message.text
    user_id = update.effective_user.id

    database.add_user(user_id, user_name)

    location_keyboard = KeyboardButton(text="Joylashuvni ulashish 📍", request_location=True)
    custom_keyboard = [[location_keyboard]]

    update.message.reply_text(
        f"Rahmat, {user_name}! Endi pastdagi tugma orqali joylashuvingizni (GPS) yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            custom_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return REGISTERING_LOCATION


def handle_location(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    location = update.message.location

    if not location:
        update.message.reply_text("Iltimos, faqat tugma yoki GPS orqali joylashuv yuboring.")
        return REGISTERING_LOCATION

    lat = location.latitude
    lon = location.longitude

    update.message.reply_text("Manzilingiz aniqlanmoqda, iltimos kuting...")

    try:
        geolocator = Nominatim(user_agent="my_telegram_bot_registration")
        location_data = geolocator.reverse((lat, lon), timeout=10)
        address = location_data.address if location_data else f"Namangan (Koordinata: {lat}, {lon})"
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        address = "Namangan fvhvkslkd.steeet fdghisur"

    user = database.get_user(user_id)
    if not user:
        database.add_user(user_id, update.effective_user.first_name)

    database.update_location(user_id, address)

    update.message.reply_text(
        f"Muvaffaqiyatli saqlandi!\n\nAniqlangan manzil:\n{address}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def admin_auth(update: Update, context: CallbackContext) -> int:
    input_password = update.message.text.strip().lower()

    if input_password == ADMIN_PASSWORD:
        users = database.get_all_users()
        if not users:
            update.message.reply_text("🔒 Admin Panel\n\nHozircha ro'yxatdan o'tgan foydalanuvchilar yo'q.")
            return ConversationHandler.END

        text = "🔒 Admin Panel\n\nRo'yxatdan o'tgan foydalanuvchilar:\n\n"
        for idx, (u_id, name, loc) in enumerate(users, 1):
            text += f"{idx}. ID: {u_id}\nIsm: {name}\nManzil: {loc}\n\n"

        update.message.reply_text(text)
        return ConversationHandler.END
    else:
        update.message.reply_text("❌ Parol noto'g'ri! Qaytadan urinib ko'ring yoki bekor qilish uchun /cancel yozing.")
        return ADMIN_AUTH


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Jarayon bekor qilindi. Boshlash uchun /start bosing.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    database.init_db()
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Yagona boshqaruv konversiyasi
    main_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("register", start),  # /register ham bosh menyuni ochadi
            CommandHandler("admin", start)  # /admin ham bosh menyuni ochadi
        ],
        states={
            MENU_SELECTION: [CallbackQueryHandler(inline_button_handler)],
            TYPING_NAME: [MessageHandler(Filters.text & ~Filters.command, save_name)],
            REGISTERING_LOCATION: [MessageHandler(Filters.location, handle_location)],
            ADMIN_AUTH: [MessageHandler(Filters.text & ~Filters.command, admin_auth)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    # To'g'ridan-to'g'ri (konversiyadan tashqari) GPS yuborilganda ham ushlab qolish
    dispatcher.add_handler(MessageHandler(Filters.location & ~Filters.command, handle_location))
    dispatcher.add_handler(main_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
