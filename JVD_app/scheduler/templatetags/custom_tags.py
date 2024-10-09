# templatetags/custom_tags.py

from django import template

register = template.Library()

@register.filter
def croatian_day_initial(date_obj):
    # Get the day of the week as a number (Monday=1, Sunday=7)
    day_number = date_obj.isoweekday()
    initials = ['P', 'U', 'S', 'Č', 'P', 'S', 'N']
    return initials[day_number - 1]

@register.filter
def croatian_month_name(date_obj):
    months = [
        'Siječanj', 'Veljača', 'Ožujak', 'Travanj', 'Svibanj', 'Lipanj',
        'Srpanj', 'Kolovoz', 'Rujan', 'Listopad', 'Studeni', 'Prosinac'
    ]
    month_number = date_obj.month
    return months[month_number - 1]
