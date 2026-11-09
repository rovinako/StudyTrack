for (const form of document.querySelectorAll('form[data-confirm]')) {
  form.addEventListener('submit', event => {
    if (!confirm(form.dataset.confirm)) event.preventDefault();
  });
}
for (const form of document.querySelectorAll('form[data-loading]')) {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button');
    button.disabled = true;
    button.textContent = 'Creating your plan…';
  });
}
