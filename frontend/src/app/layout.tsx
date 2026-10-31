import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Masuk — BAYLab AI",
  description: "Ruang riset formulasi BAYLab AI. Mulai dari rasa ingin tahu, lanjutkan dengan sains."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="id"><body>{children}</body></html>;
}
