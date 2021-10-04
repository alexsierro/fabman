import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from unidecode import unidecode

from invoicing.models import Resource, Usage, ResourceCategory
from legacy.models import CheckKey
from members.models import Member, Project


def allow_all_origins(func):
    def inner(*args, **kwargs):
        response = func(*args, **kwargs)
        response['access-control-allow-origin'] = '*'
        return response

    return inner


@allow_all_origins
def user(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    return HttpResponse(member.visa)


@allow_all_origins
def user2(request, uid):
    member = get_object_or_404(Member, rfid=uid)
    response = {'visa': member.visa, 'animateur': member.is_staff}
    return JsonResponse(response)


@allow_all_origins
def usage(request, resource, visa, time, project=None):
    resource = get_object_or_404(Resource, slug=resource)
    member = get_object_or_404(Member, visa=visa)

    if project:
        project = Project.objects.get(member=member, name=project)

    qty = Decimal(time) / Decimal(resource.logger_multiplier)

    usage = Usage.objects.create(resource=resource, member=member, project=project, qty=qty, total_price=0)

    return HttpResponse("ok")


@allow_all_origins
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


@allow_all_origins
def check(request, api_key, email):
    if CheckKey.objects.filter(key=api_key).first() is None:
        raise PermissionDenied()

    def clean(text):
        return unidecode(re.sub('\W+', '', text).lower())
        pass

    response = 'not a member'

    members = Member.objects.all()
    for member in members:
        if member.mail and clean(member.mail) == clean(email):
            response = "ok"

    return HttpResponse(response)


@allow_all_origins
def projects(request, visa):
    user = get_object_or_404(Member, visa=visa)
    projects = [project.name for project in Project.objects.filter(member=user)]

    return JsonResponse(projects, safe=None)
