"use client";

import { useState } from "react";
import { Mail, MessageSquare, Building2, Check } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";

const CHANNELS = [
  { icon: Mail,        title: "Email us",        value: "hello@productiq.app",   note: "We reply within one business day" },
  { icon: MessageSquare, title: "Support",        value: "support@productiq.app", note: "For account & billing questions" },
  { icon: Building2,   title: "Enterprise sales", value: "sales@productiq.app",   note: "Custom plans, SLA, white-label" },
];

export default function ContactPage() {
  const [sent, setSent] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // UI-only: in production this posts to a contact/CRM endpoint.
    setSent(true);
  }

  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Contact"
        title="Let's talk"
        subtitle="Questions, feedback, or an enterprise use case? We'd love to hear from you."
      />

      <div className="max-w-5xl mx-auto px-6 py-16 grid md:grid-cols-2 gap-10">

        {/* channels */}
        <div className="space-y-4">
          {CHANNELS.map((c) => (
            <div key={c.title} className="glass-card p-5 flex gap-4">
              <span className="w-11 h-11 rounded-xl bg-accent-muted flex items-center justify-center shrink-0">
                <c.icon className="w-5 h-5 text-accent" />
              </span>
              <div>
                <h3 className="font-display font-semibold text-txt-primary text-sm">{c.title}</h3>
                <p className="text-accent text-sm mt-0.5">{c.value}</p>
                <p className="text-xs text-txt-muted mt-1">{c.note}</p>
              </div>
            </div>
          ))}

          <div className="glass-card p-5">
            <p className="text-sm text-txt-secondary leading-relaxed">
              <span className="text-txt-primary font-medium">Office</span><br />
              Remote-first · Karachi · Available worldwide
            </p>
          </div>
        </div>

        {/* form */}
        <div className="glass-card p-6">
          {sent ? (
            <div className="text-center py-12">
              <span className="w-14 h-14 rounded-full bg-status-success/10 flex items-center justify-center mx-auto mb-4">
                <Check className="w-7 h-7 text-status-success" />
              </span>
              <h3 className="font-display font-semibold text-txt-primary text-lg">Message sent</h3>
              <p className="text-sm text-txt-secondary mt-2">
                Thanks for reaching out — we'll get back to you within one business day.
              </p>
              <button onClick={() => setSent(false)} className="btn-secondary mt-6 px-4 py-2 text-sm">
                Send another
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-txt-secondary mb-1.5">Name</label>
                  <input required className="input-search py-2.5" placeholder="Jane Doe" />
                </div>
                <div>
                  <label className="block text-sm text-txt-secondary mb-1.5">Email</label>
                  <input required type="email" className="input-search py-2.5" placeholder="jane@company.com" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-txt-secondary mb-1.5">Company (optional)</label>
                <input className="input-search py-2.5" placeholder="Acme Inc." />
              </div>
              <div>
                <label className="block text-sm text-txt-secondary mb-1.5">How can we help?</label>
                <textarea required rows={5} className="input-search resize-none" placeholder="Tell us what you're looking for…" />
              </div>
              <button type="submit" className="btn-primary w-full py-3 text-sm">
                Send message
              </button>
              <p className="text-xs text-txt-muted text-center">
                By submitting you agree to our privacy policy. We never share your data.
              </p>
            </form>
          )}
        </div>
      </div>
    </MarketingShell>
  );
}
