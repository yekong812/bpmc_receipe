import { EventData } from "./api";
export type BudgetItem = {
  id: number;
  book_id?: number;
  parent_id: number | null;
  level: number;
  name: string;
  budget_krw: number;
  detail: string;
  sort_order: number;
  is_active: boolean;
  category_id?: number | null;
  path?: string;
  spent_krw?: number;
  draft_spent_krw?: number;
  remaining_krw?: number;
  ratio?: number | null;
};
export type Entry = {
  id?: number;
  book_id?: number;
  expense_id?: number;
  transaction_date: string | null;
  budget_item_id: number | null;
  description: string;
  income_krw: number | null;
  expense_krw: number | null;
  entry_type: "income" | "expense" | "carryover" | "cashback";
  review_status: string;
  sort_order: number;
  note: string;
  source_type?: string;
};
export type Totals = {
  income_krw: number;
  expense_krw: number;
  balance_krw: number;
  carryover_krw: number;
  income_excluding_carryover_krw: number;
};
export type Book = {
  id: number;
  kind: "ordinary" | "b";
  year: number;
  owner_event_id: number;
  name: string;
  status: string;
  version: number;
  latest_final_version: number;
  updated_at: string;
  budget: BudgetItem[];
  entries: Entry[];
  totals: Totals;
  draft_totals: Totals;
  total_budget_krw: number;
  owner: EventData;
};
export const budgetPayload = (items: BudgetItem[]) =>
  items.map(
    ({
      id,
      parent_id,
      level,
      name,
      budget_krw,
      detail,
      sort_order,
      is_active,
    }) => ({
      id,
      parent_id,
      level,
      name,
      budget_krw,
      detail,
      sort_order,
      is_active,
    }),
  );
export const entryPayload = (items: Entry[]) =>
  items.map(
    ({
      id,
      transaction_date,
      budget_item_id,
      description,
      income_krw,
      expense_krw,
      entry_type,
      review_status,
      sort_order,
      note,
    }) => ({
      id: id && id > 0 ? id : undefined,
      transaction_date,
      budget_item_id,
      description,
      income_krw,
      expense_krw,
      entry_type,
      review_status,
      sort_order,
      note,
    }),
  );
