# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-10-03 11:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('psnvalue', '0014_auto_20170809_1702'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamelist',
            name='image_data',
            field=models.BinaryField(blank=True),
        ),
    ]
