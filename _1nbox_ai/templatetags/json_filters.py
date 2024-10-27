from django import template
import json

register = template.Library()

@register.filter(name='json_parse')
def json_parse(value):
    try:
        return json.loads(value)
    except:
        return {}
