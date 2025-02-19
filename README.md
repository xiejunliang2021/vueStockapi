# vueStockapi
- 股票分析系统
- 添加文件cleanup_db.py，用于清理数据库全部数据
`python manage.py cleanup_db`
- 添加文件cleanup_tables，用来清理数据库表（这个是部分清理,但是会删除表中的所有数据）
`python manage.py cleanup_tables`
- 添加文件rebuild_migrations，用来重新构建迁移记录
`python manage.py rebuild_migrations`
- 添加文件check_tables，用来检查数据库表文件
`python manage.py check_tables`
- 添加文件manual_analysis.py，用于手动策略分析
`python manage.py manual_analysis`
- 添加文件settings.py，用于配置数据库连接信息
- 添加文件urls.py，用于配置路由
- 添加文件views.py，用于配置视图
- 添加文件models.py，用于配置模型
- 添加文件serializers.py，用于配置序列化器
- 添加文件tasks.py，用于配置任务
- 添加文件tests.py，用于配置测试
- 添加文件utils.py，用于配置工具函数

## 主要功能

- 获取或更新股票代码
```
python manage.py fetch_and_save_stock_data
```
- 获取或更新股票日线数据
```
python manage.py fetch_and_save_stock_data
```