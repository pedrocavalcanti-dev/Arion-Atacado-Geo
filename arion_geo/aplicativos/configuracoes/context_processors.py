from .models import UserPreference


def user_theme(request):
    user = request.user
    theme = "dark"
    if user.is_authenticated:
        theme = UserPreference.objects.filter(user_id=user.pk).values_list("theme", flat=True).first() or theme
    return {"user_theme": theme}
