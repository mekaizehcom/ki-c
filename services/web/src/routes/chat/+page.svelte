<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { goto } from "$app/navigation";
  import { api, chatSocket } from "$lib/api";

  type Msg = { role: string; content: string; model?: string; sources?: any[] };

  let user: any = null;
  let loading = true;
  let agents: any[] = [];
  let conversations: any[] = [];
  let selectedAgent = "main";
  let conversationId: string | null = null;
  let messages: Msg[] = [];
  let input = "";
  let sending = false;
  let ws: WebSocket | null = null;
  let streaming = "";
  let pendingSources: any[] = [];
  let documents: any[] = [];
  let uploading = false;

  onMount(async () => {
    try {
      user = await api.me();
    } catch {
      goto("/login");
      return;
    }
    agents = await api.agents();
    conversations = await api.conversations();
    await refreshDocuments();
    loading = false;
    connect();
  });

  onDestroy(() => ws?.close());

  function connect() {
    ws = chatSocket();
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "meta") {
        conversationId = m.conversation_id;
        pendingSources = m.sources || [];
      } else if (m.type === "delta") {
        streaming += m.text;
      } else if (m.type === "done") {
        messages = [
          ...messages,
          { role: "assistant", content: streaming, model: m.model, sources: pendingSources },
        ];
        streaming = "";
        pendingSources = [];
        sending = false;
        refreshConversations();
      } else if (m.type === "error") {
        messages = [...messages, { role: "assistant", content: "⚠ " + m.error }];
        streaming = "";
        sending = false;
      }
    };
    ws.onclose = () => {
      ws = null;
    };
  }

  async function refreshConversations() {
    try {
      conversations = await api.conversations();
    } catch {}
  }

  async function refreshDocuments() {
    try {
      documents = await api.listDocuments();
    } catch {}
  }

  async function onUpload(e: Event) {
    const inp = e.target as HTMLInputElement;
    if (!inp.files || !inp.files[0]) return;
    uploading = true;
    try {
      await api.uploadDocument(inp.files[0], "workspace");
    } catch (err: any) {
      alert(err.message);
    }
    inp.value = "";
    uploading = false;
    setTimeout(refreshDocuments, 1500);
  }

  function send() {
    if (!input.trim() || sending) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connect();
      setTimeout(send, 300);
      return;
    }
    sending = true;
    messages = [...messages, { role: "user", content: input }];
    ws.send(
      JSON.stringify({
        message: input,
        conversation_id: conversationId,
        agent: selectedAgent,
      })
    );
    input = "";
  }

  async function openConversation(id: string) {
    const c = await api.conversation(id);
    conversationId = c.id;
    selectedAgent = c.agent;
    messages = c.messages;
    streaming = "";
  }

  function newChat() {
    conversationId = null;
    messages = [];
    streaming = "";
  }

  async function logout() {
    try {
      await api.logout();
    } catch {}
    goto("/login");
  }
</script>

{#if loading}
  <div class="center"><p class="muted">Loading…</p></div>
{:else}
  <div style="display:flex;height:100vh;">
    <aside style="width:260px;border-right:1px solid var(--border);padding:1rem;display:flex;flex-direction:column;gap:1rem;">
      <div>
        <b>Tessa</b>
        <div class="muted" style="font-size:0.8rem;">{user.display_name} · {user.role}</div>
      </div>
      <div class="field">
        <span class="label">Agent</span>
        <select bind:value={selectedAgent}
                style="width:100%;padding:0.5rem;background:#0d1117;color:var(--text);border:1px solid var(--border);border-radius:6px;">
          {#each agents as a}
            <option value={a.name}>{a.name} — {a.model_profile}</option>
          {/each}
        </select>
      </div>
      <button on:click={newChat}>+ New chat</button>
      <div style="flex:1;overflow:auto;">
        <span class="label">Conversations</span>
        {#each conversations as c}
          <div on:click={() => openConversation(c.id)}
               on:keydown={(e) => e.key === "Enter" && openConversation(c.id)}
               role="button" tabindex="0"
               style="padding:0.5rem;border-radius:6px;cursor:pointer;font-size:0.85rem;{c.id === conversationId ? 'background:var(--border);' : ''}">
            {c.title}
            <div class="muted" style="font-size:0.7rem;">{c.agent}</div>
          </div>
        {/each}
      </div>
      <div>
        <span class="label">Knowledge base</span>
        <label style="display:block;font-size:0.8rem;cursor:pointer;padding:0.4rem 0;color:var(--accent);">
          {uploading ? "Uploading…" : "+ Upload document"}
          <input type="file" on:change={onUpload} disabled={uploading}
                 accept=".md,.txt,.pdf,.docx,.html,.csv,.json,.log"
                 style="display:none;" />
        </label>
        <div style="max-height:120px;overflow:auto;">
          {#each documents as d}
            <div class="muted" style="font-size:0.72rem;padding:0.15rem 0;">
              {d.filename} · {d.status}
            </div>
          {/each}
        </div>
      </div>
      <a href="/settings" style="font-size:0.82rem;text-align:center;">Settings · Link SwissChat</a>
      <button on:click={logout} style="background:#30363d;">Logout</button>
    </aside>

    <main style="flex:1;display:flex;flex-direction:column;">
      <div style="flex:1;overflow:auto;padding:1.5rem;">
        {#if messages.length === 0 && !streaming}
          <p class="muted">Ask Tessa something. Agent: <b>{selectedAgent}</b></p>
        {/if}
        {#each messages as m}
          <div style="margin-bottom:1rem;">
            <div class="muted" style="font-size:0.75rem;">
              {m.role}{m.model ? " · " + m.model : ""}
            </div>
            <div style="white-space:pre-wrap;">{m.content}</div>
            {#if m.sources && m.sources.length}
              <div class="muted" style="font-size:0.72rem;margin-top:0.3rem;">
                Quellen: {#each m.sources as s}[{s.n}] {s.filename} ({s.score}) {/each}
              </div>
            {/if}
          </div>
        {/each}
        {#if streaming}
          <div style="margin-bottom:1rem;">
            <div class="muted" style="font-size:0.75rem;">assistant · …</div>
            <div style="white-space:pre-wrap;">{streaming}</div>
          </div>
        {/if}
      </div>
      <form on:submit|preventDefault={send}
            style="display:flex;gap:0.5rem;padding:1rem;border-top:1px solid var(--border);">
        <input bind:value={input} placeholder="Message Tessa…" autocomplete="off" />
        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? "…" : "Send"}
        </button>
      </form>
    </main>
  </div>
{/if}
