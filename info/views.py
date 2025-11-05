from django.shortcuts import redirect, render


def contact(request):
    return render(request, "info/contact.html")
