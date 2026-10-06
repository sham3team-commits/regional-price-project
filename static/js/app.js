// Shared UI behaviour. No build step: plain JS + Tom Select from the CDN.

function initTomSelect(root) {
  root.querySelectorAll("select[data-tom-select]").forEach((select) => {
    if (select.tomselect) return;
    const multi = select.multiple;
    new TomSelect(select, {
      maxOptions: 500,
      allowEmptyOption: !multi,
      plugins: multi ? ["remove_button"] : [],
    });
  });
}

document.addEventListener("DOMContentLoaded", () => initTomSelect(document));
