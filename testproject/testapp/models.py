from django.db import models
from django.utils.timezone import now
from django_pq import reveal, substitute_lazy, LazyContext


class TestManager(models.Manager):

    # for mocking purposes
    ftm_decorator = substitute_lazy()

    def _filter_test_model(self, integers=None, dt=None):
        kwargs = {}
        if reveal(integers):
            kwargs['int_field__in'] = integers
        if reveal(dt):
            kwargs['dt'] = dt
        return TestModel.objects.filter(**kwargs)

    filter_test_model = ftm_decorator(_filter_test_model)


class TestModel(models.Model):
    objects = TestManager()

    int_field = models.IntegerField(default=0, blank=True)
    dt_field = models.DateTimeField(default=now)


def list_to_none(kwargs):
    integers = kwargs.get('integers')
    if isinstance(integers, (list, tuple)) and not integers:
        kwargs['integers'] = None
    return kwargs


def run_cached(**kwargs):
    with LazyContext(list_to_none, **kwargs) as lazy_kwargs:
        qs = TestModel.objects.filter_test_model(**lazy_kwargs)
        return qs[0]