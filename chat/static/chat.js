(function () {
  'use strict';

  const messagesEl = document.getElementById('messages');
  const emptyEl    = document.getElementById('empty');
  const form       = document.getElementById('form');
  const input      = document.getElementById('input');
  const sendBtn    = document.getElementById('send');

  // ── State ──────────────────────────────────────────────────────────────────

  function setLoading(on) {
    sendBtn.disabled = on;
    sendBtn.textContent = on ? '…' : 'Send';
    input.disabled = on;
  }

  function hideEmpty() {
    if (emptyEl) emptyEl.remove();
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  function appendUser(text) {
    hideEmpty();
    const msg    = document.createElement('div');
    msg.className = 'msg user';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    msg.appendChild(bubble);
    messagesEl.appendChild(msg);
    scrollToBottom();
  }

  function appendAssistant(lua, iterations, lintErrors) {
    const msg = document.createElement('div');
    msg.className = 'msg assistant';

    // code block
    const wrap    = document.createElement('div');
    wrap.className = 'code-wrap';

    const pre  = document.createElement('pre');
    const code = document.createElement('code');
    code.textContent = lua;
    pre.appendChild(code);
    wrap.appendChild(pre);

    // copy button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(lua).then(() => {
        copyBtn.textContent = 'Copied!';
        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
      });
    });
    wrap.appendChild(copyBtn);
    msg.appendChild(wrap);

    // iterations meta
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = iterations + ' iteration' + (iterations !== 1 ? 's' : '');
    msg.appendChild(meta);

    // lint warnings
    if (lintErrors && lintErrors.length > 0) {
      const warn = document.createElement('div');
      warn.className = 'lint-warn';
      warn.textContent = '⚠ luacheck: ' + lintErrors.join(' · ');
      msg.appendChild(warn);
    }

    messagesEl.appendChild(msg);
    scrollToBottom();
  }

  function appendError(text) {
    hideEmpty();
    const msg    = document.createElement('div');
    msg.className = 'msg error';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    msg.appendChild(bubble);
    messagesEl.appendChild(msg);
    scrollToBottom();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const prompt = input.value.trim();
    if (!prompt) return;

    input.value = '';
    appendUser(prompt);
    setLoading(true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt }),
      });

      if (!res.ok) {
        const body = await res.text();
        let detail;
        try {
          detail = JSON.parse(body).detail || body;
        } catch (_) {
          detail = body;
        }
        appendError('Error ' + res.status + ': ' + detail);
        return;
      }

      const data = await res.json();
      appendAssistant(data.lua, data.iterations, data.lint_errors);

    } catch (err) {
      appendError('Network error: ' + err.message);
    } finally {
      setLoading(false);
      input.focus();
    }
  });

}());
