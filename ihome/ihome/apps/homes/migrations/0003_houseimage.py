# Generated by Django 3.1.7 on 2021-04-02 08:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('homes', '0002_facility_house'),
    ]

    operations = [
        migrations.CreateModel(
            name='HouseImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('url', models.CharField(max_length=256)),
                ('house', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='homes.house')),
            ],
            options={
                'db_table': 'tb_house_image',
            },
        ),
    ]
