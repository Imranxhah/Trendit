(() => {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const header = document.querySelector("[data-header]");
  const progress = document.querySelector(".scroll-progress span");
  const hero = document.querySelector(".hero");
  let ticking = false;

  const updateScrollEffects = () => {
    const y = window.scrollY;
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = maxScroll > 0 ? Math.min(y / maxScroll, 1) : 0;

    if (header) header.classList.toggle("is-scrolled", y > 20);
    if (progress) progress.style.transform = `scaleX(${ratio})`;

    if (hero && !reducedMotion && window.innerWidth > 780) {
      const shift = Math.min(y * 0.06, 34);
      hero.style.backgroundPosition = `center calc(45% + ${shift}px)`;
    }
    ticking = false;
  };

  window.addEventListener("scroll", () => {
    if (!ticking) {
      window.requestAnimationFrame(updateScrollEffects);
      ticking = true;
    }
  }, { passive: true });
  updateScrollEffects();

  const revealItems = document.querySelectorAll(".reveal:not(.is-visible)");
  if (reducedMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -50px" });
    revealItems.forEach((item) => revealObserver.observe(item));
  }

  const switcher = document.querySelector("[data-screen-switcher]");
  if (switcher) {
    const tabs = Array.from(switcher.querySelectorAll("[data-screen]"));
    const stage = switcher.querySelector(".screen-stage");
    const image = switcher.querySelector("[data-screen-image]");
    const label = switcher.querySelector("[data-screen-label]");
    const number = switcher.querySelector(".stage-number");

    tabs.forEach((tab) => {
      const preload = new Image();
      preload.src = tab.dataset.screen;

      tab.addEventListener("click", () => {
        const index = tabs.indexOf(tab);
        if (tab.classList.contains("is-active") || !image || !stage) return;

        tabs.forEach((item) => {
          const selected = item === tab;
          item.classList.toggle("is-active", selected);
          item.setAttribute("aria-selected", selected ? "true" : "false");
        });

        stage.classList.add("is-changing");
        window.setTimeout(() => {
          image.src = tab.dataset.screen;
          image.alt = tab.dataset.alt || "Trendit app screen";
          if (label) label.textContent = tab.textContent.trim();
          if (number) number.textContent = String(index + 1).padStart(2, "0");
          window.requestAnimationFrame(() => stage.classList.remove("is-changing"));
        }, reducedMotion ? 0 : 170);
      });
    });
  }

  document.querySelectorAll("a[href^='#']").forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const target = document.querySelector(anchor.getAttribute("href"));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
    });
  });

  if (window.lucide) window.lucide.createIcons();
})();
