from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(
    name='django_prepared_queries',
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='0.3.1',
    packages=['django_pq'],
    url='https://github.com/rutube/django_prepared_queries',
    license='Beer license',
    author='Tumbler',
    author_email='zimbler@bk.ru',
    description='Caches SQL queries built with Django ORM',
    install_requires=['typing', 'Django>=1.8,<2.2', 'six']
)
