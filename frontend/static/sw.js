self.addEventListener('install', event => {
    event.waitUntil(
        caches.open('sentry-cache').then(cache => {
            return cache.addAll([
                '/',
                '/static/styles.css',
                '/static/dashboard.js',
                '/static/chart.min.js',
                '/static/alpine.min.js',
                '/static/socket.io.min.js',
                '/static/interact.min.js',
                '/static/icon.png'
            ]);
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

self.addEventListener('push', event => {
    const data = event.data.json();
    self.registration.showNotification(data.title, {
        body: data.body,
        icon: '/static/icon.png'
    });
});