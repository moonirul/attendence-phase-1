import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Betopia Attendance Adapter",
  description: "Manual ERP session and dashboard inspection",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body style={{ margin: 0, fontFamily: "Arial, sans-serif", background: "#f5f7fb" }}>{children}</body></html>;
}
