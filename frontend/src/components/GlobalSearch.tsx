import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchFiles, getSearchContent, type SearchResult } from '../services/api';
import { Badge, Skeleton } from './ui';

interface GlobalSearchProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectFile?: (file: SearchResult) => void;
}

export default function GlobalSearch({ isOpen, onClose, onSelectFile }: GlobalSearchProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Search query
  const { data: searchResults, isLoading } = useQuery({
    queryKey: ['globalSearch', query],
    queryFn: () => searchFiles({ q: query, limit: 20 }),
    enabled: query.length >= 2,
    staleTime: 30000,
  });

  // Content preview
  const { data: previewContent, isLoading: previewLoading } = useQuery({
    queryKey: ['searchContent', previewPath],
    queryFn: () => getSearchContent(previewPath!, 5000),
    enabled: !!previewPath,
    staleTime: 60000,
  });

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 0);
      setQuery('');
      setSelectedIndex(0);
      setPreviewPath(null);
    }
  }, [isOpen]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!isOpen) return;

    const results = searchResults?.results || [];

    switch (e.key) {
      case 'Escape':
        onClose();
        break;
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (results[selectedIndex]) {
          onSelectFile?.(results[selectedIndex]);
          onClose();
        }
        break;
    }
  }, [isOpen, searchResults, selectedIndex, onClose, onSelectFile]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Update preview when selection changes
  useEffect(() => {
    const results = searchResults?.results || [];
    if (results[selectedIndex]) {
      setPreviewPath(results[selectedIndex].path);
    }
  }, [selectedIndex, searchResults]);

  if (!isOpen) return null;

  const results = searchResults?.results || [];

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  const getFileIcon = (fileType?: string, extension?: string) => {
    const type = fileType || extension || 'other';
    
    const icons: Record<string, string> = {
      drawing: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
      document: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      specification: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01',
      image: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
      rfi: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    };

    return icons[type] || icons.document;
  };

  const getFileTypeVariant = (fileType?: string): 'rfi' | 'submittal' | 'spec' | 'drawing' | 'default' => {
    switch (fileType?.toLowerCase()) {
      case 'rfi': return 'rfi';
      case 'submittal': return 'submittal';
      case 'specification': return 'spec';
      case 'drawing': return 'drawing';
      default: return 'default';
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" onClick={onClose}>
      <div className="min-h-screen px-4 text-center">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" />

        {/* Dialog */}
        <div
          className="inline-block w-full max-w-4xl my-8 text-left align-top transition-all transform bg-white shadow-elevated rounded-2xl overflow-hidden animate-slide-up"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Search input */}
          <div className="relative border-b border-stone-200">
            <svg
              className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-stone-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Search files, drawings, project knowledge..."
              className="w-full pl-14 pr-16 py-5 text-lg focus:outline-none placeholder-stone-400"
            />
            <div className="absolute right-5 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <kbd className="px-2 py-1 text-xs text-stone-400 bg-stone-100 rounded-md border border-stone-200">ESC</kbd>
            </div>
          </div>

          {/* Results */}
          <div className="flex">
            {/* Results list */}
            <div className="w-1/2 max-h-[60vh] overflow-y-auto border-r border-stone-200 scrollbar-thin">
              {query.length < 2 && (
                <div className="p-8 text-center">
                  <div className="w-12 h-12 mx-auto rounded-xl bg-stone-100 flex items-center justify-center mb-4">
                    <svg className="w-6 h-6 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </div>
                  <p className="text-stone-600 font-medium mb-1">Start typing to search</p>
                  <p className="text-stone-400 text-sm mb-4">Find files across all projects</p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {['door detail', 'RFI', 'waterproofing', 'landscape'].map((term) => (
                      <button
                        key={term}
                        onClick={() => setQuery(term)}
                        className="px-3 py-1.5 text-sm text-primary-700 bg-primary-50 rounded-full hover:bg-primary-100 transition"
                      >
                        {term}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {isLoading && query.length >= 2 && (
                <div className="p-4 space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center gap-3 p-3">
                      <Skeleton width={32} height={32} />
                      <div className="flex-1">
                        <Skeleton variant="text" width="60%" className="mb-2" />
                        <Skeleton variant="text" width="40%" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!isLoading && query.length >= 2 && results.length === 0 && (
                <div className="p-8 text-center">
                  <div className="w-12 h-12 mx-auto rounded-xl bg-stone-100 flex items-center justify-center mb-4">
                    <svg className="w-6 h-6 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <p className="text-stone-600 font-medium">No results for "{query}"</p>
                  <p className="text-sm text-stone-400 mt-1">Try different keywords</p>
                </div>
              )}

              {results.map((result, index) => (
                <button
                  key={result.path}
                  className={`w-full text-left px-4 py-3 flex items-start gap-3 transition ${
                    index === selectedIndex ? 'bg-primary-50' : 'hover:bg-stone-50'
                  }`}
                  onClick={() => {
                    onSelectFile?.(result);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${
                    index === selectedIndex ? 'bg-primary-100 text-primary-600' : 'bg-stone-100 text-stone-500'
                  }`}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getFileIcon(result.file_type, result.extension)} />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-stone-900 truncate">{result.filename}</p>
                    <p className="text-sm text-stone-500 truncate">{result.path}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      {result.file_type && (
                        <Badge variant={getFileTypeVariant(result.file_type)} size="sm">
                          {result.file_type}
                        </Badge>
                      )}
                      {result.size_bytes && (
                        <span className="text-xs text-stone-400">{formatFileSize(result.size_bytes)}</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Preview pane */}
            <div className="w-1/2 max-h-[60vh] overflow-y-auto bg-stone-50 p-5 scrollbar-thin">
              {!previewPath && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-stone-200 flex items-center justify-center mb-3">
                      <svg className="w-6 h-6 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    </div>
                    <p className="text-stone-500">Select a file to preview</p>
                  </div>
                </div>
              )}

              {previewLoading && previewPath && (
                <div className="space-y-3">
                  <Skeleton variant="text" width="50%" height={24} />
                  <Skeleton height={200} />
                </div>
              )}

              {previewContent && (
                <div className="animate-fade-in">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-semibold text-stone-900">{previewContent.filename}</span>
                    {previewContent.was_cached && (
                      <Badge variant="default" size="sm">cached</Badge>
                    )}
                  </div>
                  <pre className="text-sm text-stone-600 whitespace-pre-wrap font-mono bg-white p-4 rounded-xl border border-stone-200 overflow-x-auto leading-relaxed">
                    {previewContent.content || '(No text content available)'}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-5 py-3 bg-stone-50 border-t border-stone-200 flex items-center justify-between text-xs text-stone-500">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-white border border-stone-200 rounded text-stone-500">↑</kbd>
                <kbd className="px-1.5 py-0.5 bg-white border border-stone-200 rounded text-stone-500">↓</kbd>
                <span className="ml-1">navigate</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-white border border-stone-200 rounded text-stone-500">↵</kbd>
                <span className="ml-1">select</span>
              </span>
            </div>
            {searchResults && (
              <span className="font-medium">{searchResults.total} results</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
