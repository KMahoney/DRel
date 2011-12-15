'''
The classes in this file are nodes of a tree that represent an SQL
query. Each node should be both stateless and immutable -- that is,
methods should return a new AST instead of modifying an existing
one. This means expressions can be reused and composed in a similar
fashion to Django querysets.

The SQL statement is compiled by the various `_compile`
methods. Different `_compile` methods are used for different contexts
to help make sure nonsense SQL queries are not generated. We can
probably give more informative error messages in this way than the
database can.

A `Compiler` object is passed through the `_compile` methods to keep
track of any state. Currently escaped values are appended to a list
which means the nodes have to be compiled in the order they appear in
the SQL query (so the order of the '%s' values match up). Consider a
more elegant solution to be on the TODO list.

The `Compiler` object is also responsible for keeping track of table
aliasing, making sure they get unique names. This allows self joins,
for example.

'''
from collections import namedtuple

from django.db import connections

from drel.compiler import Compiler


class InvalidQuery(Exception):
    pass


class AST(object):
    '''Base class for AST nodes.'''

    # Stub the various _compile interfaces with more useful error
    # messages.

    def _compile(self, compiler):
        raise InvalidQuery("%s is not a statement" % self)

    def _compile_expression(self, compiler):
        raise InvalidQuery("%s is not an expression" % self)

    def _compile_projection(self, compiler):
        raise InvalidQuery("%s is not labeled" % self)

    def _compile_join(self, compiler):
        raise InvalidQuery("%s is not a join" % self)

    def _compile_table(self, compiler):
        raise InvalidQuery("%s is not a table" % self)

    # A neater (but less informative) representation of a node.
    # Override where suitable.

    def __repr__(self):
        return self.__class__.__name__


class ExpressionMixin(object):
    '''Provides operator overriding and labelling for expressions.'''

    def label(self, name):
        return LabeledProjection(name, self)

    @property
    def desc(self):
        return DescendingExpression(self)

    @property
    def is_null(self):
        return BinaryExpression("IS", self, RawExpression("NULL"))

    @property
    def is_not_null(self):
        return BinaryExpression("IS NOT", self, RawExpression("NULL"))

    def __eq__(self, other):
        return BinaryExpression("=", self, other)

    def __ne__(self, other):
        return BinaryExpression("<>", self, other)

    def __lt__(self, other):
        return BinaryExpression("<", self, other)

    def __le__(self, other):
        return BinaryExpression("<=", self, other)

    def __gt__(self, other):
        return BinaryExpression(">", self, other)

    def __ge__(self, other):
        return BinaryExpression(">=", self, other)

    def __or__(self, other):
        return BinaryExpression("OR", self, other)

    def __and__(self, other):
        return BinaryExpression("AND", self, other)

    def __add__(self, other):
        return BinaryExpression("+", self, other)

    def __sub__(self, other):
        return BinaryExpression("-", self, other)

    def __mul__(self, other):
        return BinaryExpression("*", self, other)

    def __mod__(self, other):
        return BinaryExpression("%", self, other)


class TableMixin(object):
    '''Basic table operations.'''

    def project(self, *fields):
        return Select(self, project=fields)

    def join(self, table, on):
        return Select(self, joins=[Join(table, on)])

    def leftjoin(self, table, on):
        return Select(self, joins=[Join(table, on, "LEFT")])

    def crossjoin(self, table):
        return Select(self, joins=[CrossJoin(table)])

    def where(self, expr):
        return Select(self, where=expr)

    def group(self, *fields):
        return Select(self, group=fields)

    def order(self, *fields):
        return Select(self, order=fields)


class DescendingExpression(AST):
    '''
    A wrapper around an expression, used to make it descending in
    an ORDER BY expression list.

    Cannot be further manipulated as an expression.

    '''
    def __init__(self, expr):
        self._expr = expr

    def _compile_expression(self, compiler):
        expr = self._expr._compile_expression(compiler)
        return "%s DESC" % expr


class LabeledProjection(AST):
    '''
    An expression that has been assigned a label.

    Cannot be further manipulated as an expression.

    '''
    def __init__(self, label, expr):
        self.row_key = label
        self._expr = expr

    def _compile_projection(self, compiler):
        expr = self._expr._compile_expression(compiler)
        return "%s AS %s" % (expr, compiler.q(self.row_key))


class BinaryExpression(AST, ExpressionMixin):
    def __init__(self, op, a, b):
        self._op = op
        self._a = a
        self._b = b

    def _compile_expression(self, compiler):
        a = self._a._compile_expression(compiler)
        b = self._b._compile_expression(compiler)
        return "%s %s %s" % (a, self._op, b)


class Const(AST, ExpressionMixin):
    '''A value to be escaped by the database engine.'''

    def __init__(self, value, alias=None):
        self._value = value

    def _compile_expression(self, compiler):
        # Compiler state is used here. This is why the SQL statement
        # has to be built in order: so the placeholders match up with
        # the list of values.
        compiler.values.append(self._value)
        return "%s"


class RawExpression(AST, ExpressionMixin):
    '''Pass through a string directly to the compiled SQL.'''

    def __init__(self, sql):
        self._sql = sql

    def _compile_expression(self, compiler):
        return self._sql


class LabelReference(AST, ExpressionMixin):
    '''A reference to a labelled field/expression.'''

    def __init__(self, label):
        self._label = label

    def _compile_expression(self, compiler):
        return compiler.q(self._label)


class FunctionExpression(AST, ExpressionMixin):
    '''SQL function application.'''

    def __init__(self, fn, *args):
        self._fn = fn
        self._args = args

    def _compile_expression(self, compiler):
        args = ",".join(a._compile_expression(compiler) for a in self._args)
        return "%s(%s)" % (self._fn, args)


class Field(AST, ExpressionMixin):
    def __init__(self, table, column, label=None):
        self._table = table
        self._column = column
        self.row_key = label or column

    def _compile_expression(self, compiler):
        alias = compiler.refer(self._table)
        column = compiler.q(self._column)
        return "%s.%s" % (alias, column)

    def _compile_projection(self, compiler):
        label = compiler.q(self.row_key)
        expr = self._compile_expression(compiler)
        return "%s AS %s" % (expr, label)


class Join(AST):
    def __init__(self, table, on, kind="INNER"):
        self._table = table
        self._on = on
        self._kind = kind

    def _compile_join(self, compiler):
        table = self._table._compile_table(compiler)
        on_expr = self._on._compile_expression(compiler)
        return "%s JOIN %s ON %s" % (self._kind, table, on_expr)


class CrossJoin(AST):
    def __init__(self, table):
        self._table = table

    def _compile_join(self, compiler):
        table = self._table._compile_table(compiler)
        return "CROSS JOIN %s" % table


class Select(AST, ExpressionMixin):
    '''Representation of a SELECT SQL statement.'''

    def __init__(self, source, project=None, joins=None,
                 where=None, group=None, order=None):
        self._source = source
        self._project = project or []
        self._joins = joins or []
        self._where = where
        self._group = group
        self._order = order

    def project(self, *fields):
        return self._modified(_project=fields)

    def join(self, table, on):
        return self._add_join(Join(table, on))

    def leftjoin(self, table, on):
        return self._add_join(Join(table, on, "LEFT"))

    def crossjoin(self, table):
        return self._add_join(CrossJoin(table))

    def where(self, expr):
        if not self._where:
            return self._modified(_where=expr)
        where = self._where & expr
        return self._modified(_where=where)

    def group(self, *fields):
        return self._modified(_group=fields)

    def order(self, *fields):
        return self._modified(_order=fields)

    @property
    def subquery(self):
        return SubQuery(self)

    def _clone(self):
        # Note: copy.copy interacts badly with __getattr__
        return Select(
            self._source,
            self._project,
            self._joins,
            self._where,
            self._group,
            self._order)

    def _modified(self, **kwargs):
        c = self._clone()
        for (k, v) in kwargs.items():
            setattr(c, k, v)
        return c

    def _add_join(self, join):
        joins = list(self._joins)
        joins.append(join)
        return self._modified(_joins=joins)

    def _execute(self, using='default'):
        con = connections[using]
        compiler = Compiler(con)
        sql = self._compile(compiler)

        cursor = con.cursor()
        cursor.execute(sql, compiler.values)
        return cursor

    def _sql(self, using='default'):
        con = connections[using]
        compiler = Compiler(con)
        return (self._compile(compiler), tuple(compiler.values))

    def to_model(self, model, using='default'):
        sql, values = self._sql(using)
        return model.objects.raw(sql, values)

    def all(self, using='default'):
        '''Execute select and return all rows.'''
        cursor = self._execute(using)
        cons = namedtuple('Row', [f.row_key for f in self._project])
        for row in cursor.fetchall():
            yield cons(*row)

    def one(self, using='default'):
        '''Execute select and return a single row.'''
        cursor = self._execute(using)
        cons = namedtuple('Row', [f.row_key for f in self._project])
        return cons(*cursor.fetchone())

    def _compile(self, compiler):
        assert self._project, "No fields projected."

        field_sql = ",".join(
            f._compile_projection(compiler) for f in self._project)
        from_sql = self._source._compile_table(compiler)
        sql = ["SELECT %s FROM %s" % (field_sql, from_sql)]

        join_sql = [j._compile_join(compiler) for j in self._joins]
        sql.extend(join_sql)

        if self._where:
            sql.append("WHERE")
            sql.append(self._where._compile_expression(compiler))

        if self._group:
            group_sql = ",".join(
                f._compile_expression(compiler) for f in self._group)
            sql.append("GROUP BY")
            sql.append(group_sql)

        if self._order:
            order_sql = ",".join(
                f._compile_expression(compiler) for f in self._order)
            sql.append("ORDER BY")
            sql.append(order_sql)

        return " ".join(sql)


class SubQuery(AST, ExpressionMixin, TableMixin):
    def __init__(self, select):
        self._select = select

    def _compile_expression(self, compiler):
        return "(%s)" % self._select._compile(compiler)

    def _compile_table(self, compiler):
        alias = compiler.refer(self)
        return "(%s) AS %s" % (self._select._compile(compiler), alias)

    def __getattr__(self, key):
        for f in self._select._project:
            if key == f.row_key:
                return Field(self, key)

        raise AttributeError(key)


class DjangoTable(AST, TableMixin):
    '''A wrapper around a Django Model for building DRel queries.'''

    def __init__(self, model):
        self._model = model

    def _compile_table(self, compiler):
        alias = compiler.refer(self)
        table = compiler.q(self._model._meta.db_table)
        return "%s AS %s" % (table, alias)

    def __getattr__(self, key):
        for f in self._model._meta.fields:
            if key == f.name:
                return Field(self, f.column, f.name)
            if key == f.column:
                return Field(self, f.column)

        raise AttributeError(key)


class DjangoM2MTable(AST, TableMixin):
    '''
    A wrapper around a Django many-to-many field for building DRel
    queries.

    '''
    def __init__(self, m2m):
        self._m2m = m2m

    def _compile_table(self, compiler):
        alias = compiler.refer(self)
        table = compiler.q(self._m2m.m2m_db_table())
        return "%s AS %s" % (table, alias)

    def __getattr__(self, key):
        if key == self._m2m.m2m_field_name():
            return Field(self, self._m2m.m2m_column_name(), key)

        if key == self._m2m.m2m_reverse_field_name():
            return Field(self, self._m2m.m2m_reverse_name(), key)

        if key == self._m2m.m2m_column_name():
            return Field(self, key)

        if key == self._m2m.m2m_reverse_name():
            return Field(self, key)

        raise AttributeError(key)
