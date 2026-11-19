(() => {
    'use strict';

    document.querySelector('.category-report').addEventListener('click', event => {
        const toggle = event.target.closest('.stat-month-toggle');
        if (!toggle) return;

        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!expanded));
        let row = toggle.closest('tr').nextElementSibling;
        while (row && row.classList.contains('stat-month-row')) {
            row.hidden = expanded;
            row = row.nextElementSibling;
        }
    });
})();
