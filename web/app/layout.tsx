import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Nav } from "@/components/nav";
import "./globals.css";

const geist = localFont({ src: "./fonts/Geist-Variable.woff2", variable: "--font-geist", display: "swap", weight: "100 900" });
const geistMono = localFont({ src: "./fonts/GeistMono-Variable.woff2", variable: "--font-geist-mono", display: "swap", weight: "100 900" });
const geistPixel = localFont({ src: "./fonts/GeistPixel-Square.woff2", variable: "--font-geist-pixel", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Red2Fix: try it", template: "%s · Red2Fix" },
  description: "Paste a GitHub pull request and watch Red2Fix prove it: a test that fails on base and passes on the PR, then a review.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0c0c0f" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable} ${geistPixel.variable}`}>
      <body>
        <div className="shell">
          <Nav />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
