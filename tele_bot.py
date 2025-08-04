import logging
import re
import os
import random
import csv
import io
import asyncio
import uuid # TÍNH NĂNG MỚI: Thêm thư viện để tạo ID duy nhất
from functools import wraps
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Thêm thư viện để vẽ biểu đồ
import matplotlib.pyplot as plt
import seaborn as sns

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# TÍNH NĂNG MỚI: Thêm các lớp cần thiết cho Chế độ Inline
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    JobQueue,
    InlineQueryHandler, # TÍNH NĂNG MỚI
)

# Import module scraper
import scraper

# Tải các biến môi trường từ file .env
load_dotenv()

# ======================= CẤU HÌNH =======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
RATING_COLUMN_NAME = os.getenv("RATING_COLUMN_NAME", "Rating")

# Cấu hình cho scraper
INSTAGRAM_COOKIE_FILE = os.getenv("INSTAGRAM_COOKIE_FILE")
FULL_NAME_COLUMN_NAME = os.getenv("FULL_NAME_COLUMN_NAME", "full_name")
PROFILE_PIC_URL_COLUMN_NAME = os.getenv("PROFILE_PIC_URL_COLUMN_NAME", "profile_pic_url")

# Bật logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Kiểm tra các biến môi trường
if not all([TELEGRAM_TOKEN, GOOGLE_SHEET_NAME, WORKSHEET_NAME, GOOGLE_CREDENTIALS_FILE, INSTAGRAM_COOKIE_FILE]):
    logger.critical("Lỗi: Một hoặc nhiều biến môi trường chưa được thiết lập trong file .env.")
    exit()

# ======================= KHỞI TẠO KẾT NỐI GOOGLE SHEET =======================
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

# ======================= ĐỊNH NGHĨA TRẠNG THÁI HỘI THOẠI =======================
(ASKING_RATING,) = range(1)
(ASK_CONFIRM_DELETE,) = range(1, 2)
(ASK_UPDATE_RATING,) = range(2, 3)
(PAGING_SEARCH_RESULTS,) = range(3, 4)

# ======================= HÀM TIỆN ÍCH & VẼ BIỂU ĐỒ =======================

def create_stats_chart(rating_counts: dict):
    """Hàm để vẽ biểu đồ cột từ dữ liệu thống kê."""
    try:
        stars = [f"{i} ⭐" for i in rating_counts.keys()]
        counts = list(rating_counts.values())

        plt.figure(figsize=(10, 6))
        sns.set_theme(style="darkgrid", font_scale=1.1)
        
        bar_plot = sns.barplot(x=stars, y=counts, palette="viridis", width=0.6)

        plt.title('Phân loại tài liệu theo xếp hạng', fontsize=18, weight='bold')
        plt.ylabel('Số lượng tài liệu', fontsize=12)
        
        for index, value in enumerate(counts):
            if value > 0:
                bar_plot.text(index, value, str(value), color='black', ha="center", va='bottom', fontsize=11)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='PNG', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
    except Exception as e:
        logger.error(f"Lỗi khi tạo biểu đồ: {e}")
        return None

def find_row_by_username(username_to_find: str):
    """Tìm hàng và dữ liệu của một hồ sơ dựa trên username."""
    if worksheet is None: return None, None
    all_records = worksheet.get_all_records()
    for index, record in enumerate(all_records):
        url = record.get("URL", "")
        if url:
            existing_username = extract_username(url)
            if existing_username and existing_username.lower() == username_to_find.lower():
                return index + 2, record
    return None, None

def extract_username(url: str) -> str | None:
    """Trích xuất username từ URL Instagram."""
    if not url: return None
    match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_](?:(?:[A-Za-z0-9_]|\.(?!\.))*[A-Za-z0-9_]){0,29})", url)
    return match.group(1) if match else None

# ======================= TÁC VỤ NỀN CHO SCRAPING =======================

async def scraping_background_task(context: ContextTypes.DEFAULT_TYPE):
    """Tác vụ chạy ngầm để cào dữ liệu mà không làm block bot."""
    job = context.job
    chat_id = job.chat_id
    
    try:
        all_records = worksheet.get_all_records()
        headers = worksheet.row_values(1)
        
        full_name_col = headers.index(FULL_NAME_COLUMN_NAME) + 1
        pic_url_col = headers.index(PROFILE_PIC_URL_COLUMN_NAME) + 1
        
        profiles_to_scrape = []
        for index, record in enumerate(all_records):
            if not record.get(FULL_NAME_COLUMN_NAME) and record.get("URL"):
                profiles_to_scrape.append({
                    "row_index": index + 2,
                    "url": record.get("URL")
                })
        
        if not profiles_to_scrape:
            await context.bot.send_message(chat_id, text="✅ Không có hồ sơ mới nào cần cào dữ liệu.")
            return

        scraped_data = await asyncio.to_thread(
            scraper.scrape_instagram_profiles, INSTAGRAM_COOKIE_FILE, profiles_to_scrape
        )
        
        if scraped_data is None:
             await context.bot.send_message(chat_id, text="❌ Lỗi: Không thể cào dữ liệu. Vui lòng kiểm tra file cookie và log.")
             return

        if scraped_data:
            cells_to_update = []
            for data in scraped_data:
                row = data['row_index']
                cells_to_update.append(gspread.Cell(row, full_name_col, data['full_name']))
                cells_to_update.append(gspread.Cell(row, pic_url_col, data['profile_pic_url']))
                
            if cells_to_update:
                worksheet.update_cells(cells_to_update)
                
            await context.bot.send_message(chat_id, text=f"✅ Hoàn tất! Đã cào và cập nhật dữ liệu cho {len(scraped_data)} hồ sơ.")
        else:
            await context.bot.send_message(chat_id, text="ℹ️ Không có dữ liệu nào được cào thành công.")

    except Exception as e:
        logger.error(f"Lỗi trong tác vụ nền scraping: {e}")
        await context.bot.send_message(chat_id, text="❌ Đã có lỗi xảy ra trong quá trình cào dữ liệu.")

# ======================= CÁC HÀM XỬ LÝ LỆNH CHÍNH =======================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Xin chào! Tôi là bot quản lý tài liệu của bạn.\n\n"
        "<b>Các lệnh có sẵn:</b>\n"
        "/add <code>&lt;url1&gt; [url2]...</code> - Thêm một hoặc nhiều tài liệu.\n"
        "/update <code>&lt;username&gt;</code> - Cập nhật rating.\n"
        "/delete <code>&lt;username&gt;</code> - Xóa một tài liệu.\n"
        "/search <code>&lt;tên&gt;</code> - Tìm kiếm tài liệu.\n"
        "/stats - Xem thống kê dữ liệu.\n"
        "/random <code>[rating]</code> - Lấy tài liệu ngẫu nhiên.\n"
        "/backup - Sao lưu dữ liệu ra file CSV.\n"
        "/scrape - Lấy thông tin chi tiết cho các tài liệu mới.\n"
        "/cancel - Hủy bỏ thao tác hiện tại.\n\n"
        "<b>Chế độ Inline:</b>\n"
        "Gõ <code>@tên_bot</code> và một từ khóa trong bất kỳ chat nào để tìm kiếm và chia sẻ nhanh!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data:
        context.user_data.clear()
        if update.callback_query:
            await update.callback_query.edit_message_text("Đã hủy thao tác.")
        else:
            await update.message.reply_text("Đã hủy thao tác.")
    return ConversationHandler.END

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if worksheet is None:
        await update.message.reply_text("Lỗi: Bot không thể kết nối tới Google Sheet.")
        return
    
    all_records = worksheet.get_all_records()
    total_profiles = len(all_records)
    
    ratings = [float(r.get(RATING_COLUMN_NAME, 0)) for r in all_records if str(r.get(RATING_COLUMN_NAME, '')).replace('.', '', 1).isdigit()]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    rating_counts = {i: 0 for i in range(1, 6)}
    for r in ratings:
        rating_int = int(round(r))
        if 1 <= rating_int <= 5:
            rating_counts[rating_int] += 1
        
    stats_text = (
        f"<b>📊 Thống kê dữ liệu</b>\n\n"
        f"<b>Tổng số tài liệu:</b> {total_profiles}\n"
        f"<b>Rating trung bình:</b> {avg_rating:.2f} ⭐️"
    )

    chart_buffer = create_stats_chart(rating_counts)
    
    if chart_buffer:
        await update.message.reply_photo(
            photo=chart_buffer,
            caption=stats_text,
            parse_mode=ParseMode.HTML
        )
    else:
        stats_text += "\n\n<b>Phân loại theo rating:</b>\n"
        for star, count in rating_counts.items():
            stats_text += f"  - {star} sao: {count} tài liệu\n"
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if worksheet is None:
        await update.message.reply_text("Lỗi: Bot không thể kết nối tới Google Sheet.")
        return
    all_records = worksheet.get_all_records()
    target_rating = context.args[0] if context.args else None
    filtered_records = all_records
    if target_rating and target_rating.isdigit():
        filtered_records = [r for r in all_records if str(r.get(RATING_COLUMN_NAME)) == target_rating]
        if not filtered_records:
            await update.message.reply_text(f"Không có tài liệu nào có rating là {target_rating} sao.")
            return
    if not filtered_records:
        await update.message.reply_text("Không có tài liệu nào trong sheet.")
        return
    random_profile = random.choice(filtered_records)
    username = extract_username(random_profile.get("URL", ""))
    profile_text = (f"<b>✨ Tài liệu ngẫu nhiên ✨</b>\n\n<b>Username:</b> <code>{username or 'N/A'}</code>\n<b>Rating:</b> {random_profile.get(RATING_COLUMN_NAME, 'N/A')} ⭐️")
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if worksheet is None:
        await update.message.reply_text("Lỗi: Bot không thể kết nối tới Google Sheet.")
        return
    await update.message.reply_text("Đang chuẩn bị file sao lưu...")
    all_data = worksheet.get_all_values()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(all_data)
    output.seek(0)
    backup_file = io.BytesIO(output.getvalue().encode('utf-8'))
    backup_file.name = f"backup_{GOOGLE_SHEET_NAME.replace(' ', '_')}.csv"
    await update.message.reply_document(document=backup_file)

async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if worksheet is None:
        await update.message.reply_text("Lỗi: Bot không thể kết nối tới Google Sheet.")
        return
    chat_id = update.effective_chat.id
    if context.job_queue:
        await update.message.reply_text("⏳ Đã bắt đầu quá trình cào dữ liệu. Tác vụ sẽ chạy ngầm, tôi sẽ thông báo khi hoàn thành.")
        context.job_queue.run_once(scraping_background_task, 0, chat_id=chat_id, name=f"scrape_{chat_id}")
    else:
        await update.message.reply_text("Lỗi: JobQueue không khả dụng.")

# --- Luồng hội thoại cho lệnh /add ---

async def write_profile_to_sheet(profile_data: dict):
    """Hàm tiện ích để ghi một hồ sơ hoàn chỉnh vào Google Sheet."""
    try:
        headers = worksheet.row_values(1)
        new_row = [''] * len(headers)
        
        url_col_index = headers.index("URL")
        rating_col_index = headers.index(RATING_COLUMN_NAME)
        
        new_row[url_col_index] = profile_data.get('url', '')
        new_row[rating_col_index] = profile_data.get('rating', '')
        
        worksheet.append_row(new_row)
        logger.info(f"Đã ghi tài liệu {profile_data.get('username')} vào sheet.")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi ghi vào sheet: {e}")
        return False

async def process_next_in_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý hồ sơ tiếp theo trong hàng đợi."""
    profiles_to_process = context.user_data.get('profiles_to_process', [])
    
    if not profiles_to_process:
        await update.callback_query.edit_message_text("✅ Hoàn tất! Đã xử lý tất cả tài liệu mới.")
        context.user_data.clear()
        return ConversationHandler.END

    next_profile = profiles_to_process.pop(0)
    context.user_data['current_profile'] = next_profile
    
    username = next_profile['username']
    
    keyboard = [[InlineKeyboardButton(f"⭐️ {i}", callback_data=str(i)) for i in range(1, 6)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"⏳ Đang xử lý: <b>{username}</b>\n({len(context.user_data['profiles_to_process']) + 1} tài liệu còn lại)\nVui lòng chọn xếp hạng:"
    
    await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    return ASKING_RATING

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu quá trình thêm và đánh giá tuần tự nhiều hồ sơ."""
    if worksheet is None:
        await update.message.reply_text("Lỗi: Bot không thể kết nối tới Google Sheet.")
        return ConversationHandler.END
    if not context.args:
        await update.message.reply_text("Sử dụng: /add <code>&lt;url1&gt; [url2]...</code>", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    urls_to_add = context.args
    profiles_to_process_queue = []
    skipped_usernames = []
    
    try:
        existing_urls = worksheet.col_values(2)[1:]
        existing_usernames = {extract_username(url).lower() for url in existing_urls if extract_username(url)}
        
        for raw_url in urls_to_add:
            new_username = extract_username(raw_url)
            if not new_username:
                await update.message.reply_text(f"URL không hợp lệ: <code>{raw_url}</code>", parse_mode=ParseMode.HTML)
                continue
            if new_username.lower() in existing_usernames:
                skipped_usernames.append(new_username)
                continue
            
            canonical_url = f"https://www.instagram.com/{new_username}/"
            profiles_to_process_queue.append({'username': new_username, 'url': canonical_url})

        if not profiles_to_process_queue:
            summary_text = "Không có tài liệu nào được thêm."
            if skipped_usernames:
                summary_text += f"\nCác tài liệu sau đã tồn tại: <code>{', '.join(skipped_usernames)}</code>"
            await update.message.reply_text(summary_text, parse_mode=ParseMode.HTML)
            return ConversationHandler.END

        context.user_data['profiles_to_process'] = profiles_to_process_queue
        
        first_profile = context.user_data['profiles_to_process'].pop(0)
        context.user_data['current_profile'] = first_profile
        username = first_profile['username']
        
        keyboard = [[InlineKeyboardButton(f"⭐️ {i}", callback_data=str(i)) for i in range(1, 6)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"⏳ Đang xử lý: <b>{username}</b>\n({len(context.user_data['profiles_to_process']) + 1} tài liệu còn lại)\nVui lòng chọn xếp hạng:"
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        return ASKING_RATING

    except Exception as e:
        logger.error(f"Lỗi khi thực hiện /add: {e}")
        await update.message.reply_text("Đã có lỗi xảy ra trong quá trình xử lý.")
        return ConversationHandler.END

async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    rating_value = query.data
    current_profile = context.user_data.get('current_profile')
    
    if not current_profile:
        await query.edit_message_text("Lỗi: Không tìm thấy thông tin tài liệu hiện tại. Vui lòng thử lại.")
        return ConversationHandler.END

    current_profile['rating'] = rating_value
    
    await write_profile_to_sheet(current_profile)
    
    return await process_next_in_queue(update, context)

# --- Các luồng hội thoại khác ---
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("Sử dụng: /delete <code>&lt;username&gt;</code>", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    username = context.args[0]
    row_index, record = find_row_by_username(username)
    if not row_index:
        await update.message.reply_text(f"Không tìm thấy tài liệu với username <code>{username}</code>.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    context.user_data['row_to_delete'] = row_index
    keyboard = [[InlineKeyboardButton("🔴 Có, xóa đi", callback_data="confirm_delete"), InlineKeyboardButton("Không", callback_data="cancel_delete")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Bạn có chắc chắn muốn xóa tài liệu của <code>{username}</code> không?", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return ASK_CONFIRM_DELETE
async def delete_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_delete":
        row_index = context.user_data.get('row_to_delete')
        try:
            worksheet.delete_rows(row_index)
            await query.edit_message_text("🗑️ Đã xóa tài liệu thành công.")
        except Exception as e:
            logger.error(f"Lỗi khi xóa hàng: {e}")
            await query.edit_message_text("Lỗi khi xóa tài liệu.")
    else:
        await query.edit_message_text("Đã hủy thao tác xóa.")
    context.user_data.clear()
    return ConversationHandler.END
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("Sử dụng: /update <code>&lt;username&gt;</code>", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    username = context.args[0]
    row_index, record = find_row_by_username(username)
    if not row_index:
        await update.message.reply_text(f"Không tìm thấy tài liệu với username <code>{username}</code>.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    context.user_data['row_to_update'] = row_index
    current_rating = record.get(RATING_COLUMN_NAME, "chưa có")
    keyboard = [[InlineKeyboardButton(f"⭐️ {i}", callback_data=f"update_{i}") for i in range(1, 6)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Tài liệu <code>{username}</code> (rating hiện tại: {current_rating}).\nChọn rating mới:", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return ASK_UPDATE_RATING
async def update_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    rating_value = query.data.split('_')[1]
    row_index = context.user_data.get('row_to_update')
    try:
        headers = worksheet.row_values(1)
        rating_col_index = headers.index(RATING_COLUMN_NAME) + 1
        worksheet.update_cell(row_index, rating_col_index, rating_value)
        await query.edit_message_text(f"✅ Đã cập nhật rating thành {rating_value} sao!")
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật rating: {e}")
        await query.edit_message_text("Lỗi khi cập nhật rating.")
    context.user_data.clear()
    return ConversationHandler.END
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("Sử dụng: /search <code>&lt;tên&gt;</code>", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    search_term = " ".join(context.args).lower()
    all_records = worksheet.get_all_records()
    results = []
    for record in all_records:
        username = extract_username(record.get("URL", ""))
        full_name = record.get("full_name", "")
        if (username and search_term in username.lower()) or (full_name and search_term in full_name.lower()):
            results.append(record)
    if not results:
        await update.message.reply_text(f"Không tìm thấy tài liệu nào khớp với '<code>{search_term}</code>'.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    context.user_data['search_results'] = results
    context.user_data['search_page'] = 0
    await send_search_page(update, context)
    return PAGING_SEARCH_RESULTS
async def send_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data['search_results']
    page = context.user_data['search_page']
    page_size = 5
    start_index = page * page_size
    end_index = start_index + page_size
    page_results = results[start_index:end_index]
    message_text = "<b>Kết quả tìm kiếm:</b>\n\n"
    for record in page_results:
        username = extract_username(record.get("URL", ""))
        message_text += f"• <code>{username or 'N/A'}</code> - Rating: {record.get(RATING_COLUMN_NAME, 'N/A')}\n"
    message_text += f"\n<i>Trang {page + 1} / { -(-len(results) // page_size) }</i>"
    keyboard = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ Trước", callback_data="search_prev"))
    if end_index < len(results):
        row.append(InlineKeyboardButton("Sau ➡️", callback_data="search_next"))
    if row:
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
async def search_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data
    if action == "search_next":
        context.user_data['search_page'] += 1
    elif action == "search_prev":
        context.user_data['search_page'] -= 1
    await send_search_page(update, context)
    return PAGING_SEARCH_RESULTS

# --- TÍNH NĂNG MỚI: Xử lý Chế độ Inline ---
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Xử lý các yêu cầu tìm kiếm inline.
    Hỗ trợ nhiều loại truy vấn: tìm kiếm theo tên, xem thống kê, lấy ngẫu nhiên, lọc theo rating.
    """
    query = update.inline_query.query.lower().strip()
    
    if worksheet is None:
        return

    all_records = worksheet.get_all_records()
    inline_results = []

    # --- Phân tích và xử lý các loại truy vấn khác nhau ---

    # 1. Xử lý lệnh "stats"
    if query == "stats":
        total_profiles = len(all_records)
        ratings = [float(r.get(RATING_COLUMN_NAME, 0)) for r in all_records if str(r.get(RATING_COLUMN_NAME, '')).replace('.', '', 1).isdigit()]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Nội dung tin nhắn sẽ được gửi
        message_content = (
            f"<b>📊 Thống kê dữ liệu</b>\n\n"
            f"<b>Tổng số tài liệu:</b> {total_profiles}\n"
            f"<b>Rating trung bình:</b> {avg_rating:.2f} ⭐️"
        )
        
        inline_results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="📊 Thống kê dữ liệu",
                description=f"Tổng số: {total_profiles} | Rating trung bình: {avg_rating:.2f} ⭐",
                input_message_content=InputTextMessageContent(
                    message_content, parse_mode=ParseMode.HTML
                )
            )
        )

    # 2. Xử lý lệnh "random"
    elif query.startswith("random"):
        if not all_records:
            return
        
        random_profile = random.choice(all_records)
        username = extract_username(random_profile.get("URL", ""))
        full_name = random_profile.get(FULL_NAME_COLUMN_NAME, username)
        rating = random_profile.get(RATING_COLUMN_NAME, "N/A")
        
        message_content = (
            f"<b>✨ Tài liệu ngẫu nhiên ✨</b>\n\n"
            f"<b>Tên:</b> {full_name}\n"
            f"<b>Username:</b> <code>{username}</code>\n"
            f"<b>Rating:</b> {rating} ⭐\n"
            f"<b>URL:</b> {random_profile.get('URL')}"
        )
        
        inline_results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🎲 Lấy tài liệu ngẫu nhiên",
                description=f"@{username} - Rating: {rating} ⭐",
                input_message_content=InputTextMessageContent(
                    message_content, parse_mode=ParseMode.HTML
                ),
                thumbnail_url=random_profile.get(PROFILE_PIC_URL_COLUMN_NAME),
            )
        )

    # 3. Xử lý lệnh lọc theo rating (ví dụ: "5 sao")
    elif "sao" in query and query.split(" ")[0].isdigit():
        try:
            target_rating = query.split(" ")[0]
            filtered_records = [r for r in all_records if str(r.get(RATING_COLUMN_NAME)) == target_rating]
            
            if not filtered_records:
                inline_results.append(InlineQueryResultArticle(id=str(uuid.uuid4()), title=f"Không có tài liệu nào được xếp hạng {target_rating} sao.", input_message_content=InputTextMessageContent(f"Không tìm thấy tài liệu nào có rating {target_rating} sao.")))
            
            for record in filtered_records[:10]: # Giới hạn 10 kết quả
                username = extract_username(record.get("URL", ""))
                full_name = record.get(FULL_NAME_COLUMN_NAME, username)
                
                message_content = (f"<b>Tài liệu tham khảo: {full_name}</b>\n\n<b>Username:</b> <code>{username}</code>\n<b>Rating:</b> {target_rating} ⭐\n<b>URL:</b> {record.get('URL')}")
                
                inline_results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=full_name,
                        description=f"@{username} - Rating: {target_rating} ⭐",
                        input_message_content=InputTextMessageContent(message_content, parse_mode=ParseMode.HTML),
                        thumbnail_url=record.get(PROFILE_PIC_URL_COLUMN_NAME),
                    )
                )
        except Exception as e:
            logger.error(f"Lỗi khi lọc inline theo rating: {e}")

    # 4. Xử lý tìm kiếm mặc định theo tên
    elif len(query) >= 2:
        search_term = query.lower()
        search_results = []
        for record in all_records:
            username = extract_username(record.get("URL", ""))
            full_name = record.get(FULL_NAME_COLUMN_NAME, "")
            if (username and search_term in username.lower()) or (full_name and search_term in full_name.lower()):
                search_results.append(record)
        
        for record in search_results[:10]:
            username = extract_username(record.get("URL", ""))
            full_name = record.get(FULL_NAME_COLUMN_NAME, username)
            rating = record.get(RATING_COLUMN_NAME, "N/A")
            
            message_content = (f"<b>Tài liệu tham khảo: {full_name}</b>\n\n<b>Username:</b> <code>{username}</code>\n<b>Rating:</b> {rating} ⭐\n<b>URL:</b> {record.get('URL')}")
            
            inline_results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=full_name,
                    description=f"@{username} - Rating: {rating} ⭐",
                    input_message_content=InputTextMessageContent(message_content, parse_mode=ParseMode.HTML),
                    thumbnail_url=record.get(PROFILE_PIC_URL_COLUMN_NAME),
                )
            )

    # Trả về kết quả cho Telegram
    await update.inline_query.answer(inline_results, cache_time=10)



def main() -> None:
    """Khởi chạy và vận hành bot."""
    job_queue = JobQueue()
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .job_queue(job_queue)
        .connect_timeout(15)
        .read_timeout(15)
        .build()
    )

    # Thêm các hội thoại
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            ASKING_RATING: [CallbackQueryHandler(rating_callback, pattern=r"^\d$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    delete_conv = ConversationHandler(entry_points=[CommandHandler("delete", delete_command)], states={ASK_CONFIRM_DELETE: [CallbackQueryHandler(delete_confirmation_callback)]}, fallbacks=[CommandHandler("cancel", cancel_command)])
    update_conv = ConversationHandler(entry_points=[CommandHandler("update", update_command)], states={ASK_UPDATE_RATING: [CallbackQueryHandler(update_rating_callback, pattern=r"^update_")]}, fallbacks=[CommandHandler("cancel", cancel_command)])
    search_conv = ConversationHandler(entry_points=[CommandHandler("search", search_command)], states={PAGING_SEARCH_RESULTS: [CallbackQueryHandler(search_page_callback, pattern=r"^search_")]}, fallbacks=[CommandHandler("cancel", cancel_command)])

    # Thêm các trình xử lý vào ứng dụng
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("scrape", scrape_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(add_conv)
    application.add_handler(delete_conv)
    application.add_handler(update_conv)
    application.add_handler(search_conv)
    
    # Thêm trình xử lý cho chế độ inline
    application.add_handler(InlineQueryHandler(inline_query_handler))

    print("🚀 Bot siêu cấp đang chạy... Nhấn Ctrl+C để dừng.")
    application.run_polling()


if __name__ == "__main__":
    main()
