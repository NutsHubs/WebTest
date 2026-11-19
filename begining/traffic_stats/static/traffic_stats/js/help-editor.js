(() => {
    'use strict';
    const source = document.getElementById('help-description');
    if (!source || !window.Jodit) return;

    // The toolbar uses formats accepted by the help page sanitizer.
    const editor = Jodit.make(source, {
        language: 'ru',
        minHeight: 320,
        toolbarAdaptive: false,
        buttons: ['paragraph', 'font', 'fontsize', 'lineHeight', '|', 'bold', 'italic', 'underline', '|',
            'ul', 'ol', 'align', '|', 'undo', 'redo'],
        askBeforePasteHTML: false,
        processPasteFromWord: false,
        defaultActionOnPaste: 'insert_only_text',
    });
    source.form.addEventListener('submit', () => { source.value = editor.value; });
})();
