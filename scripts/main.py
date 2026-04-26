import os
import time
import threading
import subprocess
import json
import shutil
from flask import Flask, render_template_string, jsonify, request, send_from_directory

from scripts.phone_interrogate import interrogate_phone
from scripts.phone_logger import PhoneLogger
from scripts.path_utils import get_data_root, get_captures_dir
import capture
from scripts.analysis import process_latest_captures


# Get paths
DATA_ROOT = get_data_root()
CAPTURES_DIR = get_captures_dir()
VIDEOS_DIR = os.path.join(DATA_ROOT, "videos")
DEBUG_DIR = os.path.join(DATA_ROOT, "debug")
profiles_file = os.path.join(DEBUG_DIR, "profiles.json")

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

app = Flask(__name__)

# Global state
phone_profiles = {}
last_capture = {}
timelapse_running = True # Auto-start
timelapse_interval = 120
interrogation_in_progress = set()

def load_profiles():
    global phone_profiles
    if os.path.exists(profiles_file):
        try:
            with open(profiles_file, 'r') as f:
                phone_profiles = json.load(f)
        except:
            phone_profiles = {}

def save_profiles():
    os.makedirs(os.path.dirname(profiles_file), exist_ok=True)
    with open(profiles_file, 'w') as f:
        json.dump(phone_profiles, f, indent=4)

def run_adb(cmd):
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, err = proc.communicate()
        return out.strip(), err.strip()
    except FileNotFoundError:
        return "", "adb-not-found"

def detect_connected_devices():
    out, err = run_adb(["adb", "devices"])
    if err == "adb-not-found":
        return []
    lines = out.split("\n")[1:]
    devices = []
    for line in lines:
        if "\tdevice" in line:
            devices.append(line.split("\t")[0])
    return devices


def ensure_device_profile(device_id):
    if device_id in phone_profiles:
        return phone_profiles[device_id]

    if device_id in interrogation_in_progress:
        return None

    interrogation_in_progress.add(device_id)
    try:
        profile = interrogate_phone(device_id)
        if profile and profile.get("save_folder"):
            capture.install_apk(device_id)
            phone_profiles[device_id] = profile
            save_profiles()
            return profile
        return profile
    finally:
        interrogation_in_progress.discard(device_id)


def ensure_all_device_profiles(devices):
    for device_id in devices:
        ensure_device_profile(device_id)


def sync_device(device_id, logger):
    """
    Research-grade sync logic:
    1. If new device (no local folder): Full backup, then clear device except last.
    2. If existing: Differential sync (pull new), then clear device except last.
    """
    remote_dir = "/sdcard/PTCaptures"
    local_device_dir = os.path.join(CAPTURES_DIR, device_id)
    is_new = not os.path.exists(local_device_dir) or not os.listdir(local_device_dir)
    os.makedirs(local_device_dir, exist_ok=True)

    # Ensure remote directory exists
    run_adb(["adb", "-s", device_id, "shell", f"mkdir -p {remote_dir}"])

    # Get list of files on device
    out, err = run_adb(["adb", "-s", device_id, "shell", f"ls {remote_dir}"])

    remote_files = sorted([f.strip() for f in out.split("\n") if f.strip() and f.endswith(".jpg")])
    if not remote_files:
        logger.log("No files found on device to sync.", major=False)
        return

    if is_new:
        # Scenario 1: New Device - Full Backup to 'backup' subfolder
        logger.log(f"New device {device_id} detected. Starting full backup of {len(remote_files)} files.", major=True)
        backup_dir = os.path.join(local_device_dir, "backup")
        os.makedirs(backup_dir, exist_ok=True)

        for f in remote_files:
            remote_path = f"{remote_dir}/{f}"
            local_path = os.path.join(backup_dir, f)
            run_adb(["adb", "-s", device_id, "pull", remote_path, local_path])

        # After backup, also copy the latest to the main folder so it acts as the reference for differential sync
        latest_file = remote_files[-1]
        shutil.copy2(os.path.join(backup_dir, latest_file), os.path.join(local_device_dir, latest_file))
        logger.log(f"Initial sync complete. Backup in {backup_dir}.", major=True)
    else:
        # Scenario 2: Existing Device - Differential Sync
        local_files = sorted([f for f in os.listdir(local_device_dir) if f.endswith(".jpg")])
        last_local = local_files[-1] if local_files else ""

        to_pull = [f for f in remote_files if f > last_local]
        if to_pull:
            logger.log(f"Differential sync: {len(to_pull)} new files found for {device_id}.", major=True)
            for f in to_pull:
                remote_path = f"{remote_dir}/{f}"
                local_path = os.path.join(local_device_dir, f)
                run_adb(["adb", "-s", device_id, "pull", remote_path, local_path])
        else:
            logger.log(f"No new files for {device_id}.", major=False)

    # Final Step: Clean device except the very last reference file
    latest_file = remote_files[-1]
    for f in remote_files[:-1]:
        run_adb(["adb", "-s", device_id, "shell", f"rm \"{remote_dir}/{f}\""])
    
    logger.log(f"Sync finished for {device_id}. Reference file {latest_file} remains on device.", major=False)


def capture_and_sync(device_id):
    ensure_device_profile(device_id)
    logger = PhoneLogger(device_id)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{timestamp}.jpg"

    logger.log(f"Triggering capture: {filename}", major=True)
    if capture.capture_on_device(device_id, filename):
        sync_device(device_id, logger)
        last_capture[device_id] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Run plant analysis
        try:
            process_latest_captures(CAPTURES_DIR)
        except Exception as e:
            print(f"[ANALYSIS] Error: {e}")

        assemble_video(device_id)
        return True
    return False

def get_ffmpeg():
    # Attempt to find ffmpeg in common locations
    candidates = [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\pt\bin\ffmpeg.exe"
    ]
    for c in candidates:
        try:
            subprocess.run([c, "-version"], capture_output=True)
            return c
        except: continue
    return None

def assemble_video(device_id):
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        print(f"[VIDEO] FFmpeg not found. Cannot assemble video for {device_id}.")
        return

    device_dir = os.path.join(CAPTURES_DIR, device_id)
    if not os.path.exists(device_dir): return

    images = sorted([f for f in os.listdir(device_dir) if f.endswith(".jpg")])
    if len(images) < 2: return

    list_file = os.path.join(device_dir, "file_list.txt")
    with open(list_file, "w") as f:
        for img in images:
            # Use absolute paths and escape single quotes
            img_path = os.path.abspath(os.path.join(device_dir, img)).replace("'", "'\\''")
            f.write(f"file '{img_path}'\n")
            f.write("duration 0.1\n")
        # Repeat last frame for a moment or just end it
        if images:
            img_path = os.path.abspath(os.path.join(device_dir, images[-1])).replace("'", "'\\''")
            f.write(f"file '{img_path}'\n")

    output_file = os.path.join(VIDEOS_DIR, f"{device_id}.mp4")
    # ffmpeg concat demuxer command
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", output_file]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"[VIDEO] Updated timelapse video for {device_id}")
    except subprocess.CalledProcessError as e:
        print(f"[VIDEO] FFmpeg error: {e.stderr.decode()}")

def timelapse_loop():
    print("[TIMELAPSE] Starting background loop...")
    while True:
        if timelapse_running:
            devices = detect_connected_devices()
            ensure_all_device_profiles(devices)
            for d in devices:
                try:
                    capture_and_sync(d)
                except Exception as e:
                    print(f"Error on device {d}: {e}")
        time.sleep(timelapse_interval)

@app.route("/")
def dashboard():
    devices = detect_connected_devices()
    ensure_all_device_profiles(devices)
    # Load debug logs for each device
    logs = {}
    for d in devices:
        log_path = os.path.join(DEBUG_DIR, f"{d}.txt")
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                # Get last 10 lines
                logs[d] = "".join(f.readlines()[-10:])
        else:
            logs[d] = "No logs yet."

    return render_template_string(DASHBOARD_HTML, devices=devices, last=last_capture, running=timelapse_running, logs=logs)

@app.route("/video/<device_id>")
def serve_video(device_id):
    return send_from_directory(VIDEOS_DIR, f"{device_id}.mp4")

@app.route("/stats")
def get_stats():
    stats_file = os.path.join(DATA_ROOT, "plant_stats.json")
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({})

@app.route("/analysis_debug/<device_id>")
def serve_analysis_debug(device_id):
    debug_dir = os.path.join(DATA_ROOT, "analysis_debug")
    device_dir = os.path.join(CAPTURES_DIR, device_id)
    if not os.path.exists(device_dir): return "Not found", 404
    files = sorted([f for f in os.listdir(device_dir) if f.endswith(".jpg")])
    if not files: return "No images", 404
    return send_from_directory(debug_dir, files[-1])

@app.route("/last_frame/<device_id>")
def serve_last_frame(device_id):
    device_dir = os.path.join(CAPTURES_DIR, device_id)
    if not os.path.exists(device_dir): return "Not found", 404
    files = sorted([f for f in os.listdir(device_dir) if f.endswith(".jpg")])
    if not files: return "No images", 404
    return send_from_directory(device_dir, files[-1])

@app.route("/capture/<device_id>")
def manual_capture(device_id):
    if capture_and_sync(device_id): return "OK"
    return "Failed", 500

@app.route("/interrogate/<device_id>")
def run_interrogate(device_id):
    profile = interrogate_phone(device_id)
    if profile and profile.get("save_folder"):
        capture.install_apk(device_id)
        phone_profiles[device_id] = profile
        save_profiles()
        return jsonify(profile)
    return "Failed", 500

@app.route("/timelapse/stop")
def stop_timelapse():
    global timelapse_running
    timelapse_running = False
    return "Stopped"

@app.route("/timelapse/start")
def start_timelapse():
    global timelapse_running
    if not timelapse_running:
        timelapse_running = True
    return "Started"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Plant Timelapse Research Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 20px; margin: 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 25px; }
        .card { background: #151515; border-radius: 12px; padding: 20px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); display: flex; flex-direction: column; }
        video, img { width: 100%; border-radius: 8px; background: #000; margin-top: 10px; border: 1px solid #222; }
        canvas { width: 100% !important; height: 150px !important; margin-top: 10px; }
        .controls { margin-top: 20px; display: flex; gap: 12px; }
        button { flex: 1; padding: 14px; cursor: pointer; background: #252525; color: white; border: 1px solid #444; border-radius: 6px; font-weight: bold; transition: 0.2s; }
        button:hover { background: #353535; border-color: #666; }
        .status-bar { margin-bottom: 30px; padding: 15px 25px; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; background: #1a1a1a; border: 1px solid #333; }
        .running { color: #74c69d; }
        .stopped { color: #ffb3c1; }
        h1 { margin: 0; font-size: 1.8em; }
        h3 { margin-top: 0; color: #fff; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .label { font-size: 0.75em; color: #666; text-transform: uppercase; margin-top: 15px; letter-spacing: 1px; font-weight: bold; }
        .fastest-badge { background: #f39c12; color: #000; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; margin-left: 10px; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; } 100% { opacity: 0.8; } }
    </style>
</head>
<body>
    <div class="status-bar">
        <h1>Plant Timelapse <span style="color:#4facfe">Research</span></h1>
        <div style="display: flex; gap: 20px; align-items: center;">
            <div class="{{ 'running' if running else 'stopped' }}">
                 ● SYSTEM {{ 'RUNNING' if running else 'STOPPED' }}
            </div>
            <button onclick="fetch('/timelapse/start').then(()=>location.reload())" style="padding: 8px 15px;">START</button>
            <button onclick="fetch('/timelapse/stop').then(()=>location.reload())" style="padding: 8px 15px;">STOP</button>
        </div>
    </div>

    <div class="grid">
        {% for d in devices %}
        <div class="card">
            <h3 id="title-{{ d }}">{{ d }}</h3>
            <p>Last Sync: <span class="timestamp">{{ last.get(d, 'Initializing...') }}</span></p>

            <div class="label">Timelapse Loop</div>
            <video id="vid-{{d}}" controls loop autoplay muted>
                <source src="/video/{{d}}" type="video/mp4">
            </video>

            <div class="controls">
                <button onclick="fetch('/capture/{{d}}').then(()=>location.reload())">Force Capture</button>
                <button onclick="document.getElementById('analysis-{{d}}').src='/last_frame/{{d}}?t='+Date.now()">Refresh Frame</button>
            </div>

            <div class="label">Realtime Frame (ArUco Detection)</div>
            <img id="analysis-{{d}}" src="/analysis_debug/{{d}}"
                 onload="this.style.display='block'"
                 onerror="this.onerror=null; this.src='/last_frame/{{d}}'">

            <div class="label">Plant Statistics & Growth Trend</div>
            <div id="stats-{{d}}" style="font-family: monospace; font-size: 0.9em; background: #000; padding: 10px; border-radius: 4px; border: 1px solid #333; margin-bottom: 10px;">
                Loading telemetry...
            </div>
            <canvas id="chart-{{d}}" style="height: 150px; background: #111; border-radius: 4px;"></canvas>

            <div class="label">System Debug Log</div>
            <div class="debug-log" id="log-{{d}}" style="font-family: monospace; font-size: 0.8em; background: #000; padding: 10px; border-radius: 4px; border: 1px solid #333; height: 100px; overflow-y: auto; white-space: pre-wrap; margin-top: 5px;">{{ logs[d] }}</div>
        </div>
        {% endfor %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const charts = {};

        function updateStats() {
            fetch('/stats').then(r => {
                if (!r.ok) throw new Error("Stats fetch failed");
                return r.json();
            }).then(stats => {
                if (!stats || Object.keys(stats).length === 0) return;

                for (const [id, info] of Object.entries(stats)) {
                    const cardTitle = document.querySelector(`.card h3#title-${id}`);
                    if (cardTitle && info.is_fastest) {
                        if (!cardTitle.innerHTML.includes('FASTEST')) {
                            cardTitle.innerHTML += ' <span class="fastest-badge">🔥 FASTEST GROWER</span>';
                        }
                    }

                    const el = document.getElementById('stats-' + id);
                    if (el && info.data) {
                        const data = info.data;
                        const area = (data.plant_area_mm2 !== undefined && data.plant_area_mm2 !== null)
                                     ? data.plant_area_mm2.toFixed(1) + ' mm²'
                                     : '0.0 mm²';
                        const rate = info.growth_rate_mm2_hr ? info.growth_rate_mm2_hr.toFixed(2) + ' mm²/hr' : '0.00 mm²/hr';
                        el.innerHTML = `
                            Markers Found: ${data.markers_found || 0}<br>
                            Scale: ${data.scale_px_per_mm ? data.scale_px_per_mm.toFixed(2) + ' px/mm' : 'N/A'}<br>
                            Plant Area: ${area}<br>
                            Growth Rate: ${rate}<br>
                            Last Update: ${info.timestamp || 'Never'}
                        `;
                    }

                    // Update Chart
                    if (info.history && info.history.length > 0) {
                        const ctx = document.getElementById('chart-' + id);
                        if (ctx) {
                            // Only plot points that have valid area data
                            const validHistory = info.history.filter(h =>
                                h.area !== undefined && h.area !== null && h.area > 0
                            );

                            if (validHistory.length === 0) continue;

                            const labels = validHistory.map(h => h.timestamp ? h.timestamp.split(' ')[1] : '');
                            const values = validHistory.map(h => h.area);

                            if (!charts[id]) {
                                charts[id] = new Chart(ctx, {
                                    type: 'line',
                                    data: {
                                        labels: labels,
                                        datasets: [{
                                            label: 'Area (mm²)',
                                            data: values,
                                            borderColor: '#74c69d',
                                            backgroundColor: 'rgba(116, 198, 157, 0.1)',
                                            fill: true,
                                            tension: 0.3,
                                            pointRadius: 2
                                        }]
                                    },
                                    options: {
                                        responsive: true,
                                        maintainAspectRatio: false,
                                        animation: false,
                                        plugins: { legend: { display: false } },
                                        scales: {
                                            y: { grid: { color: '#222' }, ticks: { color: '#666' } },
                                            x: { grid: { display: false }, ticks: { color: '#666' } }
                                        }
                                    }
                                });
                            } else {
                                charts[id].data.labels = labels;
                                charts[id].data.datasets[0].data = values;
                                charts[id].update('none');
                            }
                        }
                    }
                }
            }).catch(e => console.error("Update Stats Error:", e));
        }

        setInterval(() => {
            document.querySelectorAll('img').forEach(img => {
                const base = img.src.split('?')[0];
                img.src = base + '?t=' + Date.now();
            });
            document.querySelectorAll('video').forEach(v => { if(v.paused) v.play().catch(()=>{}); });
            updateStats();
        }, 15000);
        updateStats();
    </script>
</body>
</html>
"""

def run_app():
    load_profiles()
    # Start the timelapse thread immediately
    t = threading.Thread(target=timelapse_loop, daemon=True)
    t.start()
    print("[SERVER] Starting Flask on port 5000...")
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    run_app()
