@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /EHsc tools\dxil_roundtrip.cpp /Fo"research\65_c2077_dxil_roundtrip_20261016\dxil_roundtrip.obj" /Fe"research\65_c2077_dxil_roundtrip_20261016\dxil_roundtrip.exe"
exit /b %errorlevel%
