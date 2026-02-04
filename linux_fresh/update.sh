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

# 8. Restart (Jika pakai systemd)
echo "Step 7: Mencoba merestart layanan (jika ada)..."
sudo systemctl restart bell 2>/dev/null || echo "Info: Layanan systemd tidak ditemukan, silakan restart app.py secara manual."

echo ""
echo "=== UPDATE SELESAI ==="
echo "Versi Anda sekarang adalah v1.4.1"
