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
