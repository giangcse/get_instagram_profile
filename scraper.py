# File: scraper.py
# Module này chứa logic để cào dữ liệu từ Instagram bằng Playwright
# và tải ảnh đại diện lên Cloudinary để có URL vĩnh viễn.

import logging
import time
import random
import re
import os
import requests
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

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

async def scrape_instagram_profiles(session_file_path: str, profiles_to_scrape: list):
    """
    Hàm chính để cào dữ liệu bằng Playwright và tải ảnh lên Cloudinary.
    """
    if not os.path.exists(session_file_path):
        logger.error(f"Không tìm thấy file session tại '{session_file_path}'. Hãy tạo và tải nó lên.")
        return None

    results = []
    async with async_playwright() as p:
        # Chạy trình duyệt ở chế độ headless (không có giao diện) trên server
        browser = await p.firefox.launch()
        context = await browser.new_context(storage_state=session_file_path)

        for profile_info in profiles_to_scrape:
            url = profile_info.get('url')
            username_to_scrape = extract_username(url)

            if not username_to_scrape:
                logger.warning(f"Bỏ qua URL không hợp lệ: {url}")
                continue

            page = await context.new_page()
            try:
                logger.info(f"Đang cào dữ liệu cho: {username_to_scrape}")
                await page.goto(f"https://www.instagram.com/{username_to_scrape}/", timeout=60000)
                
                # Chờ cho đến khi phần header của trang được tải
                await page.wait_for_selector('header', timeout=20000)

                # Lấy ảnh đại diện
                img_selector = 'header img'
                await page.wait_for_selector(img_selector, timeout=10000)
                original_pic_url = await page.locator(img_selector).get_attribute('src')

                # SỬA LỖI: Logic lấy tên đầy đủ được cải tiến để ổn định hơn
                full_name = username_to_scrape # Mặc định là username
                try:
                    # Selector này tìm tất cả các thẻ span có thuộc tính dir="auto" trong header
                    full_name_selector = 'header span[dir="auto"]'
                    await page.wait_for_selector(full_name_selector, timeout=10000)
                    
                    all_spans = await page.locator(full_name_selector).all()
                    
                    # Duyệt qua các thẻ span tìm được để lọc ra tên thật
                    for span_element in all_spans:
                        text = (await span_element.text_content() or "").strip()
                        
                        # Tên thật thường không phải là các nút hành động, số, hoặc các chuỗi ngắn
                        if text and len(text) > 1 and not text.isnumeric() and text.lower() not in ["follow", "message", "following", "followers", "posts"]:
                            full_name = text
                            break # Dừng lại ngay khi tìm thấy tên hợp lệ đầu tiên
                            
                except Exception as name_error:
                    logger.warning(f"Không tìm thấy tên đầy đủ cho {username_to_scrape}, sử dụng username thay thế. Lỗi: {name_error}")
                    full_name = username_to_scrape

                logger.info(f"Đang tải ảnh đại diện của {username_to_scrape} lên Cloudinary...")
                cloudinary_pic_url = upload_image_to_cloudinary(original_pic_url, username_to_scrape)
                
                results.append({
                    'row_index': profile_info['row_index'],
                    'full_name': full_name.strip() or username_to_scrape,
                    'profile_pic_url': cloudinary_pic_url or original_pic_url,
                })
                
                sleep_time = random.uniform(3.0, 6.0)
                logger.debug(f"Nghỉ {sleep_time:.2f} giây...")
                await page.wait_for_timeout(sleep_time * 1000)

            except Exception as e:
                logger.error(f"Lỗi không xác định khi cào dữ liệu cho {username_to_scrape}: {e}")
                page_content = await page.content()
                if "Sorry, this page isn't available" in page_content:
                     results.append({'row_index': profile_info['row_index'], 'full_name': "Not Found", 'profile_pic_url': ""})
                else:
                    results.append({'row_index': profile_info['row_index'], 'full_name': "Scrape Error", 'profile_pic_url': ""})
                
            finally:
                await page.close()
        
        await browser.close()
            
    return results
