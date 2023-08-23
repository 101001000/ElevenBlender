@echo off
setlocal enabledelayedexpansion

:: First xcopy
xcopy /s /y "C:\Users\Kike\Desktop\TFM\repos\ElevenBlender\ElevenBlender\" "C:\Users\Kike\Desktop\blender-4.0.0-alpha+main.465810dd5251-windows.amd64-release\4.0\scripts\addons\ElevenBlender\"
if ERRORLEVEL 1 goto ErrorHandler

:: Second xcopy
xcopy /s /y "C:\Users\Kike\Desktop\TFM\repos\ElevenRender\build\bin\" "C:\Users\Kike\Desktop\blender-4.0.0-alpha+main.465810dd5251-windows.amd64-release\4.0\scripts\addons\ElevenBlender\bin\"
if ERRORLEVEL 1 goto ErrorHandler

:: Delete command
del "C:\Users\Kike\Desktop\blender-4.0.0-alpha+main.465810dd5251-windows.amd64-release\4.0\scripts\addons\ElevenBlender\__pycache__" /F /Q
if ERRORLEVEL 1 goto ErrorHandler

:: If we've made it this far, all commands were successful
echo|set /p="SUCCESS" <nul
color 0A
goto End

:ErrorHandler
echo|set /p="ERROR" <nul
color 0C
goto End

:End
pause