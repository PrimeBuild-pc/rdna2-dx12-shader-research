@echo off
call "C:\Program Files\Microsoft Visual Studio8\Community\VC\Auxiliary\Buildcvars64.bat" >/dev/null 2>&1
if errorlevel 1 ( echo vcvars64 not found & exit /b 1 )
cl /nologo /O2 /EHsc /std:c++17 /W3 sweep.cpp /Fe:sweep.exe /Fo:sweep.obj
exit /b %errorlevel%
