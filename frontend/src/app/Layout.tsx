import { Activity } from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { DemoBanner } from "../components/DemoBanner";
import { useHealth } from "../hooks/queries";
import { cn } from "../lib/cn";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/library", label: "Fault Library", end: false },
];

export function Layout() {
  const health = useHealth();
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to content
      </a>
      {health.data?.demo_mode && <DemoBanner />}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-slate-900">
            <Activity aria-hidden="true" className="size-5 text-sky-700" />
            FaultIQ
            <span className="text-xs font-normal text-slate-500">RTU fault detection &amp; diagnostics</span>
          </NavLink>
          <nav aria-label="Main">
            <ul className="flex gap-1">
              {NAV.map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.end}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-3 py-1.5 text-sm font-medium",
                        isActive ? "bg-sky-50 text-sky-900" : "text-slate-700 hover:bg-slate-100",
                      )
                    }
                  >
                    {n.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-600 sm:px-6">
          <p>
            <strong>Decision support only.</strong> FaultIQ doesn't control equipment and is not a substitute for a
            qualified HVAC technician. Model results are inferences, not confirmed root causes.
          </p>
          <p className="mt-1">
            Free and open source under the MIT License · API {health.data?.api_version ?? "…"}
            {health.isError && <span className="text-red-700"> · API unreachable</span>}
          </p>
        </div>
      </footer>
    </div>
  );
}
