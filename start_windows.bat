@echo off
REM Start de Collectiekaart-mediabeheerder standalone op Windows.
REM Vereist: Python 3.10+ geinstalleerd (python.org, vink "Add to PATH" aan).

cd /d "%~dp0"

if not exist venv (
    echo Eerste keer opstarten: virtuele omgeving aanmaken en afhankelijkheden installeren...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Mediabeheerder start op http://localhost:8099
echo Open die link in je browser. Sluit dit venster om te stoppen.
echo.
python app.py
pause
