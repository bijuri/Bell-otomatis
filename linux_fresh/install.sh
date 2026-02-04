#!/bin/bash

# ==========================================
# INSTALL BELL OTOMATIS (FRESH INSTALL)
# ==========================================

echo "=== MEMULAI INSTALASI BELL OTOMATIS ==="

# 1. Update & Install Dependencies
echo "Step 1: Mengunduh dependensi sistem..."
sudo apt update
sudo apt install -y python3 python3-pip sqlite3 mpg123 alsa-utils ffmpeg

# 2. Install Flask
echo "Step 2: Menginstall library Python..."
pip3 install flask --break-system-packages 2>/dev/null || pip3 install flask

# 3. Setup Permissions
echo "Step 3: Mengatur hak akses..."
chmod +x play_bell.py
chmod +x app.py

# 4. Inisialisasi Database
echo "Step 4: Menyiapkan database..."
if [ ! -f bell.db ]; then
    python3 <<EOF
import sqlite3
import os
DB = "bell.db"
conn = sqlite3.connect(DB)
conn.execute("CREATE TABLE IF NOT EXISTS bell (id INTEGER PRIMARY KEY AUTOINCREMENT, jam TEXT, hari TEXT, suara TEXT, aktif INTEGER, profile_id INTEGER)")
conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, is_active INTEGER DEFAULT 0)")
conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('audio_output', 'hw:1,0')")
conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('time_offset', '0')")
conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ntp_server', 'pool.ntp.org')")
conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('timezone_region', 'Asia/Jakarta')")
conn.execute("INSERT INTO profiles (name, is_active) VALUES ('Default', 1)")
conn.commit()
conn.close()
EOF
    echo "Database bell.db berhasil dibuat."
else
    echo "Database bell.db sudah ada, melewati pembuatan."
fi

# 5. Setup Auto-start (Cron)
echo "Step 5: Mendaftarkan jadwal ke crontab..."
PWD=$(pwd)
(crontab -l 2>/dev/null | grep -v "play_bell.py" ; echo "* * * * * python3 $PWD/play_bell.py >> $PWD/bell.log 2>&1") | crontab -

# 6. Create Systemd Service (Linux only)
echo "Step 6: Mencoba membuat service systemd (bell.service)..."
if [ -d /etc/systemd/system ]; then
    CURRENT_USER=$(whoami)
    SERVICE_FILE="/etc/systemd/system/bell.service"
    
    sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Bell Otomatis Web Server
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$PWD
ExecStart=/usr/bin/python3 $PWD/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable bell
    sudo systemctl start bell
    echo "Service 'bell.service' berhasil dibuat dan dijalankan."
else
    echo "Systemd tidak ditemukan, melewati pembuatan service."
fi

# 7. Set Permissions (Fix Permission Issues for Service/www)
echo "Step 7: Mengatur izin akses folder dan database..."
sudo chmod -R 777 "$PWD"
if id "www" >/dev/null 2>&1; then
    sudo chown -R www:www "$PWD"
    echo "Folder owner diubah ke user 'www'."
fi

echo ""
echo "=== INSTALASI SELESAI ==="
echo "Versi: v1.5.0"
echo "Aplikasi sekarang berjalan sebagai service (systemd)."
echo "Gunakan 'sudo systemctl status bell' untuk cek status."
echo "----------------------------------------"
echo "Akses melalui browser di: http://localhost:5000"
