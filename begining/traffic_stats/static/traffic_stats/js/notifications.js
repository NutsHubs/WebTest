(() => {
    'use strict';
    document.querySelectorAll('.stats-toast[data-auto-dismiss]').forEach(toast => {
        let timer, closing = false;
        function pause() { window.clearTimeout(timer); }
        function close() {
            if (closing) return;
            closing = true;
            pause();
            toast.classList.add('is-closing');
            window.setTimeout(() => toast.remove(), 200);
        }
        function resume() {
            pause();
            if (!closing && !toast.matches(':hover') && !toast.contains(document.activeElement)) timer = window.setTimeout(close, 4000);
        }
        toast.querySelector('.stats-toast-close').addEventListener('click', close);
        toast.addEventListener('pointerenter', pause);
        toast.addEventListener('pointerleave', resume);
        toast.addEventListener('focusin', pause);
        toast.addEventListener('focusout', event => { if (!toast.contains(event.relatedTarget)) window.setTimeout(resume, 0); });
        resume();
    });
})();
