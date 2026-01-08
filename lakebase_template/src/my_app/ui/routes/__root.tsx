import { ThemeProvider } from "@/components/apx/theme-provider";
import { ApxDevtools } from "@/components/apx/dev-tools";
import { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { Toaster } from "sonner";

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient;
}>()({
  component: () => (
    <ThemeProvider defaultTheme="dark" storageKey="apx-ui-theme">
      {/* DEV tools must be rendered BEFORE <Outlet /> so that ApxDevtools patches
          console.error before any route component's useEffect runs. React executes
          useEffects in tree order (siblings left-to-right, children before parents). */}
      {import.meta.env.DEV && (
        <>
          <ApxDevtools />
          <TanStackRouterDevtools position="bottom-right" />
        </>
      )}
      <Outlet />
      <Toaster richColors />
    </ThemeProvider>
  ),
});
