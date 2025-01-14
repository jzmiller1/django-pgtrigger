# Generated by Django 2.2 on 2022-08-10 19:13

import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0007_auto_20220808_1055'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchModel',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('body_vector', django.contrib.postgres.search.SearchVectorField()),
                ('title_body_vector', django.contrib.postgres.search.SearchVectorField()),
                ('title', models.CharField(max_length=128)),
                ('body', models.TextField()),
            ],
        ),
    ]
