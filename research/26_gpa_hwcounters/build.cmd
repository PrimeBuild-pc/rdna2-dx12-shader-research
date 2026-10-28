@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 ( echo vcvars64 non trovato & exit /b 1 )
set GPA=C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4
cl /nologo /O2 /EHsc /std:c++17 /W3 /I"%GPA%\include" %1 /Fe:%~n1.exe /Fo:%~n1.obj
exit /b %errorlevel%
