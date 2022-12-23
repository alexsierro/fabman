import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404
from unidecode import unidecode

from invoicing.models import Resource, Usage, ResourceCategory
from invoicing.tariff import PRICE_MEMBER, PRICE_NON_MEMBER, PRICE_CONSUMABLE_ONLY
from legacy.models import CheckKey
from members.models import Member, Project, ProjectCard


def allow_all_origins(func):
    def inner(*args, **kwargs):
        response = func(*args, **kwargs)
        response['access-control-allow-origin'] = '*'
        return response

    return inner


@allow_all_origins
def user(request, uid):
    member = Member.objects.filter(rfid=uid).first()
    if member:
        return HttpResponse(member.visa)

    project_card = ProjectCard.objects.filter(rfid=uid).first()
    if project_card:
        return HttpResponse(f'{project_card.project.name}@{project_card.project.member.visa}')

    raise Http404()


@allow_all_origins
def user2(request, uid):
    member = Member.objects.filter(rfid=uid).first()
    if member:
        response = {'visa': member.visa, 'animateur': member.is_staff, 'tariff': member.get_tariff}
        return JsonResponse(response)

    project_card = ProjectCard.objects.filter(rfid=uid).first()
    if project_card:
        visa = f'{project_card.project.name}@{project_card.project.member.visa}'
        response = {'visa': visa, 'animateur': False}
        return JsonResponse(response)

    raise Http404()

@allow_all_origins
def usage(request, resource, visa, time, project=None):
    resource = get_object_or_404(Resource, slug=resource)
    member = Member.objects.filter(visa=visa).first()

    if member is None:
        # try to find a project@visa structure, useful for ProjectCard
        splitted = visa.rsplit('@',1)
        if len(splitted) == 2:
            visa = splitted[1]
            project = splitted[0]
            member = get_object_or_404(Member, visa=visa)
        else:
            raise Http404()

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

        if len(category_items) > 0:
            entry = {'category': category.name, 'items': category_items}
            ret.append(entry)

    return JsonResponse(ret, safe=False)


def fill_category(category, list):
    # recursively fill the category with subcategories and items
    name = category.name if category else 'root'
    entry = {'type': 'category', 'name': name}

    category_items = []

    sub_categories = ResourceCategory.objects.filter(parent=category)
    for subcategory in sub_categories:
        fill_category(subcategory, category_items)

    if category:  # avoid resources without category to be mapped with root category
        resources = Resource.objects.filter(category=category).exclude(widget=None)
        for resource in resources:
            item = {
                'type': 'resource',
                'slug': resource.slug,
                'name': resource.name,
                'widget': resource.widget.name,
                'unit': resource.unit.name,
                PRICE_MEMBER: resource.price_member,
                PRICE_NON_MEMBER: resource.price_not_member,
                PRICE_CONSUMABLE_ONLY: resource.price_consumable_only
            }

            if resource.on_submit:
                item['on_submit'] = resource.on_submit

            category_items.append(item)

    entry['items'] = category_items
    list.append(entry)


@allow_all_origins
def items2(request):
    list = []
    fill_category(None, list)
    return JsonResponse(list, safe=False)

@allow_all_origins
def check(request, api_key, email):
    if CheckKey.objects.filter(key=api_key).first() is None:
        raise PermissionDenied()

    def clean(text):
        return unidecode(re.sub('\W+', '', text).lower())
        pass

    response = 'not a member'

    if Member.objects.filter(mail=email).exists():
        response = "ok"

    return HttpResponse(response)


@allow_all_origins
def projects(request, visa):
    user = Member.objects.filter(visa=visa).first()
    if user:
        projects = [project.name for project in Project.objects.filter(member=user)]
    else:
        projects = []

    return JsonResponse(projects, safe=None)
