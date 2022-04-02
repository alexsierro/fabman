from django import template

register = template.Library()


@register.filter
def running_total(usages: object) -> object:
    print(usages)
    return sum(usage.get('total_price') for usage in usages)


@register.filter
def format_currency(value: object) -> object:
    step1 = '{:x>7.2f}'.format(value)
    step2 = step1.replace('x', ' ')
    step3 = step2.replace('.00', '.00')
    return f' {step3}'


@register.filter
def format_quantity(value: object) -> object:
    step1 = '{:x>7.1f}'.format(value)
    step2 = step1.replace('x', ' ')
    step3 = step2.replace('.0', '.0')
    return f' {step3}'


@register.filter
def must_use_projects(usages_list):
    print(usages_list)
    return True
