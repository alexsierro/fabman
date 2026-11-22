"""Members count over the time, computed from the date added and the date resigned of the members.

Many members were added before the date added was recorded: for them, the date of their first usage is used.
"""
import calendar
import math
from dataclasses import dataclass
from datetime import date

from django.db.models import Min
from django.db.models.functions import TruncDate
from django.utils.formats import date_format

from .models import Member

# viewBox of the chart, in SVG units
CHART_WIDTH = 900
CHART_HEIGHT = 300
MARGIN_LEFT = 44
MARGIN_RIGHT = 12
MARGIN_TOP = 12
MARGIN_BOTTOM = 28
TARGET_Y_TICKS = 5

ALL_MEMBER_TYPES = 'all'
# not counted in the members by default
NON_MEMBER_TYPES = ['alias', 'no_member', 'hes', 'ell', 'interne']


@dataclass
class Point:
    date: date
    count: int
    x: float = 0
    y: float = 0


@dataclass
class YearRow:
    year: int
    joined: int
    resigned: int
    count: int


def members_for_type(member_type):
    """By default the NON_MEMBER_TYPES are excluded, ALL_MEMBER_TYPES includes them."""
    members = Member.objects.all()
    if member_type == ALL_MEMBER_TYPES:
        return members
    if member_type:
        return members.filter(member_type=member_type)
    return members.exclude(member_type__in=NON_MEMBER_TYPES)


def member_periods(members):
    """(start, date resigned) of each member, with the start of the member without a date added and without
    usage unknown (None)."""
    rows = members.annotate(first_usage=Min(TruncDate('usage__date')))         .values_list('date_added', 'first_usage', 'date_resigned')
    periods = []
    from_first_usage = 0
    for added, first_usage, resigned in rows:
        if added is None and first_usage is not None:
            from_first_usage += 1
        periods.append((added or first_usage, resigned))
    return periods, from_first_usage


def _month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _next_month(day):
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _count_at(periods, day):
    # an unknown start means the member was there before the history starts
    return sum(1 for added, resigned in periods
               if (added is None or added <= day) and (resigned is None or resigned > day))


def monthly_counts(periods, today):
    """Count at the end of each month, from the first known date up to today."""
    known = [day for period in periods for day in period if day is not None and day <= today]
    if not known:
        return []
    points = []
    month = min(known).replace(day=1)
    while month <= today:
        day = min(_month_end(month), today)
        points.append(Point(day, _count_at(periods, day)))
        month = _next_month(month)
    return points


def yearly_rows(periods, points, today):
    rows = []
    for year in sorted({point.date.year for point in points}, reverse=True):
        end = min(date(year, 12, 31), today)
        rows.append(YearRow(
            year=year,
            joined=sum(1 for added, _ in periods if added is not None and added.year == year and added <= today),
            resigned=sum(1 for _, resigned in periods
                         if resigned is not None and resigned.year == year and resigned <= today),
            count=_count_at(periods, end),
        ))
    return rows


def _nice_step(max_value):
    raw = max(max_value, 1) / TARGET_Y_TICKS
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return max(int(factor * magnitude), 1)


def chart(points):
    """Places the points in the SVG viewBox and returns the axes."""
    plot_width = CHART_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = CHART_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    bottom = MARGIN_TOP + plot_height

    step = _nice_step(max((point.count for point in points), default=0))
    y_max = step * max(math.ceil(max((point.count for point in points), default=0) / step), 1)

    for index, point in enumerate(points):
        point.x = MARGIN_LEFT + (plot_width * index / (len(points) - 1) if len(points) > 1 else plot_width / 2)
        point.y = bottom - plot_height * point.count / y_max

    y_ticks = [{'value': value, 'y': bottom - plot_height * value / y_max}
               for value in range(0, y_max + 1, step)]
    # a label for each January, and for the first month when the history does not start in January
    x_ticks = [{'label': point.date.year, 'x': point.x} for index, point in enumerate(points)
               if point.date.month == 1 or index == 0]
    if len(x_ticks) > 1 and x_ticks[1]['x'] - x_ticks[0]['x'] < 40:
        del x_ticks[0]

    line = ' '.join(f'{point.x:.1f},{point.y:.1f}' for point in points)
    area = f'{points[0].x:.1f},{bottom} {line} {points[-1].x:.1f},{bottom}' if points else ''
    return {
        'width': CHART_WIDTH,
        'height': CHART_HEIGHT,
        'left': MARGIN_LEFT,
        'right': CHART_WIDTH - MARGIN_RIGHT,
        'plot_width': plot_width,
        'top': MARGIN_TOP,
        'bottom': bottom,
        'line': line,
        'area': area,
        'y_ticks': y_ticks,
        'x_ticks': x_ticks,
    }


def statistics(member_type='', today=None):
    today = today or date.today()
    periods, from_first_usage = member_periods(members_for_type(member_type))
    points = monthly_counts(periods, today)
    # places the points, before they are serialised for the tooltip
    chart_axes = chart(points) if points else None
    return {
        'points': points,
        'chart_points': [{'label': date_format(point.date, 'YEAR_MONTH_FORMAT'), 'count': point.count,
                          'x': round(point.x, 1), 'y': round(point.y, 1)} for point in points],
        'chart': chart_axes,
        'years': yearly_rows(periods, points, today),
        'current_count': _count_at(periods, today),
        'from_first_usage': from_first_usage,
        'unknown_start': sum(1 for start, _ in periods if start is None),
    }
