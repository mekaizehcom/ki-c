<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let user: any = null;
  let loading = true;
  let sys: any = null;
  let providers: any[] = [];
  let agents: any[] = [];
  let users: any[] = [];
  let audit: any[] = [];
  let keyInput: Record<string, string> = {};
  let msg = "";
  let swisschat: any = null;
  let pairCode = "";
  let pairBot = "tessa";
  let pairBusy = false;
  let sandbox: any = null;
  let sbHost = "";
  let sbUser = "ubuntu";
  let sbPort = 22;
  let sbKey = "";
  let sbBusy = false;
  let sbTestResult = "";

  onMount(async () => {
    try {
      user = await api.me();
    } catch {
      goto("/login");
      return;
    }
    if (!["admin", "superadmin"].includes(user.role)) {
      goto("/chat");
      return;
    }
    await refresh();
    loading = false;
  });

  async function refresh() {
    [sys, providers, agents, users, audit, swisschat, sandbox] = await Promise.all([
      api.adminSystem(), api.adminProviders(), api.adminAgents(),
      api.adminUsers(), api.adminAudit(),
      api.swisschatStatus().catch(() => ({ configured: false })),
      api.sandboxStatus().catch(() => ({ configured: false })),
    ]);
  }

  async function saveSandbox() {
    msg = ""; sbTestResult = ""; sbBusy = true;
    try {
      await api.sandboxConfigure({
        host: sbHost.trim(), user: sbUser.trim() || "ubuntu",
        port: Number(sbPort) || 22, private_key: sbKey,
      });
      sbKey = "";
      msg = "Sandbox host saved. Running connection test…";
      const r = await api.sandboxTest();
      sbTestResult = `exit ${r.exit_code} @ ${r.host || "?"}\n` +
                     ((r.stdout || "").trim() + "\n" + (r.stderr || "").trim());
      msg = r.exit_code === 0 ? "Sandbox connection OK." : "Sandbox saved, test failed (see below).";
      await refresh();
    } catch (e: any) {
      msg = `Sandbox save failed: ${e.message}`;
    } finally { sbBusy = false; }
  }

  async function testSandbox() {
    sbTestResult = ""; sbBusy = true;
    try {
      const r = await api.sandboxTest();
      sbTestResult = `exit ${r.exit_code} @ ${r.host || "?"}\n` +
                     ((r.stdout || "").trim() + "\n" + (r.stderr || "").trim());
    } catch (e: any) { sbTestResult = e.message; }
    finally { sbBusy = false; }
  }

  async function forgetSandbox() {
    if (!confirm("Forget sandbox credentials? Tessa loses the ability to run ssh_exec.")) return;
    msg = ""; sbTestResult = "";
    try {
      await api.sandboxForget();
      msg = "Sandbox credentials forgotten.";
      await refresh();
    } catch (e: any) { msg = e.message; }
  }

  async function pairSwisschat() {
    msg = "";
    if (!pairCode.trim()) return;
    pairBusy = true;
    try {
      const r = await api.swisschatPair(pairCode.trim(), pairBot.trim() || "tessa");
      msg = `SwissChat paired as ${r.bot_username}. Webhook: ${r.webhook_url}`;
      pairCode = "";
      await refresh();
    } catch (e: any) {
      msg = `Pairing failed: ${e.message}`;
    } finally {
      pairBusy = false;
    }
  }

  async function forgetSwisschat() {
    if (!confirm("Forget SwissChat credentials? The bot will stop working until re-paired.")) return;
    msg = "";
    try {
      await api.swisschatForget();
      msg = "SwissChat credentials forgotten.";
      await refresh();
    } catch (e: any) {
      msg = e.message;
    }
  }

  async function saveProvider(p: any) {
    msg = "";
    try {
      await api.setProvider(p.provider, {
        api_key: keyInput[p.provider] || undefined,
        enabled: p.enabled,
      });
      keyInput[p.provider] = "";
      msg = `Provider ${p.provider} saved.`;
      await refresh();
    } catch (e: any) { msg = e.message; }
  }

  async function saveAgent(a: any) {
    msg = "";
    try {
      await api.setAgent(a.name, {
        autonomy: a.autonomy,
        allowed_auto_actions: a.allowed_auto_actions,
      });
      msg = `Agent ${a.name} updated.`;
    } catch (e: any) { msg = e.message; }
  }

  async function saveUser(u: any) {
    msg = "";
    try {
      await api.updateUser(u.username, { role: u.role, status: u.status });
      msg = `User ${u.username} updated.`;
      await refresh();
    } catch (e: any) { msg = e.message; }
  }

  async function reindex() {
    msg = "";
    try {
      const r = await api.reindexFailed();
      msg = `Re-queued ${r.requeued} failed documents.`;
    } catch (e: any) { msg = e.message; }
  }

  const LEVELS = ["none", "propose", "approve_required", "scoped_auto", "full_auto"];
  const ROLES = ["restricted", "user", "developer", "admin", "superadmin"];
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="max-width:960px;margin:2rem auto;padding:0 1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2>Admin</h2><a href="/chat">← Chat</a>
    </div>
    {#if msg}<div class="card" style="margin:0.8rem 0;font-size:0.88rem;">{msg}</div>{/if}

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">System</h3>
      {#if sys}
        <div class="muted" style="font-size:0.85rem;">
          ingest queue: {sys.ingest_queue} · users: {sys.users} ·
          conversations: {sys.conversations} · documents: {sys.documents} ·
          workspace: {sys.default_workspace}<br />
          providers active:
          {#each Object.entries(sys.providers_active) as [k, v]}
            {k}={v ? "yes" : "no"}&nbsp;
          {/each}
        </div>
        <button on:click={reindex} style="margin-top:0.6rem;">Re-index failed documents</button>
      {/if}
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">Model providers</h3>
      {#each providers as p}
        <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
          <b style="width:90px;">{p.provider}</b>
          <input placeholder={p.configured ? "•••• (set new to replace)" : "API key"}
                 bind:value={keyInput[p.provider]} type="password" style="flex:1;" />
          <label class="muted" style="font-size:0.8rem;">
            <input type="checkbox" bind:checked={p.enabled} /> enabled
          </label>
          <button on:click={() => saveProvider(p)}>Save</button>
        </div>
      {/each}
      <p class="muted" style="font-size:0.78rem;">
        Keys are stored Fernet-encrypted and passed to the gateway per request.
      </p>
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">Sandbox host (SSH target)</h3>
      <p class="muted" style="font-size:0.85rem;margin-top:0;">
        Tessa's <b>devops</b> agent runs free-form shell here (deploy,
        nginx, certbot, apt). This is intentionally separate from the
        Tessa host. (Superadmin only.)
      </p>
      {#if sandbox?.configured}
        <div class="muted" style="font-size:0.85rem;margin-bottom:0.6rem;">
          {sandbox.user}@<b>{sandbox.host}</b>:{sandbox.port}
          {#if sandbox.fingerprint}· fp: <code>{sandbox.fingerprint}</code>{/if}
        </div>
        <div style="display:flex;gap:0.5rem;">
          <button on:click={testSandbox} disabled={sbBusy}>Test connection</button>
          <button on:click={forgetSandbox} style="background:#b91c1c;">Forget</button>
        </div>
      {:else}
        <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
          <input bind:value={sbHost} placeholder="host or IP" style="flex:2;" />
          <input bind:value={sbUser} placeholder="user" style="flex:1;" />
          <input bind:value={sbPort} placeholder="22" style="width:80px;" inputmode="numeric" />
        </div>
        <textarea bind:value={sbKey} placeholder="Paste the private key (PEM, starts with -----BEGIN ... PRIVATE KEY-----)"
                  rows="6"
                  style="width:100%;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:0.5rem;font-family:ui-monospace,monospace;font-size:0.78rem;"></textarea>
        <div style="margin-top:0.5rem;">
          <button on:click={saveSandbox}
                  disabled={sbBusy || !sbHost.trim() || !sbKey.trim()}>
            {sbBusy ? "Saving…" : "Save & test"}
          </button>
        </div>
      {/if}
      {#if sbTestResult}
        <pre style="white-space:pre-wrap;background:#0d1117;padding:0.6rem;border-radius:6px;margin-top:0.8rem;font-size:0.78rem;max-height:200px;overflow:auto;">{sbTestResult}</pre>
      {/if}
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">SwissChat</h3>
      {#if swisschat?.configured}
        <div class="muted" style="font-size:0.85rem;margin-bottom:0.6rem;">
          Paired as <b>{swisschat.bot_username}</b> ·
          webhook: <code>{swisschat.webhook_url}</code> ·
          enabled: {swisschat.enabled ? "yes" : "no"}
        </div>
        <button on:click={forgetSwisschat} style="background:#b91c1c;">
          Forget credentials
        </button>
      {:else}
        <p class="muted" style="font-size:0.85rem;margin-top:0;">
          In SwissChat → Settings → Bots → "New bot", copy the pairing code
          (format <code>xxx-xxxx-xxxx-xxxx</code>) and paste it here.
          The code is single-use and expires after 24 h.
          (Superadmin only.)
        </p>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center;">
          <input bind:value={pairCode}
                 placeholder="kai-xxxx-xxxx-xxxx"
                 style="flex:1;min-width:240px;font-family:ui-monospace,monospace;" />
          <input bind:value={pairBot} placeholder="bot username"
                 style="width:150px;" />
          <button on:click={pairSwisschat}
                  disabled={pairBusy || !pairCode.trim()}>
            {pairBusy ? "Pairing…" : "Pair"}
          </button>
        </div>
      {/if}
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">Agent autonomy</h3>
      {#each agents as a}
        <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
          <b style="width:130px;">{a.name}</b>
          <select bind:value={a.autonomy}
                  style="padding:0.4rem;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;">
            {#each LEVELS as l}<option value={l}>{l}</option>{/each}
          </select>
          <input style="flex:1;" placeholder="allowed_auto_actions (comma)"
                 value={(a.allowed_auto_actions || []).join(",")}
                 on:change={(e) => (a.allowed_auto_actions = (e.target as HTMLInputElement).value.split(",").map((s) => s.trim()).filter(Boolean))} />
          <button on:click={() => saveAgent(a)}>Save</button>
        </div>
      {/each}
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <h3 style="margin-top:0;">Users</h3>
      {#each users as u}
        <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
          <b style="width:120px;">{u.username}</b>
          <select bind:value={u.role}
                  style="padding:0.4rem;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;">
            {#each ROLES as r}<option value={r}>{r}</option>{/each}
          </select>
          <select bind:value={u.status}
                  style="padding:0.4rem;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;">
            <option value="active">active</option>
            <option value="disabled">disabled</option>
            <option value="locked">locked</option>
          </select>
          <button on:click={() => saveUser(u)}>Save</button>
        </div>
      {/each}
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Recent audit</h3>
      <div style="max-height:240px;overflow:auto;font-size:0.78rem;font-family:monospace;">
        {#each audit as r}
          <div class="muted">{r.timestamp.slice(0, 19)} · {r.action} · {r.risk_level} · {r.status}</div>
        {/each}
      </div>
    </div>
  </div>
{/if}
