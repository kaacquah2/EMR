import * as React from "react";

const accentClasses: Record<string, string> = {
  teal: "border-l-4 border-l-[#0B8A96]",
  navy: "border-l-4 border-l-[#0C1F3D]",
  green: "border-l-4 border-l-[#059669]",
  amber: "border-l-4 border-l-[#D97706]",
};

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Optional left accent border (teal, navy, green, amber) */
  accent?: keyof typeof accentClasses;
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className = "", accent, ...props }, ref) => (
    <div
      ref={ref}
      className={`rounded-xl border border-[#E2E8F0]/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)] ${accent ? accentClasses[accent] : ""} ${className}`}
      {...props}
    />
  )
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className = "", ...props }, ref) => (
  <div ref={ref} className={`mb-4 ${className}`} {...props} />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className = "", ...props }, ref) => (
  <h2
    ref={ref as React.Ref<HTMLParagraphElement>}
    className={`font-sora text-xl font-bold text-[#0F172A] ${className}`}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className = "", ...props }, ref) => (
  <div ref={ref} className={className} {...props} />
));
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardContent };
