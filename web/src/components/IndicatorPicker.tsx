import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import type { Featured } from "../types";

interface Props {
  items: Featured[];
  current?: string;
  onSelect: (id: string) => void;
  variant?: "primary" | "outline";
}

export function IndicatorPicker({ items, current, onSelect, variant = "outline" }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  return (
    <div className="picker" ref={box}>
      <button type="button" className={`button button--${variant}`} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {t("picker.button")} <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="picker__panel" role="listbox">
          <div className="picker__head">
            <strong>{t("picker.title")}</strong>
            <span>{t("picker.hint")}</span>
          </div>
          {items.map((item, i) => (
            <button key={item.id} type="button" role="option" aria-selected={item.id === current}
              className={`picker__item ${item.id === current ? "is-active" : ""}`}
              onClick={() => { setOpen(false); onSelect(item.id); }}>
              <span className="picker__number">{String(i + 1).padStart(2, "0")}</span>
              <span className="picker__text">
                <small>{item.category}</small>
                <b>{item.title}</b>
                <span>{item.description}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
