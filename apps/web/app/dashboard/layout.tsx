import type { ReactNode } from "react";
import { Sidebar } from "@/components/dashboard/Sidebar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg-base">
      <Sidebar />
      <div className="lg:pl-60">{children}</div>
    </div>
  );
}
