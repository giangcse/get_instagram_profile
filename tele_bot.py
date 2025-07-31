import logging
import re
import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

# Tải các biến môi trường từ file .env
load_dotenv()

# ======================= CẤU HÌNH =======================
# Lấy thông tin cấu hình từ biến môi trường đã tải
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
RATING_COLUMN_NAME = os.getenv("RATING_COLUMN_NAME", "Rating")

# Bật logging để dễ dàng theo dõi và sửa lỗi
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Kiểm tra các biến môi trường quan trọng đã được thiết lập chưa
if not all([TELEGRAM_TOKEN, GOOGLE_SHEET_NAME, WORKSHEET_NAME, GOOGLE_CREDENTIALS_FILE]):
    logger.critical(
        "Lỗi: Một hoặc nhiều biến môi trường (TELEGRAM_TOKEN, GOOGLE_SHEET_NAME, WORKSHEET_NAME, GOOGLE_CREDENTIALS_FILE) "
        "chưa được thiết lập trong file .env. Vui lòng kiểm tra lại."
    )
    exit()

# ======================= KHỞI TẠO KẾT NỐI GOOGLE SHEET =======================
# TỐI ƯU: Khởi tạo kết nối một lần duy nhất khi bot khởi động để tăng tốc độ phản hồi.
worksheet = None
try:
    logger.info("Đang kết nối tới Google Sheets...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open(GOOGLE_SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    logger.info("✅ Kết nối Google Sheets thành công!")
except Exception as e:
    logger.critical(f"LỖI NGHIÊM TRỌNG: Không thể kết nối tới Google Sheets khi khởi động. Lỗi: {e}")
    # Biến worksheet sẽ là None, các lệnh sau sẽ kiểm tra và báo lỗi cho người dùng.

# Định nghĩa các trạng thái cho cuộc hội thoại
ASKING_RATING = range(1)

# ======================= CÁC HÀM CỦA BOT =======================

def extract_username(url: str) -> str | None:
    """Trích xuất username từ URL Instagram bằng regex để xử lý nhiều định dạng URL."""
    if not url:
        return None
    match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_](?:(?:[A-Za-z0-9_]|\.(?!\.))*[A-Za-z0-9_]){0,29})", url)
    if match:
        return match.group(1)
    return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng khi người dùng gõ /start."""
    await update.message.reply_text(
        "Xin chào! Tôi là bot giúp bạn thêm hồ sơ Instagram vào Google Sheet.\n\n"
        "Gửi lệnh `/add <URL_INSTAGRAM>` để bắt đầu."
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu quá trình thêm URL, kiểm tra trùng lặp và hỏi xếp hạng."""
    # TỐI ƯU: Kiểm tra xem kết nối Google Sheet có sẵn sàng không.
    if worksheet is None:
        await update.message.reply_text("Lỗi nghiêm trọng: Bot không thể kết nối tới Google Sheet. Vui lòng kiểm tra lại cấu hình và khởi động lại bot.")
        return ConversationHandler.END

    if not context.args:
        await update.message.reply_text("Vui lòng cung cấp URL. Ví dụ: /add https://www.instagram.com/google")
        return ConversationHandler.END

    profile_url = context.args[0]
    new_username = extract_username(profile_url)

    if not new_username:
        await update.message.reply_text("URL Instagram không hợp lệ. Vui lòng kiểm tra lại.")
        return ConversationHandler.END
    
    try:
        # TỐI ƯU: Sử dụng lại kết nối `worksheet` đã được khởi tạo toàn cục.
        existing_urls = worksheet.col_values(2)[1:]
        
        for existing_url in existing_urls:
            existing_username = extract_username(existing_url)
            if existing_username and existing_username.lower() == new_username.lower():
                await update.message.reply_text(
                    f"⚠️ Profile với username <code>{new_username}</code> đã tồn tại trong sheet.",
                    parse_mode=ParseMode.HTML
                )
                return ConversationHandler.END

        worksheet.append_row(["", profile_url])
        new_row_index = len(worksheet.get_all_values())
        context.user_data['row_to_update'] = new_row_index
        logger.info(f"Đã thêm URL '{profile_url}' vào hàng {new_row_index}.")

        keyboard = [[InlineKeyboardButton(f"⭐️ {i}", callback_data=str(i)) for i in range(1, 6)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("✅ Đã thêm URL vào sheet. Vui lòng chọn xếp hạng (rating):", reply_markup=reply_markup)
        
        return ASKING_RATING

    except Exception as e:
        logger.error(f"Lỗi khi thực hiện lệnh /add: {e}")
        await update.message.reply_text("Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau.")
        return ConversationHandler.END

async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý khi người dùng nhấn nút xếp hạng."""
    # TỐI ƯU: Kiểm tra xem kết nối Google Sheet có sẵn sàng không.
    if worksheet is None:
        await update.message.reply_text("Lỗi nghiêm trọng: Bot không thể kết nối tới Google Sheet. Vui lòng kiểm tra lại cấu hình và khởi động lại bot.")
        return ConversationHandler.END
        
    query = update.callback_query
    await query.answer()

    rating_value = query.data
    row_index = context.user_data.get('row_to_update')

    if not row_index:
        await query.edit_message_text(text="Có lỗi xảy ra, không tìm thấy hàng cần cập nhật. Vui lòng thử lại với lệnh /add.")
        return ConversationHandler.END

    try:
        # TỐI ƯU: Sử dụng lại kết nối `worksheet` đã được khởi tạo toàn cục.
        headers = worksheet.row_values(1)
        try:
            rating_col_index = headers.index(RATING_COLUMN_NAME) + 1
        except ValueError:
             await query.edit_message_text(text=f"Lỗi: Không tìm thấy cột '{RATING_COLUMN_NAME}' trong Google Sheet của bạn.")
             return ConversationHandler.END

        worksheet.update_cell(row_index, rating_col_index, rating_value)
        logger.info(f"Đã cập nhật xếp hạng '{rating_value}' cho hàng {row_index}.")
        await query.edit_message_text(text=f"👍 Đã lưu xếp hạng: {rating_value} sao!")

    except Exception as e:
        logger.error(f"Lỗi khi cập nhật rating: {e}")
        await query.edit_message_text(text="Có lỗi xảy ra khi cập nhật xếp hạng. Vui lòng thử lại.")
        
    if 'row_to_update' in context.user_data:
        del context.user_data['row_to_update']
        
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy bỏ cuộc hội thoại hiện tại."""
    await update.message.reply_text("Đã hủy thao tác.")
    if 'row_to_update' in context.user_data:
        del context.user_data['row_to_update']
    return ConversationHandler.END

def main() -> None:
    """Khởi chạy và vận hành bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            ASKING_RATING: [CallbackQueryHandler(rating_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(conv_handler)

    print("🚀 Bot đang chạy... Nhấn Ctrl+C để dừng.")
    application.run_polling()

if __name__ == "__main__":
    main()
