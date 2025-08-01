# File: generate_session.py
# Mục đích: Chạy file này MỘT LẦN DUY NHẤT trên máy tính của bạn để tạo file playwright_session.json
# Sau đó, tải file session này lên cùng thư mục với bot trên server hosting.

from playwright.sync_api import sync_playwright
import time
import os

SESSION_FILE = "playwright_session.json"

def run():
    with sync_playwright() as p:
        # Sử dụng trình duyệt Firefox để trông giống người dùng thật hơn
        browser = p.firefox.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

        print("🚀 Trình duyệt đã được mở.")
        print("Vui lòng đăng nhập vào tài khoản Instagram của bạn.")
        
        page.goto("https://www.instagram.com/accounts/login/")

        # Chờ người dùng đăng nhập thủ công
        # Script sẽ chờ cho đến khi bạn đăng nhập thành công và URL chuyển về trang chủ
        try:
            page.wait_for_url("https://www.instagram.com/", timeout=300000) # Chờ tối đa 5 phút
            print("✅ Đăng nhập thành công!")
            
            # Lưu lại trạng thái đăng nhập (cookies, local storage) vào file
            context.storage_state(path=SESSION_FILE)
            print(f"✅ Session đã được lưu vào file: {SESSION_FILE}")
            print("Bây giờ bạn có thể tải file này lên server hosting của mình.")

        except Exception as e:
            print(f"Đã có lỗi hoặc hết thời gian chờ. Lỗi: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    # Kiểm tra xem file session đã tồn tại chưa
    if os.path.exists(SESSION_FILE):
        overwrite = input(f"File '{SESSION_FILE}' đã tồn tại. Bạn có muốn ghi đè không? (y/n): ").lower()
        if overwrite == 'y':
            run()
        else:
            print("Đã hủy thao tác.")
    else:
        run()
