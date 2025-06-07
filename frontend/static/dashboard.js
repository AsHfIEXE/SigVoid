// frontend/static/dashboard.js

// Predefined color palettes for charts
const CHART_COLORS = [
    '#39ff14', // Neon Green (Main theme color)
    '#00BFFF', // Deep Sky Blue
    '#FFD700', // Gold
    '#FF4500', // Orange Red
    '#9400D3', // Dark Violet
    '#ADFF2F', // Green Yellow
    '#DC143C', // Crimson
    '#00CED1', // Dark Turquoise
    '#FF8C00', // Dark Orange
    '#1E90FF', // Dodger Blue
    '#FF1493', // Deep Pink
    '#7CFC00', // Lawn Green
    '#FF6347', // Tomato
    '#483D8B', // Dark Slate Blue
    '#C71585', // Medium Violet Red
    '#DAA520'  // Goldenrod
];

// Helper to get a consistent color for a given label
const getColor = (label, alpha = 1) => {
    // Special colors for anomaly and normal states
    if (label === 'anomaly_high') return `rgba(239, 68, 68, ${alpha})`; // Red for high anomaly
    if (label === 'normal') return `rgba(34, 197, 94, ${alpha})`;      // Green for normal
    if (label === 'channel_probes') return `rgba(57, 255, 20, ${alpha})`; // Consistent green for channel probes

    let hash = 0;
    for (let i = 0; i < label.length; i++) {
        hash = label.charCodeAt(i) + ((hash << 5) - hash);
    }
    const colorIndex = Math.abs(hash) % CHART_COLORS.length;
    const baseColor = CHART_COLORS[colorIndex];
    
    if (alpha !== 1) {
        const r = parseInt(baseColor.slice(1, 3), 16);
        const g = parseInt(baseColor.slice(3, 5), 16);
        const b = parseInt(baseColor.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    return baseColor;
};

// Initial chart setup functions
const createChart = (ctx, type, data, options) => {
    return new Chart(ctx, { type, data, options });
};

let signalChart, ssidChart, persistenceChart, channelChart, heapGauge, uptimeGauge;

// Function to get common chart options based on current theme
const getCommonChartOptions = () => {
    const isDark = document.body.classList.contains('dark');
    const textColor = isDark ? 'white' : '#1f2937'; // body.dark text-color-dark vs body.light text-color-light
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'; // Softer grid for light mode

    return {
        animation: { duration: 1000, easing: 'easeOutQuart' },
        responsive: true,
        maintainAspectRatio: false, // Important for custom heights
        plugins: {
            legend: {
                labels: {
                    color: textColor,
                    font: { size: 12 }
                }
            },
            tooltip: {
                backgroundColor: isDark ? 'rgba(31, 41, 55, 0.95)' : 'rgba(255, 255, 255, 0.95)', // Card background with slight opacity
                bodyColor: textColor,
                titleColor: textColor,
                borderColor: isDark ? 'rgba(57, 255, 20, 0.5)' : 'rgba(45, 212, 191, 0.5)', // Neon green border
                borderWidth: 1,
                cornerRadius: 8, // Rounded corners
                displayColors: true // Show color swatch in tooltip
            }
        },
        scales: {
            x: {
                grid: { color: gridColor },
                ticks: { color: textColor },
                title: { display: true, color: textColor, font: { size: 14, weight: 'bold' } }
            },
            y: {
                grid: { color: gridColor },
                ticks: { color: textColor },
                title: { display: true, color: textColor, font: { size: 14, weight: 'bold' } }
            }
        }
    };
};

// Initialize charts on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    const commonOptions = getCommonChartOptions();

    signalChart = createChart(document.getElementById('signal-chart').getContext('2d'), 'line', { datasets: [] }, {
        ...commonOptions,
        scales: {
            x: { ...commonOptions.scales.x, type: 'time', title: { display: true, text: 'Time' } },
            y: { ...commonOptions.scales.y, title: { display: true, text: 'RSSI (dBm)' } }
        },
        plugins: { ...commonOptions.plugins, legend: { display: true } }
    });

    ssidChart = createChart(document.getElementById('ssid-chart').getContext('2d'), 'pie', { datasets: [], labels: [] }, {
        ...commonOptions,
        plugins: { ...commonOptions.plugins, legend: { display: true, position: 'right' } }
    });

    persistenceChart = createChart(document.getElementById('persistence-chart').getContext('2d'), 'bar', { datasets: [], labels: [] }, {
        ...commonOptions,
        scales: {
            x: { ...commonOptions.scales.x, title: { display: true, text: 'MAC' } },
            y: { ...commonOptions.scales.y, title: { display: true, text: 'Persistence Score' } }
        },
        plugins: { ...commonOptions.plugins, legend: { display: false } }
    });

    channelChart = createChart(document.getElementById('channel-chart').getContext('2d'), 'bar', { datasets: [], labels: [] }, {
        ...commonOptions,
        scales: {
            x: { ...commonOptions.scales.x, title: { display: true, text: 'Channel' } },
            y: { ...commonOptions.scales.y, title: { display: true, text: 'Probe Count' } }
        },
        plugins: { ...commonOptions.plugins, legend: { display: false } }
    });

    const gaugeOptions = {
        responsive: true,
        maintainAspectRatio: false,
        circumference: 180,
        rotation: -90,
        cutout: '80%',
        plugins: {
            legend: { display: false },
            tooltip: { enabled: false } // Disable tooltips for gauges
        },
        elements: {
            arc: {
                borderWidth: 0 // No border for gauges
            }
        }
    };

    heapGauge = createChart(document.getElementById('heap-gauge').getContext('2d'), 'doughnut', {
        datasets: [{ data: [0, 1], backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue('--neon-green'), '#333'] }],
        labels: ['Used', 'Free']
    }, gaugeOptions);

    uptimeGauge = createChart(document.getElementById('uptime-gauge').getContext('2d'), 'doughnut', {
        datasets: [{ data: [0, 1], backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue('--neon-green'), '#333'] }],
        labels: ['Uptime', 'Remaining']
    }, gaugeOptions);

    // Observer to update chart colors on theme change
    new MutationObserver(() => {
        const newCommonOptions = getCommonChartOptions();
        const neonGreen = getComputedStyle(document.documentElement).getPropertyValue('--neon-green');
        const cardBgColor = getComputedStyle(document.body).getPropertyValue('--card-bg-dark'); // Get current card bg color from body.dark/light

        [signalChart, ssidChart, persistenceChart, channelChart].forEach(chart => {
            Object.assign(chart.options, newCommonOptions); // Re-assign all common options
            chart.update();
        });

        // Update gauge background colors and remaining segment color
        heapGauge.data.datasets[0].backgroundColor[0] = neonGreen;
        heapGauge.data.datasets[0].backgroundColor[1] = cardBgColor;
        heapGauge.update();

        uptimeGauge.data.datasets[0].backgroundColor[0] = neonGreen;
        uptimeGauge.data.datasets[0].backgroundColor[1] = cardBgColor;
        uptimeGauge.update();

    }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
});


const socket = io();

socket.on('update', ({ devices, diagnostics }) => {
    // Update Alpine store (which is the source of truth for the UI)
    Alpine.store('devices', devices);
    Alpine.store('diagnostics', diagnostics);

    // Signal strength chart
    signalChart.data.datasets = Object.entries(devices).map(([mac, data]) => ({
        label: `${mac} (${data.vendor})`,
        // Convert timestamps from milliseconds to milliseconds for Chart.js time scale
        data: data.timestamps.map((t, i) => ({ x: t, y: data.rssi_list[i] })),
        borderColor: getColor(mac),
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
        backgroundColor: Object.keys(ssidCounts).map(ssid => getColor(ssid, 0.7)),
        borderColor: Object.keys(ssidCounts).map(ssid => getColor(ssid, 1))
    }];
    ssidChart.update();

    // Persistence timeline
    persistenceChart.data.labels = Object.keys(devices);
    persistenceChart.data.datasets = [{
        label: 'Persistence',
        data: Object.values(devices).map(device => device.persistence_score),
        backgroundColor: Object.values(devices).map(device => 
            device.anomaly_score > 0.8 ? getColor('anomaly_high', 0.7) : getColor('normal', 0.7)
        ),
        borderColor: Object.values(devices).map(device => 
            device.anomaly_score > 0.8 ? getColor('anomaly_high', 1) : getColor('normal', 1)
        )
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
        backgroundColor: getColor('channel_probes', 0.7),
        borderColor: getColor('channel_probes', 1)
    }];
    channelChart.update();

    // Gauges
    const maxHeap = 40000; // Assuming ~40KB max free heap for a typical ESP8266 sketch
    const currentHeap = diagnostics.free_heap || 0;
    heapGauge.data.datasets[0].data = [currentHeap, Math.max(0, maxHeap - currentHeap)];
    heapGauge.update();

    const maxUptimeForGauge = 24 * 3600; // 24 hours in seconds
    const currentUptime = diagnostics.uptime || 0; // In seconds
    uptimeGauge.data.datasets[0].data = [Math.min(currentUptime, maxUptimeForGauge), Math.max(0, maxUptimeForGauge - currentUptime)];
    uptimeGauge.update();
});

// Helper to format uptime for display (e.g., 1d 5h 30m)
function formatUptime(seconds) {
    const d = Math.floor(seconds / (3600*24));
    const h = Math.floor(seconds % (3600*24) / 3600);
    const m = Math.floor(seconds % 3600 / 60);
    const s = Math.floor(seconds % 60);
    
    let parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    // Only show seconds if less than a minute, or if it's the only value
    if (s > 0 || (parts.length === 0 && s === 0)) parts.push(`${s}s`); 
    
    return parts.join(' ');
}
window.formatUptime = formatUptime; // Expose to Alpine.js

// Toast notification helper
function showToast(message, type = 'info') {
    window.dispatchEvent(new CustomEvent('toast', {
        detail: { message, type, id: Date.now() }
    }));
}

// Global handlers for buttons and forms
async function handleAsyncAction(actionFn, ...args) {
    Alpine.store('isLoading', true); // Set global loading state
    try {
        await actionFn(...args);
    } finally {
        Alpine.store('isLoading', false); // Always turn off loading
    }
}

async function handleExport(format, preset) {
    await handleAsyncAction(async () => {
        try {
            const response = await fetch(`/export/${format}?preset=${preset}`);
            const data = await response.json();
            if (response.ok && data.status) {
                showToast(data.status, 'success');
            } else {
                showToast(data.error || 'Export failed!', 'error');
            }
        } catch (error) {
            console.error('Export failed:', error);
            showToast('Export failed: Network error.', 'error');
        }
    });
}

async function handleCleanup() {
    await handleAsyncAction(async () => {
        try {
            const response = await fetch('/cleanup', { method: 'POST' });
            const data = await response.json();
            if (response.ok && data.status) {
                showToast(data.status, 'success');
            } else {
                showToast(data.error || 'Cleanup failed!', 'error');
            }
        } catch (error) {
            console.error('Cleanup failed:', error);
            showToast('Cleanup failed: Network error.', 'error');
        }
    });
}

async function handleBan(mac) {
    await handleAsyncAction(async () => {
        try {
            const response = await fetch(`/ban/${mac}`, { method: 'POST' });
            const data = await response.json();
            if (response.ok && data.status) {
                showToast(data.status, 'success');
            } else {
                showToast(data.error || 'Ban failed!', 'error');
            }
        } catch (error) {
            console.error('Ban failed:', error);
            showToast('Ban failed: Network error.', 'error');
        }
    });
}

async function updateEspConfig(alpineContext) { // alpineContext refers to 'this' in Alpine component
    await handleAsyncAction(async () => {
        try {
            const formData = new FormData();
            formData.append('ssid', alpineContext.espApSsid);
            formData.append('password', alpineContext.espApPassword); 

            const response = await fetch('/esp-config', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (response.ok) { // Check for HTTP 200 OK
                showToast(data.status || 'ESP config updated successfully.', 'success');
            } else {
                showToast(data.detail || data.error || 'Failed to update ESP config.', 'error');
            }
        } catch (error) {
            console.error('Failed to update ESP config:', error);
            showToast('Failed to update ESP config: Network error.', 'error');
        }
    });
}

// Expose handlers to Alpine.js scope
window.handleExport = handleExport;
window.handleCleanup = handleCleanup;
window.handleBan = handleBan;
window.updateEspConfig = updateEspConfig;


// Drag-and-drop widgets using interact.js for reordering
document.addEventListener('alpine:init', () => {
    // Add isLoading to Alpine.store
    Alpine.store('isLoading', false);

    Alpine.data('dashboardData', () => ({
        // ... (your existing x-data properties will be merged by Alpine)
        init() {
            Alpine.store('devices', this.devices);
            Alpine.store('diagnostics', this.diagnostics);

            // Re-order widgets based on stored order
            this.$nextTick(() => {
                const widgetsContainer = this.$refs.widgets;
                if (widgetsContainer) {
                    this.widgets.forEach((widgetId, index) => {
                        const el = widgetsContainer.querySelector(`[data-widget="${widgetId}"]`);
                        if (el) {
                            el.style.order = index;
                        }
                    });

                    interact('.widget').unset(); // Clear existing listeners before setting new ones

                    interact('.widget').draggable({
                        inertia: true,
                        autoScroll: true,
                        listeners: {
                            start (event) {
                                event.target.classList.add('dragging'); // Add dragging class for visual feedback
                            },
                            move (event) {
                                const target = event.target;
                                const x = (parseFloat(target.dataset.x) || 0) + event.dx;
                                const y = (parseFloat(target.dataset.y) || 0) + event.dy;
                                target.style.transform = `translate(${x}px, ${y}px)`;
                                target.dataset.x = x;
                                target.dataset.y = y;

                                const container = event.target.parentNode;
                                const children = Array.from(container.children).filter(el => el.classList.contains('widget'));

                                // Simple reordering during drag
                                children.forEach(child => {
                                    if (child !== target) {
                                        const targetRect = target.getBoundingClientRect();
                                        const childRect = child.getBoundingClientRect();

                                        // Check for significant overlap to trigger reorder
                                        const overlapThreshold = 0.5; // 50% overlap
                                        const xOverlap = Math.max(0, Math.min(targetRect.right, childRect.right) - Math.max(targetRect.left, childRect.left));
                                        const yOverlap = Math.max(0, Math.min(targetRect.bottom, childRect.bottom) - Math.max(targetRect.top, childRect.top));
                                        const overlapArea = xOverlap * yOverlap;
                                        const targetArea = targetRect.width * targetRect.height;

                                        if (overlapArea / targetArea > overlapThreshold) {
                                            const targetOrder = parseInt(target.style.order || children.indexOf(target), 10);
                                            const childOrder = parseInt(child.style.order || children.indexOf(child), 10);

                                            if (targetOrder !== childOrder) {
                                                const newOrder = Array.from(this.widgets);
                                                const draggedIndex = newOrder.indexOf(target.dataset.widget);
                                                const targetIndex = newOrder.indexOf(child.dataset.widget);

                                                if (draggedIndex > -1 && targetIndex > -1) {
                                                    newOrder.splice(draggedIndex, 1);
                                                    newOrder.splice(targetIndex, 0, target.dataset.widget);

                                                    newOrder.forEach((widgetId, index) => {
                                                        const el = widgetsContainer.querySelector(`[data-widget="${widgetId}"]`);
                                                        if (el) {
                                                            el.style.order = index;
                                                        }
                                                    });
                                                    this.widgets = newOrder; // Update Alpine's state immediately
                                                }
                                            }
                                        }
                                    }
                                });
                            },
                            end (event) {
                                event.target.classList.remove('dragging');
                                event.target.style.transform = ''; // Reset transform
                                event.target.dataset.x = 0;
                                event.target.dataset.y = 0; // Reset dataset for next drag
                                event.target.style.zIndex = ''; // Reset z-index

                                localStorage.setItem('widgets', JSON.stringify(this.widgets)); // Save the final order
                            }
                        }
                    });
                }
            });
        }
    }));
});