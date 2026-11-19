(() => {
    'use strict';
    const table = document.querySelector('.stats .category-report');
    const token = document.querySelector('.stat-correction-token input');
    const error = document.querySelector('.stat-edit-error');
    if (!table || !token) return;
    function fail(message) { error.textContent = message; error.hidden = false; }
    function normalized(value) { return /^[0-9]{1,19}$/.test(value) ? BigInt(value).toString() : value; }
    function changed(cell) {
        const input = cell.querySelector('input');
        const pending = normalized(input.value.trim()) !== cell.dataset.value;
        cell.nextElementSibling.querySelector('.stat-save').hidden = !pending;
        cell.nextElementSibling.querySelector('.stat-undo').hidden = pending || cell.dataset.value === cell.dataset.original;
        cell.nextElementSibling.querySelector('.stat-info').hidden = cell.dataset.value === cell.dataset.original;
        const value = cell.querySelector('.stat-counter-value');
        if (cell.dataset.value !== cell.dataset.original) {
            value.title = 'Исходное значение: ' + cell.dataset.original;
        } else {
            value.removeAttribute('title');
        }
    }
    function recalculate(section) {
        const leaves = Array.from(section.querySelectorAll('.editable-stat'));
        for (const field of ['received','sent']) {
            const relevant = leaves.filter(cell => cell.dataset.counterField === field);
            section.querySelector(`[data-total-field="${field}"]`).textContent = relevant.reduce((sum, cell) => sum + BigInt(cell.dataset.value), 0n).toString();
            section.querySelectorAll('[data-summary-subscriber]').forEach(row => {
                const total = relevant.filter(cell => cell.dataset.subscriberId === row.dataset.summarySubscriber).reduce((sum, cell) => sum + BigInt(cell.dataset.value), 0n);
                const cell = row.querySelector(`[data-counter-field="${field}"]`);
                cell.dataset.value = total.toString();
                cell.querySelector('.stat-counter-value').textContent = total.toString();
            });
        }
    }
    table.querySelectorAll('.stat-edit-category:not(:disabled)').forEach(button => {
        button.addEventListener('click', () => {
            const section = button.closest('tbody');
            const editing = section.classList.toggle('is-editing');
            button.setAttribute('aria-pressed', String(editing));
            if (editing) section.querySelector('.stat-editor input')?.focus();
        });
    });
    table.querySelectorAll('.editable-stat').forEach(cell => {
        const input = cell.querySelector('input');
        const button = cell.nextElementSibling.querySelector('.stat-save');
        const undo = cell.nextElementSibling.querySelector('.stat-undo');
        input.addEventListener('input', () => changed(cell));
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') { event.preventDefault(); if (!button.hidden) button.click(); }
            if (event.key === 'Escape') { input.value = cell.dataset.value; changed(cell); }
        });
        async function saveValue(text) {
            if (!/^[0-9]{1,19}$/.test(text) || BigInt(text) > 9223372036854775807n) {
                fail('Введите целое неотрицательное число не больше 9223372036854775807.'); input.focus(); return;
            }
            const value = normalized(text);
            const expected = cell.dataset.value;
            button.disabled = undo.disabled = input.disabled = true;
            error.hidden = true;
            try {
                const response = await fetch(cell.dataset.correctionUrl, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'X-CSRFToken': token.value, 'Content-Type':'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({field:cell.dataset.counterField,value,expected,month:table.dataset.reportMonth})
                });
                let data;
                try { data = await response.json(); } catch (_) { throw new Error('Не удалось сохранить значение. Обновите страницу и повторите.'); }
                if (!response.ok) throw new Error(data.error || 'Не удалось сохранить значение.');
                cell.dataset.value = data.value;
                input.value = data.value;
                cell.querySelector('.stat-counter-value').textContent = data.value;
                changed(cell);
                recalculate(cell.closest('tbody'));
            } catch (exception) { fail(exception.message || 'Ошибка соединения. Повторите сохранение.'); }
            finally { button.disabled = undo.disabled = input.disabled = false; }
        }
        button.addEventListener('click', () => saveValue(input.value.trim()));
        undo.addEventListener('click', () => saveValue(cell.dataset.original));
    });
})();
