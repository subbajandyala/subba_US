import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Subba US Options Analyzer",
  description: "US Options & Stock trading via MooMoo",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden bg-surface text-slate-200">
        <Providers>
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
