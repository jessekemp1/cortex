import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

/**
 * Military styled button component
 * Tactical, functional design with status-based variants
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', children, disabled, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center font-mono font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cortex-accent focus:ring-offset-2 focus:ring-offset-cortex-bg disabled:opacity-50 disabled:cursor-not-allowed'

    const variantStyles = {
      primary: 'bg-cortex-accent hover:bg-cortex-accent-muted text-white border border-cortex-accent',
      secondary: 'bg-cortex-elevated hover:bg-cortex-border text-cortex-text-primary border border-cortex-border',
      ghost: 'bg-transparent hover:bg-cortex-surface text-cortex-text-secondary hover:text-cortex-text-primary',
      danger: 'bg-cortex-critical hover:bg-cortex-critical-muted text-white border border-cortex-critical',
    }

    const sizeStyles = {
      sm: 'px-3 py-1.5 text-sm rounded',
      md: 'px-4 py-2 text-base rounded-md',
      lg: 'px-6 py-3 text-lg rounded-lg',
    }

    return (
      <button
        ref={ref}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
