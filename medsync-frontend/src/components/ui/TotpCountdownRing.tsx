"use client";

import React, { useEffect, useState } from "react";

interface TotpCountdownRingProps {
  size?: number;
  strokeWidth?: number;
}

export const TotpCountdownRing: React.FC<TotpCountdownRingProps> = ({
  size = 40,
  strokeWidth = 3,
}) => {
  const [seconds, setSeconds] = useState(() => {
    const now = Math.floor(Date.now() / 1000);
    return 30 - (now % 30);
  });

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Math.floor(Date.now() / 1000);
      setSeconds(30 - (now % 30));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (seconds / 30) * circumference;

  return (
    <div className="flex flex-col items-center justify-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          className="transform -rotate-90"
          width={size}
          height={size}
        >
          {/* Background circle */}
          <circle
            className="text-gray-200"
            strokeWidth={strokeWidth}
            stroke="currentColor"
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
          {/* Progress circle */}
          <circle
            className={`${seconds < 5 ? "text-red-500" : "text-teal-600"} transition-all duration-1000 ease-linear`}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            style={{ strokeDashoffset: offset }}
            strokeLinecap="round"
            stroke="currentColor"
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-600">
          {seconds}s
        </span>
      </div>
      <span className="text-[10px] text-gray-400 uppercase tracking-tighter">
        New code in
      </span>
    </div>
  );
};
