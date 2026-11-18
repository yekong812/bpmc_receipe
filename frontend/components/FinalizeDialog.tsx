"use client";
import { useEffect, useState } from "react";
import { api, EventData, won } from "../lib/api";
import Dialog from "./Dialog";
type Check = {
  errors: string[];
  warnings: string[];
  version: number;
  expense_count: number;
  total_krw: number;
};
export default function FinalizeDialog({
  event,
  onClose,
  onDone,
  countLabel = "지출",
}: {
  event: EventData;
  onClose: () => void;
  onDone: () => Promise<void>;
  countLabel?: string;
}) {
  const [result, setResult] = useState<Check | null>(null),
    [reason, setReason] = useState(""),
    [accepted, setAccepted] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Check>(`/events/${event.id}/finalize/check`)
      .then(setResult)
      .catch((e) => setError(e.message));
  }, [event.id]);
  return (
    <Dialog title="최종 확정 전 확인" onClose={onClose}>
      <p className="muted">
        확정하면 현재 데이터를 불변 버전으로 보관하고 편집을 잠급니다. 변경은
        수정 재오픈을 통해 진행합니다.
      </p>
      <p className="small muted">
        확정 대상: <strong>{event.name}</strong>
      </p>
      {!result && !error && (
        <p className="muted" role="status">
          확정 조건을 확인하는 중입니다…
        </p>
      )}
      {result && (
        <>
          <div className="preview-summary">
            <strong>
              {countLabel} {result.expense_count}건
            </strong>
            <strong>지출 합계 ₩ {won(result.total_krw)}</strong>
          </div>
          {!!result.errors.length && (
            <div className="alert error">
              <b>확정 전에 수정해주세요.</b>
              {result.errors.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
            </div>
          )}
          {!!result.warnings.length && (
            <div className="alert warning">
              <b>사유 확인이 필요한 항목 {result.warnings.length}건</b>
              {result.warnings.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
              <label className="field">
                승인 사유
                <textarea
                  aria-label="승인 사유"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="예: 현금 구매로 영수증 미첨부, 담당자 확인 완료"
                />
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                위 경고와 사유를 확인했습니다.
              </label>
            </div>
          )}
          <div className="dialog-actions">
            <button onClick={onClose}>돌아가서 수정</button>
            <button
              className="primary"
              disabled={
                busy ||
                !!result.errors.length ||
                (!!result.warnings.length && (!reason.trim() || !accepted))
              }
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api(`/events/${event.id}/finalize`, "POST", {
                    version: result.version,
                    approval_reason: reason,
                    acknowledge_warnings: accepted,
                  });
                  await onDone();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy
                ? "확정 중…"
                : `최종 확정 v${event.latest_final_version + 1}`}
            </button>
          </div>
        </>
      )}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
