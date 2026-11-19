import secrets
import json
import re
from datetime import date
from types import SimpleNamespace
from urllib.parse import urlencode
from django.utils.formats import date_format
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .models import Subscriber, Channel, ImportBatch, Record, CATEGORIES, TYPES
from .forms import SubscriberForm, ChannelForm
from .lifecycle import delete_unused_subscribers
from .reporting import category_sections, report_rows
from .parser import parse, decode, ImportError, without_aftn_totals, parse_pasted_reports

KEYS = ('received','sent')

def render_statistics(request, template_name, context):
    context['latest_statistics'] = Record.objects.order_by('-report_month').values_list('report_month', flat=True).first()
    return render(request, template_name, context)


def preview_rows(payload, start_index=0):
    channels = list(Channel.objects.filter(kind=payload['kind']).select_related('subscriber'))
    existing = {channel.route_address:channel for channel in channels}
    amhs_names = {}
    for channel in channels:
        amhs_names.setdefault(channel.name, []).append(channel)
    result = []
    for i, row in enumerate(payload['rows'], start_index):
        matches = amhs_names.get(row['source_name'], []) if payload['kind'] == 'AMHS' else []
        channel = (matches[0] if len(matches) == 1 else None) if payload['kind'] == 'AMHS' else existing.get(row['route_address'])
        result.append(dict(row=row, index=i, channel=channel, ambiguous=len(matches)>1))
    return result


def upload_preview_groups(payload):
    index = 0
    for report in payload.get('reports', [payload]):
        items = preview_rows(report, index)
        yield report, items
        index += len(items)


def save_upload_report(payload, items, form):
    channels = []
    seen_addresses = set()
    for item in items:
        channel, row, index = item['channel'], item['row'], item['index']
        if item['ambiguous']:
            raise ImportError(f"Несколько AMHS-каналов имеют имя {row['source_name']}. Уточните имена в справочнике.")
        address = channel.route_address if channel else (row['route_address'] if payload['kind'] == 'AFTN' else '')
        if channel is None and payload['kind'] == 'AMHS':
            address = form.get(f'route_address_{index}', address).strip()
            if len(address) > 200:
                raise ImportError('Адрес AMHS-канала должен быть не длиннее 200 символов.')
            if address and Channel.objects.filter(kind='AMHS', route_address=address).exists():
                raise ImportError(f'AMHS-канал с адресом {address} уже существует.')
        if address and address in seen_addresses:
            raise ImportError(f'Один адрес назначен нескольким строкам: {address}.')
        if address:
            seen_addresses.add(address)
        item['save_address'] = address
    for item in items:
        row, i = item['row'], item['index']
        channel = item['channel']
        if channel is None:
            sid = form.get(f'subscriber_{i}')
            new_name = form.get(f'new_{i}','').strip()
            if sid:
                subscriber = Subscriber.objects.filter(pk=sid).first() if sid.isdigit() else None
                if subscriber is None:
                    raise ImportError('Выберите существующего абонента.')
            elif new_name:
                category = form.get(f'category_{i}','other')
                if len(new_name)>200 or category not in dict(CATEGORIES):
                    raise ImportError('Проверьте название и категорию абонента.')
                subscriber, created = Subscriber.objects.get_or_create(name=new_name, defaults={'category':category})
            else:
                raise ImportError(f"Назначьте абонента для {row['route_address']}.")
            name = form.get(f'name_{i}','').strip() or row['source_name']
            if len(name)>200:
                raise ImportError('Название канала должно быть не длиннее 200 символов.')
            channel = Channel.objects.create(kind=payload['kind'], route_address=item['save_address'],
                name=name, subscriber=subscriber, mailing_received=subscriber.category == 'local',
                mailing_addresses=item['save_address'])
        if payload['kind'] == 'AFTN':
            channel.logical_number = int(row['number'])
            channel.transmission_designation = row['designation']
            update_fields = ['logical_number', 'transmission_designation']
            if row.get('merged'):
                channel.name = row['source_name']
                update_fields.append('name')
            channel.save(update_fields=update_fields)
        channels.append(channel)
    batch, created = ImportBatch.objects.update_or_create(month=payload['month'],kind=payload['kind'], defaults={'filename':payload['filename'],'source':payload['source']})
    batch.records.all().delete()
    Record.objects.bulk_create([Record(batch=batch,channel=c,report_month=batch.month,**{k:row[k] for k in KEYS}) for c,row in zip(channels,payload['rows'])])


def upload(request):
    if request.method == 'GET':
        request.session.pop('stats_preview', None)
    payload = request.session.get('stats_preview')
    if payload and 'rows' in payload:
        for row in payload['rows']:
            if 'system_name' in row:
                row['route_address'] = row.pop('system_name')
    error = None
    pasted_text = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'preview':
            request.session.pop('stats_preview', None)
            payload = None
            try:
                pasted_text = request.POST.get('statistics_text', '')
                if pasted_text.strip():
                    if len(pasted_text.encode('utf-8')) > 2 * 1024 * 1024:
                        raise ImportError('Вставленный текст должен быть не больше 2 МБ.')
                    reports = parse_pasted_reports(pasted_text)
                    payload = reports[0] if len(reports) == 1 else {'reports': reports}
                else:
                    f = request.FILES.get('file')
                    if not f or f.size > 5*1024*1024:
                        raise ImportError('Выберите текстовый файл размером до 5 МБ или вставьте статистику.')
                    source = without_aftn_totals(decode(f.read()))
                    payload = dict(parse(source), source=source, filename=f.name[:255])
                payload['token'] = secrets.token_hex(16)
                pasted_text = ''
                request.session['stats_preview'] = payload
            except (ImportError, ValueError) as exc:
                error = str(exc)
        elif request.POST.get('action') == 'save':
            if not payload or request.POST.get('token') != payload['token']:
                return HttpResponseBadRequest('Предпросмотр устарел. Загрузите файл снова.')
            try:
                with transaction.atomic():
                    reports = payload.get('reports', [payload])
                    if request.POST.get('replace') != 'yes' and any(
                        ImportBatch.objects.filter(month=report['month'], kind=report['kind']).exists()
                        for report in reports
                    ):
                        raise ImportError('Подтвердите полную замену данных этого типа за месяц.')
                    for report, items in upload_preview_groups(payload):
                        save_upload_report(report, items, request.POST)
                request.session.pop('stats_preview',None)
                messages.success(request,'Статистика сохранена.',extra_tags='stats-saved-toast')
                months = sorted(report['month'][:7] for report in reports)
                params = {'month': months[0]}
                if months[-1] != months[0]:
                    params['end_month'] = months[-1]
                return redirect(reverse('traffic_stats:report') + '?' + urlencode(params))
            except ImportError as exc:
                error = str(exc)
            except IntegrityError:
                error = 'Адрес канала или данные импорта уже изменились. Загрузите файл заново.'
    sections = []
    for report, rows in upload_preview_groups(payload) if payload else ():
        for item in rows:
            index = item['index']
            submitted = request.method == 'POST' and request.POST.get('action') == 'save'
            item['subscriber_name'] = request.POST.get(f'new_{index}', item['row']['source_name']) if submitted else item['row']['source_name']
            item['selected_category'] = request.POST.get(f'category_{index}', 'other') if submitted else 'other'
            default_address = item['channel'].route_address if item['channel'] else (item['row']['route_address'] if report['kind'] == 'AFTN' else '')
            item['address'] = request.POST.get(f'route_address_{index}', default_address) if submitted and not item['channel'] and report['kind'] == 'AMHS' else default_address
        replaces = ImportBatch.objects.filter(month=report['month'], kind=report['kind']).exists()
        sections.append(dict(report=report, rows=rows, replaces=replaces))
    rows = [item for section in sections for item in section['rows']]
    replacements = [section['report'] for section in sections if section['replaces']]
    return render(request, 'traffic_stats/upload.html', dict(
        payload=payload, rows=rows, sections=sections, error=error, pasted_text=pasted_text,
        replaces=bool(replacements), replacements=replacements,
        subscribers=Subscriber.objects.all(), categories=CATEGORIES))


def monthly_chart(request, records, month, end_month):
    """Return the same filtered and corrected values as the report, by month."""
    scope = request.GET['chart']
    key = request.GET.get('chart_id', '')
    if scope == 'category' and key in dict(CATEGORIES):
        records = records.filter(channel__subscriber__category=key)
    elif scope in ('subscriber', 'channel') and key.isascii() and key.isdecimal() and len(key) <= 19:
        pk = int(key)
        if not 0 < pk <= 9223372036854775807:
            return JsonResponse({'error': 'Некорректная строка отчёта.'}, status=400)
        field = 'channel_id' if scope == 'channel' else 'channel__subscriber_id'
        records = records.filter(**{field: pk})
    else:
        return JsonResponse({'error': 'Некорректная строка отчёта.'}, status=400)

    points = records.values('report_month').annotate(
        **{key: Sum(Coalesce('user_' + key, key)) for key in KEYS}
    ).order_by('report_month')
    return JsonResponse({
        'month': month, 'end_month': end_month,
        'points': [
            {'month': point['report_month'].isoformat()[:7],
             **{key: str(point[key]) for key in KEYS}}
            for point in points
        ],
    })


def report(request):
    if 'filters' in request.GET:
        params = request.GET.copy()
        params.pop('filters', None)
        params['period'] = '1'
        return redirect(reverse('traffic_stats:report') + '?' + params.urlencode())
    latest_statistics = Record.objects.order_by('-report_month').values_list('report_month', flat=True).first()
    show_period = True
    report_requested = bool(request.GET.get('month'))
    default = latest_statistics.strftime('%Y-%m') if latest_statistics else ''
    value = request.GET.get('month', default)
    end_value = request.GET.get('end_month', '') or value
    try:
        # The same month at both ends is a monthly report.
        if value and (len(value) != 7 or len(end_value) != 7):
            raise ValueError()
        start_month = date.fromisoformat(value+'-01') if value else None
        end_month = date.fromisoformat(end_value+'-01') if end_value else None
        if bool(start_month) != bool(end_month) or (start_month and start_month > end_month):
            raise ValueError()
    except ValueError:
        return HttpResponseBadRequest('Некорректный диапазон месяцев.')
    start_label = date_format(start_month, 'F Y').lower() if start_month else ''
    end_label = date_format(end_month, 'F Y').lower() if end_month else ''
    period_label = start_label if start_month == end_month else f'{start_label} — {end_label}'
    report_title = 'Статистика по каналам за ' + period_label
    kind = request.GET.get('kind','')
    category = request.GET.get('category','')
    selected = request.GET.getlist('subscriber')
    if kind not in ('','AFTN','AMHS') or category not in ('',*dict(CATEGORIES)) or any(not x.isdigit() for x in selected):
        return HttpResponseBadRequest('Некорректные фильтры.')
    records = Record.objects.for_period(start_month, end_month) if report_requested and start_month else Record.objects.none()
    if kind:
        records = records.filter(channel__kind=kind)
    if category:
        records = records.filter(channel__subscriber__category=category)
    if selected:
        records = records.filter(channel__subscriber_id__in=selected)
    can_edit = bool(report_requested and start_month and start_month == end_month)
    is_range = bool(report_requested and start_month and start_month < end_month)
    if 'chart' in request.GET:
        if not is_range:
            return JsonResponse({'error': 'Выберите период больше одного месяца.'}, status=400)
        return monthly_chart(request, records, value, end_value)
    monthly_records = {row['channel_id']:row for row in records.values('id','channel_id','received','sent','user_received','user_sent')} if can_edit else {}
    aggregated = list(records.values('channel_id').annotate(**{k: Sum(Coalesce('user_' + k, k)) for k in KEYS}).order_by('channel__subscriber__name', 'channel__kind', 'channel__route_address'))
    channels = Channel.objects.select_related('subscriber').in_bulk([r['channel_id'] for r in aggregated])
    groups, totals = {}, {}
    for values in aggregated:
        record = SimpleNamespace(channel=channels[values['channel_id']], record=monthly_records.get(values['channel_id']), **{k: values[k] for k in KEYS})
        channel = record.channel
        key = (channel.subscriber_id,channel.kind)
        group = groups.setdefault(key,dict(subscriber=channel.subscriber,kind=channel.kind,rows=[],totals=dict.fromkeys(KEYS,0)))
        total = totals.setdefault(channel.kind,dict.fromkeys(KEYS,0))
        group['rows'].append(record)
        for k in KEYS:
            group['totals'][k] += getattr(record,k) or 0
            total[k] += getattr(record,k) or 0
    report_groups = list(groups.values())
    context = dict(
        can_edit=can_edit, show_chart=is_range, show_period=show_period,
        report_requested=report_requested, latest_statistics=latest_statistics,
        month=value, end_month=end_value, period_label=period_label, report_title=report_title,
        kind=kind, category=category, selected=selected, subscribers=Subscriber.objects.all(),
        categories=CATEGORIES, types=TYPES, groups=report_groups,
        category_sections=category_sections(report_groups, include_channel_rows=not is_range), totals=totals,
    )
    if request.GET.get('print') == 'period':
        if not is_range:
            return HttpResponseBadRequest('Для печати сводной таблицы выберите период больше одного месяца.')
        return render(request, 'traffic_stats/print_period.html', context)
    if request.GET.get('print') in ('centers', 'subscribers', 'channels', 'all'):
        if not can_edit:
            return HttpResponseBadRequest('Для печати выберите один месяц.')
        from .monthly_export import TemplateExportError
        from .printing import sheet_print_context
        try:
            return render(request, 'traffic_stats/print_sheet.html', sheet_print_context(context, variant=request.GET['print']))
        except TemplateExportError as exc:
            return HttpResponseBadRequest('Ошибка шаблона Excel: ' + str(exc))
    if is_range:
        monthly_totals = {}
        points = records.values('channel_id', 'report_month').annotate(
            **{key: Sum(Coalesce('user_' + key, key)) for key in KEYS}
        ).order_by('report_month')
        # Sum across channels in Python, as the main report does for its totals.
        for point in points.iterator():
            subscriber_id = channels[point['channel_id']].subscriber_id
            month = point['report_month']
            subscriber_months = monthly_totals.setdefault(subscriber_id, {})
            if month not in subscriber_months:
                subscriber_months[month] = {
                    'label': date_format(month, 'F Y').lower(), 'received': 0, 'sent': 0,
                }
            for key in KEYS:
                subscriber_months[month][key] += point[key]
        for section in context['category_sections']:
            for entry in section['subscribers']:
                entry['monthly_totals'] = list(monthly_totals.get(entry['subscriber'].pk, {}).values())

    if request.GET.get('download') in ('all', 'economists'):
        if not can_edit:
            return HttpResponseBadRequest('Для скачивания файла по шаблону выберите один месяц.')
        from .monthly_export import export_monthly_workbook, TemplateExportError
        try:
            return export_monthly_workbook(context, variant=request.GET['download'])
        except TemplateExportError as exc:
            return HttpResponseBadRequest('Ошибка шаблона Excel: ' + str(exc))
    if report_requested and request.GET.get('export') == 'xlsx':
        from .exports import export_report
        return export_report(context)
    count_lengths = (
        len(str(value))
        for row_kind, values in report_rows(context)
        if row_kind in ('subscriber', 'channel', 'total')
        for value in values[1:3]
    )
    context['count_column_chars'] = max(8, max(count_lengths, default=0)) + 2
    return render(request, 'traffic_stats/report.html', context)

@require_GET
def directory(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'address')
    direction = request.GET.get('direction', 'asc')
    if sort not in ('address', 'channel', 'subscriber'):
        sort = 'address'
    if direction not in ('asc', 'desc'):
        direction = 'asc'
    channels = list(Channel.objects.select_related('subscriber'))
    if query:
        needle = query.casefold()
        channels = [channel for channel in channels if any(needle in value.casefold() for value in (channel.route_address, channel.name, channel.subscriber.name, channel.mailing_addresses))]
    def sort_key(channel):
        primary = channel.route_address if sort == 'address' else channel.name if sort == 'channel' else channel.subscriber.name
        return (primary.casefold(), channel.route_address.casefold(), channel.kind, channel.pk)
    channels.sort(key=sort_key, reverse=direction == 'desc')
    def sort_url(column):
        next_direction = 'desc' if sort == column and direction == 'asc' else 'asc'
        return '?' + urlencode({'q':query, 'sort':column, 'direction':next_direction})
    return render_statistics(request, 'traffic_stats/directory.html', dict(
        channels=channels, search=query, subscribers=Subscriber.objects.all(), categories=CATEGORIES,
        sort=sort, direction=direction, address_sort_url=sort_url('address'), channel_sort_url=sort_url('channel'), subscriber_sort_url=sort_url('subscriber')))


def _channel_edit_state(channel):
    return dict(subscriber_id=channel.subscriber_id, category=channel.subscriber.category,
        route_address=channel.route_address, mailing_received=channel.mailing_received,
        mailing_sent=channel.mailing_sent, mailing_addresses=channel.mailing_addresses)


@require_POST
def assign_channel(request, pk):
    name = request.POST.get('subscriber_name', '').strip()
    expected = request.POST.get('expected_subscriber', '')
    category = request.POST.get('category')
    if not name or len(name) > 200 or not re.fullmatch(r'[0-9]{1,20}', expected):
        return JsonResponse({'error':'Укажите имя абонента длиной до 200 символов.'}, status=400)
    if category is not None and category not in dict(CATEGORIES):
        return JsonResponse({'error':'Выберите категорию абонента.'}, status=400)
    try:
        with transaction.atomic():
            channel = Channel.objects.select_for_update().select_related('subscriber').filter(pk=pk).first()
            if channel is None:
                return JsonResponse({'error':'Канал удалён. Обновите страницу.'}, status=404)
            if channel.subscriber_id != int(expected):
                return JsonResponse({'error':'Абонент канала уже изменён. Обновите страницу.'}, status=409)
            if 'expected_state' in request.POST:
                try:
                    state = json.loads(request.POST['expected_state'])
                except (ValueError, TypeError):
                    return JsonResponse({'error':'Некорректные данные редактирования. Обновите страницу.'}, status=400)
                if state != _channel_edit_state(channel):
                    return JsonResponse({'error':'Данные канала или категория уже изменились. Обновите страницу.'}, status=409)
            address = request.POST.get('route_address', channel.route_address).strip()
            if (not address and channel.kind == 'AFTN') or len(address) > 200:
                return JsonResponse({'error':'Укажите адрес канала длиной до 200 символов.'}, status=400)
            if address and Channel.objects.filter(kind=channel.kind, route_address=address).exclude(pk=pk).exists():
                return JsonResponse({'error':'Канал этого типа с таким адресом уже существует.'}, status=400)
            updates = dict(route_address=address, mailing_addresses=request.POST.get('mailing_addresses', channel.mailing_addresses).strip())
            if len(updates['mailing_addresses']) > 200:
                return JsonResponse({'error':'Адреса рассылки должны содержать не больше 200 символов.'}, status=400)
            for field in ('mailing_received', 'mailing_sent'):
                if field not in request.POST:
                    updates[field] = getattr(channel, field)
                    continue
                value = request.POST[field].lower()
                if value not in ('1','0','true','false','on','off','yes','no',''):
                    return JsonResponse({'error':'Некорректное значение флажка рассылки.'}, status=400)
                updates[field] = value in ('1','true','on','yes')
            subscriber = Subscriber.objects.filter(name=name).first()
            if subscriber is None:
                subscriber, _ = Subscriber.objects.get_or_create(name=name, defaults={'category':category or 'other'})
            if category is not None and subscriber.category != category:
                subscriber.category = category
                subscriber.save(update_fields=['category'])
            updates['subscriber'] = subscriber
            updated = Channel.objects.filter(pk=pk, subscriber_id=channel.subscriber_id).update(**updates)
            if not updated:
                transaction.set_rollback(True)
                return JsonResponse({'error':'Привязка канала уже изменилась. Обновите страницу.'}, status=409)
            old_name = channel.subscriber.name
            removed, _ = delete_unused_subscribers([channel.subscriber_id], using=channel._state.db)
    except IntegrityError:
        return JsonResponse({'error':'Адрес или привязка канала уже изменились. Обновите страницу.'}, status=409)
    return JsonResponse(dict(ok=True, subscriber_id=subscriber.pk, subscriber_name=subscriber.name,
        category=subscriber.category, category_label=subscriber.get_category_display(),
        route_address=address, mailing_received=updates['mailing_received'], mailing_sent=updates['mailing_sent'],
        mailing_addresses=updates['mailing_addresses'], removed_subscriber_name=old_name if removed else None))


def subscriber_edit(request,pk):
    obj = get_object_or_404(Subscriber,pk=pk)
    form = SubscriberForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        form.save()
        return redirect('traffic_stats:directory')
    return render_statistics(request,'traffic_stats/edit.html',dict(form=form,label='Абонент: '+obj.name))

def channel_edit(request,pk):
    obj = get_object_or_404(Channel,pk=pk)
    form = ChannelForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        form.save()
        return redirect('traffic_stats:directory')
    return render_statistics(request,'traffic_stats/edit.html',dict(form=form,label=f'Канал {obj.kind}: {obj.route_address}'))


@require_POST
def correct_record(request, pk):
    field = request.POST.get('field')
    value_text = request.POST.get('value', '').strip()
    expected_text = request.POST.get('expected', '').strip()
    month_text = request.POST.get('month', '')
    if field not in KEYS or not re.fullmatch(r'[0-9]{1,19}', value_text) or not re.fullmatch(r'[0-9]{1,19}', expected_text):
        return JsonResponse({'error':'Введите целое неотрицательное число.'}, status=400)
    value, expected = int(value_text), int(expected_text)
    if value > 9223372036854775807 or expected > 9223372036854775807:
        return JsonResponse({'error':'Значение слишком велико.'}, status=400)
    try:
        if len(month_text) != 7:
            raise ValueError()
        month = date.fromisoformat(month_text+'-01')
    except ValueError:
        return JsonResponse({'error':'Укажите один отчётный месяц.'}, status=400)
    user_field = 'user_' + field
    with transaction.atomic():
        record = Record.objects.filter(pk=pk, report_month=month).first()
        if record is None:
            return JsonResponse({'error':'Запись удалена или отчёт был заменён. Обновите страницу.'}, status=404)
        previous = getattr(record, user_field)
        original = getattr(record, field)
        current = previous if previous is not None else original
        if current != expected:
            return JsonResponse({'error':'Значение уже изменилось. Обновите отчёт перед сохранением.'}, status=409)
        replacement = None if value == original else value
        updated = Record.objects.filter(pk=pk, **{user_field:previous}).update(**{user_field:replacement})
        if not updated:
            return JsonResponse({'error':'Значение уже изменилось. Обновите отчёт.'}, status=409)
    return JsonResponse({'ok':True,'value':str(value),'overridden':replacement is not None})
