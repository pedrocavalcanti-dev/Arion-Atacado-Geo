from django.conf import settings
from django.db import models


class SavedAnalyticsView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_analytics_views")
    name = models.CharField(max_length=80)
    configuration = models.JSONField(default=dict)
    favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-favorite", "name")
        constraints = [models.UniqueConstraint(fields=("user", "name"), name="unique_saved_analytics_view_name")]
