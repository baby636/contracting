'''
TODO: IMPORTANT: Don't allow overlapping temp and permanent table names

TODO: complex stuff, soft delete a permanent, create temporary, delete temporary
'''
import sys

import re
import copy
import MySQLdb
from seneca.seneca_internal.util import *

import seneca.seneca_internal.storage.mysql_executer as ex_base
from seneca.seneca_internal.storage.mysql_intermediate import *

unalterted_queries = [ DeleteRows,
                       UpdateRows,
                       InsertRows,
                       SelectRows,
                       CountUniqueRows,
                       CountRows,
                       DescribeTable,
]

dissallowed_queries = [ AddTableColumn,
                        DropTableColumn,
]

def make_temp_name(table_name):
    '''
    >>> make_temp_name('test')
    '$temp$test'
    '''
    return '$temp$' + table_name

def make_query_with_temp_name(q):
    '''
    >>> q = mysqli.InsertRows('test_users', ['username', 'first_name', 'balance'],
    ...   [['tester', 'test', 500],
    ...    ['tester2', 'two', 200],
    ...   ])
    >>> q1 = make_query_with_temp_name(q)
    >>> q1.table_name
    '$temp$test_users'
    '''
    q1 = copy.copy(q)
    q1.table_name = make_temp_name(q1.table_name)
    return q1

import sys
def CreateTableAction(ex, q):
    '''
    Clear state:
    >>> ex = make_ex()
    >>> _ = ex.rollback()
    >>> _ = ex.cur.execute('DROP DATABASE seneca_test;')
    >>> _ = ex.cur.execute('CREATE DATABASE seneca_test;')
    >>> _ = ex.cur.execute('use seneca_test;')

    >>> _ = CreateTableAction(ex, ct)

    Confirm that table name is stored in temp_tables field, used for rollback and commit
    >>> ex.temp_tables
    {'test_users'}

    Confirm that the table is created (not established in this step if it's actually a temp table)
    >>> ex.cur.execute('SELECT * from seneca_test.$temp$test_users')
    0
    >>> print(ex.cur.fetchall())
    ()

    Confirm that the table is temporary (temporary tables are not returned by mysql's show tables)
    >>> ex.cur.execute('SHOW TABLES;')
    0

    Make sure no table has actually been created and commited.
    >>> ist = easy_db.Table.from_existing('INFORMATION_SCHEMA.TABLES').run(ex)
    >>> len(ist.select('table_name').where(ist.TABLE_NAME == 'test_users').run(ex))
    0
    >>> ex.rollback()

    Repeat process but commit:
    >>> _ = CreateTableAction(ex, ct)
    >>> _ = ex.commit()
    >>> ist = easy_db.Table.from_existing('INFORMATION_SCHEMA.TABLES').run(ex)
    >>> len(ist.select('table_name').where(ist.TABLE_NAME == 'test_users').run(ex))
    1
    >>> ex.temp_tables
    set()
    '''
    name = q.table_name
    temp_table_exists = name in ex.temp_tables
    permanent_table_exists = 0 < ex.cur.execute("SELECT table_name FROM INFORMATION_SCHEMA.TABLES where table_name = '{}'".format(name))
    soft_delete_exists = name in ex.soft_deleted_tables

    q_type = type(q)

    if temp_table_exists:
        raise Exception('SPITS: Table already logically exists (as temp).')
    elif permanent_table_exists and (not soft_delete_exists):
        raise Exception('SPITS: Table already exists')
    elif q_type != CreateTable:
        raise Exception('Argument 1 q is wrong type, should be CreateTable got %' % str(q_type))

    # Important, temp tables are stored in executer temp table without temp table prefix
    ex.temp_tables.add(name)
    # Prefix added here for create query
    sql_str = make_query_with_temp_name(q).to_sql()

    # NOTE: A little janky
    sql_preamble_re = re.compile('^CREATE TABLE')
    assert re.match(sql_preamble_re, sql_str)

    new_query = re.sub(sql_preamble_re, 'CREATE TEMPORARY TABLE', sql_str)
    #print(new_query)
    res = ex.cur.execute(new_query)

    return ex_base.format_result(q_type, ex.cur)


def ListTablesAction(ex, q):
    '''
    '''
#
#    TODO: finish this tests
#    Result comes from db:
#    >> _ = ex.commit()
#    >> str(ListTablesAction(ex,ListTables()))
#    "SQLExecutionResult({'success': True, 'data': ['test_users']})"
#
#    Soft delete table hidden:
#    >> _ = CreateTableAction(ex, ct)
#    >> _ = ex.commit()
#
#    '''
    q_type = type(q)
    ex.cur.execute(q.to_sql())

    sql_ex_res = ex_base.format_result(q_type, ex.cur)
    table_names = sql_ex_res.data

    table_names_temp = list(
                         set( ex.temp_tables | \
                              {t for t in table_names if t not in ex.soft_deleted_tables}
                         )
                       )
    sql_ex_res.data = table_names_temp

    # Not formatting
    return ex_base.SQLExecutionResult(True, sql_ex_res.data)


def DropTableAction(ex, q):
    '''
    Clear state:
    >>> ex = make_ex()
    >>> _ = ex.rollback()
    >>> _ = ex.cur.execute('DROP DATABASE seneca_test;')
    >>> _ = ex.cur.execute('CREATE DATABASE seneca_test;')
    >>> _ = ex.cur.execute('use seneca_test;')

    Delete an uncommited table (temporary):
    >>> _ = CreateTableAction(ex, ct)
    >>> ex.temp_tables
    {'test_users'}

    >>> str(DropTableAction(ex, DropTable('test_users')))
    "SQLExecutionResult({'success': True, 'data': 'Uncommitted table test_users has been deleted.'})"

    >>> ex.temp_tables
    set()


    Clear state:
    >>> ex = make_ex()
    >>> _ = ex.rollback()
    >>> _ = ex.cur.execute('DROP DATABASE seneca_test;')
    >>> _ = ex.cur.execute('CREATE DATABASE seneca_test;')
    >>> _ = ex.cur.execute('use seneca_test;')

    Soft delete a table and confirm name has been added to the soft_delete list:
    >>> _ = CreateTableAction(ex, ct)
    >>> _ = ex.commit()
    >>> str(DropTableAction(ex, DropTable('test_users')))
    "SQLExecutionResult({'success': True, 'data': 'Table test_users has been soft-deleted.'})"
    >>> ex.soft_deleted_tables
    {'test_users'}
    >>> ex.temp_tables
    set()

    >>> _ = ex.commit()

    Test that soft-deleting an already soft deleted table sends a failure:
    >>> str(DropTableAction(ex, DropTable('test_users')))
    'SQLExecutionResult({\\'success\\': False, \\'data\\': "SPITS ERROR: Attempting to delete a table that doesn\\'t logically exist"})'
    '''
    q_type = type(q)

    name = q.table_name
    temp_name = make_temp_name(name)

    temp_table_exists = name in ex.temp_tables
    permanent_table_exists = 0 < ex.cur.execute("SELECT table_name FROM INFORMATION_SCHEMA.TABLES where table_name ='{}'".format(name))
    soft_delete_exists = name in ex.soft_deleted_tables

    if temp_table_exists:
        # TODO: Make sure this is the right logic and in the right place
        assert permanent_table_exists == soft_delete_exists, "SPITS ERROR: Table delete status in inconsistent state."

        ex.cur.execute("DROP TEMPORARY TABLE %s" % temp_name)
        # TODO: validate result
        ex.temp_tables.remove(name)
        return ex_base.SQLExecutionResult(True, "Uncommitted table %s has been deleted." % name)

    elif permanent_table_exists and (not soft_delete_exists):
        ex.soft_deleted_tables.add(name)
        return ex_base.SQLExecutionResult(True, "Table %s has been soft-deleted." % name)

    else:
        return ex_base.SQLExecutionResult(False, 'SPITS ERROR: Attempting to delete a table that doesn\'t logically exist')



special_action_query_dict = { CreateTable: CreateTableAction,
                              ListTables: ListTablesAction,
                              DropTable: DropTableAction,
}

special_action_queries = list(special_action_query_dict.keys())

# TODO: Dedupe with main executer
class Executer(object):
    def __init__(self, username, password, db, host, port=3306):
        ''' Tested below '''
        self.conn = MySQLdb.connect(host=host, user=username, passwd=password,
                                    db=db, port=port)
        self.conn.autocommit = False
        self.cur = self.conn.cursor()
        self.temp_tables = set()
        self.soft_deleted_tables = set()

    @classmethod
    def init_local_noauth_dev(cls, db_name='seneca_test'):
        ''' Not testing this. '''
        s = cls('root', '', '', 'localhost')
        s.cur.execute('CREATE DATABASE IF NOT EXISTS {};'.format(db_name))
        s.cur.execute('use {};'.format(db_name))
        s.conn.database = db_name

        return s

    def __call__(self, query):
        q_type = type(query)
        assert issubclass(q_type, Query), 'The passed parameter is not a query.'

        try:
            if q_type in unalterted_queries:
                if query.table_name in self.soft_deleted_tables:
                    raise Exception("Table does not exist, (soft deleted).")

                if query.table_name in self.temp_tables:
                    query = make_query_with_temp_name(query)

                self.cur.execute(query.to_sql())
                return ex_base.format_result(q_type, self.cur)

            elif q_type in dissallowed_queries:
                raise Exception('Dissallowed query. Incompatible with SPITS.')

            elif q_type in special_action_queries:
                return special_action_query_dict(q_type)(self, query)

            else:
                raise Exception("Unrecognized query type. \
SPITS does not have the needed info to execute this query.")

        except Exception as err:
            # Note: This function may return a formated result, or it may reraise the error
            return handle_error(q_type, err)

    def _clear(self):
        self.temp_tables = set()
        self.soft_deleted_tables = set()


    def commit(self):
        ''' Tested elsewhere '''
        # DML commit
        self.conn.commit()

        # DDL pseudo-commit
        for t in self.temp_tables:
            name = t
            temp_name = make_temp_name(name)

            q_str = 'CREATE TABLE {name} LIKE {temp_name};\
                     INSERT {name} SELECT * FROM {temp_name};\
                     DROP TEMPORARY TABLE {temp_name};'.format(**locals())

            self.cur.execute(q_str)

        for t in self.soft_deleted_tables:
            self.cur.execute("DROP TABLE %s;" % t)

        # Purge internal scratch
        self._clear()


    def rollback(self):
        ''' Tested elsewhere '''
        # DML rollback
        self.conn.rollback()

        # DDL pseudo-rollback
        for t in self.temp_tables:
            self.cur.execute("DROP TEMPORARY TABLE %s;" % make_temp_name(t))

        # Purge internal scratch
        self._clear()

    def many(self, queries):
        # TODO: Test the speed on this
        # TODO: Error handling
        # TODO: Test atomicity
        for q in queries:
            self.cur.execute(q.to_sql())
        self.conn.commit()

        return ex_base.SQLExecutionResult(True, None)


def run_tests():
    '''
    Setup/clear state:
    >>> ex = make_ex()
    >>> _ = ex.rollback(); ex.soft_deleted_tables |  ex.temp_tables
    set()
    >>> _ = ex.cur.execute('DROP DATABASE IF EXISTS seneca_test;')
    >>> _ = ex.cur.execute('CREATE DATABASE seneca_test;')
    >>> _ = ex.cur.execute('use seneca_test;')

    List empty:
    >>> str(ListTablesAction(ex,ListTables()))
    "SQLExecutionResult({'success': True, 'data': []})"

    Create temporary table:
    >>> _ = CreateTableAction(ex, ct)
    >>> ex.temp_tables
    {'test_users'}

    List with results from temporary table record in executer:
    >>> str(ListTablesAction(ex,ListTables()))
    "SQLExecutionResult({'success': True, 'data': ['test_users']})"

    List with results from permanent table:
    >>> ex.commit()
    >>> ex.temp_tables
    set()
    >>> str(ListTablesAction(ex,ListTables()))
    "SQLExecutionResult({'success': True, 'data': ['test_users']})"

    Results exclude soft deleted table:
    >>> str(DropTableAction(ex, DropTable('test_users')))
    "SQLExecutionResult({'success': True, 'data': 'Table test_users has been soft-deleted.'})"

    '''
    '''
    >>> ex.soft_deleted_tables
    ['test_users']
    >>> str(ListTablesAction(ex,ListTables()))
    "SQLExecutionResult({'success': True, 'data': []})"

    '''
    import configparser
    import os
    import sys

    settings = configparser.ConfigParser()
    settings._interpolation = configparser.ExtendedInterpolation()
    this_dir = os.path.dirname(__file__)
    settings.read(os.path.join(this_dir, 'test_db_conf.ini'))

    conn = MySQLdb.connect(host=settings.get('DB', 'hostname'),
                           user=settings.get('DB', 'username'),
                           passwd=settings.get('DB', 'password'),
                           port=3306)
    conn.autocommit = False
    cur = conn.cursor()

    def clear_db():
        print("Clearing db...")
        try:
            cur.execute('DROP DATABASE seneca_test;')
        except MySQLdb.OperationalError as e:
            if not e.args == (1008, "Can't drop database 'seneca_test'; database doesn't exist"):
                raise
        cur.execute('CREATE DATABASE seneca_test;')
        print("DB cleared.")

    clear_db()

    def make_ex():
        return Executer(settings.get('DB', 'username'),
                        settings.get('DB', 'password'),
                        settings.get('DB', 'database'),
                        settings.get('DB', 'hostname'),
               )

    import doctest
    import seneca.seneca_internal.storage.mysql_intermediate as mysqli
    import seneca.seneca_internal.storage.easy_db as easy_db
    #doctest.testmod(extraglobs={'ex': ex})

    ct = CreateTable(
          'test_users',
          AutoIncrementColumn('id'),
          [ ColumnDefinition('username', SQLType('VARCHAR', 30), True),
            ColumnDefinition('drivers_licence_unmber', SQLType('VARCHAR', 30), True),
            ColumnDefinition('first_name', SQLType('VARCHAR', 30), False),
            ColumnDefinition('balance', SQLType('BIGINT'), False),
    ])

    doctest.testmod(sys.modules[__name__],
                    extraglobs={'mysqli': mysqli,
                                'easy_db': easy_db,
                                'clear_db': clear_db,
                                'make_ex': make_ex,
                                'ct': ct,
                                }
    )