# Generated by Django 2.1.2 on 2018-11-03 07:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simpatik', '0005_auto_20181101_2224'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='picture',
            field=models.ImageField(blank=True, upload_to='items'),
        ),
        migrations.AlterField(
            model_name='item',
            name='booked_quantity',
            field=models.IntegerField(default=0),
        ),
    ]
