# coding: utf-8
import logging
from collections import defaultdict
from functools import wraps
from logging import getLogger

from django.db import models
from typing import Dict, Tuple, Any, Callable, Optional

from .lazy import LazyContext, Lazy
from .queryset import normalize, RawQuerySet


# Type definitions
QS = models.QuerySet

# query parameters type
ParamsType = Tuple[Any]

# (sql, params)
SqlWithParams = Tuple[str, ParamsType]

# prepared queries cache for arguments values
QueryCache = Dict[Tuple, RawQuerySet]

# prepared queries cache for arguments list
CacheType = Dict[Tuple, QueryCache]

# decorated functions type
WrappingFuncType = Callable[..., QS]


class MappingFailed(Exception):
    """ Lazy result differs from native one."""
    pass


class SqlMappingFailed(MappingFailed):
    """ SQL queries are not equal."""
    pass


class ParamsMappingFailed(MappingFailed):
    """ Query parameters are not equal."""
    pass


class Stub(object):
    """ Stub for cache key meaning "argument is present" """
    def __repr__(self):
        return '/stub/'


class LazySubstitute(object):
    """ Decorator for queryset caching."""

    logger = getLogger('django.db.backends.Substitute')

    special = [True, False, None, 0, 1]

    stub = Stub()

    def __init__(self, check=True, debug=True, enabled=True):
        """
        :param check: enables checking real and lazy results before caching
        :param debug: enables debug mode
        :param enabled: flag for complete disable of caching
        """
        # prepared queries cache
        self.cache = defaultdict(dict)  # type: CacheType
        self.DEBUG = debug
        self.check = check or debug
        self.enabled = enabled
        if not debug:
            self.logger.setLevel(logging.ERROR)

    def __call__(self, func):
        # type: (WrappingFuncType) -> WrappingFuncType
        """ Cached function decorator."""
        if not self.enabled:
            return func

        self.func = func
        self._func_repr = repr(func)

        @wraps(func)
        def inner(this, **kwargs):
            try:
                return self.do_call(this, **kwargs)
            finally:
                LazyContext.allow_values()

        return inner

    def get_cache_key(self, params):
        """
        Computes cache key respecting presence, type and some values of
        function arguments.
        """
        result = []
        for p in params:
            if p in self.special:
                # known constants are used directly in cache key
                result.append(p)
            else:
                # unknown values are marked as "parameter is present"
                result.append(self.stub)
        return tuple(result)

    def get_native_queryset(self, this, **kwargs):
        # type: (Any, Dict[str, Any]) -> QS
        """
        Computes native queryset without any caching
        """
        qs = self.func(this, **kwargs)
        return qs

    def get_lazy_result(self, this, **kwargs):
        # type: (Any, Dict[str, Any]) -> QS
        """
        Computes queryset with Lazy parameters passed to function
        """
        kwargs = {k: Lazy(k, v) for k, v in kwargs.items()}
        return self.get_native_queryset(this, **kwargs)

    def assert_equivalent(self, first, second, message):
        # type: (SqlWithParams, SqlWithParams) -> None
        """ Checks that real and lazy results are equivalent."""
        sql1, params1 = normalize(first)
        sql2, params2 = normalize(second)
        if sql1 != sql2:  # pragma: no cover
            self.logger.error(
                "[PQ] %s:\n%s" % (message, '\n'.join(
                    (sql1, sql2))))
            raise SqlMappingFailed(sql1, sql2)
        if params1 != params2:  # pragma: no cover
            self.logger.error(
                "[PQ] %s:\n%s" % (message, '\n'.join(
                    (sql1, repr(params1), repr(params2)))))
            raise ParamsMappingFailed(sql1, params1, params2)

    def cache_result(self, cache, cache_key, lazy_qs, real_qs=None):
        # type: (QueryCache, tuple, QS, Optional[QS]) -> RawQuerySet
        """ Caches queryset if it is possible.

        :param cache: cache for current argument list
        :param cache_key: cache key for current call
        :param lazy_qs: function call result with Lazy-parameters
        :param real_qs: native function call result
        """

        lazy = lazy_qs.query.sql_with_params()

        if real_qs is not None:
            real = real_qs.query.sql_with_params()
            self.assert_equivalent(lazy, real, "Can't cache queryset")

        sql, params = lazy

        raw_qs = RawQuerySet(sql, params=params, model=lazy_qs.model)

        cache[cache_key] = raw_qs
        return raw_qs

    @staticmethod
    def get_normalized_queryset(qs):
        # type: (RawQuerySet) -> RawQuerySet
        """
        Returns a copy of cached queryset with SQL query normalized respecting
        current actual parameters values.
        """
        sql, params = normalize(qs.raw_query, qs.params)

        return RawQuerySet(sql, model=qs.model, params=params)

    def do_call(self, this, **kwargs):
        """ Handles cache hits and misses
        :param this: "self" for wrapped method.
        """
        signature = tuple(sorted(kwargs))
        cache_key = self.get_cache_key(kwargs[k] for k in signature)
        # argument list cache
        cache = self.cache[signature]

        if self.DEBUG:
            # computing native queryset without any manupulations
            expected_qs = self.get_native_queryset(this, **kwargs)
            expected = expected_qs.query.sql_with_params()
        else:
            expected = expected_qs = None
        try:

            # checking if cached queryset if present for current values
            cached_qs = cache[cache_key]
            self.logger.debug("Cache hit for %s:%s\n%s" %
                              (self._func_repr, signature, cache_key))
        except KeyError:
            self.logger.debug("Cache miss for %s:%s\n%s" %
                              (self._func_repr, signature, cache_key))
            # computing native queryset if check before cache flag is active.
            if self.check:
                # check is forced in __init__ by debug value so real_sq is
                # already computed above.
                real_qs = expected_qs
            else:
                # check before cache is disabled
                real_qs = None

            lazy = self.get_lazy_result(this, **kwargs)

            try:
                # caching queryset
                raw_qs = self.cache_result(cache, cache_key, lazy, real_qs)
                # returning RawQuerySet
                return self.get_normalized_queryset(raw_qs)
            except MappingFailed:  # pragma: no cover
                if self.DEBUG:
                    raise
                # check before cache failed, returning native queryset.
                return real_qs

        # cache hit, substituting actual parameter values.

        normalized_qs = self.get_normalized_queryset(cached_qs)

        if self.DEBUG:
            # check if cached version with actual parameters and native result
            # are equal

            cached = (normalized_qs.raw_query, normalized_qs.params)
            self.assert_equivalent(cached, expected,
                                   'Cached result does not match real')
            self.logger.debug("Used cached result for %s" % self._func_repr)
        return normalized_qs
