"use client";
import { useState } from "react";
import { BudgetItem } from "../lib/annual";
import { won } from "../lib/api";
export default function BudgetEditor({
  items,
  setItems,
  year,
  locked,
}: {
  items: BudgetItem[];
  setItems: (v: BudgetItem[]) => void;
  year: number;
  locked: boolean;
}) {
  const [level, setLevel] = useState(1),
    [parent, setParent] = useState(""),
    [name, setName] = useState("");
  const update = (id: number, key: keyof BudgetItem, value: unknown) =>
    setItems(items.map((x) => (x.id === id ? { ...x, [key]: value } : x)));
  const map = new Map(items.map((x) => [x.id, x]));
  const leaves = items.filter((x) => x.level === 3);
  const spent = leaves.reduce((s, x) => s + (x.spent_krw || 0), 0),
    total = leaves.reduce((s, x) => s + x.budget_krw, 0);
  const sections = items.filter((x) => x.level === 2);
  return (
    <fieldset disabled={locked} className="grid-fieldset">
      <div className="section-title">
        <h3>{year}년 예산 현황</h3>
        <p className="muted small">
          실지출은 최신 확정 거래만 반영합니다. 편집 중 지출은 별도로
          표시합니다. 관·항·목은 이 연도에서만 사용합니다.
        </p>
      </div>
      <form
        className="toolbar budget-create"
        onSubmit={(e) => {
          e.preventDefault();
          if (level !== 1 && !parent) return;
          setItems([
            ...items,
            {
              id: Math.min(0, ...items.map((x) => x.id)) - 1,
              parent_id: level === 1 ? null : Number(parent),
              level,
              name: name.trim(),
              budget_krw: 0,
              detail: "",
              sort_order: items.length,
              is_active: true,
            },
          ]);
          setName("");
        }}
      >
        <div className="actions wrap">
          <select
            aria-label="새 예산 레벨"
            value={level}
            onChange={(e) => {
              setLevel(Number(e.target.value));
              setParent("");
            }}
          >
            <option value={1}>관</option>
            <option value={2}>항</option>
            <option value={3}>목</option>
          </select>
          {level !== 1 && (
            <select
              aria-label="상위 예산 항목"
              required
              value={parent}
              onChange={(e) => setParent(e.target.value)}
            >
              <option value="">상위 {level === 2 ? "관" : "항"} 선택</option>
              {items
                .filter((x) => x.level === level - 1 && x.is_active)
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.level === 2 ? `${map.get(x.parent_id!)?.name} / ` : ""}
                    {x.name}
                  </option>
                ))}
            </select>
          )}
          <input
            aria-label="새 예산 항목명"
            required
            maxLength={80}
            placeholder="항목명 입력"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button>＋ 예산 항목 추가</button>
        </div>
      </form>
      <details className="hierarchy-manager">
        <summary>
          관·항 계층 관리 ({items.filter((i) => i.level !== 3).length}개)
        </summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>레벨</th>
                <th>상위</th>
                <th>명칭</th>
                <th>순서</th>
                <th>사용</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {items
                .filter((x) => x.level !== 3)
                .map((x) => (
                  <tr key={x.id}>
                    <td>{x.level === 1 ? "관" : "항"}</td>
                    <td>
                      {x.level === 2 ? (
                        <select
                          aria-label={`${x.name} 상위 관`}
                          value={x.parent_id || ""}
                          onChange={(e) =>
                            update(x.id, "parent_id", Number(e.target.value))
                          }
                        >
                          {items
                            .filter((p) => p.level === 1)
                            .map((p) => (
                              <option value={p.id} key={p.id}>
                                {p.name}
                              </option>
                            ))}
                        </select>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <input
                        aria-label={`${x.name} 명칭`}
                        maxLength={80}
                        value={x.name}
                        onChange={(e) => update(x.id, "name", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${x.name} 순서`}
                        className="order-input"
                        type="number"
                        value={x.sort_order}
                        onChange={(e) =>
                          update(x.id, "sort_order", Number(e.target.value))
                        }
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${x.name} 사용`}
                        type="checkbox"
                        checked={x.is_active}
                        onChange={(e) =>
                          update(x.id, "is_active", e.target.checked)
                        }
                      />
                    </td>
                    <td>
                      <button
                        disabled={items.some((i) => i.parent_id === x.id)}
                        onClick={() => {
                          if (confirm("사용하지 않는 계층 항목을 삭제할까요?"))
                            setItems(items.filter((i) => i.id !== x.id));
                        }}
                      >
                        삭제
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
      <div className="table-scroll annual-table">
        <table>
          <thead>
            <tr>
              <th>관</th>
              <th>항</th>
              <th>목</th>
              <th className="numeric">{year} 예산</th>
              <th>세부내용</th>
              <th className="numeric">확정 실지출</th>
              <th className="numeric">잔액</th>
              <th className="numeric">비율</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((section) => {
              const rows = leaves.filter((l) => l.parent_id === section.id),
                subtotal = rows.reduce((a, x) => a + x.budget_krw, 0),
                actual = rows.reduce((a, x) => a + (x.spent_krw || 0), 0);
              return (
                <SectionRows
                  key={section.id}
                  section={section}
                  rows={rows}
                  map={map}
                  update={update}
                  remove={(id) => {
                    if (
                      confirm(
                        "사용하지 않는 목을 삭제할까요? 사용 중이면 저장 시 차단됩니다.",
                      )
                    )
                      setItems(items.filter((x) => x.id !== id));
                  }}
                  subtotal={subtotal}
                  actual={actual}
                />
              );
            })}
            <tr className="sum-row">
              <th colSpan={3}>합계</th>
              <td className="numeric">₩ {won(total)}</td>
              <td />
              <td className="numeric">₩ {won(spent)}</td>
              <td className="numeric">₩ {won(total - spent)}</td>
              <td className="numeric">
                {total ? `${((spent / total) * 100).toFixed(1)}%` : "—"}
              </td>
              <td />
            </tr>
          </tbody>
        </table>
        {!leaves.length && (
          <div className="empty">
            <h3>이 연도의 예산 항목이 없습니다.</h3>
            <p>관 → 항 → 목 순서로 만들거나 예산 Excel을 가져오세요.</p>
          </div>
        )}
      </div>
    </fieldset>
  );
}
function SectionRows({
  section,
  rows,
  map,
  update,
  remove,
  subtotal,
  actual,
}: {
  section: BudgetItem;
  rows: BudgetItem[];
  map: Map<number, BudgetItem>;
  update: (id: number, key: keyof BudgetItem, value: unknown) => void;
  remove: (id: number) => void;
  subtotal: number;
  actual: number;
}) {
  return (
    <>
      {rows.map((x) => (
        <tr key={x.id}>
          <td>{map.get(section.parent_id!)?.name}</td>
          <td>{section.name}</td>
          <td>
            <input
              aria-label={`${x.name} 목 이름`}
              value={x.name}
              maxLength={80}
              onChange={(e) => update(x.id, "name", e.target.value)}
            />
          </td>
          <td>
            <input
              aria-label={`${x.name} 예산`}
              type="number"
              min="0"
              step="1"
              value={x.budget_krw}
              onChange={(e) =>
                update(x.id, "budget_krw", Number(e.target.value))
              }
            />
          </td>
          <td>
            <input
              aria-label={`${x.name} 세부내용`}
              value={x.detail}
              onChange={(e) => update(x.id, "detail", e.target.value)}
            />
          </td>
          <td className="numeric">
            ₩ {won(x.spent_krw)}
            <small className="draft-amount">
              편집 중 {won(x.draft_spent_krw)}
            </small>
          </td>
          <td
            className={`numeric ${x.budget_krw < (x.spent_krw || 0) ? "warning-text" : ""}`}
          >
            ₩ {won(x.budget_krw - (x.spent_krw || 0))}
          </td>
          <td className="numeric">
            {x.budget_krw
              ? `${(((x.spent_krw || 0) / x.budget_krw) * 100).toFixed(1)}%`
              : "—"}
          </td>
          <td>
            <label className="small actions">
              <input
                aria-label={`${x.name} 사용`}
                type="checkbox"
                checked={x.is_active}
                onChange={(e) => update(x.id, "is_active", e.target.checked)}
              />
              사용
            </label>
            <button className="text-button danger" onClick={() => remove(x.id)}>
              삭제
            </button>
          </td>
        </tr>
      ))}
      <tr className="subtotal-row">
        <th colSpan={3}>{section.name} 소계</th>
        <td className="numeric">₩ {won(subtotal)}</td>
        <td />
        <td className="numeric">₩ {won(actual)}</td>
        <td className="numeric">₩ {won(subtotal - actual)}</td>
        <td />
        <td />
      </tr>
    </>
  );
}
