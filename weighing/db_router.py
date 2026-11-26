class WeighingRouter:
    """
    数据库路由器：
    - notes 应用使用 Oracle 新库 notes_oracle（xiansanzhenren，2026-11-26 切换）
    - weighing、backtest、subscription 应用使用 MySQL 数据库
    - 其他应用使用默认的 Oracle 数据库（stockapi）
    """
    mysql_app_labels = {'weighing', 'backtest', 'subscription'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'notes':
            return 'notes_oracle'
        if model._meta.app_label in self.mysql_app_labels:
            return 'mysql'
        return 'default'  # Oracle

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'notes':
            return 'notes_oracle'
        if model._meta.app_label in self.mysql_app_labels:
            return 'mysql'
        return 'default'  # Oracle

    def allow_relation(self, obj1, obj2, **hints):
        # notes 内部关系（同在 notes_oracle）放行；notes 与其他库的对象不允许关系
        if obj1._meta.app_label == 'notes' or obj2._meta.app_label == 'notes':
            return obj1._meta.app_label == obj2._meta.app_label == 'notes'
        # 允许同一数据库内的关系
        if (obj1._meta.app_label in self.mysql_app_labels) and \
           (obj2._meta.app_label in self.mysql_app_labels):
            return True
        # 如果一个在 MySQL 列表中而另一个不在，则不允许关系
        if (obj1._meta.app_label in self.mysql_app_labels) != \
           (obj2._meta.app_label in self.mysql_app_labels):
            return False
        # 否则，让Django决定
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'notes':
            # notes 应用的迁移只在 notes_oracle 上执行
            return db == 'notes_oracle'
        if app_label in self.mysql_app_labels:
            # weighing 和 backtest 应用的迁移只在 mysql 上执行
            return db == 'mysql'
        # 对于其他应用，只允许在 default (Oracle) 上迁移
        return db == 'default'
