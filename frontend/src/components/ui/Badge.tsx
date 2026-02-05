import { forwardRef, type HTMLAttributes } from 'react';

type BadgeVariant = 'default' | 'rfi' | 'submittal' | 'spec' | 'drawing' | 'success' | 'warning' | 'error';
type BadgeSize = 'sm' | 'md';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-stone-100 text-stone-700',
  rfi: 'bg-rfi-100 text-rfi-700',
  submittal: 'bg-submittal-100 text-submittal-700',
  spec: 'bg-spec-100 text-spec-700',
  drawing: 'bg-drawing-100 text-drawing-700',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
};

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-stone-400',
  rfi: 'bg-rfi-500',
  submittal: 'bg-submittal-500',
  spec: 'bg-spec-500',
  drawing: 'bg-drawing-500',
  success: 'bg-green-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', size = 'md', dot = false, className = '', children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={`
          inline-flex items-center gap-1.5 rounded-lg font-medium
          ${variantStyles[variant]}
          ${sizeStyles[size]}
          ${className}
        `}
        {...props}
      >
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]}`} />}
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';
