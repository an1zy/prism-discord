@echo off
chcp 65001 >nul
title PRISM - Discord Bot Management & Control Suite
cls
python prism.py
if errorlevel 1 (
    echo.
    echo [ERROR] Execution failed or Python not found.
    pause
)
