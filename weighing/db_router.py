class WeighingRouter:
    """
    数据库路由器：
    - weighing 应用使用 MySQL 数据库
    - 其他应用使用默认的 Oracle 数据库
    """
    route_app_labels = {'weighing'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'mysql_db'
        return 'default'  # Oracle

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'mysql_db'
        return 'default'  # Oracle

    def allow_relation(self, obj1, obj2, **hints):
        # 允许同一数据库内的关系
        if (obj1._meta.app_label in self.route_app_labels) == (obj2._meta.app_label in self.route_app_labels):
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            # weighing 应用的迁移只在 mysql_db 上执行
            return db == 'mysql_db'
        # 其他应用的迁移在 default (Oracle) 上执行
        return db == 'default' 