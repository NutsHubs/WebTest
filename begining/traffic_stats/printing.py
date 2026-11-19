"""Браузерная печать листов статистики из той же книги, что заполняет экспорт.

Не дублируем правила расчёта или разметку таблицы: сначала заполняем только
нужный лист Excel, затем переводим его ячейки и оформление в HTML.
Печать выполняет браузер пользователя; доступ к принтеру сервера не требуется.
"""
from datetime import date, datetime
import re

from .monthly_export import build_monthly_workbook, TemplateExportError

# Верхнее и нижнее поля браузерной печати (Excel-шаблон не изменяется).
PRINT_VERTICAL_MARGIN_MM = 10


def _color(color):
    """Частые цвета шаблона: RGB, стандартная палитра и чёрный/белый темы."""
    from openpyxl.styles.colors import COLOR_INDEX
    if color is None:
        return None
    value = None
    if color.type == 'rgb':
        value = color.rgb
    elif color.type == 'indexed' and 0 <= color.indexed < len(COLOR_INDEX):
        value = COLOR_INDEX[color.indexed]
    elif color.type == 'theme':
        value = {0:'FFFFFF', 1:'000000'}.get(color.theme)
    return '#' + value[-6:] if isinstance(value, str) and re.fullmatch(r'[0-9A-Fa-f]{6,8}', value) else None


def _cell_style(cell):
    """Перенести шрифт, заливку, выравнивание и границы ячейки в CSS."""
    font, align = cell.font, cell.alignment
    family = re.sub(r'[^\w ,.-]', '', font.name or 'Arial')
    rules = [f'font-family:{family},Arial,sans-serif', f'font-size:{font.sz or 11}pt',
             'white-space:pre-wrap' if align.wrap_text else 'white-space:pre',
             'overflow-wrap:anywhere' if align.wrap_text else 'overflow-wrap:normal']
    if font.b:
        rules.append('font-weight:bold')
    if font.i:
        rules.append('font-style:italic')
    if font.u:
        rules.append('text-decoration:underline')
    if _color(font.color):
        rules.append('color:' + _color(font.color))
    if cell.fill.patternType == 'solid' and _color(cell.fill.fgColor):
        rules.append('background-color:' + _color(cell.fill.fgColor))
    horizontal = align.horizontal
    if horizontal in ('left', 'center', 'right', 'justify'):
        rules.append('text-align:' + horizontal)
    else:
        rules.append('text-align:' + ('right' if isinstance(cell.value, (int, float)) else 'left'))
    rules.append('vertical-align:' + {'top':'top', 'bottom':'bottom'}.get(align.vertical, 'middle'))
    for edge in ('top', 'right', 'bottom', 'left'):
        side = getattr(cell.border, edge)
        if side and side.style:
            weight = {'medium':1.5, 'thick':2, 'double':2}.get(side.style, .5)
            line = 'double' if side.style == 'double' else 'dotted' if side.style in ('dotted', 'hair') else 'dashed' if 'dash' in side.style.lower() else 'solid'
            rules.append(f'border-{edge}:{weight}pt {line} {_color(side.color) or "#000000"}')
    return ';'.join(rules)


def _print_value(cell, visited=None):
    """Вычислить SUM и TODAY для печати без Excel и без eval.

    В операторском шаблоне итоги — SUM(C13:C...), диапазон уже расширен
    общим экспортом. Пустые и текстовые ячейки не участвуют в сумме.
    Произвольные формулы не исполняем: неподдерживаемая формула или цикл
    возвращают понятную ошибку вместо неправильного результата на бумаге.
    """
    if cell.data_type != 'f':
        return cell.value
    if re.fullmatch(r'=TODAY\(\s*\)', cell.value, re.I):
        # Текущая дата в часовом поясе приложения, в том числе при USE_TZ=False.
        from django.utils import timezone
        return datetime.now(timezone.get_current_timezone()).date()
    visited = set() if visited is None else visited
    if cell.coordinate in visited:
        raise TemplateExportError(f'Циклическая формула в ячейке {cell.coordinate}.')
    match = re.fullmatch(r'=SUM\(\s*(\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+)\s*\)', cell.value, re.I)
    if not match:
        raise TemplateExportError(f'Неподдерживаемая формула для печати в ячейке {cell.coordinate}: {cell.value}')
    path = visited | {cell.coordinate}
    values = (_print_value(item, path) for row in cell.parent[match.group(1).replace('$', '')] for item in row)
    return sum(value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool))


def _display(cell):
    """Текст ячейки для HTML; данные экранируются шаблонизатором Django."""
    value = _print_value(cell)
    if value is None:
        return ''
    if isinstance(value, (date, datetime)):
        return value.strftime('%d.%m.%Y')
    if isinstance(value, (int, float)):
        if value == int(value):
            return format(int(value), ',').replace(',', ' ') if ',' in cell.number_format else str(int(value))
    return str(value)


def _sheet_context(sheet):
    """Перенести один заполненный лист в HTML: ячейки, размеры и параметры печати.

    Область печати берём из XLSX. Объединения становятся colspan/rowspan,
    перекрытые ячейки пропускаются. Высота минимальная: браузер может увеличить
    строку под длинный текст. Каждый лист получает собственную именованную
    страницу CSS, чтобы сохранить его размер бумаги, ориентацию и поля.
    """
    from openpyxl.utils.cell import range_boundaries
    area = re.search(r'\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+', str(sheet.print_area))
    left, top, right, bottom = range_boundaries(area.group() if area else sheet.calculate_dimension())
    columns = []
    for col in range(left, right + 1):
        dim = next((d for d in sheet.column_dimensions.values() if d.min <= col <= d.max), None)
        # Ширины Excel измеряются в символах; приближённый перевод в пункты.
        columns.append(dict(width=((dim.width if dim else sheet.sheet_format.defaultColWidth or 13) * 7 + 5) * .75,
                            hidden=bool(dim and dim.hidden)))
    merged, covered = {}, set()
    for region in sheet.merged_cells.ranges:
        if region.max_col < left or region.min_col > right or region.max_row < top or region.min_row > bottom:
            continue
        r1, r2 = max(top, region.min_row), min(bottom, region.max_row)
        c1, c2 = max(left, region.min_col), min(right, region.max_col)
        merged[r1, c1] = (r2-r1+1, c2-c1+1)
        covered.update((row, col) for row in range(r1, r2+1) for col in range(c1, c2+1) if (row, col) != (r1, c1))
    rows = []
    for index in range(top, bottom + 1):
        dim = sheet.row_dimensions[index]
        if dim.hidden:
            continue
        cells = []
        for col in range(left, right + 1):
            if (index, col) in covered:
                continue
            cell = sheet.cell(index, col)
            rowspan, colspan = merged.get((index, col), (1, 1))
            cells.append(dict(value=_display(cell), style=_cell_style(cell), rowspan=rowspan, colspan=colspan,
                              hidden=columns[col-left]['hidden']))
        rows.append(dict(height=dim.height or sheet.sheet_format.defaultRowHeight or 15, cells=cells))
    margins = sheet.page_margins
    paper = {'8':'A3', '9':'A4', '11':'A5', '1':'letter', '5':'legal'}.get(str(sheet.page_setup.paperSize), 'A4')
    orientation = 'landscape' if sheet.page_setup.orientation == 'landscape' else 'portrait'
    return dict(sheet_label=sheet.title, rows=rows, columns=columns,
                table_width=sum(c['width'] for c in columns if not c['hidden']),
                page_size=paper + ' ' + orientation,
                # Порядок CSS: верх, право, низ, лево. Боковые поля — из XLSX.
                margins=f'{PRINT_VERTICAL_MARGIN_MM}mm {margins.right * 72:g}pt '
                        f'{PRINT_VERTICAL_MARGIN_MM}mm {margins.left * 72:g}pt')


def sheet_print_context(context, variant='centers'):
    """Подготовить один или несколько листов для одного диалога печати.

    «Каналы» используют тот же состав, что файл для экономистов. «Все» —
    весь шаблон в исходном порядке. Повторно заполнять отдельные книги нельзя:
    общая книга сохраняет единые данные и планы строк для всех листов.
    """
    title = {
        'centers': 'Согласование',
        'subscribers': 'Рассылка абонентам',
        'channels': 'Каналы',
        'all': 'Вся статистика',
    }[variant]
    export_variant = 'economists' if variant == 'channels' else variant
    month = date.fromisoformat(context['month'] + '-01')
    book = build_monthly_workbook(context, month, export_variant)
    try:
        sheets = [_sheet_context(sheet) for sheet in book]
        # Верхние ключи первого листа сохраняем для существующих потребителей
        # однолистовой формы. HTML перебирает sheets для любого варианта печати.
        return dict(sheets[0], title=title + ' — ' + context['period_label'], sheets=sheets)
    finally:
        book.close()
