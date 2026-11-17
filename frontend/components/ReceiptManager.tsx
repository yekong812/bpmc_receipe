"use client";
import { useEffect, useRef, useState } from "react";
import { api, download, EventData, Receipt, won } from "../lib/api";

export default function ReceiptManager({
  event,
  refresh,
  action,
  busy,
  inform,
  onDirtyChange,
}: {
  event: EventData;
  refresh: () => Promise<void>;
  action: (fn: () => Promise<void>) => Promise<void>;
  busy: boolean;
  inform: (s: string) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [selected, setSelected] = useState<number | null>(null),
    [editing, setEditing] = useState<Receipt | null>(null),
    [suggestions, setSuggestions] = useState<
      {
        receipt_id: number;
        candidates: { expense_id: number; score: number }[];
      }[]
    >([]),
    [extractions, setExtractions] = useState<
      {
        id: number;
        analyzed_at: string;
        extracted_json: string;
        model_name: string;
        input_kind: string;
        usage_json: string;
        estimated_cost_usd: string | null;
        error_message: string;
      }[]
    >([]),
    [expense, setExpense] = useState(""),
    [allocated, setAllocated] = useState(""),
    [newCat, setNewCat] = useState(""),
    [job, setJob] = useState<{
      id: string;
      status: string;
      processed: number;
      total: number;
    } | null>(null);
  const [llm, setLlm] = useState<{
    enabled: boolean;
    key_configured: boolean;
    model: string;
    mode: string;
    allow_images: boolean;
  } | null>(null);
  useEffect(() => {
    api<{ llm: NonNullable<typeof llm> }>("/health")
      .then((h) => setLlm(h.llm))
      .catch(() => {});
  }, []);
  const input = useRef<HTMLInputElement>(null);
  const pending =
    !!editing &&
    JSON.stringify(editing) !==
      JSON.stringify(event.receipts.find((r) => r.id === editing.id));
  useEffect(() => {
    onDirtyChange(pending);
  }, [pending, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    api<typeof suggestions>(`/events/${event.id}/receipt-suggestions`)
      .then(setSuggestions)
      .catch(() => {});
  }, [event]);
  useEffect(() => {
    if (selected) {
      const r = event.receipts.find((r) => r.id === selected);
      setEditing(r ? { ...r } : null);
    }
  }, [selected, event]);
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const id = setInterval(async () => {
      try {
        const j = await api<typeof job>(`/jobs/${job.id}`);
        setJob(j);
        if (j.status !== "running") {
          await refresh();
          inform("분석이 끝났습니다. 영수증별 결과를 검토해주세요.");
        }
      } catch (e) {
        setJob(null);
        inform((e as Error).message);
      }
    }, 1500);
    return () => clearInterval(id);
  }, [job?.id, job?.status, refresh, inform]);
  useEffect(() => {
    if (selected)
      api<typeof extractions>(`/receipts/${selected}/extractions`)
        .then(setExtractions)
        .catch(() => setExtractions([]));
  }, [selected, event.version]);
  const analyzing = job?.status === "running";
  function select(r: Receipt) {
    if (
      pending &&
      !confirm("저장하지 않은 영수증 검토값을 버리고 다른 영수증을 열까요?")
    )
      return;
    setSelected(r.id);
    setEditing({ ...r });
    setExpense("");
    setAllocated(String(r.final_amount_krw ?? ""));
  }
  const links = event.links.filter((l) => l.receipt_id === selected);
  return (
    <div>
      {llm && (
        <p className="muted small">
          {llm.enabled
            ? `외부 LLM: ${llm.model} · ${llm.mode} · ${llm.key_configured ? "API 키 설정됨" : "API 키 미설정"}${llm.allow_images ? " · 이미지 외부 전송 허용" : " · 이미지 외부 전송 차단"}`
            : "외부 LLM 꺼짐 · 로컬 OCR 사용"}
        </p>
      )}
      <div className="toolbar">
        <div className="actions">
          <input
            hidden
            ref={input}
            type="file"
            accept=".zip"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f)
                action(async () => {
                  const d = new FormData();
                  d.append("file", f);
                  const r = await api<{
                    uploaded_count: number;
                    duplicate_count: number;
                  }>(`/events/${event.id}/receipts/upload`, "POST", d);
                  await refresh();
                  inform(
                    `${r.uploaded_count}장 업로드 · 중복 ${r.duplicate_count}장 제외`,
                  );
                });
              e.target.value = "";
            }}
          />
          <button
            disabled={busy || analyzing}
            onClick={() => input.current?.click()}
          >
            ↥ 영수증 ZIP 업로드
          </button>
          <button
            disabled={busy || analyzing || !event.receipts.length}
            onClick={() =>
              action(async () => {
                setJob(
                  await api(`/events/${event.id}/receipts/analyze`, "POST"),
                );
              })
            }
          >
            {analyzing
              ? `분석 중 ${job?.processed}/${job?.total}`
              : "◎ 영수증 분석 시작"}
          </button>
        </div>
        <button
          disabled={analyzing || !event.receipts.length}
          onClick={() =>
            action(() =>
              download(
                `/events/${event.id}/receipts/export-zip${event.latest_final_version ? "" : "?draft=true"}`,
                `${event.latest_final_version ? "" : "DRAFT_"}${event.name}_영수증.zip`,
              ),
            )
          }
        >
          ↧ 정리된 ZIP 다운로드
        </button>
      </div>
      <p className="muted small">
        JPG·PNG·WebP / ZIP 최대 50MB, 200장 · 날짜·금액을 확인하고 영수증을
        연결하세요. 분석 후 지출 초안을 자동 생성하며 최종 확정은 사용자만 할 수
        있습니다.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>No.</th>
              <th>원본파일</th>
              <th>거래일시</th>
              <th>상호 / 내역</th>
              <th className="numeric">최종금액</th>
              <th>매칭 지출행</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            {event.receipts.map((r, i) => (
              <tr
                tabIndex={0}
                key={r.id}
                className={
                  selected === r.id ? "selected clickable" : "clickable"
                }
                onClick={() => select(r)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") select(r);
                }}
              >
                <td>{i + 1}</td>
                <td>
                  <strong>{r.original_name}</strong>
                </td>
                <td>
                  {r.transaction_at?.replace("T", " ") || "날짜 확인 필요"}
                </td>
                <td>{r.merchant || "—"}</td>
                <td className="numeric">
                  {r.final_amount_krw === null
                    ? "—"
                    : `₩ ${won(r.final_amount_krw)}`}
                </td>
                <td>
                  {event.links
                    .filter((l) => l.receipt_id === r.id)
                    .map(
                      (l) =>
                        `#${event.expenses.findIndex((e) => e.id === l.expense_id) + 1}`,
                    )
                    .join(", ") || <span className="muted">미연결</span>}
                </td>
                <td>
                  <span
                    className={`badge ${r.ocr_status === "확인됨" ? "done" : "review"}`}
                  >
                    {r.ocr_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!event.receipts.length && (
          <div className="empty">
            <span className="empty-icon">▧</span>
            <h3>영수증을 한 번에 정리하세요</h3>
            <p>
              영수증 사진을 ZIP으로 묶어 업로드하면 검토와 연결을 시작할 수
              있어요.
            </p>
            <button onClick={() => input.current?.click()}>
              ZIP 파일 선택
            </button>
          </div>
        )}
      </div>
      {editing && (
        <div className="receipt-editor">
          <div className="image-preview">
            <h3>
              원본 미리보기 <small>{editing.original_name}</small>
            </h3>
            <a
              href={`/api/receipts/${editing.id}/image`}
              target="_blank"
              rel="noreferrer"
            >
              <img
                src={`/api/receipts/${editing.id}/image`}
                alt={`${editing.original_name} 영수증 원본`}
              />
            </a>
            <details>
              <summary>OCR 추출 텍스트</summary>
              <pre>{editing.ocr_text || "아직 추출된 텍스트가 없습니다."}</pre>
            </details>
          </div>
          <fieldset className="grid-fieldset" disabled={busy || analyzing}>
            <h3>추출값 검토</h3>
            <p className="muted small">
              원본을 확인해 수정한 뒤 저장하세요. 검토 사유를 비우고 날짜·금액을
              입력하면 확인 완료됩니다.
            </p>
            {!!extractions.length && (
              <details className="extraction-comparison">
                <summary>
                  분석 이력·현재 값 비교 ({extractions.length}회)
                </summary>
                {extractions.map((ex) => {
                  const value = JSON.parse(ex.extracted_json);
                  const usage = JSON.parse(ex.usage_json || "{}");
                  return (
                    <div key={ex.id}>
                      <p className="small muted">
                        {ex.analyzed_at} · {ex.model_name} · {ex.input_kind}
                      </p>
                      <p className="small muted">
                        입력 토큰 {usage.input_tokens ?? "—"} / 출력 토큰{" "}
                        {usage.output_tokens ?? "—"} · 추정 비용{" "}
                        {ex.estimated_cost_usd
                          ? `$${ex.estimated_cost_usd}`
                          : "단가 미설정"}
                      </p>
                      {ex.error_message && (
                        <p className="error-text">{ex.error_message}</p>
                      )}
                      <table>
                        <thead>
                          <tr>
                            <th>필드</th>
                            <th>분석 후보</th>
                            <th>현재 수정값</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            [
                              "transaction_at",
                              "merchant",
                              "final_amount_krw",
                              "description",
                            ] as const
                          ).map((key) => (
                            <tr key={key}>
                              <th>
                                {
                                  {
                                    transaction_at: "거래일시",
                                    merchant: "상호",
                                    final_amount_krw: "결제금액",
                                    description: "사용 내역",
                                  }[key]
                                }
                              </th>
                              <td>{String(value[key] ?? "미확인")}</td>
                              <td>{String(editing[key] ?? "미확인")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <button
                        onClick={() => {
                          if (
                            confirm(
                              "이 분석 후보를 검토폼에 가져올까요? 저장하기 전까지 DB는 변경되지 않습니다.",
                            )
                          )
                            setEditing({ ...editing, ...value });
                        }}
                      >
                        이 후보를 검토폼에 가져오기
                      </button>
                    </div>
                  );
                })}
              </details>
            )}
            <label className="field">
              거래일시
              <input
                type="datetime-local"
                value={editing.transaction_at?.slice(0, 19) || ""}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    transaction_at: e.target.value || null,
                  })
                }
              />
            </label>
            <label className="field small">
              날짜만 확인된 경우
              <input
                aria-label="거래 날짜만 입력"
                type="date"
                value={editing.transaction_at?.slice(0, 10) || ""}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    transaction_at: e.target.value || null,
                  })
                }
              />
              <span className="muted">
                시간을 모르면 날짜만 저장하세요. 확정 ZIP의 검토 폴더로
                분리합니다.
              </span>
            </label>
            <div className="form-row">
              <label className="field">
                상호명
                <input
                  value={editing.merchant}
                  onChange={(e) =>
                    setEditing({ ...editing, merchant: e.target.value })
                  }
                />
              </label>
              <label className="field">
                최종 결제금액
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={editing.final_amount_krw ?? ""}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      final_amount_krw:
                        e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
            </div>
            <label className="field">
              사용 내역
              <input
                value={editing.description}
                onChange={(e) =>
                  setEditing({ ...editing, description: e.target.value })
                }
              />
            </label>
            <label className="field">
              검토 사유
              <textarea
                aria-label="검토 사유"
                value={editing.review_reason}
                onChange={(e) =>
                  setEditing({ ...editing, review_reason: e.target.value })
                }
              />
            </label>
            <div className="actions">
              <button
                className="primary"
                disabled={busy || analyzing}
                onClick={() =>
                  action(async () => {
                    await api(`/receipts/${editing.id}`, "PATCH", editing);
                    await refresh();
                    inform("영수증 검토값을 저장했습니다.");
                  })
                }
              >
                검토값 저장
              </button>
              <button
                disabled={!pending || busy}
                onClick={() =>
                  setEditing({
                    ...event.receipts.find((r) => r.id === editing.id)!,
                  })
                }
              >
                검토값 되돌리기
              </button>
              <button
                disabled={busy || analyzing}
                className="danger"
                onClick={() => {
                  if (confirm("이 영수증 원본과 연결을 삭제할까요?"))
                    action(async () => {
                      await api(`/receipts/${editing.id}`, "DELETE");
                      setEditing(null);
                      setSelected(null);
                      await refresh();
                    });
                }}
              >
                영수증 삭제
              </button>
              <button
                disabled={busy || analyzing || !!links.length}
                onClick={() =>
                  action(async () => {
                    await api(`/receipts/${editing.id}/exclude`, "POST");
                    await refresh();
                    inform("중복 영수증을 제외했습니다. 원본은 보관합니다.");
                  })
                }
              >
                중복 제외
              </button>
            </div>
            <div className="link-section">
              <h3>지출 행 연결</h3>
              <p className="muted small">
                배분액 합계가 영수증 결제금액을 넘지 않도록 연결합니다.
              </p>
              {suggestions
                .find((s) => s.receipt_id === selected)
                ?.candidates.map((c) => {
                  const x = event.expenses.find((e) => e.id === c.expense_id);
                  return (
                    <button
                      key={c.expense_id}
                      className="suggestion"
                      onClick={() => {
                        setExpense(String(c.expense_id));
                        setAllocated(String(x?.amount_krw || 0));
                      }}
                    >
                      추천 #
                      {event.expenses.findIndex((e) => e.id === c.expense_id) +
                        1}{" "}
                      {x?.item_name} · {c.score}점
                    </button>
                  );
                })}
              {links.map((l) => (
                <div className="existing-link" key={l.expense_id}>
                  <span>
                    #
                    {event.expenses.findIndex((e) => e.id === l.expense_id) + 1}{" "}
                    ·{" "}
                    {
                      event.expenses.find((e) => e.id === l.expense_id)
                        ?.item_name
                    }{" "}
                    · ₩ {won(l.allocated_amount_krw)}
                  </span>
                  <button
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        await api(
                          `/events/${event.id}/receipt-links/${l.expense_id}/${l.receipt_id}`,
                          "DELETE",
                        );
                        await refresh();
                      })
                    }
                  >
                    연결 해제
                  </button>
                </div>
              ))}
              <div className="actions wrap">
                <select
                  aria-label="연결 지출 선택"
                  value={expense}
                  onChange={(e) => setExpense(e.target.value)}
                >
                  <option value="">연결할 지출 선택</option>
                  {event.expenses.map((x, i) => (
                    <option value={x.id} key={x.id}>
                      #{i + 1} {x.item_name} (₩ {won(x.amount_krw)})
                    </option>
                  ))}
                </select>
                <input
                  aria-label="배분금액"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="배분금액"
                  value={allocated}
                  onChange={(e) => setAllocated(e.target.value)}
                />
                <button
                  disabled={busy || !expense || allocated === ""}
                  onClick={() =>
                    action(async () => {
                      await api(`/events/${event.id}/receipt-links`, "POST", {
                        expense_id: Number(expense),
                        receipt_id: editing.id,
                        allocated_amount_krw: Number(allocated),
                      });
                      await refresh();
                      inform("영수증을 연결했습니다.");
                    })
                  }
                >
                  연결 확정
                </button>
              </div>
              <div className="actions wrap">
                <select
                  aria-label="새 지출 항목"
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                >
                  <option value="">신규 지출 항목 선택</option>
                  {event.categories
                    .filter((c) => c.is_active)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
                <button
                  disabled={busy || !newCat || !!links.length}
                  onClick={() =>
                    action(async () => {
                      await api(
                        `/receipts/${editing.id}/create-expense?category_id=${newCat}`,
                        "POST",
                      );
                      await refresh();
                      inform("영수증으로 새 지출을 만들었습니다.");
                    })
                  }
                >
                  이 영수증으로 지출 생성
                </button>
              </div>
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
}
