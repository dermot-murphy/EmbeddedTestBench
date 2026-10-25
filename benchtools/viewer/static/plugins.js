// Device plugins' panel scripts (#238). The viewer serves each plugin's
// static files under /plugin/<name>/; this loads the scripts its panels name,
// in the order the plugins were loaded, after the page's own scripts.
"use strict";

(async function loadPluginScripts() {
  let listed = [];
  try {
    listed = await (await fetch("/api/plugins")).json();
  } catch (error) {
    return;
  }
  for (const plugin of listed) {
    for (const panel of plugin.panels || []) {
      for (const src of panel.scripts || []) {
        await new Promise((resolve) => {
          const script = document.createElement("script");
          script.src = src;
          script.onload = resolve;
          script.onerror = resolve;
          document.body.appendChild(script);
        });
      }
    }
  }
})();
