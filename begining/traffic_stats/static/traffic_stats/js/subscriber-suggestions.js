(() => {
    'use strict';
    const source = document.getElementById('upload-subscribers');
    if (!source) return;
    const normalize = value => value.trim().toLocaleLowerCase('ru-RU');
    const subscribers = () => Array.from(source.options, option => ({name: option.value, category: option.dataset.category}));
    const popup = document.createElement('div');
    popup.id = 'stats-subscriber-suggestions';
    popup.className = 'stats-subscriber-suggestions';
    popup.setAttribute('role', 'listbox');
    popup.setAttribute('aria-label', 'Найденные абоненты');
    popup.hidden = true;
    document.body.append(popup);
    let active = null, matches = [], selected = -1;
    function close() {
        if (active) {
            active.setAttribute('aria-expanded', 'false');
            active.removeAttribute('aria-activedescendant');
        }
        popup.hidden = true;
        selected = -1;
    }
    function categoryFor(input) {
        return input.closest('tr').querySelector('select[name^="category_"]');
    }
    function synchronize(input, chosen = false) {
        const category = categoryFor(input);
        const match = subscribers().find(sub => sub.name === input.value.trim());
        const editable = input.hasAttribute('data-edit-existing-category');
        const previous = input.dataset.matchedSubscriber || '';
        if (match && (chosen || !editable || previous !== match.name)) category.value = match.category;
        else if (!match && (previous || category.disabled)) category.value = 'other';
        category.disabled = Boolean(match) && !editable;
        input.dataset.matchedSubscriber = match ? match.name : '';
    }
    function choose(index) {
        if (!active || !matches[index]) return;
        active.value = matches[index].name;
        synchronize(active, true);
        close();
        active.focus();
    }
    function highlight(index) {
        selected = index;
        Array.from(popup.children).forEach((option, i) => option.setAttribute('aria-selected', String(i === index)));
        const option = popup.children[index];
        active.setAttribute('aria-activedescendant', option.id);
        option.scrollIntoView({block: 'nearest'});
    }
    function show(input) {
        if (active !== input) close();
        active = input;
        const query = normalize(input.value);
        matches = query ? subscribers().filter(sub => normalize(sub.name).includes(query)).slice(0, 20) : [];
        popup.replaceChildren();
        selected = -1;
        input.removeAttribute('aria-activedescendant');
        if (!matches.length) { close(); return; }
        matches.forEach((subscriber, index) => {
            const option = document.createElement('div');
            option.id = 'stats-subscriber-option-' + index;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');
            option.textContent = subscriber.name;
            option.addEventListener('pointerdown', event => { event.preventDefault(); choose(index); });
            popup.append(option);
        });
        const rect = input.getBoundingClientRect();
        popup.style.width = Math.min(Math.max(rect.width, 220), window.innerWidth - 16) + 'px';
        popup.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - parseFloat(popup.style.width) - 8)) + 'px';
        const below = window.innerHeight - rect.bottom - 8;
        const above = rect.top - 8;
        const upwards = below < 160 && above > below;
        popup.style.maxHeight = Math.max(40, Math.min(240, upwards ? above : below)) + 'px';
        popup.style.top = upwards ? 'auto' : rect.bottom + 'px';
        popup.style.bottom = upwards ? window.innerHeight - rect.top + 'px' : 'auto';
        popup.hidden = false;
        input.setAttribute('aria-expanded', 'true');
    }
    document.querySelectorAll('input[data-subscriber-autocomplete]').forEach(input => {
        // Keep the native datalist available when JavaScript is disabled.
        input.removeAttribute('list');
        input.autocomplete = 'off';
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-controls', popup.id);
        input.setAttribute('aria-expanded', 'false');
        synchronize(input);
        input.addEventListener('stats-subscriber-sync', () => synchronize(input));
        input.addEventListener('focus', () => { synchronize(input); show(input); });
        input.addEventListener('input', () => { synchronize(input); show(input); });
        input.addEventListener('blur', close);
        input.addEventListener('keydown', event => {
            if (event.key === 'Escape') { close(); return; }
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (popup.hidden || active !== input) show(input);
                if (popup.hidden) return;
                highlight((selected + (event.key === 'ArrowDown' ? 1 : selected < 0 ? 0 : -1) + matches.length) % matches.length);
            } else if (event.key === 'Enter' && !popup.hidden && selected >= 0) {
                event.preventDefault(); choose(selected);
            }
        });
    });
    window.addEventListener('resize', close);
    document.addEventListener('scroll', event => { if (!popup.contains(event.target)) close(); }, true);
})();
