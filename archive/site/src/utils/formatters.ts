/**
 * Format token count with K/M suffix
 * @example formatTokens(1500) => "1.5K"
 * @example formatTokens(1500000) => "1.5M"
 */
export function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`
  }
  return tokens.toString()
}

/**
 * Format large numbers with comma separators
 * @example formatNumber(1500) => "1,500"
 * @example formatNumber(1500000) => "1,500,000"
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

/**
 * Format duration in milliseconds to human-readable string
 * @example formatDuration(1500) => "1.5s"
 * @example formatDuration(65000) => "1m 5s"
 * @example formatDuration(3665000) => "1h 1m"
 */
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    const remainingMinutes = minutes % 60
    return `${hours}h ${remainingMinutes}m`
  }

  if (minutes > 0) {
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  if (seconds > 0) {
    return `${seconds}s`
  }

  return `${ms}ms`
}

/**
 * Format timestamp to relative time
 * @example formatRelativeTime(Date.now() - 5000) => "5 seconds ago"
 * @example formatRelativeTime(Date.now() - 65000) => "1 minute ago"
 */
export function formatRelativeTime(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) {
    return `${days} day${days > 1 ? 's' : ''} ago`
  }
  if (hours > 0) {
    return `${hours} hour${hours > 1 ? 's' : ''} ago`
  }
  if (minutes > 0) {
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
  }
  if (seconds > 0) {
    return `${seconds} second${seconds > 1 ? 's' : ''} ago`
  }
  return 'just now'
}

/**
 * Format timestamp to time string (HH:MM:SS)
 * @example formatTime(new Date()) => "14:30:45"
 */
export function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/**
 * Format timestamp to date and time string
 * @example formatDateTime(new Date()) => "2024-01-15 14:30:45"
 */
export function formatDateTime(date: Date): string {
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/**
 * Format percentage with decimals
 * @example formatPercentage(0.856) => "85.6%"
 * @example formatPercentage(0.856, 0) => "86%"
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format cost in dollars
 * @example formatCost(1.5) => "$1.50"
 * @example formatCost(0.005) => "$0.01"
 */
export function formatCost(dollars: number): string {
  return `$${dollars.toFixed(2)}`
}
