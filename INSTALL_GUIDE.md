# Installation & Distribution Guide

## For Personal Use

### Option 1: Simple Direct Run (Easiest)
```powershell
cd C:\Program Files\pt
pip install flask
python main.py
```

### Option 2: Package Installation (Recommended)
```powershell
cd C:\Program Files\pt
pip install -e .
plant-timelapse
```

### Option 3: Using Batch File (Automatic Admin)
Double-click `run.bat` - it will automatically request admin privileges and show a menu.

---

## For Distribution

### Preparing for Distribution

1. **Update version in setup.py and pyproject.toml**
   ```python
   version = "1.0.1"  # Change as needed
   ```

2. **Update author info**
   ```python
   authors = [{name = "Your Name"}]
   ```

3. **Ensure all dependencies are in requirements.txt**
   ```
   flask>=2.0.0
   ```

### Option A: PyPI Distribution (Public)

1. **Build the package**
   ```powershell
   pip install build twine
   python -m build
   ```

2. **Create PyPI account** at https://pypi.org/

3. **Upload to PyPI**
   ```powershell
   python -m twine upload dist/*
   ```

4. **Users can then install with**
   ```powershell
   pip install plant-timelapse
   plant-timelapse
   ```

### Option B: GitHub Distribution

1. **Initialize git repository**
   ```powershell
   cd C:\Program Files\pt
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/plant-timelapse.git
   git push -u origin main
   ```

2. **Create release on GitHub with built package**
   ```powershell
   python -m build
   # Upload dist/ files as release assets
   ```

3. **Users can install from GitHub**
   ```powershell
   pip install git+https://github.com/yourusername/plant-timelapse.git
   ```

### Option C: Standalone Executable (PyInstaller)

For non-Python users:

1. **Install PyInstaller**
   ```powershell
   pip install pyinstaller
   ```

2. **Build executable**
   ```powershell
   pyinstaller --onefile --name plant-timelapse --icon=icon.ico scripts/main.py
   ```

3. **Share the `dist/plant-timelapse.exe` file**

Users can run directly without Python installed!

---

## System Requirements

- Windows 10/11 or Linux/macOS
- Python 3.7+ (not needed if using PyInstaller executable)
- ADB (Android Debug Bridge) installed and in PATH
- At least 500MB free disk space for logs/photos

---

## Development Setup

### Clone for Development
```powershell
git clone https://github.com/yourusername/plant-timelapse.git
cd plant-timelapse
pip install -e .[dev]
```

### Running Tests
```powershell
pytest
```

### Code Formatting
```powershell
black scripts/
```
