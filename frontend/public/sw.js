/* Service Worker for Jarvis Push Insights */

self.addEventListener("push", (event) => {
  let data = { title: "Jarvis Insight", body: "New insight detected" };
  try {
    data = event.data.json();
  } catch (e) {
    // fallback to defaults
  }

  const options = {
    body: data.body,
    icon: "/favicon.ico",
    badge: "/favicon.ico",
    tag: data.insight_id || "jarvis-insight",
    data: { insightId: data.insight_id },
    actions: [{ action: "view", title: "View" }],
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      // Focus existing tab or open new one
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.focus();
          client.postMessage({ type: "open-insights", insightId: event.notification.data?.insightId });
          return;
        }
      }
      return clients.openWindow("/?insights=open");
    })
  );
});
