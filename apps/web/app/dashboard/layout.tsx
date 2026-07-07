import type { ReactNode } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    // .theme-light gives the app the SAME light skin as the marketing site,
    // so the whole product feels uniform (only the layout differs: sidebar vs top-nav).
    <div className="theme-light min-h-screen bg-mkt-surface">
      <Sidebar />
      <div className="lg:pl-60">{children}</div>
    </div>
  );
}
