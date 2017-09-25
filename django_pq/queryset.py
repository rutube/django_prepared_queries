# coding: utf-8
from datetime import datetime
from django.db import connections
from django.db.models.query import RawQuerySet as DjangoRawQuerySet
from django.db.models.query_utils import InvalidQuery, deferred_class_factory

from django_pq.lazy import reveal


class RawQuerySet(DjangoRawQuerySet):
    # fixed virtual field bug in Django-1.8 for RawQuerySet

    def _clone(self):
        return RawQuerySet(self.raw_query, model=self.model, params=self.params)

    # noinspection PyProtectedMember
    def __iter__(self):
        # Cache some things for performance reasons outside the loop.
        db = self.db
        compiler = connections[db].ops.compiler('SQLCompiler')(
            self.query, connections[db], db
        )

        query = iter(self.query)

        try:
            init_order = self.resolve_model_init_order()
            model_init_names, model_init_pos, annotation_fields = init_order

            # Find out which model's fields are not present in the query.
            skip = set()
            for field in self.model._meta.concrete_fields: # XXX Here is the fix
                if field.attname not in model_init_names:
                    skip.add(field.attname)
            if skip:
                if self.model._meta.pk.attname in skip:
                    raise InvalidQuery('Raw query must include the primary key')
                model_cls = deferred_class_factory(self.model, skip)
            else:
                model_cls = self.model
            fields = [self.model_fields.get(c, None) for c in self.columns]
            converters = compiler.get_converters([
                f.get_col(f.model._meta.db_table) if f else None for f in fields
            ])
            for values in query:
                if converters:
                    values = compiler.apply_converters(values, converters)
                # Associate fields to values
                model_init_values = [values[pos] for pos in model_init_pos]
                instance = model_cls.from_db(db, model_init_names,
                                             model_init_values)
                if annotation_fields:
                    for column, pos in annotation_fields:
                        setattr(instance, column, values[pos])
                yield instance
        finally:
            # Done iterating the Query. If it has its own cursor, close it.
            if hasattr(self.query, 'cursor') and self.query.cursor:
                self.query.cursor.close()


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
