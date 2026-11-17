export const today = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
export const statusClass = (s: string) =>
  s === "최종 확정" ? "done" : s === "검토중" ? "review" : "draft";
