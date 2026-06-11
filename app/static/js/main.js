document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("demo-modal");
  const iframe = document.getElementById("demo-iframe");
  const modalName = document.getElementById("modal-demo-name");

  function openDemo(card) {
    const slug = card.dataset.slug;
    const name = card.dataset.name;

    modalName.textContent = name;
    iframe.src = `/demos/${slug}/index.html`;
    modal.hidden = false;
    document.body.style.overflow = "hidden";

    fetch(`/api/demos/${slug}/view`, { method: "POST" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        const counter = card.querySelector("[data-view-count]");
        if (counter) {
          counter.textContent = `\u{1F441} ${data.view_count}`;
        }
      })
      .catch(() => {});
  }

  function closeModal() {
    modal.hidden = true;
    iframe.src = "about:blank";
    document.body.style.overflow = "";
  }

  document.querySelectorAll(".demo-card").forEach((card) => {
    card.addEventListener("click", () => openDemo(card));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDemo(card);
      }
    });
  });

  document.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
});
