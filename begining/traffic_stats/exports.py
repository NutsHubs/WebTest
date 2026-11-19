from io import BytesIO
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from .reporting import report_rows


def filter_text(c):
    from .models import Subscriber, CATEGORIES
    names = ', '.join(Subscriber.objects.filter(pk__in=c['selected']).values_list('name',flat=True)) if c['selected'] else 'все'
    return f"Тип: {c['kind'] or 'все'}; категория: {dict(CATEGORIES).get(c['category'],'все')}; абоненты: {names}"


def load_export_dependencies():
    import sys
    local = Path(settings.BASE_DIR).parent / '.codex-deps'
    if local.is_dir() and str(local) not in sys.path:
        sys.path.append(str(local))


def export_report(context):
    load_export_dependencies()
    rows = report_rows(context, include_month_rows=True)
    title = context['report_title']
    filters = filter_text(context)
    output = BytesIO()
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    book = Workbook()
    sheet = book.active
    sheet.title = 'Статистика'
    sheet.append([title]); sheet.append([filters])
    previous_kind = None
    for row_kind, values in rows:
        sheet.append(values)
        index = sheet.max_row
        if row_kind == 'category':
            sheet.merge_cells(start_row=index,start_column=1,end_row=index,end_column=4)
        for cell in sheet[index]:
            if row_kind in ('category', 'header', 'total'):
                cell.fill = PatternFill('solid', fgColor='A7F3D7' if row_kind=='header' else 'FFF4D6')
                cell.font = Font(bold=True)
            if row_kind=='header':
                cell.alignment = Alignment(horizontal='center',vertical='top',wrap_text=True)
        if row_kind in ('subscriber', 'channel', 'month', 'total'):
            for column in ('B', 'C'):
                sheet[f'{column}{index}'].number_format = '#,##0'
        if row_kind == 'month':
            if previous_kind == 'subscriber':
                # The subscriber summary sits above the collapsed month rows.
                sheet.sheet_properties.outlinePr.summaryBelow = False
                sheet.row_dimensions[index - 1].collapsed = True
            dimension = sheet.row_dimensions[index]
            dimension.outlineLevel = 1
            dimension.hidden = True
        previous_kind = row_kind
    for row in sheet:
        for cell in row:
            if isinstance(cell.value,str):
                cell.data_type='s'
            if cell.alignment.horizontal != 'center':
                cell.alignment = Alignment(vertical='top',wrap_text=True)
    for index, (row_kind, values) in enumerate(rows, 3):
        if row_kind in ('subscriber', 'channel'):
            sheet[f'D{index}'].alignment = Alignment(horizontal='center',vertical='top',wrap_text=True)
        if row_kind == 'month':
            sheet[f'A{index}'].alignment = Alignment(vertical='top', wrap_text=True, indent=1)
        if row_kind == 'total':
            sheet[f'A{index}'].alignment = Alignment(horizontal='right',vertical='top',wrap_text=True)
    for column, width in [('A',48),('B',22),('C',22),('D',48)]:
        sheet.column_dimensions[column].width = width
    sheet.row_dimensions[2].height=45
    sheet.merge_cells('A1:D1'); sheet.merge_cells('A2:D2')
    sheet.freeze_panes='B5'
    sheet.print_title_rows='1:2'
    sheet.sheet_properties.pageSetUpPr.fitToPage=True
    sheet.page_setup.orientation='landscape'; sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth=1; sheet.page_setup.fitToHeight=0
    book.save(output)
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response=HttpResponse(output.getvalue(),content_type=mime)
    period_filename=context['month'] or 'empty'
    if context['end_month'] != context['month']:
        period_filename+='-to-'+context['end_month']
    response['Content-Disposition']=f'attachment; filename="statistics-{period_filename}.xlsx"'
    return response
