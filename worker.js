// =============================================================
//  Discord Bot – Cloudflare Worker (API only)
//  HTML panel je na rutterle.eu – Worker přijímá jen requesty
//  s hlavičkou X-Internal-Token (nastavit v CF env jako INTERNAL_TOKEN)
//
//  ENV proměnné:
//    INTERNAL_TOKEN       – sdílený secret s Ubuntu serverem
//    WEBHOOK_SECRET       – secret pro email webhook (mailbot)
//    ADMIN_PASSWORD       – fallback (už se nepoužívá z browseru)
//    DISCORD_BOT_TOKEN
//    DISCORD_CHANNEL_ID
//    DISCORD_TEST_CHANNEL_ID
// =============================================================

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ----------------------------------------------------------
    // EMAIL WEBHOOK  POST /
    // Volá ho mailbot externě → vlastní secret v query nebo header
    // ----------------------------------------------------------
    if (request.method === "POST" && url.pathname === "/") {
      const secret = request.headers.get("X-Webhook-Secret") ?? url.searchParams.get("secret");
      if (secret !== env.WEBHOOK_SECRET) {
        return json({ error: "Unauthorized" }, 401);
      }
      return handleEmailWebhook(request, env);
    }

    // ----------------------------------------------------------
    // INTERNÍ API  – všechno ostatní vyžaduje X-Internal-Token
    // ----------------------------------------------------------
    const internalToken = request.headers.get("X-Internal-Token");
    if (internalToken !== env.INTERNAL_TOKEN) {
      return json({ error: "Forbidden" }, 403);
    }

    if (request.method !== "POST") return json({ error: "Method Not Allowed" }, 405);

    switch (url.pathname) {
      case "/api/get-messages":    return handleGetMessages(request, env);
      case "/api/delete-messages": return handleDeleteMessages(request, env);
      case "/api/update-pfp":      return handleUpdatePfp(request, env);
      case "/api/test-cat":        return handleTestCat(request, env);
      default:                     return json({ error: "Not Found" }, 404);
    }
  },

  async scheduled(event, env) {
    console.log("Spouštím Daily Cat Update...");
    await runCatLogic(env);
  }
};

// ---- Handlery ------------------------------------------------

async function handleGetMessages(request, env) {
  const { channelId, limit = 25 } = await request.json();
  if (!channelId) return json({ error: "channelId required" }, 400);

  const r = await discordFetch(
    `channels/${channelId}/messages?limit=${Math.min(limit, 100)}`,
    { method: "GET" },
    env
  );
  const data = await r.json();
  if (!r.ok) return json({ error: data }, r.status);
  return json({ messages: data });
}

async function handleDeleteMessages(request, env) {
  const { channelId, messageIds } = await request.json();
  if (!channelId || !Array.isArray(messageIds) || messageIds.length === 0) {
    return json({ error: "channelId a messageIds jsou povinné" }, 400);
  }

  let deleted = 0, failed = 0;

  if (messageIds.length >= 2) {
    // Bulk delete (Discord max 100, zprávy mladší 14 dní)
    const r = await discordFetch(
      `channels/${channelId}/messages/bulk-delete`,
      { method: "POST", body: JSON.stringify({ messages: messageIds.slice(0, 100) }) },
      env
    );
    if (r.status === 204) {
      deleted = messageIds.length;
    } else {
      // Fallback – mazej po jedné (starší zprávy)
      for (const id of messageIds) {
        const dr = await discordFetch(`channels/${channelId}/messages/${id}`, { method: "DELETE" }, env);
        dr.status === 204 ? deleted++ : failed++;
      }
    }
  } else {
    const dr = await discordFetch(
      `channels/${channelId}/messages/${messageIds[0]}`,
      { method: "DELETE" },
      env
    );
    dr.status === 204 ? deleted++ : failed++;
  }

  return json({ ok: true, deleted, failed });
}

async function handleUpdatePfp(request, env) {
  const { avatar } = await request.json();
  await updateDiscordAvatar(avatar, env, "Nová profilovka! 😎");
  return json({ ok: true });
}

async function handleTestCat(request, env) {
  await runCatLogic(env);
  return json({ ok: true });
}

async function handleEmailWebhook(request, env) {
  try {
    const payload = await request.json();
    
    // Přeposlání na backend server (panel.rutterle.eu)
    // Předpokládáme, že endpoint je na /api/webhook
    const serverUrl = "https://panel.rutterle.eu/api/webhook";
    
    const r = await fetch(serverUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Webhook-Secret": env.WEBHOOK_SECRET
      },
      body: JSON.stringify(payload)
    });

    if (!r.ok) {
      const errorText = await r.text();
      return json({ error: `Backend Error: ${r.status} - ${errorText}` }, r.status);
    }
    
    return json({ ok: true });
  } catch (err) {
    return json({ error: err.message }, 500);
  }
}

// ---- Sdílené funkce ------------------------------------------

async function discordFetch(path, options = {}, env) {
  return fetch(`https://discord.com/api/v10/${path}`, {
    ...options,
    headers: {
      "Authorization": `Bot ${env.DISCORD_BOT_TOKEN}`,
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });
}

async function runCatLogic(env) {
  const catResp = await fetch("https://api.thecatapi.com/v1/images/search?mime_types=jpg,png");
  const [{ url }] = await catResp.json();

  const imgBuf = await (await fetch(url)).arrayBuffer();
  const bytes = new Uint8Array(imgBuf);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  const base64 = "data:image/jpeg;base64," + btoa(binary);

  await updateDiscordAvatar(base64, env, "Dnešní dávka koček je tu! 🐱📅");
}

async function updateDiscordAvatar(base64Image, env, chatMessage) {
  const r = await discordFetch(
    "users/@me",
    { method: "PATCH", body: JSON.stringify({ avatar: base64Image }) },
    env
  );
  if (!r.ok) throw new Error("Discord Avatar Error: " + JSON.stringify(await r.json()));

  if (env.DISCORD_TEST_CHANNEL_ID) {
    const bytes = new Uint8Array(atob(base64Image.split(",")[1]).split("").map(c => c.charCodeAt(0)));
    const form = new FormData();
    form.append("content", chatMessage);
    form.append("files[0]", new Blob([bytes], { type: "image/jpeg" }), "avatar.jpg");

    await fetch(`https://discord.com/api/v10/channels/${env.DISCORD_TEST_CHANNEL_ID}/messages`, {
      method: "POST",
      headers: { "Authorization": `Bot ${env.DISCORD_BOT_TOKEN}` },
      body: form
    });
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
