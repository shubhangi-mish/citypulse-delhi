import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";
import "mapbox-gl/dist/mapbox-gl.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });
const display = Instrument_Serif({ subsets: ["latin"], weight: "400", variable: "--font-display-serif" });

export const metadata: Metadata = {
  title: { default: "CityPulse Delhi", template: "%s · CityPulse Delhi" },
  description: "See what's happening around you in Delhi, report issues, coordinate with neighbours — connected by a city graph.",
};

export const viewport: Viewport = { themeColor: "#172B45", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${geist.variable} ${geistMono.variable} ${display.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
