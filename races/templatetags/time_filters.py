from django import template

register = template.Library()


@register.filter(name="format_timedelta")
def format_timedelta(value):
    if not value:
        return ""
    hours, remainder = divmod(value.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02}:{:02}:{:02}".format(hours, minutes, seconds)
