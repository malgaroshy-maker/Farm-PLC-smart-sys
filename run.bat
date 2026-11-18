@echo off
REM Starts the full simulation stack. Config comes from the repo-root .env
REM (copy .env.example to .env first). Requires apps\api\.venv with requirements installed.
echo Starting Farm-PLC Services...

if not exist .env (
  echo [!] No .env found - copy .env.example to .env and set ADMIN_PASSWORD, SECRET_KEY, SIMULATOR_TOKEN.
  pause
  exit /b 1
)

echo [0/3] Migrating database and seeding (safe to re-run)...
pushd apps\api
call .venv\Scripts\python.exe -m alembic upgrade head || (popd & echo Migration failed & pause & exit /b 1)
call .venv\Scripts\python.exe -m app.seed
popd

echo [1/3] Starting API Backend...
start "Farm-PLC API" cmd /k "cd apps\api & .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo [2/3] Starting Simulator Engine...
start "Farm-PLC Simulator" cmd /k "cd apps\simulator & ..\api\.venv\Scripts\python.exe -m src.main"

echo [3/3] Starting Web Frontend...
start "Farm-PLC Web Frontend" cmd /k "pnpm --filter @algaroshy/web run dev"

echo All services launched. Open http://localhost:5173
