<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let user: any = null;
  let loading = true;

  onMount(async () => {
    try {
      user = await api.me();
    } catch {
      goto("/login");
      return;
    }
    loading = false;
  });

  async function logout() {
    try { await api.logout(); } catch {}
    goto("/login");
  }
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="max-width:820px;margin:3rem auto;padding:0 1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2>Tessa</h2>
      <div>
        <span class="muted">{user.display_name} ({user.role})</span>
        <button on:click={logout} style="margin-left:1rem;">Logout</button>
      </div>
    </div>
    <div class="card" style="margin-top:1.5rem;">
      <p>You are authenticated. Workspace agents and chat arrive in <b>Phase 2</b>.</p>
      <p class="muted">
        Foundation is live: TOTP login, sessions, audit logging, Postgres,
        Nginx/TLS, Docker stack.
      </p>
    </div>
  </div>
{/if}
