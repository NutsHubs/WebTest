"""Формирование месячной Excel-книги для пункта «Скачать все».

Точка входа — export_monthly_workbook(context), вызываемая из views.report
при download=all. Здесь используется пользовательский template.xlsx;
обычный экспорт таблицы в Excel/PDF находится отдельно в exports.py.

Последовательность: _datasets собирает значения → _plan определяет новые
номера строк на всех листах → _fill_sheet переносит оформление и заполняет
метки → книга сохраняется в память и возвращается браузеру для скачивания.

Где менять поведение:
* состав и суммы таблиц, правила флажков рассылки — _datasets;
* доступные #метки — CATEGORY_MARKERS / GLOBAL_FIELDS / ROW_FIELDS,
  их значения — _datasets и _replace;
* повторение строк и сдвиг формул — _plan, _mapped_row и _formula;
* перенос длинных имён/адресов и высоту строк — _fit_row;
* расположение таблиц, цвета, ширины, подписи — excel_templates/template.xlsx;
* имя скачиваемого файла — конец export_monthly_workbook.

Шаблон читается, но не перезаписывается. Номера строк таблиц и названия листов
не зашиты в код: строки данных определяются категориальными #метками.
"""
from copy import copy
from datetime import date
from io import BytesIO
from textwrap import wrap
from pathlib import Path
import re

from django.http import HttpResponse
from django.utils.formats import date_format
from django.utils.http import content_disposition_header
from .exports import load_export_dependencies

# Путь относительно этого модуля: не зависит от текущей рабочей папки сервера.
TEMPLATE = Path(__file__).resolve().parent / 'excel_templates' / 'template.xlsx'
# Метки регистронезависимы; поддерживаются русские/латинские буквы и подчёркивание.
# Состав и порядок сокращённой книги для экономистов. Имена совпадают с шаблоном.
ECONOMIST_SHEETS = ('Каналы ПД', 'ФГУП ГК', 'Сторонние')
MARKER = re.compile(r'#([A-Za-zА-Яа-яЁё_]+)')
# Только обычные ссылки A1 или A1:B10, включая $A$1; иные типы ссылок не сдвигаются.
CELL_RANGE = re.compile(r'^(\$?[A-Z]{1,3})(\$?)([1-9][0-9]*)(?::(\$?[A-Z]{1,3})(\$?)([1-9][0-9]*))?$')
# Метка категории в строке означает: повторить эту строку по каждому абоненту
# выбранной категории. «абонент» — специальный набор для операторской рассылки.
# Для новой категории добавьте здесь метку и обеспечьте набор данных в _datasets.
CATEGORY_MARKERS = {
    'федеральный':'federal', 'федеральные':'federal',
    'международный':'international', 'международные':'international',
    'региональный':'regional', 'региональные':'regional',
    'локальный':'local', 'локальные':'local',
    'прочее':'other', 'прочие':'other', 'абонент':'operator',
}
# Общие метки разрешены в любой текстовой ячейке, в том числе в подписях.
# ROW_FIELDS разрешены только в строке с меткой категории/абонента.
GLOBAL_FIELDS = {'месяц', 'год', 'должность', 'имя'}
ROW_FIELDS = {'user_received', 'user_sent', 'route_address', 'mailing_addresses', 'transmission_designation'}


class TemplateExportError(ValueError):
    """Ошибка разметки шаблона; views.report показывает её пользователю как HTTP 400."""
    pass


def _text(cell, value):
    """Записать значения, сохранив числа числами, а пользовательский текст текстом."""
    # Имя, начинающееся с «=», не должно превращаться в исполняемую формулу Excel.
    cell.value = value
    if isinstance(value, str):
        cell.data_type = 's'


def _style(source, target):
    """Скопировать компоненты стиля между разными книгами без общих style_id."""
    # Нельзя просто переносить _style: внутренние индексы относятся к исходной книге.
    for attribute in ('font', 'fill', 'border', 'alignment', 'protection'):
        setattr(target, attribute, copy(getattr(source, attribute)))
    target.number_format = source.number_format


def _datasets(context):
    """Подготовить словари значений для повторяемых строк каждого вида таблицы.

    category_sections строится в reporting.py из данных выбранного периода.
    entry['received'/'sent'] и row.received/sent уже учитывают пользовательские
    корректировки (в том числе замену на 0), рассчитанные во views.report.
    all_channels содержит все каналы абонента, включая единственный канал;
    channels из entry использовать нельзя: там только детальные подстроки
    абонентов с несколькими каналами, необходимые для экранной таблицы.
    """
    datasets = {key:[] for key in set(CATEGORY_MARKERS.values())}
    operators = {}
    for section in context['category_sections']:
        for entry in section['subscribers']:
            channels = entry['all_channels']
            # Обычные категориальные листы: все каналы, сумма на абонента,
            # непустые адреса без повторов. Здесь флажки рассылки не применяются.
            addresses = sorted({row.channel.route_address for row in channels if row.channel.route_address}, key=str.casefold)
            datasets[section['category']].append(dict(name=entry['subscriber'].name,
                user_received=entry['received'], user_sent=entry['sent'], route_address=', '.join(addresses)))
            # Лист оператора: одна строка на абонента только при наличии флажков.
            # Каждый счётчик суммируется по своему набору каналов. Например,
            # канал с одним флажком ПРМ не добавляет ничего в сумму ПРД.
            selected = [row for row in channels if row.channel.mailing_received or row.channel.mailing_sent]
            if selected:
                received = [row.received for row in selected if row.channel.mailing_received]
                sent = [row.sent for row in selected if row.channel.mailing_sent]
                # Объединяем именно mailing_addresses выбранных каналов,
                # а не route_address и не адреса всех каналов абонента.
                # Запятая, «;» и перевод строки разделяют адреса. Пробелы внутри
                # отдельного значения сохраняем; одинаковые значения удаляет set.
                mailing_addresses = {
                    address.strip()
                    for row in selected
                    for address in re.split(r'[,;\r\n]+', row.channel.mailing_addresses)
                    if address.strip()
                }
                # Ключ — ID абонента: AMHS/AFTN попадают в общую строку.
                # None оставляет пустую ячейку при отсутствии выбранного направления;
                # непустой список из нулей даёт числовой 0. Это разные случаи.
                operators[entry['subscriber'].pk] = dict(name=entry['subscriber'].name,
                    user_received=sum(received) if received else None,
                    user_sent=sum(sent) if sent else None,
                    route_address=', '.join(sorted({row.channel.route_address for row in selected if row.channel.route_address}, key=str.casefold)),
                    mailing_addresses=', '.join(sorted(mailing_addresses, key=str.casefold)),
                    # Старый шаблон может содержать « / #transmission_designation».
                    # Пустое значение уберёт и обозначение, и разделитель в _replace.
                    transmission_designation='')
    datasets['operator'] = sorted(operators.values(), key=lambda item:item['name'].casefold())
    return datasets


def _plan(sheet, datasets):
    """Составить план размножения строк, пока не изменяя сам лист.

    rows: (исходная строка, новая строка, значения абонента либо None,
    является ли строка повторяемой). mapping: исходный номер → список новых
    номеров. Этой картой далее пользуются формулы, объединения и область печати.
    """
    rows, mapping = [], {}
    for source_row in range(1, sheet.max_row + 1):
        tokens = {match.group(1).casefold() for cell in sheet[source_row] if isinstance(cell.value,str)
                  for match in MARKER.finditer(cell.value)}
        unknown = tokens - set(CATEGORY_MARKERS) - ROW_FIELDS - GLOBAL_FIELDS
        if unknown:
            raise TemplateExportError(f'Неизвестная метка #{sorted(unknown)[0]}: лист «{sheet.title}», строка {source_row}.')
        categories = {CATEGORY_MARKERS[token] for token in tokens if token in CATEGORY_MARKERS}
        if len(categories) > 1:
            raise TemplateExportError(f'Несколько групп абонентов в одной строке: лист «{sheet.title}», строка {source_row}.')
        if tokens & ROW_FIELDS and not categories:
            raise TemplateExportError(f'Не указана метка абонента для строки {source_row} листа «{sheet.title}».')
        # Без метки категории строка копируется один раз (заголовок, подпись).
        # Пустая категория также оставляет одну оформленную пустую строку:
        # диапазон SUM остаётся корректным и возвращает 0.
        category = next(iter(categories), None)
        entries = (datasets[category] or [None]) if category else [None]
        mapping[source_row] = []
        for entry in entries:
            destination = len(rows) + 1
            rows.append((source_row, destination, entry, category is not None))
            mapping[source_row].append(destination)
    return dict(rows=rows, mapping=mapping, source_max=sheet.max_row, offset=len(rows)-sheet.max_row)


def _mapped_row(plan, row, end=False):
    """Перевести номер строки шаблона в номер выходной книги.

    Для конца диапазона берём последнюю копию строки (end=True), для начала —
    первую. Строки ниже данных шаблона сдвигаются на общий прирост offset;
    это нужно, например, для области печати, захватывающей пустое место снизу.
    """
    mapped = plan['mapping'].get(row)
    return mapped[-1 if end else 0] if mapped else row + (plan['offset'] if row > plan['source_max'] else 0)


def _formula(formula, sheet_name, plans, source_row=None, destination_row=None, repeated=False):
    """Пересчитать обычные ссылки в формуле по планам расширения всех листов.

    Например, SUM(D7:D7) при трёх абонентах станет SUM(D7:D9).
    Ссылки на другие листы используют карту соответствующего листа.
    $ сохраняется, но номер строки обновляется: это структурный сдвиг из-за
    вставки строк, а не обычное протягивание формулы мышью в Excel.
    Именованные диапазоны, ссылки на целые столбцы и другие конструкции,
    не распознанные CELL_RANGE, остаются без изменений.
    """
    from openpyxl.formula import Tokenizer
    parsed = Tokenizer(formula)
    for token in parsed.items:
        # Токенизатор позволяет менять ссылки, не затрагивая строки внутри формулы.
        # Формулы без ссылок, например TODAY(), проходят без изменения.
        if token.type != 'OPERAND' or token.subtype != 'RANGE':
            continue
        qualifier, separator, address = token.value.rpartition('!')
        target = qualifier.strip("'").replace("''", "'") if separator else sheet_name
        address = address if separator else token.value
        match = CELL_RANGE.fullmatch(address)
        if target not in plans or not match:
            continue
        first_col, first_abs, first_row, last_col, last_abs, last_row = match.groups()
        plan = plans[target]
        def mapped(row, end=False):
            # Ссылка повторяемой строки на саму себя должна вести в её текущую копию.
            if repeated and target == sheet_name and row == source_row:
                return destination_row
            return _mapped_row(plan, row, end)
        updated = f'{first_col}{first_abs}{mapped(int(first_row))}'
        if last_col:
            updated += f':{last_col}{last_abs}{mapped(int(last_row), True)}'
        token.value = (qualifier + '!' if separator else '') + updated
    return '=' + ''.join(token.value for token in parsed.items)


def _replace(value, entry, month, signer=None):
    """Заменить #метки значениями строки, месяца и текущего подписанта.

    Если метка занимает всю ячейку, возвращаем исходный тип (число, None,
    строка). Внутри текста, например «за #месяц #год», подставляем строки.
    Новую общую метку нужно разрешить в GLOBAL_FIELDS и задать здесь;
    новое поле строки — разрешить в ROW_FIELDS и заполнить в _datasets.
    """
    if not isinstance(value, str) or not MARKER.search(value):
        return value
    values = {name:(entry or {}).get('name') for name in CATEGORY_MARKERS}
    values.update({name:(entry or {}).get(name) for name in ROW_FIELDS})
    values.update(месяц=date_format(month,'F').lower(), год=month.year)
    values.update(должность=signer.position if signer else '', имя=signer.name if signer else '')
    if not values['transmission_designation']:
        value = re.sub(r'\s*/\s*#transmission_designation', '', value, flags=re.IGNORECASE)
    match = MARKER.fullmatch(value)
    if match:
        return values[match.group(1).casefold()]
    return MARKER.sub(lambda match: '' if values[match.group(1).casefold()] is None else str(values[match.group(1).casefold()]), value)


def _copy_layout(source, target):
    """Перенести настройки листа, печати, колонтитулы и размеры столбцов.

    Ячейки, высоты строк и объединения копируются отдельно в _fill_sheet:
    их координаты зависят от количества абонентов в текущем отчёте.
    """
    target.sheet_format = copy(source.sheet_format)
    target.sheet_properties = copy(source.sheet_properties)
    target.page_setup = copy(source.page_setup)
    target.page_margins = copy(source.page_margins)
    target.print_options = copy(source.print_options)
    target.views = copy(source.views)
    target.protection = copy(source.protection)
    target.sheet_state = source.sheet_state
    for attribute in ('oddHeader','oddFooter','evenHeader','evenFooter','firstHeader','firstFooter'):
        setattr(target, attribute, copy(getattr(source, attribute)))
    for letter, dimension in source.column_dimensions.items():
        dst = target.column_dimensions[letter]
        for attribute in ('width','hidden','outlineLevel','collapsed','bestFit','min','max'):
            setattr(dst, attribute, getattr(dimension, attribute))
        _style(dimension, dst)


def _fit_row(sheet, row):
    """Увеличить высоту строки под длинные имена и несколько адресов.

    openpyxl не выполняет Excel AutoFit. Оцениваем доступную ширину, учитывая
    объединённые ячейки, размер шрифта, явные переводы строк и перенос по словам.
    Коэффициенты .85 (запас по ширине), 1.5 (межстрочная высота) и 4 (отступы)
    подобраны с запасом, чтобы адреса не обрезались. При смене шрифта/шаблона
    корректировать расчёт нужно здесь. Однострочный текст сохраняет высоту
    шаблона; оценку высоты применяем только при переносе. Уже заданную большую
    высоту не уменьшаем. Правило общее для скачивания и браузерной печати.
    """
    from openpyxl.utils.cell import get_column_letter
    height = sheet.row_dimensions[row].height or sheet.sheet_format.defaultRowHeight or 15
    needed = height
    for cell in sheet[row]:
        if not isinstance(cell.value, str) or cell.data_type == 'f':
            continue
        width = sheet.column_dimensions[cell.column_letter].width
        for merged in sheet.merged_cells.ranges:
            if merged.min_row == merged.max_row == row and merged.min_col == cell.column:
                width = sum(sheet.column_dimensions[get_column_letter(col)].width for col in range(merged.min_col, merged.max_col+1))
                break
        # Считаем строки по словам: два восьмизначных адреса могут не влезть
        # рядом, хотя деление общей длины текста на ширину обещает меньше строк.
        font_size = cell.font.sz or 11
        capacity = max(1, int((width - 1) * .85 * 11 / font_size))
        lines = sum(max(1, len(wrap(line, width=capacity))) for line in cell.value.split('\n'))
        if lines > 1:
            needed = max(needed, lines * (font_size * 1.5) + 4)
            alignment = copy(cell.alignment)
            alignment.wrap_text = True
            cell.alignment = alignment
    if needed > height:
        sheet.row_dimensions[row].height = needed
        for cell in sheet[row]:
            if cell.value is not None:
                alignment = copy(cell.alignment)
                alignment.vertical = 'center'
                cell.alignment = alignment


def _fill_sheet(source, target, plan, plans, month, signer=None):
    """Собрать один выходной лист по заранее рассчитанному плану.

    Сначала переносим строки/ячейки и их стили, заполняя текстовые метки и
    обновляя формулы. Затем восстанавливаем объединения, подбираем высоты
    и сдвигаем область печати, повторяемые заголовки и закрепление областей.
    """
    from openpyxl.utils.cell import get_column_letter, range_boundaries
    _copy_layout(source, target)
    for source_row, destination_row, entry, repeated in plan['rows']:
        src_dim, dst_dim = source.row_dimensions[source_row], target.row_dimensions[destination_row]
        for attribute in ('height','hidden','outlineLevel','collapsed','thickTop','thickBot'):
            setattr(dst_dim, attribute, getattr(src_dim, attribute))
        _style(src_dim, dst_dim)
        for column in range(1, source.max_column+1):
            src, dst = source.cell(source_row,column), target.cell(destination_row,column)
            _style(src, dst)
            if src.data_type == 'f':
                dst.value = _formula(src.value, source.title, plans, source_row, destination_row, repeated)
            else:
                _text(dst, _replace(src.value, entry, month, signer))
            if src.comment:
                dst.comment = copy(src.comment)
            if src.hyperlink:
                dst.hyperlink = copy(src.hyperlink)
    # Горизонтальное объединение строки данных повторяем для каждого абонента.
    # Многострочное объединение растягиваем между новыми крайними строками.
    for merged in source.merged_cells.ranges:
        if merged.min_row == merged.max_row:
            for row in plan['mapping'][merged.min_row]:
                target.merge_cells(start_row=row,start_column=merged.min_col,end_row=row,end_column=merged.max_col)
        else:
            target.merge_cells(start_row=_mapped_row(plan,merged.min_row),start_column=merged.min_col,
                end_row=_mapped_row(plan,merged.max_row,True),end_column=merged.max_col)
    for _, destination_row, entry, repeated in plan['rows']:
        if repeated and entry is not None:
            _fit_row(target,destination_row)
    # Область печати и подписи должны включать все добавленные строки.
    # Если в шаблоне область не задана, печатается весь заполненный прямоугольник.
    areas=[]
    for area in re.findall(r'\$?[A-Z]{1,3}\$?[1-9][0-9]*:\$?[A-Z]{1,3}\$?[1-9][0-9]*', str(source.print_area)):
        left,top,right,bottom=range_boundaries(area)
        areas.append(f'{get_column_letter(left)}{_mapped_row(plan,top)}:{get_column_letter(right)}{_mapped_row(plan,bottom,True)}')
    target.print_area=areas or [f'A1:{get_column_letter(source.max_column)}{len(plan["rows"])}']
    if source.print_title_rows:
        start,end=(int(value.replace('$','')) for value in source.print_title_rows.split(':'))
        target.print_title_rows=f'{_mapped_row(plan,start)}:{_mapped_row(plan,end,True)}'
    if source.print_title_cols:
        target.print_title_cols=source.print_title_cols
    if source.freeze_panes:
        from openpyxl.utils.cell import coordinate_from_string
        column,row=coordinate_from_string(source.freeze_panes)
        target.freeze_panes=f'{column}{_mapped_row(plan,row)}'


def build_monthly_workbook(context, month, variant):
    """Заполнить книгу для скачивания или печати.

    views.report проверяет период и разрешает этот экспорт только за один
    месяц; сюда поступают уже отфильтрованные данные отчёта. Подписант берётся
    из текущей единственной записи админки.
    variant='economists' выбирает только ECONOMIST_SHEETS; 'all' — весь шаблон.
    'centers' и 'subscribers' заполняют лист согласования/оператора для печати.
    """
    from .models import StatisticsSigner
    # Импорты зависимостей отложены до построения книги, чтобы обычные страницы
    # статистики не требовали загрузки библиотек экспорта.
    load_export_dependencies()
    from openpyxl import Workbook, load_workbook
    from openpyxl.workbook.properties import CalcProperties
    signer=StatisticsSigner.objects.first()
    template=load_workbook(TEMPLATE,data_only=False,keep_links=False)
    try:
        # Планы нужны сразу для всех листов: формула на одном листе может
        # ссылаться на другой, строки которого тоже расширяются.
        datasets=_datasets(context)
        # Оба варианта используют один шаблон и общий механизм заполнения.
        # Отсутствующий обязательный лист — ошибка шаблона, а не повод выдать
        # неполный файл для экономистов. Ненужные листы в этой книге не создаём.
        if variant == 'economists':
            missing = [name for name in ECONOMIST_SHEETS if name not in template.sheetnames]
            if missing:
                raise TemplateExportError('В шаблоне отсутствуют листы: ' + ', '.join(missing))
            sources = [template[name] for name in ECONOMIST_SHEETS]
        elif variant in ('centers', 'subscribers'):
            name = 'для согласования' if variant == 'centers' else 'для Оператора'
            if name not in template.sheetnames:
                raise TemplateExportError('В шаблоне отсутствует лист: ' + name)
            sources = [template[name]]
        elif variant == 'all':
            sources = list(template)
        else:
            raise TemplateExportError('Неизвестный вариант скачивания.')
        plans={sheet.title:_plan(sheet,datasets) for sheet in sources}
        # Создаём отдельную книгу: исходный файл остаётся шаблоном.
        # Удаляем стандартный пустой лист и создаём листы в порядке шаблона.
        book=Workbook()
        book.remove(book.active)
        book.loaded_theme=template.loaded_theme
        book.properties=copy(template.properties)
        book.calculation=copy(template.calculation) if template.calculation else CalcProperties()
        # openpyxl сохраняет формулы, но не вычисляет их результаты.
        # Excel должен пересчитать итоги и TODAY() при открытии файла.
        book.calculation.fullCalcOnLoad=True
        book.calculation.forceFullCalc=True
        for source in sources:
            _fill_sheet(source,book.create_sheet(source.title),plans[source.title],plans,month,signer)
        return book
    finally:
        template.close()


def export_monthly_workbook(context, variant='all'):
    """Вернуть заполненную месячную книгу как скачиваемый XLSX."""
    month = date.fromisoformat(context['month'] + '-01')
    book = build_monthly_workbook(context, month, variant)
    output = BytesIO()
    try:
        book.save(output)
    finally:
        book.close()
    # attachment предлагает браузеру скачать книгу. Django корректно кодирует
    # русское имя для Content-Disposition; месяц зависит от локали приложения.
    # Для изменения схемы имени файла править filename ниже.
    response=HttpResponse(output.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename=f"Статистика_{date_format(month,'F').lower()}_{month.year}.xlsx"
    if variant == 'economists':
        filename = filename.removesuffix('.xlsx') + '_для_экономистов.xlsx'
    response['Content-Disposition']=content_disposition_header(True,filename)
    return response
