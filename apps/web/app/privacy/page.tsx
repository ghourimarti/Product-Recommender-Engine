import { LegalPage } from "@/components/LegalPage";

export const metadata = { title: "Privacy Policy — ProductIQ" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      updated="June 1, 2026"
      intro="At ProductIQ, we take your privacy seriously. This policy explains what data we collect, how we use it, and the controls you have over it."
      sections={[
        {
          heading: "Information we collect",
          body: [
            "Account information: when you sign up, we collect your name and email address via our authentication provider (Clerk). We do not store your password — authentication is handled securely by Clerk.",
            "Usage data: we record the searches you make, the results returned, and basic performance metrics (latency, cost) to operate and improve the service and to enforce plan quotas.",
          ],
        },
        {
          heading: "How we use your data",
          body: [
            "We use your data to provide the product-discovery service, personalize your experience, enforce rate limits and quotas, and improve our ranking and explanation quality.",
            "We never sell your personal data. We never use your search queries to place sponsored or paid product placements.",
          ],
        },
        {
          heading: "Data sharing",
          body: [
            "To generate recommendations and explanations, your query text may be sent to our model providers (e.g. inference APIs). We send only what is necessary to fulfill the request, and our providers are bound by data-processing agreements.",
            "We use Clerk for authentication and standard cloud infrastructure for hosting. These sub-processors are contractually restricted in how they may use your data.",
          ],
        },
        {
          heading: "Data retention",
          body: [
            "We retain your search history for as long as your account is active, so you can revisit past results. You can delete individual searches at any time from your dashboard.",
            "When you delete your account, we remove your personal data and search history within 30 days, except where retention is required by law.",
          ],
        },
        {
          heading: "Your rights (GDPR)",
          body: [
            "You have the right to access, correct, export, and delete your personal data. You can exercise the right to be forgotten directly from Settings → Delete account, which triggers a full data-deletion workflow.",
            "For any data request, contact privacy@productiq.app and we will respond within the timelines required by applicable law.",
          ],
        },
        {
          heading: "Security",
          body: [
            "All data is encrypted in transit (TLS) and at rest. Access is authenticated and rate-limited, and each user's data and session are isolated from others'.",
          ],
        },
        {
          heading: "Contact",
          body: ["Questions about this policy? Email privacy@productiq.app."],
        },
      ]}
    />
  );
}
