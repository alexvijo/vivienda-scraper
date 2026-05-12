$root = $PSScriptRoot

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
  Set-Location '$root';
  .\.venv313\Scripts\Activate.ps1;
  Set-Location backend;
  py -3.13 -m uvicorn main:app --reload --port 8000
"

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
  Set-Location '$root\frontend';
  npm start
"
