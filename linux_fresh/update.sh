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

# 3. Download Update Baru
echo "Step 2: Mengunduh paket pembaruan..."
UPDATE_URL="https://github.com/bijuri/Bell-otomatis/releases/download/v1.3.0/bell_update_v1.3.0.zip"
# Note: Jika menggunakan URL ZIP rilis GitHub, bisa disesuaikan nanti.
# Untuk demo, kita asumsikan file zip tersedia di repo.

curl -L -o update_temp.zip "https://github.com/bijuri/Bell-otomatis/releases/download/v1.3.0/bell_update_v1.3.0.zip"

if [ $? -ne 0 ]; then
    echo "Gagal mengunduh update."
    exit 1
fi

# 4. Extract
echo "Step 3: Mengekstrak file..."
mkdir -p temp_extract
unzip -o update_temp.zip -d temp_extract/

# 5. Copy Files (Kecuali database)
echo "Step 4: Memperbarui script..."
cp -rv temp_extract/* . --exclude=bell.db

# 6. Cleanup
echo "Step 5: Membersihkan file sementara..."
rm update_temp.zip
rm -rf temp_extract/

# 7. Restart (Jika pakai systemd)
echo "Step 6: Mencoba merestart layanan (jika ada)..."
sudo systemctl restart bell.service 2>/dev/null || echo "Info: Layanan systemd tidak ditemukan, silakan restart app.py secara manual."

echo ""
echo "=== UPDATE SELESAI ==="
echo "Versi Anda sekarang adalah v1.3.0"
