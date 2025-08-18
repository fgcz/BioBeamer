@echo off
setlocal enabledelayedexpansion

REM Check if a folder was dropped on the batch file
if "%~1"=="" (
    echo No folder provided. Please drag and drop a folder onto this batch file.
    pause
    exit /b 1
)

REM Get the dropped folder path
set "folder_path=%~1"

REM Remove quotes if present
set "folder_path=%folder_path:"=%"

REM Check if the path exists and is a directory
if not exist "%folder_path%" (
    echo Error: Path does not exist: %folder_path%
    pause
    exit /b 1
)

if not exist "%folder_path%\*" (
    echo Error: Path is not a directory: %folder_path%
    pause
    exit /b 1
)

echo Folder to process: %folder_path%
echo.

REM Prompt for username
set /p "username=Enter username (default: analytics): "

REM If no username entered, use default
if "!username!"=="" set "username=analytics"

echo Using username: !username!
echo.

REM Call the Python script with the provided parameters
python zip_and_copy.py "%folder_path%" --username "!username!" --no-prompt

REM Check if Python script was successful
if %errorlevel% neq 0 (
    echo.
    echo Python script failed with error code: %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo Batch file completed successfully.
pause
