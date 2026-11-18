"use client";
import { useState } from "react";
import Dialog from "./Dialog";
import { api, won } from "../lib/api";
import { Book } from "../lib/annual";
type Preview = {
  job_id: string;
  rows: Record<string, unknown>[];
  errors: { row: number; message: string }[];
  warnings: string[];
  needs_mapping: boolean;
  sample: string[][];
  sheets: string[];
  sheet_name: string;
};
export default function AnnualExcelImport({
  book,
  target,
  onClose,
  onDone,
}: {
  book: Book;
  target: "budget" | "entries";
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [sheet, setSheet] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [mode, setMode] = useState("append"),
    [replace, setReplace] = useState(false),
    [accept, setAccept] = useState(false);
  async function inspect() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("target", target);
      form.append("mapping", JSON.stringify(mapping));
      form.append("sheet_name", sheet);
      setPreview(
        await api<Preview>(
          `/${book.kind}/books/${book.id}/excel/import/preview`,
          "POST",
          form,
        ),
      );
      setAccept(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={`${target === "budget" ? "예산표" : "장부"} Excel 가져오기`}
      onClose={onClose}
    >
      <p className="muted">
        {book.year}년 {book.name}에 초안으로 반영합니다. 다른 연도 거래와 오류
        행은 반영하지 않습니다.
      </p>
      <label className="upload-zone">
        <strong>.xlsx 파일 선택</strong>
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setPreview(null);
            setMapping({});
            setSheet("");
          }}
        />
      </label>
      <button disabled={!file || busy} onClick={inspect}>
        미리보기 분석
      </button>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {preview && (
        <>
          <label className="field">
            시트 선택
            <select
              aria-label="시트 선택"
              value={sheet || preview.sheet_name}
              onChange={(e) => {
                setSheet(e.target.value);
                setMapping({});
              }}
            >
              {preview.sheets.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <button disabled={busy} onClick={inspect}>
            선택 시트 다시 분석
          </button>
          {preview.needs_mapping ? (
            <>
              <h3>열 매핑</h3>
              <div className="table-scroll">
                <table>
                  <tbody>
                    {preview.sample.map((r, i) => (
                      <tr key={i}>
                        <th>{i + 1}</th>
                        {r.map((v, j) => (
                          <td key={j}>{v}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="small muted">열 번호: A=1, B=2 …</p>
              {[
                "header_row",
                ...(target === "budget"
                  ? ["관", "항", "목", "예산", "세부내용"]
                  : [
                      "날짜",
                      ...(book.kind === "ordinary" ? ["항", "목"] : []),
                      "내용",
                      "수입",
                      "지출",
                    ]),
              ].map((key) => (
                <label key={key} className="mapping-row">
                  {key === "header_row" ? "헤더 행 번호" : key}
                  <input
                    type="number"
                    min="1"
                    value={mapping[key] || ""}
                    onChange={(e) =>
                      setMapping({ ...mapping, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
              <button disabled={busy} onClick={inspect}>
                매핑 적용
              </button>
            </>
          ) : (
            <>
              <p className="preview-summary">
                반영 후보 {preview.rows.length}건
              </p>
              <div className="table-scroll preview-table">
                <table>
                  <thead>
                    <tr>
                      {(target === "budget"
                        ? ["원본 행", "관 / 항 / 목", "예산", "세부내용"]
                        : ["원본 행", "날짜", "내용", "수입", "지출"]
                      ).map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((r, i) => (
                      <tr key={i}>
                        <td>{String(r.source_row)}</td>
                        {target === "budget" ? (
                          <>
                            <td>
                              {String(r.division)} / {String(r.section)} /{" "}
                              {String(r.name)}
                            </td>
                            <td>{won(Number(r.budget_krw))}</td>
                            <td>{String(r.detail)}</td>
                          </>
                        ) : (
                          <>
                            <td>{String(r.transaction_date)}</td>
                            <td>{String(r.description)}</td>
                            <td>{won(Number(r.income_krw))}</td>
                            <td>{won(Number(r.expense_krw))}</td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!!preview.errors.length && (
                <div className="alert error">
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
                    <summary>경고 {preview.warnings.length}건</summary>
                    {preview.warnings.map((w, i) => (
                      <p key={i}>{w}</p>
                    ))}
                  </details>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={accept}
                      onChange={(e) => setAccept(e.target.checked)}
                    />
                    연도 보완·중복 경고를 확인했습니다.
                  </label>
                </div>
              )}
              <div className="form-row">
                <label className="check-label">
                  <input
                    type="radio"
                    checked={mode === "append"}
                    onChange={() => setMode("append")}
                  />
                  기존 자료에 추가/예산 갱신
                </label>
                <label className="check-label">
                  <input
                    type="radio"
                    checked={mode === "replace"}
                    onChange={() => setMode("replace")}
                  />
                  기존 자료 대체
                </label>
              </div>
              {mode === "replace" && (
                <label className="check-label warning-text">
                  <input
                    type="checkbox"
                    checked={replace}
                    onChange={(e) => setReplace(e.target.checked)}
                  />
                  기존 자료와 영수증 연결이 변경되는 것을 확인했습니다. 이전
                  자료는 변경 이력에 보관합니다.
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
                    (!!preview.warnings.length && !accept) ||
                    (mode === "replace" && !replace)
                  }
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      await api(
                        `/${book.kind}/books/${book.id}/excel/import/commit`,
                        "POST",
                        {
                          job_id: preview.job_id,
                          mode,
                          confirm_replace: replace,
                          accept_warnings: accept,
                        },
                      );
                      await onDone();
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  검토한 자료 반영
                </button>
              </div>
            </>
          )}
        </>
      )}
    </Dialog>
  );
}
