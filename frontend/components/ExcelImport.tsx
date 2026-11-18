"use client";
import { useState } from "react";
import { api, download, EventData, Preview, won } from "../lib/api";

import Dialog from "./Dialog";
export default function ExcelImport({
  event,
  onClose,
  onDone,
}: {
  event: EventData;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [mode, setMode] = useState("append"),
    [accepted, setAccepted] = useState(false),
    [replace, setReplace] = useState(false),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [catMapping, setCatMapping] = useState<Record<string, string | null>>({});
  const inspect = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const f = new FormData();
      f.append("file", file);
      f.append("mapping", JSON.stringify(mapping));
      setPreview(
        await api<Preview>(
          `/events/${event.id}/excel/import/preview`,
          "POST",
          f,
        ),
      );
      setAccepted(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog title="Excel 가져오기" onClose={onClose}>
      <p className="muted">
        .xlsx 파일을 검토한 후 지출내역에 반영합니다. 가져온 영수증 열은 연결
        데이터로 확정하지 않습니다.
      </p>
      <button
        type="button"
        onClick={() =>
          download(
            `/events/${event.id}/excel/import/template`,
            "행사비_지출내역_샘플.xlsx",
          ).catch((e) => setError((e as Error).message))
        }
      >
        ↧ 샘플 양식 다운로드
      </button>
      <p className="small muted">
        샘플의 예시 행을 실제 자료로 바꾼 뒤 업로드하세요. 작성 안내 시트도
        확인해주세요.
      </p>
      <label className="upload-zone">
        ↥<strong>지출내역 Excel 파일 선택</strong>
        <span>.xlsx · 최대 15MB</span>
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setPreview(null);
            setMapping({});
          }}
        />
        {file && <b>{file.name}</b>}
      </label>
      <button className="primary" disabled={!file || busy} onClick={inspect}>
        {busy ? "분석 중…" : "파일 분석 · 미리보기"}
      </button>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      {preview?.needs_mapping && (
        <>
          <h3>열 매핑이 필요합니다.</h3>
          <p className="small muted">
            숫자는 Excel의 열 번호입니다(A=1, B=2). 실제 헤더 행을 지정해주세요.
          </p>
          <div className="table-scroll">
            <table>
              <tbody>
                {preview.sample.map((r, i) => (
                  <tr key={i}>
                    <th>{i + 1}</th>
                    {r.map((c, j) => (
                      <td key={j}>{c}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {[
            "header_row",
            "지출일",
            "항목",
            "품목",
            "총계",
            "구매처",
            "구매 여부",
          ].map((k) => (
            <label className="mapping-row" key={k}>
              {k === "header_row" ? "헤더 행 번호" : k}
              <input
                type="number"
                min="1"
                max={k === "header_row" ? 10000 : 200}
                value={mapping[k] || ""}
                onChange={(e) =>
                  setMapping({ ...mapping, [k]: e.target.value })
                }
              />
            </label>
          ))}
          <button onClick={inspect} disabled={busy}>
            매핑 적용 · 다시 분석
          </button>
        </>
      )}
      {preview && !preview.needs_mapping && (
        <>
          <div className="preview-summary">
            <strong>{preview.rows.length}개 지출</strong>
            <span className="muted">
              합계 ₩{" "}
              {won(preview.rows.reduce((a, r) => a + (r.amount_krw || 0), 0))}
            </span>
          </div>
          <div className="table-scroll preview-table">
            <table>
              <thead>
                <tr>
                  <th>원본 행</th>
                  <th>지출일</th>
                  <th>항목</th>
                  <th>품목</th>
                  <th>총계</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.source_row}</td>
                    <td>{r.expense_date}</td>
                    <td>{r.category_name}</td>
                    <td>{r.item_name}</td>
                    <td className="numeric">{won(r.amount_krw)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!!preview.errors.length && (
            <div className="alert error">
              <b>파일을 수정한 후 다시 업로드해주세요.</b>
              {preview.errors.map((e, i) => (
                <p key={i}>
                  {e.row}행: {e.message}
                </p>
              ))}
            </div>
          )}
          {!!preview.warnings.length && (
            <div className="alert warning">
              <details>
                <summary>
                  확인이 필요한 경고 {preview.warnings.length}건
                </summary>
                {preview.warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </details>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                날짜 보완 및 중복 후보를 확인했습니다.
              </label>
            </div>
          )}
          {!!preview.new_categories.length && (
            <>
              <h3>새 항목 처리</h3>
              {preview.new_categories.map((n) => (
                <label className="mapping-row" key={n}>
                  {n}
                  <select
                    value={
                      catMapping[n] === null ? "__skip" : catMapping[n] || n
                    }
                    onChange={(e) =>
                      setCatMapping({
                        ...catMapping,
                        [n]:
                          e.target.value === "__skip" ? null : e.target.value,
                      })
                    }
                  >
                    <option value={n}>“{n}” 항목 생성</option>
                    {event.categories
                      .filter((c) => c.is_active)
                      .map((c) => (
                        <option key={c.id} value={c.name}>
                          {c.name}에 매핑
                        </option>
                      ))}
                    <option value="__skip">이 항목 행 제외</option>
                  </select>
                </label>
              ))}
            </>
          )}
          <div className="form-row">
            <label className="check-label">
              <input
                type="radio"
                name="mode"
                checked={mode === "append"}
                onChange={() => setMode("append")}
              />
              기존 지출에 추가
            </label>
            <label className="check-label">
              <input
                type="radio"
                name="mode"
                checked={mode === "replace"}
                onChange={() => setMode("replace")}
              />
              기존 지출 대체
            </label>
          </div>
          {mode === "replace" && (
            <label className="check-label warning-text">
              <input
                type="checkbox"
                checked={replace}
                onChange={(e) => setReplace(e.target.checked)}
              />
              기존 지출과 영수증 연결이 삭제되는 것을 확인했습니다.
            </label>
          )}
          <div className="dialog-actions">
            <button onClick={onClose}>취소</button>
            <button
              className="primary"
              disabled={
                busy ||
                !preview.rows.length ||
                !!preview.errors.length ||
                (!!preview.warnings.length && !accepted) ||
                (mode === "replace" && !replace)
              }
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api(`/events/${event.id}/excel/import/commit`, "POST", {
                    job_id: preview.job_id,
                    mode,
                    confirm_replace: replace,
                    accept_warnings: accepted,
                    category_mapping: catMapping,
                  });
                  await onDone();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              검토한 지출 반영
            </button>
          </div>
        </>
      )}
    </Dialog>
  );
}
