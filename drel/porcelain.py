'''
User facing top-level functions.

'''
from drel.ast import (
    DjangoTable, DjangoM2MTable, Const,
    FunctionExpression, LabelReference, RawExpression)
from django.db.models.base import ModelBase
from django.db.models.fields.related import ReverseManyRelatedObjectsDescriptor


def table(t):
    '''
    Create a DRel table from a Django Model or many-to-many foreign
    key.

    '''
    if isinstance(t, ReverseManyRelatedObjectsDescriptor):
        return DjangoM2MTable(t.field)
    assert isinstance(t, ModelBase), "Expected Django model."
    return DjangoTable(t)


def const(c):
    '''A constant SQL value. Escaped by the database engine.'''
    return Const(c)


def label(l):
    '''A reference to a labelled field or expression.'''
    return LabelReference(l)


def raw_expr(expr):
    '''A raw SQL expression.'''
    return RawExpression(expr)


def fn(name, *args):
    '''Apply a SQL function.'''
    return FunctionExpression(name, *args)


def sum(arg):
    '''Sum aggregate function.'''
    return fn("SUM", arg)


def avg(arg):
    '''Average aggregate function.'''
    return fn("AVG", arg)


def max(arg):
    '''Max aggregate function.'''
    return fn("MAX", arg)


def min(arg):
    '''Min aggregate function.'''
    return fn("MIN", arg)


def count(arg=raw_expr("*")):
    '''Count aggregate function.'''
    return fn("COUNT", arg)
