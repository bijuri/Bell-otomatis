#!/usr/bin/env python3
import os
import sqlite3
import subprocess
import time
import zipfile
import shutil
import signal
from flask import Flask, render_template, request, redirect, session, url_for, flash

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "bell.db")
SOUND_DIR = os.path.join(BASE_DIR, "static/sounds")

# Windows support
IS_WINDOWS = os.name == 'nt'
AUDIO_HW = "hw:1,0" if not IS_WINDOWS else None
LOGIN_PIN = "1996"
AUTO_LOGOUT = 300  # 5 menit (detik)

# ================= AUDIO HELPER =================


def play_sound_file(path):
    if not os.path.isfile(path):
        return False

    audio_output = get_setting('audio_output', 'hw:1,0')

    try:
        if IS_WINDOWS:
            # On Windows, use PowerShell for a reliable way to play both WAV and MP3
            # We use System.Windows.Media.MediaPlayer which is available since .NET 3.0
            # Note: Changing output device on Windows via PowerShell MediaPlayer is complex
            # For now we'll stick to default, but we'll store the setting for Linux/Advanced use
            cmd = [
                "powershell", "-c",
                f"$m = New-Object System.Windows.Media.MediaPlayer; "
                f"$m.Open('{path}'); "
                f"$m.Play(); "
                f"Start-Sleep -s 1"  # Give it a moment to start
            ]
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(
                subprocess, 'CREATE_NO_WINDOW') else 0)
        else:
            # Linux logic uses the setting
            if path.lower().endswith(".wav"):
                subprocess.Popen(["aplay", "-D", audio_output, path])
            else:
                subprocess.Popen(["mpg123", "-a", audio_output, path])
        return True
    except Exception as e:
        print(f"Error playing sound: {e}")
        return False


# ================= APP =================
app = Flask(__name__)
app.secret_key = "bell-secret"

# ================= DB HELPER =================


def get_db():
    conn = sqlite3.connect(
        DB,
        timeout=10,
        check_same_thread=False
    )
    # Ensure settings table exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('audio_output', 'hw:1,0')")
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('time_offset', '0')")
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('ntp_server', 'pool.ntp.org')")
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('timezone_region', 'Asia/Jakarta')")

    # Profiles Table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, is_active INTEGER DEFAULT 0)")

    # Ensure at least one profile exists
    if not conn.execute("SELECT id FROM profiles").fetchone():
        conn.execute(
            "INSERT INTO profiles (name, is_active) VALUES ('Default', 1)")

    # Migration for bell table (add profile_id)
    try:
        conn.execute("ALTER TABLE bell ADD COLUMN profile_id INTEGER")
        # Assign existing bells to the default profile
        default_id = conn.execute(
            "SELECT id FROM profiles WHERE name='Default'").fetchone()[0]
        conn.execute("UPDATE bell SET profile_id=?", (default_id,))
    except sqlite3.OperationalError:
        # Column already exists
        pass

    conn.commit()
    return conn


def get_active_profile():
    conn = get_db()
    row = conn.execute(
        "SELECT id, name FROM profiles WHERE is_active=1").fetchone()
    conn.close()
    return row if row else (1, "Default")


def get_profiles():
    conn = get_db()
    rows = conn.execute("SELECT id, name, is_active FROM profiles").fetchall()
    conn.close()
    return rows


def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def get_audio_devices():
    devices = []
    try:
        if IS_WINDOWS:
            # Get output devices via PowerShell
            # We filter out generic names and clean up the output
            cmd = ["powershell", "-NoProfile",
                   "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name"]
            output = subprocess.check_output(cmd, text=True).splitlines()
            devices = [d.strip() for d in output if d.strip()]
        else:
            # Linux: parse aplay -L
            # Usually lines starting with 'hw:' are the physical devices
            cmd = ["aplay", "-L"]
            output = subprocess.check_output(
                cmd, text=True, stderr=subprocess.DEVNULL).splitlines()
            for line in output:
                line = line.strip()
                if line and not line.startswith(" ") and (line.startswith("hw:") or line.startswith("plughw:")):
                    devices.append(line)
    except Exception as e:
        print(f"Device discovery error: {e}")

    return sorted(list(set(devices)))

# ================= SESSION TIMEOUT =================


def check_timeout():
    if "login" not in session:
        return True

    now = time.time()
    last = session.get("last_active", now)

    if now - last > AUTO_LOGOUT:
        session.clear()
        return True

    session["last_active"] = now
    return False

# ================= LOGIN =================


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin")

        if pin == LOGIN_PIN:
            session["login"] = True
            session["last_active"] = time.time()
            return redirect(url_for("index"))

        return render_template("login.html", error="PIN salah")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= HOME =================


@app.route("/")
def index():
    if check_timeout():
        return redirect(url_for("login"))

    active_profile = get_active_profile()
    conn = get_db()
    data = conn.execute(
        "SELECT * FROM bell WHERE profile_id=? ORDER BY jam",
        (active_profile[0],)
    ).fetchall()
    conn.close()

    sounds = []
    if os.path.isdir(SOUND_DIR):
        sounds = sorted(
            f for f in os.listdir(SOUND_DIR)
            if f.lower().endswith((".wav", ".mp3"))
        )

    return render_template(
        "index.html",
        data=data,
        sounds=sounds,
        auto_logout=AUTO_LOGOUT,
        audio_output=get_setting('audio_output', 'hw:1,0'),
        devices=get_audio_devices(),
        active_profile=active_profile,
        profiles=get_profiles(),
        time_offset=int(get_setting('time_offset', '0'))
    )

# ================= ADD BELL =================


@app.route("/add", methods=["POST"])
def add():
    if check_timeout():
        return redirect(url_for("login"))

    jam = request.form.get("jam")
    hari = ",".join(request.form.getlist("hari[]"))
    suara = request.form.get("suara")
    profile_id = get_active_profile()[0]

    conn = get_db()
    conn.execute(
        "INSERT INTO bell (jam,hari,suara,aktif,profile_id) VALUES (?,?,?,1,?)",
        (jam, hari, suara, profile_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

# ================= TEST SOUND =================


@app.route("/test/<filename>")
def test_sound(filename):
    if check_timeout():
        return redirect(url_for("login"))

    path = os.path.join(SOUND_DIR, filename)
    if not play_sound_file(path):
        return "Gagal memutar suara atau file tidak ditemukan", 404

    return redirect(url_for("index"))

# ================= CEK SOUND PAGE =================


@app.route("/ceksound")
def cek_sound():
    if check_timeout():
        return redirect(url_for("login"))

    sounds = []
    if os.path.isdir(SOUND_DIR):
        sounds = sorted(
            f for f in os.listdir(SOUND_DIR)
            if f.lower().endswith((".wav", ".mp3"))
        )

    return render_template("ceksound.html", sounds=sounds)


# ================= CHANGELOG =================


@app.route("/changelog")
def changelog():
    if check_timeout():
        return redirect(url_for("login"))

    return render_template("changelog.html")

# ================= TOGGLE =================


@app.route("/toggle/<int:id>")
def toggle(id):
    if check_timeout():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "UPDATE bell SET aktif = CASE aktif WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
        (id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

# ================= DELETE BELL =================


@app.route("/delete/<int:id>")
def delete(id):
    if check_timeout():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM bell WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

# ================= EDIT SOUND =================


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if check_timeout():
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        jam = request.form.get("jam")
        hari = ",".join(request.form.getlist("hari[]"))
        suara = request.form.get("suara")
        conn.execute(
            "UPDATE bell SET jam=?, hari=?, suara=? WHERE id=?",
            (jam, hari, suara, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    data = conn.execute(
        "SELECT * FROM bell WHERE id=?",
        (id,)
    ).fetchone()
    conn.close()

    sounds = sorted(os.listdir(SOUND_DIR))
    return render_template("edit.html", data=data, sounds=sounds)

# ================= EDIT JAM =================


@app.route("/edit_jam/<int:id>", methods=["POST"])
def edit_jam(id):
    if check_timeout():
        return redirect(url_for("login"))

    jam = request.form.get("jam")

    conn = get_db()
    conn.execute(
        "UPDATE bell SET jam=? WHERE id=?",
        (jam, id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

# ================= UPLOAD SOUND =================


@app.route("/upload", methods=["POST"])
def upload():
    if check_timeout():
        return redirect(url_for("login"))

    f = request.files.get("sound")
    if f:
        os.makedirs(SOUND_DIR, exist_ok=True)
        f.save(os.path.join(SOUND_DIR, f.filename))

    return redirect(url_for("index"))

# ================= DELETE SOUND =================


@app.route("/delete_sound", methods=["POST"])
def delete_sound():
    if check_timeout():
        return redirect(url_for("login"))

    fn = request.form.get("filename")
    path = os.path.join(SOUND_DIR, fn)

    if os.path.isfile(path):
        os.remove(path)

    return redirect(url_for("index"))

# ================= EDIT HARI =================


@app.route("/edit_hari/<int:id>", methods=["POST"])
def edit_hari(id):
    if check_timeout():
        return redirect(url_for("login"))

    hari_list = request.form.getlist("hari[]")
    hari = ",".join(hari_list)

    conn = get_db()
    conn.execute(
        "UPDATE bell SET hari=? WHERE id=?",
        (hari, id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ================= PENGATURAN PAGE =================


@app.route("/pengaturan")
def pengaturan_page():
    if check_timeout():
        return redirect(url_for("login"))

    return render_template(
        "pengaturan.html",
        active_profile=get_active_profile(),
        profiles=get_profiles(),
        audio_output=get_setting('audio_output', 'hw:1,0'),
        time_offset=int(get_setting('time_offset', '0')),
        ntp_server=get_setting('ntp_server', 'pool.ntp.org'),
        timezone_region=get_setting('timezone_region', 'Asia/Jakarta'),
        devices=get_audio_devices()
    )


# ================= SETTINGS =================


@app.route("/update_audio", methods=["POST"])
def update_audio():
    if check_timeout():
        return redirect(url_for("login"))

    audio_output = request.form.get("audio_output", "hw:1,0")
    conn = get_db()
    conn.execute(
        "UPDATE settings SET value=? WHERE key='audio_output'", (audio_output,))
    conn.commit()
    conn.close()
    return redirect(url_for("pengaturan_page"))


@app.route("/update_time", methods=["POST"])
def update_time():
    if check_timeout():
        return redirect(url_for("login"))

    time_offset = request.form.get("time_offset", "0")
    ntp_server = request.form.get("ntp_server", "pool.ntp.org")
    timezone_region = request.form.get("timezone_region", "Asia/Jakarta")

    conn = get_db()
    conn.execute(
        "UPDATE settings SET value=? WHERE key='time_offset'", (time_offset,))
    conn.execute(
        "UPDATE settings SET value=? WHERE key='ntp_server'", (ntp_server,))
    conn.execute(
        "UPDATE settings SET value=? WHERE key='timezone_region'", (timezone_region,))
    conn.commit()
    conn.close()
    return redirect(url_for("pengaturan_page"))


@app.route("/sync_time")
def sync_time():
    if check_timeout():
        return redirect(url_for("login"))

    import json
    import socket
    import struct
    from urllib.request import urlopen, Request

    ntp_server = get_setting('ntp_server', 'pool.ntp.org')
    timezone_region = get_setting('timezone_region', 'Asia/Jakarta')

    def get_ntp_time(host):
        try:
            addr = (host, 123)
            msg = b'\x1b' + 47 * b'\0'
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2)
            client.sendto(msg, addr)
            msg, _ = client.recvfrom(1024)
            t = struct.unpack("!12I", msg)[10]
            return t - 2208988800
        except:
            return None

    remote_time = None

    # Try NTP first
    if ntp_server:
        remote_time = get_ntp_time(ntp_server)

    # Fallback to WorldTimeAPI if NTP fails or not set
    if remote_time is None:
        try:
            url = f"http://worldtimeapi.org/api/timezone/{timezone_region}"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                remote_time = data['unixtime']
        except Exception as e:
            print(f"Sync error (API): {e}")

    if remote_time is not None:
        local_time = int(time.time())
        offset = int(remote_time - local_time)

        conn = get_db()
        conn.execute(
            "UPDATE settings SET value=? WHERE key='time_offset'", (str(offset),))
        conn.commit()
        conn.close()

    return redirect(url_for("pengaturan_page"))


# ================= PROFILES =================


@app.route("/add_profile", methods=["POST"])
def add_profile():
    if check_timeout():
        return redirect(url_for("login"))

    name = request.form.get("profile_name")
    if name:
        conn = get_db()
        conn.execute(
            "INSERT INTO profiles (name, is_active) VALUES (?, 0)", (name,))
        conn.commit()
        conn.close()

    return redirect(url_for("pengaturan_page"))


@app.route("/switch_profile/<int:id>")
def switch_profile(id):
    if check_timeout():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("UPDATE profiles SET is_active=0")
    conn.execute("UPDATE profiles SET is_active=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("pengaturan_page"))


@app.route("/delete_profile/<int:id>")
def delete_profile(id):
    if check_timeout():
        return redirect(url_for("login"))

    conn = get_db()
    # Don't delete the active profile if it's the last one
    profile = conn.execute(
        "SELECT is_active FROM profiles WHERE id=?", (id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    if count > 1:
        if profile and profile[0] == 1:
            # If deleting active, switch to another first
            another = conn.execute(
                "SELECT id FROM profiles WHERE id!=?", (id,)).fetchone()
            conn.execute(
                "UPDATE profiles SET is_active=1 WHERE id=?", (another[0],))

        conn.execute("DELETE FROM profiles WHERE id=?", (id,))
        # Also delete bells associated with this profile
        conn.execute("DELETE FROM bell WHERE profile_id=?", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for("pengaturan_page"))


@app.route("/update_system", methods=["POST"])
def update_system():
    if check_timeout():
        return redirect(url_for("login"))

    file = request.files.get('update_zip')
    if not file or not file.filename.endswith('.zip'):
        return "File tidak valid", 400

    update_path = os.path.join(BASE_DIR, "temp_update.zip")
    extract_path = os.path.join(BASE_DIR, "temp_extract")

    try:
        file.save(update_path)

        # Clear old extract path if exists
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path)

        # Extract
        with zipfile.ZipFile(update_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # Move files to base dir (excluding database to prevent data loss)
        for root, dirs, files in os.walk(extract_path):
            for filename in files:
                if filename == 'bell.db':
                    continue  # Protect existing database

                rel_path = os.path.relpath(
                    os.path.join(root, filename), extract_path)
                dest_path = os.path.join(BASE_DIR, rel_path)

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(os.path.join(root, filename), dest_path)

        # Cleanup
        shutil.rmtree(extract_path)
        os.remove(update_path)

        # Self-restart logic
        def restart():
            time.sleep(2)
            os.kill(os.getpid(), signal.SIGTERM)

        import threading
        threading.Thread(target=restart).start()

        return "Update Berhasil! Sistem sedang restart..."

    except Exception as e:
        return f"Update Gagal: {e}", 500


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
