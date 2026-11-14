@echo off
setlocal
cd /d "%~dp0"
echo Создание ярлыка WPT Coil Designer на Рабочем столе...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut([IO.Path]::Combine($desktop, 'WPT Coil Designer.lnk')); $s.TargetPath = [IO.Path]::Combine((Get-Location).Path, 'run.bat'); $s.WorkingDirectory = (Get-Location).Path; $s.IconLocation = [IO.Path]::Combine((Get-Location).Path, 'assets\icon.ico'); $s.Description = 'WPT Coil Designer & Analyzer'; $s.Save()"
echo.
echo [УСПЕХ] Фирменный ярлык с иконкой создан на вашем Рабочем столе!
echo Теперь вы можете запускать программу прямо с Рабочего стола.
echo.
timeout /t 3 >nul
