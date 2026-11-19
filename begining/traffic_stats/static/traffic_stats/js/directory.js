(() => {
    'use strict';
    const table = document.querySelector('.subscriber-directory');
    const token = document.querySelector('.directory-token input');
    const error = document.querySelector('.directory-error');
    const source = document.getElementById('upload-subscribers');
    if (!table || !token) return;
    function fail(message) { error.textContent = message; error.hidden = false; }
    function state(row) {
        return {subscriber_id:Number(row.dataset.subscriberId), category:row.dataset.category,
            route_address:row.dataset.routeAddress, mailing_received:row.dataset.mailingReceived === '1',
            mailing_sent:row.dataset.mailingSent === '1', mailing_addresses:row.dataset.mailingAddresses};
    }
    table.querySelectorAll('tr[data-assign-url]').forEach(row => {
        const input = row.querySelector('input[data-subscriber-autocomplete]');
        const category = row.querySelector('select');
        const address = row.querySelector('[data-channel-field=route_address]');
        const received = row.querySelector('[data-channel-field=mailing_received]');
        const sent = row.querySelector('[data-channel-field=mailing_sent]');
        const mailing = row.querySelector('[data-channel-field=mailing_addresses]');
        const edit = row.querySelector('.directory-edit');
        const save = row.querySelector('.directory-save');
        const fields = [input, category, address, received, sent, mailing];
        edit.hidden = false;
        function setEditing(editing) {
            row.classList.toggle('is-editing', editing);
            edit.setAttribute('aria-pressed', String(editing));
            edit.title = editing ? 'Отменить редактирование' : 'Редактировать';
            save.hidden = !editing;
            input.value = row.dataset.subscriberName;
            category.value = row.dataset.category;
            address.value = row.dataset.routeAddress;
            received.checked = row.dataset.mailingReceived === '1';
            sent.checked = row.dataset.mailingSent === '1';
            mailing.value = row.dataset.mailingAddresses.replace(/[\r\n]+/g, ', ');
            received.disabled = sent.disabled = !editing;
            input.dispatchEvent(new Event('stats-subscriber-sync'));
            if (editing) input.focus();
        }
        edit.addEventListener('click', () => setEditing(!row.classList.contains('is-editing')));
        row.addEventListener('keydown', event => {
            if (event.defaultPrevented || !row.classList.contains('is-editing')) return;
            if (event.key === 'Escape') { event.preventDefault(); setEditing(false); edit.focus(); }
            if (event.key === 'Enter' && [input, address].includes(event.target)) { event.preventDefault(); save.click(); }
        });
        save.addEventListener('click', async () => {
            const name = input.value.trim();
            if (!name || name.length > 200) { fail('Укажите имя абонента длиной до 200 символов.'); input.focus(); return; }
            if ((!address.value.trim() && row.dataset.kind === 'AFTN') || address.value.trim().length > 200) { fail('Укажите адрес канала длиной до 200 символов.'); address.focus(); return; }
            if (mailing.value.trim().length > 200) { fail('Адреса рассылки должны содержать не больше 200 символов.'); mailing.focus(); return; }
            const body = new URLSearchParams({subscriber_name:name, category:category.value,
                expected_subscriber:row.dataset.subscriberId, expected_state:JSON.stringify(state(row)),
                route_address:address.value.trim(), mailing_received:received.checked ? '1' : '0',
                mailing_sent:sent.checked ? '1' : '0', mailing_addresses:mailing.value});
            save.disabled = edit.disabled = true;
            fields.forEach(field => { field.disabled = true; });
            error.hidden = true;
            let saved = false;
            try {
                const response = await fetch(row.dataset.assignUrl, {
                    method:'POST', credentials:'same-origin',
                    headers:{'X-CSRFToken':token.value,'Content-Type':'application/x-www-form-urlencoded'}, body
                });
                let data;
                try { data = await response.json(); } catch (_) { throw new Error('Не удалось сохранить. Обновите страницу и повторите.'); }
                if (!response.ok) throw new Error(data.error || 'Не удалось сохранить канал.');
                row.dataset.subscriberId = String(data.subscriber_id);
                row.dataset.subscriberName = data.subscriber_name;
                row.dataset.category = data.category;
                row.dataset.routeAddress = data.route_address;
                row.dataset.mailingReceived = data.mailing_received ? '1' : '0';
                row.dataset.mailingSent = data.mailing_sent ? '1' : '0';
                row.dataset.mailingAddresses = data.mailing_addresses;
                row.querySelector('.directory-name').textContent = data.subscriber_name;
                row.querySelector('.directory-route-label').textContent = data.route_address;
                row.querySelector('.directory-category-label').textContent = data.category_label;
                row.querySelector('.directory-mailing-label').textContent = data.mailing_addresses;
                if (data.removed_subscriber_name) {
                    Array.from(source.options).filter(option => option.value === data.removed_subscriber_name).forEach(option => option.remove());
                }
                let option = Array.from(source.options).find(item => item.value === data.subscriber_name);
                if (!option) { option = document.createElement('option'); option.value = data.subscriber_name; source.append(option); }
                option.dataset.category = data.category;
                table.querySelectorAll('tr[data-assign-url]').forEach(other => {
                    if (other !== row && other.dataset.subscriberId === String(data.subscriber_id) && !other.classList.contains('is-editing')) {
                        other.dataset.category = data.category;
                        other.querySelector('.directory-category-label').textContent = data.category_label;
                        other.querySelector('select').value = data.category;
                    }
                });
                saved = true;
                setEditing(false);
            } catch (exception) { fail(exception.message || 'Ошибка соединения. Повторите сохранение.'); }
            finally {
                save.disabled = edit.disabled = false;
                fields.forEach(field => { field.disabled = false; });
                received.disabled = sent.disabled = saved;
                input.dispatchEvent(new Event('stats-subscriber-sync'));
            }
        });
    });
})();
