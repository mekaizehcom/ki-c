<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let user: any = null;
  let loading = true;
  let links: any[] = [];
  let code = "";
  let totp = "";
  let msg = "";
  let err = "";
  let busy = false;

  onMount(async () => {
    try {
      user = await api.me();
    } catch {
      goto("/login");
      return;
    }
    await refresh();
    loading = false;
  });

  async function refresh() {
    try {
      links = await api.swisschatMe();
    } catch {}
  }

  async function link() {
    err = "";
    msg = "";
    busy = true;
    try {
      const r = await api.swisschatLink(code.trim(), totp.trim());
      msg = `SwissChat linked (${r.swisschat_user_id}).`;
      code = "";
      totp = "";
      await refresh();
    } catch (e: any) {
      err = e.message;
    } finally {
      busy = false;
    }
  }
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="max-width:560px;margin:3rem auto;padding:0 1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2>Settings</h2>
      <a href="/chat">← Chat</a>
    </div>

    <div class="card" style="margin-top:1.5rem;">
      <h3 style="margin-top:0;">Link SwissChat</h3>
      <p class="muted" style="font-size:0.88rem;">
        In SwissChat, message the Tessa bot once. It replies with a 6-digit
        code. Enter it here with your authenticator code to confirm (TOTP).
      </p>
      <div class="field">
        <span class="label">Linking code</span>
        <input bind:value={code} inputmode="numeric" maxlength="6"
               placeholder="123456" />
      </div>
      <div class="field">
        <span class="label">TOTP code</span>
        <input bind:value={totp} inputmode="numeric" maxlength="8"
               autocomplete="one-time-code" placeholder="000000" />
      </div>
      <button on:click={link} disabled={busy || !code || !totp}>
        {busy ? "…" : "Confirm link"}
      </button>
      {#if msg}<div class="muted" style="margin-top:0.6rem;">{msg}</div>{/if}
      {#if err}<div class="error">{err}</div>{/if}
    </div>

    <div class="card" style="margin-top:1rem;">
      <h3 style="margin-top:0;">Linked accounts</h3>
      {#if links.length === 0}
        <p class="muted">No SwissChat accounts linked yet.</p>
      {:else}
        {#each links as l}
          <div class="muted" style="font-size:0.85rem;">
            {l.swisschat_user_id} · {l.linked ? "linked" : "pending"}
          </div>
        {/each}
      {/if}
    </div>
  </div>
{/if}
