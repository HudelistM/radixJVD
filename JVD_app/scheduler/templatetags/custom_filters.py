from django import template

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