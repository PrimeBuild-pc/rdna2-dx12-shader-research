@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
set BASE=research\66_c2077_shader_loader_20261016
set INC=%BASE%\sources\reshade-6.8.0\include
cl /nologo /std:c++17 /O2 /W4 /EHsc /MT /D_WIN32_WINNT=0x0A00 /DSHADER_LAB_SELFTEST /I"%INC%" /I"%BASE%\build" tools\c2077_shader_addon.cpp /Fo"%BASE%\build\shader_lab_test.obj" /Fe"%BASE%\build\shader_lab_test.exe"
if errorlevel 1 exit /b 1
"%BASE%\build\shader_lab_test.exe"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /EHsc /MT /D_WIN32_WINNT=0x0A00 /LD /I"%INC%" /I"%BASE%\build" tools\c2077_shader_addon.cpp /Fo"%BASE%\build\shader_lab_addon.obj" /link /OUT:"%BASE%\stage\C2077ShaderLab\C2077ShaderLab.addon64" /IMPLIB:"%BASE%\build\shader_lab.lib"
exit /b %errorlevel%
