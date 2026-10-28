@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 ( echo vcvars64 non trovato & exit /b 1 )
cl /nologo /O2 /EHsc /std:c++17 /W3 bench.cpp /Fe:bench.exe /Fo:bench.obj
exit /b %errorlevel%
