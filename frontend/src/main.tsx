import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/app.css";
import { injectVercelAnalytics, reportWebVitals } from "./lib/analytics";

// Initialize Vercel Analytics, Speed Insights and Web Vitals monitoring
injectVercelAnalytics();
reportWebVitals();

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
