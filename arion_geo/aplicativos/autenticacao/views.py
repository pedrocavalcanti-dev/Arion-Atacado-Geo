from django.shortcuts import redirect


def home(request):
    destination = "mapa:index" if request.user.is_authenticated else "autenticacao:login"
    return redirect(destination)
