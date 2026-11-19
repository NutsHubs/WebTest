import calendar
import csv
import re
from datetime import date

class ImportError(ValueError):
    pass

def decode(data):
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportError('Не удалось прочитать кодировку файла.')

def without_aftn_totals(text):
    lines = text.splitlines(keepends=True)
    first = next((line.strip() for line in lines if line.strip()), '')
    if first != 'AFTN':
        return text
    return ''.join(line for line in lines if not re.match(r'^\s*ИТОГО(?:\s|:|;|$)', line, re.I))


def parse(text):
    text = without_aftn_totals(text)
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    if not lines:
        raise ImportError('Файл пуст.')
    kind = lines[0]
    if kind not in ('AFTN', 'AMHS'):
        raise ImportError('Первая строка файла должна содержать AFTN или AMHS.')
    if len(lines) < 2:
        raise ImportError('Не указан отчётный период.')
    period = lines[1]
    if kind == 'AFTN':
        match = re.fullmatch(r'(\d{2})\.(\d{2})\s*-\s*(\d{2})\.(\d{2})\s+(\d{4})', period)
        if not match:
            raise ImportError('Период AFTN должен иметь вид 01.05-31.05 2026.')
        d1, m1, d2, m2, year = map(int, match.groups())
    else:
        match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2})\.(\d{2})\.(\d{4})', period)
        if not match:
            raise ImportError('Период AMHS должен иметь вид 01.10.2026-31.10.2026.')
        d1, m1, year, d2, m2, year2 = map(int, match.groups())
        if year != year2:
            raise ImportError('Период должен быть одним месяцем.')
    data = lines[2:]
    try:
        month = date(year, m1, 1)
        if d1 != 1 or m1 != m2 or d2 != calendar.monthrange(year, m1)[1]:
            raise ValueError()
    except ValueError:
        raise ImportError('Нужен полный календарный месяц.')
    rows, seen = [], {}
    for line in data:
        fields = next(csv.reader([line], delimiter=';'))
        fields = [v.strip() for v in fields]
        if len(fields) != (6 if kind == 'AFTN' else 3):
            raise ImportError(f'Некорректное число полей: {line[:100]}')
        if kind == 'AFTN' and (not re.fullmatch(r'[0-9]+', fields[0]) or int(fields[0]) > 2147483647):
            raise ImportError('Некорректный логический номер канала.')
        key = fields[2] if kind == 'AFTN' else fields[0]
        if not key or len(key)>200 or (kind == 'AFTN' and not re.fullmatch(r'[А-ЯA-ZЁ]{8}', key)):
            raise ImportError(f'Некорректное имя/маршрут канала: {key}')
        if kind == 'AMHS' and key in seen:
            raise ImportError(f'Повтор канала: {key}')
        counts = fields[4:] if kind == 'AFTN' else fields[1:]
        if any(not re.fullmatch(r'[0-9]+', x) or int(x)>9223372036854775807 for x in counts):
            raise ImportError(f'Некорректные счётчики канала {key}.')
        counts = list(map(int, counts))
        if kind == 'AFTN' and key in seen:
            row = seen[key]
            received, sent = row['received'] + counts[0], row['sent'] + counts[1]
            if max(received, sent) > 9223372036854775807:
                raise ImportError(f'Сумма счётчиков канала {key} превышает допустимое значение.')
            name = row['source_name'] + ' / ' + fields[3]
            if len(name) > 200:
                raise ImportError(f'Объединённое название канала {key} должно быть не длиннее 200 символов.')
            row.update(received=received, sent=sent, source_name=name, designation='', merged=True)
            continue
        rows.append(dict(route_address=key if kind=='AFTN' else '', number=fields[0] if kind=='AFTN' else '', designation=fields[1] if kind=='AFTN' else '', source_name=fields[3] if kind=='AFTN' else key, received=counts[0], sent=counts[1]))
        seen[key] = rows[-1]
    if not rows:
        raise ImportError('Нет строк каналов.')
    return dict(kind=kind, month=month.isoformat(), rows=rows)


def parse_pasted_reports(text):
    """Каждый отчёт начинается с отдельной строки AFTN или AMHS."""
    text = text.lstrip('\ufeff').strip()
    if not text:
        raise ImportError('Вставьте текст статистики или выберите файл.')
    parts = re.split(r'(?m)^(?=[^\S\n]*(?:AFTN|AMHS)[^\S\n]*$)', text)
    sources = [part.strip() for part in parts if part.strip()]
    if len(sources) > 2:
        raise ImportError('Вставьте не более двух отчётов за одну загрузку.')
    reports, seen = [], set()
    for number, source in enumerate(sources, 1):
        source = without_aftn_totals(source)
        try:
            report = parse(source)
        except ImportError as exc:
            raise ImportError(f'Отчёт {number}: {exc}') from exc
        key = report['kind']
        if key in seen:
            raise ImportError('За одну загрузку можно вставить один отчёт AFTN и один AMHS.')
        seen.add(key)
        reports.append(dict(report, source=source, filename='Вставленный текст'))
    return reports
