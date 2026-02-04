# Bell-otomatis

## 📋 Deskripsi
Pembaruan besar ini menghadirkan fitur sinkronisasi waktu internet, manajemen profil mandiri, dan sistem pembaruan manual via dashboard.

## ✨ Fitur Baru
- **🌐 Sinkronisasi Waktu (NTP/GMT)**: Jam aplikasi sekarang bisa disinkronkan dengan server internet atau manual offset. Mendukung zona waktu WIB, WITA, dan WIT.
- **🎛️ Panel Pengaturan Mandiri**: Navigasi baru `/pengaturan` untuk memisahkan konfigurasi dari dashboard utama.
- **🗂️ Manajemen Profil**: Buat beberapa set jadwal (Normal, Ujian, Ramadhan) dan ganti secara cepat.
- **🆙 Manual Update**: Fitur unggah file ZIP langsung dari browser untuk update script tanpa menyentuh terminal.
- **🔊 Perbaikan Audio**: Pemilihan soundcard yang lebih stabil di Linux & Windows.



# 1. Update sistem dan instal unzip jika belum ada
sudo apt update && sudo apt install -y unzip curl
# 2. Buat folder untuk aplikasi
mkdir -p ~/bell && cd ~/bell
# 3. Download file ZIP rilis
curl -L -o bell_install.zip https://github.com/bijuri/Bell-otomatis/releases/download/v1.5.0/bell_fresh_install_v1.5.0.zip
# 4. Ekstrak file
unzip bell_install.zip
rm bell_install.zip
# 5. Jalankan script instalasi otomatis
# Script ini akan menginstal Python, Flask, dan membuat bell.service (systemd)
chmod +x install.sh
./install.sh
