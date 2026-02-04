#!/bin/bash

# ==========================================
# UPDATE BELL OTOMATIS (CLI VERSION)
# ==========================================

echo "=== MEMULAI UPDATE BELL OTOMATIS VIA CLI ==="

# 1. Cek Lokasi
if [ ! -f app.py ]; then
    echo "Error: app.py tidak ditemukan. Pastikan Anda menjalankan script ini di folder instalasi bell."
    exit 1
fi

# 2. Backup Database (Safety First)
echo "Step 1: Mencadangkan database..."
cp bell.db bell_backup_$(date +%Y%m%d_%H%M%S).db

# 3. Update Dependencies (Auto-Install Requirements)
echo "Step 2: Memeriksa dan menginstall dependensi..."
sudo apt update
sudo apt install -y python3 python3-pip sqlite3 mpg123 alsa-utils ffmpeg
pip3 install flask --break-system-packages 2>/dev/null || pip3 install flask

# 4. Download Update Baru
echo "Step 3: Mengunduh paket pembaruan v1.4.1..."
curl -L -o update_temp.zip "https://github.com/bijuri/Bell-otomatis/raw/main/release_v141/bell_update_v1.4.1.zip"

if [ $? -ne 0 ]; then
    echo "Gagal mengunduh update."
    exit 1
fi

# 5. Extract
echo "Step 4: Mengekstrak file..."
mkdir -p temp_extract
unzip -o update_temp.zip -d temp_extract/

# 6. Copy Files (Kecuali database)
echo "Step 5: Memperbarui script..."
cp -rv temp_extract/* . --exclude=bell.db

# 7. Cleanup
echo "Step 6: Membersihkan file sementara..."
rm update_temp.zip
rm -rf temp_extract/

# 8. Set Permissions (Fix Permission Issues)
echo "Step 7: Mengatur ulang izin akses folder dan database..."
PWD=$(pwd)
sudo chmod -R 777 "$PWD"
if id "www" >/dev/null 2>&1; then
    sudo chown -R www:www "$PWD"
    echo "Folder owner diubah ke user 'www'."
fi

# 9. Restart (Jika pakai systemd)
echo "Step 8: Mencoba merestart layanan (bell.service)..."
if systemctl is-active --quiet bell; then
    sudo systemctl restart bell
    echo "Service 'bell.service' berhasil direstart."
else
    echo "Info: Service 'bell.service' tidak aktif atau tidak ditemukan."
    echo "Mencoba restart manual jika app.py sedang berjalan..."
    pkill -f app.py
fi

echo ""
echo "=== UPDATE SELESAI ==="
echo "Versi Anda sekarang adalah v1.5.0"
