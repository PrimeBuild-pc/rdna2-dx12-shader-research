@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
set BASE=research\68_c2077_backbuffer_catalog_20261016
set SDK=research\66_c2077_shader_loader_20261016
cl /nologo /std:c++17 /O2 /W4 /EHsc /MT /D_WIN32_WINNT=0x0A00 /DBACKBUFFER_SELFTEST /I"%SDK%\sources\reshade-6.8.0\include" /I"%SDK%\build" tools\c2077_backbuffer_probe.cpp /Fo"%BASE%\build\test.obj" /Fe"%BASE%\build\test.exe"
if errorlevel 1 exit /b 1
"%BASE%\build\test.exe"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /EHsc /MT /D_WIN32_WINNT=0x0A00 /LD /I"%SDK%\sources\reshade-6.8.0\include" /I"%SDK%\build" tools\c2077_backbuffer_probe.cpp /Fo"%BASE%\build\probe.obj" /link /OUT:"%BASE%\payload\C2077BackbufferProbe.addon64" /IMPLIB:"%BASE%\build\probe.lib"
exit /b %errorlevel%
