async function refresh() {
  try {
    const response = await fetch('/summary');
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      if (response.status === 401 || (response.status === 503 && String(failure.detail).includes('token'))) {
        throw new Error('Private operator metadata. Public synthetic demo mode is disabled.');
      }
      throw new Error('Metadata unavailable. Retry shortly.');
    }
    const state = await response.json();
    document.querySelector('.eyebrow').textContent = state.public_demo ? 'SYNTHETIC DATA / PUBLIC READ-ONLY DEMO' : 'PIPELINE RELIABILITY / CONTROL PLANE';
    document.querySelector('footer').textContent = state.public_demo ? 'Synthetic demo metadata · Refreshes every 10 seconds · Raw records and admin operations require an operator token' : 'Private operator metadata · Raw records and admin operations require an operator token';
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
