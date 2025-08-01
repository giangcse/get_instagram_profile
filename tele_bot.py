# File: scraper.py
# Module này chứa logic để cào dữ liệu từ Instagram bằng Selenium (chế độ headless)
# và tải ảnh đại diện lên Cloudinary để có URL vĩnh viễn.

import logging
import time
import random
import re
import os
import pickle
import requests
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# SỬA LỖI: Gỡ bỏ hoàn toàn webdriver-manager
# from webdriver_manager.chrome import ChromeDriverManager

# Tải các biến môi trường ngay khi module này được import
load_dotenv()

logger = logging.getLogger(__name__)

# --- CẤU HÌNH CLOUDINARY TỪ BIẾN MÔI TRƯỜDNG ---
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

def extract_username(url: str) -> str | None:
    """Trích xuất username từ URL Instagram."""
    if not url: return None
    match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_](?:(?:[A-Za-z0-9_]|\.(?!\.))*[A-Za-z0-9_]){0,29})", url)
    return match.group(1) if match else None

def upload_image_to_cloudinary(image_url: str, public_id: str):
    """
    Tải ảnh từ một URL và đẩy lên Cloudinary.
    """
    if not image_url:
        return None
    try:
        response = requests.get(image_url, stream=True, timeout=20)
        response.raise_for_status()
        
        upload_result = cloudinary.uploader.upload(
            response.raw,
            public_id=f"instagram_profiles/{public_id}",
            overwrite=True,
            resource_type="image"
        )
        return upload_result.get('secure_url')
    except Exception as e:
        logger.error(f"Lỗi khi tải ảnh lên Cloudinary cho {public_id}: {e}")
        return None

def scrape_instagram_profiles(cookie_file_path: str, profiles_to_scrape: list):
    """
    Hàm chính để cào dữ liệu bằng Selenium và tải ảnh lên Cloudinary.
    """
    if not os.path.exists(cookie_file_path):
        logger.error(f"Không tìm thấy file cookie tại '{cookie_file_path}'. Hãy tạo và tải nó lên.")
        return None

    # --- Cấu hình Selenium để chạy ở chế độ headless ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # SỬA LỖI: Trỏ trực tiếp đến chromedriver đã cài đặt trên hệ thống Raspberry Pi
    chromedriver_path = "/usr/bin/chromedriver"
    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    
    # Tải cookie để đăng nhập
    driver.get("https://www.instagram.com/")
    cookies = pickle.load(open(cookie_file_path, "rb"))
    for cookie in cookies:
        driver.add_cookie(cookie)
    
    logger.info("✅ Trình duyệt Selenium (headless) đã khởi động và tải cookie thành công.")

    results = []
    try:
        for profile_info in profiles_to_scrape:
            url = profile_info.get('url')
            username_to_scrape = extract_username(url)

            if not username_to_scrape:
                logger.warning(f"Bỏ qua URL không hợp lệ: {url}")
                continue

            try:
                logger.info(f"Đang cào dữ liệu cho: {username_to_scrape}")
                driver.get(f"https://www.instagram.com/{username_to_scrape}/")
                
                wait = WebDriverWait(driver, 15)

                # 1. Lấy ảnh đại diện
                original_pic_url = None
                try:
                    img_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'header img')))
                    original_pic_url = img_element.get_attribute('src')
                except Exception as img_error:
                    logger.warning(f"Không thể lấy ảnh cho {username_to_scrape}. Lỗi: {img_error}")

                # 2. Lấy tên đầy đủ từ thẻ <title> của trang
                full_name = username_to_scrape
                try:
                    wait.until(EC.title_contains(f"@{username_to_scrape}"))
                    page_title = driver.title
                    match = re.search(r'^(.*?)\s+\(@', page_title)
                    if match:
                        extracted_name = match.group(1).strip()
                        if extracted_name:
                            full_name = extracted_name
                except Exception as title_error:
                    logger.warning(f"Không thể lấy tên từ title cho {username_to_scrape}, sử dụng username thay thế. Lỗi: {title_error}")

                # 3. Tải ảnh lên Cloudinary
                logger.info(f"Đang tải ảnh đại diện của {username_to_scrape} lên Cloudinary...")
                cloudinary_pic_url = upload_image_to_cloudinary(original_pic_url, username_to_scrape)
                
                results.append({
                    'row_index': profile_info['row_index'],
                    'full_name': full_name.strip() or username_to_scrape,
                    'profile_pic_url': cloudinary_pic_url or original_pic_url or "",
                })
                
                sleep_time = random.uniform(3.0, 6.0)
                logger.debug(f"Nghỉ {sleep_time:.2f} giây...")
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Lỗi không xác định khi cào dữ liệu cho {username_to_scrape}: {e}")
                if "Sorry, this page isn't available" in driver.page_source:
                     results.append({'row_index': profile_info['row_index'], 'full_name': "Not Found", 'profile_pic_url': ""})
                else:
                    results.append({'row_index': profile_info['row_index'], 'full_name': "Scrape Error", 'profile_pic_url': ""})
    
    finally:
        driver.quit()
            
    return results
