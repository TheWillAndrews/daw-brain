@echo off
rem DAW Brain - Windows launcher (dev mode)
rem Lives at <repo>\launcher\ and starts the Electron app from ..\desktop,
rem so the repo can live anywhere.

cd /d "%~dp0..\desktop"

if not exist node_modules (
  echo First run: installing dependencies...
  call npm install
  if errorlevel 1 (
    echo.
    echo npm install failed. Is Node.js installed and on PATH?
    pause
    exit /b 1
  )
)

call npm start
if errorlevel 1 pause
