Django Prepared Queries
=======================

[![PyPI version](https://badge.fury.io/py/django_prepared_queries.svg)](https://badge.fury.io/py/django_prepared_queries)
[![codecov](https://codecov.io/gh/rutube/django_prepared_queries/branch/master/graph/badge.svg)](https://codecov.io/gh/rutube/django_prepared_queries)
[![Build Status](https://travis-ci.org/rutube/django_prepared_queries.svg)](https://travis-ci.org/rutube/django_prepared_queries)
`django_pq` allows to cache SQL generated with Django ORM and reuse cached 
queries with only substituting new parameters values.

Short example
-------------

Some developers think that Django ORM is slow. It is true if your code looks 
like this:

```python
from django.db import models
from countries_field.fields import countries_isnull, countries_contains

    
def filter_queryset(self, domains=None, **kwargs):
    query = models.Q()
    if domains:
        query &= ((models.Q(allow_domains__name__in=domains) |
                   models.Q(allow_domains__isnull=True)) &
                  (~models.Q(deny_domains__name__in=domains) |
                   models.Q(deny_domains__isnull=True)))
    else:
        query &= (models.Q(allow_domains__isnull=True) &
                  models.Q(deny_domains__isnull=True))
    user_agent = kwargs.pop('user_agent', None)
    if user_agent:
        query &= (models.Q(user_agents=user_agent) |
                  models.Q(user_agents__isnull=True))
    else:
        query &= models.Q(user_agents__isnull=True)

    country = kwargs.pop('country')
    if country:
        query &= countries_isnull() | countries_contains([country])
    else:
        query &= countries_isnull()

    return self.get_queryset().filter(query)
```

Generated SQL query is quite long and in our case takes up to 50% of HTTP 
request handling. What if we could cache generated SQL and just substitute
actual parameters values instead of repeating heavy queryset filtering?

Well, with `django_pq` you can do following.

```python

from django.db import models
import django_pq


# Add caching decorator for heavy queryset constructing method
@django_pq.substitute_lazy()
def filter_queryset_lazy(self, domains=None, **kwargs):
    query = models.Q()
    
    # branches in decorated function must check real value instead of Lazy 
    # wrapper, because actual value this time could be False.
    if django_pq.reveal(domains):
        # You pass Lazy wrappers in to any lookup parameters for queryset,
        # and these Lazy wrappers remain lazy until it's time to query the 
        # database.
        query &= ((models.Q(allow_domains__name__in=domains) |
                   models.Q(allow_domains__isnull=True)) &
                  (~models.Q(deny_domains__name__in=domains) |
                   models.Q(deny_domains__isnull=True)))
    else:
        query &= (models.Q(allow_domains__isnull=True) &
                  models.Q(deny_domains__isnull=True))
                
    # ... 
    # 
    # modify other parts of queryset constuction with respect of lazy nature of
    # arguments.
    
    return self.get_queryset().filter(query)
        
def filter_queryset(self, **kwargs):
    # wrap parameters into context manager so Lazy wrappers could get actual
    # values when they need.
    with django_pq.LazyContext(**kwargs):
        queryset = self.filter_queryset_lazy(**kwargs)
        # queryset is now RawQuerySet with Lazy wrappers in params.
        
        # database queries should be performed within LazyContext.
        return queryset.first()
        
```

That's it - your queryset generation code is cached.

Rules for preparing code for caching
------------------------------------

1. Don't check Lazy wrappers for anything - use `reveal()` to check actual 
parameter values. I.e. `Lazy(None) is not None` is always true (this it not 
what you meant really).
2. Don't pass Model instances as parameters. This allows Model instance method 
calls and may lead to implicit branching that could not be detected from actual 
parameters list. Instead, pass primary key values.
3. Don't query DB within cached method - branching could not be detected.
4. Add all `if` expressions as new parameters to your method - it would be 
usefull for proper caching.
5. Don't pass empty lists as parameter values. Django ORM checks it for 
emptiness and removes empty lookups from WhereNode (with respect of boolean 
algebra rules). Pass `None` instead.
6. Don't use and volatile values like `datetime.now() `in queryset filtering;
Pass it as a parameter instead.
7. Test your code with 100% branch coverage *before* adding caching.

Normalize parameters
--------------------

To help you to normalize parameters passed into cached function `LazyContext` 
may call a list of callables and return normalized parameter values when 
entering context.

```python
from django.db import models
from django_pq import LazyContext


def model_to_pk(kwargs):
    for k, v in list(kwargs.items()):
        if isinstance(v, models.Model):
            kwargs[k] = v.pk  # Model -> Model.pk
    return kwargs 
    
def empty_list_to_none(kwargs):
    for k, v in list(kwargs.items()):
        if isinstance(v, list) and not v:
            kwargs[k] = None  # [] -> None
    return kwargs


def filter_queryset(self, **kwargs):    
    with LazyContext(model_to_pk, empty_list_to_none, **kwargs) as lazy_kwargs:
        queryset = self.filter_queryset_lazy(**lazy_kwargs)
        return queryset.first()

```

How it works
------------

1. First, `substitute_lazy()` decorator wraps all parameters with Lazy wrapper,
and with wrapper remains "lazy" until SQL generation is completed.
2. Your code is called twice, with lazy wrappers as arguments and with actual 
values, to ensure that lazy result is identical to native queryset.
3. If SQL and normalized parameters match, a `RawQuerySet` instance is cached
with Lazy wrappers as parameters.
4. Cache key respects presence of any argument and certain constants like 
`True, False, 0, 1, None`.
5. In "cache hit" situation new actual parameters values are substituted from 
LazyContext into `RawQuerySet.params` and that's result of caching.
6. If you are doing it right, `RawQuerySet` will act almost like normal 
`QuerySet`, or (more correctly) as your Model instances iterator.

