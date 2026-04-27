// Custom service worker additions for MedSync
// This file extends the auto-generated Workbox service worker

// Push notification handler
self.addEventListener("push", (event) => {
  if (!event.data) return;

  const data = event.data.json();
  const options = {
    body: data.body || "New notification from MedSync",
    icon: "/icons/icon-192x192.png",
    badge: "/icons/badge-72x72.png",
    vibrate: [100, 50, 100],
    data: {
      url: data.url || "/",
      type: data.type,
    },
    actions: data.actions || [],
    tag: data.tag || "medsync-notification",
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(data.title || "MedSync EMR", options)
  );
});

// Notification click handler - deep link to relevant page
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const url = event.notification.data?.url || "/";
  
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // Try to focus existing window
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // Open new window if none exists
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

// Background sync for offline queue
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-pending-actions") {
    event.waitUntil(syncPendingActions());
  }
});

async function syncPendingActions() {
  // This will be called when connectivity is restored
  // The actual sync logic is in the main app's offline-store.ts
  const channel = new BroadcastChannel("medsync-sync");
  channel.postMessage({ type: "SYNC_TRIGGERED" });
  channel.close();
}

// Listen for skip waiting message from app
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// Cache size management - limit to 50MB
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const MAX_CACHE_SIZE = 50 * 1024 * 1024; // 50MB - reserved for future size-based trimming

async function trimCaches() {
  const cacheNames = await caches.keys();
  
  for (const cacheName of cacheNames) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    
    // Simple LRU-like: remove oldest entries if too many
    if (keys.length > 500) {
      const toDelete = keys.slice(0, keys.length - 400);
      for (const key of toDelete) {
        await cache.delete(key);
      }
    }
  }
}

// Periodic cache cleanup
self.addEventListener("periodicsync", (event) => {
  if (event.tag === "cache-cleanup") {
    event.waitUntil(trimCaches());
  }
});
