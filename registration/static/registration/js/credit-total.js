/* Keeps the credit-unit total on the course selection page up to date.
   The server re-checks everything on submit; this is only for feedback. */
(function () {
    "use strict";

    var form = document.querySelector("[data-credit-total]");
    if (!form) {
        return;
    }

    var max = parseInt(form.getAttribute("data-max-units"), 10) || 0;
    var output = document.querySelector("[data-credit-total-output]");
    var warning = document.querySelector("[data-credit-total-warning]");
    var boxes = form.querySelectorAll('input[name="courses"]');

    function update() {
        var total = 0;
        boxes.forEach(function (box) {
            if (box.checked) {
                total += parseInt(box.getAttribute("data-credit-units"), 10) || 0;
            }
        });
        if (output) {
            output.textContent = total;
        }
        if (warning) {
            warning.hidden = total <= max;
        }
    }

    boxes.forEach(function (box) {
        box.addEventListener("change", update);
    });

    update();
})();
