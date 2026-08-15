const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const agentStateBox = document.getElementById('agent-state');
const toolCallsBox = document.getElementById('tool-calls');

let conversationId = localStorage.getItem('novaflow_conversation_id');
if (!conversationId) {
  conversationId = 'conv_' + Math.random().toString(36).slice(2, 14);
  localStorage.setItem('novaflow_conversation_id', conversationId);
}

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.textContent = text;
  chatHistory.appendChild(div);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function renderState(state) {
  const {
    response,
    last_tool_calls,
    ...rest
  } = state;
  agentStateBox.textContent = JSON.stringify(rest, null, 2);
  toolCallsBox.textContent = JSON.stringify(last_tool_calls || [], null, 2);
}

async function sendMessage(text) {
  appendMessage('user', text);
  messageInput.value = '';

  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message: text }),
  });

  if (!res.ok) {
    appendMessage('assistant', 'Ошибка соединения с сервером.');
    return;
  }

  const state = await res.json();
  appendMessage('assistant', state.response);
  renderState(state);
}

chatForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  sendMessage(text);
});

appendMessage('assistant', 'Привет! Я AI-агент NovaFlow AI. Расскажите, какую задачу хотите решить?');
renderState({
  conversation_id: conversationId,
  lead_id: null,
  intent: null,
  stage: 'new',
  lead_score: null,
  lead_quality: null,
  next_best_action: 'continue_conversation',
  missing_fields: ['business_problem'],
  collected_fields: {},
  last_tool_calls: [],
  response: 'Привет! Я AI-агент NovaFlow AI. Расскажите, какую задачу хотите решить?',
});
