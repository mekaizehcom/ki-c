<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api } from "$lib/api";

  onMount(async () => {
    try {
      await api.me();
      goto("/chat");
    } catch {
      goto("/login");
    }
  });
</script>

<div class="center"><p class="muted">Loading Tessa…</p></div>
