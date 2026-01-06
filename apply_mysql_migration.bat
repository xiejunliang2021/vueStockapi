@echo off
REM 应用backtest迁移到MySQL数据库
echo ========================================
echo 应用数据库迁移到MySQL
echo ========================================
echo.

echo 步骤1：应用backtest迁移到MySQL数据库...
python manage.py migrate backtest --database=mysql

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo 成功！迁移已应用到MySQL
    echo ========================================
    echo.
    echo 现在可以运行测试:
    echo   python test_full.py
) else (
    echo.
    echo ========================================
    echo 失败！请检查错误信息
    echo ========================================
)

pause
