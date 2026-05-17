@echo off
REM ================================================================
REM ejecutar_pipeline.bat
REM Script de automatización para Windows.
REM Ejecuta el pipeline de scraping + indexación cada vez que
REM el Programador de Tareas lo invoca.
REM
REM CONFIGURACIÓN (edita las rutas antes de usar):
REM ================================================================

REM Ruta absoluta a la carpeta del proyecto
SET PROYECTO=C:\Users\ALEXANDRA\Desktop\bolivia_noticias

REM Ruta al ejecutable de Python del entorno virtual (recomendado)
REM Si no usas venv, usa simplemente: SET PYTHON=python
SET PYTHON=%PROYECTO%\venv\Scripts\python.exe

REM ================================================================
REM No editar debajo de esta línea
REM ================================================================

echo [%date% %time%] Iniciando pipeline de Bolivia Noticias...

cd /d %PROYECTO%
%PYTHON% main.py pipeline

echo [%date% %time%] Pipeline finalizado.
