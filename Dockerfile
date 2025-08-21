# Sử dụng Python 3.11 slim image (tương thích với python-telegram-bot)
FROM python:3.11.8-slim

# Cài đặt các dependencies hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . .

# Thiết lập biến môi trường cho Chrome
ENV DISPLAY=:99

# Expose port (nếu cần)
EXPOSE 8080

# Chạy bot
CMD ["python", "tele_bot.py"]
