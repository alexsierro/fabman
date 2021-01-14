import re
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from unidecode import unidecode

from invoicing.models import Resource, Usage
from legacy.models import CheckKey
from members.models import Member, Project


def user(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    return HttpResponse(member.visa)


def user2(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    response = {'visa': member.visa, 'animateur': member.is_staff}
    return JsonResponse(response)


def usage(request, resource, user, time, project=None):
    resource = get_object_or_404(Resource, slug=resource)
    member = get_object_or_404(Member, visa=user)

    if project:
        project = Project.objects.get(member=member, name=project)

    qty = int(time) / Decimal(resource.logger_multiplier)

    usage = Usage.objects.create(resource=resource, member=member, project=project, qty=qty, total_price=0)

    return HttpResponse("ok")


def items(request):
    return HttpResponse("ok")


def check(request, api_key, name, surname):
    if CheckKey.objects.filter(key=api_key).first() is None:
        return HttpResponse(status=403)

    def clean(text):
        return unidecode(re.sub('\W+', '', text).lower())
        pass

    response = 'not a member'

    members = Member.objects.all()
    for member in members:
        if clean(name) == clean(member.name) and clean(surname) == clean(member.surname):
            response = "ok"

    return HttpResponse(response)
