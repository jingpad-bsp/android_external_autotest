import common
import MySQLdb as driver
import db

class db_mysql(db.db_sql):
    def connect(self, host, database, user, password, port):
        connection_args = {
            'host': host,
            'user': user,
            'db': database,
            'passwd': password,
        }
        if port:
            connection_args['port'] = int(port)
        return driver.connect(**connection_args)
