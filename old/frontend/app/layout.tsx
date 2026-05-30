import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Product Recommender",
  description: "Production-grade RAG product recommender",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
