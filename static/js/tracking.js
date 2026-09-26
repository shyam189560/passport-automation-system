const stageIcons = {
  done: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg>',
  current: '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>',
  pending: ''
};

async function trackApplication() {
  const id = document.getElementById('trackInput').value.trim();
  const resultEl = document.getElementById('trackResult');
  const btn = document.getElementById('trackBtn');
  if (!id) { showToast('Please enter an Application ID.', 'error'); return; }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  resultEl.innerHTML = '';

  try {
    const res = await fetch(`/api/track/${encodeURIComponent(id)}`);
    const data = await res.json();
    btn.disabled = false;
    btn.textContent = 'Track';

    if (!data.ok) {
      resultEl.innerHTML = `
        <div class="track-result empty-state">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>
          <h3>Application not found</h3>
          <p>${data.error}</p>
        </div>`;
      return;
    }

    const nodes = data.stages.map(s => {
      const state = s.done ? 'done' : (s.current ? 'current' : '');
      const icon = s.done ? stageIcons.done : (s.current ? stageIcons.current : '');
      return `
        <div class="timeline-node ${state}">
          <div class="timeline-dot">${icon}</div>
          <div>
            <div class="tn-title">${s.name}</div>
            ${s.current ? '<div class="tn-sub">Currently in progress</div>' : ''}
          </div>
        </div>`;
    }).join('');

    resultEl.innerHTML = `
      <div class="track-result">
        <div class="track-head">
          <div>
            <div style="font-size:0.8rem;color:var(--ink-faint);margin-bottom:4px;">Application ID</div>
            <h3 style="margin:0;">${data.application_id}</h3>
          </div>
          <span class="chip chip-info">${data.passport_type || 'New Passport'}</span>
        </div>
        <div class="timeline-v">${nodes}</div>
      </div>`;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Track';
    showToast('Network error — please try again.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('trackInput');
  if (input) {
    input.addEventListener('keydown', e => { if (e.key === 'Enter') trackApplication(); });
    if (input.value) trackApplication();
  }
});
