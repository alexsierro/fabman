import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from unidecode import unidecode

from invoicing.models import Resource, Usage, ResourceCategory
from legacy.models import CheckKey
from members.models import Member, Project


def user(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    return HttpResponse(member.visa)


def user2(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    response = {'visa': member.visa, 'animateur': member.is_staff}
    return JsonResponse(response)


def usage(request, resource, visa, time, project=None):
    resource = get_object_or_404(Resource, slug=resource)
    member = get_object_or_404(Member, visa=visa)

    if project:
        project = Project.objects.get(member=member, name=project)

    qty = int(time) / Decimal(resource.logger_multiplier)

    usage = Usage.objects.create(resource=resource, member=member, project=project, qty=qty, total_price=0)

    return HttpResponse("ok")


def items(request):
    categories = ResourceCategory.objects.all()

    ret = []

    for category in categories:

        resources = Resource.objects.filter(category=category).exclude(widget=None)

        category_items = []

        for resource in resources:
            item = {
                'slug': resource.slug,
                'name': resource.name,
                'type': resource.widget.name,
                'unit': resource.unit.name,
                'price_member': resource.price_member,
                'price_non_member': resource.price_not_member,
            }

            if resource.on_submit:
                item['on_submit'] = resource.on_submit

            category_items.append(item)

        entry = {'category': category.name, 'items': category_items}
        ret.append(entry)

    return JsonResponse(ret, safe=False)


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


def projects(request, visa):
    user = get_object_or_404(Member, visa=visa)
    projects = [project.name for project in Project.objects.filter(member=user)]

    return JsonResponse(projects, safe=None)
