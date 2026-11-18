"use client";
import { useState } from "react";
import { won } from "../lib/api";

export default function WonInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      aria-label={label}
      className="numeric won-input"
      inputMode="numeric"
      value={value === null ? "" : focused ? String(value) : `₩ ${won(value)}`}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onChange={(e) => {
        const digits = e.target.value.replace(/[₩,\s]/g, "");
        if (/^\d*$/.test(digits) && Number(digits) <= 10 ** 12)
          onChange(digits === "" ? null : Number(digits));
      }}
    />
  );
}
