<script lang="ts">
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  let phase: "password" | "totp" = "password";
  let username = "";
  let password = "";
  let code = "";
  let challengeId = "";
  let enroll = false;
  let error = "";
  let busy = false;

  async function submitPassword() {
    error = "";
    busy = true;
    try {
      const r = await api.login(username, password);
      challengeId = r.challenge_id;
      enroll = r.status === "totp_enroll";
      phase = "totp";
    } catch (e: any) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function submitTotp() {
    error = "";
    busy = true;
    try {
      await api.totpVerify(challengeId, code);
      goto("/chat");
    } catch (e: any) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="center">
  <div class="card" style="width: 380px;">
    <h2 style="margin-top:0;">Tessa</h2>

    {#if phase === "password"}
      <form on:submit|preventDefault={submitPassword}>
        <div class="field">
          <label class="label" for="u">Username</label>
          <input id="u" bind:value={username} autocomplete="username" />
        </div>
        <div class="field">
          <label class="label" for="p">Password</label>
          <input id="p" type="password" bind:value={password}
                 autocomplete="current-password" />
        </div>
        <button type="submit" disabled={busy || !username || !password}>
          {busy ? "…" : "Continue"}
        </button>
      </form>
    {:else}
      <form on:submit|preventDefault={submitTotp}>
        {#if enroll}
          <p class="muted">
            First login — scan this QR with Google Authenticator
            (or any RFC-6238 app), then enter the 6-digit code.
          </p>
          <div style="text-align:center; margin-bottom:1rem;">
            <img alt="TOTP QR"
                 src={`/api/auth/totp/qr?challenge_id=${encodeURIComponent(challengeId)}`}
                 style="width:200px;height:200px;background:#fff;border-radius:6px;" />
          </div>
        {:else}
          <p class="muted">Enter the 6-digit code from your authenticator app.</p>
        {/if}
        <div class="field">
          <label class="label" for="c">TOTP code</label>
          <input id="c" bind:value={code} inputmode="numeric"
                 autocomplete="one-time-code" maxlength="8" />
        </div>
        <button type="submit" disabled={busy || code.length < 6}>
          {busy ? "…" : "Sign in"}
        </button>
      </form>
    {/if}

    {#if error}<div class="error">{error}</div>{/if}
  </div>
</div>
