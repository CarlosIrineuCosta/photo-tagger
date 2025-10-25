import { type RefObject, useEffect, useState } from "react"

/**
 * Hook for observing when an element intersects with the viewport
 * @param options - IntersectionObserver options
 * @returns [ref, isIntersecting] - Ref to attach to element and boolean indicating if it's intersecting
 */
export function useIntersectionObserver(
  options: IntersectionObserverInit = {}
): [RefObject<HTMLDivElement>, boolean] {
  const [isIntersecting, setIsIntersecting] = useState(false)
  const [ref, setRef] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!ref) return

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting)
    }, options)

    observer.observe(ref)

    return () => {
      observer.disconnect()
    }
  }, [ref, options])

  // Create a ref object with a callback
  const refObject = {
    get current() {
      return ref
    },
    set current(value) {
      setRef(value)
    },
  } as RefObject<HTMLDivElement>

  return [refObject, isIntersecting]
}
