let currentStep = 1;

function goToStep(step) {
  document.querySelectorAll('.step-panel').forEach(p => {
    p.style.display = Number(p.dataset.panel) === step ? '' : 'none';
  });
  document.querySelectorAll('.stepper-item').forEach(item => {
    const s = Number(item.dataset.step);
    item.classList.toggle('active', s === step);
    item.classList.toggle('done', s < step);
  });
  currentStep = step;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function nextStep(step) {
  const payload = { step };

  if (step === 1) {
    payload.full_name = document.getElementById('full_name').value;
    payload.dob = document.getElementById('dob').value;
    payload.gender = document.getElementById('gender').value;
    payload.email = document.getElementById('email').value;
    payload.mobile = document.getElementById('mobile').value;
    if (!payload.full_name || !payload.email) {
      showToast('Please fill in your name and email.', 'error');
      return;
    }
  } else if (step === 2) {
    payload.address = document.getElementById('address').value;
    payload.city = document.getElementById('city').value;
    payload.state = document.getElementById('state').value;
    payload.pincode = document.getElementById('pincode').value;
  } else if (step === 3) {
    const selected = document.querySelector('input[name="passport_type"]:checked');
    payload.passport_type = selected ? selected.value : 'New Passport';
  }

  try {
    const res = await apiPost('/api/application/save-step', payload);
    if (res.ok) {
      goToStep(step + 1);
    } else {
      showToast(res.error || 'Something went wrong. Please try again.', 'error');
    }
  } catch (err) {
    showToast('Network error — please try again.', 'error');
  }
}

// Passport type selection
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.type-option').forEach(opt => {
    opt.addEventListener('click', () => {
      document.querySelectorAll('.type-option').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      opt.querySelector('input').checked = true;
    });
  });
});

async function handleUpload(event, docType) {
  const file = event.target.files[0];
  if (!file) return;
  const card = event.target.closest('.upload-card');
  const actions = card.querySelector('.upload-actions');
  actions.innerHTML = '<span class="spinner dark"></span> Uploading...';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);

  try {
    const res = await apiPost('/api/application/upload-document', formData, true);
    if (res.ok) {
      card.classList.add('has-file');
      card.querySelector('.upload-card-file').textContent = res.original_name;
      const topRow = card.querySelector('.upload-card-top');
      if (!topRow.querySelector('.chip')) {
        const chip = document.createElement('span');
        chip.className = 'chip chip-warning';
        chip.textContent = 'Pending';
        topRow.appendChild(chip);
      }
      actions.innerHTML = `
        <button class="btn btn-secondary btn-sm" onclick="showToast('Preview is a demo feature.')">Preview</button>
        <button class="btn btn-ghost btn-sm" onclick="removeDocument('${docType}')">Remove</button>`;
      showToast('Document uploaded successfully.', 'success');
    } else {
      showToast(res.error || 'Upload failed.', 'error');
    }
  } catch (err) {
    showToast('Network error — please try again.', 'error');
  }
}

async function removeDocument(docType) {
  const res = await apiPost('/api/application/remove-document', { doc_type: docType });
  if (res.ok) {
    const card = document.querySelector(`.upload-card[data-doctype="${docType}"]`);
    card.classList.remove('has-file');
    card.querySelector('.upload-card-file').textContent = 'No file uploaded';
    const chip = card.querySelector('.chip');
    if (chip) chip.remove();
    const input = card.querySelector('input[type=file]');
    input.value = '';
    card.querySelector('.upload-actions').innerHTML =
      '<button class="upload-drop" onclick="this.closest(\'.upload-card\').querySelector(\'input[type=file]\').click()">Click to upload</button>';
    showToast('Document removed.');
  }
}

function buildSummary() {
  const rows = [
    ['Full Name', document.getElementById('full_name').value || '—'],
    ['Date of Birth', document.getElementById('dob').value || '—'],
    ['Gender', document.getElementById('gender').value || '—'],
    ['Email', document.getElementById('email').value || '—'],
    ['Mobile Number', document.getElementById('mobile').value || '—'],
    ['Address', document.getElementById('address').value || '—'],
    ['City', document.getElementById('city').value || '—'],
    ['State', document.getElementById('state').value || '—'],
    ['PIN Code', document.getElementById('pincode').value || '—'],
    ['Passport Type', (document.querySelector('input[name="passport_type"]:checked') || {}).value || 'New Passport'],
  ];

  const docsRows = [];
  document.querySelectorAll('.upload-card').forEach(card => {
    const label = card.querySelector('.upload-card-title').textContent;
    const file = card.querySelector('.upload-card-file').textContent;
    docsRows.push([label, file]);
  });

  const html = `
    <div class="summary-block">
      <h4>Applicant Details</h4>
      <div class="summary-grid">
        ${rows.map(([k, v]) => `<div class="summary-row"><span class="k">${k}</span><span>${v}</span></div>`).join('')}
      </div>
    </div>
    <div class="summary-block">
      <h4>Documents</h4>
      <div class="summary-grid">
        ${docsRows.map(([k, v]) => `<div class="summary-row"><span class="k">${k}</span><span>${v}</span></div>`).join('')}
      </div>
    </div>
  `;
  document.getElementById('summaryContainer').innerHTML = html;
}

async function submitApplication() {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Submitting...';
  try {
    const res = await apiPost('/api/application/submit', {});
    if (res.ok) {
      document.getElementById('successAppId').innerHTML =
        `Your Application ID is <strong>${res.application_id}</strong>. Please note it down to track your status.`;
      document.getElementById('successModal').classList.add('open');
    } else {
      showToast(res.error || 'Submission failed.', 'error');
      btn.disabled = false;
      btn.textContent = 'Submit Application';
    }
  } catch (err) {
    showToast('Network error — please try again.', 'error');
    btn.disabled = false;
    btn.textContent = 'Submit Application';
  }
}
