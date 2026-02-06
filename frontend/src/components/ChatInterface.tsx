import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendChatMessage, type ChatAction } from '../services/api';
import { Button, Badge } from './ui';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{
    filename: string;
    section?: string;
    path?: string;
  }>;
  actions?: ChatAction[];
  timestamp: string;
}

interface ChatInterfaceProps {
  projectId?: number;
  projectName?: string;
  onClose?: () => void;
  onAction?: (action: ChatAction) => void;
}

export default function ChatInterface({ projectId, projectName, onClose, onAction }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const chatMutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (response) => {
      setSessionId(response.session_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.content,
        sources: response.sources,
        actions: (response as { actions?: ChatAction[] }).actions,
        timestamp: response.timestamp,
      }]);
    },
    onError: (error: Error) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}`,
        timestamp: new Date().toISOString(),
      }]);
    },
  });
  
  // Handle action button clicks
  const handleActionClick = (action: ChatAction) => {
    if (onAction) {
      onAction(action);
    }
  };
  
  // Get icon for action
  const getActionIcon = (iconName?: string) => {
    switch (iconName) {
      case 'search':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        );
      case 'sparkles':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
          </svg>
        );
      case 'folder':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
        );
      case 'document':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
      case 'settings':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        );
      default:
        return null;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || chatMutation.isPending) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');

    chatMutation.mutate({
      content: userMessage.content,
      project_id: projectId,
      session_id: sessionId || undefined,
    });
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  return (
    <div className="flex flex-col h-full bg-white border-l border-stone-200">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200 bg-stone-50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-sm">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-stone-900">Ask OLI</h3>
            {projectName ? (
              <Badge variant="default" size="sm">{projectName}</Badge>
            ) : (
              <p className="text-xs text-stone-500">Search all projects</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="p-2 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100 transition"
              title="Clear chat"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100 transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.length === 0 && (
          <div className="text-center py-10">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-primary-50 flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h4 className="font-medium text-stone-900 mb-2">Ask me anything</h4>
            <p className="text-sm text-stone-500 max-w-xs mx-auto">
              I can help you find information, search drawings, project files, and answer questions about {projectName ? 'this project' : 'your documents'}.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[
                'Find door details',
                'Waterproofing details',
                'Recent RFIs',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="px-3 py-1.5 text-sm text-primary-700 bg-primary-50 rounded-full hover:bg-primary-100 transition"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-stone-100 text-stone-900'
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
              
              {/* Sources */}
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-stone-200/50">
                  <p className="text-xs font-medium text-stone-500 mb-2">Sources:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {message.sources.map((source, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center px-2 py-1 text-xs bg-white rounded-lg text-stone-600 shadow-sm"
                        title={source.path || source.filename}
                      >
                        <svg className="w-3 h-3 mr-1 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {source.filename}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Quick Actions */}
              {message.actions && message.actions.length > 0 && (
                <div className="mt-3 pt-3 border-t border-stone-200/50">
                  <p className="text-xs font-medium text-stone-500 mb-2">Quick Actions:</p>
                  <div className="flex flex-wrap gap-2">
                    {message.actions.map((action, i) => (
                      <button
                        key={i}
                        onClick={() => handleActionClick(action)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 transition border border-primary-200"
                        title={action.description}
                      >
                        {getActionIcon(action.icon)}
                        {action.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {chatMutation.isPending && (
          <div className="flex justify-start animate-fade-in">
            <div className="bg-stone-100 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-stone-200 bg-white">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="input flex-1"
            disabled={chatMutation.isPending}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={!input.trim() || chatMutation.isPending}
            icon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            }
          />
        </div>
      </form>
    </div>
  );
}
