# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TestModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('int_field', models.IntegerField(default=0, blank=True)),
                ('dt_field', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
