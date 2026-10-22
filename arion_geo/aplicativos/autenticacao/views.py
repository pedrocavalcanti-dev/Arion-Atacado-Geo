from django.shortcuts import redirect


def home(request):
    destination = "painel:index" if request.user.is_authenticated else "autenticacao:login"
    return redirect(destination)
