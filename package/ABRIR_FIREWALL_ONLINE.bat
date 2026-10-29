@echo off
net session >nul 2>&1 || (echo Ejecuta como ADMINISTRADOR & pause & exit /b 1)
for %%P in (1223 1224 10025) do netsh advfirewall firewall add rule name="MH3U UDP %%P" dir=in action=allow protocol=UDP localport=%%P >nul
netsh advfirewall firewall add rule name="MH3U tools" dir=in action=allow program="%~dp0mh3u-tools.exe" enable=yes profile=any >nul
netsh advfirewall firewall add rule name="MH3U server" dir=in action=allow program="%~dp0server.exe" enable=yes profile=any >nul
echo Reglas de firewall creadas.
pause
