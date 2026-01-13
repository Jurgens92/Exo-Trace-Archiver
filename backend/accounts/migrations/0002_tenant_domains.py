# Generated migration for adding domains field to Tenant model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='domains',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Comma-separated list of organization email domains for direction detection (e.g., contoso.com,contoso.onmicrosoft.com)'
            ),
        ),
    ]
