const socket = io();

// Charts
const signalChart = new Chart(document.getElementById('signal-chart').getContext('2d'), {
    type: 'line',
    data: { datasets: [] },
    options: {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        scales: {
            x: { type: 'time', title: { display: true, text: 'Time' } },
            y: { title: { display: true, text: 'RSSI (dBm)' } }
        },
        plugins: { legend: { display: true } }
    }
});

const ssidChart = new Chart(document.getElementById('ssid-chart').getContext('2d'), {
    type: 'pie',
    data: { datasets: [], labels: [] },
    options: {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        plugins: { legend: { display: true, position: 'right' } }
    }
});

const persistenceChart = new Chart(document.getElementById('persistence-chart').getContext('2d'), {
    type: 'bar',
    data: { datasets: [], labels: [] },
    options: {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        scales: {
            x: { title: { display: true, text: 'MAC' } },
            y: { title: { display: true, text: 'Persistence Score' } }
        },
        plugins: { legend: { display: false } }
    }
});

const channelChart = new Chart(document.getElementById('channel-chart').getContext('2d'), {
    type: 'bar',
    data: { datasets: [], labels: [] },
    options: {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        scales: {
            x: { title: { display: true, text: 'Channel' } },
            y: { title: { display: true, text: 'Probe Count' } }
        },
        plugins: { legend: { display: false } }
    }
});

// Gauges
const heapGauge = new Chart(document.getElementById('heap-gauge').getContext('2d'), {
    type: 'doughnut',
    data: {
        datasets: [{ data: [0, 100], backgroundColor: ['#39ff14', '#333'] }],
        labels: ['Heap', 'Remaining']
    },
    options: {
        circumference: 180,
        rotation: -90,
        cutout: '80%',
        plugins: { legend: { display: false } }
    }
});

const uptimeGauge = new Chart(document.getElementById('uptime-gauge').getContext('2d'), {
    type: 'doughnut',
    data: {
        datasets: [{ data: [0, 100], backgroundColor: ['#39ff14', '#333'] }],
        labels: ['Uptime', 'Remaining']
    },
    options: {
        circumference: 180,
        rotation: -90,
        cutout: '80%',
        plugins: { legend: { display: false } }
    }
});

socket.on('update', ({ devices, diagnostics }) => {
    Alpine.store('devices', devices);
    Alpine.store('diagnostics', diagnostics);

    // Signal strength chart
    signalChart.data.datasets = Object.entries(devices).map(([mac, data]) => ({
        label: `${mac} (${data.vendor})`,
        data: data.timestamps.map((t, i) => ({ x: t * 1000, y: data.rssi_list[i] })),
        borderColor: `hsl(${Math.random() * 360}, 70%, 50%)`,
        fill: false,
        tension: 0.3
    }));
    signalChart.update();

    // SSID distribution chart
    const ssidCounts = {};
    Object.values(devices).forEach(device => {
        device.ssid_list.forEach(ssid => {
            ssidCounts[ssid] = (ssidCounts[ssid] || 0) + 1;
        });
    });
    ssidChart.data.labels = Object.keys(ssidCounts);
    ssidChart.data.datasets = [{
        data: Object.values(ssidCounts),
        backgroundColor: Object.keys(ssidCounts).map(() => `hsl(${Math.random() * 360}, 70%, 50%)`)
    }];
    ssidChart.update();

    // Persistence timeline
    persistenceChart.data.labels = Object.keys(devices);
    persistenceChart.data.datasets = [{
        label: 'Persistence',
        data: Object.values(devices).map(device => device.persistence_score),
        backgroundColor: Object.values(devices).map(device => device.anomaly_score > 0.8 ? 'rgba(255, 0, 0, 0.5)' : 'rgba(57, 255, 20, 0.5)')
    }];
    persistenceChart.update();

    // Channel activity
    const channelCounts = {};
    Object.values(devices).forEach(device => {
        Object.entries(device.channel_counts).forEach(([channel, count]) => {
            channelCounts[channel] = (channelCounts[channel] || 0) + count;
        });
    });
    channelChart.data.labels = Object.keys(channelCounts).map(Number).sort((a, b) => a - b);
    channelChart.data.datasets = [{
        label: 'Probes',
        data: Object.values(channelCounts),
        backgroundColor: 'rgba(57, 255, 20, 0.5)'
    }];
    channelChart.update();

    // Gauges
    heapGauge.data.datasets[0].data = [diagnostics.free_heap || 0, Math.max(0, 32000 - (diagnostics.free_heap || 0))];
    heapGauge.update();
    uptimeGauge.data.datasets[0].data = [Math.min(diagnostics.uptime || 0, 3600), Math.max(0, 3600 - (diagnostics.uptime || 0))];
    uptimeGauge.update();
});

// Drag-and-drop widgets
interact('.widget').draggable({
    listeners: {
        move(event) {
            const target = event.target;
            const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
            const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
            target.style.transform = `translate(${x}px, ${y}px)`;
            target.setAttribute('data-x', x);
            target.setAttribute('data-y', y);
        },
        end(event) {
            const widgets = Array.from(document.querySelectorAll('.widget')).map(el => el.getAttribute('data-widget'));
            localStorage.setItem('widgets', JSON.stringify(widgets));
        }
    }
});

// PWA service worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js');
}