@echo off
setlocal EnableDelayedExpansion

rem Desktop path from USERPROFILE
set "DESKTOP=%USERPROFILE%\Desktop"
set "LOG=%DESKTOP%\biobeamer_test_bat.log"

if not exist "%LOG%" (
    rem %DATE% and %TIME% are locale-dependent, but usually safe enough
    set "NOW=%DATE% %TIME%"
    rem Trim spaces at end of %TIME%
    set "NOW=!NOW: = !"
    >"%LOG%" echo !NOW!
    echo Created: "%LOG%"
) else (
    echo File already exists: "%LOG%"
)

endlocal
exit /b 0


