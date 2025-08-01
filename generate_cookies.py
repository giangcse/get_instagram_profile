# File: generate_cookies.py
# Mục đích: Chạy file này MỘT LẦN DUY NHẤT trên máy tính của bạn để tạo file instagram_cookies.pkl
# Sau đó, tải file .pkl này lên cùng thư mục với bot trên server hosting.

import time
import pickle
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE_PATH = "instagram_cookies.pkl"

print("🚀 Khởi tạo trình duyệt Selenium...")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

try:
    print("Vui lòng đăng nhập vào Instagram trên trình duyệt vừa mở.")
    driver.get("https://www.instagram.com/accounts/login/")
    
    # Chờ người dùng đăng nhập thủ công
    input(">>> Sau khi đã đăng nhập thành công, nhấn phím Enter ở đây để tiếp tục...")
    
    # Lấy và lưu cookies
    cookies = driver.get_cookies()
    pickle.dump(cookies, open(COOKIE_FILE_PATH, "wb"))
    
    print(f"✅ Đã lưu cookie thành công vào file '{COOKIE_FILE_PATH}'.")
    print("Bây giờ bạn có thể tải file này lên server hosting của mình.")

finally:
    driver.quit()

