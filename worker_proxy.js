// Cloudflare Worker - Email Proxy to Admin Panel
// This worker receives emails via POST and forwards them to the server for processing (filters, history, Discord).

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Forward email webhooks to the server
    if (request.method === "POST" && url.pathname === "/") {
      return forwardToPanel("webhook/email", request, env);
    }

    // 2. Proxy other API calls (fallback if not handled directly by server)
    const internalToken = request.headers.get("X-Internal-Token");
    if (internalToken !== env.INTERNAL_TOKEN) {
      return json({ error: "Forbidden" }, 403);
    }

    switch (url.pathname) {
      case "/api/get-messages":    return handleGetMessages(request, env);
      case "/api/delete-messages": return handleDeleteMessages(request, env);
      case "/api/update-pfp":      return handleUpdatePfp(request, env);
      case "/api/test-cat":        return forwardToPanel("api/test-cat-manual", request, env); // Server handles the logic
      default:                     return json({ error: "Not Found" }, 404);
    }
  },

  async scheduled(event, env) {
    // Trigger the server to run its daily cat logic
    console.log("Triggering Daily Cat on Server...");
    await fetch(`${env.PANEL_URL}/api/test-cat`, {
      method: "POST",
      headers: {
        "X-Internal-Token": env.INTERNAL_TOKEN,
        "Content-Type": "application/json"
      }
    });
  }
};

async function forwardToPanel(path, request, env) {
  const panelUrl = env.PANEL_URL || "https://panel.rutterle.eu";
  const body = await request.clone().text();

  return fetch(`${panelUrl}/${path.lstrip('/')}`, {
    method: "POST",
    headers: {
      ...Object.fromEntries(request.headers),
      "X-Internal-Token": env.INTERNAL_TOKEN
    },
    body: body
  });
}

// Minimal handlers for legacy support or if server is down
async function handleGetMessages(request, env) {
  const { channelId, limit = 25 } = await request.json();
  const r = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages?limit=${limit}`, {
    headers: { "Authorization": `Bot ${env.DISCORD_BOT_TOKEN}` }
  });
  return new Response(r.body, { status: r.status, headers: { "Content-Type": "application/json" } });
}

async function handleDeleteMessages(request, env) {
  const { channelId, messageIds } = await request.json();
  // Simplified for proxy
  for (const id of messageIds) {
    await fetch(`https://discord.com/api/v10/channels/${channelId}/messages/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bot ${env.DISCORD_BOT_TOKEN}` }
    });
  }
  return json({ ok: true });
}

async function handleUpdatePfp(request, env) {
  const { avatar } = await request.json();
  const r = await fetch("https://discord.com/api/v10/users/@me", {
    method: "PATCH",
    headers: {
      "Authorization": `Bot ${env.DISCORD_BOT_TOKEN}`,
      "Content-Type": "application/json"
    },
    json: { avatar }
  });
  return new Response(r.body, { status: r.status });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
