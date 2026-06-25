export function useDebouncedJob(job: () => void, delayMs = 120) {
  let timer: ReturnType<typeof window.setTimeout> | null = null

  function cancel() {
    if (timer != null) {
      window.clearTimeout(timer)
      timer = null
    }
  }

  function schedule() {
    cancel()
    timer = window.setTimeout(() => {
      timer = null
      job()
    }, delayMs)
  }

  function runNow() {
    cancel()
    job()
  }

  return { schedule, cancel, runNow }
}
