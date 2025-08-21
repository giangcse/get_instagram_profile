#!/bin/bash

# Cài đặt Google Chrome và ChromeDriver cho Selenium
echo "Cài đặt Google Chrome..."
apt-get update
apt-get install -y wget gnupg
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

# Cài đặt các dependencies khác
apt-get install -y xvfb

# Chạy bot Telegram
echo "Khởi động bot Telegram..."
python tele_bot.py
