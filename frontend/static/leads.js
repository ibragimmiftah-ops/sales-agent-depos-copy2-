const tableBody = document.querySelector('#leads-table tbody');
const detailBox = document.getElementById('lead-detail');
const eventsBox = document.getElementById('lead-events');

function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}

function setText(element, text) {
  if (element) {
    element.textContent = text ?? '-';
  }
}

function createCell(text, className) {
  const td = document.createElement('td');
  td.textContent = text ?? '-';
  if (className) {
    td.className = className;
  }
  return td;
}

async function getAuthHeaders() {
  const token = localStorage.getItem('sales_agent_operator_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function loadLeads() {
  const res = await fetch('/api/v1/leads', { headers: await getAuthHeaders() });
  if (res.status === 401) {
    tableBody.innerHTML = '';
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.textContent = 'Operator login required';
    row.appendChild(cell);
    tableBody.appendChild(row);
    return;
  }
  if (!res.ok) {
    return;
  }
  const leads = await res.json();
  tableBody.innerHTML = '';
  leads.forEach(lead => {
    const row = document.createElement('tr');
    row.appendChild(createCell(lead.name));
    row.appendChild(createCell(lead.company));
    row.appendChild(createCell(lead.industry));
    row.appendChild(createCell(lead.lead_score));
    const statusCell = document.createElement('td');
    const statusSpan = document.createElement('span');
    statusSpan.className = `status ${lead.status}`;
    statusSpan.textContent = lead.status;
    statusCell.appendChild(statusSpan);
    row.appendChild(statusCell);
    row.appendChild(createCell(formatDate(lead.created_at)));
    row.addEventListener('click', () => loadLeadDetail(lead.id));
    tableBody.appendChild(row);
  });
}

async function loadLeadDetail(leadId) {
  const headers = await getAuthHeaders();
  const [leadRes, eventsRes] = await Promise.all([
    fetch(`/api/v1/leads/${encodeURIComponent(leadId)}`, { headers }),
    fetch(`/api/v1/leads/${encodeURIComponent(leadId)}/events`, { headers }),
  ]);
  if (!leadRes.ok || !eventsRes.ok) {
    detailBox.textContent = 'Failed to load lead details';
    eventsBox.textContent = '';
    return;
  }
  const lead = await leadRes.json();
  const events = await eventsRes.json();
  detailBox.textContent = JSON.stringify(lead, null, 2);
  eventsBox.textContent = JSON.stringify(events, null, 2);
}

loadLeads();
