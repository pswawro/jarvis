import { useMemo } from "react";
import { motion } from "framer-motion";
import type { ChatSummary } from "../types";

interface Props {
  chatList: ChatSummary[];
  activeChatId: string | null;
  onSwitch: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export function ChatListPanel({ chatList, activeChatId, onSwitch, onNew, onDelete }: Props) {
  const sorted = useMemo(() => [...chatList].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)), [chatList]);

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden border-b border-gray-100 shrink-0"
    >
      <div className="max-h-[200px] overflow-y-auto">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-4 py-2 text-[12px] font-medium text-az-navy hover:bg-gray-50 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
        {sorted.map((chat) => (
          <div
            key={chat.id}
            className={`flex items-center gap-2 px-4 py-2 cursor-pointer transition-colors ${
              chat.id === activeChatId ? "bg-az-navy/5 border-l-2 border-az-navy" : "hover:bg-gray-50"
            }`}
            onClick={() => onSwitch(chat.id)}
          >
            <span className="flex-1 min-w-0 text-[12px] text-gray-700 truncate">
              {chat.title}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(chat.id);
              }}
              className="shrink-0 text-gray-300 hover:text-red-400 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
        {sorted.length === 0 && (
          <div className="px-4 py-3 text-[11px] text-gray-400 text-center">No saved chats</div>
        )}
      </div>
    </motion.div>
  );
}
