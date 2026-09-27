@echo off
setlocal
set "GARDSFAKTURA_FOLDER=%~dp0"
powershell.exe -NoProfile -Command "$folder=$env:GARDSFAKTURA_FOLDER; $desktop=[Environment]::GetFolderPath('Desktop'); $shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut((Join-Path $desktop 'Gardsfaktura.lnk')); $shortcut.TargetPath=Join-Path $folder 'Gardsfaktura.exe'; $shortcut.WorkingDirectory=$folder; $shortcut.Description='Offline fakturering'; $shortcut.Save()"
if errorlevel 1 (
    echo Kunne ikke opprette snarveien.
) else (
    echo Snarveien er opprettet paa skrivebordet.
)
pause
