from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0019_add_webhook_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, verbose_name='البريد الإلكتروني')),
                ('token', models.CharField(max_length=100, unique=True, verbose_name='التوكن')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('expires_at', models.DateTimeField(verbose_name='تاريخ الانتهاء')),
                ('used', models.BooleanField(default=False, verbose_name='مستخدم')),
            ],
            options={
                'verbose_name': 'توكن تفعيل البريد',
                'verbose_name_plural': 'توكنات تفعيل البريد',
            },
        ),
    ]
