"use client";
import { useState } from "react";
import { EventData } from "../lib/api";
import { today } from "../lib/ui";

import Dialog from "./Dialog";
export default function EventForm({
  event,
  onClose,
  onSubmit,
  excel = false,
}: {
  event?: EventData;
  onClose: () => void;
  onSubmit: (data: unknown) => Promise<void>;
  excel?: boolean;
}) {
  const [name, setName] = useState(event?.name || ""),
    [eventDate, setEventDate] = useState(event?.event_date || today()),
    [start, setStart] = useState(event?.start_date || today()),
    [end, setEnd] = useState(event?.end_date || today()),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Dialog
      title={
        event
          ? "행사 정보 수정"
          : excel
            ? "Excel로 행사 생성"
            : "새 행사 만들기"
      }
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onSubmit({
              name,
              event_date: eventDate,
              start_date: start,
              end_date: end,
              status: event?.status ?? "작성중",
            });
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="muted">
          {excel
            ? "행사 정보를 입력한 후 Excel 파일을 가져옵니다."
            : "행사별로 지출내역과 영수증을 모아 관리합니다."}
        </p>
        <label className="field">
          행사명
          <input
            autoFocus
            required
            maxLength={200}
            value={name}
            placeholder="예: 11월 정기 행사"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="field">
          행사 날짜
          <input
            required
            type="date"
            value={eventDate}
            onChange={(e) => setEventDate(e.target.value)}
          />
        </label>
        <div className="form-row">
          <label className="field">
            시작일
            <input
              required
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label className="field">
            종료일
            <input
              required
              type="date"
              min={start}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
        </div>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            취소
          </button>
          <button disabled={busy} className="primary">
            {busy
              ? "저장 중…"
              : event
                ? "수정 저장"
                : excel
                  ? "행사 생성 후 Excel 가져오기"
                  : "행사 만들기"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
