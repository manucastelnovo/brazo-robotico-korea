import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HUENIT robot control",
  description: "Local demo: face login and gamepad control for the HUENIT arm",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
