import { Toast } from "@/components/ui/toast"
import { useToast } from "@/hooks/use-toast"

export function Toaster() {
  const { toasts, dismiss } = useToast()

  return (
    <div className="fixed top-0 right-0 z-50 flex flex-col gap-2 p-4 md:max-w-[420px]">
      {toasts.map(({ id, title, description, variant, duration }) => (
        <Toast
          key={id}
          id={id}
          title={title}
          description={description}
          variant={variant}
          duration={duration}
          onDismiss={() => dismiss(id)}
        />
      ))}
    </div>
  )
}
