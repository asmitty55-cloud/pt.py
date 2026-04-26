# Research-Grade Plant Timelapse System

A robust Android timelapse system featuring custom APK-based capture, differential synchronization, and ArUco-tag-based growth analysis.

## 🚀 Key Features

- **Custom APK Capture**: Bypasses unreliable "Camera Intents" and OEM UI quirks using `ptcapture.apk` for 100% consistent behavior.
- **Aggressive Bypass Logic**: Uses ADB flags (`-g`, `-t`, `-d`, `-r`) and network kill-switches to prevent Play Protect interference and ensure automation stability.
- **ArUco Growth Analysis**: Integrated computer vision using `opencv-contrib-python` to detect 60mm x 60mm markers for precise scale and growth tracking.
- **Differential Sync**: Research-grade sync logic that pulls only new captures and maintains a reference file on-device to minimize data transfer.
- **Real-time Dashboard**: Flask-based UI with live ArUco detection overlays, telemetry panels (Markers Found, Scale px/mm), and automated video assembly.
- **Multi-Dictionary Support**: Robust marker detection checking `DICT_4X4_50`, `4X4_250`, `6X6_250`, and `APRILTAG_36h11`.

## 🛠️ Prerequisites

- **Python 3.8+**
- **ADB (Android Debug Bridge)**: Must be in your system PATH.
- **FFmpeg**: Required for automated timelapse video assembly.
- **Android Devices**: Android 6.0+ recommended.

## 📦 Installation

1. **Clone/Download** this repository to `C:\Program Files\pt`.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Ensure APK is present**: Place `ptcapture.apk` in the root directory.
4. **FFmpeg Setup**: Ensure `ffmpeg` is in your PATH or located in `C:\ffmpeg\bin\`.

## 🏃 Usage

1. **Start the System**:
   ```bash
   python main.py
   ```
2. **Access Dashboard**: Open `http://localhost:5000` in your browser.
3. **Connect Devices**: Plug in Android phones via USB with Developer Mode and USB Debugging enabled. The system will automatically detect, interrogate, and install the capture APK.

## 📊 Computer Vision (ArUco)

The system looks for ArUco markers (default 60mm x 60mm) to establish a spatial scale.
- **Data output**: Scale (px/mm) and marker centers are saved to `plant_stats.json`.
- **Debug View**: Check `http://localhost:5000/analysis_debug/<device_id>` to see the latest detection overlay.

## 📁 Project Structure

- `main.py`: Entry point and Flask server.
- `capture.py`: Low-level ADB/APK communication and "bulletproof" capture logic.
- `scripts/analysis.py`: OpenCV-based ArUco detection and scaling engine.
- `scripts/phone_interrogate.py`: Verification logic for new devices.
- `captures/`: Local storage for downloaded photos (organized by Device ID).
- `videos/`: Automatically assembled MP4 timelapse videos.

## 🔧 Robustness Features

- **Network Kill-Switch**: Disables WiFi/Data during capture/install to prevent Google Play Protect from blocking the custom APK.
- **Channel Correction**: Automatic grayscale/BGR conversion to prevent OpenCV "Bad number of channels" errors.
- **Path Fallback**: Uses `path_utils.py` to handle permission-restricted environments.

---
*Developed for research-grade botanical imaging and growth analysis.*
