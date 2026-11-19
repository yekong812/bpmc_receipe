import Dialog from "./Dialog";

export default function SaveNotice({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <Dialog title="저장 안내" onClose={onClose}>
      <p>{message}</p>
      <div className="dialog-actions">
        <button type="button" className="primary" onClick={onClose}>
          확인
        </button>
      </div>
    </Dialog>
  );
}
