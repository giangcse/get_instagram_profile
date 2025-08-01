# File: scraper.py
# Module này chứa logic để cào dữ liệu từ Instagram bằng thư viện Instaloader
# và tải ảnh đại diện lên Cloudinary để có URL vĩnh viễn.

import instaloader
import logging
import time
import random
import re
import os
import requests
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# Tải các biến môi trường ngay khi module này được import
load_dotenv()

logger = logging.getLogger(__name__)

# --- CẤU HÌNH CLOUDINARY TỪ BIẾN MÔI TRƯỜNG ---
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# Tương thích với nhiều phiên bản Instaloader
try:
    from instaloader.exceptions import ProfileNotFoundException
except ImportError:
    try:
        from instaloader.exceptions import ProfileNotExistException as ProfileNotFoundException
    except ImportError:
        from instaloader.exceptions import ProfileNotExistsException as ProfileNotFoundException


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

def scrape_instagram_profiles(session_file_path: str, profiles_to_scrape: list):
    """
    Hàm chính để cào dữ liệu và tải ảnh lên Cloudinary.
    """
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        sleep=True,
        fatal_status_codes=[400, 401, 403, 429]
    )

    try:
        username_for_session = session_file_path.split('/')[-1].split('\\')[-1]
        logger.info(f"Đang tải session cho user '{username_for_session}' từ file: {session_file_path}")
        L.load_session_from_file(username_for_session, session_file_path)
        logger.info("✅ Tải session thành công.")
    except FileNotFoundError:
        logger.error(f"Không tìm thấy file session tại '{session_file_path}'. Hãy tạo và tải nó lên.")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi tải session: {e}")
        return None

    results = []
    for profile_info in profiles_to_scrape:
        url = profile_info.get('url')
        username_to_scrape = extract_username(url)

        if not username_to_scrape:
            logger.warning(f"Bỏ qua URL không hợp lệ: {url}")
            continue

        try:
            logger.info(f"Đang cào dữ liệu cho: {username_to_scrape}")
            profile = instaloader.Profile.from_username(L.context, username_to_scrape)
            
            original_pic_url = profile.profile_pic_url
            
            logger.info(f"Đang tải ảnh đại diện của {username_to_scrape} lên Cloudinary...")
            cloudinary_pic_url = upload_image_to_cloudinary(original_pic_url, username_to_scrape)
            
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': profile.full_name or profile.username,
                'profile_pic_url': cloudinary_pic_url or original_pic_url,
            })
            
            sleep_time = random.uniform(5.0, 10.0)
            logger.debug(f"Nghỉ {sleep_time:.2f} giây...")
            time.sleep(sleep_time)

        # SỬA LỖI: Xử lý lỗi session hết hạn hoặc không hợp lệ
        except instaloader.exceptions.LoginRequiredException:
            logger.error("LỖI NGHIÊM TRỌNG: Session không hợp lệ hoặc đã hết hạn. Instagram yêu cầu đăng nhập lại.")
            # Dừng toàn bộ quá trình và trả về None để bot biết và thông báo cho người dùng
            return None
            
        except instaloader.exceptions.TooManyRequestsException:
            logger.error(f"Bị giới hạn tốc độ (rate-limited) khi cào dữ liệu cho {username_to_scrape}. Bỏ qua profile này.")
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': "Rate Limited",
                'profile_pic_url': "",
            })
            continue

        except ProfileNotFoundException:
            logger.warning(f"Profile không tồn tại: {username_to_scrape}")
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': "Not Found",
                'profile_pic_url': "",
            })
        except Exception as e:
            logger.error(f"Lỗi không xác định khi cào dữ liệu cho {username_to_scrape}: {e}")
            continue
            
    return results
