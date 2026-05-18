<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let user: any = null;
  let loading = true;
  let rows: any[] = [];
  let totp: Record<string, string> = {};
  let msg = "";

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
      rows = await api.listApprovals();
    } catch (e: any) {
      msg = e.message;
    }
  }

  async function doApprove(id: string) {
    msg = "";
    try {
      const r = await api.approve(id, totp[id]);
      msg = `#${id.slice(0, 8)}: ${r.status}${r.detail ? " — " + r.detail : ""}` +
        (r.result ? ` (exit ${r.result.exit_code})` : "");
    } catch (e: any) {
      msg = e.message;
    }
    await refresh();
  }

  async function doDeny(id: string) {
    msg = "";
    try {
      const r = await api.deny(id);
      msg = `#${id.slice(0, 8)}: ${r.status}`;
    } catch (e: any) {
      msg = e.message;
    }
    await refresh();
  }
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="max-width:820px;margin:3rem auto;padding:0 1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2>Approvals</h2>
      <a href="/chat">← Chat</a>
    </div>
    {#if msg}<div class="card" style="margin:1rem 0;font-size:0.88rem;">{msg}</div>{/if}
    {#if rows.length === 0}
      <p class="muted">No approval requests.</p>
    {/if}
    {#each rows as a}
      <div class="card" style="margin-bottom:0.8rem;">
        <div style="display:flex;justify-content:space-between;">
          <b>{a.action}</b>
          <span class="muted">{a.risk} · {a.status}</span>
        </div>
        <div class="muted" style="font-size:0.8rem;margin:0.3rem 0;">
          agent={a.agent} tool={a.tool}
          target={a.payload?.target ?? "—"} · {a.created_at}
        </div>
        {#if a.status === "pending"}
          <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;">
            {#if a.payload?.totp_reconfirm}
              <input placeholder="TOTP" bind:value={totp[a.id]}
                     style="width:120px;" inputmode="numeric" maxlength="8" />
            {/if}
            <button on:click={() => doApprove(a.id)}>Approve</button>
            <button on:click={() => doDeny(a.id)} style="background:#b91c1c;">Deny</button>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
