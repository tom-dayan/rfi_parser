import { forwardRef, type HTMLAttributes } from 'react';

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number; // 0-100
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  label?: string;
  variant?: 'default' | 'success' | 'warning';
  indeterminate?: boolean;
}

const sizeStyles = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
};

const variantStyles = {
  default: 'bg-primary-500',
  success: 'bg-green-500',
  warning: 'bg-amber-500',
};

export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ value, size = 'md', showLabel = false, label, variant = 'default', indeterminate = false, className = '', ...props }, ref) => {
    const clampedValue = Math.min(100, Math.max(0, value));

    return (
      <div ref={ref} className={`w-full ${className}`} {...props}>
        {(showLabel || label) && (
          <div className="flex justify-between items-center mb-2">
            {label && <span className="text-sm font-medium text-stone-700">{label}</span>}
            {showLabel && !indeterminate && <span className="text-sm text-stone-500">{Math.round(clampedValue)}%</span>}
          </div>
        )}
        <div className={`w-full bg-stone-200 rounded-full overflow-hidden ${sizeStyles[size]}`}>
          {indeterminate ? (
            <div
              className={`h-full rounded-full ${variantStyles[variant]} animate-pulse`}
              style={{ width: '30%', animation: 'indeterminate 1.5s infinite ease-in-out' }}
            />
          ) : (
            <div
              className={`h-full rounded-full transition-all duration-300 ease-out ${variantStyles[variant]}`}
              style={{ width: `${clampedValue}%` }}
            />
          )}
        </div>
      </div>
    );
  }
);

Progress.displayName = 'Progress';

// Multi-step progress indicator
interface StepProgressProps {
  steps: { id: string; label: string }[];
  currentStep: number; // 0-indexed
  className?: string;
}

export function StepProgress({ steps, currentStep, className = '' }: StepProgressProps) {
  return (
    <div className={`flex items-center ${className}`}>
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`
                w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                transition-all duration-200
                ${index < currentStep 
                  ? 'bg-primary-600 text-white' 
                  : index === currentStep 
                    ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-500' 
                    : 'bg-stone-100 text-stone-400'}
              `}
            >
              {index < currentStep ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                index + 1
              )}
            </div>
            <span 
              className={`
                mt-2 text-xs font-medium whitespace-nowrap
                ${index <= currentStep ? 'text-stone-700' : 'text-stone-400'}
              `}
            >
              {step.label}
            </span>
          </div>
          {index < steps.length - 1 && (
            <div 
              className={`
                w-12 h-0.5 mx-2 mt-[-1rem]
                ${index < currentStep ? 'bg-primary-500' : 'bg-stone-200'}
              `} 
            />
          )}
        </div>
      ))}
    </div>
  );
}
