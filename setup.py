from distutils.core import setup

setup(
    name='django_prepared_queries',
    version='0.1',
    packages=['django_pq'],
    url='https://github.com/rutube/django_prepared_queries',
    license='Beer license',
    author='Tumbler',
    author_email='zimbler@bk.ru',
    description='Caches SQL queries built with Django ORM',
    setup_requires=['typing', 'Django>=1.8,<1.9']
)
