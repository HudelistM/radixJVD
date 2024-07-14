from django import template
from django.template.defaultfilters import dictsort
import itertools

register = template.Library()

DAY_TRANSLATIONS = {
    "Mon": "Pon",
    "Tue": "Uto",
    "Wed": "Sri",
    "Thu": "Čet",
    "Fri": "Pet",
    "Sat": "Sub",
    "Sun": "Ned",
}

@register.filter(name='translate_day')
def translate_day(value):
    return DAY_TRANSLATIONS.get(value[:3], value)

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})

@register.filter(name='split')
def split_string(value, key):
    """
    Returns the value turned into a list.
    """
    return value.split(key)

@register.filter
def exclude_and_sort_by_group(employees, group_to_exclude='1'):
    # Exclude group '1' and sort by 'group'
    filtered_employees = [emp for emp in employees if emp.group != group_to_exclude]
    return sorted(filtered_employees, key=lambda x: x.group)

@register.filter
def move_shifts_to_end(shift_types, shift_names_to_move):
    # Ensure shift_names_to_move is a list
    shift_names_to_move = shift_names_to_move.split(',')  # This assumes the names are passed as a comma-separated string
    normal_shifts = [s for s in shift_types if s.name not in shift_names_to_move]
    shifted_to_end = [s for s in shift_types if s.name in shift_names_to_move]
    return normal_shifts + shifted_to_end

@register.filter(name='translate_days')
def translate_days(day):
    days = {
        'Mon': 'Pon',
        'Tue': 'Uto',
        'Wed': 'Sri',
        'Thu': 'Čet',
        'Fri': 'Pet',
        'Sat': 'Sub',
        'Sun': 'Ned'
    }
    return days.get(day, day)

@register.filter
def groupby(value, arg):
    """
    Groups a list of dictionaries by a specified key.
    """
    if not value:
        return []

    # Sort the list by the specified attribute to ensure the groupby works correctly
    sorted_value = dictsort(value, arg)

    # Group the sorted list by the specified attribute
    grouped = itertools.groupby(sorted_value, key=lambda x: getattr(x, arg))

    return [{
        'grouper': key,
        'list': list(val)
    } for key, val in grouped]