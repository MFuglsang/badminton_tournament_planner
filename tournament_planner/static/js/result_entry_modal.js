(function () {
  var dialog = document.getElementById('result-entry-dialog');
  if (!dialog) return;

  var content = dialog.querySelector('.result-entry-dialog-content');
  var activeResultLink = null;

  function renderForm(html, url) {
    var parsed = new DOMParser().parseFromString(html, 'text/html');
    var formContent = parsed.querySelector('.content-col-sm');
    if (!formContent) {
      window.location.href = url;
      return;
    }

    content.replaceChildren();
    var styles = parsed.head.querySelectorAll('style');
    if (styles.length) content.appendChild(styles[styles.length - 1].cloneNode(true));
    content.appendChild(document.importNode(formContent, true));

    var form = content.querySelector('#result-form');
    form.action = url;
    var formScript = Array.from(parsed.scripts).find(function (script) {
      return script.textContent.indexOf('var TEAM1_PK') !== -1;
    });
    if (formScript) {
      var executable = document.createElement('script');
      executable.textContent = formScript.textContent;
      document.body.appendChild(executable);
      executable.remove();
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      fetch(url, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
      }).then(function (response) {
        if (response.status === 204) {
          dialog.close();
          window.location.reload();
          return;
        }
        return response.text().then(function (responseHtml) {
          renderForm(responseHtml, response.url || url);
        });
      });
    });
    var cancelButton = content.querySelector('#cancel-result-popup');
    if (cancelButton) {
      cancelButton.addEventListener('click', function () {
        dialog.close();
      });
    }
  }

  function openResultEntryModal(rawUrl, trigger) {
    var url = new URL(rawUrl, window.location.href);
    url.searchParams.set('popup', '1');
    activeResultLink = trigger || null;
    content.textContent = '';
    dialog.showModal();
    fetch(url.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (response) {
        return response.text().then(function (html) {
          renderForm(html, response.url);
        });
      })
      .catch(function () { window.location.href = url.href; });
  }

  window.openResultEntryModal = function (url) {
    openResultEntryModal(url, null);
  };

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a.js-result-modal');
    if (!link) return;
    event.preventDefault();
    openResultEntryModal(link.href, link);
  });
  dialog.addEventListener('close', function () {
    if (activeResultLink) activeResultLink.blur();
    activeResultLink = null;
  });
  dialog.querySelector('.result-entry-dialog-close').addEventListener('click', function () {
    dialog.close();
  });
  dialog.addEventListener('click', function (event) {
    if (event.target === dialog) dialog.close();
  });
})();