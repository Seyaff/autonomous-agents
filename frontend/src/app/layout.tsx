import type { Metadata, Viewport } from "next";
import { siteUrl } from "@/lib/site";
import { JsonLd } from "@/components/seo/json-ld";
import { Analytics } from "@vercel/analytics/next";
import { Familjen_Grotesk, Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/components/providers/query-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import AuthProvider from "@/components/providers/auth-provider";

const fontDisplay = Familjen_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const fontBody = Hanken_Grotesk({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const fontMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: "Siyaf: AI WhatsApp ordering for restaurants",
    template: "%s · Siyaf",
  },
  description: "AI that answers your restaurant's WhatsApp and takes orders.",
  manifest: "/site.webmanifest",
  openGraph: {
    siteName: "Siyaf",
    locale: "en_PK",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

const organization = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Siyaf",
  url: siteUrl(),
  logo: `${siteUrl()}/brand/logo-light-1024.png`,
};

export const viewport: Viewport = {
  themeColor: "#0b0b0c",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontBody.variable} ${fontMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <JsonLd data={organization} />
        <QueryProvider>
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            <AuthProvider>
              <TooltipProvider>
                {children}
                <Analytics />
                <Toaster />
              </TooltipProvider>
            </AuthProvider>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}