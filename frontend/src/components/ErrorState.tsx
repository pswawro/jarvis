export function ErrorState({ message = 'Failed to load data', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-red-400">
      <p>{message}</p>
      {onRetry && (
        <button className="mt-2 text-sm underline" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
