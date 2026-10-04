import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'
import { cn } from '@pricepolicy/ui/lib/utils'

const alertVariants = cva('relative w-full rounded-lg border p-4 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:h-5 [&>svg]:w-5 [&>svg+div]:translate-y-[-1px] [&:has(svg)]:pl-11', {
  variants: {
    variant: {
      default: 'bg-card text-foreground border-border',
      destructive: 'border-destructive/40 bg-destructive/5 text-destructive [&>svg]:text-destructive',
      warning: 'border-warning/40 bg-warning/10 text-warning-ink [&>svg]:text-warning',
      success: 'border-success/40 bg-success/10 text-success [&>svg]:text-success',
      info: 'border-primary/30 bg-primary/5 text-primary [&>svg]:text-primary',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
})

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
))
Alert.displayName = 'Alert'

const AlertTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5 ref={ref} className={cn('mb-1 font-semibold leading-none tracking-tight', className)} {...props} />
  ),
)
AlertTitle.displayName = 'AlertTitle'

const AlertDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('text-sm [&_p]:leading-relaxed', className)} {...props} />
  ),
)
AlertDescription.displayName = 'AlertDescription'

export { Alert, AlertTitle, AlertDescription }
