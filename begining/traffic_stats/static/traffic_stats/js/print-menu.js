(() => {
    'use strict';
    const menus = document.querySelectorAll('.stats-report-heading .stats-print-menu');
    menus.forEach(menu => {
        menu.addEventListener('toggle', () => {
            if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; });
        });
        menu.addEventListener('click', event => {
            if (event.target.closest('.stats-print-options a[href]')) {
                menu.open = false;
                menu.querySelector('summary').focus({ preventScroll: true });
            }
        });
        document.addEventListener('click', event => {
            if (!menu.contains(event.target)) menu.open = false;
        });
        menu.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                menu.open = false;
                menu.querySelector('summary').focus();
            }
        });
    });
})();
