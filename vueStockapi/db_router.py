class WeighingAppRouter:
    """
    A router to control all database operations on models in the
    weighing application.
    """

    def db_for_read(self, model, **hints):
        """
        Attempts to read weighing models go to mysql_db.
        """
        if model._meta.app_label == 'weighing':
            return 'mysql_db'
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write weighing models go to mysql_db.
        """
        if model._meta.app_label == 'weighing':
            return 'mysql_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the weighing app is involved.
        """
        if obj1._meta.app_label == 'weighing' or obj2._meta.app_label == 'weighing':
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the weighing app only appears in the 'mysql_db'
        database.
        """
        if app_label == 'weighing':
            return db == 'mysql_db'
        return None