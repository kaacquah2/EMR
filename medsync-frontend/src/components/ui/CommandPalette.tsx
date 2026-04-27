"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
  Search, 
  User, 
  FileText, 
  Calendar, 
  Settings, 
  LogOut,
  Beaker,
  Activity,
  Bed,
  X
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
  roles?: string[];
}

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { user, logout } = useAuth();

  // Define available commands
  const allCommands: Command[] = [
    {
      id: "search-patients",
      label: "Search Patients",
      shortcut: "⌘P",
      icon: <User className="h-4 w-4" />,
      action: () => router.push("/patients/search"),
      roles: ["doctor", "nurse", "receptionist", "hospital_admin", "super_admin"],
    },
    {
      id: "new-encounter",
      label: "Start New Encounter",
      icon: <FileText className="h-4 w-4" />,
      action: () => router.push("/encounters/new"),
      roles: ["doctor", "nurse"],
    },
    {
      id: "worklist",
      label: "View Worklist",
      icon: <Activity className="h-4 w-4" />,
      action: () => router.push("/worklist"),
      roles: ["doctor", "nurse"],
    },
    {
      id: "appointments",
      label: "View Appointments",
      icon: <Calendar className="h-4 w-4" />,
      action: () => router.push("/appointments"),
      roles: ["doctor", "nurse", "receptionist", "hospital_admin"],
    },
    {
      id: "lab-orders",
      label: "Lab Orders Queue",
      icon: <Beaker className="h-4 w-4" />,
      action: () => router.push("/lab/orders"),
      roles: ["lab_technician", "doctor"],
    },
    {
      id: "ward-patients",
      label: "Ward Patients",
      icon: <Bed className="h-4 w-4" />,
      action: () => router.push("/ward"),
      roles: ["nurse"],
    },
    {
      id: "settings",
      label: "Settings",
      icon: <Settings className="h-4 w-4" />,
      action: () => router.push("/settings"),
    },
    {
      id: "logout",
      label: "Log Out",
      icon: <LogOut className="h-4 w-4" />,
      action: () => logout(),
    },
  ];

  // Filter commands based on user role
  const commands = allCommands.filter(
    (cmd) => !cmd.roles || (user?.role && cmd.roles.includes(user.role))
  );

  // Filter by search query
  const filteredCommands = commands.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Open with Cmd/Ctrl + K
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen(true);
        setQuery("");
        setSelectedIndex(0);
      }

      // Close with Escape
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Handle navigation
  const handleKeyNavigation = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
      } else if (e.key === "Enter" && filteredCommands[selectedIndex]) {
        e.preventDefault();
        filteredCommands[selectedIndex].action();
        setIsOpen(false);
      }
    },
    [filteredCommands, selectedIndex]
  );

  // Reset selection when filteredCommands length changes
  const prevFilteredLengthRef = useRef(filteredCommands.length);
  useEffect(() => {
    if (prevFilteredLengthRef.current !== filteredCommands.length) {
      prevFilteredLengthRef.current = filteredCommands.length;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedIndex(0);
    }
  }, [filteredCommands.length]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setIsOpen(false)}
      />

      {/* Palette */}
      <div className="relative w-full max-w-lg mx-4 bg-background rounded-xl shadow-2xl border overflow-hidden">
        {/* Search input */}
        <div className="flex items-center border-b px-4 py-3">
          <Search className="h-5 w-5 text-muted-foreground mr-3" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyNavigation}
            placeholder="Search commands..."
            className="flex-1 bg-transparent outline-none text-foreground placeholder:text-muted-foreground"
            data-testid="command-palette-input"
          />
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 hover:bg-muted rounded"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Commands list */}
        <div className="max-h-80 overflow-y-auto py-2">
          {filteredCommands.length === 0 ? (
            <div className="px-4 py-8 text-center text-muted-foreground">
              No commands found
            </div>
          ) : (
            filteredCommands.map((cmd, index) => (
              <button
                key={cmd.id}
                onClick={() => {
                  cmd.action();
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-colors ${
                  index === selectedIndex
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-muted text-foreground"
                }`}
                data-testid={`command-${cmd.id}`}
              >
                <span className="text-muted-foreground">{cmd.icon}</span>
                <span className="flex-1">{cmd.label}</span>
                {cmd.shortcut && (
                  <kbd className="hidden sm:inline-block px-2 py-0.5 text-xs bg-muted rounded">
                    {cmd.shortcut}
                  </kbd>
                )}
              </button>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="border-t px-4 py-2 text-xs text-muted-foreground flex gap-4">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
