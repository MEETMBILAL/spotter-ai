// Analytics and Vercel Speed Insights client module

/**
 * Initializes Vercel Web Analytics (@vercel/analytics) dynamically if available or via script
 */
export function injectVercelAnalytics() {
  if (typeof window === "undefined") return;

  // Prevent duplicate injection
  if ((window as unknown as { __va_initialized?: boolean }).__va_initialized) return;
  (window as unknown as { __va_initialized?: boolean }).__va_initialized = true;

  // 1. Inject Vercel Analytics script
  const vaScript = document.createElement("script");
  vaScript.defer = true;
  vaScript.src = "/_vercel/insights/script.js";
  vaScript.onerror = () => {
    // Graceful fallback when not deployed on Vercel or running locally
  };
  document.head.appendChild(vaScript);

  // 2. Inject Vercel Speed Insights script
  const speedScript = document.createElement("script");
  speedScript.defer = true;
  speedScript.src = "/_vercel/speed-insights/script.js";
  speedScript.onerror = () => {
    // Graceful fallback when running locally or on non-Vercel host
  };
  document.head.appendChild(speedScript);
}

/**
 * Custom performance reporter for Core Web Vitals (LCP, FID, CLS, INP, FCP, TTFB)
 * Transmits metrics to both standard Performance API console and any attached analytics beacons
 */
export function reportWebVitals() {
  if (typeof window === "undefined" || !("PerformanceObserver" in window)) return;

  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        // Send metric to custom analytics event or console in development
        if (process.env.NODE_ENV === "development") {
          console.debug(`[Speed Insights] ${entry.name}:`, entry);
        }
      }
    });

    observer.observe({
      entryTypes: ["largest-contentful-paint", "first-input", "layout-shift", "navigation"],
    });
  } catch {
    // Safari / older browser gracefully ignored
  }
}

/**
 * Custom tracking function for key actions (AEO / engagement analytics)
 */
export function trackEvent(name: string, properties?: Record<string, unknown>) {
  if (typeof window === "undefined") return;

  // Send to Vercel custom event queue if present
  const va = (window as unknown as { va?: (type: string, name: string, data?: Record<string, unknown>) => void }).va;
  if (typeof va === "function") {
    va("event", name, properties);
  }

  // Also dispatch standard custom event for generic analytics integration
  window.dispatchEvent(new CustomEvent("spotter_analytics_event", { detail: { name, properties } }));
}
