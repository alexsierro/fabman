from django import template

register = template.Library()


@register.filter
def running_total(usages: object) -> object:
    return sum(usage.get('total_price') for usage in usages)


@register.filter
def format_currency(value: object) -> object:
    step1 = '{:x>7.2f}'.format(value)
    step2 = step1.replace('x', ' ')
    step3 = step2.replace('.00', '.00')
    return f' {step3}'


@register.filter
def chf(value):
    """An amount the Swiss way, 10'711.05: for the pages, the invoices keep format_currency."""
    if value in (None, ''):
        return ''
    return f'{value:,.2f}'.replace(',', "'")


@register.filter
def format_quantity(value: object) -> object:
    step1 = '{:x>7.1f}'.format(value)
    step2 = step1.replace('x', ' ')
    step3 = step2.replace('.0', '.0')
    return f' {step3}'


@register.filter
def must_use_projects(usages_list):
    return True
