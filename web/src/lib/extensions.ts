import type { ComponentType, ReactNode } from "react";

/**
 * Private extension point. Files under `src/private/` are gitignored and can
 * export `routes` and `nav` arrays; the public build simply sees none of them.
 *
 * Example `src/private/index.tsx`:
 *
 *   export const nav = [{ to: "/private/demo", label: "私有功能" }];
 *   export const routes = [{ path: "private/demo", element: <DemoPage /> }];
 */
export interface PrivateNavItem {
  to: string;
  label: string;
  icon?: ComponentType<{ size?: number; strokeWidth?: number }>;
  end?: boolean;
  badge?: number;
}

export interface PrivateRoute {
  path: string;
  element: ReactNode;
}

interface PrivateExtensions {
  routes: PrivateRoute[];
  nav: PrivateNavItem[];
}

let cached: PrivateExtensions | null = null;

export function loadPrivateExtensions(): PrivateExtensions {
  if (cached) return cached;
  const modules = import.meta.glob("../private/**/*.{ts,tsx}", { eager: true });
  const routes: PrivateRoute[] = [];
  const nav: PrivateNavItem[] = [];
  Object.values(modules).forEach((module) => {
    const value = module as {
      routes?: PrivateRoute[];
      nav?: PrivateNavItem[];
    };
    if (Array.isArray(value.routes)) routes.push(...value.routes);
    if (Array.isArray(value.nav)) nav.push(...value.nav);
  });
  cached = { routes, nav };
  return cached;
}
