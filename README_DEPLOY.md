# Hướng dẫn Deploy Bot Instagram lên Render.com

## 📋 Chuẩn bị trước khi deploy

### 1. Tạo Git Repository
```bash
git init
git add .
git commit -m "Initial commit"
```

Đẩy code lên GitHub, GitLab hoặc Bitbucket.

### 2. Chuẩn bị các file cần thiết
Đảm bảo bạn có:
- ✅ `credentials.json` (Google Service Account)
- ✅ File `.env` với đầy đủ biến môi trường
- ✅ `instagram_cookies.pkl` (nếu có)

## 🚀 Các bước deploy trên Render.com

### Bước 1: Tạo tài khoản Render
1. Truy cập [render.com](https://render.com)
2. Đăng ký/đăng nhập tài khoản
3. Kết nối với GitHub/GitLab

### Bước 2: Tạo Web Service mới
1. Click **"New"** → **"Web Service"**
2. Chọn repository chứa code bot
3. Cấu hình service:

#### ⚙️ Cấu hình cơ bản:
- **Name**: `instagram-telegram-bot` (hoặc tên bạn muốn)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python tele_bot.py`
- **Plan**: `Free` (hoặc trả phí nếu cần)

### Bước 3: Thiết lập Environment Variables
Trong phần **Environment**, thêm các biến sau:

#### 🔑 Telegram Configuration:
```
TELEGRAM_TOKEN = your_actual_telegram_bot_token
```

#### 📊 Google Sheets Configuration:
```
GOOGLE_SHEET_NAME = your_sheet_name
WORKSHEET_NAME = Profiles
GOOGLE_CREDENTIALS_FILE = credentials.json
```

#### 📝 Column Configuration:
```
RATING_COLUMN_NAME = Rating
FULL_NAME_COLUMN_NAME = full_name
PROFILE_PIC_URL_COLUMN_NAME = profile_pic_url
```

#### 📷 Instagram Configuration:
```
INSTAGRAM_COOKIE_FILE = instagram_cookies.pkl
```

#### ☁️ Cloudinary Configuration:
```
CLOUDINARY_CLOUD_NAME = your_cloudinary_cloud_name
CLOUDINARY_API_KEY = your_cloudinary_api_key
CLOUDINARY_API_SECRET = your_cloudinary_api_secret
```

### Bước 4: Upload các file nhạy cảm

#### 📄 Upload credentials.json:
1. Trong dashboard Render, vào **Environment**
2. Thêm **Secret File**:
   - **Name**: `credentials.json`
   - **Contents**: Copy nội dung file credentials.json của bạn

#### 🍪 Upload instagram_cookies.pkl (nếu có):
1. Encode file cookies thành base64:
   ```bash
   base64 instagram_cookies.pkl > cookies_base64.txt
   ```
2. Thêm environment variable:
   ```
   INSTAGRAM_COOKIES_BASE64 = nội_dung_file_base64
   ```

### Bước 5: Deploy
1. Click **"Create Web Service"**
2. Render sẽ tự động build và deploy
3. Theo dõi logs để kiểm tra

## 🔧 Xử lý sự cố thường gặp

### 1. Lỗi Chrome/Selenium:
- Render đã cài đặt Chrome tự động qua Dockerfile
- Nếu gặp lỗi, kiểm tra logs trong Render dashboard

### 2. Lỗi file credentials.json:
```python
# Thêm vào đầu tele_bot.py nếu cần:
import os
if not os.path.exists('credentials.json') and os.getenv('GOOGLE_CREDENTIALS_JSON'):
    with open('credentials.json', 'w') as f:
        f.write(os.getenv('GOOGLE_CREDENTIALS_JSON'))
```

### 3. Lỗi cookies:
```python
# Thêm vào code nếu có biến INSTAGRAM_COOKIES_BASE64:
import base64
if os.getenv('INSTAGRAM_COOKIES_BASE64') and not os.path.exists('instagram_cookies.pkl'):
    cookies_data = base64.b64decode(os.getenv('INSTAGRAM_COOKIES_BASE64'))
    with open('instagram_cookies.pkl', 'wb') as f:
        f.write(cookies_data)
```

## 📊 Kiểm tra Bot hoạt động

1. **Kiểm tra logs**: Trong Render dashboard → Logs
2. **Test bot**: Gửi `/start` cho bot trên Telegram
3. **Monitor**: Kiểm tra trạng thái service trong dashboard

## 💡 Lưu ý quan trọng

- **Free Plan**: Có giới hạn 750 giờ/tháng
- **Sleep Mode**: Free plan sẽ sleep sau 15 phút không hoạt động
- **Keep Alive**: Để bot luôn chạy, upgrade lên paid plan
- **Security**: Không bao giờ commit file `.env` hoặc `credentials.json` lên Git

## 🆘 Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra logs trong Render dashboard
2. Đảm bảo tất cả environment variables đã được set đúng
3. Kiểm tra format của file credentials.json
