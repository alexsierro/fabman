from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import InscriptionForm


def index(request):
    return HttpResponse("Hello world")


def new_inscription(request):
    if request.method == "POST":
        form = InscriptionForm(request.POST)
        if form.is_valid():
            inscription = form.save(commit=False)
            inscription.published_date = timezone.now()
            inscription.save()
            return redirect('new_inscription_infos.html')
    else:
        form = InscriptionForm()
    return render(request, 'new_inscription.html', {'form': form})


def new_inscription_infos(request):
    return render(request, 'new_inscription_infos.html')
