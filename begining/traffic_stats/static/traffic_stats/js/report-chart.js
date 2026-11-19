(() => {
    'use strict';

    const dialog = document.getElementById('stats-chart');
    const title = document.getElementById('stats-chart-title');
    const status = dialog.querySelector('[data-chart-status]');
    const content = dialog.querySelector('[data-chart-content]');
    const plot = dialog.querySelector('[data-chart-plot]');
    const plotScroll = plot.parentElement;
    const table = dialog.querySelector('[data-chart-values]');
    const gaps = dialog.querySelector('[data-chart-gap]');
    const download = dialog.querySelector('[data-chart-download]');
    const period = dialog.querySelector('[data-chart-period]');
    const monthLabel = new Intl.DateTimeFormat('ru', { month: 'short', year: 'numeric', timeZone: 'UTC' });
    const exactNumber = new Intl.NumberFormat('ru');
    const series = { received: 'Принято', sent: 'Передано' };
    let activeRequest;
    let chartExport;

    function monthIndex(month) {
        const [year, number] = month.split('-').map(Number);
        return year * 12 + number - 1;
    }

    function label(index) {
        const date = new Date(0);
        date.setUTCFullYear(Math.floor(index / 12), index % 12, 1);
        return monthLabel.format(date);
    }

    function draw(tag, attributes, text, parent = plot) {
        const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
        if (text !== undefined) node.textContent = text;
        parent.append(node);
        return node;
    }

    function renderChart({ month, end_month, points }) {
        const start = monthIndex(month);
        const end = monthIndex(end_month);
        const span = end - start;
        const top = 20, bottom = 273;
        const maximum = points.reduce((max, point) => {
            const received = BigInt(point.received);
            const sent = BigInt(point.sent);
            return received > max && received > sent ? received : sent > max ? sent : max;
        }, 0n);
        const tick = (maximum + 3n) / 4n || 1n;
        const axisTop = Number(4n * tick);
        const y = value => bottom - Number(value) / axisTop * (bottom - top);
        plot.replaceChildren();
        table.replaceChildren();

        const yLabels = [];
        for (let i = 0n; i <= 4n; i++) {
            const value = i * tick;
            const height = y(value);
            const text = draw('text', { y: height + 5, 'text-anchor': 'end' }, exactNumber.format(value));
            yLabels.push({ text, height });
        }
        // Reserve room for the full numbers using their rendered widths.
        const left = Math.max(60, Math.ceil(Math.max(...yLabels.map(item => item.text.getComputedTextLength()))) + 16);
        const rightPadding = 40;
        const width = Math.max(plotScroll.clientWidth, left + span * 48 + rightPadding);
        const right = width - rightPadding;
        const monthWidth = (right - left) / span;
        const x = index => left + (index - start) * monthWidth;
        plot.setAttribute('viewBox', '0 0 ' + width + ' 320');
        plot.style.width = width + 'px';
        for (const { text, height } of yLabels) {
            text.setAttribute('x', left - 9);
            draw('line', { x1: left, y1: height, x2: right, y2: height, class: 'chart-grid' });
        }
        const monthLabels = draw('g', { class: 'chart-month-labels' });
        function fillMonthLabels(target, first, last) {
            target.replaceChildren();
            for (let index = first; index <= last; index++) {
                const month = String(index % 12 + 1).padStart(2, '0');
                const year = String(Math.floor(index / 12) % 100).padStart(2, '0');
                draw('text', { x: x(index), y: bottom + 24, 'text-anchor': 'middle' },
                    month + '/' + year, target);
            }
        }
        chartExport = {
            filename: 'График_' + month + '_' + end_month + '.png',
            fillLabels: target => fillMonthLabels(target, start, end),
        };
        let firstVisible, lastVisible;
        function drawMonthLabels() {
            // Keep every month on the timeline while rendering only the visible labels.
            const offset = plotScroll.scrollLeft - left;
            const first = Math.max(start, start + Math.floor(offset / monthWidth));
            const last = Math.min(end, start + Math.ceil((offset + plotScroll.clientWidth) / monthWidth));
            if (first === firstVisible && last === lastVisible) return;
            firstVisible = first;
            lastVisible = last;
            fillMonthLabels(monthLabels, first, last);
        }
        plotScroll.scrollLeft = 0;
        plotScroll.onscroll = drawMonthLabels;
        drawMonthLabels();

        // Connect each pair of available observations over their actual month positions.
        for (const [field, name] of Object.entries(series)) {
            const group = draw('g', { class: 'chart-' + field });
            const path = points.map((point, index) =>
                (index === 0 ? 'M ' : 'L ') + x(monthIndex(point.month)) + ' ' + y(point[field])
            ).join(' ');
            draw('path', { d: path, class: 'chart-line' }, undefined, group);
            for (const point of points) {
                const index = monthIndex(point.month);
                const marker = draw('circle', { cx: x(index), cy: y(point[field]), r: 4 }, undefined, group);
                draw('title', {}, label(index) + ' · ' + name + ': ' + exactNumber.format(BigInt(point[field])), marker);
            }
        }

        for (const point of points) {
            const row = table.insertRow();
            row.insertCell().textContent = label(monthIndex(point.month));
            for (const field of Object.keys(series)) {
                row.insertCell().textContent = exactNumber.format(BigInt(point[field]));
            }
        }
        gaps.hidden = points.length === span + 1;
    }

    function buildImageSvg(fillLabels) {
        const chart = plot.cloneNode(true);
        const bounds = plot.viewBox.baseVal;
        const padding = 16;
        const headerHeight = 84;
        const width = bounds.width + padding * 2;
        const height = bounds.height + headerHeight;
        const svg = document.createElementNS(plot.namespaceURI, 'svg');
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
        svg.setAttribute('font-family', 'Arial, sans-serif');

        // A standalone image needs its own styles. Use a light background for sharing.
        draw('style', {}, [
            'text { fill: #222; font-size: 14px; }',
            '.chart-received { color: #2563eb; }',
            '.chart-sent { color: #b45309; }',
            '.chart-grid { stroke: #d1d5db; }',
            '.chart-line { fill: none; stroke: currentColor; stroke-width: 2.5; }',
            'circle { fill: white; stroke: currentColor; stroke-width: 2; }',
        ].join('\n'), svg);
        draw('rect', { width, height, fill: 'white' }, undefined, svg);
        draw('text', { x: padding, y: 24, 'font-weight': 'bold' }, title.textContent, svg);
        draw('text', { x: padding, y: 45 }, period.textContent, svg);
        for (const [index, [field, name]] of Object.entries(series).entries()) {
            const x = padding + index * 123;
            const legend = draw('g', { class: 'chart-' + field }, undefined, svg);
            draw('line', { x1: x, x2: x + 18, y1: 65, y2: 65, class: 'chart-line' }, undefined, legend);
            draw('text', { x: x + 24, y: 70 }, name, legend);
        }

        chart.removeAttribute('style');
        chart.setAttribute('width', bounds.width);
        chart.setAttribute('height', bounds.height);
        chart.setAttribute('x', padding);
        chart.setAttribute('y', headerHeight);
        fillLabels(chart.querySelector('.chart-month-labels'));
        svg.append(chart);
        return { svg, width, height };
    }

    download.addEventListener('click', async () => {
        if (!chartExport) return;
        download.disabled = true;
        const { filename, fillLabels } = chartExport;
        let sourceUrl;
        try {
            const { svg, width, height } = buildImageSvg(fillLabels);
            sourceUrl = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], {
                type: 'image/svg+xml;charset=utf-8',
            }));
            const image = new Image();
            image.src = sourceUrl;
            await image.decode();
            const canvas = document.createElement('canvas');
            const scale = Math.min(2, 16384 / Math.max(width, height));
            canvas.width = Math.max(1, Math.round(width * scale));
            canvas.height = Math.max(1, Math.round(height * scale));
            canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
            const png = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
            if (!png) throw new Error('PNG encoding failed');
            const pngUrl = URL.createObjectURL(png);
            const link = document.createElement('a');
            link.href = pngUrl;
            link.download = filename;
            link.click();
            setTimeout(() => URL.revokeObjectURL(pngUrl), 1000);
        } catch (error) {
            status.textContent = 'Не удалось скачать изображение. Попробуйте ещё раз.';
            status.hidden = false;
        } finally {
            if (sourceUrl) URL.revokeObjectURL(sourceUrl);
            download.disabled = false;
        }
    });

    document.querySelector('.category-report').addEventListener('click', async event => {
        const button = event.target.closest('.stat-chart-button');
        if (!button) return;

        const request = new AbortController();
        activeRequest?.abort();
        activeRequest = request;
        chartExport = null;
        title.textContent = button.dataset.chartLabel;
        status.textContent = 'Загружаем данные…';
        status.hidden = false;
        content.hidden = true;
        dialog.showModal();

        const url = new URL(window.location.href);
        url.searchParams.set('chart', button.dataset.chartScope);
        url.searchParams.set('chart_id', button.dataset.chartKey);

        try {
            const response = await fetch(url, { signal: request.signal, headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('Chart request failed');
            const data = await response.json();
            if (request.signal.aborted) return;
            if (!data.points.length) {
                status.textContent = 'Нет данных за выбранный период.';
                return;
            }
            content.hidden = false;
            renderChart(data);
            status.hidden = true;
        } catch (error) {
            if (!request.signal.aborted) {
                content.hidden = true;
                status.textContent = 'Не удалось загрузить график. Попробуйте ещё раз.';
            }
        }
    });

    dialog.addEventListener('close', () => activeRequest?.abort());
})();
