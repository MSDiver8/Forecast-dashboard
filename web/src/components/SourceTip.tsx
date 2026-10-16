import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

const POP_WIDTH = 320;

/** "i" next to a source name: what the source is, then what to keep in mind about its numbers. */
export function SourceTip({ summary, caveat }: { summary?: string | null; caveat?: string | null }) {
  const anchor = useRef<HTMLSpanElement>(null);
  const [place, setPlace] = useState<CSSProperties | null>(null);

  // A fixed tip does not follow the page: it closes on scroll and resize.
  useEffect(() => {
    if (!place) return;
    const hide = () => setPlace(null);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [place]);

  if (!summary && !caveat) return null;

  // The tip is drawn in <body>: scrolling side panels would clip it or the next panel would cover it.
  const open = () => {
    const box = anchor.current?.getBoundingClientRect();
    if (!box) return;
    const left = Math.max(8, Math.min(box.left - 10, window.innerWidth - POP_WIDTH - 16));
    const below = box.bottom < window.innerHeight * 0.6;
    setPlace(below ? { top: box.bottom + 8, left } : { bottom: window.innerHeight - box.top + 8, left });
  };
  const close = () => setPlace(null);

  return (
    <span
      ref={anchor}
      className="source-tip"
      tabIndex={0}
      aria-label={[summary, caveat].filter(Boolean).join(" ")}
      onMouseEnter={open}
      onMouseLeave={close}
      onFocus={open}
      onBlur={close}
    >
      i
      {place &&
        createPortal(
          <span className="source-tip__pop" role="tooltip" style={{ ...place, width: POP_WIDTH }}>
            {summary && <span className="source-tip__summary">{summary}</span>}
            {caveat && <span className="source-tip__warn">{caveat}</span>}
          </span>,
          document.body,
        )}
    </span>
  );
}
