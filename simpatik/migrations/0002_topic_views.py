# Generated by Django 2.1.2 on 2018-10-14 02:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simpatik', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='topic',
            name='views',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
