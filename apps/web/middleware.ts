import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// The whole app surface lives under /dashboard and is auth-gated.
// Marketing pages (/, /features, /pricing, /about, /contact, /blog, legal) stay public.
const isProtected = createRouteMatcher(["/dashboard(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtected(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
