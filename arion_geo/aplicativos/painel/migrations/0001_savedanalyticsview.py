from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="SavedAnalyticsView", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("name", models.CharField(max_length=80)), ("configuration", models.JSONField(default=dict)),
        ("favorite", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_analytics_views", to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ("-favorite", "name")}), migrations.AddConstraint(model_name="savedanalyticsview", constraint=models.UniqueConstraint(fields=("user", "name"), name="unique_saved_analytics_view_name"))]
