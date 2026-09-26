let selectedOffice = null, selectedDate = null, selectedTime = null;

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.office-option').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.office-option').forEach(o => o.classList.remove('selected'));
      el.classList.add('selected');
      selectedOffice = el.dataset.value;
    });
  });
  document.querySelectorAll('.date-chip').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.date-chip').forEach(o => o.classList.remove('selected'));
      el.classList.add('selected');
      selectedDate = el.dataset.value;
    });
  });
  document.querySelectorAll('.slot-chip').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.slot-chip').forEach(o => o.classList.remove('selected'));
      el.classList.add('selected');
      selectedTime = el.dataset.value;
    });
  });
});

async function confirmAppointment() {
  if (!selectedOffice || !selectedDate || !selectedTime) {
    showToast('Please select an office, date, and time slot.', 'error');
    return;
  }
  const btn = document.getElementById('confirmBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Confirming...';

  try {
    const res = await apiPost('/api/appointment/book', {
      office: selectedOffice, date: selectedDate, time: selectedTime
    });
    if (res.ok) {
      showToast('Appointment confirmed!', 'success');
      setTimeout(() => window.location.href = '/dashboard', 900);
    } else {
      showToast(res.error || 'Booking failed.', 'error');
      btn.disabled = false;
      btn.textContent = 'Confirm Appointment';
    }
  } catch (err) {
    showToast('Network error — please try again.', 'error');
    btn.disabled = false;
    btn.textContent = 'Confirm Appointment';
  }
}
