from django import template
from django.urls import reverse
from ..models import Job

register = template.Library()

@register.simple_tag(takes_context=True)
def prepare_context(context):
    request = context.request
    user = request.user
    if user.is_authenticated:
        context['new_count'] = Job.new_count(user) or ''
    context['urls'] = {
        'new_count_text': reverse('new_count_text'),
    }
    return ''
