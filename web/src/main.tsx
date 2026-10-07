import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/fira-sans-condensed/400.css";
import "@fontsource/pt-sans/400.css";
import "@fontsource/pt-sans/700.css";
import "./styles.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
