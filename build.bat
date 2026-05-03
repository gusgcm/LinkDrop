@echo off
echo [BUILD] Limpando ambiente e instalando versoes compativeis com XP...

:: Forçar a remoção de pacotes instalados incorretamente
C:\Python34\python.exe -m pip uninstall -y pywin32-ctypes pefile altgraph pyinstaller Pillow

:: Instalar dependências em versões específicas para Python 3.4
C:\Python34\python.exe -m pip install --no-cache-dir pyperclip==1.8.2
C:\Python34\python.exe -m pip install --no-cache-dir plyer==2.1.0
C:\Python34\python.exe -m pip install --no-cache-dir altgraph==0.16.1
C:\Python34\python.exe -m pip install --no-cache-dir pywin32-ctypes==0.2.0
C:\Python34\python.exe -m pip install --no-cache-dir pefile==2019.4.18
C:\Python34\python.exe -m pip install --no-cache-dir pyinstaller==3.3

echo.
echo [BUILD] Iniciando compilacao...
:: Se o Pillow falhar, o código linkdrop_server.py ignora e funciona sem ele.
C:\Python34\Scripts\pyinstaller.exe --onefile --windowed --name "LinkDrop" --icon "linkdrop.ico" linkdrop_server.py

echo.
echo Build finalizado. Verifique a pasta 'dist'.
pause