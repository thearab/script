import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Ghurfati",
  description: "AI Interior Design with affiliate product matching"
};

const RootLayout = ({ children }: { children: ReactNode }) => {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
};

export default RootLayout;
