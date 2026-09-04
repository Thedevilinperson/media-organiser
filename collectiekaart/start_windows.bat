@echo off
REM Start Collectiekaart op Windows.
REM Nodig: Python 3.10 of nieuwer, met "Add python.exe to PATH" aangevinkt.

cd /d "%~dp0"

if not exist venv (
    echo Eerste start: omgeving klaarzetten. Dit duurt een minuutje.
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Collectiekaart draait op http://localhost:8099
echo Open die link in je browser. Sluit dit venster om te stoppen.
echo.
python app.py
pause
