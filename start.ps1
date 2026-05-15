$pythonPath = "C:\Users\mskolmakov\AppData\Local\Programs\Python\Python311\python.exe"
$appPath = Join-Path $PSScriptRoot "app.py"
$env:STREAMLIT_EMAIL = ""
& $pythonPath -m streamlit run $appPath --server.port 8503
