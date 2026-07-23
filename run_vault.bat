@echo off
echo ===================================================
echo    Vault Secure - Auto Deployment System
echo ===================================================
echo.

echo [1/4] Cleaning up old database files...
if exist vault.db del vault.db
if exist credentials.db del credentials.db
if exist flask.db del flask.db

echo [2/4] Installing/Updating required libraries...
pip install flask flask-login werkzeug

echo [3/4] Starting the Server on your Network...
echo ---------------------------------------------------
echo SERVER IS STARTING...
echo ---------------------------------------------------
echo.
echo [IMPORTANT]
echo 1. Keep this window OPEN to keep the server running.
echo 2. Open your browser and go to: http://localhost:5000
echo 3. To access from other devices on your network,
echo    use your IP address (e.g., http://192.168.1.xx:5000)
echo ---------------------------------------------------
echo.

python app.py

pause
