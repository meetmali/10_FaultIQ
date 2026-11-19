/* eslint-disable react-refresh/only-export-components -- route table: lazy pages and the router
   factory live together on purpose; this file has no state for Fast Refresh to keep. */
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Link } from "react-router";

import { Loading } from "../components/QueryState";
import { Layout } from "./Layout";

// Each screen loads lazily, so the first page stays small (ADR 0008).
const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const DiagnosticsPage = lazy(() => import("../pages/DiagnosticsPage"));
const LibraryPage = lazy(() => import("../pages/LibraryPage"));
const LibraryEntryPage = lazy(() => import("../pages/LibraryEntryPage"));

const page = (el: ReactNode) => <Suspense fallback={<Loading />}>{el}</Suspense>;

function NotFound() {
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-slate-600">
        That page doesn't exist. <Link to="/" className="text-sky-800 underline">Go to the dashboard</Link>.
      </p>
    </div>
  );
}

export const routes = [
  {
    element: <Layout />,
    children: [
      { index: true, element: page(<DashboardPage />) },
      { path: "equipment/:equipmentId", element: page(<DiagnosticsPage />) },
      { path: "library", element: page(<LibraryPage />) },
      { path: "library/:faultId", element: page(<LibraryEntryPage />) },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
