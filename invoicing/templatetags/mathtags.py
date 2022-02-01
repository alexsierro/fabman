from django import template

register = template.Library()


@register.filter()
def divide(n1, n2):
    try:
        return n1 / n2
    except (ZeroDivisionError, TypeError):
        return None


@register.filter()
def floor_divide(n1, n2):
    try:
        return n1 // n2
    except (ZeroDivisionError, TypeError):
        return None


@register.filter()
def multiply(n1, n2):
    try:
        return n1 * n2
    except TypeError:
        return None