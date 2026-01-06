@echo off
REM 使用测试配置运行单元测试
echo 使用MySQL数据库运行测试...
set DJANGO_SETTINGS_MODULE=vueStockapi.settings_test
python manage.py test backtest.tests -v 2
