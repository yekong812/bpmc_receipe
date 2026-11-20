"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, EventData } from "../../../lib/api";
import EventModal from "../../../components/EventModal";

function EventPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const [event, setEvent] = useState<EventData | null>(null);
  const [events, setEvents] = useState<EventData[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [importOnOpen] = useState(() => search.get("import") === "1");
  const inform = useCallback((s: string) => {
    setNotice(s);
    setTimeout(() => setNotice(""), 5000);
  }, []);
  const loadList = useCallback(async () => {
    setEvents(await api<EventData[]>("/events"));
  }, []);
  useEffect(() => {
    let cancelled = false;
    setError("");
    setEvent(null);
    Promise.all([api<EventData>(`/events/${id}`), api<EventData[]>("/events")])
      .then(([current, list]) => {
        if (cancelled) return;
        setEvent(current);
        setEvents(list);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);
  useEffect(() => {
    if (importOnOpen) router.replace(`/events/${id}`);
  }, [id, importOnOpen, router]);
  if (error)
    return (
      <div className="workspace">
        <div className="empty">
          <h3>행사를 열 수 없습니다.</h3>
          <p>{error}</p>
          <button onClick={() => router.push("/events")}>행사 목록으로</button>
        </div>
      </div>
    );
  if (!event) return <div className="empty">행사를 불러오는 중입니다…</div>;
  return (
    <>
      <EventModal
        key={event.id}
        initial={event}
        events={events}
        importOnOpen={importOnOpen}
        onClose={() => router.push("/events")}
        onChanged={loadList}
        inform={inform}
      />
      {notice && (
        <div className="toast" role="status">
          ✓ {notice}
        </div>
      )}
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="empty">행사를 불러오는 중입니다…</div>}>
      <EventPage />
    </Suspense>
  );
}
