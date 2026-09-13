@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Забираю последнюю версию сайта с GitHub...
git pull --rebase --autostash || goto :fail

echo Загружаю данные из Google Таблицы...
python update-data.py || goto :fail

git add assets/data.js index.html
git diff --cached --quiet
if %errorlevel%==0 (
  echo Данные не изменились — публиковать нечего.
  pause
  exit /b 0
)

git commit -m "Обновление данных вручную" || goto :fail
git push || goto :fail

echo.
echo Готово! Сайт обновится через 1-2 минуты:
echo https://ol272g.github.io/kinolega-quiz/
pause
exit /b 0

:fail
echo.
echo Что-то пошло не так — сообщение об ошибке выше.
pause
exit /b 1
