# Build OdooManager.exe  ->  dist\OdooManager.exe
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -3 -m venv .venv
    & $py -m pip install PySide6 psutil psycopg2-binary pyinstaller cryptography
}
# make the .ico from the same drawn icon the app uses
& $py -c "import os;os.environ['QT_QPA_PLATFORM']='offscreen';from PySide6.QtWidgets import QApplication;a=QApplication([]);from odoo_manager.theme import app_icon;app_icon().pixmap(256,256).save('icon.ico')"
& $py -m PyInstaller --noconfirm --onefile --windowed --name OdooManager --icon icon.ico `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQuick --exclude-module PySide6.Qt3DCore `
    app.py
