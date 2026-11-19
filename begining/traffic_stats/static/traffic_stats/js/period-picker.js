/* Progressive enhancement: the server still receives YYYY-MM month fields. */
(() => {
    'use strict';
    const form = document.querySelector('.stats form.filters');
    if (!form || typeof window.AirDatepicker !== 'function') return;
    const nativeFields = form.querySelector('.stats-period-native');
    const pickerFields = form.querySelector('.stats-period-picker');
    const start = form.elements.month;
    const end = form.elements.end_month;
    const input = form.querySelector('#report-period');
    const error = form.querySelector('#report-period-error');
    const clear = form.querySelector('[data-clear-period]');
    const monthName = new Intl.DateTimeFormat('ru-RU', {month: 'long'});
    const initialValues = [start.value, end.value];
    let picker;
    input.addEventListener('change', () => {
        input.value = input.value.toLocaleLowerCase('ru-RU');
    });

    function parseMonth(value) {
        if (!/^\d{4}-\d{2}$/.test(value)) return null;
        const [year, month] = value.split('-').map(Number);
        if (year < 1000 || month < 1 || month > 12) return null;
        return new Date(year, month - 1, 1);
    }
    function wireMonth(date) {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    }
    function formatMonth(date) {
        return `${monthName.format(date)} ${date.getFullYear()}`;
    }
    function synchronize(value) {
        const dates = (Array.isArray(value) ? value : value ? [value] : []).slice().sort((a, b) => a - b);
        input.value = dates.map(formatMonth).join(' — ');
        start.value = dates.length ? wireMonth(dates[0]) : '';
        end.value = dates.length ? wireMonth(dates[dates.length - 1]) : '';
        error.textContent = '';
        error.hidden = true;
        input.removeAttribute('aria-invalid');
    }
    const selectedDates = [...new Set(initialValues.filter(Boolean))].map(parseMonth).filter(Boolean);
    try {
        picker = new AirDatepicker(input, {
            view: 'months',
            minView: 'months',
            range: true,
            toggleSelected: false,
            multipleDatesSeparator: ' — ',
            classes: 'stats-period-calendar',
            isMobile: window.matchMedia('(max-width: 767px)').matches,
            selectedDates,
            startDate: selectedDates[0] || new Date(),
            dateFormat: 'MMMM yyyy',
            onSelect({date}) {
                synchronize(date);
                if (Array.isArray(date) && date.length === 2 && picker) picker.hide();
            }
        });
        synchronize(selectedDates);
        start.required = false;
        start.type = 'hidden';
        end.type = 'hidden';
        nativeFields.hidden = true;
        pickerFields.hidden = false;
        input.disabled = false;
        clear.addEventListener('click', () => {
            picker.clear();
            input.focus();
        });
        form.addEventListener('submit', event => {
            if (start.value) return;
            event.preventDefault();
            error.textContent = 'Выберите месяц или диапазон месяцев.';
            error.hidden = false;
            input.setAttribute('aria-invalid', 'true');
            input.focus();
            picker.show();
        });
    } catch (exception) {
        if (picker) picker.destroy();
        start.type = end.type = 'month';
        start.value = initialValues[0];
        end.value = initialValues[1];
        start.required = true;
        nativeFields.hidden = false;
        pickerFields.hidden = true;
        input.disabled = true;
        console.warn('Календарь периода недоступен; используются стандартные поля.', exception);
    }
})();
