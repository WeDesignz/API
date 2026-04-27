from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('Catalog', '0011_pdfclient_customer_mobile'),
    ]

    operations = [
        migrations.CreateModel(
            name='LensSearchEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_authenticated', models.BooleanField(default=False)),
                ('source', models.CharField(blank=True, default='', max_length=64)),
                ('session_id', models.CharField(blank=True, default='', max_length=128)),
                ('referer', models.TextField(blank=True, default='')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('device_type', models.CharField(blank=True, default='', max_length=20)),
                ('image_file_name', models.CharField(blank=True, default='', max_length=255)),
                ('image_mime_type', models.CharField(blank=True, default='', max_length=100)),
                ('image_size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('image_storage_path', models.CharField(blank=True, default='', max_length=500)),
                ('num_results_requested', models.PositiveIntegerField(default=20)),
                ('results_count', models.PositiveIntegerField(default=0)),
                ('total_matched', models.PositiveIntegerField(default=0)),
                ('result_product_numbers', models.JSONField(blank=True, default=list)),
                ('success', models.BooleanField(default=False)),
                ('error_message', models.TextField(blank=True, default='')),
                ('processing_time_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('searched_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lens_search_events', to='auth.user')),
            ],
            options={
                'verbose_name': 'Lens Search Event',
                'verbose_name_plural': 'Lens Search Events',
                'db_table': 'lens_search_event',
                'ordering': ['-searched_at'],
            },
        ),
    ]

