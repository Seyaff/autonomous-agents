import React from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms for using Siyaf, the WhatsApp ordering and AI agent service for restaurants.",
  alternates: { canonical: "/terms" },
};

export default function TermsOfService() {
  return (
    <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 20px", fontFamily: "sans-serif", color: "#333", lineHeight: "1.6" }}>
      <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "8px" }}>Terms of Service</h1>
      <p style={{ color: "#666", fontSize: "0.9rem", marginBottom: "24px" }}>These terms apply to your use of Siyaf.</p>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>1. The service</h2>
        <p>
          Siyaf provides an AI agent that answers customers on WhatsApp for restaurants, with orders, menus and
          owner tools. You must be a restaurant owner or authorised to act for one.
        </p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>2. Your account</h2>
        <p>Keep your sign-in details safe. You&apos;re responsible for activity on your account.</p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>3. Plans and payment</h2>
        <p>
          Plans, prices and the free trial are shown in the app. WhatsApp message fees are billed by Meta to your
          business, not by Siyaf. Invoices and renewals follow the billing rules shown on your Billing page.
        </p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>4. Your responsibilities</h2>
        <p>
          You&apos;re responsible for the menu, prices, opening hours and orders your restaurant handles, and for following
          WhatsApp&apos;s and Meta&apos;s business policies. You can cancel at any time from the Billing page.
        </p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>5. Data</h2>
        <p>How we handle personal data is described in our <a href="/privacy">Privacy Policy</a>.</p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>6. Changes</h2>
        <p>We may update these terms. We&apos;ll tell you about material changes in the app or by email.</p>
      </section>
    </main>
  );
}
