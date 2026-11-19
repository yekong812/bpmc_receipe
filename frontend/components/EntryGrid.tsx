"use client";
import { useState } from "react";
import { Book, Entry } from "../lib/annual";
import { won } from "../lib/api";
import { useSessionFilters } from "../lib/useSessionFilters";
import WonInput from "./WonInput";

const emptyFilters = {
  month: "",
  section: "",
  leafFilter: "",
  receiptFilter: "",
  reviewFilter: "",
  query: "",
};

export default function EntryGrid({
  book,
  rows,
  setRows,
  locked,
  onReceipt,
}: {
  book: Book;
  rows: Entry[];
  setRows: (rows: Entry[]) => void;
  locked: boolean;
  onReceipt: (id: number) => void;
}) {
  const [filters, setFilters] = useSessionFilters(
    `entries:${book.kind}:${book.year}:${book.id}`,
    emptyFilters,
  );
  const { month, section, leafFilter, receiptFilter, reviewFilter, query } =
    filters;
  const [selected, setSelected] = useState<number[]>([]),
    [focus, setFocus] = useState<number | null>(null),
    [sections, setSections] = useState<Record<string, string>>({});
  const ordinary = book.kind === "ordinary",
    leaves = book.budget.filter((b) => b.level === 3),
    parents = book.budget.filter((b) => b.level === 2);
  const update = (index: number, patch: Partial<Entry>) =>
    setRows(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  const links = (r: Entry) =>
    book.owner.links.filter((l) => l.expense_id === r.expense_id);
  const filtered = rows
    .map((row, index) => ({ row, index }))
    .filter(
      ({ row }) =>
        (!month ||
          !row.transaction_date ||
          row.transaction_date.slice(5, 7) === month) &&
        (!section ||
          leaves.find((l) => l.id === row.budget_item_id)?.parent_id ===
            Number(section)) &&
        (!leafFilter || row.budget_item_id === Number(leafFilter)) &&
        (!receiptFilter ||
          (receiptFilter === "linked"
            ? links(row).length > 0
            : links(row).length === 0)) &&
        (!reviewFilter || row.review_status === reviewFilter) &&
        (!query || row.description.toLowerCase().includes(query.toLowerCase())),
    );
  const totalIncome = filtered.reduce(
      (s, { row }) => s + (row.income_krw || 0),
      0,
    ),
    totalExpense = filtered.reduce(
      (s, { row }) => s + (row.expense_krw || 0),
      0,
    );
  const allVisibleChecked =
    filtered.length > 0 &&
    selected.length === filtered.length &&
    filtered.every(({ index }) => selected.includes(index));
  return (
    <>
      <div className="toolbar">
        <div className="actions wrap">
          <button
            className="primary"
            disabled={locked}
            onClick={() => {
              setRows([
                ...rows,
                {
                  transaction_date: `${book.year}-01-01`,
                  budget_item_id: null,
                  description: "",
                  income_krw: 0,
                  expense_krw: 0,
                  entry_type: "expense",
                  review_status: "확인됨",
                  sort_order: rows.length,
                  note: "",
                },
              ]);
              setFocus(rows.length);
            }}
          >
            ＋ 거래 추가
          </button>
          <button
            className="delete-action"
            disabled={locked || !selected.length}
            onClick={() => {
              if (
                confirm(
                  "선택한 거래를 삭제할까요? 저장 시 영수증 연결도 해제되고 변경 이력에 남습니다.",
                )
              ) {
                setRows(rows.filter((_, i) => !selected.includes(i)));
                setSelected([]);
                setFocus(null);
              }
            }}
          >
            선택 삭제 {selected.length || ""}
          </button>
        </div>
        <span className="small muted">
          조회 {filtered.length}건 · 수입 ₩ {won(totalIncome)} / 지출 ₩{" "}
          {won(totalExpense)} / 차액 ₩ {won(totalIncome - totalExpense)}
        </span>
      </div>
      <div className="filters ledger-filters">
        <input
          aria-label="거래 내용 검색"
          value={query}
          placeholder="내용 검색"
          onChange={(e) => setFilters({ ...filters, query: e.target.value })}
        />
        <select
          aria-label="거래 월 필터"
          value={month}
          onChange={(e) => setFilters({ ...filters, month: e.target.value })}
        >
          <option value="">전체 월</option>
          {Array.from({ length: 12 }, (_, i) => (
            <option key={i} value={String(i + 1).padStart(2, "0")}>
              {i + 1}월
            </option>
          ))}
        </select>
        {ordinary && (
          <>
            <select
              aria-label="항 필터"
              value={section}
              onChange={(e) =>
                setFilters({
                  ...filters,
                  section: e.target.value,
                  leafFilter: "",
                })
              }
            >
              <option value="">모든 항</option>
              {parents.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              aria-label="목 필터"
              value={leafFilter}
              onChange={(e) =>
                setFilters({ ...filters, leafFilter: e.target.value })
              }
            >
              <option value="">모든 목</option>
              {leaves
                .filter((l) => !section || l.parent_id === Number(section))
                .map((l) => (
                  <option value={l.id} key={l.id}>
                    {l.name}
                  </option>
                ))}
            </select>
          </>
        )}
        <select
          aria-label="영수증 연결 필터"
          value={receiptFilter}
          onChange={(e) =>
            setFilters({ ...filters, receiptFilter: e.target.value })
          }
        >
          <option value="">영수증 전체</option>
          <option value="linked">연결됨</option>
          <option value="unlinked">미연결</option>
        </select>
        <select
          aria-label="거래 검토 필터"
          value={reviewFilter}
          onChange={(e) =>
            setFilters({ ...filters, reviewFilter: e.target.value })
          }
        >
          <option value="">검토 상태 전체</option>
          <option>확인됨</option>
          <option>검토 필요</option>
        </select>
        <button
          className="text-button"
          onClick={() => setFilters(emptyFilters)}
        >
          초기화
        </button>
      </div>
      <fieldset disabled={locked} className="grid-fieldset">
        <div className="table-scroll annual-table">
          <table className="annual-entry-table">
            <thead>
              <tr>
                <th>
                  <input
                    aria-label="거래 전체 선택"
                    type="checkbox"
                    disabled={!filtered.length}
                    checked={allVisibleChecked}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? filtered.map(({ index }) => index)
                          : [],
                      )
                    }
                  />
                </th>
                <th scope="col">No.</th>
                <th>날짜</th>
                {ordinary && (
                  <>
                    <th>항</th>
                    <th>목</th>
                  </>
                )}
                <th>내용</th>
                <th className="numeric">수입</th>
                <th className="numeric">지출</th>
                <th>영수증번호</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(({ row: r, index: i }) => {
                const leaf = leaves.find((l) => l.id === r.budget_item_id),
                  chosen =
                    sections[r.id || `new-${i}`] ??
                    String(leaf?.parent_id || "");
                return (
                  <tr
                    key={r.id || `new-${i}`}
                    className={focus === i ? "selected" : ""}
                    onClick={() => setFocus(i)}
                  >
                    <td>
                      <input
                        aria-label={`${i + 1}거래 선택`}
                        type="checkbox"
                        checked={selected.includes(i)}
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? [...selected, i]
                              : selected.filter((n) => n !== i),
                          )
                        }
                      />
                    </td>
                    <td>{i + 1}</td>
                    <td>
                      <input
                        aria-label={`${i + 1}거래 날짜`}
                        type="date"
                        min={`${book.year}-01-01`}
                        max={`${book.year}-12-31`}
                        value={r.transaction_date || ""}
                        onChange={(e) =>
                          update(i, {
                            transaction_date: e.target.value || null,
                          })
                        }
                      />
                    </td>
                    {ordinary && (
                      <>
                        <td>
                          <select
                            aria-label={`${i + 1}거래 항`}
                            value={chosen}
                            onChange={(e) => {
                              setSections({
                                ...sections,
                                [r.id || `new-${i}`]: e.target.value,
                              });
                              update(i, { budget_item_id: null });
                            }}
                          >
                            <option value="">항 선택</option>
                            {parents
                              .filter(
                                (p) => p.is_active || p.id === leaf?.parent_id,
                              )
                              .map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.name}
                                </option>
                              ))}
                          </select>
                        </td>
                        <td>
                          <select
                            aria-label={`${i + 1}거래 목`}
                            value={r.budget_item_id || ""}
                            onChange={(e) =>
                              update(i, {
                                budget_item_id: e.target.value
                                  ? Number(e.target.value)
                                  : null,
                              })
                            }
                          >
                            <option value="">목 선택</option>
                            {leaves
                              .filter(
                                (l) =>
                                  l.parent_id === Number(chosen) &&
                                  (l.is_active || l.id === r.budget_item_id),
                              )
                              .map((l) => (
                                <option value={l.id} key={l.id}>
                                  {l.name}
                                  {l.is_active ? "" : " (비활성)"}
                                </option>
                              ))}
                          </select>
                        </td>
                      </>
                    )}
                    <td>
                      <input
                        aria-label={`${i + 1}거래 내용`}
                        maxLength={500}
                        placeholder="거래 내용"
                        value={r.description}
                        onChange={(e) =>
                          update(i, { description: e.target.value })
                        }
                      />
                      <small className="muted">
                        {r.entry_type === "carryover"
                          ? "이월금"
                          : r.entry_type === "cashback"
                            ? "캐시백"
                            : ""}
                        {r.review_status === "검토 필요" ? " · 검토 필요" : ""}
                        {r.note.includes("[임시 분류: 기타]") &&
                          " · 임시 분류: 기타"}
                      </small>
                    </td>
                    <td>
                      <WonInput
                        label={`${i + 1}거래 수입`}
                        value={r.income_krw}
                        onChange={(n) => {
                          update(i, {
                            income_krw: n,
                            ...(n
                              ? {
                                  expense_krw: 0,
                                  entry_type:
                                    r.entry_type === "carryover" ||
                                    r.entry_type === "cashback"
                                      ? r.entry_type
                                      : "income",
                                }
                              : {}),
                          });
                        }}
                      />
                    </td>
                    <td>
                      <WonInput
                        label={`${i + 1}거래 지출`}
                        value={r.expense_krw}
                        onChange={(n) => {
                          update(i, {
                            expense_krw: n,
                            ...(n
                              ? { income_krw: 0, entry_type: "expense" }
                              : {}),
                          });
                        }}
                      />
                    </td>
                    <td>
                      {links(r).map((l) => {
                        const index = book.owner.receipts.findIndex(
                          (x) => x.id === l.receipt_id,
                        );
                        const receipt = book.owner.receipts[index];
                        if (!receipt) return null;
                        return (
                          <a
                            key={l.receipt_id}
                            className="text-button"
                            href={`/api/receipts/${receipt.id}/image`}
                            aria-haspopup="dialog"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              onReceipt(receipt.id);
                            }}
                          >
                            #{receipt.receipt_number || index + 1}
                          </a>
                        );
                      })}
                      {!links(r).length && (
                        <span className="muted small">미연결</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="empty">
              <h3>조회된 거래가 없습니다.</h3>
              <p>거래를 추가하거나 영수증을 분석해 초안을 만드세요.</p>
            </div>
          )}
        </div>
        {focus !== null && rows[focus] && (
          <div className="entry-detail">
            <strong>#{focus + 1} 거래 검토</strong>
            <label>
              거래유형
              <select
                aria-label="선택 거래유형"
                value={rows[focus].entry_type}
                onChange={(e) => {
                  const type = e.target.value as Entry["entry_type"];
                  update(focus, {
                    entry_type: type,
                    ...(type === "expense"
                      ? {}
                      : {
                          income_krw:
                            rows[focus].income_krw || rows[focus].expense_krw,
                          expense_krw: 0,
                        }),
                  });
                }}
              >
                <option value="expense">지출</option>
                <option value="income">일반 수입</option>
                <option value="carryover">이월금</option>
                <option value="cashback">캐시백</option>
              </select>
            </label>
            <label className="check-label">
              <input
                aria-label="선택 거래 검토 완료"
                type="checkbox"
                checked={rows[focus].review_status === "확인됨"}
                onChange={(e) =>
                  update(focus, {
                    review_status: e.target.checked ? "확인됨" : "검토 필요",
                  })
                }
              />
              검토 완료
            </label>
            <label className="entry-note">
              영수증 없음/차액 사유
              <input
                aria-label="선택 거래 메모"
                maxLength={2000}
                placeholder="사유 또는 메모"
                value={rows[focus].note}
                onChange={(e) => update(focus, { note: e.target.value })}
              />
            </label>
            <span className="small muted">
              출처: {rows[focus].source_type || "manual"}
            </span>
          </div>
        )}
      </fieldset>
    </>
  );
}
