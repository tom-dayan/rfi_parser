import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createProject, validateFolder } from '../services/api';
import type { ProjectCreate, FolderValidation } from '../types';
import FolderBrowser from './FolderBrowser';

interface FolderConfigProps {
  onProjectCreated?: (projectId: number) => void;
}

export default function FolderConfig({ onProjectCreated }: FolderConfigProps) {
  const [name, setName] = useState('');
  const [rfiPath, setRfiPath] = useState('');
  const [specsPath, setSpecsPath] = useState('');
  const [rfiValidation, setRfiValidation] = useState<FolderValidation | null>(null);
  const [specsValidation, setSpecsValidation] = useState<FolderValidation | null>(null);
  const [browsingFor, setBrowsingFor] = useState<'rfi' | 'specs' | null>(null);

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (project: ProjectCreate) => createProject(project),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setName('');
      setRfiPath('');
      setSpecsPath('');
      setRfiValidation(null);
      setSpecsValidation(null);
      onProjectCreated?.(data.id);
    },
  });

  const validateRfiFolder = async () => {
    if (!rfiPath.trim()) return;
    try {
      const result = await validateFolder(rfiPath);
      setRfiValidation(result);
    } catch {
      setRfiValidation({
        path: rfiPath,
        exists: false,
        is_directory: false,
        readable: false,
        file_count: 0,
        error: 'Failed to validate folder',
      });
    }
  };

  const validateSpecsFolder = async () => {
    if (!specsPath.trim()) return;
    try {
      const result = await validateFolder(specsPath);
      setSpecsValidation(result);
    } catch {
      setSpecsValidation({
        path: specsPath,
        exists: false,
        is_directory: false,
        readable: false,
        file_count: 0,
        error: 'Failed to validate folder',
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !rfiPath.trim() || !specsPath.trim()) return;

    createMutation.mutate({
      name: name.trim(),
      rfi_folder_path: rfiPath.trim(),
      specs_folder_path: specsPath.trim(),
    });
  };

  const isValid =
    name.trim() &&
    rfiValidation?.exists &&
    rfiValidation?.readable &&
    specsValidation?.exists &&
    specsValidation?.readable;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-2">Create New Project</h2>
      <p className="text-sm text-slate-500 mb-6">
        Configure the folder paths for your RFIs, Submittals, and Specifications.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1.5">
            Project Name
          </label>
          <input
            type="text"
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Building A Renovation"
            className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-900 placeholder:text-slate-400"
          />
        </div>

        {/* RFI/Submittal Folder */}
        <div>
          <label htmlFor="rfiPath" className="block text-sm font-medium text-slate-700 mb-1.5">
            RFI/Submittal Folder Path
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              id="rfiPath"
              value={rfiPath}
              onChange={(e) => {
                setRfiPath(e.target.value);
                setRfiValidation(null);
              }}
              placeholder="/path/to/rfis-and-submittals"
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-900 placeholder:text-slate-400"
            />
            <button
              type="button"
              onClick={() => setBrowsingFor('rfi')}
              className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
              title="Browse folders"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={validateRfiFolder}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Validate
            </button>
          </div>
          {rfiValidation && (
            <FolderStatus validation={rfiValidation} />
          )}
        </div>

        {/* Specs Folder */}
        <div>
          <label htmlFor="specsPath" className="block text-sm font-medium text-slate-700 mb-1.5">
            Specifications Folder Path
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              id="specsPath"
              value={specsPath}
              onChange={(e) => {
                setSpecsPath(e.target.value);
                setSpecsValidation(null);
              }}
              placeholder="/path/to/specs"
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-900 placeholder:text-slate-400"
            />
            <button
              type="button"
              onClick={() => setBrowsingFor('specs')}
              className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
              title="Browse folders"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={validateSpecsFolder}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Validate
            </button>
          </div>
          {specsValidation && (
            <FolderStatus validation={specsValidation} />
          )}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={!isValid || createMutation.isPending}
          className="w-full px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {createMutation.isPending ? 'Creating Project...' : 'Create Project'}
        </button>

        {createMutation.isError && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
            Failed to create project. Please check the folder paths and try again.
          </div>
        )}
      </form>

      {/* Folder Browser Modal */}
      <FolderBrowser
        isOpen={browsingFor !== null}
        onClose={() => setBrowsingFor(null)}
        onSelect={(path) => {
          if (browsingFor === 'rfi') {
            setRfiPath(path);
            setRfiValidation(null);
          } else if (browsingFor === 'specs') {
            setSpecsPath(path);
            setSpecsValidation(null);
          }
          setBrowsingFor(null);
        }}
        initialPath={browsingFor === 'rfi' ? rfiPath : specsPath}
      />
    </div>
  );
}

function FolderStatus({ validation }: { validation: FolderValidation }) {
  if (validation.error) {
    return (
      <div className="mt-2 flex items-center text-sm text-red-600">
        <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        {validation.error}
      </div>
    );
  }

  if (!validation.exists) {
    return (
      <div className="mt-2 flex items-center text-sm text-red-600">
        <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        Folder does not exist
      </div>
    );
  }

  if (!validation.is_directory) {
    return (
      <div className="mt-2 flex items-center text-sm text-red-600">
        <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        Path is not a directory
      </div>
    );
  }

  if (!validation.readable) {
    return (
      <div className="mt-2 flex items-center text-sm text-yellow-600">
        <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        Folder is not readable
      </div>
    );
  }

  return (
    <div className="mt-2 flex items-center text-sm text-green-600">
      <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
      Valid folder - {validation.file_count} supported files found
    </div>
  );
}
