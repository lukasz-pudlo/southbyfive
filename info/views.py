
from django.shortcuts import render, redirect


def contact(request):
    return render(request, 'info/contact.html')
