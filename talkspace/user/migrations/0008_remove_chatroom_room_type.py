# Generated by Django 5.1.4 on 2025-02-17 10:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0007_chatroom_room_type_alter_chatroom_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chatroom',
            name='room_type',
        ),
    ]
