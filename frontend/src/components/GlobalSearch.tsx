import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchFiles, getSearchContent, type SearchResult } from '../services/api';

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

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" onClick={onClose}>
      <div className="min-h-screen px-4 text-center">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black/50 transition-opacity" />

        {/* Dialog */}
        <div
          className="inline-block w-full max-w-3xl my-8 text-left align-top transition-all transform bg-white shadow-2xl rounded-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Search input */}
          <div className="relative border-b border-slate-200">
            <svg
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400"
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
              placeholder="Search files, drawings, specifications..."
              className="w-full pl-12 pr-4 py-4 text-lg focus:outline-none"
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <kbd className="px-2 py-1 text-xs text-slate-400 bg-slate-100 rounded">ESC</kbd>
            </div>
          </div>

          {/* Results */}
          <div className="flex">
            {/* Results list */}
            <div className="w-1/2 max-h-[60vh] overflow-y-auto border-r border-slate-200">
              {query.length < 2 && (
                <div className="p-8 text-center">
                  <p className="text-slate-500">Type at least 2 characters to search</p>
                  <div className="mt-4 space-y-2">
                    <p className="text-xs text-slate-400">Try searching for:</p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {['door detail', 'RFI', 'waterproofing', 'foundation'].map((term) => (
                        <button
                          key={term}
                          onClick={() => setQuery(term)}
                          className="px-2 py-1 text-sm text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100"
                        >
                          {term}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {isLoading && query.length >= 2 && (
                <div className="p-8 text-center">
                  <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-slate-300 border-t-blue-600" />
                </div>
              )}

              {!isLoading && query.length >= 2 && results.length === 0 && (
                <div className="p-8 text-center">
                  <p className="text-slate-500">No results found for "{query}"</p>
                  <p className="text-sm text-slate-400 mt-2">Try different keywords or wildcards (*)</p>
                </div>
              )}

              {results.map((result, index) => (
                <button
                  key={result.path}
                  className={`w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-50 transition ${
                    index === selectedIndex ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => {
                    onSelectFile?.(result);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
                    index === selectedIndex ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500'
                  }`}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getFileIcon(result.file_type, result.extension)} />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 truncate">{result.filename}</p>
                    <p className="text-sm text-slate-500 truncate">{result.path}</p>
                    <div className="flex items-center gap-3 mt-1">
                      {result.file_type && (
                        <span className="text-xs text-slate-400">{result.file_type}</span>
                      )}
                      {result.size_bytes && (
                        <span className="text-xs text-slate-400">{formatFileSize(result.size_bytes)}</span>
                      )}
                      {result.project_name && (
                        <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                          {result.project_name}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Preview pane */}
            <div className="w-1/2 max-h-[60vh] overflow-y-auto bg-slate-50 p-4">
              {!previewPath && (
                <div className="h-full flex items-center justify-center text-slate-400">
                  <p>Select a file to preview</p>
                </div>
              )}

              {previewLoading && previewPath && (
                <div className="h-full flex items-center justify-center">
                  <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-slate-300 border-t-blue-600" />
                </div>
              )}

              {previewContent && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-medium text-slate-900">{previewContent.filename}</span>
                    {previewContent.was_cached && (
                      <span className="text-xs text-slate-400">(cached)</span>
                    )}
                  </div>
                  <pre className="text-sm text-slate-600 whitespace-pre-wrap font-mono bg-white p-3 rounded-lg border border-slate-200 overflow-x-auto">
                    {previewContent.content || '(No text content)'}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-4">
              <span>
                <kbd className="px-1.5 py-0.5 bg-slate-200 rounded">↑↓</kbd> to navigate
              </span>
              <span>
                <kbd className="px-1.5 py-0.5 bg-slate-200 rounded">Enter</kbd> to select
              </span>
            </div>
            {searchResults && (
              <span>{searchResults.total} results</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
