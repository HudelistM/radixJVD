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

@register.filter
def reorder_shifts(shift_types):
    # Define the desired full order of shifts
    order = [
        "1. Smjena", 
        "2.smjena (Priprema od 7:00)", 
        "Priprema od 19:00", 
        "JANAF 1.smjena", 
        "JANAF 2.Smjena", 
        "Slobodan Dan 1", 
        "Slobodan Dan 2", 
        "Godišnji odmor", 
        "Bolovanje", 
        "INA 1.Smjena", 
        "INA 2. Smjena"
    ]
    
    # Create a map of shift names to their respective order index
    order_map = {name: index for index, name in enumerate(order)}
    
    # Sort the shifts based on the predefined order
    sorted_shifts = sorted(shift_types, key=lambda s: order_map.get(s.name, len(order_map)))
    
    return sorted_shifts

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