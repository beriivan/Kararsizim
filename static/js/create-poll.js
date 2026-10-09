// Add/remove option inputs on the poll form (2-5 options).
// The server validates the same rules, so the form still works without JavaScript.
(function () {
  var MIN = 2;
  var MAX = 5;
  var list = document.getElementById("option-list");
  var addButton = document.getElementById("add-option");
  if (!list || !addButton) return;

  var rows = Array.prototype.slice.call(list.querySelectorAll("[data-option-row]"));

  function input(row) { return row.querySelector("input"); }
  function isHidden(row) { return row.hidden; }
  function visibleRows() { return rows.filter(function (row) { return !isHidden(row); }); }

  function refresh() {
    var visible = visibleRows();
    addButton.hidden = visible.length >= MAX;
    visible.forEach(function (row) {
      row.querySelector("[data-remove]").hidden = visible.length <= MIN;
    });
  }

  // Start with the filled rows (at least MIN) visible; hide the rest.
  var shown = 0;
  rows.forEach(function (row) {
    if (shown < MIN || input(row).value.trim() !== "") {
      row.hidden = false;
      shown++;
    } else {
      row.hidden = true;
    }
  });

  addButton.addEventListener("click", function () {
    var next = rows.find(isHidden);
    if (!next) return;
    next.hidden = false;
    input(next).focus();
    refresh();
  });

  list.addEventListener("click", function (event) {
    var button = event.target.closest("[data-remove]");
    if (!button || visibleRows().length <= MIN) return;
    var row = button.closest("[data-option-row]");
    input(row).value = "";
    row.hidden = true;
    // Keep hidden rows at the end so "add" always reveals the next one in order.
    list.appendChild(row);
    rows = Array.prototype.slice.call(list.querySelectorAll("[data-option-row]"));
    refresh();
  });

  refresh();

  // Character counter for the question.
  var question = document.querySelector("#poll-form [name='question']");
  var counter = document.getElementById("question-counter");
  if (question && counter) {
    var max = parseInt(counter.dataset.max, 10);
    var update = function () { counter.textContent = question.value.length + " / " + max; };
    question.setAttribute("maxlength", max);
    question.addEventListener("input", update);
    update();
  }
})();
