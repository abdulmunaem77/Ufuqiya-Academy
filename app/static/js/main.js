/* WAHJ Academy — progressive enhancement only (site works without JS). */
(function () {
  'use strict';

  // Mobile navigation
  var toggle = document.querySelector('[data-nav-toggle]');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // Dismiss flash messages
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-dismiss]');
    if (b) { var f = b.closest('.flash'); if (f) f.remove(); }
  });

  // Print button (certificates)
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-print]')) window.print();
  });

  // Confirm destructive POST forms
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute && e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Auto-submit selects (filters, status changes)
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el.matches && el.matches('select[data-autosubmit]') && el.form) {
      if (el.form.requestSubmit) el.form.requestSubmit(); else el.form.submit();
    }
  });
})();
