from django.shortcuts import redirect, render


def contact(request):
    return render(request, "info/contact.html")


def developer(request):
    return render(request, "info/developer.html")
