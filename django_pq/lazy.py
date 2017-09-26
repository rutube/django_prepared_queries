# coding: utf-8
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils.functional import Promise

LAZY_PROXY_CHECK_ERROR = "You are checking Lazy proxy instead of it's value"
LAZY_EMPTY_LIST_FORBIDDEN = "Empty list in Lazy leads to unequivalent results"
LAZY_MODEL_FORBIDDEN = "You should not pass Model object as a cache argument"


class Lazy(Promise):

    def __init__(self, key, value=None):
        if isinstance(value, (list, tuple)) and not value:
            # "In" lookup check value against empty list and raises
            # EmptyResultSet instead of adding new condition to WhereNode.

            # In this case IN clause disappears from SQL leading to equivalent
            # but not identical SQL queries for generated for non-empty lists.
            raise RuntimeError(key, LAZY_EMPTY_LIST_FORBIDDEN)
        if isinstance(value, models.Model):
            # If object instance methods or attributes are needed to construct
            # an SQL query, there may be a hidden parameter leading to incorrect
            # cache keys for SQL.
            raise RuntimeError(key, LAZY_MODEL_FORBIDDEN)
        if isinstance(key, Lazy):
            # In some cases Lazy is constructed from another Lazy object
            # noinspection PyProtectedMember
            key = key._Lazy__key
        self.__key = key

    def _prepare(self):
        """
        Called in Field.get_prep_lookup to prevent revealing real values.
        """
        return self

    def reveal(self, safe=False):
        """
        Gets current parameter value from LazyContext manager instance.
        """
        try:
            return LazyContext.instance.get(self.__key, safe=safe)
        except RuntimeError:
            return self

    def __str__(self):
        value = self.reveal()
        # datetime values workaround for sqlite3 backend
        if isinstance(value, datetime) or LazyContext.instance.values_allowed:
            return str(value)
        raise RuntimeError("str for lazy object!")

    def __unicode__(self):
        # preserving Lazy when casting to unicode
        if LazyContext.instance.values_allowed:
            return unicode(self.reveal())
        return UnicodeLazy(self.__key)

    @property
    def tzinfo(self):
        # allows sqlite3 to check if datetime value is timezone-aware
        return self.reveal(safe=True).tzinfo

    def __iter__(self):
        # Returns an iterator with single element containing lazy list value.
        # SQL generated for IN lookup does not depend on actual values count
        # because it's corrected in django_pq.queryset.normalize function.
        yield Lazy(self.__key)

    def __int__(self):
        lazy = IntLazy(self.__key)
        return lazy

    def __repr__(self):
        return '<%s>(%s)' % (self.__class__.__name__,
                             repr(self.reveal(safe=True)))

    def __nonzero__(self):
        """ Checking lazy wrapper instead of actual value is an error."""
        raise RuntimeError(LAZY_PROXY_CHECK_ERROR)

    def __getattr__(self, item):
        """ Prohibits hashattr('__iter__') checks for Lazy objects."""
        if item == '__iter__':
            raise AttributeError(item)
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            if LazyContext.instance.values_allowed:
                return getattr(self.reveal(), item)
            raise

    def __getattribute__(self, name):
        """ Prohibits hashattr('__iter__') checks for Lazy objects."""
        if name == '__iter__':
            raise AttributeError(name)
        return super(Lazy, self).__getattribute__(name)

    # override Promise value computing method
    _proxy____cast = reveal


class UnicodeLazy(Lazy, unicode):
    pass


class IntLazy(Lazy, int):
    """ Integer class that remains lazy on int cast."""

    def __new__(cls, key):
        """ int(lazy)"""
        # noinspection PyTypeChecker
        new = int.__new__(cls, 0)
        new.__init__(key)
        return new

    def __int__(self):
        return self.reveal()


def reveal(value):
    if isinstance(value, Lazy):
        # noinspection PyProtectedMember
        return value.reveal(safe=True)
    return value


def reveal_unsafe(value):
    """ sqlite3 adapter for Lazy classes."""
    if isinstance(value, Lazy):
        # noinspection PyProtectedMember
        return value.reveal(safe=False)
    return value


class LazyContext(object):
    """ Context manager for actual parameters values lookup."""
    instance = None

    def __init__(self, *args, **params):
        kwargs = params.copy()
        for norm in args:
            kwargs = norm(kwargs)
        self.kwargs = kwargs
        self.__prev_instance = None
        self.values_allowed = False

    def __enter__(self):
        self.__prev_instance = self.instance
        self.__class__.instance = self
        return self.kwargs

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__class__.instance = self.__prev_instance

    def get(self, key, safe=False):
        """
        Returns actual parameter value only if it is safe, or if actual values
        returning is allowed for current context.
        """
        if not (self.values_allowed or safe):
            raise RuntimeError("Get real value is unsafe now")
        return self.kwargs[key]

    @classmethod
    def allow_values(cls):
        """ Allows returning actual values for current context."""
        if cls.instance:
            cls.instance.values_allowed = True


if 'sqlite3' in settings.DATABASES['default']['ENGINE']:
    # sqlite3 adapters for Lazy-classes.
    # MySQL uses Lazy.__str__ for that purposes.
    import sqlite3
    for lazy_klass in (Lazy, IntLazy, UnicodeLazy):
        sqlite3.register_adapter(lazy_klass, reveal_unsafe)
