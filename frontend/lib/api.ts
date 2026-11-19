export type Category = {
  id: number;
  event_id: number;
  name: string;
  color: string;
  sort_order: number;
  is_active: boolean;
};
export type Expense = {
  id?: number;
  category_id: number | null;
  expense_date: string | null;
  item_name: string;
  amount_krw: number | null;
  vendor: string;
  purchased: boolean;
  sort_order: number;
  note: string;
  source_type?: string;
  review_status?: string;
};
export type Receipt = {
  id: number;
  original_name: string;
  receipt_number?: number | null;
  transaction_at: string | null;
  merchant: string;
  description: string;
  final_amount_krw: number | null;
  ocr_status: string;
  review_reason: string;
  ocr_text: string;
};
export type Link = {
  expense_id: number;
  receipt_id: number;
  allocated_amount_krw: number | null;
};
export type EventData = {
  created_at?: string;
  id: number;
  name: string;
  event_date: string;
  latest_final_version: number;
  draft_total_krw?: number;
  start_date: string;
  end_date: string;
  status: string;
  version: number;
  total_krw: number;
  expense_count: number;
  matched_count: number;
  receipt_count: number;
  categories: Category[];
  expenses: Expense[];
  receipts: Receipt[];
  links: Link[];
};
export type Preview = {
  job_id: string;
  rows: (Expense & { category_name: string; source_row: number })[];
  errors: { row: number; message: string }[];
  warnings: string[];
  needs_mapping: boolean;
  sample: string[][];
  new_categories: string[];
};
export const won = (n: number | null | undefined) =>
  new Intl.NumberFormat("ko-KR").format(n ?? 0);
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const form = data instanceof FormData;
  const res = await fetch(`/api${path}`, {
    method,
    headers: data && !form ? { "Content-Type": "application/json" } : undefined,
    body: data ? (form ? data : JSON.stringify(data)) : undefined,
  });
  if (!res.ok) {
    const error = await res
      .json()
      .catch(() => ({ detail: "요청을 처리하지 못했습니다." }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : "입력값을 확인하세요.",
    );
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
export async function download(path: string, name: string) {
  const r = await fetch(`/api${path}`);
  if (!r.ok) {
    const e = await r.json();
    throw new Error(e.detail);
  }
  const u = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  URL.revokeObjectURL(u);
}
