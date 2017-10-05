import mock
from django.test import TestCase

from models import TestModel, run_cached


# noinspection PyUnusedLocal
class CacheTestCase(TestCase):
    def setUp(self):
        self.t1 = TestModel.objects.create(int_field=1)
        self.t2 = TestModel.objects.create(int_field=2)

    def tearDown(self):
        super(CacheTestCase, self).tearDown()
        TestModel.objects.ftm_decorator.cache.clear()

    def test_run_cached(self):
        x = run_cached(integers=[1])
        self.assertEqual(x, self.t1)
        self.assertEqual(len(TestModel.objects.ftm_decorator.cache), 1)
        # check cache hit
        x = run_cached(integers=[1])
        self.assertEqual(x, self.t1)

    @mock.patch('testapp.models.TestManager.ftm_decorator.DEBUG',
                new_callable=mock.PropertyMock(return_value=False))
    def test_run_disable_debug(self, *args):
        x = run_cached(integers=[1])
        self.assertEqual(x, self.t1)
        with mock.patch('django.db.models.sql.compiler.SQLCompiler.as_sql',
                        side_effect=RuntimeError("check cached")):
            # cache hit - checking that no sql is compiled
            x = run_cached(integers=[1])
            self.assertEqual(x, self.t1)

    @mock.patch('testapp.models.TestManager.ftm_decorator.check',
                new_callable=mock.PropertyMock(return_value=False))
    @mock.patch('testapp.models.TestManager.ftm_decorator.DEBUG',
                new_callable=mock.PropertyMock(return_value=False))
    def test_run_disable_check(self, *args):
        x = run_cached(integers=[1])
        self.assertEqual(x, self.t1)
        self.assertEqual(len(TestModel.objects.ftm_decorator.cache), 1)
