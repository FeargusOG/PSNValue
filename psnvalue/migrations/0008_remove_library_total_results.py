# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-06-08 09:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('psnvalue', '0007_gameratings_weighted_rating'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='library',
            name='total_results',
        ),
    ]