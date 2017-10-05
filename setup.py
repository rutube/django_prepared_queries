from setuptools import setup


try:
    # noinspection PyPackageRequirements
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()


setup(
    name='django_prepared_queries',
    long_description=read_md('README.md'),
    version='0.2.1',
    packages=['django_pq'],
    url='https://github.com/rutube/django_prepared_queries',
    license='Beer license',
    author='Tumbler',
    author_email='zimbler@bk.ru',
    description='Caches SQL queries built with Django ORM',
    install_requires=['typing', 'Django>=1.8,<2.0', 'six']
)
