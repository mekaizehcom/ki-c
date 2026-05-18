<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let user: any = null;
  let loading = true;
  let tools: any[] = [];
  let agent = "devops";
  let command = "";
  let target = "";
  let out = "";

  onMount(async () => {
    try {
      user = await api.me();
    } catch {
      goto("/login");
      return;
    }
    tools = await api.listTools();
    command = tools[0]?.name ?? "";
    loading = false;
  });

  $: selected = tools.find((t) => t.name === command);

  async function exec() {
    out = "Running…";
    try {
      const r = await api.executeTool({ agent, command, target: target || null });
      if (r.status === "pending_approval") {
        out = `Pending approval (${r.risk}, needs ${r.approver_role}` +
          `${r.totp_reconfirm ? " + TOTP" : ""}). See /approvals. ${r.reason}`;
      } else if (r.status === "proposed") {
        out = `Proposed (not executed): ${JSON.stringify(r.would_run)}`;
      } else if (r.status === "executed") {
        out = `exit ${r.result.exit_code}\n${r.result.stdout || r.result.stderr}`;
      } else {
        out = JSON.stringify(r);
      }
    } catch (e: any) {
      out = e.message;
    }
  }
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="max-width:820px;margin:3rem auto;padding:0 1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2>Tools</h2><a href="/chat">← Chat</a>
    </div>
    <div class="card" style="margin-top:1rem;">
      <div class="field">
        <span class="label">Agent</span>
        <input bind:value={agent} />
      </div>
      <div class="field">
        <span class="label">Command</span>
        <select bind:value={command}
                style="width:100%;padding:0.5rem;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;">
          {#each tools as t}
            <option value={t.name}>{t.name} — {t.risk}{t.approval_required ? " (approval)" : ""}</option>
          {/each}
        </select>
      </div>
      {#if selected?.takes_target}
        <div class="field">
          <span class="label">Target ({selected.description})</span>
          <input bind:value={target} placeholder="e.g. /etc/hostname or container name" />
        </div>
      {/if}
      <button on:click={exec}>Run</button>
      {#if out}
        <pre style="white-space:pre-wrap;background:#0d1117;padding:0.8rem;border-radius:6px;margin-top:1rem;font-size:0.82rem;">{out}</pre>
      {/if}
    </div>
  </div>
{/if}
