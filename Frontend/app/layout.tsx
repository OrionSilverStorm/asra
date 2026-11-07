/**
 * Root layout: wraps every page in the app.
 *
 * Responsibilities:
 * - load the two fonts and expose them as CSS variables
 * - apply the saved theme before first paint (no light flash)
 * - set the page <title>/<meta description>
 * - render the site header and footer around the page content
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

// next/font downloads the fonts at build time and self-hosts them (no
// request to Google at runtime). Each one exposes a CSS variable that
// globals.css maps to Tailwind's font-sans / font-mono.

/** Body text and headings (research portals use sans throughout). */
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

/** Sequences, IDs, numbers. */
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

/** Shown in the browser tab and in link previews. */
export const metadata: Metadata = {
  title: "ASRA · Across-Species Risk Assessment",
  description:
    "Compare human and animal biology across sequence, localisation, cell-type and tissue expression before choosing an animal model.",
};

// LayoutProps<"/"> is a type Next.js generates for this route.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // Attach the font variables so any element can use them.
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      // The inline script below may add data-theme before React hydrates;
      // this tells React to keep the DOM's value instead of warning.
      suppressHydrationWarning
    >
      <head>
        {/* Runs synchronously during parsing, before the first paint. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      {/* Flex column: header, growing main, footer pinned to the bottom. */}
      <body className="flex min-h-full flex-col">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
