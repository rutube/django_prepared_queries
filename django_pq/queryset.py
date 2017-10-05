# coding: utf-8
from datetime import datetime

import django

from django_pq.lazy import reveal


__all__ = ['normalize', 'RawQuerySet']


if django.VERSION < (1, 9, 0):
    from .fixups import RawQuerySet
else:
    from django.db.models.query import RawQuerySet


def datetime_to_str(p):
    if isinstance(p, datetime):
        return str(p)
    return p


def normalize(sql, params=None):
    """ Reveals actual parameter values and flattens params for IN lookups."""
    if params is None:
        sql, params = sql

    placeholders = []
    real_params = []
    for p in map(reveal, params):
        if isinstance(p, (list, tuple)):
            # IN(%s) -> IN(%s,%s,%s)
            placeholders.append(', '.join(['%s'] * len(p)))
            real_params.extend(p)
        else:
            placeholders.append('%s')
            real_params.append(p)
    return sql % tuple(placeholders), tuple(map(datetime_to_str, real_params))
