(() => {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const header = document.querySelector("[data-header]");
  const progress = document.querySelector(".scroll-progress span");
  const hero = document.querySelector(".hero");
  let scrollTicking = false;

  const updateScrollEffects = () => {
    const scrollY = window.scrollY;
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = maxScroll > 0 ? Math.min(scrollY / maxScroll, 1) : 0;

    if (header) {
      header.classList.toggle("is-scrolled", scrollY > 18);
    }

    if (progress) {
      progress.style.transform = `scaleX(${ratio})`;
    }

    scrollTicking = false;
  };

  window.addEventListener("scroll", () => {
    if (scrollTicking) return;
    scrollTicking = true;
    window.requestAnimationFrame(updateScrollEffects);
  }, { passive: true });

  updateScrollEffects();

  const downloadCountUrl = document.body.dataset.downloadCountUrl;
  const downloadCountNodes = document.querySelectorAll("[data-download-count]");
  const downloadProof = document.querySelector(".download-proof");
  let displayedDownloadCount = Number.parseInt(
    document.body.dataset.downloadCount || "0",
    10,
  );

  const formatDownloadCount = (count) => new Intl.NumberFormat("en-US").format(count);

  const updateDownloadCount = (count) => {
    if (!Number.isFinite(count)) return;
    displayedDownloadCount = count;
    downloadCountNodes.forEach((node) => {
      node.textContent = formatDownloadCount(count);
    });
    downloadProof?.classList.remove("is-updating");
    window.requestAnimationFrame(() => {
      downloadProof?.classList.add("is-updating");
    });
  };

  const getCookie = (name) => {
    const cookie = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  };

  document.querySelectorAll("[data-download-link]").forEach((link) => {
    link.addEventListener("click", () => {
      if (!downloadCountUrl) return;

      updateDownloadCount(displayedDownloadCount + 1);
      const csrfToken = getCookie("csrftoken");
      const payload = new FormData();
      payload.append("csrfmiddlewaretoken", csrfToken);

      if (navigator.sendBeacon?.(downloadCountUrl, payload)) return;

      fetch(downloadCountUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken },
        keepalive: true,
      }).catch(() => {
        // The browser may already be following the APK link.
      });
    });
  });

  const trendCanvas = document.querySelector("[data-trend-field]");
  if (trendCanvas && hero) {
    const context = trendCanvas.getContext("2d", { alpha: false });
    const pointer = { x: 0.74, y: 0.42, active: false };
    const lanes = [
      { base: 0.25, amplitude: 25, frequency: 0.009, speed: 0.0011, phase: 0.2, color: "#ff5a16", width: 2.2 },
      { base: 0.42, amplitude: 17, frequency: 0.012, speed: -0.0008, phase: 1.7, color: "rgba(255,255,255,0.58)", width: 1 },
      { base: 0.59, amplitude: 21, frequency: 0.008, speed: 0.0007, phase: 2.9, color: "#8ddcff", width: 1.2 },
      { base: 0.75, amplitude: 14, frequency: 0.014, speed: -0.001, phase: 4.1, color: "#c8f36b", width: 1 },
    ];
    const carriers = Array.from({ length: 24 }, (_, index) => ({
      lane: index % lanes.length,
      offset: (index * 0.173) % 1,
      speed: 0.000035 + (index % 5) * 0.000006,
      size: 4 + (index % 3) * 2,
    }));
    let canvasWidth = 0;
    let canvasHeight = 0;
    let animationFrame = null;
    let isVisible = true;

    const laneY = (lane, x, time) => {
      const baseY = lane.base * canvasHeight;
      const wave = Math.sin((x * lane.frequency) + (time * lane.speed) + lane.phase) * lane.amplitude;
      if (!pointer.active) return baseY + wave;

      const distance = (x - (pointer.x * canvasWidth)) / Math.max(canvasWidth * 0.2, 1);
      const influence = Math.exp(-(distance * distance));
      return baseY + wave + ((pointer.y * canvasHeight) - baseY) * influence * 0.11;
    };

    const drawTrendField = (time = 0) => {
      if (!context || !canvasWidth || !canvasHeight) return;

      context.fillStyle = "#09090a";
      context.fillRect(0, 0, canvasWidth, canvasHeight);

      const gridSize = canvasWidth < 680 ? 48 : 72;
      context.lineWidth = 1;
      context.strokeStyle = "rgba(255,255,255,0.055)";
      context.beginPath();
      for (let x = 0; x <= canvasWidth; x += gridSize) {
        context.moveTo(x + 0.5, 0);
        context.lineTo(x + 0.5, canvasHeight);
      }
      for (let y = 0; y <= canvasHeight; y += gridSize) {
        context.moveTo(0, y + 0.5);
        context.lineTo(canvasWidth, y + 0.5);
      }
      context.stroke();

      context.strokeStyle = "rgba(255,90,22,0.22)";
      context.strokeRect(canvasWidth * 0.64, canvasHeight * 0.1, canvasWidth * 0.28, canvasHeight * 0.72);
      context.strokeStyle = "rgba(141,220,255,0.15)";
      context.strokeRect(canvasWidth * 0.71, canvasHeight * 0.18, canvasWidth * 0.2, canvasHeight * 0.56);

      lanes.forEach((lane) => {
        context.beginPath();
        context.lineWidth = lane.width;
        context.strokeStyle = lane.color;
        for (let x = 0; x <= canvasWidth + 8; x += 8) {
          const y = laneY(lane, x, time);
          if (x === 0) context.moveTo(x, y);
          else context.lineTo(x, y);
        }
        context.stroke();
      });

      carriers.forEach((carrier, index) => {
        const lane = lanes[carrier.lane];
        const progressValue = ((time * carrier.speed) + carrier.offset) % 1;
        const x = progressValue * canvasWidth;
        const y = laneY(lane, x, time);
        context.save();
        context.translate(x, y);
        if (index % 2 === 0) context.rotate(Math.PI / 4);
        context.fillStyle = lane.color;
        context.fillRect(-carrier.size / 2, -carrier.size / 2, carrier.size, carrier.size);
        context.restore();
      });

      const scanX = ((time * 0.000055) % 1) * canvasWidth;
      context.strokeStyle = "rgba(255,90,22,0.34)";
      context.beginPath();
      context.moveTo(scanX, 0);
      context.lineTo(scanX, canvasHeight);
      context.stroke();

      const barStart = canvasWidth * 0.76;
      context.fillStyle = "rgba(255,255,255,0.16)";
      for (let index = 0; index < 13; index += 1) {
        const barX = barStart + index * 15;
        const barHeight = 12 + Math.abs(Math.sin((time * 0.0012) + index * 0.58)) * 52;
        context.fillRect(barX, canvasHeight * 0.88 - barHeight, 5, barHeight);
      }

      context.font = '700 9px "Manrope", Arial, sans-serif';
      context.fillStyle = "rgba(255,255,255,0.34)";
      context.fillText("COMMUNITY SIGNAL", 18, 24);
      context.fillText("DISCOVER / RATE / CONNECT", 18, canvasHeight - 18);
    };

    const resizeTrendField = () => {
      const bounds = trendCanvas.getBoundingClientRect();
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvasWidth = Math.max(Math.round(bounds.width), 1);
      canvasHeight = Math.max(Math.round(bounds.height), 1);
      trendCanvas.width = Math.round(canvasWidth * pixelRatio);
      trendCanvas.height = Math.round(canvasHeight * pixelRatio);
      context?.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      drawTrendField(0);
    };

    const animateTrendField = (time) => {
      drawTrendField(time);
      animationFrame = isVisible && !document.hidden
        ? window.requestAnimationFrame(animateTrendField)
        : null;
    };

    const startTrendField = () => {
      if (reducedMotion || animationFrame !== null || !isVisible || document.hidden) return;
      animationFrame = window.requestAnimationFrame(animateTrendField);
    };

    const stopTrendField = () => {
      if (animationFrame === null) return;
      window.cancelAnimationFrame(animationFrame);
      animationFrame = null;
    };

    hero.addEventListener("pointermove", (event) => {
      const bounds = hero.getBoundingClientRect();
      pointer.x = Math.min(Math.max((event.clientX - bounds.left) / Math.max(bounds.width, 1), 0), 1);
      pointer.y = Math.min(Math.max((event.clientY - bounds.top) / Math.max(bounds.height, 1), 0), 1);
      pointer.active = true;
    }, { passive: true });

    hero.addEventListener("pointerleave", () => {
      pointer.active = false;
    }, { passive: true });

    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(resizeTrendField);
      resizeObserver.observe(trendCanvas);
    } else {
      window.addEventListener("resize", resizeTrendField, { passive: true });
    }

    if ("IntersectionObserver" in window) {
      const visibilityObserver = new IntersectionObserver((entries) => {
        isVisible = entries.some((entry) => entry.isIntersecting);
        if (isVisible) startTrendField();
        else stopTrendField();
      }, { threshold: 0.01 });
      visibilityObserver.observe(hero);
    }

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopTrendField();
      else startTrendField();
    });

    resizeTrendField();
    if (reducedMotion) drawTrendField(0);
    else startTrendField();
  }

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
    }, {
      threshold: 0.1,
      rootMargin: "0px 0px -40px",
    });

    revealItems.forEach((item) => revealObserver.observe(item));
  }

  const explorer = document.querySelector("[data-screen-explorer]");
  if (explorer) {
    const tabs = Array.from(explorer.querySelectorAll("[data-screen-one]"));
    const stage = explorer.querySelector(".screen-stage");
    const imageOne = explorer.querySelector("[data-screen-image-one]");
    const imageTwo = explorer.querySelector("[data-screen-image-two]");
    const titleOne = explorer.querySelector("[data-screen-title-one]");
    const titleTwo = explorer.querySelector("[data-screen-title-two]");
    const label = explorer.querySelector("[data-screen-label]");
    const copy = explorer.querySelector("[data-screen-copy]");
    const counter = explorer.querySelector("[data-current-screen]");
    const previousButton = explorer.querySelector("[data-screen-previous]");
    const nextButton = explorer.querySelector("[data-screen-next]");
    let activeIndex = 0;
    let pointerStart = null;

    tabs.forEach((tab) => {
      [tab.dataset.screenOne, tab.dataset.screenTwo].forEach((source) => {
        if (!source) return;
        const preload = new Image();
        preload.src = source;
      });
    });

    const showScreen = (nextIndex, shouldFocus = false) => {
      if (!tabs.length || !imageOne || !imageTwo || !stage) return;

      const normalizedIndex = (nextIndex + tabs.length) % tabs.length;
      const nextTab = tabs[normalizedIndex];
      if (
        normalizedIndex === activeIndex
        && imageOne.src.endsWith(nextTab.dataset.screenOne)
        && imageTwo.src.endsWith(nextTab.dataset.screenTwo)
      ) return;

      activeIndex = normalizedIndex;
      tabs.forEach((tab, index) => {
        const selected = index === activeIndex;
        tab.classList.toggle("is-active", selected);
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
      });

      const commitImage = () => {
        imageOne.src = nextTab.dataset.screenOne;
        imageTwo.src = nextTab.dataset.screenTwo;
        imageOne.alt = nextTab.dataset.altOne || "Trendit app screen";
        imageTwo.alt = nextTab.dataset.altTwo || "Trendit app screen";
        if (titleOne) titleOne.textContent = nextTab.dataset.titleOne;
        if (titleTwo) titleTwo.textContent = nextTab.dataset.titleTwo;
        if (label) label.textContent = nextTab.dataset.label;
        if (copy) copy.textContent = nextTab.dataset.copy;
        if (counter) counter.textContent = String(activeIndex + 1).padStart(2, "0");

        window.requestAnimationFrame(() => {
          stage.classList.remove("is-changing");
        });
      };

      stage.classList.add("is-changing");
      if (reducedMotion) {
        commitImage();
      } else {
        const sources = [nextTab.dataset.screenOne, nextTab.dataset.screenTwo];
        Promise.all(sources.map((source) => new Promise((resolve, reject) => {
          const nextImage = new Image();
          nextImage.onload = resolve;
          nextImage.onerror = reject;
          nextImage.src = source;
        }))).then(commitImage).catch(() => stage.classList.remove("is-changing"));
      }

      const tabList = nextTab.parentElement;
      if (tabList) {
        const targetLeft = nextTab.offsetLeft
          - ((tabList.clientWidth - nextTab.offsetWidth) / 2);
        tabList.scrollTo({
          left: Math.max(targetLeft, 0),
          behavior: reducedMotion ? "auto" : "smooth",
        });
      }

      if (shouldFocus) nextTab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => showScreen(index));
      tab.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        showScreen(index + (event.key === "ArrowRight" ? 1 : -1), true);
      });
    });

    previousButton?.addEventListener("click", () => showScreen(activeIndex - 1));
    nextButton?.addEventListener("click", () => showScreen(activeIndex + 1));

    stage?.addEventListener("pointerdown", (event) => {
      pointerStart = { x: event.clientX, y: event.clientY };
    }, { passive: true });

    stage?.addEventListener("pointerup", (event) => {
      if (!pointerStart) return;
      const deltaX = event.clientX - pointerStart.x;
      const deltaY = event.clientY - pointerStart.y;
      pointerStart = null;

      if (Math.abs(deltaX) < 46 || Math.abs(deltaX) < Math.abs(deltaY) * 1.3) return;
      showScreen(activeIndex + (deltaX < 0 ? 1 : -1));
    }, { passive: true });

    stage?.addEventListener("pointercancel", () => {
      pointerStart = null;
    });
  }

  document.querySelectorAll("a[href^='#']").forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;
      const target = document.querySelector(href);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
    });
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }
})();
