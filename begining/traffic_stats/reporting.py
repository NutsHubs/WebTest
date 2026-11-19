"""Shared category/subscriber/channel layout for HTML and file exports."""
CATEGORY_HEADINGS = [
    ('federal', 'Федеральные каналы'),
    ('international', 'Международные каналы'),
    ('regional', 'Региональные каналы'),
    ('local', 'Абоненты'),
    ('other', 'Прочие каналы'),
]


def category_sections(groups, *, include_channel_rows=True):
    sections = []
    for category, title in CATEGORY_HEADINGS:
        matching = [g for g in groups if g['subscriber'].category == category]
        if not matching:
            continue
        combined = {}
        for group in matching:
            entry = combined.setdefault(group['subscriber'].pk, {
                'subscriber':group['subscriber'], 'received':0, 'sent':0, 'rows':[]})
            entry['rows'].extend(group['rows'])
            entry['received'] += group['totals']['received']
            entry['sent'] += group['totals']['sent']
        subscribers = []
        totals = {'received':0, 'sent':0}
        for entry in sorted(combined.values(), key=lambda e: e['subscriber'].name.casefold()):
            rows = sorted(entry.pop('rows'), key=lambda row: (row.channel.route_address, row.channel.kind))
            for row in rows:
                row.display_channel = row.channel.name if row.channel.kind == 'AMHS' else row.channel.route_address
            entry.update(address=rows[0].display_channel if len(rows)==1 else '',
                         multiple=len(rows)>1, channels=rows if include_channel_rows and len(rows)>1 else [], all_channels=rows,
                         record=getattr(rows[0], 'record', None) if len(rows)==1 else None)
            subscribers.append(entry)
            for key in totals:
                totals[key] += entry[key]
        sections.append({'category':category, 'title':title,
            'first_column':'Абонент' if category in ('local','other') else 'Центр',
            'subscribers':subscribers, 'totals':totals})
    return sections


def report_rows(context, *, include_month_rows=False):
    """Four cells per row; totals count subscriber summaries once."""
    result = []
    for section in context['category_sections']:
        result.append(('category', [section['title'], '', '', '']))
        result.append(('header', [section['first_column'], 'Принято', 'Передано', 'Канал']))
        for entry in section['subscribers']:
            result.append(('subscriber', [entry['subscriber'].name, entry['received'], entry['sent'], entry['address']]))
            if include_month_rows:
                for month in entry.get('monthly_totals', ()):
                    result.append(('month', [month['label'], month['received'], month['sent'], '']))
            for row in entry['channels']:
                result.append(('channel', ['', row.received, row.sent, row.display_channel]))
        result.append(('total', ['Итого', section['totals']['received'], section['totals']['sent'], '']))
    return result
