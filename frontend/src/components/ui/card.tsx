import { ReactNode } from "react";
import clsx from "clsx";

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "rounded-[28px] p-5 shadow-sm",
        !className && "border border-stone-300 bg-white",
        className
      )}
    >
      {children}
    </section>
  );
}
