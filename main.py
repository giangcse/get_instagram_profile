import time
import os
import pickle
import json
import re
import gspread # THƯ VIỆN MỚI
from google.oauth2.service_account import Credentials # THƯ VIỆN MỚI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException

# ======================= CẤU HÌNH =======================
# THAY ĐỔI: Cấu hình cho Google Sheets
GOOGLE_SHEET_NAME = "DSSV" # Ví dụ: "Instagram Scraper"
WORKSHEET_NAME = "Profiles" # Tên trang tính (tab) bên trong file Sheet
GOOGLE_CREDENTIALS_FILE = "credentials.json" # Đường dẫn đến file JSON bạn đã tải về

# Giữ lại tên các cột để logic không thay đổi
URL_COLUMN_NAME = "URL"
FULL_NAME_COLUMN_NAME = "full_name"
PROFILE_PIC_URL_COLUMN = "profile_pic_url"
COOKIE_FILE_PATH = "instagram_cookies.pkl"
# ==========================================================

# SỬA ĐỔI: Hàm được nâng cấp để lấy username làm phương án dự phòng
def get_instagram_profile_data(driver, url):
    """
    Sử dụng Selenium để truy cập URL và lấy dữ liệu profile từ JSON endpoint.
    Nếu thất bại, sẽ thử lại bằng cách cào dữ liệu từ thẻ meta.
    Luôn ưu tiên lấy full_name, nếu không có sẽ lấy username.
    """
    try:
        # Đảm bảo URL sạch và thêm endpoint JSON
        clean_url = url.split("?")[0]
        if not clean_url.endswith('/'):
            clean_url += '/'
        json_url = f"{clean_url}?__a=1&__d=dis"

        driver.get(json_url)
        time.sleep(2)

        pre_tag = driver.find_element(By.TAG_NAME, 'pre')
        data = json.loads(pre_tag.text)

        user_data = data.get('graphql', {}).get('user', {})
        
        # THAY ĐỔI: Ưu tiên lấy full_name, nếu rỗng thì lấy username
        display_name = user_data.get('full_name') or user_data.get('username', '')
        avatar_url = user_data.get('profile_pic_url_hd', user_data.get('profile_pic_url', ''))

        if user_data.get('is_private') and not user_data.get('followed_by_viewer'):
            print(" Lỗi: Đây là tài khoản riêng tư và bạn không theo dõi.")
            return "Private Account", None

        return display_name, avatar_url

    except (NoSuchElementException, json.JSONDecodeError):
        print(f" Info: Không thể lấy JSON cho {url}. Thử lại bằng cách cào dữ liệu meta tag.")
        try:
            driver.get(url)
            time.sleep(3)
            
            if "This account is private" in driver.page_source:
                print(" Lỗi: Đây là tài khoản riêng tư và bạn không theo dõi.")
                return "Private Account", None

            title_element = driver.find_element(By.XPATH, "//meta[@property='og:title']")
            title_content = title_element.get_attribute('content')

            # THAY ĐỔI: Trích xuất full_name và username từ tiêu đề meta tag
            full_name = title_content.split('(')[0].strip()
            
            username_match = re.search(r'\(@(.*?)\)', title_content)
            username = username_match.group(1) if username_match else ''
            
            # Ưu tiên full_name, nếu không có thì lấy username
            display_name = full_name or username

            avatar_element = driver.find_element(By.XPATH, "//meta[@property='og:image']")
            avatar_url = avatar_element.get_attribute('content')

            return display_name, avatar_url
        except Exception as e:
            print(f" Lỗi khi thử lại bằng meta tag cho URL {url}: {e}")
            return None, None
    except Exception as e:
        print(f" Lỗi không xác định khi xử lý URL {url}: {e}")
        return None, None

# --- THAY ĐỔI: Khởi tạo kết nối Google Sheets ---
print("🔐 Đang kết nối tới Google Sheets...")
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(creds)
spreadsheet = client.open(GOOGLE_SHEET_NAME)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
print(f"✅ Kết nối thành công tới Sheet '{GOOGLE_SHEET_NAME}' và Worksheet '{WORKSHEET_NAME}'")

# --- Khởi tạo trình duyệt Selenium (Giữ nguyên) ---
print("🚀 Khởi tạo trình duyệt Selenium...")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# --- Xử lý Cookie và đăng nhập (Giữ nguyên) ---
try:
    if os.path.exists(COOKIE_FILE_PATH):
        print("🍪 Tìm thấy file cookie, đang tải phiên đăng nhập...")
        cookies = pickle.load(open(COOKIE_FILE_PATH, "rb"))
        driver.get("https://www.instagram.com/")
        time.sleep(2)
        for cookie in cookies:
            driver.add_cookie(cookie)
        print("✅ Đã tải cookie thành công!")
        driver.refresh()
    else:
        print("⚠️ Không tìm thấy file cookie. Vui lòng đăng nhập thủ công.")
        driver.get("https://www.instagram.com/accounts/login/")
        input(">>> Đăng nhập vào Instagram trên trình duyệt vừa mở, sau đó nhấn Enter ở đây để tiếp tục...")
        pickle.dump(driver.get_cookies(), open(COOKIE_FILE_PATH, "wb"))
        print("✅ Đã lưu cookie thành công.")

    # --- THAY ĐỔI: Quá trình quét dữ liệu từ Google Sheets ---
    print(f"\n✅ Bắt đầu quá trình lấy dữ liệu từ Google Sheets...")
    all_records = worksheet.get_all_records() # Lấy tất cả dữ liệu dưới dạng danh sách các dictionary
    headers = worksheet.row_values(1) # Lấy tên các cột tiêu đề
    
    # Lấy chỉ số (index) của các cột cần cập nhật
    full_name_col_index = headers.index(FULL_NAME_COLUMN_NAME) + 1
    pic_url_col_index = headers.index(PROFILE_PIC_URL_COLUMN) + 1

    # Dùng enumerate để lấy cả chỉ số hàng (bắt đầu từ 2 vì hàng 1 là tiêu đề)
    for row_index, row_data in enumerate(all_records, start=2):
        profile_url = row_data.get(URL_COLUMN_NAME)

        # Bỏ qua nếu đã có đủ thông tin
        if row_data.get(FULL_NAME_COLUMN_NAME) and row_data.get(PROFILE_PIC_URL_COLUMN):
            print(f"⏩ Bỏ qua hàng {row_index} vì đã có đủ thông tin.")
            continue

        if not profile_url or not profile_url.strip():
            print(f"⚠️ Bỏ qua hàng {row_index} vì không có URL.")
            continue

        print(f"\n⏳ Đang xử lý URL từ hàng {row_index}: {profile_url}")
        display_name, avatar_url = get_instagram_profile_data(driver, profile_url)

        updates_made = False
        # Cập nhật từng ô nếu có dữ liệu mới và ô hiện tại trống
        if display_name and not row_data.get(FULL_NAME_COLUMN_NAME):
            worksheet.update_cell(row_index, full_name_col_index, display_name)
            print(f"  -> Cập nhật Tên: {display_name}")
            updates_made = True

        if avatar_url and not row_data.get(PROFILE_PIC_URL_COLUMN):
            worksheet.update_cell(row_index, pic_url_col_index, avatar_url)
            print(f"  -> Cập nhật URL ảnh: {avatar_url}")
            updates_made = True

        if updates_made:
            print(f"✅ Cập nhật thành công hàng {row_index}.")
        else:
            print(f"❌ Không có thông tin mới để cập nhật cho URL: {profile_url}")
            
        time.sleep(5) # Giữ khoảng nghỉ để tránh bị block

finally:
    print("\n🎉 Hoàn thành! Đóng trình duyệt.")
    driver.quit()