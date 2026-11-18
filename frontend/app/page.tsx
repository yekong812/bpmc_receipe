"use client";
import { useCallback, useEffect, useState } from "react";
import { api, EventData, won } from "../lib/api";
import EventForm from "../components/EventForm";
import EventModal from "../components/EventModal";
import { statusClass } from "../lib/ui";
export default function Home() {
  const [events, setEvents] = useState<EventData[]>([]),
    [current, setCurrent] = useState<EventData | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [query, setQuery] = useState(""),
    [status, setStatus] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [eventFrom, setEventFrom] = useState(""),
    [eventTo, setEventTo] = useState(""),
    [sort, setSort] = useState("date"),
    [page, setPage] = useState(1);
  const [create, setCreate] = useState(false),
    [excelCreate, setExcelCreate] = useState(false),
    [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      setEvents(await api<EventData[]>("/events"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    setPage(1);
  }, [query, status, start, end, eventFrom, eventTo, events.length]);
  const inform = (s: string) => {
    setNotice(s);
    setTimeout(() => setNotice(""), 5000);
  };
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const filtered = events
    .filter(
      (e) =>
        (!query || e.name.toLowerCase().includes(query.toLowerCase())) &&
        (!status || e.status === status) &&
        (!start || e.end_date >= start) &&
        (!end || e.start_date <= end) &&
        (!eventFrom || e.event_date >= eventFrom) &&
        (!eventTo || e.event_date <= eventTo),
    )
    .sort((a, b) =>
      sort === "amount"
        ? b.total_krw - a.total_krw
        : sort === "name"
          ? a.name.localeCompare(b.name)
          : sort === "status"
            ? a.status.localeCompare(b.status)
            : (b.event_date || b.end_date).localeCompare(
                a.event_date || a.end_date,
              ),
    );
  return (
    <main>
      <div className="workspace">
        <div className="breadcrumb">
          워크스페이스 <span>/</span> 행사 목록
        </div>
        <section className="page-heading">
          <div>
            <p className="eyebrow">EVENT EXPENSE MANAGER</p>
            <h1>행사의 모든 지출, 한눈에.</h1>
            <p className="muted">
              지출내역부터 영수증 정리까지, 행사별로 꼼꼼하게 관리하세요.
            </p>
          </div>
          <div className="actions">
            <button
              onClick={() => {
                setExcelCreate(true);
                setCreate(true);
              }}
            >
              ↥ Excel로 행사 생성
            </button>
            <button
              className="primary"
              onClick={() => {
                setExcelCreate(false);
                setCreate(true);
              }}
            >
              ＋ 새 행사
            </button>
          </div>
        </section>
        <div className="stats">
          <Stat
            label="전체 행사"
            value={String(events.length)}
            unit="개"
            sub="등록된 행사"
          />
          <Stat
            label="총 지출금액"
            value={won(events.reduce((a, e) => a + e.total_krw, 0))}
            unit="원"
            sub="모든 지출 행 기준"
          />
          <Stat
            label="영수증 연결"
            value={String(events.reduce((a, e) => a + e.matched_count, 0))}
            unit={`/ ${events.reduce((a, e) => a + e.expense_count, 0)}건`}
            sub="영수증이 연결된 지출 / 전체 지출"
          />
          <Stat
            label="검토 중인 행사"
            value={String(events.filter((e) => e.status === "검토중").length)}
            unit="개"
            sub="마지막 확인을 기다리고 있어요"
          />
        </div>
        {error && (
          <div className="alert error" role="alert">
            {error}
            <button onClick={() => setError("")}>닫기</button>
          </div>
        )}
        <section className="event-panel">
          <div className="panel-heading">
            <h2>
              행사 목록 <span className="count">{filtered.length}</span>
            </h2>
            <span className="muted small">
              행사를 선택해 지출내역서를 열어보세요.
            </span>
          </div>
          <div className="filters">
            <label className="search">
              <span>⌕</span>
              <input
                aria-label="행사명 검색"
                placeholder="행사명을 검색하세요"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <label>
              <span className="small muted">행사기간</span>
              <input
                aria-label="필터 시작일"
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <span className="muted">~</span>
            <input
              aria-label="필터 종료일"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
            <label>
              <span className="small muted">행사 날짜</span>
              <input
                aria-label="행사 날짜 필터 시작"
                type="date"
                value={eventFrom}
                onChange={(e) => setEventFrom(e.target.value)}
              />
            </label>
            <span className="muted">~</span>
            <input
              aria-label="행사 날짜 필터 종료"
              type="date"
              value={eventTo}
              onChange={(e) => setEventTo(e.target.value)}
            />
            <select
              aria-label="상태 필터"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">모든 상태</option>
              {["작성중", "검토중", "최종 확정", "재수정중"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              className="text-button"
              onClick={() => {
                setQuery("");
                setStatus("");
                setStart("");
                setEnd("");
                setEventFrom("");
                setEventTo("");
              }}
            >
              초기화
            </button>
            <select
              aria-label="정렬"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="date">최근 행사순</option>
              <option value="amount">지출 많은순</option>
              <option value="name">이름순</option>
              <option value="status">상태순</option>
            </select>
          </div>
          <div className="table-scroll">
            <table className="event-table">
              <thead>
                <tr>
                  <th>No.</th>
                  <th>
                    <button
                      className="text-button"
                      onClick={() => setSort("name")}
                    >
                      행사명 ↕
                    </button>
                  </th>
                  <th>
                    <button
                      className="text-button"
                      onClick={() => setSort("date")}
                    >
                      행사 날짜 ↕
                    </button>
                  </th>
                  <th>행사기간</th>
                  <th className="numeric">지출건수</th>
                  <th className="numeric">
                    <button
                      className="text-button"
                      onClick={() => setSort("amount")}
                    >
                      총지출 ↕
                    </button>
                  </th>
                  <th title="영수증이 한 장 이상 연결된 지출 행 수 / 전체 지출 행 수">
                    영수증 연결 ⓘ
                  </th>
                  <th>
                    <button
                      className="text-button"
                      onClick={() => setSort("status")}
                    >
                      진행상태 ↕
                    </button>
                  </th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice((page - 1) * 10, page * 10).map((e, i) => (
                  <tr
                    key={e.id}
                    onClick={() => setCurrent(e)}
                    tabIndex={0}
                    onKeyDown={(k) => {
                      if (k.key === "Enter") setCurrent(e);
                    }}
                  >
                    <td className="muted">{(page - 1) * 10 + i + 1}</td>
                    <td>
                      <div className="event-name">
                        <span className="folder-icon">▤</span>
                        <div>
                          <strong>{e.name}</strong>
                          <small>영수증 {e.receipt_count}장</small>
                        </div>
                      </div>
                    </td>
                    <td className="date-text">
                      {e.event_date?.replaceAll("-", ".")}
                    </td>
                    <td className="date-text">
                      {e.start_date.replaceAll("-", ".")} —{" "}
                      {e.end_date.replaceAll("-", ".")}
                    </td>
                    <td className="numeric">{e.expense_count}건</td>
                    <td className="numeric amount">₩ {won(e.total_krw)}</td>
                    <td>
                      <div className="receipt-ratio">
                        {e.matched_count}
                        <span> / {e.expense_count}건</span>
                      </div>
                      <div className="progress">
                        <div
                          style={{
                            width: `${e.expense_count ? (e.matched_count / e.expense_count) * 100 : 0}%`,
                          }}
                        />
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${statusClass(e.status)}`}>
                        <i />
                        {e.status}
                      </span>
                    </td>
                    <td>
                      <div
                        className="actions"
                        onClick={(x) => x.stopPropagation()}
                      >
                        <button
                          className="text-button"
                          onClick={() => setCurrent(e)}
                        >
                          상세 ↗
                        </button>
                        <button
                          title="행사 복제 (영수증 제외)"
                          disabled={busy}
                          onClick={() =>
                            action(async () => {
                              await api(`/events/${e.id}/duplicate`, "POST");
                              await refresh();
                              inform(
                                "행사를 복제했습니다. 영수증은 복사하지 않습니다.",
                              );
                            })
                          }
                        >
                          ⧉
                        </button>
                        <button
                          title="행사 삭제"
                          disabled={busy}
                          onClick={() => {
                            if (
                              confirm(
                                `“${e.name}” 행사와 모든 지출·영수증을 삭제할까요?`,
                              )
                            )
                              action(async () => {
                                await api(`/events/${e.id}`, "DELETE");
                                await refresh();
                                inform("행사를 삭제했습니다.");
                              });
                          }}
                        >
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {loading ? (
            <div className="empty">행사를 불러오는 중입니다…</div>
          ) : (
            !filtered.length && (
              <div className="empty">
                <span className="empty-icon">▦</span>
                <h3>
                  {events.length
                    ? "조건에 맞는 행사가 없습니다."
                    : "첫 번째 행사를 만들어보세요"}
                </h3>
                <p>
                  {events.length
                    ? "검색어나 필터를 변경해보세요."
                    : "행사를 만들고 지출내역을 입력하거나 Excel 파일을 가져오세요."}
                </p>
                <button
                  onClick={() => {
                    setExcelCreate(false);
                    setCreate(true);
                  }}
                >
                  ＋ 새 행사 만들기
                </button>
              </div>
            )
          )}
          <footer className="table-footer">
            <span>총 {filtered.length}개 행사</span>
            <div className="actions">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                ‹
              </button>
              <span>
                {page} / {Math.max(1, Math.ceil(filtered.length / 10))}
              </span>
              <button
                disabled={page >= Math.ceil(filtered.length / 10)}
                onClick={() => setPage(page + 1)}
              >
                ›
              </button>
            </div>
          </footer>
        </section>
        <p className="footnote">
          ⓘ 총지출은 구매 여부와 관계없이 모든 지출 행의 금액을 합산합니다.
        </p>
      </div>
      {create && (
        <EventForm
          onClose={() => setCreate(false)}
          onSubmit={async (data) => {
            const e = await api<EventData>("/events", "POST", data);
            setCreate(false);
            setCurrent(e);
            await refresh();
          }}
          excel={excelCreate}
        />
      )}
      {current && (
        <EventModal
          initial={current}
          events={events}
          importOnOpen={excelCreate}
          onClose={() => {
            setCurrent(null);
            setExcelCreate(false);
            refresh();
          }}
          onChanged={refresh}
          inform={inform}
        />
      )}
      {notice && (
        <div className="toast" role="status">
          ✓ {notice}
        </div>
      )}
    </main>
  );
}
function Stat({
  label,
  value,
  unit,
  sub,
}: {
  label: string;
  value: string;
  unit: string;
  sub: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <div>
        {value}
        <small>{unit}</small>
      </div>
      <p>{sub}</p>
    </div>
  );
}
