// Device plugins' panel scripts and tabs (#238, #303). The viewer serves each
// plugin's static files under /plugin/<name>/; this adds a tab on the RF page
// for each tab a panel lists, and loads the scripts its panels name, in the
// order the plugins were loaded, after the page's own scripts. A panel's
// script fills its tabs (registerRfView in app.js). It looks again every few
// seconds, so a plugin the viewer loads later (a run started from the page) is
// picked up, and each script is loaded once.
"use strict";

const pluginScriptsLoaded = new Set();

async function loadPluginScripts() {
  let reply = null;
  try {
    reply = await (await fetch("/api/plugins")).json();
  } catch (error) {
    return;
  }
  for (const plugin of reply.plugins || []) {
    for (const panel of plugin.panels || []) {
      for (const tab of panel.tabs || []) addRfTab(panel.name + "." + tab.id, tab.label);
      for (const src of panel.scripts || []) {
        if (pluginScriptsLoaded.has(src)) continue;
        pluginScriptsLoaded.add(src);
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
}

loadPluginScripts();
setInterval(loadPluginScripts, 5000);
