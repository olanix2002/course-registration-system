/* Keeps the credit-unit total on the course selection page up to date.
   The server re-checks every number on submit; this is feedback only. */
(function () {
  "use strict";

  var form = document.querySelector("[data-credit-total]");
  if (!form) {
    return;
  }

  var max = parseInt(form.getAttribute("data-max-units"), 10) || 0;
  var output = document.querySelector("[data-credit-total-output]");
  var warning = document.querySelector("[data-credit-total-warning]");
  var progress = document.querySelector("[data-credit-progress]");
  var progressBar = document.querySelector("[data-credit-progress-bar]");
  var saveButton = form.querySelector("[data-save-button]");
  var boxes = form.querySelectorAll('input[name="courses"]');

  function update() {
    var total = 0;
    boxes.forEach(function (box) {
      if (box.checked) {
        total += parseInt(box.getAttribute("data-credit-units"), 10) || 0;
      }
      // Highlight the matching mobile card.
      var card = box.closest(".course-card");
      if (card) {
        card.classList.toggle("is-selected", box.checked);
      }
    });

    var over = total > max;

    if (output) {
      output.textContent = total;
    }

    if (warning) {
      warning.hidden = !over;
    }

    if (progress && progressBar) {
      var percent = max > 0 ? Math.min((total / max) * 100, 100) : 0;
      progressBar.style.width = percent + "%";
      progressBar.setAttribute("aria-valuenow", String(total));
      progress.classList.toggle("is-over", over);
      progress.classList.toggle("is-near", !over && total >= max * 0.85);
    }

    if (saveButton) {
      saveButton.disabled = over;
    }
  }

  boxes.forEach(function (box) {
    box.addEventListener("change", update);
  });

  update();
})();