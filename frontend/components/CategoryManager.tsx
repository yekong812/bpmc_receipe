"use client";
import { useState, useEffect } from "react";
import { api, Category, EventData } from "../lib/api";

export default function CategoryManager({
  event,
  events,
  refresh,
  action,
  busy,
  onDirtyChange,
}: {
  event: EventData;
  events: EventData[];
  refresh: () => Promise<void>;
  action: (fn: () => Promise<void>) => Promise<void>;
  busy: boolean;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [name, setName] = useState(""),
    [color, setColor] = useState("#dbeafe"),
    [source, setSource] = useState("");
  const [drafts, setDrafts] = useState<Record<number, Category>>({});
  const [move, setMove] = useState<Record<number, string>>({});
  const pending =
    !!name.trim() ||
    Object.values(drafts).some(
      (d) =>
        JSON.stringify(d) !==
        JSON.stringify(event.categories.find((c) => c.id === d.id)),
    );
  useEffect(() => {
    onDirtyChange(pending);
  }, [pending, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  const change = (c: Category, key: keyof Category, value: unknown) =>
    setDrafts({ ...drafts, [c.id]: { ...(drafts[c.id] || c), [key]: value } });
  const patch = async (c: Category) => {
    await api(`/categories/${c.id}`, "PATCH", c);
    setDrafts((old) => {
      const next = { ...old };
      delete next[c.id];
      return next;
    });
    await refresh();
  };
  return (
    <div className="category-section">
      <div className="section-title">
        <h3>행사별 항목 설정</h3>
        <p className="muted">
          항목 이름을 바꿔도 기존 지출 연결은 유지됩니다. 사용 중인 항목은
          이동하거나 비활성화하세요.
        </p>
      </div>
      <div className="toolbar">
        <form
          className="actions"
          onSubmit={(e) => {
            e.preventDefault();
            action(async () => {
              await api(`/events/${event.id}/categories`, "POST", {
                name,
                color,
                sort_order: event.categories.length,
              });
              setName("");
              await refresh();
            });
          }}
        >
          <input
            aria-label="새 항목명"
            required
            maxLength={80}
            placeholder="새 항목명"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            aria-label="새 항목 색상"
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
          />
          <button disabled={busy}>＋ 항목 추가</button>
          <button
            type="button"
            disabled={!pending}
            onClick={() => {
              setDrafts({});
              setName("");
            }}
          >
            입력 취소
          </button>
        </form>
        <div className="actions">
          <select
            aria-label="항목 복사할 행사"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">다른 행사 선택</option>
            {events
              .filter((e) => e.id !== event.id)
              .map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
          </select>
          <button
            disabled={!source || busy}
            onClick={() =>
              action(async () => {
                await api(`/events/${event.id}/categories/copy`, "POST", {
                  source_event_id: Number(source),
                });
                await refresh();
              })
            }
          >
            항목 복사
          </button>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>순서</th>
              <th>항목명</th>
              <th>표시색</th>
              <th>사용 여부</th>
              <th>지출건수</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {event.categories.map((c) => {
              const d = drafts[c.id] || c;
              const used = event.expenses.filter(
                (e) => e.category_id === c.id,
              ).length;
              return (
                <tr key={c.id}>
                  <td>
                    <input
                      className="order-input"
                      type="number"
                      aria-label={`${c.name} 순서`}
                      value={d.sort_order}
                      onChange={(e) =>
                        change(c, "sort_order", Number(e.target.value))
                      }
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`${c.name} 이름`}
                      value={d.name}
                      maxLength={80}
                      onChange={(e) => change(c, "name", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`${c.name} 색상`}
                      type="color"
                      value={d.color}
                      onChange={(e) => change(c, "color", e.target.value)}
                    />
                  </td>
                  <td>
                    <label className="actions">
                      <input
                        type="checkbox"
                        checked={d.is_active}
                        onChange={(e) =>
                          change(c, "is_active", e.target.checked)
                        }
                      />
                      {d.is_active ? "사용" : "비활성"}
                    </label>
                  </td>
                  <td>{used}건</td>
                  <td>
                    <div className="actions">
                      <button
                        disabled={busy || !drafts[c.id]}
                        onClick={() => action(() => patch(d))}
                      >
                        저장
                      </button>
                      {used > 0 && (
                        <select
                          aria-label={`${c.name} 이동 대상`}
                          value={move[c.id] || ""}
                          onChange={(e) =>
                            setMove({ ...move, [c.id]: e.target.value })
                          }
                        >
                          <option value="">이동 대상 선택</option>
                          {event.categories
                            .filter((x) => x.id !== c.id && x.is_active)
                            .map((x) => (
                              <option value={x.id} key={x.id}>
                                {x.name}
                              </option>
                            ))}
                        </select>
                      )}
                      <button
                        className="danger"
                        disabled={busy || (used > 0 && !move[c.id])}
                        onClick={() => {
                          if (
                            confirm(
                              `“${c.name}” 항목을 삭제할까요?${used ? " 연결된 지출은 선택한 항목으로 이동합니다." : ""}`,
                            )
                          )
                            action(async () => {
                              await api(
                                `/categories/${c.id}${move[c.id] ? `?move_to=${move[c.id]}` : ""}`,
                                "DELETE",
                              );
                              setDrafts({});
                              await refresh();
                            });
                        }}
                      >
                        {used ? "이동 후 삭제" : "삭제"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
