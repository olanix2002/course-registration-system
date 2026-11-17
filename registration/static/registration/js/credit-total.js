/* Keeps every credit-unit readout on the course selection page in step.

   There is exactly one checkbox per course, so the total is simply the sum
   of the ticked boxes. The server re-checks every number on submit; this is
   feedback only. */
(function () {
  "use strict";

  var form = document.querySelector("[data-credit-total]");
  if (!form) {
    return;
  }

  var max = parseInt(form.getAttribute("data-max-units"), 10) || 0;

  // Several elements may carry the same hook (summary card, sticky bar), so
  // they are collected as lists and all of them get updated.
  function all(selector) {
    return Array.prototype.slice.call(document.querySelectorAll(selector));
  }

  var totals = all("[data-credit-total-output]");
  var counts = all("[data-credit-count-output]");
  var warnings = all("[data-credit-total-warning]");
  var meters = all("[data-credit-progress]");
  var bars = all("[data-credit-progress-bar]");
  var saveButtons = all("[data-save-button]");
  var boxes = all('input[name="courses"]');

  /* Work out the total from the ticked boxes. */
  function computeTotal() {
    var total = 0;
    var count = 0;
    boxes.forEach(function (box) {
      if (box.checked) {
        total += parseInt(box.getAttribute("data-credit-units"), 10) || 0;
        count += 1;
      }
    });
    return { total: total, count: count };
  }

  /* Write the total to every place that shows units. */
  function render() {
    var result = computeTotal();
    var total = result.total;
    var over = total > max;

    totals.forEach(function (node) {
      node.textContent = String(total);
    });

    counts.forEach(function (node) {
      node.textContent = String(result.count);
    });

    warnings.forEach(function (node) {
      node.hidden = !over;
    });

    var percent = max > 0 ? Math.min((total / max) * 100, 100) : 0;
    bars.forEach(function (bar) {
      bar.style.width = percent + "%";
    });
    meters.forEach(function (meter) {
      meter.setAttribute("aria-valuenow", String(total));
      meter.classList.toggle("is-over", over);
      meter.classList.toggle("is-near", !over && total >= max * 0.85);
    });

    saveButtons.forEach(function (button) {
      button.disabled = over;
    });

    // Highlight the selected rows.
    boxes.forEach(function (box) {
      var item = box.closest(".course-item");
      if (item) {
        item.classList.toggle("is-selected", box.checked);
      }
    });
  }

  boxes.forEach(function (box) {
    box.addEventListener("change", render);
  });

  render();
})();