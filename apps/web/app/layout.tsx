import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "500", "600"],
});

export const metadata = {
  title: "ProductIQ — AI-Powered Product Discovery",
  description:
    "Semantic search meets rating intelligence. Find the perfect product with AI that understands natural language, weighs real reviews, and explains its reasoning.",
  keywords: ["product discovery", "AI recommendations", "semantic search", "product finder"],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${inter.variable} ${mono.variable}`}>
        <body className="antialiased bg-bg-base text-txt-primary font-sans">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
