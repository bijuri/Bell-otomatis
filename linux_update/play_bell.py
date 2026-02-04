#!/usr/bin/env python3
import sqlite3
import datetime
import os
import subprocess
import sys
import time

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "bell.db")
SOUND_DIR = os.path.join(BASE_DIR, "static/sounds")

# OS detection
IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    LOCK_DIR = os.path.join(BASE_DIR, "locks")
    LOG_FILE = os.path.join(BASE_DIR, "bell.log")
else:
    LOCK_DIR = "/tmp/bell_lock"
    LOG_FILE = "/tmp/bell.log"
    AUDIO_HW = "hw:1,0"

# ================= INIT =================
os.makedirs(LOCK_DIR, exist_ok=True)

# waktu sekarang (will be adjusted by offset once DB is ready)


def get_effective_now(offset=0):
    return datetime.datetime.now() + datetime.timedelta(seconds=offset)

# ================= LOGGING =================


def log(msg):
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
        print(f"[{ts}] {msg}")
    except Exception as e:
        print(f"LOG ERROR: {e}", file=sys.stderr)


# Script started

# ================= DB HELPER =================


def get_setting(cursor, key, default=None):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

# ================= AUDIO HELPER =================


def play_sound(path, audio_output):
    if not os.path.isfile(path):
        log(f"File not found: {path}")
        return False

    try:
        if IS_WINDOWS:
            cmd = [
                "powershell", "-c",
                f"$m = New-Object System.Windows.Media.MediaPlayer; "
                f"$m.Open('{path}'); "
                f"$m.Play(); "
                f"while($m.Position -lt $m.NaturalDuration.TimeSpan) {{ Start-Sleep -ms 100 }}"
            ]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(
                subprocess, 'CREATE_NO_WINDOW') else 0)
        else:
            if path.lower().endswith(".wav"):
                subprocess.Popen(["aplay", "-D", audio_output, path])
            else:
                subprocess.Popen(["mpg123", "-a", audio_output, path])
        return True
    except Exception as e:
        log(f"Error playing sound: {e}")
        return False


# ================= DB =================
try:
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Fetch settings
    audio_output = get_setting(cursor, 'audio_output', 'hw:1,0')
    time_offset = int(get_setting(cursor, 'time_offset', '0'))

    # Calculate effective time after getting offset
    now = get_effective_now(time_offset)
    jam = now.strftime("%H:%M")
    hari_en = now.strftime("%A")
    menit_id = now.strftime("%Y%m%d_%H%M")

    log(f"Effective time: {hari_en} {jam} (offset: {time_offset}s)")

    cursor.execute("""
        SELECT b.id, b.hari, b.suara
        FROM bell b
        JOIN profiles p ON b.profile_id = p.id
        WHERE b.jam=? AND b.aktif=1 AND p.is_active=1
    """, (jam,))
    rows = cursor.fetchall()
    conn.close()
except Exception as e:
    log(f"DB error: {e}")
    rows = []
    audio_output = 'hw:1,0'
    # Fallback to system time if DB fails
    now = datetime.datetime.now()
    jam = now.strftime("%H:%M")
    hari_en = now.strftime("%A")
    menit_id = now.strftime("%Y%m%d_%H%M")

if not rows:
    log("No bells scheduled for this time.")
    exit(0)

# ================= PLAY =================
for bell_id, hari_db, suara in rows:
    # cek hari
    if hari_en not in hari_db.split(","):
        log(f"Bell {bell_id} skipped (hari {hari_en} not in {hari_db})")
        continue

    lock_file = os.path.join(LOCK_DIR, f"bell_{bell_id}_{menit_id}.lock")

    # skip jika sudah bunyi
    if os.path.exists(lock_file):
        log(f"Bell {bell_id} already played this minute.")
        continue

    # buat lock
    try:
        with open(lock_file, "w") as f:
            f.write("played")
    except Exception as e:
        log(f"Cannot create lock file: {e}")
        continue

    sound_path = os.path.join(SOUND_DIR, suara)
    log(f"Playing sound {sound_path} using {audio_output}")
    play_sound(sound_path, audio_output)
