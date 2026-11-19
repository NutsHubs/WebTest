(() => {
    'use strict';
    document.querySelectorAll('.breadcrumbs .stats-header-menu').forEach(menu => {
        const dropdown = menu.querySelector('.stats-header-dropdown');
        const summary = dropdown.querySelector('summary');
        menu.addEventListener('pointerenter', event => {
            if (event.pointerType === 'mouse') dropdown.open = true;
        });
        menu.addEventListener('pointerleave', event => {
            if (event.pointerType === 'mouse' && !menu.contains(document.activeElement)) dropdown.open = false;
        });
        menu.addEventListener('focusout', event => {
            if (!menu.contains(event.relatedTarget) && !menu.matches(':hover')) dropdown.open = false;
        });
        menu.addEventListener('keydown', event => {
            if (event.key === 'Escape' && dropdown.open) {
                event.preventDefault();
                dropdown.open = false;
                summary.focus();
            }
        });
        document.addEventListener('click', event => {
            if (!menu.contains(event.target)) dropdown.open = false;
        });
    });
})();
