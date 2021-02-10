from django import template
register = template.Library()


@register.filter
def running_total(usages):
    print(usages)
    return sum(usage.get('total_price') for usage in usages)