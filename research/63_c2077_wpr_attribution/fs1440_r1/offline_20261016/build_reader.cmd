@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /EHsc tools\etl_extract.cpp /Fo"research\63_c2077_wpr_attribution\fs1440_r1\offline_20261016\etl_extract.obj" /Fe"research\63_c2077_wpr_attribution\fs1440_r1\offline_20261016\etl_extract.exe"
if errorlevel 1 exit /b 1
"research\63_c2077_wpr_attribution\fs1440_r1\offline_20261016\etl_extract.exe" --selfcheck
