(() => {
    'use strict';
    const form = document.getElementById('stats-upload-form');
    const file = form.elements.file;
    const pastedText = form.elements.statistics_text;

    file.addEventListener('change', () => {
        if (!file.files.length) return;
        // Choosing a file explicitly submits just the file, even if text is present.
        if (pastedText) pastedText.disabled = true;
        try {
            form.requestSubmit();
        } finally {
            if (pastedText) pastedText.disabled = false;
        }
    });
})();
