@echo off
cd /d "%~dp0"
set STREAMLIT_EMAIL=
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_SERVER_HEADLESS=true
"C:\Users\mskolmakov\AppData\Local\Programs\Python\Python311\python.exe" -m streamlit run app.py --server.port 8503
pause
