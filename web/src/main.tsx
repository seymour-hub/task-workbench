import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import App from "./App";
import { loadTaxonomy } from "./lib/taxonomy";
import "./index.css";

if (new URLSearchParams(window.location.search).get("dock") === "1") {
  document.documentElement.classList.add("dock-mode");
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

loadTaxonomy().finally(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              style: {
                background: "#111A2E",
                border: "1px solid #24365A",
                color: "#E6ECF7",
              },
            }}
          />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  );
});
