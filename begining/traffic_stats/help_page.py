import re
from html import escape

from bs4 import BeautifulSoup, NavigableString
from bs4.element import PreformattedString
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods

FORMATTING_TAGS = {
    'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'b', 'strong', 'i', 'em', 'u',
    'ul', 'ol', 'li', 'pre', 'code', 'blockquote',
}


# Стандартные локальные семейства из меню выбора шрифта Jodit.
FONT_FAMILIES = {
    'arial,helvetica,sans-serif': 'Arial, Helvetica, sans-serif',
    'courier new,courier,monospace': "'Courier New', Courier, monospace",
    'georgia,palatino,serif': 'Georgia, Palatino, serif',
    'lucida sans unicode,lucida grande,sans-serif': "'Lucida Sans Unicode', 'Lucida Grande', sans-serif",
    'tahoma,geneva,sans-serif': 'Tahoma, Geneva, sans-serif',
    'times new roman,times,serif': "'Times New Roman', Times, serif",
    'trebuchet ms,helvetica,sans-serif': "'Trebuchet MS', Helvetica, sans-serif",
    'helvetica,sans-serif': 'Helvetica, sans-serif',
    'impact,charcoal,sans-serif': 'Impact, Charcoal, sans-serif',
    'verdana,geneva,sans-serif': 'Verdana, Geneva, sans-serif',
}


# Размеры из меню Jodit, в пикселях.
FONT_SIZES = {8, 9, 10, 11, 12, 14, 16, 18, 24, 30, 32, 34, 36, 48, 60, 72, 96}
TEXT_ALIGNMENTS = {'left', 'center', 'right', 'justify'}
LINE_HEIGHTS = {'1', '1.1', '1.2', '1.3', '1.4', '1.5', '2'}


def formatting_style(node):
    """Восстанавливает только разрешённые значения CSS."""
    styles = {}
    for declaration in node.get('style', '').split(';'):
        name, _, value = declaration.partition(':')
        name = name.strip().lower()
        value = value.strip().casefold()
        if name == 'font-family':
            key = ','.join(part.strip().strip('"\'') for part in value.split(','))
            family = FONT_FAMILIES.get(key)
            if family:
                styles[name] = family
        elif name == 'font-size':
            match = re.fullmatch(r'([0-9]{1,2})px', value)
            if match and int(match[1]) in FONT_SIZES:
                styles[name] = f'{int(match[1])}px'
        elif name == 'line-height' and value in LINE_HEIGHTS:
            styles[name] = value
        elif name == 'text-align' and value in TEXT_ALIGNMENTS:
            styles[name] = value
    if not styles:
        return ''
    rules = '; '.join(f'{name}: {value}' for name, value in styles.items())
    return f' style="{rules}"'


def clean_description(content):
    """Сохраняет разрешённые теги и оформление текста."""
    fragment = BeautifulSoup(content, 'html.parser')
    for node in fragment.find_all(['script', 'style', 'svg', 'math', 'iframe', 'template']):
        node.decompose()

    def serialize(node):
        if isinstance(node, PreformattedString):
            return ''
        if isinstance(node, NavigableString):
            return escape(str(node))
        children = ''.join(serialize(child) for child in node.children)
        if node.name not in FORMATTING_TAGS and node.name != 'span':
            return children
        style = formatting_style(node)
        if node.name == 'span' and not style:
            return children
        if node.name == 'br':
            return '<br>'
        return f'<{node.name}{style}>{children}</{node.name}>'

    return serialize(fragment)


def find_description(site):
    return FlatPage.objects.filter(url=reverse('traffic_stats:help'), sites=site).order_by('pk').first()


def show_help(request):
    page = find_description(get_current_site(request))
    description = page.content if page else render_to_string('traffic_stats/help_default.html')
    return render(request, 'traffic_stats/help.html', {
        'description': mark_safe(clean_description(description)),
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def edit_help(request):
    site = get_current_site(request)
    page = find_description(site)
    error = None
    if request.method == 'POST':
        description = request.POST.get('description', '')
        if len(description) > 100_000:
            error = 'Описание должно быть не длиннее 100 000 символов.'
            description = description[:100_000]
        else:
            description = clean_description(description)
            if not BeautifulSoup(description, 'html.parser').get_text(strip=True):
                error = 'Введите описание.'
        if not error:
            # Храним справку среди существующих редактируемых страниц сайта.
            with transaction.atomic():
                type(site).objects.select_for_update().get(pk=site.pk)
                page = find_description(site)
                if page is None:
                    page = FlatPage.objects.create(url=reverse('traffic_stats:help'),
                                                   title='Помощь по заполнению', content=description)
                    page.sites.add(site)
                else:
                    page.content = description
                    page.save(update_fields=['content'])
            return redirect('traffic_stats:help')
    else:
        description = page.content if page else render_to_string('traffic_stats/help_default.html')
    return render(request, 'traffic_stats/help_edit.html', {
        'description': clean_description(description), 'error': error,
    })
