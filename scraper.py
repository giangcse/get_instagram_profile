# File: scraper.py
# Module này chứa logic để cào dữ liệu từ Instagram bằng thư viện Instaloader.

import instaloader
import logging
import time
import random
import re

logger = logging.getLogger(__name__)

def extract_username(url: str) -> str | None:
    """Trích xuất username từ URL Instagram."""
    if not url: return None
    match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_](?:(?:[A-Za-z0-9_]|\.(?!\.))*[A-Za-z0-9_]){0,29})", url)
    return match.group(1) if match else None

def scrape_instagram_profiles(session_file_path: str, profiles_to_scrape: list):
    """
    Hàm chính để cào dữ liệu cho một danh sách các hồ sơ bằng Instaloader.
    Hàm này chạy đồng bộ (synchronous) nhưng hiệu quả và ổn định.
    """
    L = instaloader.Instaloader(
        # Cấu hình để chỉ tải metadata, không tải ảnh/video để tăng tốc độ
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    try:
        # Tên session file chính là username đã dùng để đăng nhập
        username_for_session = session_file_path.split('/')[-1].split('\\')[-1]
        logger.info(f"Đang tải session cho user '{username_for_session}' từ file: {session_file_path}")
        L.load_session_from_file(username_for_session, session_file_path)
        logger.info("✅ Tải session thành công.")
    except FileNotFoundError:
        logger.error(f"Không tìm thấy file session tại '{session_file_path}'. Hãy tạo và tải nó lên bằng script generate_session.py.")
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
            # Lấy đối tượng Profile từ username
            profile = instaloader.Profile.from_username(L.context, username_to_scrape)
            
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': profile.full_name or profile.username,
                'profile_pic_url': profile.profile_pic_url,
            })
            
            # Thêm một khoảng nghỉ ngẫu nhiên để tránh bị block
            sleep_time = random.uniform(2.5, 5.0)
            logger.debug(f"Nghỉ {sleep_time:.2f} giây...")
            time.sleep(sleep_time)

        except instaloader.exceptions.ProfileNotExist:
            logger.warning(f"Profile không tồn tại: {username_to_scrape}")
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': "Not Found",
                'profile_pic_url': "Not Found",
            })
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            logger.warning(f"Profile là tài khoản riêng tư và không được theo dõi: {username_to_scrape}")
            results.append({
                'row_index': profile_info['row_index'],
                'full_name': "Private Account",
                'profile_pic_url': "Private Account",
            })
        except Exception as e:
            logger.error(f"Lỗi không xác định khi cào dữ liệu cho {username_to_scrape}: {e}")
            continue # Bỏ qua profile này và tiếp tục với cái tiếp theo
            
    return results
