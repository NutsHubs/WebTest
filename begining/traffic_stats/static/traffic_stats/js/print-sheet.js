(() => {
    'use strict';
    const printSheet = () => window.print();
    document.querySelector('[data-print-sheet]').addEventListener('click', printSheet);
    // Дожидаемся шрифтов и полной загрузки, чтобы диалог получил готовый лист.
    window.addEventListener('load', async () => {
        if (document.fonts) await document.fonts.ready;
        printSheet();
    }, {once: true});
})();
