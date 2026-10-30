async function refresh() {
  try {
    const response = await fetch('/summary');
    if (!response.ok) throw new Error('Database unavailable');
    const state = await response.json();
    document.querySelector('#health').textContent = 'SQL CONNECTED';
    for (const label of ['published', 'rejected']) document.querySelector('#' + label).textContent = state.attempts[label] || 0;
    document.querySelector('#failed').textContent = (state.attempts.failed || 0) + (state.attempts.abandoned || 0);
    const rows = document.querySelector('#rows');
    rows.replaceChildren();
    for (const snapshot of state.snapshots) {
      const tr = document.createElement('tr');
      for (const value of [snapshot.period, '#' + snapshot.batch_id, new Date(snapshot.published_at * 1000).toISOString()]) {
        const td = document.createElement('td'); td.textContent = value; tr.appendChild(td);
      }
      rows.appendChild(tr);
    }
    document.querySelector('#empty').hidden = state.snapshots.length !== 0;
    document.querySelector('#error').textContent = '';
  } catch (error) {
    document.querySelector('#health').textContent = 'DEGRADED';
    document.querySelector('#error').textContent = error.message;
  }
}
document.querySelector('#refresh').addEventListener('click', refresh);
refresh(); setInterval(refresh, 10000);
