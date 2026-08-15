const tableBody = document.querySelector('#leads-table tbody');
const detailBox = document.getElementById('lead-detail');
const eventsBox = document.getElementById('lead-events');

function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}

async function loadLeads() {
  const res = await fetch('/leads');
  const leads = await res.json();
  tableBody.innerHTML = '';
  leads.forEach(lead => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${lead.name || '-'}</td>
      <td>${lead.company || '-'}</td>
      <td>${lead.industry || '-'}</td>
      <td>${lead.lead_score ?? '-'}</td>
      <td><span class="status ${lead.status}">${lead.status}</span></td>
      <td>${formatDate(lead.created_at)}</td>
    `;
    row.addEventListener('click', () => loadLeadDetail(lead.id));
    tableBody.appendChild(row);
  });
}

async function loadLeadDetail(leadId) {
  const [leadRes, eventsRes] = await Promise.all([
    fetch(`/leads/${leadId}`),
    fetch(`/leads/${leadId}/events`),
  ]);
  const lead = await leadRes.json();
  const events = await eventsRes.json();
  detailBox.textContent = JSON.stringify(lead, null, 2);
  eventsBox.textContent = JSON.stringify(events, null, 2);
}

loadLeads();
