"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useState } from "react";
const DirtyContext = createContext<(dirty: boolean) => void>(() => {});
export const useWorkspaceDirty = () => useContext(DirtyContext);
export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    router = useRouter();
  const [dirty, setDirty] = useState(false);
  const navigate = (event: React.MouseEvent, href: string) => {
    if (dirty) {
      event.preventDefault();
      if (confirm("저장하지 않은 변경사항을 버리고 메뉴를 이동할까요?")) {
        setDirty(false);
        router.push(href);
      }
    }
  };
  return (
    <DirtyContext.Provider value={setDirty}>
      <header className="site-header">
        <Link
          className="brand"
          href="/events"
          onClick={(e) => navigate(e, "/events")}
        >
          <span className="brand-icon">▦</span>
          <b>BPMC</b>
          <span className="brand-divider" />
          통합 지출 관리
        </Link>
        <span className="local-badge">
          <i /> 개인 작업 공간
        </span>
      </header>
      <aside className="sidebar">
        <p className="eyebrow">WORKSPACE</p>
        <nav aria-label="주 메뉴">
          {[
            ["/events", "행사비", "▤"],
            ["/ordinary", "경상비", "▦"],
            ["/b", "B", "⇄"],
          ].map(([href, label, icon]) => (
            <Link
              key={href}
              href={href}
              onClick={(e) => navigate(e, href)}
              aria-current={
                path === href || (href === "/events" && path === "/")
                  ? "page"
                  : undefined
              }
              className={
                path === href || (href === "/events" && path === "/")
                  ? "active"
                  : ""
              }
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>
        <p className="sidebar-note">
          영수증에서 장부까지
          <br />
          검토하고, 확정하고, 보관하세요.
        </p>
      </aside>
      <div className="app-content">{children}</div>
    </DirtyContext.Provider>
  );
}
