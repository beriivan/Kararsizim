// Turn Django messages into toasts that fade away after a few seconds.
// Without JavaScript they simply stay as a strip at the top of the page.
(function () {
  var container = document.querySelector(".messages");
  if (!container) return;

  container.classList.add("is-toast");
  var VISIBLE_MS = 4500;

  container.querySelectorAll(".message").forEach(function (message, index) {
    message.style.pointerEvents = "auto";
    setTimeout(function () {
      message.classList.add("is-leaving");
      setTimeout(function () { message.remove(); }, 350);
    }, VISIBLE_MS + index * 400);
  });
})();

// Send each POST form only once: ignore further clicks while the request is
// in flight. (The server also guards against duplicates; this is the first line.)
(function () {
  function unlock(form) {
    delete form.dataset.submitting;
    form.querySelectorAll("button[type=submit]").forEach(function (button) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || (form.method || "").toLowerCase() !== "post") return;

    if (form.dataset.submitting) {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "1";
    // Disable after the browser has collected the form data.
    setTimeout(function () {
      form.querySelectorAll("button[type=submit]").forEach(function (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
      });
    }, 0);
  });

  // Coming back with the browser's back button must not leave a locked form.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-submitting]").forEach(unlock);
  });
})();
