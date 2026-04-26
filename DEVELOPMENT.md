# Development Guide

## Project Structure

```
plant-timelapse/
├── main.py                      # Entry point
├── run.bat                      # Windows launcher with admin support
├── setup.py                     # Package configuration (setuptools)
├── pyproject.toml               # Modern package config (PEP 517/518)
├── requirements.txt             # Dependencies
├── README.md                    # User documentation
├── INSTALL_GUIDE.md             # Installation instructions
├── DEVELOPMENT.md               # This file
├── LICENSE                      # MIT License
├── .gitignore                   # Git ignore patterns
├── scripts/                     # Main package
│   ├── __init__.py              # Package marker
│   ├── __main__.py              # Module entry point (python -m scripts)
│   ├── main.py                  # Core application (Flask app, ADB commands)
│   ├── phone_logger.py          # Device logging system
│   └── phone_interrogate.py     # Phone detection & profile discovery
├── captures/                    # Downloaded photos (device_id/timestamp.ext)
└── debug/                       # Logs and configuration
    ├── profiles.json            # Device profiles (auto-generated)
    └── <device_id>.txt          # Per-device logs (rotated)
```

## Module Overview

### `scripts/main.py`
- **Purpose**: Core Flask web server and ADB command orchestration
- **Key Functions**:
  - `run_app()`: Application entry point
  - `detect_connected_devices()`: Lists ADB-connected phones
  - `interrogate_phone()`: Discovers phone's camera folder
  - `capture_image()`: Takes photo and downloads it
  - `pull_missed_photos()`: Recovers photos from previous runs
  - `timelapse_loop()`: Background thread for periodic captures
- **Routes**:
  - `GET /`: Dashboard UI
  - `GET /interrogate/<device_id>`: Profile discovery
  - `GET /capture/<device_id>`: Manual capture
  - `GET /timelapse/start`: Begin timed captures
  - `GET /timelapse/stop`: Stop timed captures

### `scripts/phone_logger.py`
- **Purpose**: Per-device logging with rotation
- **Features**:
  - Logs to `debug/<device_id>.txt`
  - Auto-rotates at 1MB (keeps 3 archived files)
  - Preserves `profiles.json` during rotation
- **Key Methods**:
  - `log()`: Write timestamped log entry
  - `log_error_with_adb_output()`: Log errors with ADB output

### `scripts/phone_interrogate.py`
- **Purpose**: Automatically detect phone camera settings
- **Key Functions**:
  - `interrogate_phone(device_id)`: Main discovery process
  - `find_newest_file()`: Locate newest photo on device
  - `list_candidate_paths()`: Possible camera paths to check
- **Detects**:
  - Camera save folder path
  - File extension (.jpg, .png, etc)
  - Camera shutter delay
  - Storage location (internal vs SD card)

## Development Workflow

### Setup Dev Environment
```powershell
git clone <repo>
cd plant-timelapse
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .[dev]
pip install -r requirements.txt
```

### Running Locally
```powershell
python main.py
# Visit http://localhost:5000
```

### Code Style
- Follow PEP 8
- Use meaningful variable names
- Add docstrings to functions
- Format with Black: `black scripts/`

## Adding Features

### Adding a New Route
1. Add function in `scripts/main.py` with `@app.route()` decorator
2. Use existing functions like `run_adb()`, `detect_connected_devices()`
3. Return JSON with `jsonify()`

Example:
```python
@app.route("/status/<device_id>")
def get_device_status(device_id):
    if device_id not in phone_profiles:
        return jsonify({"error": "Unknown device"}), 404
    
    profile = phone_profiles[device_id]
    last_photo = last_capture.get(device_id, "Never")
    
    return jsonify({
        "device_id": device_id,
        "profile": profile,
        "last_capture": last_photo
    })
```

### Adding Logging
```python
from scripts.phone_logger import PhoneLogger

logger = PhoneLogger(device_id)
logger.log("Starting operation", major=True)  # Includes timestamp
logger.log("Details", major=False)             # No timestamp
logger.log_error_with_adb_output("Failed", out, err)  # With ADB output
```

### Extending Phone Interrogation
Edit `scripts/phone_interrogate.py`:
1. Add to `list_candidate_paths()` for more folder detection
2. Add detectors in `interrogate_phone()` for new attributes
3. Save to `profile` dict

## Testing

Create `tests/test_system.py`:
```python
import pytest
from scripts.phone_interrogate import list_candidate_paths

def test_candidate_paths():
    paths = list_candidate_paths()
    assert len(paths) > 0
    assert "/storage/emulated/0/DCIM/Camera" in paths
```

Run tests:
```powershell
pytest tests/
```

## Common Tasks

### Update Dependencies
```powershell
pip freeze > requirements.txt
pip install -U -r requirements.txt
```

### Bump Version
1. Edit `setup.py`: `version = "1.0.1"`
2. Edit `pyproject.toml`: `version = "1.0.1"`
3. Commit: `git tag v1.0.1`

### Build for Distribution
```powershell
pip install build
python -m build
# Creates dist/plant_timelapse-1.0.0-py3-none-any.whl
# and dist/plant_timelapse-1.0.0.tar.gz
```

### Create Standalone Executable
```powershell
pip install pyinstaller
pyinstaller --onefile --name plant-timelapse scripts/main.py
# Creates dist/plant-timelapse.exe
```

## Troubleshooting Development

**Module not found**: Ensure you're using `from scripts.xxx` imports when inside package

**Logging errors**: Check `debug/` folder has write permissions

**ADB issues**: Verify `adb devices` lists phones from command line

**Profile not saving**: Ensure `debug/` folder exists and is writable

## Performance Considerations

- Photo pulls are serial to avoid ADB conflicts
- Timelapse uses a background daemon thread
- Log rotation prevents unbounded disk usage
- Profile JSON is small and cached in memory

## Security Notes

- ADB commands are passed as lists (no shell injection)
- Input validation on device_id (used in filenames)
- No credentials stored (ADB is local)
- Flask runs on localhost only (not network accessible)

## License

MIT - See LICENSE file
