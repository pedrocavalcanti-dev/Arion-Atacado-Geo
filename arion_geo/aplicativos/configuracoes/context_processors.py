from .models import UserPreference
from config.releases import current_version


def user_theme(request):
    user = request.user
    theme = "dark"
    if user.is_authenticated:
        theme = UserPreference.objects.filter(user_id=user.pk).values_list("theme", flat=True).first() or theme
    return {"user_theme": theme}


def arion_version(request):
    return {"arion_version": current_version()}
