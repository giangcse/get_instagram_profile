# File: generate_session.py
# Mục đích: Chạy file này MỘT LẦN DUY NHẤT trên máy tính của bạn để tạo file session.
# Sau đó, tải file session này lên cùng thư mục với bot trên server hosting.

import instaloader
import getpass
import os

try:
    # Tạo một instance của Instaloader
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )

    # Lấy username và password từ người dùng
    USER = input("Enter your Instagram username: ")
    PASSWORD = getpass.getpass("Enter your Instagram password (sẽ không hiển thị khi gõ): ")

    print(f"Logging in as {USER}...")
    L.login(USER, PASSWORD)
    print("✅ Đăng nhập thành công!")

    # Lưu session vào file. Tên file sẽ là username của bạn.
    # Ví dụ: nếu username là 'mybot', nó sẽ lưu một file tên là 'mybot'.
    session_filename = os.path.join(os.getcwd(), USER)
    L.save_session_to_file(session_filename)
    
    print(f"✅ Session đã được lưu vào file: {session_filename}")
    print("Bây giờ bạn có thể tải file này lên server hosting của mình.")
    print("Lưu ý: Tên file chính là username của bạn.")

except Exception as e:
    print(f"Đã có lỗi xảy ra: {e}")

