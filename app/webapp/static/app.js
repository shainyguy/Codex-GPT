const api = '/api/v1';
const token = () => document.getElementById('token').value;

async function createAgent() {
  const payload = {
    name: document.getElementById('name').value,
    provider: document.getElementById('provider').value,
    model: document.getElementById('model').value,
    system_prompt: document.getElementById('prompt').value,
    token_limit: 4000,
    tools: { text_analysis: true },
    memory_enabled: true,
    behavior: { tone: 'helpful' }
  };
  await fetch(`${api}/agents`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` }, body: JSON.stringify(payload)});
  loadAgents();
}

async function loadAgents() {
  const res = await fetch(`${api}/agents`, { headers: { Authorization: `Bearer ${token()}` }});
  document.getElementById('agents').textContent = JSON.stringify(await res.json(), null, 2);
}

function connectWs() {
  const ws = new WebSocket(`ws://${location.host}/api/v1/ws/tokens?token=${token()}`);
  ws.onmessage = (ev) => { document.getElementById('wallets').textContent = ev.data; };
}
